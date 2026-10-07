# Systems and their emulators. `famidrive.systems` is the single table that
# frontend.nix renders into es_systems.xml, famidrive-launch dispatches on, and
# the RomM agent uses to map RomM platforms onto ES-DE folders.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  # The stores Heroic brings: ES-DE system -> its name and Heroic's runner.
  heroicStores = {
    gog = { fullname = "GOG"; runner = "gog"; };
    epic = { fullname = "Epic Games Store"; runner = "legendary"; };
    amazon = { fullname = "Amazon Games"; runner = "nile"; };
  };
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  fw = "${cfg.dataDir}/firmware";

  # Every RetroArch-run system shares one RetroArch: one saves dir, one
  # system (firmware) dir, one controller autoconfig. [ package core-file-name ];
  # the .so names are VERIFY against each nixpkgs core.
  cores = with pkgs.libretro; {
    swanstation = [ swanstation "swanstation" ];
    mgba = [ mgba "mgba" ];
    snes9x = [ snes9x "snes9x" ];
    mupen64plus = [ mupen64plus "mupen64plus_next" ];
    genesis = [ genesis-plus-gx "genesis_plus_gx" ];
    saturn = [ beetle-saturn "mednafen_saturn" ];
    flycast = [ flycast "flycast" ];
    stella = [ stella "stella" ];
    atari800 = [ atari800 "atari800" ];
    prosystem = [ prosystem "prosystem" ];
    virtualjaguar = [ virtualjaguar "virtualjaguar" ];
    melondsds = [ melondsds "melondsds" ];
  };
  # The Ports system's command, before or after: each entry's, picked by
  # the entry's extension.
  byExtension = part:
    let parts = lib.filterAttrs (_: p: p.${part} != "") config.famidrive.ports;
    in lib.optionalString (parts != { }) ''
      case "$ROM" in
      ${lib.concatStrings (lib.mapAttrsToList (ext: p: ''
        *${ext})
          ${p.${part}}
          ;;
      '') parts)}
      esac
    '';

  retroarch = pkgs.retroarch.withCores (_: map builtins.head (lib.attrValues cores));
  core = name: "${builtins.head cores.${name}}/lib/retroarch/cores/${builtins.elemAt cores.${name} 1}_libretro.so";

  # A RetroArch system. Cores that write <rom>.srm get save sync now; the
  # rest (Saturn .bkr, Dreamcast VMUs, melonDS DS) wait until their save
  # files are mapped (roms.md "Mapping saves to games").
  ra = { coreName, saves ? true }: {
    # The game's real path, not ES-DE's link to it: a .cue names its .bin
    # next to itself, and the core looks beside whatever path it's given.
    # Found on the first box 2026-10-07: every PlayStation game in a
    # folder (Pepsiman/Pepsiman.cue, .bin) failed to find its .bin.
    command = ''${retroarch}/bin/retroarch -f -L ${core coreName} "$(readlink -f "$ROM")"'';
    emulator = "retroarch-${coreName}";
    firmwareDir = "retroarch";
    saveSync = saves;
    saveLayout = { kind = "retroarch-srm"; root = "~/.config/retroarch/saves"; };
  };

  systemType = types.submodule {
    options = {
      fullname = mkOption {
        type = types.str;
        description = "The system's name in ES-DE's menu.";
      };
      extensions = mkOption {
        type = types.listOf types.str;
        description = "File extensions ES-DE lists as games for this system, with the dot.";
      };
      command = mkOption {
        type = types.str;
        description = "The emulator's command line. `$ROM` is replaced with the game's path.";
      };
      # Found on the first box 2026-10-06: Clone Hero's score push and
      # bindings save were in its command, and a quit skipped them.
      before = mkOption {
        type = types.lines;
        default = "";
        description = "Shell run just before the command, outside it.";
      };
      after = mkOption {
        type = types.lines;
        default = "";
        description = ''
          Shell run just after the command, outside it. Quitting (Select +
          Start) ends the command's whole process group, so anything that
          must still happen after a quit (pushing a save) goes here, never
          in the command.
        '';
      };
      contentCategories = mkOption {
        type = types.listOf types.str;
        default = [ ];
        description = ''
          RomM file categories (its subfolders) pulled along with the game
          into its folder, such as a Switch game's `update` and `dlc`.
        '';
      };
      rommPlatform = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "The RomM platform (its slug) this system's games come from. null: not from RomM.";
      };
      saveSync = mkOption {
        type = types.bool;
        default = false;
        description = "Pull each game's save from RomM before it starts and push it back after.";
      };
      # Per-emulator layout mapping is still an open question (roms.md
      # "Console saves: RomM sync API only").
      saveLayout = mkOption {
        type = types.nullOr types.attrs;
        default = null;
        description = ''
          Where the emulator keeps saves and how a game maps to its save,
          for the RomM agent: `{ kind; root; }`, with a kind the agent
          knows (`dolphin-gci-folder`, `eden-title-id`, `retroarch-srm`, ...).
        '';
      };
      platform = mkOption {
        type = types.str;
        default = "pc";
        description = "ES-DE's platform for it, which picks its scraper.";
      };
      # Found on the first box 2026-10-05: Steam and Media showed the "pc"
      # theme's IBM PC logo.
      theme = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "The ES-DE theme folder for its logo and art. null: the platform's.";
      };
      sortName = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "Where it sits in ES-DE's system list, which is otherwise by full name. Never shown. null: the full name.";
      };
      emulator = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "The emulator's name, sent to RomM with each save so its web UI shows what made it.";
      };
      firmwareDir = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = ''
          The folder under the library's `firmware/` this system's firmware
          goes to. null: the RomM platform. RetroArch systems share
          `retroarch`.
        '';
      };
    };
  };
in
{
  options.famidrive.systems = mkOption {
    type = types.attrsOf systemType;
    default = { };
    description = ''
      The systems in ES-DE's menu, by ES-DE's folder name for them. Every
      console FamiDrive supports is already here (with the `roms` lane);
      set one's fields to change it, or add a system of your own.
    '';
  };

  # One Ports system for everything that isn't a console or a store:
  # Minecraft's instances, Clone Hero, ... Each kind of entry has its own
  # file extension, the command that starts it ($ROM is the entry), and
  # shell for before and after it (the systems' before and after).
  options.famidrive.ports = mkOption {
    type = types.attrsOf (types.submodule {
      options = {
        command = mkOption {
          type = types.lines;
          description = "Shell that runs the entry. `$ROM` is the entry's file.";
        };
        before = mkOption {
          type = types.lines;
          default = "";
          description = "Shell run just before the command, outside it.";
        };
        after = mkOption {
          type = types.lines;
          default = "";
          description = "Shell run just after the command, outside it, even when the player quits with Select + Start.";
        };
      };
    });
    default = { };
    internal = true;
  };

  config = lib.mkIf cfg.enable {
    # The library's RetroArch BIOS files (romm-agent firmwareDir), linked
    # into this player's RetroArch system folder. Anything a core made
    # there itself is left alone.
    famidrive.sessionSetup = lib.mkIf (hasLane "roms") ''
      sys="$HOME/.config/retroarch/system"
      mkdir -p "$sys"
      # Links to files the library no longer has go, so a core can make
      # its own folder there again. Found on the first box 2026-10-07:
      # Mupen64plus pointed at a library folder gone after a firmware
      # pull, the N64 core couldn't write its game database there, and
      # Mario Party 3 got the wrong save type and wouldn't start.
      for t in "$sys"/*; do
        if [ -L "$t" ] && [ ! -e "$t" ]; then
          case "$(readlink "$t")" in ${fw}/retroarch/*) rm -f "$t" ;; esac
        fi
      done
      for f in ${fw}/retroarch/*; do
        [ -e "$f" ] || continue
        t="$sys/$(basename "$f")"
        if [ -e "$t" ] && [ ! -L "$t" ]; then continue; fi
        ln -sfn "$f" "$t"
      done
      # SwanStation (PlayStation) looks for its BIOS by one name per
      # region, scph5501.bin for the US, and nothing else. Found on the
      # first box 2026-10-07: RomM's BIOS was SCPH1001.BIN, the original
      # US one, and every game failed to start. Any BIOS of the region,
      # whatever its name or case, is linked under the expected name.
      for want in "scph5501.bin:scph5501 scph7001 scph7501 scph1001 scph101 scph9001" \
                  "scph5502.bin:scph5502 scph7502 scph7002 scph1002 scph102 scph9002" \
                  "scph5500.bin:scph5500 scph7000 scph7500 scph1000 scph3000 scph3500"; do
        name="''${want%%:*}"
        [ -e "$sys/$name" ] && continue
        for b in ''${want#*:}; do
          f=$(find "$sys" -maxdepth 1 -iname "$b.bin" -print -quit)
          if [ -n "$f" ]; then ln -sfn "$(basename "$f")" "$sys/$name"; break; fi
        done
      done
    '';

    famidrive.systems = lib.mkMerge [
      (lib.mkIf (hasLane "roms") {
        gc = {
          fullname = "Nintendo GameCube";
          extensions = [ ".iso" ".rvz" ".gcz" ".ciso" ];
          command = ''${pkgs.dolphin-emu}/bin/dolphin-emu --batch --exec="$ROM"'';
          rommPlatform = "ngc";
          emulator = "dolphin";
          saveSync = true;
          platform = "gc";
          saveLayout = { kind = "dolphin-gci-folder"; root = "~/.local/share/dolphin-emu/GC"; };
        };
        wii = {
          fullname = "Nintendo Wii";
          extensions = [ ".iso" ".rvz" ".wbfs" ];
          command = ''${pkgs.dolphin-emu}/bin/dolphin-emu --batch --exec="$ROM"'';
          rommPlatform = "wii";
          emulator = "dolphin";
          saveSync = true;
          platform = "wii";
          saveLayout = { kind = "dolphin-wii-title"; root = "~/.local/share/dolphin-emu/Wii/title"; };
        };
        psx = ra { coreName = "swanstation"; } // {
          fullname = "Sony PlayStation";
          extensions = [ ".chd" ".cue" ".pbp" ];
          rommPlatform = "psx";   # RomM's folder slug (its display slug is "ps"; the agent matches either)
          platform = "psx";
        };
        ps2 = {
          fullname = "Sony PlayStation 2";
          extensions = [ ".iso" ".chd" ];
          command = ''${pkgs.pcsx2}/bin/pcsx2-qt -batch -fullscreen -- "$ROM"'';
          rommPlatform = "ps2";
          emulator = "pcsx2";
          saveSync = true;
          platform = "ps2";
          saveLayout = { kind = "pcsx2-folder-memcard"; root = "~/.config/PCSX2/memcards"; card = "Mcd001.ps2"; };
        };
        ps3 = {
          fullname = "Sony PlayStation 3";
          extensions = [ ".iso" ".ps3" ];
          command = ''${pkgs.rpcs3}/bin/rpcs3 --no-gui "$ROM"'';
          rommPlatform = "ps3";
          emulator = "rpcs3";
          saveSync = true;
          platform = "ps3";
          saveLayout = { kind = "rpcs3-savedata"; root = "~/.config/rpcs3/dev_hdd0/home/00000001/savedata"; };
        };
        switch = {
          fullname = "Nintendo Switch";
          extensions = [ ".nsp" ".xci" ];
          # Revised 2026-10-05: Eden, not Ryubing (roms.md). Its Qt UI runs
          # on XWayland under gamescope (QT_QPA_PLATFORM=xcb).
          # Eden only knows -f (main_window.cpp). Found on the first box 2026-10-05:
          # --fullscreen was taken as a game path and ignored, so gamescope
          # stretched the normal window, menu bar and status bar included.
          # In single-window mode, -f hides both.
          # A game listed in switch.ryujinx.games runs in Ryujinx instead
          # (ryujinx.nix's before hook sets $FAMIDRIVE_RYUJINX). --no-gui:
          # no game list around it, and Ryujinx quits when the game does.
          command = lib.optionalString (cfg.switch.ryujinx.games != [ ]) ''
            if [ -n "''${FAMIDRIVE_RYUJINX:-}" ]; then
              exec ${lib.getExe cfg.switch.ryujinx.package} --no-gui --fullscreen "$ROM"
            fi
          '' + ''QT_QPA_PLATFORM=xcb ${lib.getExe pkgs.eden} -f -g "$ROM"'';
          rommPlatform = "switch";
          emulator = "eden";
          # Updates and DLC from RomM, beside each game, where Eden reads
          # them (romm-agent eden-gamedir): one copy for every player.
          contentCategories = [ "update" "dlc" ];
          saveSync = true;
          platform = "switch";
          # One folder per game, named by title ID, under the profile's folder:
          # <root>/<edenProfileId>/<title ID>/. No save index to write on restore.
          # The profile is each player's (players.<name>.edenProfileId).
          saveLayout = { kind = "eden-title-id"; root = "~/.local/share/eden/nand/user/save/0000000000000000"; };
        };
        xbox360 = {
          fullname = "Microsoft Xbox 360";
          extensions = [ ".iso" ".xex" ];
          command = ''${pkgs.xenia-netplay}/bin/xenia_canary "$ROM"'';   # fork choice still open
          rommPlatform = "xbox360";
          emulator = "xenia";
          saveSync = true;
          platform = "xbox360";
          saveLayout = { kind = "xenia-content"; root = "~/.local/share/Xenia/content"; };   # profile: each player's xeniaXuid. TODO: verify path
        };

        # Added 2026-10-05: every other RomM platform except Windows/PC, the
        # computer platforms (mac, appleii), ones Linux can't emulate (ios,
        # series-x-s, switch-2) and OG Xbox (project phase 2). rommPlatform is
        # RomM's folder slug. Standalone emulators' launch flags: VERIFY.

        # Handhelds and cartridge consoles: RetroArch, so no binding step
        # (controllers.md) and .srm saves that sync from day one.
        gb = ra { coreName = "mgba"; } // {
          fullname = "Nintendo Game Boy"; rommPlatform = "gb"; platform = "gb";
          extensions = [ ".gb" ".zip" ];
        };
        gbc = ra { coreName = "mgba"; } // {
          fullname = "Nintendo Game Boy Color"; rommPlatform = "gbc"; platform = "gbc";
          extensions = [ ".gbc" ".gb" ".zip" ];
        };
        gba = ra { coreName = "mgba"; } // {
          fullname = "Nintendo Game Boy Advance"; rommPlatform = "gba"; platform = "gba";
          extensions = [ ".gba" ".zip" ];
        };
        snes = ra { coreName = "snes9x"; } // {
          fullname = "Super Nintendo"; rommPlatform = "snes"; platform = "snes";
          extensions = [ ".sfc" ".smc" ".zip" ];
        };
        n64 = ra { coreName = "mupen64plus"; } // {
          fullname = "Nintendo 64"; rommPlatform = "n64"; platform = "n64";
          extensions = [ ".z64" ".n64" ".v64" ".zip" ];
        };
        n64dd = ra { coreName = "mupen64plus"; saves = false; } // {
          # Needs the 64DD IPL BIOS from RomM in the shared firmware dir. Disk
          # saves are written back into the disk image: not mapped yet.
          fullname = "Nintendo 64DD"; rommPlatform = "64dd"; platform = "n64dd";
          extensions = [ ".ndd" ".d64" ];
        };
        genesis = ra { coreName = "genesis"; } // {
          fullname = "Sega Genesis / Mega Drive"; rommPlatform = "genesis"; platform = "genesis";
          extensions = [ ".md" ".gen" ".bin" ".smd" ".zip" ];
        };
        mastersystem = ra { coreName = "genesis"; } // {
          fullname = "Sega Master System"; rommPlatform = "sms"; platform = "mastersystem";
          extensions = [ ".sms" ".zip" ];
        };
        gamegear = ra { coreName = "genesis"; } // {
          fullname = "Sega Game Gear"; rommPlatform = "gamegear"; platform = "gamegear";
          extensions = [ ".gg" ".zip" ];
        };
        saturn = ra { coreName = "saturn"; saves = false; } // {
          fullname = "Sega Saturn"; rommPlatform = "saturn"; platform = "saturn";   # BIOS from RomM
          extensions = [ ".chd" ".cue" ".m3u" ];
        };
        dreamcast = ra { coreName = "flycast"; saves = false; } // {
          fullname = "Sega Dreamcast"; rommPlatform = "dc"; platform = "dreamcast";
          extensions = [ ".chd" ".cdi" ".gdi" ".m3u" ];
        };
        atari2600 = ra { coreName = "stella"; saves = false; } // {
          fullname = "Atari 2600"; rommPlatform = "atari2600"; platform = "atari2600";
          extensions = [ ".a26" ".bin" ".zip" ];
        };
        atari5200 = ra { coreName = "atari800"; saves = false; } // {
          fullname = "Atari 5200"; rommPlatform = "atari5200"; platform = "atari5200";   # BIOS from RomM
          extensions = [ ".a52" ".bin" ".zip" ];
        };
        atari7800 = ra { coreName = "prosystem"; saves = false; } // {
          fullname = "Atari 7800"; rommPlatform = "atari7800"; platform = "atari7800";
          extensions = [ ".a78" ".bin" ".zip" ];
        };
        atarijaguar = ra { coreName = "virtualjaguar"; saves = false; } // {
          fullname = "Atari Jaguar"; rommPlatform = "jaguar"; platform = "atarijaguar";
          extensions = [ ".j64" ".jag" ".zip" ];
        };
        nds = ra { coreName = "melondsds"; saves = false; } // {
          fullname = "Nintendo DS"; rommPlatform = "nds"; platform = "nds";
          extensions = [ ".nds" ".zip" ];
        };
        dsi = ra { coreName = "melondsds"; saves = false; } // {
          # DSi mode needs the DSi BIOS/firmware/NAND from RomM.
          fullname = "Nintendo DSi"; rommPlatform = "nintendo-dsi"; platform = "nds";
          extensions = [ ".nds" ".dsi" ];
        };

        # Standalone emulators. Save sync waits for each one's layout.
        n3ds = {
          fullname = "Nintendo 3DS"; rommPlatform = "3ds"; platform = "n3ds"; emulator = "azahar";
          extensions = [ ".3ds" ".cci" ".cxi" ".app" ".3dsx" ];
          command = ''${lib.getExe pkgs.azahar} -f "$ROM"'';
        };
        new3ds = {
          fullname = "New Nintendo 3DS"; rommPlatform = "new-nintendo-3ds"; platform = "n3ds"; emulator = "azahar";
          extensions = [ ".3ds" ".cci" ".cxi" ".app" ".3dsx" ];
          command = ''${lib.getExe pkgs.azahar} -f "$ROM"'';
        };
        psp = {
          fullname = "Sony PSP"; rommPlatform = "psp"; platform = "psp"; emulator = "ppsspp";
          extensions = [ ".iso" ".cso" ".pbp" ".chd" ];
          command = ''${pkgs.ppsspp-sdl}/bin/PPSSPPSDL --fullscreen "$ROM"'';
        };
        wiiu = {
          # Was "later" in roms.md; in from 2026-10-05 with the rest of RomM.
          fullname = "Nintendo Wii U"; rommPlatform = "wiiu"; platform = "wiiu"; emulator = "cemu";
          extensions = [ ".wua" ".wud" ".wux" ".rpx" ];
          command = ''${lib.getExe pkgs.cemu} -f -g "$ROM"'';
        };
      })

      # PC lanes: the placeholder file's *content* is the launch ID, written by
      # famidrive-generators. No RomM save sync; PC saves are pc-saves.nix's job.
      (lib.mkIf (hasLane "steam") {
        steam = {
          fullname = "Steam";
          extensions = [ ".steam" ];
          # -applaunch returns at once; gamescope-fg --steam waits for the game.
          command = ''${pkgs.gamescope-fg}/bin/gamescope-fg --steam "$(cat "$ROM")"'';
          theme = "steam";
        };
      })
      # GOG, the Epic Games Store and Amazon Games, each its own system,
      # all through Heroic. --no-gui launches the game without Heroic's
      # window and quits Heroic when the game ends (read in Heroic 2.22's
      # source, 2026-10-07), so the command lasts as long as the game.
      # The entry's file holds the game's app name in that store.
      (lib.mkIf (hasLane "heroic") (lib.mapAttrs (system: s: {
        inherit (s) fullname;
        extensions = [ ".${system}" ];
        command = ''${pkgs.heroic}/bin/heroic --no-gui --no-sandbox "heroic://launch?appName=$(cat "$ROM")&runner=${s.runner}"'';
        theme = system;
      }) heroicStores))
      (lib.mkIf (cfg.ports != { }) {
        ports = {
          fullname = "Ports";
          theme = "ports";   # Art Book Next's ports art
          extensions = lib.attrNames cfg.ports;
          command = byExtension "command";
          before = byExtension "before";
          after = byExtension "after";
        };
      })
    ];

    # Minecraft's instances are Ports entries (Found on the first box
    # 2026-10-06: as a system of their own they showed as a second Ports,
    # with the same art). Every instance starts fullscreen, whoever made
    # it (pkgs/famidrive-prism).
    famidrive.ports = lib.mkIf (hasLane "minecraft") {
      ".prism".command = ''
        ${pkgs.famidrive-prism}/bin/famidrive-prism fullscreen "$HOME/.local/share/PrismLauncher/instances/$(cat "$ROM")"
        ${pkgs.prismlauncher}/bin/prismlauncher --launch "$(cat "$ROM")"
      '';
    };

    programs.steam = lib.mkIf (hasLane "steam") {
      enable = true;
      extraCompatPackages = [ pkgs.proton-ge-bin ];
    };

    environment.systemPackages =
      lib.optionals (hasLane "heroic") [ pkgs.heroic ]
      ++ lib.optionals (hasLane "minecraft") [ pkgs.prismlauncher ];

    # Seeded/locked emulator settings. Only the keys this design depends
    # on are locked; everything else stays editable from each emulator's
    # own UI and survives rebuilds.
    famidrive.playerHome = { lib, ... }: {
      home.activation.famidriveEmulators = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/dolphin-emu/Dolphin.ini";
          keys.Core = {
            # One folder per game, not one shared memory card for every game.
            # Without this, GameCube saves can't map to per-ROM RomM saves.
            SlotA = 8;   # TODO: verify the enum value for "GCI Folder"
          };
        }}
        ${seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/dolphin-emu/GFX.ini";
          # HD texture packs from RomM (romm-agent textures): Dolphin's
          # "Load Custom Textures", and preloading them so they don't
          # stutter in as they're first seen.
          keys.Settings = { HiresTextures = "True"; CacheHiresTextures = "True"; };
        }}
        ${seedLib.lockKeys {
          format = "keyValue";
          target = "$HOME/.config/retroarch/retroarch.cfg";
          keys = {
            # Each player's own, with the library's BIOS files linked in at
            # the start of each session (below): cores also write there
            # (Mupen64Plus its ini and shader cache), and the library's
            # firmware folder is read-only to players.
            system_directory = "~/.config/retroarch/system";
            savefile_directory = "~/.config/retroarch/saves";   # RetroArch expands ~ itself
            sort_savefiles_by_content_enable = "false";
            # Every save straight in saves/, where the RomM agent's
            # retroarch-srm layout looks (<game>.srm). RetroArch's own
            # default puts each core's in a folder of its own. Found on the
            # first box 2026-10-07: Mario Party 3's save was in
            # saves/Mupen64Plus-Next/, so it had never synced.
            sort_savefiles_enable = "false";
            video_fullscreen = "true";
          };
        }}
        # Saves already sorted into a core's folder move up next to the
        # rest. One already there is newer (RetroArch wrote it with
        # sorting off), so the sorted copy is left where it is.
        for f in "$HOME/.config/retroarch/saves"/*/*.srm; do
          [ -e "$f" ] || continue
          to="$HOME/.config/retroarch/saves/$(basename "$f")"
          [ -e "$to" ] || mv "$f" "$to"
        done
        ${seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/PCSX2/inis/PCSX2.ini";
          keys = {
            Folders.Bios = "${fw}/ps2";
            EmuCore.McdFolderAutoManage = "true";   # per-game folder memcards; TODO: verify key
          };
        }}
        ${seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/eden/qt-config.ini";
          # Qt-style keys: a setting only counts when its \default flag is false.
          keys.UI = {
            # -f only hides the menu and status bars in single-window mode.
            "singleWindowMode\\default" = "false";
            singleWindowMode = "true";
            # famidrive-quit's SIGTERM becomes a window close in Eden; with
            # the default "always ask" it waits on a dialog nobody can reach
            # and gets SIGKILLed. 2 = Ask_Never (settings_enums.h).
            "confirmStop\\default" = "false";
            confirmStop = 2;
          };
        }}
        # Eden's profile (players.<name>.edenProfileId) isn't seeded: profiles.dat
        # is binary. Open question in roms.md.
        # Xenia profile: pin each player's xeniaXuid once the fork's profile
        # config format is known (depends on the Xenia fork decision).
      '';
    };
  };
}
