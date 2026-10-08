# 3D Pinball Space Cadet, in ES-DE's Ports system, through
# k4zmu2a/SpaceCadetPinball, a reverse-engineered port of the game that
# came with Windows.
#
# The port is open source; the game's data (PINBALL.DAT, its sounds and
# music) is Microsoft's. nixpkgs' package downloads that data from an
# archive and bundles it. FamiDrive provides no game files, so the
# engine is built here without it, and plays the owner's own copy from a
# folder on the library disk, shared by every player. Full Tilt! Pinball's
# data (CADET.DAT) works too.
#
# The port looks for its data in the folder it's started from first, so
# it's started from that one. High scores and settings are each player's,
# in ~/.local/share/SpaceCadetPinball.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  dir = "${cfg.dataDir}/space-cadet-pinball";
  engine = pkgs.space-cadet-pinball.overrideAttrs { postInstall = ""; };
in
{
  options.famidrive.spaceCadetPinball = {
    enable = lib.mkEnableOption ''
      3D Pinball Space Cadet, in ES-DE's Ports system. It plays your own
      copy of the game's files (from Windows), copied into
      `space-cadet-pinball/` on the library disk: PINBALL.DAT, PINBALL.MID,
      the .WAV sounds and the rest of the game's folder'';
  };

  config = lib.mkIf (cfg.enable && cfg.spaceCadetPinball.enable) {
    # Any player can copy the game's files in.
    systemd.tmpfiles.rules = [ "d ${dir} 2775 famidrive-library famidrive -" ];

    famidrive.ports.".port".command = ''
      case "$(cat "$ROM")" in
        spacecadet)
          if [ -z "$(find ${lib.escapeShellArg dir} -maxdepth 1 \( -iname pinball.dat -o -iname cadet.dat \) 2>/dev/null)" ]; then
            ${pkgs.famidrive-toast}/bin/famidrive-toast --kind alert "Space Cadet Pinball needs its game files" \
              "Copy PINBALL.DAT and the rest of the game's folder from your own Windows copy into ${dir}."
          else
            (cd ${lib.escapeShellArg dir} && ${lib.getExe engine})
          fi
          ;;
      esac
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveSpaceCadet = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/ports"}
        printf spacecadet > ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/Space Cadet Pinball.port"}
      '';
    };
  };
}
