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
#   Wi-Fi: <network>,       join a network, forget one, see the wired
#   Forget Wi-Fi: <network>, port's state (famidrive-network); written each
#   Ethernet                session for the box's own adapters;
#                           networkSettings
#
# And a Controllers system beside it, for Bluetooth pairing, which crowded
# Settings out with one Forget entry per controller:
#
#   Forget <controller>,    Bluetooth pairing (famidrive-bluetooth), with
#   Pair a Controller       toasts for what's happening; only on a box
#                           with a Bluetooth adapter, checked each session;
#                           controllers.bluetoothPairing. Pairing is
#                           always first, by its sort name.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  steam = lib.elem "steam" cfg.lanes;
  heroic = lib.elem "heroic" cfg.lanes;
  jellyfin = cfg.media.jellyfin.enable;
  bluetooth = cfg.controllers.bluetoothPairing;
  network = cfg.networkSettings && config.networking.networkmanager.enable;

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
      A Controllers system with "Pair a Controller" (always first), and a
      "Forget" entry for each paired controller: Bluetooth pairing from
      the couch, with no SSH. The entries appear only on a box with a
      Bluetooth adapter (ES-DE hides a system with nothing in it).
    '';
  };

  options.famidrive.networkSettings = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Wi-Fi and Ethernet in Settings: an entry for each Wi-Fi network in
      range (launch it to join; a password is typed in ES-DE's game-info
      editor as the entry's Sort name), one to forget each remembered
      network, and one per wired port that shows its state. Needs
      NetworkManager (`networking.networkmanager.enable`).
    '';
  };

  config = lib.mkIf (cfg.enable && (entries != { } || bluetooth || network)) {
    famidrive.systems.controllers = lib.mkIf bluetooth {
      fullname = "Controllers";
      # Art Book Next has no controller or Bluetooth art: its fallback,
      # chosen 2026-10-10, over borrowing another system's.
      theme = "_default";
      sortName = "zzzy";   # just before Settings
      extensions = [ ".setting" ];
      command = ''
        case "$(cat "$ROM")" in
          bluetooth-pair) exec ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth pair ;;
          bluetooth-forget\ *) exec ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth forget "$(cut -d' ' -f2 "$ROM")" ;;
        esac
      '';
    };

    famidrive.systems.settings = lib.mkIf (entries != { } || network) {
      fullname = "Settings";
      theme = "tools";   # Art Book Next's tools art
      sortName = "zzzz";   # last in the system list, after every game system
      extensions = [ ".setting" ];
      command = ''
        case "$(cat "$ROM")" in
          ${lib.optionalString steam ''steam) exec ${pkgs.gamescope-fg}/bin/gamescope-fg --steam bigpicture ;;''}
          ${lib.optionalString heroic ''heroic) XDG_CURRENT_DESKTOP=FamiDrive ${pkgs.heroic}/bin/heroic --fullscreen --no-sandbox ;;''}
          ${lib.optionalString jellyfin ''jellyfin) ${cfg.systems.media.command} ;;''}
          ${lib.optionalString network ''network-*) exec ${pkgs.famidrive-network}/bin/famidrive-network launch "$ROM" ;;''}
        esac
      '';
    };

    # Bluetooth's entries follow the hardware and what's paired, so
    # they're written as each session starts, not at switch. Ones left in
    # Settings, where they were before Controllers, are taken out there.
    famidrive.sessionSetup = lib.optionalString bluetooth ''
      ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth entries "$HOME/.local/share/famidrive/roms/controllers" \
        "$HOME/.local/share/famidrive/roms/settings" \
        || echo "famidrive-session: couldn't list Bluetooth controllers" >&2
    '' + lib.optionalString network ''
      ${pkgs.famidrive-network}/bin/famidrive-network entries "$HOME/.local/share/famidrive/roms/settings" \
        || echo "famidrive-session: couldn't list networks" >&2
    '';

    # Players join and forget networks for the whole box, so Wi-Fi is up
    # before anyone picks a player. NetworkManager asks for an admin
    # password for that otherwise, which can't be typed from a controller.
    security.polkit.extraConfig = lib.mkIf network ''
      polkit.addRule(function(action, subject) {
        if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0
            && subject.isInGroup("famidrive")) {
          return polkit.Result.YES;
        }
      });
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
