# Miis. Games take them from the console's own Mii database, not from
# their saves, so the per-game save sync doesn't carry them (#140).
#
# Wii: the database is one file in Dolphin's NAND,
# shared2/menu/FaceLib/RFL_DB.dat (room for 100 Miis), and Miis are made
# in the Mii Channel, a title installed in that NAND with the Wii System
# Menu, from the owner's own Wii. Seen on the first box 2026-10-08: the
# file, magic RNOD, 779,968 bytes, and the Mii Channel at
# title/00010002/48414341, which `dolphin-emu --nand_title` starts by
# itself.
#
# The Mii Channel's entry in ES-DE's Wii list is a file this module
# writes into the shared Wii folder, "Mii Channel.nand", holding its title
# ID; the Wii command boots .nand files from Dolphin's NAND.
#
# Each player's database syncs as the save of a "Mii Channel" entry in
# RomM, added by hand on the Wii platform with "Add Physical Game" (no
# file), like an app's (Clone Hero's scores): pulled before every Wii game
# and the Mii Channel, pushed after. The library pull skips physical
# entries, and the Wii save sync skips .nand files, so neither touches it.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  wii = cfg.miis.wii;
  sync = cfg.romm.enable && wii.romm.entry != null;
  hasRoms = lib.elem "roms" cfg.lanes;

  dolphinWii = "~/.local/share/dolphin-emu/Wii";
  miiChannel = "0001000248414341";   # HACA
  entry = "${cfg.dataDir}/roms/wii/Mii Channel.nand";
in
{
  options.famidrive.miis.wii = {
    enable = mkEnableOption ''
      Wii Miis: the Mii Channel in ES-DE's Wii list, and each player's
      Miis synced with RomM, as the save of the Mii Channel's RomM entry
      (`miis.wii.romm.entry`). The Mii Channel itself comes from the
      owner's own Wii: it has to be installed in Dolphin's Wii NAND, with
      the Wii System Menu'';

    romm.entry = mkOption {
      type = types.nullOr types.str;
      default = "Mii Channel";
      description = ''
        The RomM entry each player's Wii Miis are saved under, by name.
        Add it to RomM by hand, on the Wii platform, with "Add Physical
        Game" (it needs no file). null keeps Miis on this box only.
      '';
    };
  };

  config = lib.mkIf (cfg.enable && hasRoms && wii.enable) {
    # The Mii Channel's entry, in the shared Wii folder. A service rather
    # than tmpfiles alone: the library disk can mount after tmpfiles runs.
    systemd.services.famidrive-mii-channel = {
      description = "Put the Mii Channel in ES-DE's Wii list";
      wantedBy = [ "multi-user.target" ];
      unitConfig.RequiresMountsFor = cfg.dataDir;
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = "famidrive-library";
        Group = "famidrive";
      };
      script = ''
        mkdir -p ${lib.escapeShellArg "${cfg.dataDir}/roms/wii"}
        printf ${miiChannel} > ${lib.escapeShellArg entry}
      '';
    };

    famidrive.systems.wii = {
      # The Mii Channel only runs when it's installed. Without it, say so,
      # instead of Dolphin's own error.
      before = ''
        case "$ROM" in
          *.nand)
            if [ ! -d "$HOME/.local/share/dolphin-emu/Wii/title/$(cut -c1-8 "$ROM")/$(cut -c9-16 "$ROM")" ]; then
              famidrive-toast --kind alert "The Mii Channel isn't installed" \
                "Add a Wii System Menu zip to RomM's Wii firmware, or install it in Dolphin (Tools, Perform Online System Update)."
              exit 0
            fi
            ;;
        esac
      '' + lib.optionalString sync ''
        [ -z "$sync" ] || romm-agent save-pull wii-miis app:wii-miis \
          || echo "famidrive-launch: Wii Miis not pulled" >&2
      '';
      after = lib.optionalString sync ''
        [ -z "$sync" ] || romm-agent save-push wii-miis app:wii-miis \
          || echo "famidrive-launch: Wii Miis not pushed, reconcile will retry" >&2
      '';
    };

    famidrive.romm.apps = lib.mkIf sync {
      wii-miis = {
        title = "Wii Miis";
        rom = wii.romm.entry;
        emulator = "dolphin";
        saveLayout = { kind = "files"; root = dolphinWii; paths = [ "shared2/menu/FaceLib/RFL_DB.dat" ]; };
      };
    };
  };
}
