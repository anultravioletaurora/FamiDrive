# ES-DE and famidrive-launch, the one wrapper every game goes through.
#
# Ownership (tv-interface.md "ES-DE config management"):
#   es_systems.xml, themes          -> only Nix writes them: plain symlinks
#   es_settings.xml                 -> ES-DE rewrites it: seed + lock a few keys
#   gamelists/, ROMs, placeholders  -> runtime-generated, Nix never touches them
#
# Each player's ES-DE reads their own ROM folder (players.<name>, `roms`):
# every shared system is a link into dataDir/roms, and the per-player
# lanes (Steam, GOG, Minecraft, Settings, Media, Ports) are their own.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };

  # Systems whose entries differ per player. Every other system is the
  # shared library's.
  perPlayer = [ "steam" "gog" "epic" "amazon" "minecraft" "settings" "media" "ports" ];
  shared = lib.filter (n: !(lib.elem n perPlayer)) (lib.attrNames cfg.systems);
  # Shared systems whose games (and so art) come from RomM.
  rommShared = lib.optionals cfg.romm.enable
    (lib.filter (n: cfg.systems.${n}.rommPlatform != null && !(cfg.localRoms ? ${n})) shared);

  # famidrive-launch <system> <rom>
  #   1. pull the newest save for this ROM from RomM (consoles only, and
  #      only for players with a RomM account: not the guest)
  #   2. run the emulator with the STEAM_GAME focus atom set, so gamescope
  #      shows the game, not ES-DE (base-os.md "The real cost: window focus")
  #   3. push the save back to RomM after the emulator exits
  famidriveLaunch = pkgs.writeShellApplication {
    name = "famidrive-launch";
    runtimeInputs = [ pkgs.romm-agent pkgs.gamescope-fg pkgs.famidrive-toast ];
    # Each emulator command is single-quoted on purpose: $ROM is exported and
    # expands inside the game's own shell, not here.
    excludeShellChecks = [ "SC2016" ];
    text = ''
      system="$1"
      ROM="$2"
      export ROM
      ${lib.optionalString cfg.romm.enable ''
        # Save sync is for players with a RomM agent config of their own.
        sync=""
        if [ -e "/etc/famidrive/romm/$(id -un).json" ]; then sync=1; fi
      ''}

      case "$system" in
      ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
        ${name})
          ${lib.optionalString (s.saveSync && cfg.romm.enable) ''[ -z "$sync" ] || romm-agent save-pull ${name} "$ROM" || echo "famidrive-launch: save pull failed, launching with local save" >&2''}
          ${s.before}
          rc=0
          gamescope-fg bash -c ${lib.escapeShellArg s.command} || rc=$?
          ${s.after}
          ${lib.optionalString (s.saveSync && cfg.romm.enable) ''[ -z "$sync" ] || romm-agent save-push ${name} "$ROM" || { echo "famidrive-launch: save push failed, timer reconcile will retry" >&2; famidrive-toast --kind alert "Save not uploaded" "It stays on this box, and FamiDrive tries RomM again within 15 minutes."; }''}
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
  #
  # Commands name famidrive-launch through /run/current-system, not its
  # store path. ES-DE reads this file once, when it starts, so a store
  # path kept a running ES-DE launching through the previous build's
  # hooks after a switch until the player quit ES-DE (#82). The system's
  # link always points at the newest build (environment.systemPackages
  # below), so a switch reaches the next launch from the menu.
  esSystemsXml = pkgs.writeText "es_systems.xml" ''
    <?xml version="1.0"?>
    <systemList>
    ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
      <system>
        <name>${name}</name>
        <fullname>${s.fullname}</fullname>
        <path>%ROMPATH%/${name}</path>
        <extension>${lib.concatStringsSep " " (s.extensions ++ map lib.toUpper s.extensions)}</extension>
        <command label="${s.fullname}">/run/current-system/sw/bin/famidrive-launch ${name} %ROM%</command>
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
    defaultText = lib.literalMD "[Art Book Next](https://github.com/anthonycaccese/art-book-next-es-de), pinned";
    example = lib.literalExpression ''{ name = "my-theme"; src = ./themes/my-theme; }'';
    description = "ES-DE theme, symlinked in and selected. null = ES-DE's bundled default.";
  };

  options.famidrive.esde.musicVolume = lib.mkOption {
    type = lib.types.ints.between 0 100;
    default = 50;
    description = ''
      Volume of the menu's music, 0 to 100. ES-DE has no music of its own:
      FamiDrive plays each player's `~/ES-DE/music` (MP3, OGG, FLAC, ...)
      shuffled behind the menu, paused while a game or app is open.
      Players without music files get none.
    '';
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

  config = lib.mkIf cfg.enable {
    # Before the session: ES-DE only reads its folders at startup.
    systemd.services.famidrive-skip-folders = lib.mkIf (cfg.esde.skipFolders != [ ]) {
      description = "Hide DLC and update folders from ES-DE";
      wantedBy = [ "display-manager.service" ];
      before = [ "display-manager.service" ];
      after = [ "local-fs.target" ];
      # As root: the shared library isn't any one player's. noload.txt is
      # an empty marker, so who owns it doesn't matter.
      serviceConfig.Type = "oneshot";
      # -L: systems from localRoms are symlinks to elsewhere.
      script = ''
        ${pkgs.findutils}/bin/find -L ${cfg.dataDir}/roms -mindepth 2 -type d \( ${
          lib.concatMapStringsSep " -o " (n: "-iname ${lib.escapeShellArg n}") cfg.esde.skipFolders
        } \) -prune -exec ${pkgs.coreutils}/bin/touch {}/noload.txt \; 2>/dev/null || true
      '';
    };

    environment.systemPackages = [ famidriveLaunch ];

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.file = {
        "ES-DE/custom_systems/es_systems.xml".source = esSystemsXml;
        "ES-DE/custom_systems/es_systems_sorting.xml".source = esSystemsSortingXml;
      } // lib.optionalAttrs (theme != null) {
        "ES-DE/themes/${theme.name}".source = theme.src;
      };

      # This player's ROM folder: a link to each shared system. Links to
      # systems this box no longer has are cleared out; their own folders
      # (Steam, Settings, ...) are left to the generators.
      home.activation.famidriveRoms = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        roms=${lib.escapeShellArg famidrivePlayer.roms}
        mkdir -p "$roms"
        for link in "$roms"/*; do
          [ -L "$link" ] || continue
          case " ${lib.concatStringsSep " " shared} " in
            *" $(basename "$link") "*) ;;
            *) rm -f "$link" ;;
          esac
        done
        ${lib.concatMapStrings (n: ''
          ln -sfn ${lib.escapeShellArg "${cfg.dataDir}/roms/${n}"} "$roms/${n}"
        '') shared}

        # Box art and screenshots from RomM, for the systems it fills:
        # ES-DE's media folder for each is a link to the library's, which
        # the RomM pull keeps. Art scraped here before is moved aside, not
        # deleted. Steam, GOG and the rest keep their own: Steam's come
        # from Steam (famidrive-generate steam-media), the rest from
        # ES-DE's scraper.
        media="$HOME/ES-DE/downloaded_media"
        before="$HOME/ES-DE/downloaded_media-before-romm"
        mkdir -p "$media"
        for link in "$media"/*; do
          [ -L "$link" ] || continue
          case "$(readlink "$link")" in
            ${lib.escapeShellArg "${cfg.dataDir}/media/"}*)
              case " ${lib.concatStringsSep " " rommShared} " in
                *" $(basename "$link") "*) ;;
                *) rm -f "$link" ;;
              esac
              ;;
          esac
        done
        ${lib.concatMapStrings (n: ''
          if [ -d "$media/${n}" ] && [ ! -L "$media/${n}" ]; then
            mkdir -p "$before"
            dest="$before/${n}"
            [ ! -e "$dest" ] || dest="$dest.$(date +%s)"
            mv "$media/${n}" "$dest"
          fi
          ln -sfn ${lib.escapeShellArg "${cfg.dataDir}/media/${n}"} "$media/${n}"
        '') rommShared}
      '';

      home.activation.famidriveEsSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${seedLib.lockKeys {
          format = "esSettings";
          target = "$HOME/ES-DE/settings/es_settings.xml";
          keys = {
            ROMDirectory = { type = "string"; value = famidrivePlayer.roms; };
            # ES-DE's Quit menu: Quit ES-DE (back to "Who's playing?"),
            # Reboot system, Power off system. The way to turn the box off
            # from a controller.
            ShowQuitMenu = { type = "bool"; value = "true"; };
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
