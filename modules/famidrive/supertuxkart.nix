# SuperTuxKart, in ES-DE's Ports system. Free and open source, and made
# for controllers: its menus, multiplayer setup (each player presses a
# button on their own pad) and on-screen keyboard all work from a pad, so
# it needs nothing else.
#
# Its config and story progress are in ~/.config/supertuxkart, each
# player's own. They don't sync with RomM yet.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
in
{
  options.famidrive.superTuxKart = {
    enable = lib.mkEnableOption "SuperTuxKart, in ES-DE's Ports system";
  };

  config = lib.mkIf (cfg.enable && cfg.superTuxKart.enable) {
    environment.systemPackages = [ pkgs.supertuxkart ];

    # Another kind of Ports entry, like Clone Hero's: a .port file whose
    # content says which.
    famidrive.ports.".port".command = ''
      case "$(cat "$ROM")" in
        supertuxkart) ${lib.getExe pkgs.supertuxkart} ;;
      esac
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveSuperTuxKart = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/ports"}
        printf supertuxkart > ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/SuperTuxKart.port"}
      '';
    };
  };
}
