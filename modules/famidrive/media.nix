# Jellyfin on the TV (media.md). A bonus, not a game lane: one "Media"
# entry in ES-DE that opens Jellyfin MPV Shim's 10-foot library browser.
# Same path as every game: famidrive-launch -> gamescope-fg, quit -> ES-DE.
{ config, options, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
in
{
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

  config = lib.mkIf (cfg.enable && cfg.media.jellyfin.enable) {
    # One fixed entry, so no generator: the placeholder is written at
    # activation, below.
    famidrive.systems.media = {
      fullname = "Media";
      # Art Book Next has no Jellyfin art; Kodi's media-center art is
      # closest. Without it ES-DE falls back to the "pc" (IBM) logo.
      theme = "kodi";
      extensions = [ ".jellyfin" ];
      command = lib.optionalString (cfg.media.jellyfin.server != null)
        "FAMIDRIVE_JELLYFIN_SERVER=${lib.escapeShellArg cfg.media.jellyfin.server} "
        + "${lib.getExe pkgs.jellyfin-mpv-shim}";   # ignores $ROM
      # saveSync stays false: watch progress lives on the Jellyfin server.
    };

    environment.systemPackages = [ pkgs.jellyfin-mpv-shim ];

    # The shim rewrites conf.json from its own settings screen: lock the few
    # keys a TV box depends on, leave the rest editable. Key names from
    # 3.1.0's conf.py.
    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveJellyfin = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        # The Media entry, in this player's own library view: each player
        # signs in to their own Jellyfin account.
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/media"}
        touch ${lib.escapeShellArg "${famidrivePlayer.roms}/media/Jellyfin.jellyfin"}
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
      '';
    };
  };
}
