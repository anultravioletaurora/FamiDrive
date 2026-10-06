# ES-DE and famidrive-launch, the one wrapper every game goes through.
#
# Ownership (tv-interface.md "ES-DE config management"):
#   es_systems.xml, themes          -> only Nix writes them: plain symlinks
#   es_settings.xml                 -> ES-DE rewrites it: seed + lock a few keys
#   gamelists/, ROMs, placeholders  -> runtime-generated, Nix never touches them
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };

  # famidrive-launch <system> <rom>
  #   1. pull the newest save for this ROM from RomM (consoles only)
  #   2. run the emulator with the STEAM_GAME focus atom set, so gamescope
  #      shows the game, not ES-DE (base-os.md "The real cost: window focus")
  #   3. push the save back to RomM after the emulator exits
  famidriveLaunch = pkgs.writeShellApplication {
    name = "famidrive-launch";
    runtimeInputs = [ pkgs.romm-agent pkgs.gamescope-fg ];
    # Each emulator command is single-quoted on purpose: $ROM is exported and
    # expands inside the game's own shell, not here.
    excludeShellChecks = [ "SC2016" ];
    text = ''
      system="$1"
      ROM="$2"
      export ROM

      case "$system" in
      ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
        ${name})
          ${lib.optionalString (s.saveSync && cfg.romm.enable) ''romm-agent save-pull ${name} "$ROM" || echo "famidrive-launch: save pull failed, launching with local save" >&2''}
          rc=0
          gamescope-fg bash -c ${lib.escapeShellArg s.command} || rc=$?
          ${lib.optionalString (s.saveSync && cfg.romm.enable) ''romm-agent save-push ${name} "$ROM" || echo "famidrive-launch: save push failed, timer reconcile will retry" >&2''}
          exit "$rc"
          ;;
      '') cfg.systems)}
        *)
          echo "famidrive-launch: unknown system '$system'" >&2
          exit 64
          ;;
      esac
    '';
  };

  # Every system is redefined here, including ones ES-DE bundles, because
  # every launch has to go through famidrive-launch for save sync and focus.
  # A custom_systems entry with the same <name> replaces the bundled one.
  # The exact command-template syntax is still an open item in roms.md and pc-games.md.
  esSystemsXml = pkgs.writeText "es_systems.xml" ''
    <?xml version="1.0"?>
    <systemList>
    ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
      <system>
        <name>${name}</name>
        <fullname>${s.fullname}</fullname>
        <path>%ROMPATH%/${name}</path>
        <extension>${lib.concatStringsSep " " (s.extensions ++ map lib.toUpper s.extensions)}</extension>
        <command label="${s.fullname}">${famidriveLaunch}/bin/famidrive-launch ${name} %ROM%</command>
        <platform>${s.platform}</platform>
        <theme>${if s.theme != null then s.theme else s.platform}</theme>
      </system>
    '') cfg.systems)}
    </systemList>
  '';

  # ES-DE's custom system order: a sort key per system, by full name unless
  # the system sets its own (Settings goes last).
  esSystemsSortingXml = pkgs.writeText "es_systems_sorting.xml" ''
    <?xml version="1.0"?>
    <systemList>
    ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
      <system>
        <name>${name}</name>
        <systemsortname>${if s.sortName != null then s.sortName else s.fullname}</systemsortname>
      </system>
    '') cfg.systems)}
    </systemList>
  '';

  theme = cfg.esde.theme;
in
{
  options.famidrive.esde.theme = lib.mkOption {
    type = lib.types.nullOr (lib.types.submodule {
      options = {
        name = lib.mkOption { type = lib.types.str; description = "Folder name under ES-DE/themes/, which is also ES-DE's Theme setting."; };
        src = lib.mkOption { type = lib.types.path; description = "The theme's files."; };
      };
    });
    # Art Book Next (ES-DE edition) by Anthony Caccese: a coffee-table-book
    # look. Decided 2026-10-05 as FamiDrive's default. Pinned; bump rev+hash
    # to update. The theme repo states no license; it's fetched from the
    # author, never redistributed here.
    default = {
      name = "art-book-next-es-de";
      src = pkgs.fetchFromGitHub {
        owner = "anthonycaccese";
        repo = "art-book-next-es-de";
        rev = "d772d07109701d9bd7c9fda305bfef6601105ab8";   # 2026-02-07
        hash = "sha256-9yfLa1g5t2+bH4qyYQv2zX5QA/X5t0Jhs9gQ4J8jrlk=";
      };
    };
    description = "ES-DE theme, symlinked in and selected. null = ES-DE's bundled default.";
  };

  options.famidrive.esde.skipFolders = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    # RomM's names for a game's extra folders, plus common variants.
    default = [ "dlc" "update" "updates" "patch" "patches" "mod" "mods" "manual" "manuals" ];
    description = ''
      Folders, at any depth under a system's ROMs, that ES-DE shouldn't
      list: a game's DLC, updates and the like, which the emulator installs
      or applies, not something to launch. Matched by name, ignoring case.
      Each one gets an empty `noload.txt`, ES-DE's own "skip this folder"
      marker, at boot and on every switch.
    '';
  };

  options.famidrive.esde.music = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = "Music";
    example = "/srv/media/music";
    description = ''
      Folder of background music for ES-DE's menus (MP3 or OGG), relative
      to the home folder or absolute. ES-DE only looks in ES-DE/music, so
      that becomes a link to this folder. null: leave ES-DE/music alone.
      Music plays while ES-DE's "Play background music" (Sound settings)
      is on; ES-DE reads the folder when it starts.
    '';
  };

  config = lib.mkIf cfg.enable {
    # Before the session: ES-DE only reads its folders at startup.
    systemd.services.famidrive-skip-folders = lib.mkIf (cfg.esde.skipFolders != [ ]) {
      description = "Hide DLC and update folders from ES-DE";
      wantedBy = [ "display-manager.service" ];
      before = [ "display-manager.service" ];
      after = [ "local-fs.target" ];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
      };
      # -L: systems from localRoms are symlinks to elsewhere.
      script = ''
        ${pkgs.findutils}/bin/find -L ${cfg.dataDir}/roms -mindepth 2 -type d \( ${
          lib.concatMapStringsSep " -o " (n: "-iname ${lib.escapeShellArg n}") cfg.esde.skipFolders
        } \) -prune -exec ${pkgs.coreutils}/bin/touch {}/noload.txt \; 2>/dev/null || true
      '';
    };

    environment.systemPackages = [ famidriveLaunch ];

    home-manager.users.${cfg.user} = { config, lib, ... }: {
      home.file = {
        "ES-DE/custom_systems/es_systems.xml".source = esSystemsXml;
        "ES-DE/custom_systems/es_systems_sorting.xml".source = esSystemsSortingXml;
      } // lib.optionalAttrs (theme != null) {
        "ES-DE/themes/${theme.name}".source = theme.src;
      } // lib.optionalAttrs (cfg.esde.music != null) {
        # Out of the store: the music stays where it is, and adding a song
        # needs no rebuild, only an ES-DE restart.
        "ES-DE/music".source = config.lib.file.mkOutOfStoreSymlink
          (if lib.hasPrefix "/" cfg.esde.music then cfg.esde.music
           else "${config.home.homeDirectory}/${cfg.esde.music}");
      };

      home.activation.famidriveEsSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${seedLib.lockKeys {
          format = "esSettings";
          target = "$HOME/ES-DE/settings/es_settings.xml";
          keys = {
            ROMDirectory = { type = "string"; value = "${cfg.dataDir}/roms"; };
          } // lib.optionalAttrs (theme != null) {
            # Locked, so a rebuild always brings the chosen theme back. The
            # theme's own options (color scheme, aspect ratio) stay editable.
            Theme = { type = "string"; value = theme.name; };
          } // {
            # Everything else (screensaver, UI sounds, sort order, ...) stays
            # editable from the TV menu and survives rebuilds.
          };
        }}
      '';
    };
  };
}
