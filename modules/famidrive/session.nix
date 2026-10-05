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
      # Start Steam hidden up front. Otherwise the first `steam -applaunch`
      # brings up Steam's own client windows, which then fight the game
      # for gamescope's single focused window.
      steam -silent &
    ''}
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
  options.famidrive.display.hdr = mkOption {
    type = types.bool;
    default = false;
    description = ''
      Whether this box's TV does HDR. On: gamescope outputs HDR and Proton
      games are told they may use it. Off (the default): plain SDR, nothing
      to go wrong on a TV that doesn't support it.
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
