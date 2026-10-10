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

  # What the performance overlay can show, by FamiDrive's name, and the
  # MangoHud settings for each (MangoHud 0.8; with legacy_layout off it
  # shows exactly these, in this order).
  stats = {
    fps = [ "fps" ];
    frametime = [ "frametime" "frame_timing" ];   # the number, then its graph
    cpu = [ "cpu_stats" ];                        # CPU load, %
    cpu_temp = [ "cpu_temp" ];
    gpu = [ "gpu_stats" ];                        # GPU load, %
    gpu_temp = [ "gpu_temp" ];
    ram = [ "ram" ];                              # memory in use
    vram = [ "vram" ];                            # graphics memory in use
  };
  stat = types.enum (lib.attrNames stats);
  value = types.oneOf [ types.bool types.int types.float types.str ];

  mangohudConf = perf: lib.concatStringsSep "\n" ([
    "legacy_layout=0"
    "position=${perf.position}"
  ] ++ lib.concatMap (s: stats.${s}) perf.show
    ++ lib.optionals (perf.layout == "row") [ "horizontal" "horizontal_stretch=0" "hud_compact" ]
    ++ [ "background_alpha=0.4" "round_corners=8" ]
    ++ lib.mapAttrsToList (k: v: if v == true then k else if v == false then "${k}=0" else "${k}=${toString v}") perf.settings
  ) + "\n";

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
        show = opt (types.listOf stat) [ "fps" "frametime" "gpu" "gpu_temp" "cpu" "cpu_temp" "ram" "vram" ] ''
          What it shows, in this order: `"fps"` (frame rate), `"frametime"`
          (frame time, and its graph), `"cpu"` and `"gpu"` (load, in
          percent), `"cpu_temp"` and `"gpu_temp"`, `"ram"` and `"vram"`
          (memory and graphics memory in use).
        '';
        layout = opt (types.enum [ "column" "row" ]) "column" ''
          `"column"`: one stat under another. `"row"`: all of them on one
          line, a bar along the edge it's placed at.
        '';
        settings = opt (types.attrsOf value) { } ''
          Any other MangoHud setting, by its name in MangoHud.conf, over
          FamiDrive's: `true` turns one on, `false` off, anything else is
          its value. For example `{ font_size = 20; background_alpha = 0.2; }`.
        '';
      };
    };

  # Each player's settings, the box's filling in what they leave unset.
  resolve = p:
    let mine = p.overlays or { toasts = { }; performance = { }; };
        pick = section: name: let v = mine.${section}.${name} or null; in
          if v == null then cfg.overlays.${section}.${name} else v;
    in {
      toasts = { position = pick "toasts" "position"; hide = pick "toasts" "hide"; };
      performance = lib.genAttrs [ "enable" "position" "show" "layout" "settings" ] (pick "performance");
    };

  toastSpec = pkgs.writeText "famidrive-toast.json" (builtins.toJSON {
    theme = if cfg.esde.theme != null then "${cfg.esde.theme.src}" else null;
    default = { inherit (cfg.overlays.toasts) position hide; };
    players = lib.mapAttrs' (_: p: lib.nameValuePair p.user (resolve p).toasts) cfg.allPlayers;
  });
in
{
  options.famidrive.overlays = overlayOptions false // {
    toastSpec = mkOption {
      type = types.path;
      internal = true;
      readOnly = true;
      description = "The toast daemon's settings, for the sessions and \"Who's playing?\".";
    };
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
    famidrive.overlays.toastSpec = toastSpec;

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
        xdg.configFile."MangoHud/MangoHud.conf".text = mangohudConf perf;
      };
  };
}
