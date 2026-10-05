# PC-lane generators (pc-games.md "Auto-generating the manual lanes").
# Nix ships the generator logic and its triggers, never the game list.
# Each one reads its tool's own install manifest and rewrites that lane's
# ES-DE placeholder folder. A path watch means an install or uninstall
# shows up without a scan button.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;
  home = "/home/${cfg.user}";

  watched = {
    steam = "${home}/.local/share/Steam/steamapps";
    gog = "${home}/.config/gogdl-cli";   # TODO: real gogdl-cli manifest dir
    minecraft = "${home}/.local/share/PrismLauncher/instances";
  };

  mkGenerator = lane: {
    services."famidrive-gen-${lane}" = {
      description = "Regenerate ES-DE placeholders for the ${lane} lane";
      # Also once at boot, finished before the session starts: ES-DE only
      # reads its folders at startup. Found on the first box 2026-10-05:
      # with a tmpfs dataDir, ES-DE started 7 s before the path watch had
      # written the Steam folder, so Steam was missing from the menu.
      wantedBy = [ "display-manager.service" ];
      before = [ "display-manager.service" ];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        ExecStart = "${pkgs.famidrive-generators}/bin/famidrive-generate ${lane} ${watched.${lane}} ${cfg.dataDir}/roms/${lane}";
      };
    };
    paths."famidrive-gen-${lane}" = {
      wantedBy = [ "multi-user.target" ];
      pathConfig = {
        PathChanged = watched.${lane};
        MakeDirectory = true;
      };
    };
  };

  lanes = lib.filter hasLane [ "steam" "gog" "minecraft" ];
in
{
  config = lib.mkIf cfg.enable {
    systemd = lib.mkMerge (map mkGenerator lanes);
  };
}
