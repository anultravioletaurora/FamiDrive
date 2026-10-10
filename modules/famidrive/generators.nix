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
  # What each lane's generator reads, and the files whose changes
  # trigger it.
  source = p: {
    steam = "${p.home}/.local/share/Steam/steamapps";
    heroic = "${p.home}/.config/heroic";
    minecraft = "${p.home}/.local/share/PrismLauncher/instances";
  };
  watched = p: {
    steam = [ (source p).steam ];
    # Heroic's installed-games files, one per store (famidrive_generate.py).
    heroic = map (f: "${(source p).heroic}/${f}") [
      "gog_store/installed.json"
      "legendaryConfig/legendary/installed.json"
      "nile_config/nile/installed.json"
    ];
    minecraft = [ (source p).minecraft ];
  };

  mkGenerator = p: lane: {
    services = {
      "famidrive-gen-${lane}-${p.name}" = {
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
          # Minecraft's and Heroic's entries live in the Desktop system's
          # folder (Heroic's with an extension per store).
          ExecStart = "${pkgs.famidrive-generators}/bin/famidrive-generate ${lane} ${(source p).${lane}} ${p.roms}${folder lane}";
        };
        # Steam's (and Heroic's) art and details for new games, once the
        # menu entries are in place, without holding up the session: a
        # first run can take a minute or two (a store lookup per game).
        onSuccess = lib.optional (lane == "steam") "famidrive-steam-media-${p.name}.service"
          ++ lib.optional (lane == "heroic") "famidrive-heroic-media-${p.name}.service";
      };
    } // lib.optionalAttrs (lane == "steam") {
      "famidrive-steam-media-${p.name}" = {
        description = "Steam's art and details for ${p.displayName}'s Steam games in ES-DE";
        wants = [ "network-online.target" ];
        after = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = p.user;
          ExecStart = "${pkgs.famidrive-generators}/bin/famidrive-generate steam-media ${(source p).steam} ${p.roms}/steam";
        };
      };
    } // lib.optionalAttrs (lane == "heroic") {
      # The names, details and art in Heroic's own store cache, with images
      # from the stores' servers.
      "famidrive-heroic-media-${p.name}" = {
        description = "Heroic's art and details for ${p.displayName}'s GOG, Epic and Amazon games in ES-DE";
        wants = [ "network-online.target" ];
        after = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = p.user;
          ExecStart = "${pkgs.famidrive-generators}/bin/famidrive-generate heroic-media ${(source p).heroic} ${p.roms}/desktop";
        };
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

  folder = lane: { minecraft = "/desktop"; heroic = "/desktop"; }.${lane} or "/${lane}";

  lanes = lib.filter hasLane [ "steam" "heroic" "minecraft" ];
in
{
  config = lib.mkIf cfg.enable {
    systemd = lib.mkMerge (lib.concatMap (p: map (mkGenerator p) lanes) (lib.attrValues cfg.allPlayers));
  };
}
