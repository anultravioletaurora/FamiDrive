# Boot straight into ES-DE inside gamescope, with no display manager UI and no DE.
# Steam is one entry on the menu, not the shell (base-os.md).
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  # Writes famidrive.steam.compatTools into Steam's CompatToolMapping (the
  # per-game "Force a compatibility tool" setting). Steam rewrites
  # config.vdf when it exits, so this only sticks while Steam isn't
  # running: the session runs it just before starting Steam.
  steamCompat = pkgs.writers.writePython3 "famidrive-steam-compat" {
    flakeIgnore = [ "E501" ];
  } ''
    # A narrow text edit, not a VDF round trip: a parser rewrites the rest
    # of the file too (tabs, escaped newlines), and Steam owns that.
    import json
    import re
    import sys
    from pathlib import Path

    steam = Path.home() / ".local/share/Steam"
    path = steam / "config/config.vdf"
    if not path.exists():
        sys.exit(0)   # Steam hasn't been set up yet; next session


    def installed():
        """Installed games' names (lowercased) to app ids, in every library."""
        libraries = [steam / "steamapps"]
        try:
            folders = (steam / "steamapps/libraryfolders.vdf").read_text(errors="replace")
            libraries += [Path(p) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', folders)]
        except OSError:
            pass
        names = {}
        for lib in libraries:
            for acf in lib.glob("appmanifest_*.acf"):
                text = acf.read_text(errors="replace")
                appid = re.search(r'"appid"\s+"(\d+)"', text)
                name = re.search(r'"name"\s+"([^"]+)"', text)
                if appid and name:
                    names[name.group(1).lower()] = appid.group(1)
        return names


    # Games may be given by name (as ES-DE shows them) or by app id.
    wanted, names = {}, None
    for game, tool in json.loads(sys.argv[1]).items():
        if not game.isdigit():
            names = installed() if names is None else names
            if game.lower() not in names:
                print(f"famidrive-steam-compat: {game!r} isn't installed; skipped", file=sys.stderr)
                continue
            game = names[game.lower()]
        wanted[game] = tool
    if not wanted:
        sys.exit(0)
    lines = path.read_text(errors="replace").split("\n")

    head = next((i for i, line in enumerate(lines)
                 if line.strip().lower() == '"compattoolmapping"'), None)
    if head is None or lines[head + 1].strip() != "{":
        # Steam writes the section the first time any game is forced to a tool.
        print("famidrive-steam-compat: no CompatToolMapping in config.vdf yet", file=sys.stderr)
        sys.exit(0)
    indent = re.match(r"\s*", lines[head]).group(0) + "\t"


    def block_end(i):
        """Index of the '}' closing the block whose '{' is at line i."""
        depth = 0
        for j in range(i, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth == 0:
                return j
        raise SystemExit("famidrive-steam-compat: unbalanced config.vdf")


    end = block_end(head + 1)
    i = head + 2
    while i < end:   # drop the entries being replaced
        key = lines[i].strip().strip('"')
        if key in wanted and lines[i + 1].strip() == "{":
            close = block_end(i + 1)
            del lines[i:close + 1]
            end -= close + 1 - i
        else:
            i += 1

    new = []
    for appid, tool in wanted.items():
        new += [f'{indent}"{appid}"', f"{indent}{{",
                f'{indent}\t"name"\t\t"{tool}"',
                f'{indent}\t"config"\t\t""',
                f'{indent}\t"priority"\t\t"250"',
                f"{indent}}}"]
    lines[head + 2:head + 2] = new

    backup = path.with_name("config.vdf.famidrive-backup")
    if not backup.exists():
        backup.write_text(path.read_text(errors="replace"))   # once, before FamiDrive's first edit
    path.write_text("\n".join(lines))
  '';

  famidriveSession = pkgs.writeShellScript "famidrive-session" ''
    ${lib.optionalString cfg.display.hdr ''
      # Proton games only output HDR when asked; gamescope (--hdr-enabled)
      # carries it to the TV. SDR content is unaffected.
      export DXVK_HDR=1
    ''}
    ${lib.optionalString (hasLane "steam") ''
      ${lib.optionalString (cfg.steam.compatTools != { }) ''
        ${steamCompat} ${lib.escapeShellArg (builtins.toJSON cfg.steam.compatTools)} \
          || echo "famidrive-session: couldn't set Steam compatibility tools" >&2
      ''}
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
