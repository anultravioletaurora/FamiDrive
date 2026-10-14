# Boot straight into ES-DE inside gamescope, with no display manager UI and no DE.
# Steam is one entry on the menu, not the shell (base-os.md).
#
# With more than one player (famidrive.players, the guest counts), the box
# starts on "Who's playing?" instead (pkgs/famidrive-picker, as greetd's
# greeter), and quitting ES-DE (its Quit menu) comes back to it.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  steamGames = import ./lib/steam-games.nix { inherit lib; };

  # Launch options FamiDrive knows games need (lib/steam-games.nix), for
  # the games the host hasn't set its own for, by app id or name.
  knownLaunchOptions = lib.optionalAttrs cfg.steam.defaultLaunchOptions
    (lib.filterAttrs (appid: _: !steamGames.setIn cfg.steam.launchOptions appid) steamGames.plain);

  # famidrive-steam-config's settings, with a player's own launch options
  # (by app id) over the box's. A box entry by the same game's name is
  # dropped, or both would reach the tool and the name's would win.
  steamSettings = own: lib.escapeShellArg (builtins.toJSON {
    inherit (cfg.steam) steamInput steamInputGames;
    # "0" is Steam's own app id for "Enable Steam Play for all other
    # titles"; a compatTools pin for a real game wins over it, same as
    # in Steam's own UI.
    compatTools = lib.optionalAttrs (cfg.steam.protonDefault != null) { "0" = cfg.steam.protonDefault; }
      // cfg.steam.compatTools;
    # Guide is FamiDrive's menu (pkgs/famidrive-quit), not Steam's.
    guideFocusesSteam = false;
    launchOptions = lib.filterAttrs
      (game: _: !lib.any (appid: (steamGames.games.${appid}.name or null) == game) (lib.attrNames own))
      (knownLaunchOptions // cfg.steam.launchOptions) // own;
  });
  hasLane = l: lib.elem l cfg.lanes;

  # True once this player has signed in to Steam on this box: Steam makes
  # userdata/<account>/config/localconfig.vdf at the first sign-in, and
  # that's where famidrive-steam-config turns Guide off.
  steamSignedIn = pkgs.writeShellScript "famidrive-steam-signed-in" ''
    for f in "$HOME"/.local/share/Steam/userdata/*/config/localconfig.vdf; do
      [ -e "$f" ] && exit 0
    done
    exit 1
  '';

  picker = lib.length (lib.attrNames cfg.allPlayers) > 1;

  # Players with MangoHud's performance overlay on (overlays.nix).
  perfUsers = lib.attrNames (lib.filterAttrs (_: o: o.performance.enable) cfg.overlays.resolved);

  # The menu's music says what's playing (esde.nowPlaying): a toast with
  # the song's title and artist as each one starts, from its tags, or its
  # file name when it has none. An mpv script, so it's mpv's own playlist
  # that decides when a song changes.
  nowPlaying = pkgs.writeText "famidrive-now-playing.lua" ''
    local function tag(key)
      local v = mp.get_property("metadata/by-key/" .. key)
      if v and v ~= "" then return v end
    end
    mp.register_event("file-loaded", function()
      local title = tag("title") or mp.get_property("filename/no-ext")
      if not title or title == "" then return end
      local args = { "${pkgs.famidrive-toast}/bin/famidrive-toast", "--kind", "notice",
                     "--icon", "music", "--id", "now-playing", title }
      local artist = tag("artist") or tag("album_artist")
      if artist then table.insert(args, artist) end
      mp.command_native_async({ name = "subprocess", args = args, playback_only = false }, function() end)
    end)
  '';

  famidriveSession = pkgs.writeShellScript "famidrive-session" ''
    ${lib.optionalString (perfUsers != [ ]) ''
      # MangoHud (gamescope --mangoapp, for players with the performance
      # overlay on). gamescope hands mangoapp a config that says
      # no_display, for Steam's quick-access menu to change, which this
      # session doesn't have; the player's own goes there instead. Steam
      # starts without STEAM_USE_MANGOAPP, so it never writes it back.
      if [ -n "''${MANGOHUD_CONFIGFILE:-}" ] && [ -f "$HOME/.config/MangoHud/MangoHud.conf" ]; then
        cp "$HOME/.config/MangoHud/MangoHud.conf" "$MANGOHUD_CONFIGFILE"
        unset STEAM_USE_MANGOAPP
      fi
    ''}
    ${lib.optionalString cfg.display.hdr ''
      # Proton games only output HDR when asked; gamescope (--hdr-enabled)
      # carries it to the TV. SDR content is unaffected.
      export DXVK_HDR=1
    ''}
    ${lib.optionalString (hasLane "steam") ''
      # The idle copy (famidrive-steam-background, below) has to be gone
      # before its settings files are edited and before this session
      # starts its own; famidrive-end-session brings it back on the way out.
      systemctl --user stop famidrive-steam-background.service 2>/dev/null || true
      # And any other Steam of this player's still on its way out (an
      # earlier session's): `steam -silent` below would only hand itself
      # to it, and this session's games would go to a Steam with no screen.
      for _ in $(seq 1 30); do
        ${pkgs.procps}/bin/pgrep -u "$(id -u)" -x steam > /dev/null || break
        sleep 0.5
      done
      # Proton pins, Steam Input, launch options and Guide, written while Steam
      # isn't running (pkgs/famidrive-steam-config). A player's own launch
      # options (their mods') go over the box's.
      case "$(id -un)" in
      ${lib.concatStrings (lib.mapAttrsToList (user: own: ''
        ${user}) steam_settings=${steamSettings own} ;;
      '') cfg.steam.playerLaunchOptions)}
        *) steam_settings=${steamSettings { }} ;;
      esac
      ${pkgs.famidrive-steam-config}/bin/famidrive-steam-config "$steam_settings" \
        || echo "famidrive-session: couldn't apply Steam settings" >&2
      # Instrument adapters out of Steam and its games (controllers.instruments):
      # games inherit Steam's environment. Not exported as SDL's own name,
      # or ES-DE, Clone Hero and YARG wouldn't see the guitars either;
      # gamescope-fg passes it on wherever it starts Steam.
      export FAMIDRIVE_STEAM_SDL_IGNORE=${lib.escapeShellArg cfg.controllers.sdlIgnoreDevices}
      # Start Steam hidden up front. Otherwise the first `steam -applaunch`
      # brings up Steam's own client windows, which then fight the game
      # for gamescope's single focused window.
      #
      # Only once this player has signed in to Steam, though: before that
      # there's no localconfig.vdf to turn "Guide Button Focuses Steam"
      # off in, and a Steam with nobody signed in still hears the pads.
      # Found on the second box 2026-10-14: Guide opened FamiDrive's menu,
      # then Big Picture came up over it. Signing in goes through Steam
      # Settings (gamescope-fg starts Steam for it), and the next session
      # has the file.
      if ${steamSignedIn}; then
        SDL_GAMECONTROLLER_IGNORE_DEVICES="$FAMIDRIVE_STEAM_SDL_IGNORE" steam -silent &
      fi
    ''}
    ${lib.optionalString (config.famidrive.esde.theme != null) ''
      # The Steam launch status screen draws in the theme's fonts.
      export FAMIDRIVE_STATUS_THEME=${config.famidrive.esde.theme.src}
    ''}
    ${lib.optionalString (cfg.romm.enable && lib.elem "roms" cfg.lanes) ''
      # Players with RomM: the library's newest game lists before ES-DE
      # reads them, then firmware into this player's emulators. By name,
      # from the system's PATH, not its store path: an agent fix then
      # doesn't count as a new session, and a switch doesn't restart the
      # TV for it. Found on the first box 2026-10-06.
      if [ -e "/etc/famidrive/romm/$(id -un).json" ]; then
        romm-agent gamelists || echo "famidrive-session: couldn't copy game lists" >&2
        ${lib.optionalString picker ''
          # Their RomM picture for "Who's playing?", next time it shows.
          romm-agent avatar ${avatarDir} || echo "famidrive-session: couldn't fetch the RomM picture" >&2
        ''}
        ${lib.optionalString (cfg.systems ? switch) ''
          # Before Eden ever starts: this player's profile, the same ID on each of their boxes.
          romm-agent eden-profile || echo "famidrive-session: couldn't set up the Eden profile" >&2
        ''}
        romm-agent firmware-install &
      fi
      # The library's Dolphin texture packs and Switch mods, for every
      # player and the guest: they belong to the box, like the ROMs.
      ROMM_AGENT_CONFIG=/etc/famidrive/romm/library.json romm-agent textures \
        || echo "famidrive-session: couldn't link texture packs" >&2
      ${lib.optionalString (cfg.systems ? switch) ''
        # The library's Switch folder, where Eden finds updates and DLC.
        ROMM_AGENT_CONFIG=/etc/famidrive/romm/library.json romm-agent eden-gamedir \
          || echo "famidrive-session: couldn't add the library to Eden" >&2
      ''}
    ''}
    ${lib.optionalString picker ''
      # A fresh start for this player's audio. Found on the first box
      # 2026-10-06: after switching players, WirePlumber tried to open the
      # HDMI output while logind was still handing the TV over, gave up,
      # and left only "Dummy Output" (no sound) for the whole session.
      systemctl --user restart wireplumber.service || echo "famidrive-session: couldn't restart WirePlumber" >&2
    ''}
    ${cfg.sessionSetup}
    # The menu's music: ES-DE has none of its own (ES-DE 3.5 has no music
    # support at all), so the player's ES-DE/music plays here, shuffled,
    # and gamescope-fg pauses it while a game or app covers the menu.
    music="$HOME/ES-DE/music"
    if [ -n "$(${pkgs.findutils}/bin/find -L "$music" -type f \( -iname '*.mp3' -o -iname '*.ogg' -o -iname '*.opus' \
        -o -iname '*.flac' -o -iname '*.m4a' -o -iname '*.wav' \) -print -quit 2>/dev/null)" ]; then
      ${pkgs.mpv}/bin/mpv --no-video --no-terminal --really-quiet --shuffle --loop-playlist=inf \
        --volume=${toString cfg.esde.musicVolume} \
        ${lib.optionalString cfg.esde.nowPlaying "--script=${nowPlaying} "}--input-ipc-server="''${XDG_RUNTIME_DIR:-/tmp}/famidrive-music.sock" "$music" &
    fi
    # Nothing is running yet: clear what a crashed launch may have left.
    rm -f "''${XDG_RUNTIME_DIR:-/nonexistent}"/famidrive-game.*
    # Hold Select + Start on any controller to quit the running game, and
    # press Guide for the menu the toast daemon draws (pkgs/famidrive-quit).
    # It exits on its own when the session ends.
    ${pkgs.famidrive-quit}/bin/famidrive-quit &
    # ES-DE through gamescope-fg, which labels its window and makes it what
    # gamescope shows (nothing does that without Steam; see gamescope-fg).
    ${pkgs.gamescope-fg}/bin/gamescope-fg --frontend ${pkgs.es-de}/bin/es-de --no-splash || true
    # ES-DE closed: Quit ES-DE in its Quit menu (or Power off / Reboot,
    # which it has already asked for, or a crash). End the session cleanly:
    # "Who's playing?" comes back, or on a one-player box, ES-DE.
    exec ${pkgs.famidrive-end-session}/bin/famidrive-end-session
  '';

  gamescopeFlags = lib.optionals cfg.display.vrr [
    "--adaptive-sync"
  ] ++ lib.optionals cfg.display.hdr [
    "--hdr-enabled"
  ] ++ lib.optionals (cfg.display.refresh != null) [
    # gamescope otherwise takes the TV's preferred mode, which is usually 60 Hz.
    "-r" (toString cfg.display.refresh)
  ] ++ lib.optionals (cfg.display.cursorScale != null) [
    "--cursor-scale-height" (toString cfg.display.cursorScale)
  ];

  gamescopeCmd = lib.concatStringsSep " " ([
    # Plain gamescope, not the programs.gamescope.capSysNice wrapper.
    # Found on the first box 2026-10-05: the wrapper's CAP_SYS_NICE is inherited
    # by everything gamescope starts, and bubblewrap (ES-DE's AppImage
    # sandbox, Steam's FHS sandbox) refuses to run with capabilities:
    # "bwrap: Unexpected capabilities but not setuid". The cost is
    # gamescope's realtime scheduling boost.
    "${pkgs.gamescope}/bin/gamescope"
    "-f"                  # fullscreen
    "-e"                  # Steam-integration mode, needed for STEAM_GAME focus atoms
    "\"\${overlay[@]}\""   # the player's performance overlay (famidrive-start)
  ] ++ gamescopeFlags ++ [
    "--"
    "${famidriveSession}"
  ]);

  # gamescope, ES-DE and everything they launch print to the TV's console,
  # where nobody can read it. Keep the last session's output in a file
  # instead (the previous one is kept as session.log.1).
  sessionCmd = "${pkgs.writeShellScript "famidrive-start" ''
    log="$HOME/.local/state/famidrive"
    mkdir -p "$log"
    [ -f "$log/session.log" ] && mv "$log/session.log" "$log/session.log.1"
    # MangoHud over everything, for players who turned it on
    # (overlays.nix); gamescope starts mangoapp itself.
    overlay=()
    ${lib.optionalString (perfUsers != [ ]) ''
      case "$(id -un)" in
        ${lib.concatStringsSep "|" perfUsers}) overlay=(--mangoapp) ;;
      esac
    ''}
    exec ${gamescopeCmd} > "$log/session.log" 2>&1
  ''}";

  # "Who's playing?": greetd's greeter, in a gamescope of its own (no
  # Steam mode: it's the only window). Picks a player and asks greetd to
  # start their session, the same one autologin starts with one player.
  avatarDir = "/var/lib/famidrive-picker/avatars";
  pickerSpec = pkgs.writeText "famidrive-picker.json" (builtins.toJSON {
    # The primary player first, then the others by name, the guest last.
    players = map (p: { inherit (p) user displayName isGuest; avatar = if p.avatar or null != null then "${p.avatar}" else null; })
      (lib.sortOn (p: (if p.name == cfg.primaryPlayer then "0" else if p.isGuest then "2" else "1") + p.name)
        (lib.attrValues cfg.allPlayers));
    session = [ sessionCmd ];
    last = "/var/lib/famidrive-picker/last";
    # Each player's RomM picture, copied there at their session start.
    avatars = avatarDir;
    theme = if cfg.esde.theme != null then "${cfg.esde.theme.src}" else null;
    powerOff = [ "${config.systemd.package}/bin/systemctl" "poweroff" ];
  });
  # "Who's playing?" with a toast daemon of its own, so controllers
  # connecting and going flat show there too. The greeter has no runtime
  # folder; famidrive-toast falls back to /tmp for it.
  pickerSession = pkgs.writeShellScript "famidrive-picker-session" ''
    ${pkgs.famidrive-toast}/bin/famidrive-toast daemon ${cfg.overlays.toastSpec} greeter &
    exec ${pkgs.famidrive-picker}/bin/famidrive-picker ${pickerSpec}
  '';
  pickerCmd = lib.concatStringsSep " " ([
    "${pkgs.gamescope}/bin/gamescope" "-f"
  ] ++ gamescopeFlags ++ [
    "--" "${pickerSession}"
  ]);
in
{
  # Shell lines run at the start of each player's session, before ES-DE,
  # as that player. For setup that has to follow the shared library, which
  # changes between rebuilds.
  options.famidrive.sessionSetup = mkOption {
    type = types.lines;
    internal = true;
    default = "";
  };

  options.famidrive.steam.compatTools = mkOption {
    type = types.attrsOf types.str;
    default = { };
    example = { "Rocket League" = "proton_experimental"; "1091500" = "GE-Proton"; };
    description = ''
      Per-game Proton pins, by game name (as Steam and ES-DE show it) or
      Steam app id: what Steam's "Force the use of a specific Steam Play
      compatibility tool" sets. Tool names are Steam's internal ones
      (`proton_experimental`, `proton_10`, `proton_hotfix`, or a custom
      tool's folder name such as `GE-Proton`). Mostly for games whose
      native Linux build Steam still prefers but which no longer works,
      like Rocket League.

      This is for settling on a choice. To try versions out without a
      rebuild, use Steam Settings in ES-DE's Steam system (Big Picture →
      the game → Properties → Compatibility). Pinned games are set back to
      their pin at the start of each session, before Steam starts; other
      games keep whatever Steam was told. Names of games that aren't
      installed yet are skipped until they are.
    '';
  };

  options.famidrive.steam.protonDefault = mkOption {
    type = types.nullOr types.str;
    default = "GE-Proton";
    description = ''
      Steam's "Enable Steam Play for all other titles" default
      compatibility tool (`compatTools`' app id `"0"`): every installed
      game without its own pin in `compatTools` runs under this one,
      instead of Steam's own per-title choice (often Proton Experimental,
      sometimes an older pinned Proton). The default is GloriousEggroll's
      GE-Proton, the same build Heroic gets.

      A game that needs Valve's own Proton specifically still gets it
      from its own pin (`compatTools.<game> = "proton_experimental";`),
      which wins over this default. `null` leaves Steam's own choice of
      compatibility tool alone for every game that has no pin.
    '';
  };

  options.famidrive.steam.steamInput = mkOption {
    type = types.bool;
    default = false;
    description = ''
      Whether Steam Input stands between controllers and Steam games.
      Off (the default): FamiDrive sets "Disable Steam Input" on every
      installed game at the start of each session, so each game reads the
      pad itself, the same as every emulator does. Games installed during
      a session get it from the next one. On: Steam's own per-game
      choices are left alone.
    '';
  };

  options.famidrive.steam.steamInputGames = mkOption {
    type = types.listOf types.str;
    default = [ ];
    example = [ "Left 4 Dead 2" ];
    description = ''
      Games that keep Steam Input while `steamInput` is off, by name (as
      Steam and ES-DE show it) or app id. For games whose own controller
      support is missing or worse, such as Valve's older games, which
      expect Steam Input.
    '';
  };

  options.famidrive.steam.offlineGames = mkOption {
    type = types.listOf types.str;
    default = [ ];
    example = [ "268910" ];
    description = ''
      Steam games, by app id, that the Guide menu freezes while it's open,
      so they're paused, as emulators are. Without this, Steam's own
      labels decide: a game marked Single-player and none of the
      multiplayer kinds (Multi-player, Co-op, Online PvP, Shared/Split
      Screen…) is frozen, and any other keeps running under the menu,
      with the pads taken from it, since stopping an online game drops it
      off its server. For a game whose multiplayer is only on the couch,
      such as Cuphead, which Steam marks Multi-player.
    '';
  };

  options.famidrive.steam.onlineGames = mkOption {
    type = types.listOf types.str;
    default = [ ];
    description = ''
      Steam games, by app id, that keep running under the Guide menu even
      though Steam marks them Single-player only, for one that's online
      anyway.
    '';
  };

  options.famidrive.steam.playerLaunchOptions = mkOption {
    type = types.attrsOf (types.attrsOf types.str);
    default = { };
    internal = true;
    description = "Launch options for one player only, by their user, over `launchOptions` (thunderstore.nix, nexusmods.nix).";
  };

  options.famidrive.steam.launchOptions = mkOption {
    type = types.attrsOf types.str;
    default = { };
    example = { "Cyberpunk 2077" = ''WINEDLLOVERRIDES="winmm,version=n,b" %command% --launcher-skip''; };
    description = ''
      Games' launch options, by name (as Steam and ES-DE show it) or app
      id. Set at the start of each session; a game not listed keeps what
      was set in Steam, or gets FamiDrive's own (`defaultLaunchOptions`).
      A game set here gets exactly this, in place of FamiDrive's, for
      every player, mods or not.
    '';
  };

  options.famidrive.steam.defaultLaunchOptions = mkOption {
    type = types.bool;
    default = true;
    description = ''
      Give games FamiDrive knows about the launch options they need
      (lib/steam-games.nix), so nobody has to find them out again:
      Cyberpunk 2077 skips its launcher (`--launcher-skip`), whose window
      stays black on the TV, and a player's modded games load their mods
      (Cyberpunk 2077 through Nexus Mods; Valheim and Risk of Rain 2
      through Thunderstore). A game in `launchOptions` gets that instead.
      Off: only what `launchOptions` and players' own set.
    '';
  };

  options.famidrive.session.restartOnSwitch = mkOption {
    type = types.bool;
    default = true;
    description = ''
      Restart the TV's session on `nixos-rebuild switch` when the switch
      changed it, so the new one is what's on screen. Whatever is running
      on the TV closes (back to "Who's playing?" or the menu). Off: the
      new session starts at the next reboot or
      `systemctl restart display-manager`, as on plain NixOS.
    '';
  };

  options.famidrive.display.hdr = mkOption {
    type = types.bool;
    default = false;
    description = ''
      Whether this box's TV does HDR. On: gamescope outputs HDR and Proton
      games are told they may use it. Off (the default): plain SDR, nothing
      to go wrong on a TV that doesn't support it.
    '';
  };

  options.famidrive.display.vrr = mkOption {
    type = types.bool;
    default = false;
    description = ''
      Variable refresh rate (FreeSync / HDMI VRR): the TV follows the
      game's frame rate. Smoother when a game dips below the refresh rate,
      but many TVs pulse in brightness when the frame rate is low or
      uneven. Found on the first box 2026-10-05: Jackbox Party Pack 6
      pulsed on the TV with it on. Off by default, like `hdr`: turn it on
      for a TV that handles it well.
    '';
  };

  options.famidrive.display.cursorScale = mkOption {
    type = types.nullOr types.ints.positive;
    default = 720;
    example = 1080;
    description = ''
      The mouse pointer's size, as the screen height it's drawn for
      (gamescope's `--cursor-scale-height`): at 720 it's three times as
      large on a 4K TV and one and a half times on a 1080p one. The
      pointer only shows when something needs it, such as the controller
      as a mouse over a game's setup window. A TV across the room needs
      it larger than a desktop monitor does. Found on the first box
      2026-10-10: at its own size, the pointer was tiny on a 4K TV.
      `null` leaves it at the size programs ask for.
    '';
  };

  options.famidrive.display.refresh = mkOption {
    type = types.nullOr types.ints.positive;
    default = null;
    example = 120;
    description = "Refresh rate gamescope asks the TV for. null = the TV's preferred mode.";
  };

  options.famidrive.display.scale = mkOption {
    type = types.oneOf [ types.int types.float ];
    default = 1.5;
    example = 2;
    description = ''
      How much to enlarge things for this TV. Two couch problems, one
      number:
        - Chromium's own UI scale (`--force-device-scale-factor`),
          passed to Discord, Vesktop and Equibop (`voice.nix`): their
          fonts and icons are a desktop app's, tiny from a couch.
        - Lutris's window (`stores.nix`): GTK's scale, rounded to the
          nearest whole number, with its text at this scale exactly.
        - Plymouth's boot screen (`boot.nix`), rounded to the
          nearest whole number and clamped to 1-4, the only sizes it has
          pre-rendered images for.
      It can't tell how far away a TV is: the default, 1.5, is sized for
      a 4K TV (rounding to 2 for Plymouth); use 1 on a 1080p one.
    '';
  };

  options.famidrive.cec.enable = lib.mkEnableOption ''
    HDMI-CEC TV power-on. Deferred to project phase 2 (spec.md); off by
    default and untested. AMD discrete GPUs don't expose CEC on Linux, so
    on those it also needs a USB-CEC adapter (tv-interface.md)'';

  config = lib.mkIf cfg.enable {
    programs.gamescope = {
      enable = true;
      capSysNice = false;   # see gamescopeCmd
    };

    # A switch restarts the session only when the session itself changed
    # (greetd's unit names the session and picker commands), so a new
    # session comes up without restarting display-manager by hand.
    # NixOS's own default is never, so a rebuild can't end a game.
    systemd.services.greetd.restartIfChanged = lib.mkForce cfg.session.restartOnSwitch;

    services.greetd = {
      enable = true;
      settings = if picker then {
        # "Who's playing?" on boot, after quitting ES-DE, and if a session
        # ever exits or crashes.
        default_session = {
          user = "greeter";
          command = pickerCmd;
        };
      } else
        let only = lib.head (lib.attrValues cfg.allPlayers); in {
        # One player: autologin straight into the session on boot.
        initial_session = {
          user = only.user;
          command = sessionCmd;
        };
        # If the session ever exits or crashes, greetd falls back to
        # default_session. Pointing it at the same command makes the TV
        # come back to ES-DE without a login prompt.
        default_session = {
          user = only.user;
          command = sessionCmd;
        };
      };
    };

    # Picking a player is the whole login: no password, the same as the
    # one-player box's autologin. Only for greetd (the TV), only for
    # players (group famidrive), and checked before the password prompt.
    security.pam.services.greetd.rules.auth.famidrive-player = lib.mkIf picker {
      order = config.security.pam.services.greetd.rules.auth.unix.order - 10;
      control = "sufficient";
      modulePath = "${config.security.pam.package}/lib/security/pam_succeed_if.so";
      args = [ "user" "ingroup" "famidrive" "quiet" ];
    };
    # Powering off and rebooting from the TV: ES-DE's Quit menu (as a
    # player) and "Who's playing?" (as the greeter). Without this, logind
    # asks for a password whenever anyone else is logged in, an SSH login
    # included, and the TV has no way to type one.
    security.polkit.extraConfig = ''
      polkit.addRule(function (action, subject) {
        if ((action.id.indexOf("org.freedesktop.login1.power-off") == 0
             || action.id.indexOf("org.freedesktop.login1.reboot") == 0)
            && subject.local && subject.active
            && (subject.isInGroup("famidrive") || subject.user == "greeter")) {
          return polkit.Result.YES;
        }
      });
    '';
    # Who played last starts out selected.
    systemd.tmpfiles.rules = lib.optionals picker [
      "d /var/lib/famidrive-picker 0755 greeter greeter -"
      # Players write their own picture; sticky, so not anyone else's.
      "d ${avatarDir} 3775 greeter famidrive -"
    ];

    # Steam idle in the background from boot, for players with Steam
    # configured (famidrive.lanes' "steam"), so Remote Play and remote
    # installs work before anyone's picked that player on "Who's
    # playing?". Needs lingering (a user service that starts and keeps
    # running without a login session); the session above stops it before
    # starting its own copy, and famidrive-end-session starts it again.
    users.users = lib.optionalAttrs (hasLane "steam")
      (lib.mapAttrs' (_: p: lib.nameValuePair p.user { linger = true; })
        (lib.filterAttrs (_: p: !p.isGuest) cfg.allPlayers))
      // {
        greeter.extraGroups = lib.mkIf picker [ "video" "input" "render" ];
      };

    famidrive.playerHome = { lib, famidrivePlayer, ... }:
      lib.mkIf (hasLane "steam" && !famidrivePlayer.isGuest) {
        # No gamescope, no window: a plain Xvfb, just enough of a display
        # for Steam's own UI to start. Stopped before this player's own
        # session starts Steam under gamescope (above), so there's never two.
        systemd.user.services.famidrive-steam-background = {
          Unit = {
            Description = "Steam, idle, until ${famidrivePlayer.displayName} is picked on the TV";
            After = [ "network-online.target" ];
          };
          Install.WantedBy = [ "default.target" ];
          Service = {
            Environment = "PATH=/run/current-system/sw/bin:/run/wrappers/bin";
            # Not for a player who's never signed in to Steam here: it would
            # only sit at the sign-in screen, and react to Guide on the TV's
            # pads (see the session's own Steam, above). famidrive-end-session
            # starts it again when the session they sign in from ends.
            ExecCondition = toString steamSignedIn;
            # The same Steam settings the session writes, before this Steam
            # starts too. Found on the first box 2026-10-13: another
            # player's background Steam still had "Guide Button Focuses
            # Steam" on, heard Guide on the TV's pads (players are in the
            # input group) and played its sounds under FamiDrive's menu.
            ExecStartPre = toString (pkgs.writeShellScript "famidrive-steam-background-settings" ''
              ${pkgs.famidrive-steam-config}/bin/famidrive-steam-config ${steamSettings (cfg.steam.playerLaunchOptions.${famidrivePlayer.user} or { })} \
                || echo "famidrive-steam-background: couldn't apply Steam settings" >&2
            '');
            ExecStart = "${pkgs.xvfb-run}/bin/xvfb-run -a steam -silent";
            # Asks Steam to quit, then waits for it: systemd sends SIGTERM
            # to whatever's left the moment ExecStop returns. By full path,
            # since systemd looks a command up in its own PATH, not
            # Environment's. Found on the first box 2026-10-12: a bare
            # `steam` failed (203/EXEC), so Steam was killed mid-work
            # each time a player was picked, and the session's own Steam
            # that started a second later ignored every -applaunch.
            ExecStop = toString (pkgs.writeShellScript "famidrive-steam-background-stop" ''
              steam -shutdown > /dev/null 2>&1 || true
              for _ in $(seq 1 50); do
                kill -0 "$MAINPID" 2> /dev/null || exit 0
                sleep 0.5
              done
            '');
            TimeoutStopSec = 30;
            Restart = "on-failure";
            RestartSec = 30;
          };
        };
      };

    hardware.graphics.enable = true;
    hardware.bluetooth.enable = true;
    services.pipewire = {
      enable = true;
      pulse.enable = true;
      # Full volume for a player's first time on an output, so the TV's
      # own remote is the volume control. WirePlumber's default is 40%.
      # Found on the first box 2026-10-06: a new player's sound was much
      # quieter than the existing account's. Volumes changed later are
      # kept per player, as before.
      wireplumber.extraConfig.famidrive-volume."wireplumber.settings" = {
        "device.routes.default-sink-volume" = 1.0;
      };
    };

    # HDMI-CEC: turn the TV on and switch input on boot/resume.
    # Deferred to project phase 2 (spec.md); kept as a sketch, not in v1 scope.
    # Whether this works without a USB-CEC adapter depends on the GPU
    # (open question in tv-interface.md).
    environment.systemPackages = [ pkgs.v4l-utils pkgs.mangohud ];
    systemd.services.famidrive-tv-on = lib.mkIf cfg.cec.enable {
      description = "Power on the TV over HDMI-CEC";
      wantedBy = [ "multi-user.target" "post-resume.target" ];
      after = [ "post-resume.target" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = [
          "${pkgs.v4l-utils}/bin/cec-ctl --playback"
          "${pkgs.v4l-utils}/bin/cec-ctl --to 0 --image-view-on"
          "${pkgs.v4l-utils}/bin/cec-ctl --to 0 --active-source phys-addr=1.0.0.0"   # TODO: real phys-addr
        ];
      };
    };
  };
}
