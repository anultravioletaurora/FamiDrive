# Ryujinx (Ryubing) for the Switch games that need it. Eden runs every
# other Switch game; a game listed here runs in Ryujinx instead, from the
# same entry in ES-DE's Switch system. Found on the first box 2026-10-07:
# HewDraw Remix (Smash Ultimate) is built on Skyline plugins, which Eden,
# like yuzu before it, can't run, and Ryujinx can.
#
# A Ryujinx game shares everything else with Eden: updates and DLC from
# the library's Switch folder, the player's keys and firmware (copied or
# linked from their Eden), mods from RomM (romm-agent links those into
# Ryujinx's own layout), and the save, which is bridged through Eden's
# folder before and after each launch (famidrive-ryujinx), so RomM syncs
# it from the one place.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  ryu = cfg.switch.ryujinx;
in
{
  options.famidrive.switch.ryujinx = {
    games = mkOption {
      type = types.listOf (types.strMatching "0100[0-9A-Fa-f]{12}");
      default = [ ];
      example = [ "01006A800016E000" ];
      description = ''
        Switch games to run in Ryujinx instead of Eden, by title ID. For
        games, or mods, that only work there: HewDraw Remix for Smash
        Ultimate (`01006A800016E000`) needs Skyline plugins, which Eden
        can't run. Each player's save for the game is the same one Eden
        would use, so switching a game between the two keeps it.
      '';
    };

    package = mkOption {
      type = types.package;
      default = pkgs.ryubing;
      defaultText = lib.literalExpression "pkgs.ryubing";
      description = "The Ryujinx to run them with: nixpkgs' Ryubing, or a canary build.";
    };
  };

  config = lib.mkIf (cfg.enable && ryu.games != [ ] && lib.elem "roms" cfg.lanes) {
    environment.systemPackages = [ ryu.package pkgs.famidrive-ryujinx ];

    # famidrive-launch's hooks, around the Switch system's command
    # (emulators.nix, which runs Ryujinx when $FAMIDRIVE_RYUJINX is set).
    # The save pull from RomM has already put the player's save in Eden's
    # folder, and the push after this takes it from there.
    famidrive.systems.switch = {
      before = ''
        rom="$(readlink -f "$(dirname "$ROM")")/$(basename "$ROM")"
        tid=$(${pkgs.jq}/bin/jq -r --arg p "$rom" '.[$p].title_id // empty' ${lib.escapeShellArg "${cfg.dataDir}/index.json"} 2>/dev/null || true)
        case " ${lib.toUpper (lib.concatStringsSep " " ryu.games)} " in
          *" ''${tid^^} "*)
            export FAMIDRIVE_RYUJINX="$tid"
            ${pkgs.famidrive-ryujinx}/bin/famidrive-ryujinx setup ${lib.escapeShellArg (builtins.toJSON {
              library = "${cfg.dataDir}/roms/switch";
              inherit (cfg.controllers) faceButtons;
              edenKeys = "~/.local/share/eden/keys";   # expanded by famidrive-ryujinx
              edenFirmware = "~/.local/share/eden/nand/system/Contents/registered";
              defaults = pkgs.famidrive-ryujinx.defaultConfig;
              sdl = "${pkgs.SDL2}/lib/libSDL2.so";
            })} || echo "famidrive-launch: couldn't set up Ryujinx" >&2
            ${pkgs.famidrive-ryujinx}/bin/famidrive-ryujinx save-in "$tid" \
              || echo "famidrive-launch: save not copied into Ryujinx" >&2
            ;;
        esac
      '';
      after = ''
        if [ -n "''${FAMIDRIVE_RYUJINX:-}" ]; then
          ${pkgs.famidrive-ryujinx}/bin/famidrive-ryujinx save-out "$FAMIDRIVE_RYUJINX" \
            || echo "famidrive-launch: Ryujinx's save not copied back" >&2
        fi
      '';
    };
  };
}
