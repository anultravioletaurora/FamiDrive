# The end of a player's session: ES-DE has closed (its Quit menu, or a
# crash). Then greetd brings back "Who's playing?" (pkgs/famidrive-picker),
# or, on a one-player box, starts the session again.
#
# Steam is asked to quit first and given a moment: it keeps its login and
# downloads tidy that way, and doesn't stay behind in a session nobody's
# using. Then the whole session ends (logind), which takes everything else
# in it along.
#
# Its idle background copy (famidrive-steam-background, session.nix) comes
# back once it's gone, so Remote Play and remote installs keep working
# until this player is picked again.
{ writeShellApplication, procps, systemd, coreutils }:

writeShellApplication {
  name = "famidrive-end-session";
  runtimeInputs = [ procps systemd coreutils ];
  text = ''
    if pgrep -u "$(id -u)" -x steam > /dev/null; then
      steam -shutdown > /dev/null 2>&1 || true
      for _ in $(seq 1 20); do
        pgrep -u "$(id -u)" -x steam > /dev/null || break
        sleep 0.5
      done
    fi
    systemctl --user start famidrive-steam-background.service > /dev/null 2>&1 || true
    if [ -n "''${XDG_SESSION_ID:-}" ]; then
      exec loginctl terminate-session "$XDG_SESSION_ID"
    fi
    # No logind session id: end gamescope, which ends the session greetd started.
    exec pkill -u "$(id -u)" -x gamescope
  '';
}
