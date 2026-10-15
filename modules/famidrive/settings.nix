# Each launcher's own entry sits at the top of its store's system, where
# its games are: the system shows before anything's installed, and a
# player's favorites still come first (ES-DE lists them first; the
# entry's sort name puts it before every other game). Written each
# session, before ES-DE reads its game lists (famidrive-generate
# launcher). Each system starts its .setting entry itself.
#
#   Steam Settings          in Steam: Steam's Big Picture (Proton per
#                           game, launch options, Steam Input, downloads);
#                           steam lane
#   Heroic Games Launcher   in Epic Games Store: sign in to the stores
#                           Heroic runs, install and remove their games;
#                           stores lane, with Epic Heroic's (stores.nix).
#                           In Settings on a box whose Heroic runs only
#                           GOG or Amazon (their games are in Desktop)
#   Lutris                  in Lutris: sign in to the stores Lutris runs
#                           (GOG, Amazon, Battle.net, EA, Ubisoft, Humble
#                           Bundle, by default), install and remove their
#                           games; stores lane
#
# All three were in Settings until 2026-10-15.
#
# A Settings system in ES-DE: one entry per feature this box has that's
# configured from its own screens, so the game lists hold only games.
# ES-DE's own settings menu can't take custom entries.
#
#   Jellyfin Media Player   the Jellyfin app, with its sign-in and its
#                           own settings menu; media.jellyfin.enable
#   Discord Voice Chat      the client's own window: sign in, pick a
#                           channel, mute; only for a player with
#                           players.<name>.voice.discord.enable (voice.nix).
#                           Closing it (Select + Start) lowers it; the
#                           client keeps running and the call keeps going
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
  heroic = cfg.launchers.heroic != [ ];
  lutris = cfg.launchers.lutris != [ ];
  jellyfin = cfg.media.jellyfin.enable;
  bluetooth = cfg.controllers.bluetoothPairing;
  network = cfg.networkSettings && config.networking.networkmanager.enable;
  voiceUsers = lib.filterAttrs (_: p: p.voice.discord.enable or false) cfg.allPlayers;
  voice = voiceUsers != { };

  # Placeholder file name (what ES-DE shows) -> what it opens. Every
  # player's folder gets these alike; Discord Voice Chat is only this
  # player's own (added in playerHome below, not here).
  entries =
    lib.optionalAttrs heroicInSettings { "Heroic Games Launcher" = "heroic"; }
    // lib.optionalAttrs jellyfin { "Jellyfin Media Player" = "jellyfin"; };

  # Heroic's own entry goes in the Epic system only when Heroic runs Epic.
  heroicInSettings = heroic && !(lib.elem "epic" cfg.launchers.heroic);

  # System folder -> the launcher's entry at its top: what ES-DE shows,
  # and what's in the file.
  launchers =
    lib.optionalAttrs steam { steam = { name = "Steam Settings"; id = "steam"; }; }
    // lib.optionalAttrs (heroic && !heroicInSettings) { epic = { name = "Heroic Games Launcher"; id = "heroic"; }; }
    // lib.optionalAttrs lutris { lutris = { name = "Lutris"; id = "lutris"; }; };
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

  config = lib.mkIf (cfg.enable && (entries != { } || launchers != { } || bluetooth || network || voice)) {
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

    famidrive.systems.settings = lib.mkIf (entries != { } || network || voice) {
      fullname = "Settings";
      theme = "tools";   # Art Book Next's tools art
      sortName = "zzzz";   # last in the system list, after every game system
      extensions = [ ".setting" ];
      command = ''
        case "$(cat "$ROM")" in
          ${lib.optionalString heroicInSettings ''heroic) XDG_CURRENT_DESKTOP=FamiDrive ${pkgs.heroic}/bin/heroic --fullscreen --no-sandbox ;;''}
          ${lib.optionalString jellyfin ''jellyfin) ${cfg.systems.media.command} ;;''}
          ${lib.optionalString network ''network-*) exec ${pkgs.famidrive-network}/bin/famidrive-network launch "$ROM" ;;''}
          ${lib.optionalString voice ''discord-voice) exec ${pkgs.gamescope-fg}/bin/gamescope-fg --voice-show ;;''}
        esac
      '';
    };

    # Bluetooth's entries follow the hardware and what's paired, so
    # they're written as each session starts, not at switch. Ones left in
    # Settings, where they were before Controllers, are taken out there.
    famidrive.sessionSetup = lib.concatStrings (lib.mapAttrsToList (system: l: ''
      famidrive-generate launcher "$HOME/.local/share/famidrive/roms/${system}" ${lib.escapeShellArgs [ l.name l.id ]} \
        || echo "famidrive-session: couldn't add ${l.name} to its system" >&2
    '') launchers) + lib.optionalString bluetooth ''
      ${pkgs.famidrive-bluetooth}/bin/famidrive-bluetooth entries "$HOME/.local/share/famidrive/roms/controllers" \
        "$HOME/.local/share/famidrive/roms/settings" \
        || echo "famidrive-session: couldn't list Bluetooth controllers" >&2
    '' + lib.optionalString network ''
      ${pkgs.famidrive-network}/bin/famidrive-network entries "$HOME/.local/share/famidrive/roms/settings" \
        || echo "famidrive-session: couldn't list networks" >&2
    '';

    # famidrive-generate by name, from PATH: a fix to it then doesn't
    # restart the TV (box-testing.md).
    environment.systemPackages = lib.mkIf (launchers != { }) [ pkgs.famidrive-generators ];

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
    famidrive.playerHome = { lib, famidrivePlayer, ... }:
      let myEntries = entries // lib.optionalAttrs (famidrivePlayer.voice.discord.enable or false)
            { "Discord Voice Chat" = "discord-voice"; };
      in {
      home.activation.famidriveSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        d=${lib.escapeShellArg "${famidrivePlayer.roms}/settings"}
        mkdir -p "$d"
        ${lib.concatStrings (lib.mapAttrsToList (name: what: ''
          printf '%s' ${what} > "$d/${name}.setting"
        '') myEntries)}
        ${lib.concatMapStrings (name: ''
          rm -f "$d/${name}.setting"
        '') (lib.filter (n: !(myEntries ? ${n}))
          [ "Steam Settings" "Heroic Games Launcher" "Lutris" "Jellyfin Media Player" "Discord Voice Chat" "Switch Player" ])}
      '';
    };
  };
}
