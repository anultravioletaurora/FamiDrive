# osu! (lazer), in ES-DE's Ports system. The official build
# (osu-lazer-bin, ppy's AppImage) rather than nixpkgs' build from source:
# only official builds can submit scores online.
#
# osu! is played with a mouse, a pen tablet or a touchscreen, plus a
# keyboard (or a tablet's buttons) to tap. It has no controller navigation,
# so a box needs those plugged in to play it.
#
# Tablets: lazer has OpenTabletDriver built in, which reads tablets through
# their hidraw devices. Those are root-only by default, so the player at
# the TV gets them through OpenTabletDriver's udev rules (uaccess), the
# same as YARG's instruments. Only the rules: OpenTabletDriver's own
# daemon (hardware.opentabletdriver) would fight lazer for the tablet.
#
# Scores, beatmaps and the account live in ~/.local/share/osu, each
# player's own. Scores are kept by osu!'s servers when the player signs in,
# so nothing goes to RomM.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption;
  cfg = config.famidrive;
in
{
  options.famidrive.osu = {
    enable = mkEnableOption ''
      osu! (lazer), in ES-DE's Ports system, played with a mouse, a pen
      tablet or a touchscreen, and a keyboard. Pen tablets work through
      osu!'s built-in OpenTabletDriver'';
  };

  config = lib.mkIf (cfg.enable && cfg.osu.enable) {
    services.udev.packages = [ pkgs.opentabletdriver ];
    environment.systemPackages = [ pkgs.osu-lazer-bin ];

    # Another kind of Ports entry, like Clone Hero's and YARG's: a .port
    # file whose content says which.
    famidrive.ports.".port".command = ''
      case "$(cat "$ROM")" in
        osu) ${lib.getExe pkgs.osu-lazer-bin} ;;
      esac
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveOsu = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/ports"}
        printf osu > ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/osu!.port"}
      '';
    };
  };
}
