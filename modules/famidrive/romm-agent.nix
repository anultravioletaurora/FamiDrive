# The RomM agent: the box's only link to RomM, over HTTPS.
#   - library pull: mirror the library (or one collection) locally, write gamelist.xml
#   - firmware pull: bios/ for each platform (PS1/PS2/PS3/Switch), then
#     run each emulator's firmware install where one exists
#   - save sync: called by famidrive-launch before/after each game, plus a
#     timer reconcile for the crash/power-cut cases
# No NFS mount anywhere (roms.md "Library sync: pulling ROMs from RomM").
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;

  # Everything the agent needs to know, generated from the same
  # famidrive.systems table ES-DE and famidrive-launch use.
  agentConfig = pkgs.writeText "romm-agent.json" (builtins.toJSON {
    url = cfg.romm.url;
    tokenFile = cfg.romm.tokenFile;
    owner = cfg.owner;
    deviceName = config.networking.hostName;
    collection = cfg.romm.collection;
    dataDir = cfg.dataDir;
    gamelistDir = "/home/${cfg.user}/ES-DE/gamelists";
    firmwarePlatforms = cfg.romm.firmwarePlatforms;
    edenProfileId = cfg.identity.edenProfileId;
    systems = lib.mapAttrs (_: s: {
      inherit (s) rommPlatform saveSync saveLayout extensions emulator firmwareDir;
    }) (lib.filterAttrs (_: s: s.rommPlatform != null) cfg.systems);
  });

  serviceBase = {
    environment.ROMM_AGENT_CONFIG = "${agentConfig}";
    serviceConfig = {
      Type = "oneshot";
      User = cfg.user;
      Nice = 10;
      IOSchedulingClass = "idle";   # first bulk sync shouldn't stutter a game
    };
  };
in
{
  config = lib.mkIf (cfg.enable && cfg.romm.enable && lib.elem "roms" cfg.lanes) {
    environment.systemPackages = [ pkgs.romm-agent ];
    environment.sessionVariables.ROMM_AGENT_CONFIG = "${agentConfig}";

    systemd.services.romm-library-pull = serviceBase // {
      description = "Mirror this box's RomM library locally";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = serviceBase.serviceConfig // {
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

    # Backstop for the post-exit push famidrive-launch couldn't do (crash,
    # power cut, killed session). Conflicts are flagged by RomM, never
    # resolved silently here.
    systemd.services.romm-save-reconcile = serviceBase // {
      description = "Reconcile local console saves with RomM";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = serviceBase.serviceConfig // {
        ExecStart = "${pkgs.romm-agent}/bin/romm-agent reconcile";
      };
    };
    systemd.timers.romm-save-reconcile = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "1min";
        OnUnitActiveSec = "15min";
      };
    };
  };
}
