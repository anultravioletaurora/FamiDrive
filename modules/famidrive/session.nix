# Boot straight into ES-DE inside gamescope, with no display manager UI and no DE.
# Steam is one entry on the menu, not the shell (base-os.md).
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  famidriveSession = pkgs.writeShellScript "famidrive-session" ''
    ${lib.optionalString cfg.display.hdr ''
      # Proton games only output HDR when asked; gamescope (--hdr-enabled)
      # carries it to the TV. SDR content is unaffected.
      export DXVK_HDR=1
    ''}
    ${lib.optionalString (hasLane "steam") ''
      # Proton pins and Steam Input, written while Steam isn't running
      # (pkgs/famidrive-steam-config).
      ${pkgs.famidrive-steam-config}/bin/famidrive-steam-config ${lib.escapeShellArg (builtins.toJSON {
        inherit (cfg.steam) compatTools steamInput;
      })} || echo "famidrive-session: couldn't apply Steam settings" >&2
      # Start Steam hidden up front. Otherwise the first `steam -applaunch`
      # brings up Steam's own client windows, which then fight the game
      # for gamescope's single focused window.
      steam -silent &
    ''}
    # Nothing is running yet: clear what a crashed launch may have left.
    rm -f "''${XDG_RUNTIME_DIR:-/nonexistent}"/famidrive-game.*
    # Hold Select + Start on any controller to quit the running game
    # (pkgs/famidrive-quit). It exits on its own when the session ends.
    ${pkgs.famidrive-quit}/bin/famidrive-quit &
    # ES-DE through gamescope-fg, which labels its window and makes it what
    # gamescope shows (nothing does that without Steam; see gamescope-fg).
    exec ${pkgs.gamescope-fg}/bin/gamescope-fg --frontend ${pkgs.es-de}/bin/es-de --no-splash
  '';

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
  ] ++ lib.optionals cfg.display.vrr [
    "--adaptive-sync"
  ] ++ lib.optionals cfg.display.hdr [
    "--hdr-enabled"
  ] ++ lib.optionals (cfg.display.refresh != null) [
    # gamescope otherwise takes the TV's preferred mode, which is usually 60 Hz.
    "-r" (toString cfg.display.refresh)
  ] ++ [
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
    exec ${gamescopeCmd} > "$log/session.log" 2>&1
  ''}";
in
{
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

  options.famidrive.display.refresh = mkOption {
    type = types.nullOr types.ints.positive;
    default = null;
    example = 120;
    description = "Refresh rate gamescope asks the TV for. null = the TV's preferred mode.";
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

    services.greetd = {
      enable = true;
      settings = {
        # Autologin straight into the session on boot.
        initial_session = {
          user = cfg.user;
          command = sessionCmd;
        };
        # If the session ever exits or crashes, greetd falls back to
        # default_session. Pointing it at the same command makes the TV
        # come back to ES-DE without a login prompt.
        default_session = {
          user = cfg.user;
          command = sessionCmd;
        };
      };
    };

    hardware.graphics.enable = true;
    hardware.bluetooth.enable = true;
    services.pipewire = {
      enable = true;
      pulse.enable = true;
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
