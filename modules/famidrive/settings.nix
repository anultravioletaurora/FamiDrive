# A Settings system in ES-DE: one entry per feature this box has that's
# configured from its own screens, so the game lists hold only games.
# ES-DE's own settings menu can't take custom entries.
#
#   Steam Settings          Steam's Big Picture (Proton per game, launch
#                           options, Steam Input, downloads); steam lane
#   Heroic Games Launcher   sign in to GOG, Epic and Amazon, install and
#                           remove their games; heroic lane
#   Jellyfin Media Player   the Jellyfin app, with its sign-in and its
#                           own settings menu; media.jellyfin.enable
#   Pair a Controller,      Bluetooth pairing (famidrive-bluetooth), with
#   Forget <controller>     toasts for what's happening; only on a box
#                           with a Bluetooth adapter, checked each session;
#                           controllers.bluetoothPairing
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  steam = lib.elem "steam" cfg.lanes;
  heroic = lib.elem "heroic" cfg.lanes;
  jellyfin = cfg.media.jellyfin.enable;
  bluetooth = cfg.controllers.bluetoothPairing;

  # Placeholder file name (what ES-DE shows) -> what it opens.
  entries =
    lib.optionalAttrs steam { "Steam Settings" = "steam"; }
    // lib.optionalAttrs heroic { "Heroic Games Launcher" = "heroic"; }
    // lib.optionalAttrs jellyfin { "Jellyfin Media Player" = "jellyfin"; };

  gamelist = pkgs.writeText "gamelist.xml" ''
    <?xml version="1.0"?>
    <gameList>
      <game>
        <path>./Steam Settings.setting</path>
        <name>Steam Settings</name>
        <sortname>0</sortname>
      </game>
    </gameList>
  '';
in
{
  options.famidrive.controllers.bluetoothPairing = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      "Pair a Controller" in Settings, and a "Forget" entry for each
      paired controller: Bluetooth pairing from the couch, with no SSH.
      The entries appear only on a box with a Bluetooth adapter.
    '';
  };

  config = lib.mkIf (cfg.enable && (entries != { } || bluetooth)) {
    famidrive.systems.settings = {
      fullname = "Settings";
      theme = "tools";   # Art Book Next's tools art
      sortName = "zzzz";   # last in the system list, after every game system
      extensions = [ ".setting" ];
      command = ''
        case "$(cat "$ROM")" in
          ${lib.optionalString steam ''steam) exec ${pkgs.gamescope-fg}/bin/gamescope-fg --steam bigpicture ;;''}
          ${lib.optionalString heroic ''heroic) XDG_CURRENT_DESKTOP=FamiDrive ${pkgs.heroic}/bin/heroic --fullscreen --no-sandbox ;;''}
          ${lib.optionalString jellyfin ''jellyfin) ${cfg.systems.media.command} ;;''}
          ${lib.optionalString bluetooth ''
            bluetooth-pair) exec ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth pair ;;
            bluetooth-forget\ *) exec ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth forget "$(cut -d' ' -f2 "$ROM")" ;;
          ''}
        esac
      '';
    };

    # Bluetooth's entries follow the hardware and what's paired, so
    # they're written as each session starts, not at switch.
    famidrive.sessionSetup = lib.mkIf bluetooth ''
      ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth entries "$HOME/.local/share/famidrive/roms/settings" \
        || echo "famidrive-session: couldn't list Bluetooth controllers" >&2
    '';

    # Each player's own Settings folder, rewritten on every boot and
    # switch. An entry whose feature is turned off is removed with it, and
    # so is the old Switch Player (ES-DE's own Quit does that now).
    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        d=${lib.escapeShellArg "${famidrivePlayer.roms}/settings"}
        mkdir -p "$d"
        ${lib.concatStrings (lib.mapAttrsToList (name: what: ''
          printf '%s' ${what} > "$d/${name}.setting"
        '') entries)}
        ${lib.concatMapStrings (name: ''
          rm -f "$d/${name}.setting"
        '') (lib.filter (n: !(entries ? ${n})) [ "Steam Settings" "Heroic Games Launcher" "Jellyfin Media Player" "Switch Player" ])}
        ${lib.optionalString steam ''
          # ES-DE sorts by name; Steam Settings goes first by its sort name.
          # ES-DE rewrites gamelists itself (play counts), so this is only a
          # first copy.
          g="$HOME/ES-DE/gamelists/settings/gamelist.xml"
          if [ ! -e "$g" ]; then
            mkdir -p "$(dirname "$g")"
            install -m 0644 ${gamelist} "$g"
          fi
        ''}
      '';
    };
  };
}
