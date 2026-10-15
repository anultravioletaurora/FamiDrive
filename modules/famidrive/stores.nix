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

  # umu-run is a bash script (nixpkgs-unstable's, as umu-launcher =
  # unstable.umu-launcher pins it in flake.nix's overlay), and it
  # crashes before running a single line of itself - bash aborts with a
  # stack-smashing failure during its own dynamic-linker startup
  # (SIGABRT, lutris.log's exit 134) - every time Lutris's wine runner
  # (wine.py, get_env()) execs it, on both the installer's set_regedit
  # step and the actual .exe launch. Lutris's own create_prefix never
  # hits it: it skips get_env() and builds its environment from
  # scratch. #211 found one contributing cause, on the first box
  # 2026-10-13: get_env()'s LD_LIBRARY_PATH is built for the FHS
  # sandbox's 32-bit/legacy compat libs, an older bundled glibc among
  # them, ahead of the sandbox's own glibc in the search path - and
  # LD_LIBRARY_PATH beats a binary's own DT_RUNPATH, so bash loads that
  # older libc.so.6 instead of the one it's actually linked against.
  # Dropping LD_LIBRARY_PATH before re-exec'ing didn't fully clear it,
  # though: found on the first box 2026-10-14, still installing
  # Battle.net, coredumpctl's backtrace named the exact bash binary
  # that aborted - nixpkgs-unstable's (5.3p15, pinned alongside
  # umu-launcher/Heroic/GE-Proton), never the release's own (5.3p9,
  # running throughout that same nested bwrap sandbox all session with
  # no issue). Running the very same umu-run script, byte for byte,
  # under the release's bash instead (its own shebang ignored, the way
  # "bash script args" always does) avoids it outright, on top of the
  # LD_LIBRARY_PATH fix, which still matters for whatever umu-run execs
  # after it starts (Proton, Wine). Named umu-run itself (not just a
  # wrapper with its own name): is_umu_path() (proton.py) only matches
  # a path whose last segment is literally "umu-run".
  umuRun = pkgs.writeShellScriptBin "umu-run" ''
    unset LD_LIBRARY_PATH
    exec ${pkgs.bash}/bin/bash ${pkgs.umu-launcher}/bin/umu-run "$@"
  '';

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
        # Lutris doesn't say which games are online, and most of its
        # stores' are (Battle.net's all are): the Guide menu leaves them
        # running. Found on the first box 2026-10-15: it froze Black Ops
        # Cold War in a multiplayer match.
        guideMenu = "block";
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

        # Lutris's own default Wine is its "ge-proton" sentinel (0.5.22+),
        # which runs through umu-run inside Steam's Sniper runtime
        # container (pressure-vessel) - the same sandbox BattlEye's and
        # Easy Anti-Cheat's Linux support check for, so games that need
        # them still work, same as through Steam or Heroic (a plain Wine
        # build, with no container, wouldn't pass that check). With no
        # PROTONPATH, umu fetches its own idea of "latest" GE-Proton over
        # the network the first time a game runs; Battle.net's installer
        # aborted under whatever it fetched (exit 134, lutris.log, #205).
        # Pointing PROTONPATH at the GE-Proton Steam and Heroic already
        # have instead keeps every launcher on the same pinned build, with
        # no fetch: a stable symlink, refreshed every activation (so
        # bumping the pin here reaches Lutris with no further edit), the
        # same way famidriveHeroicProton does it for Heroic.
        #
        # That alone isn't enough, though: as long as Wine's "version" is
        # still the "ge-proton" sentinel, Lutris's own wine runner
        # (wine.py, get_env()) sets PROTONPATH to the literal string
        # "GE-Proton" - umu's own "fetch latest" sentinel - unconditionally,
        # before our value is even considered, undoing the pin. Pointing
        # "version" at "custom" with custom_wine_path set to umu-run itself
        # (not a raw wine/wine64 binary, which would skip umu and the
        # Sniper container entirely) sidesteps that: Lutris still treats it
        # as an umu path (is_umu_path() matches on the filename alone) and
        # runs it the same way, but no longer overwrites PROTONPATH first,
        # so the pin from system.yml below sticks. umuRun (above) is that
        # same umu-run, run under a bash that doesn't crash nested in
        # Lutris's sandbox.
        home.activation.famidriveLutrisProton = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          lutris_dir="$HOME/.local/share/lutris"
          if [ -d "$HOME/.config/lutris" ]; then
            lutris_dir="$HOME/.config/lutris"
          fi
          mkdir -p "$lutris_dir"
          ln -sfn ${pkgs.proton-ge-bin.steamcompattool} "$lutris_dir/GE-Proton-FamiDrive"

          wine_conf="$lutris_dir/runners/wine.yml"
          mkdir -p "$(dirname "$wine_conf")"
          touch "$wine_conf"
          version=$(${pkgs.yq-go}/bin/yq '.wine.version' "$wine_conf" 2>/dev/null || echo "null")
          custom_path=$(${pkgs.yq-go}/bin/yq '.wine.custom_wine_path' "$wine_conf" 2>/dev/null || echo "null")
          # custom_path is content-addressed (umuRun), so a FamiDrive fix
          # to it (#211, #215) is a new store path that always exists, not
          # a missing one: re-point whenever it's still famidrive's own
          # (named "umu-run"), not a player's real custom Wine.
          if [ "$version" = "null" ] || [ "$version" = "ge-proton" ] \
            || { [ "$version" = "custom" ] && { [ "$custom_path" = "null" ] || [ ! -e "$custom_path" ] \
                 || [ "$(basename "$custom_path")" = "umu-run" ]; }; }; then
            ${pkgs.yq-go}/bin/yq -i ${lib.escapeShellArg ''.wine.version = "custom" | .wine.custom_wine_path = "${umuRun}/bin/umu-run"''} "$wine_conf" \
              || echo "famidrive: couldn't set Lutris's default Wine" >&2
          fi

          sys_conf="$lutris_dir/system.yml"
          touch "$sys_conf"
          current=$(${pkgs.yq-go}/bin/yq '.system.env.PROTONPATH' "$sys_conf" 2>/dev/null || echo "null")
          if [ "$current" = "null" ] || [ ! -e "$current" ]; then
            export FAMIDRIVE_PROTON_GE="$lutris_dir/GE-Proton-FamiDrive"
            ${pkgs.yq-go}/bin/yq -i '.system.env.PROTONPATH = strenv(FAMIDRIVE_PROTON_GE)' "$sys_conf" \
              || echo "famidrive: couldn't set Lutris's default Proton" >&2
          fi
        '';
      };
    })
  ];
}
