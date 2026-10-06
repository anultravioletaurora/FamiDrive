# The RomM agent: the box's only link to RomM, over HTTPS.
#   - library pull: mirror the library (or one collection) locally, write gamelist.xml
#   - firmware pull: bios/ for each platform (PS1/PS2/PS3/Switch), then
#     run each emulator's firmware install where one exists
#   - save sync: called by famidrive-launch before/after each game, plus a
#     timer reconcile for the crash/power-cut cases
# No NFS mount anywhere (roms.md "Library sync: pulling ROMs from RomM").
#
# Two roles. The library (ROMs, cover art, firmware) is the box's, shared
# by every player: pulled by the famidrive-library account with the
# primary player's token, into dataDir, where players can only read it.
# Saves are each player's own: pulled and pushed by that player, with their
# own token, into their own home, as their own RomM device. The guest has
# no RomM account, so no save sync.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;

  systems = lib.mapAttrs (_: s: {
    inherit (s) rommPlatform saveSync saveLayout extensions emulator firmwareDir;
  }) (lib.filterAttrs (_: s: s.rommPlatform != null) cfg.systems);

  # Everything the agent needs to know, generated from the same
  # famidrive.systems table ES-DE and famidrive-launch use.
  libraryConfig = {
    url = cfg.romm.url;
    tokenFile = null;   # systemd hands it over (LoadCredential, below)
    deviceName = config.networking.hostName;
    collection = cfg.romm.collection;
    dataDir = cfg.dataDir;
    firmwarePlatforms = cfg.romm.firmwarePlatforms;
    inherit systems;
  };

  playerConfig = p: {
    url = cfg.romm.url;
    tokenFile = p.tokenFile;
    owner = p.owner;
    inherit (p) displayName;   # names a new Eden profile
    deviceName = config.networking.hostName;
    dataDir = cfg.dataDir;
    playerRoms = p.roms;   # famidrive-launch hands over ROM paths in here
    gamelistDir = "${p.home}/ES-DE/gamelists";
    edenProfileId = p.edenProfileId;
    xeniaXuid = p.xeniaXuid;
    inherit systems;
  };

  rommPlayers = lib.filterAttrs (_: p: p.tokenFile != null) cfg.allPlayers;
  primary = cfg.allPlayers.${cfg.primaryPlayer};

  background = {
    Type = "oneshot";
    Nice = 10;
    IOSchedulingClass = "idle";   # first bulk sync shouldn't stutter a game
  };
in
{
  config = lib.mkIf (cfg.enable && cfg.romm.enable && lib.elem "roms" cfg.lanes) (lib.mkMerge [{
    environment.systemPackages = [ pkgs.romm-agent ];

    # romm-agent reads /etc/famidrive/romm/<user>.json for whoever runs it.
    environment.etc = {
      "famidrive/romm/library.json".text = builtins.toJSON libraryConfig;
    } // lib.mapAttrs' (_: p: lib.nameValuePair "famidrive/romm/${p.user}.json" {
      text = builtins.toJSON (playerConfig p);
    }) rommPlayers;

    systemd.services.romm-library-pull = {
      description = "Mirror this box's RomM library locally";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      environment.ROMM_AGENT_CONFIG = "/etc/famidrive/romm/library.json";
      # The library disk, and its folders with the right owners first.
      # Found on the first box 2026-10-06: a freshly formatted library disk
      # was mounted after tmpfiles had run, so dataDir was root's and the
      # first pull couldn't make roms/.
      unitConfig.RequiresMountsFor = cfg.dataDir;
      serviceConfig = background // {
        ExecStartPre = "+${config.systemd.package}/bin/systemd-tmpfiles --create --prefix=${cfg.dataDir}";
        User = "famidrive-library";
        Group = "famidrive";
        # The primary player's token, read by systemd as root, so it can
        # stay readable only by that player.
        LoadCredential = "romm-token:${toString primary.tokenFile}";
        ExecStart = [
          "${pkgs.romm-agent}/bin/romm-agent pull"
          "${pkgs.romm-agent}/bin/romm-agent firmware"
        ];
      };
    };
    systemd.timers.romm-library-pull = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2min";
        OnUnitActiveSec = "30min";
        Persistent = true;
      };
    };
  } {
    # Backstop for the post-exit push famidrive-launch couldn't do (crash,
    # power cut, killed session), one per player. Conflicts are flagged by
    # RomM, never resolved silently here.
    systemd.services = lib.mapAttrs' (name: p: lib.nameValuePair "romm-save-reconcile-${name}" {
      description = "Reconcile ${p.displayName}'s console saves with RomM";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = background // {
        User = p.user;
        ExecStart = "${pkgs.romm-agent}/bin/romm-agent reconcile";
      };
    }) rommPlayers;
    systemd.timers = lib.mapAttrs' (name: _: lib.nameValuePair "romm-save-reconcile-${name}" {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "1min";
        OnUnitActiveSec = "15min";
      };
    }) rommPlayers;
  }]);
}
