# What's drawn over the TV on top of games and the menu, and where: toasts
# (pkgs/famidrive-toast) and the performance overlay (MangoHud, through
# gamescope's --mangoapp). One place says where each goes, box-wide, and
# each player can move theirs. Both are composited by gamescope as its
# external overlay, so neither takes focus or input from a game.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;

  # MangoHud's names, which toasts use too, so one list serves every
  # overlay. No dead center: that's where the game is.
  position = types.enum [
    "top-left" "top-center" "top-right"
    "middle-left" "middle-right"
    "bottom-left" "bottom-center" "bottom-right"
  ];
  kinds = types.enum [ "notice" "alert" "progress" "achievement" ];

  # The box's options, or (player = true) a player's, where null means
  # "the box's".
  overlayOptions = player:
    let opt = type: default: description: mkOption ({
      type = if player then types.nullOr type else type;
      default = if player then null else default;
      inherit description;
    } // lib.optionalAttrs player { defaultText = lib.literalMD "the box's (`famidrive.overlays`)"; });
    in {
      toasts = {
        position = opt position "bottom-right" "Where toasts show up.";
        hide = opt (types.listOf kinds) [ ] ''
          Kinds of toast not to show: `"notice"` (a save uploaded and the
          like), `"alert"` (something went wrong), `"progress"` (downloads
          and other background work), `"achievement"` (RetroAchievements
          unlocks). Toasts are always on; this is how to quiet some.
        '';
      };
      performance = {
        enable = opt types.bool false ''
          MangoHud's performance overlay (frame rate, frame times, CPU and
          GPU load and temperatures) over every game and the menu, through
          gamescope's `--mangoapp`. Takes effect at the player's next
          session.
        '';
        position = opt position "middle-left" "Where the performance overlay shows up.";
      };
    };

  # Each player's settings, the box's filling in what they leave unset.
  resolve = p:
    let mine = p.overlays or { toasts = { }; performance = { }; };
        pick = section: name: let v = mine.${section}.${name} or null; in
          if v == null then cfg.overlays.${section}.${name} else v;
    in {
      toasts = { position = pick "toasts" "position"; hide = pick "toasts" "hide"; };
      performance = { enable = pick "performance" "enable"; position = pick "performance" "position"; };
    };

  toastSpec = pkgs.writeText "famidrive-toast.json" (builtins.toJSON {
    theme = if cfg.esde.theme != null then "${cfg.esde.theme.src}" else null;
    default = { inherit (cfg.overlays.toasts) position hide; };
    players = lib.mapAttrs' (_: p: lib.nameValuePair p.user (resolve p).toasts) cfg.allPlayers;
  });
in
{
  options.famidrive.overlays = overlayOptions false // {
    resolved = mkOption {
      type = types.attrsOf types.anything;
      internal = true;
      readOnly = true;
      description = "Each player's overlay settings by Linux account, the box's filling in.";
    };
  };

  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.overlays = overlayOptions true;
    });
  };

  config = lib.mkIf cfg.enable {
    famidrive.overlays.resolved = lib.mapAttrs' (_: p: lib.nameValuePair p.user (resolve p)) cfg.allPlayers;

    environment.systemPackages = [ pkgs.famidrive-toast ];
    # Where the box's own services (the library pull) reach whoever is on
    # the TV: each session's toast daemon puts a socket here. setgid, so
    # the sockets are group famidrive, which players and the library
    # account share; nobody else can send.
    systemd.tmpfiles.rules = [ "d /run/famidrive-toast 2770 root famidrive -" ];

    # Before ES-DE, so the session's own work can toast. It ends with the
    # session: gamescope's X server going away closes it.
    famidrive.sessionSetup = ''
      ${pkgs.famidrive-toast}/bin/famidrive-toast daemon ${toastSpec} "$(id -un)" &
    '';

    famidrive.playerHome = { famidrivePlayer, ... }:
      let perf = (resolve famidrivePlayer).performance; in
      lib.mkIf perf.enable {
        xdg.configFile."MangoHud/MangoHud.conf".text = ''
          position=${perf.position}
          fps
          frametime
          frame_timing
          gpu_stats
          gpu_temp
          cpu_stats
          cpu_temp
          ram
          vram
          background_alpha=0.4
          round_corners=8
        '';
      };
  };
}
