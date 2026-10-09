# Clone Hero, in ES-DE's Ports system. Songs are the box's, shared by
# every player like ROMs: charts listed in Nix by their Chorus Encore md5,
# downloaded to the library disk (not the Nix store: a song library runs
# to many GB), plus a folder for songs added by hand. Profiles, scores and
# Clone Hero's own settings stay each player's; the TV's audio and video
# calibration is the box's, so it's set here once for everyone. Each
# player's scores and profiles sync with RomM like a console game's save.
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

  sync = cfg.romm.enable && ch.romm.entry != null;

  # Scores and profiles: what a player would miss on another box. Clone
  # Hero's settings and bindings stay put (they belong to this box's TV
  # and guitars), and so does the Unity prefs file, which also holds a
  # login token.
  saveLayout = {
    kind = "files";
    root = "~";
    paths = [
      ".config/unity3d/srylain Inc_/Clone Hero/scoredata.bin"
      ".config/unity3d/srylain Inc_/Clone Hero/scoresext.bin"
      ".clonehero/profiles.ini"
    ];
  };

  # A profile for every player, in "Who's playing?" order, then guests.
  playerSpec = builtins.toJSON {
    profiles = map (p: p.displayName)
      (lib.sortOn (p: (if p.name == cfg.primaryPlayer then "0" else "1") + p.name)
        (lib.filter (p: !p.isGuest) (lib.attrValues cfg.allPlayers)))
      ++ lib.genList (i: "Guest ${toString (i + 1)}") ch.guestProfiles;
    stamps = [ "${dir}/songs/.famidrive-stamp" "${dir}/local" ];
    bindings = if ch.sharedBindings then "${dir}/bindings" else null;
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
        Charts for every player on this box, in Clone Hero and in YARG
        (`famidrive.yarg`), by name (the file's name) and
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

    romm.entry = mkOption {
      type = types.nullOr types.str;
      default = "Clone Hero";
      description = ''
        The RomM entry each player's Clone Hero scores and profiles are
        saved under, by name. RomM keeps saves only for games in its
        library, so add one by hand, with "Add Physical Game" (no file
        needed). null keeps scores on this box only.
      '';
    };

    sharedBindings = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Controller bindings are the box's: when anyone binds a guitar (or
        rebinds one) and exits Clone Hero, every player gets the same
        bindings the next time it starts. They're kept on the library disk
        (clonehero/bindings). false leaves each player's own.
      '';
    };

    videoOffset = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "Clone Hero's video calibration in milliseconds, the same for every player. null leaves each player's own.";
    };
  };

  config = lib.mkMerge [
  # The song library: Clone Hero's, and YARG's too (yarg.nix), which reads
  # the same chart formats.
  (lib.mkIf (cfg.enable && (ch.enable || cfg.yarg.enable)) {
    # songs/ is the managed library, local/ is for songs added by hand
    # (any player can copy into it).
    systemd.tmpfiles.rules = [
      "d ${dir} 0755 famidrive-library famidrive -"
      "d ${dir}/songs 0755 famidrive-library famidrive -"
      "d ${dir}/local 2775 famidrive-library famidrive -"
    ];

    systemd.services.famidrive-clonehero-songs = {
      description = "Download this box's Clone Hero and YARG songs";
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
  })

  (lib.mkIf (cfg.enable && ch.enable) {
    environment.systemPackages = [ pkgs.clonehero pkgs.famidrive-clonehero ];

    # An entry in the Ports system (emulators.nix). Its setup and the
    # saving after it run in famidrive-launch, outside the game, so a
    # quit with Select + Start doesn't skip them. Scores come down before
    # the profiles are seeded, so a new box doesn't take its freshly
    # seeded profiles.ini for a save RomM lacks. $sync: famidrive-launch's,
    # set for players with a RomM agent config of their own.
    famidrive.ports.".port" = {
      before = ''
        if [ "$(cat "$ROM")" = clonehero ]; then
          ${lib.optionalString sync ''
            [ -z "$sync" ] || romm-agent save-pull clonehero app:clonehero \
              || echo "famidrive-launch: Clone Hero scores not pulled" >&2
          ''}
          ${pkgs.famidrive-clonehero}/bin/famidrive-clonehero player ${lib.escapeShellArg playerSpec} \
            || echo "famidrive-launch: couldn't set up Clone Hero" >&2
        fi
      '';
      command = ''
        case "$(cat "$ROM")" in
          clonehero) ${pkgs.clonehero}/bin/clonehero ;;
        esac
      '';
      after = ''
        if [ "$(cat "$ROM")" = clonehero ]; then
          ${pkgs.famidrive-clonehero}/bin/famidrive-clonehero played ${lib.escapeShellArg playerSpec} \
            || echo "famidrive-launch: Clone Hero's bindings not saved for the box" >&2
          ${lib.optionalString sync ''
            [ -z "$sync" ] || romm-agent save-push clonehero app:clonehero \
              || echo "famidrive-launch: Clone Hero scores not pushed, reconcile will retry" >&2
          ''}
        fi
      '';
    };

    # The box's guitar bindings (any player writes them).
    systemd.tmpfiles.rules =
      lib.optional ch.sharedBindings "f ${dir}/bindings 0664 famidrive-library famidrive -";

    famidrive.romm.apps = lib.mkIf sync {
      clonehero = { title = "Clone Hero"; rom = ch.romm.entry; emulator = "clonehero"; inherit saveLayout; };
    };

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
  })
  ];
}
