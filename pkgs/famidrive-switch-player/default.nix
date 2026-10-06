# Settings → Switch Player: end this player's session, so greetd brings
# back "Who's playing?" (pkgs/famidrive-picker).
#
# Steam is asked to quit first and given a moment: it keeps its login and
# downloads tidy that way. Then the whole session ends (logind), which
# takes everything else in it along.
{ writeShellApplication, procps, systemd, coreutils }:

writeShellApplication {
  name = "famidrive-switch-player";
  runtimeInputs = [ procps systemd coreutils ];
  text = ''
    if pgrep -u "$(id -u)" -x steam > /dev/null; then
      steam -shutdown > /dev/null 2>&1 || true
      for _ in $(seq 1 20); do
        pgrep -u "$(id -u)" -x steam > /dev/null || break
        sleep 0.5
      done
    fi
    if [ -n "''${XDG_SESSION_ID:-}" ]; then
      exec loginctl terminate-session "$XDG_SESSION_ID"
    fi
    # No logind session id: end gamescope, which ends the session greetd started.
    exec pkill -u "$(id -u)" -x gamescope
  '';
}
