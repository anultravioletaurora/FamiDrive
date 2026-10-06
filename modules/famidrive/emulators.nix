# Systems and their emulators. `famidrive.systems` is the single table that
# frontend.nix renders into es_systems.xml, famidrive-launch dispatches on, and
# the RomM agent uses to map RomM platforms onto ES-DE folders.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;
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
  retroarch = pkgs.retroarch.withCores (_: map builtins.head (lib.attrValues cores));
  core = name: "${builtins.head cores.${name}}/lib/retroarch/cores/${builtins.elemAt cores.${name} 1}_libretro.so";

  # A RetroArch system. Cores that write <rom>.srm get save sync now; the
  # rest (Saturn .bkr, Dreamcast VMUs, melonDS DS) wait until their save
  # files are mapped (roms.md "Mapping saves to games").
  ra = { coreName, saves ? true }: {
    command = ''${retroarch}/bin/retroarch -f -L ${core coreName} "$ROM"'';
    emulator = "retroarch-${coreName}";
    firmwareDir = "retroarch";
    saveSync = saves;
    saveLayout = { kind = "retroarch-srm"; root = "~/.config/retroarch/saves"; };
  };

  systemType = types.submodule {
    options = {
      fullname = mkOption { type = types.str; };
      extensions = mkOption { type = types.listOf types.str; };
      # Emulator command. "$ROM" is substituted by famidrive-launch.
      command = mkOption { type = types.str; };
      # RomM platform slug this system is pulled from (null = PC lane, not RomM-backed).
      rommPlatform = mkOption { type = types.nullOr types.str; default = null; };
      # Pull/push saves through RomM's sync API around each launch. Consoles only.
      saveSync = mkOption { type = types.bool; default = false; };
      # Where this emulator keeps saves, and how a ROM maps to its save
      # path. Read by the RomM agent. Per-emulator layout mapping is still
      # an open question (roms.md "Console saves: RomM sync API only").
      saveLayout = mkOption { type = types.nullOr types.attrs; default = null; };
      platform = mkOption { type = types.str; default = "pc"; };   # ES-DE scraper platform
      # ES-DE theme folder for the system's logo and art (default: platform).
      # Found on the first box 2026-10-05: Steam and Media showed the "pc"
      # theme's IBM PC logo.
      theme = mkOption { type = types.nullOr types.str; default = null; };
      # Sent to RomM with each save, so its web UI shows what made it.
      emulator = mkOption { type = types.nullOr types.str; default = null; };
      # Folder under dataDir/firmware/ this system's firmware lands in
      # (default: the RomM platform slug). RetroArch systems share "retroarch".
      firmwareDir = mkOption { type = types.nullOr types.str; default = null; };
    };
  };
in
{
  options.famidrive.systems = mkOption {
    type = types.attrsOf systemType;
    default = { };
  };

  config = lib.mkIf cfg.enable {
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
          command = ''QT_QPA_PLATFORM=xcb ${lib.getExe pkgs.eden} -f -g "$ROM"'';
          rommPlatform = "switch";
          emulator = "eden";
          saveSync = true;
          platform = "switch";
          # One folder per game, named by title ID, under the profile's folder:
          # <root>/<edenProfileId>/<title ID>/. No save index to write on restore.
          saveLayout = { kind = "eden-title-id"; root = "~/.local/share/eden/nand/user/save/0000000000000000"; profile = cfg.identity.edenProfileId; };
        };
        xbox360 = {
          fullname = "Microsoft Xbox 360";
          extensions = [ ".iso" ".xex" ];
          command = ''${pkgs.xenia-netplay}/bin/xenia_canary "$ROM"'';   # fork choice still open
          rommPlatform = "xbox360";
          emulator = "xenia";
          saveSync = true;
          platform = "xbox360";
          saveLayout = { kind = "xenia-content"; root = "~/.local/share/Xenia/content"; profile = cfg.identity.xeniaXuid; };   # TODO: verify path
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
      (lib.mkIf (hasLane "gog") {
        gog = {
          fullname = "GOG";
          extensions = [ ".gog" ];
          command = ''${pkgs.gogdl-cli}/bin/gogdl-cli launch "$(cat "$ROM")"'';   # TODO: verify subcommand
        };
      })
      (lib.mkIf (hasLane "minecraft") {
        minecraft = {
          fullname = "Minecraft";
          extensions = [ ".prism" ];
          # Every instance starts fullscreen, whoever made it (pkgs/famidrive-prism).
          command = ''
            ${pkgs.famidrive-prism}/bin/famidrive-prism fullscreen "$HOME/.local/share/PrismLauncher/instances/$(cat "$ROM")"
            ${pkgs.prismlauncher}/bin/prismlauncher --launch "$(cat "$ROM")"
          '';
          # Art Book Next has no Minecraft art; its generic "ports" art is
          # closest. Without it ES-DE falls back to the "pc" (IBM) logo.
          theme = "ports";
        };
      })
    ];

    programs.steam = lib.mkIf (hasLane "steam") {
      enable = true;
      extraCompatPackages = [ pkgs.proton-ge-bin ];
    };

    environment.systemPackages =
      lib.optionals (hasLane "gog") [ pkgs.gogdl-cli pkgs.tcli ]
      ++ lib.optionals (hasLane "minecraft") [ pkgs.prismlauncher ];

    # Seeded/locked emulator settings. Only the keys this design depends
    # on are locked; everything else stays editable from each emulator's
    # own UI and survives rebuilds.
    home-manager.users.${cfg.user} = { lib, ... }: {
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
          format = "keyValue";
          target = "$HOME/.config/retroarch/retroarch.cfg";
          keys = {
            system_directory = "${fw}/retroarch";   # every core's BIOS, flat (romm-agent firmwareDir)
            savefile_directory = "~/.config/retroarch/saves";   # RetroArch expands ~ itself
            sort_savefiles_by_content_enable = "false";
            video_fullscreen = "true";
          };
        }}
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
        # Eden's profile (cfg.identity.edenProfileId) isn't seeded: profiles.dat
        # is binary. Open question in roms.md.
        # Xenia profile: pin cfg.identity.xeniaXuid once the fork's profile
        # config format is known (depends on the Xenia fork decision).
      '';
    };
  };
}
