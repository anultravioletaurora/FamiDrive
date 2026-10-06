# PC-lane generators (pc-games.md "Auto-generating the manual lanes").
# Nix ships the generator logic and its triggers, never the game list.
# Each one reads its tool's own install manifest and rewrites that lane's
# ES-DE placeholder folder. A path watch means an install or uninstall
# shows up without a scan button.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  # One generator per player and lane: each player's own Steam library and
  # Prism instances fill their own menu (their `roms` folder), so a game
  # installed in two players' homes shows up for each of them.
  watched = p: {
    steam = "${p.home}/.local/share/Steam/steamapps";
    gog = "${p.home}/.config/gogdl-cli";   # TODO: real gogdl-cli manifest dir
    minecraft = "${p.home}/.local/share/PrismLauncher/instances";
  };

  mkGenerator = p: lane: {
    services."famidrive-gen-${lane}-${p.name}" = {
      description = "Regenerate ${p.displayName}'s ES-DE placeholders for the ${lane} lane";
      # Also once at boot, finished before the session starts: ES-DE only
      # reads its folders at startup. Found on the first box 2026-10-05:
      # with a tmpfs dataDir, ES-DE started 7 s before the path watch had
      # written the Steam folder, so Steam was missing from the menu.
      wantedBy = [ "display-manager.service" ];
      before = [ "display-manager.service" ];
      serviceConfig = {
        Type = "oneshot";
        User = p.user;
        # Minecraft's entries live in the Ports system's folder.
        ExecStart = "${pkgs.famidrive-generators}/bin/famidrive-generate ${lane} ${(watched p).${lane}} ${p.roms}/${folder lane}";
      };
    };
    # No MakeDirectory: it would make the folder as root inside the
    # player's home (and a root-owned Steam folder breaks Steam's first
    # start). systemd watches the nearest parent that exists instead.
    paths."famidrive-gen-${lane}-${p.name}" = {
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = (watched p).${lane};
    };
  };

  folder = lane: { minecraft = "ports"; }.${lane} or lane;

  lanes = lib.filter hasLane [ "steam" "gog" "minecraft" ];
in
{
  config = lib.mkIf cfg.enable {
    systemd = lib.mkMerge (lib.concatMap (p: map (mkGenerator p) lanes) (lib.attrValues cfg.allPlayers));
  };
}
