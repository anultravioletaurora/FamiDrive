# Clone Hero, in ES-DE's Ports system. Songs are the box's, shared by
# every player like ROMs: charts listed in Nix by their Chorus Encore md5,
# downloaded to the library disk (not the Nix store: a song library runs
# to many GB), plus a folder for songs added by hand. Profiles, scores and
# Clone Hero's own settings stay each player's; the TV's audio and video
# calibration is the box's, so it's set here once for everyone.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  ch = cfg.cloneHero;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  dir = "${cfg.dataDir}/clonehero";

  songsSpec = builtins.toJSON {
    dir = "${dir}/songs";
    inherit (ch) songs onlyListed;
  };

  # A profile for every player, in "Who's playing?" order, then guests.
  playerSpec = builtins.toJSON {
    profiles = map (p: p.displayName)
      (lib.sortOn (p: (if p.name == cfg.primaryPlayer then "0" else "1") + p.name)
        (lib.filter (p: !p.isGuest) (lib.attrValues cfg.allPlayers)))
      ++ lib.genList (i: "Guest ${toString (i + 1)}") ch.guestProfiles;
    stamps = [ "${dir}/songs/.famidrive-stamp" ];
  };
in
{
  options.famidrive.cloneHero = {
    enable = mkEnableOption "Clone Hero, in ES-DE's Ports system";

    songs = mkOption {
      type = types.attrsOf types.str;
      default = { };
      example = { "AFI - Miss Murder" = "05185565cb931978c11de73d3048206e"; };
      description = ''
        Charts for every player on this box, by name (the file's name) and
        Chorus Encore md5 (enchor.us: a chart's download is
        files.enchor.us/<md5>.sng). Downloaded to the library disk at boot
        and whenever this list changes. A changed md5 downloads again.
      '';
    };

    onlyListed = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Remove charts from the managed library that are no longer listed.
        Songs added by hand go in `clonehero/local` on the library disk
        (dataDir), which is never touched.
      '';
    };

    guestProfiles = mkOption {
      type = types.ints.between 0 8;
      default = 3;
      description = ''
        Clone Hero profiles named "Guest 1", "Guest 2", ... next to one for
        each player, so friends can jump in on another instrument with a
        profile of their own.
      '';
    };

    audioOffset = mkOption {
      type = types.nullOr types.int;
      default = null;
      example = 200;
      description = ''
        Clone Hero's audio calibration in milliseconds, the same for every
        player: it belongs to the TV and speakers, not the person. null
        leaves each player's own (Settings → Calibration).
      '';
    };

    videoOffset = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "Clone Hero's video calibration in milliseconds, the same for every player. null leaves each player's own.";
    };
  };

  config = lib.mkIf (cfg.enable && ch.enable) {
    environment.systemPackages = [ pkgs.clonehero pkgs.famidrive-clonehero ];

    famidrive.systems.ports = {
      fullname = "Ports";
      theme = "ports";   # Art Book Next's ports art
      extensions = [ ".port" ];
      command = ''
        case "$(cat "$ROM")" in
          clonehero) ${pkgs.clonehero}/bin/clonehero ;;
        esac
      '';
    };

    # songs/ is the managed library, local/ is for songs added by hand
    # (any player can copy into it).
    systemd.tmpfiles.rules = [
      "d ${dir} 0755 famidrive-library famidrive -"
      "d ${dir}/songs 0755 famidrive-library famidrive -"
      "d ${dir}/local 2775 famidrive-library famidrive -"
    ];

    systemd.services.famidrive-clonehero-songs = {
      description = "Download this box's Clone Hero songs";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      unitConfig.RequiresMountsFor = cfg.dataDir;
      restartTriggers = [ songsSpec ];   # again whenever the list changes
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = "famidrive-library";
        Group = "famidrive";
        Nice = 10;
        IOSchedulingClass = "idle";
        ExecStartPre = "+${config.systemd.package}/bin/systemd-tmpfiles --create --prefix=${dir}";
        ExecStart = "${pkgs.famidrive-clonehero}/bin/famidrive-clonehero songs ${lib.escapeShellArg songsSpec}";
      };
    };

    # By name (systemPackages), so a fix to it doesn't restart the TV.
    famidrive.sessionSetup = ''
      famidrive-clonehero player ${lib.escapeShellArg playerSpec} \
        || echo "famidrive-session: couldn't set up Clone Hero" >&2
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveCloneHero = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/ports"}
        printf clonehero > ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/Clone Hero.port"}
        mkdir -p "$HOME/.clonehero"
        touch "$HOME/.clonehero/settings.ini"
        ${seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.clonehero/settings.ini";
          keys = {
            # The box's songs, then hand-added ones, then the player's own.
            directories = {
              path0 = "${dir}/songs";
              path1 = "${dir}/local";
              path2 = "${famidrivePlayer.home}/.clonehero/Songs";
            };
            video = {
              fullscreen = 1;
              framerate = if cfg.display.refresh != null then cfg.display.refresh else 60;
            };
          } // lib.optionalAttrs (ch.audioOffset != null || ch.videoOffset != null) {
            offsets = lib.optionalAttrs (ch.audioOffset != null) { audio = ch.audioOffset; }
              // lib.optionalAttrs (ch.videoOffset != null) { video = ch.videoOffset; };
          };
        }}
      '';
    };
  };
}
