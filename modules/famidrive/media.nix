# Movies and TV on the TV (media.md). A bonus, not a game lane: entries in
# ES-DE's Media system. Same path as every game: famidrive-launch ->
# gamescope-fg, quit -> ES-DE.
#
#   - Kodi (media.kodi): the box's own media folders (an external drive)
#     in its library, Jellyfin through the Jellyfin for Kodi add-on, and
#     any other add-on from nixpkgs' kodiPackages
#   - Jellyfin MPV Shim (media.jellyfin): Jellyfin's own 10-foot browser,
#     playing through mpv
#
# Each player is their own Linux account, so each has their own Kodi
# (~/.kodi): their own Jellyfin sign-in, watched state and resume points.
{ config, options, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  kodi = cfg.media.kodi;
  jellyfin = cfg.media.jellyfin;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };

  kodiAddons = p: [ p.jellyfin p.joystick p.inputstream-adaptive ] ++ kodi.addons p;

  # Kodi's power menu says "Exit" for leaving Kodi, which on a FamiDrive
  # box goes back to the home screen. Estuary's power menu is the only
  # place that string (#13012) is used.
  kodiPackage = (pkgs.kodi.withPackages kodiAddons).overrideAttrs (old: {
    postBuild = old.postBuild + ''
      lang=$out/share/kodi/addons/resource.language.en_gb
      src=$(readlink -f "$lang")
      rm "$lang"
      cp -r "$src" "$lang"
      chmod -R u+w "$lang"
      sed -i '/^msgctxt "#13012"$/{n;s/^msgid "Exit"$/msgid "Return Home"/}' "$lang/resources/strings.po"
      grep -q '^msgid "Return Home"$' "$lang/resources/strings.po"
    '';
  });

  kodiSpec = builtins.toJSON {
    inherit (kodi) sources;
    # To switch on: Kodi can leave add-ons it didn't install itself off.
    # VERIFY on the first box.
    addons = map (a: a.namespace) (lib.filter (a: a ? namespace) (kodiAddons pkgs.kodiPackages));
  };
in
{
  options.famidrive.media.kodi = {
    enable = mkEnableOption "Kodi as a Media entry in ES-DE, with Jellyfin for Kodi";

    sources = mkOption {
      type = types.attrsOf (types.submodule {
        options = {
          path = mkOption {
            type = types.str;
            example = "/media/movies";
            description = "A folder on this box, usually on an external drive the host mounts.";
          };
          content = mkOption {
            type = types.enum [ "movies" "tvshows" ];
            description = "What the folder holds, so Kodi knows how to scan it (its \"Set content\").";
          };
        };
      });
      default = { };
      example = {
        Movies = { path = "/media/movies"; content = "movies"; };
        "TV Shows" = { path = "/media/tv"; content = "tvshows"; };
      };
      description = ''
        This box's own media folders, in every player's Kodi library:
        named sources, set to their content with Kodi's TMDB scrapers,
        and scanned each time Kodi starts, so new files turn up on their
        own. A folder that isn't there (an unplugged drive) is skipped.

        Mount the drive in the host's config, readable by every player,
        and with `nofail` so the box still boots without it:

            fileSystems."/media" = {
              device = "/dev/disk/by-label/media";
              options = [ "nofail" "x-systemd.automount" ];
            };

        (exFAT and NTFS drives also need `uid`/`gid`/`umask` options,
        since they have no Linux permissions of their own.)
      '';
    };

    addons = mkOption {
      type = types.functionTo (types.listOf types.package);
      default = _: [ ];
      defaultText = lib.literalExpression "p: [ ]";
      example = lib.literalExpression "p: [ p.upnext p.a4ksubtitles p.pvr-hdhomerun ]";
      description = ''
        More Kodi add-ons from nixpkgs' kodiPackages, for every player.
        Jellyfin for Kodi, controller support and inputstream.adaptive
        are always there.
      '';
    };
  };

  options.famidrive.media.jellyfin = {
    enable = mkEnableOption "Jellyfin MPV Shim as a Media entry in ES-DE";

    server = mkOption {
      type = types.nullOr types.str;
      default =
        if options.famidrive.endpoints.jellyfin.isDefined then cfg.endpoints.jellyfin else null;
      description = ''
        Public Jellyfin hostname, the same from every box on or off the LAN.
        Pre-filled into the shim's sign-in form (a small patch in the flake
        overlay), so first launch is just "Use Quick Connect" and a code. The
        shim keeps its own login token afterwards; nothing secret is here.
      '';
    };
  };

  config = lib.mkIf (cfg.enable && (kodi.enable || jellyfin.enable)) {
    # Fixed entries, so no generator: the placeholders are written at
    # activation, below. The placeholder's extension picks the app.
    famidrive.systems.media = {
      fullname = "Media";
      # Art Book Next's Kodi art (it has none for Jellyfin). Without it
      # ES-DE falls back to the "pc" (IBM) logo.
      theme = "kodi";
      extensions = lib.optional kodi.enable ".kodi" ++ lib.optional jellyfin.enable ".jellyfin";
      command = ''
        case "$ROM" in
      '' + lib.optionalString kodi.enable ''
          *.kodi)
            ${pkgs.famidrive-kodi}/bin/famidrive-kodi prepare ${lib.escapeShellArg kodiSpec} \
              || echo "famidrive-launch: couldn't set up Kodi" >&2
            # Sets up the media folders once Kodi has made its database,
            # then scans them.
            PATH=${kodiPackage}/bin:${pkgs.kodi}/bin:$PATH \
              ${pkgs.famidrive-kodi}/bin/famidrive-kodi library ${lib.escapeShellArg kodiSpec} &
            library=$!
            rc=0
            ${kodiPackage}/bin/kodi -fs || rc=$?
            kill "$library" 2>/dev/null || true
            exit "$rc"
            ;;
      '' + lib.optionalString jellyfin.enable ''
          *.jellyfin)
            ${lib.optionalString (jellyfin.server != null)
              "FAMIDRIVE_JELLYFIN_SERVER=${lib.escapeShellArg jellyfin.server} "}${lib.getExe pkgs.jellyfin-mpv-shim}
            ;;
      '' + ''
        esac
      '';
      # saveSync stays false: watch progress lives on the Jellyfin server,
      # or in each player's own Kodi.
    };

    environment.systemPackages =
      lib.optional kodi.enable kodiPackage
      ++ lib.optional jellyfin.enable pkgs.jellyfin-mpv-shim;

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveMedia = lib.hm.dag.entryAfter [ "writeBoundary" ] (''
        # The Media entries, in this player's own library view: each
        # player signs in to their own accounts.
        media=${lib.escapeShellArg "${famidrivePlayer.roms}/media"}
        mkdir -p "$media"
        rm -f "$media/Kodi.kodi" "$media/Jellyfin.jellyfin"
      '' + lib.optionalString kodi.enable ''
        touch "$media/Kodi.kodi"
      '' + lib.optionalString jellyfin.enable ''
        touch "$media/Jellyfin.jellyfin"
        # The shim rewrites conf.json from its own settings screen: lock
        # the few keys a TV box depends on, leave the rest editable. Key
        # names from 3.1.0's conf.py.
        ${seedLib.lockKeys {
          format = "json";
          target = "$HOME/.config/jellyfin-mpv-shim/conf.json";
          keys = {
            ".input_gamepad" = true;         # needs mpv-gamepad (flake overlay)
            ".browser_fullscreen" = true;
            ".fullscreen" = true;
            ".close_to_tray" = false;        # quitting must exit, so famidrive-launch returns to ES-DE
            ".allow_background" = false;
            ".hwdec" = "auto-safe";          # shim default is "no"; open question in media.md
            # gamepad_swap_confirm (A bottom vs. A right) depends on the pads
            # in the house, so it's left to the settings screen.
          };
        }}
      '');
    };
  };
}
