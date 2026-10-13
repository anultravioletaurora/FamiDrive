# PC stores other than Steam (#205): which launcher each one's games go
# through, and the Lutris system.
#
# Each store is either Heroic's (Epic, by default) or Lutris's (the rest),
# or off. Where their games show in ES-DE follows the launcher:
#   Lutris  every game it has installed, in the Lutris system
#   Heroic  Epic's in the Epic system; GOG's and Amazon's in Desktop
# Art Book Next has art for Steam, Epic and Lutris, and none for GOG or
# Amazon on their own. Heroic's half lives in emulators.nix and
# generators.nix, beside Steam's.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  on = lib.elem "stores" cfg.lanes;

  store = { launchers, default, name }: mkOption {
    type = types.nullOr (types.enum launchers);
    inherit default;
    description = ''
      What runs ${name} games: ${lib.concatMapStringsSep " or " (l: "`\"${l}\"`") launchers},
      or `null` for none. Only on a box whose `lanes` has `"stores"`.
    '';
  };

  # Lutris's name for each store's service (lutris/services/__init__.py,
  # Lutris 0.5.23).
  lutrisServices = {
    gog = "gog";
    epic = "egs";
    amazon = "amazon";
    battlenet = "battlenet";
    ea = "ea_app";
    ubisoft = "ubisoft";
    humble = "humblebundle";
  };

  lutrisStores = cfg.launchers.lutris;

  # Lutris is GTK 3, which only scales by whole numbers (GDK_SCALE): the
  # nearest one to display.scale, as Plymouth's, with text then sized
  # to display.scale exactly (GDK_DPI_SCALE). At 1.5: widgets and icons
  # twice their size, text one and a half times. Found on the first box
  # 2026-10-13: under gamescope, Lutris's window filled the 4K screen at
  # desktop size, unreadable from the couch.
  scale = cfg.display.scale * 1.0;
  gdkScale = lib.max 1 (builtins.floor (scale + 0.5));
  lutris = pkgs.writeShellScriptBin "lutris" ''
    export GDK_SCALE=${toString gdkScale}
    export GDK_DPI_SCALE=${toString (scale / gdkScale)}
    exec ${pkgs.lutris}/bin/lutris "$@"
  '';
in
{
  options.famidrive.stores = {
    gog = store { name = "GOG"; launchers = [ "lutris" "heroic" ]; default = "lutris"; };
    epic = store { name = "Epic Games Store"; launchers = [ "heroic" "lutris" ]; default = "heroic"; };
    amazon = store { name = "Amazon"; launchers = [ "lutris" "heroic" ]; default = "lutris"; };
    battlenet = store { name = "Battle.net"; launchers = [ "lutris" ]; default = "lutris"; };
    ea = store { name = "EA"; launchers = [ "lutris" ]; default = "lutris"; };
    ubisoft = store { name = "Ubisoft Connect"; launchers = [ "lutris" ]; default = "lutris"; };
    humble = store { name = "Humble Bundle"; launchers = [ "lutris" ]; default = "lutris"; };
  };

  options.famidrive.lutris = mkOption {
    type = types.package;
    internal = true;
    readOnly = true;
    description = "Lutris, at the TV's scale (`display.scale`).";
  };

  options.famidrive.launchers = mkOption {
    type = types.attrsOf (types.listOf types.str);
    internal = true;
    readOnly = true;
    description = "Launcher -> the stores it runs on this box (`stores`, when `lanes` has `\"stores\"`).";
  };

  config = lib.mkMerge [
    {
      famidrive.lutris = lutris;
      famidrive.launchers = lib.genAttrs [ "heroic" "lutris" ] (l:
        lib.optionals on (lib.filter (s: cfg.stores.${s} == l) (lib.attrNames cfg.stores)));

      # famidrive-nexusmods finds a GOG game in Heroic's records only.
      warnings = lib.optional (cfg.enable && cfg.stores.gog != "heroic" && lib.any (p:
        lib.any (lib.hasPrefix "gog:") (lib.attrNames (p.nexusmods.games or { })))
        (lib.attrValues cfg.players))
        "famidrive.stores.gog isn't \"heroic\", but a player's nexusmods.games has a GOG game (\"gog:...\"), and its mods install only into Heroic's copy. Set famidrive.stores.gog = \"heroic\" to keep it.";
    }

    (lib.mkIf (cfg.enable && lutrisStores != [ ]) {
      # lutris:rungameid quits Lutris when the game ends, when Lutris
      # wasn't already open (lutris/gui/application.py, 0.5.23), so the
      # command lasts as long as the game. Through gamescope-fg --launcher:
      # the status screen until a window is up, which for a Battle.net game
      # is Battle.net's, where Play is pressed with the controller as a
      # mouse.
      famidrive.systems.lutris = {
        fullname = "Lutris";
        theme = "lutris";   # Art Book Next's Lutris art
        extensions = [ ".lutris" ];
        command = ''${pkgs.gamescope-fg}/bin/gamescope-fg --launcher "$ROM" ${lutris}/bin/lutris "lutris:rungameid/$(cat "$ROM")"'';
      };

      environment.systemPackages = [ lutris ];

      # The stores this box runs through Lutris are its services (its
      # sidebar, where a player signs in and installs); the others are
      # turned off, so a GOG game isn't installed through Lutris on a box
      # whose GOG is Heroic's. Steam's too: Steam games are in the Steam
      # system. Every other service is the player's to turn on. Lutris
      # turns its defaults on only where lutris.conf has no value
      # (lutris/startup.py). Its config is in ~/.local/share/lutris unless
      # an older Lutris left one in ~/.config/lutris (lutris/settings.py).
      famidrive.playerHome = { lib, ... }: {
        home.activation.famidriveLutris = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          lutris_conf="$HOME/.local/share/lutris/lutris.conf"
          if [ -d "$HOME/.config/lutris" ]; then
            lutris_conf="$HOME/.config/lutris/lutris.conf"
          fi
          ${(import ./lib/seed.nix { inherit lib pkgs; }).lockKeys {
            format = "ini";
            target = "$lutris_conf";
            keys.services = lib.mapAttrs' (s: service: lib.nameValuePair service
              (if lib.elem s lutrisStores then "True" else "False")) lutrisServices
              // { steam = "False"; };
          }}
        '';
      };
    })
  ];
}
