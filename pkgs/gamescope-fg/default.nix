# Window focus without Steam (base-os.md "The real cost: window focus").
#
# gamescope runs in Steam mode (-e). In that mode it only shows windows
# carrying a STEAM_GAME app id, and which app is on top is chosen by the
# GAMESCOPECTRL_BASELAYER_APPID list on the root window, a job Steam
# normally does. Here this script does it. Found on the first box 2026-10-05:
# without it, ES-DE ran fine but gamescope showed a black screen, because
# nothing was "focusable".
#
#   gamescope-fg --frontend CMD...   ES-DE: tag its window FRONTEND, make it the base layer
#   gamescope-fg CMD...              a game: tag every new window GAME and put it on
#                                    top of the frontend until CMD exits
#
# A game runs in its own process group, whose id is kept in
# $XDG_RUNTIME_DIR/famidrive-game.pgid while it runs. famidrive-quit (the
# Select + Start combo) reads it to close the game and everything it started.
{ writeShellApplication, xprop, xwininfo, procps, util-linux }:

writeShellApplication {
  name = "gamescope-fg";
  runtimeInputs = [ xprop xwininfo procps util-linux ];
  text = ''
    FRONTEND=1
    GAME=2

    base() { xprop -root -f GAMESCOPECTRL_BASELAYER_APPID 32c -set GAMESCOPECTRL_BASELAYER_APPID "$1"; }

    # Label every top-level window that doesn't have an app id yet. Windows
    # already labelled (ES-DE's, or ones Steam labels itself) are left alone.
    tag_new() {
      # gamescope's own 1x1 "steamcompmgr" window is never a candidate.
      for wid in $(xwininfo -root -children 2>/dev/null | awk '/^ +0x/ && !/"steamcompmgr"/ { print $1 }'); do
        if ! xprop -id "$wid" STEAM_GAME 2>/dev/null | grep -q " = "; then
          xprop -id "$wid" -f STEAM_GAME 32c -set STEAM_GAME "$1" 2>/dev/null || true
        fi
      done
    }

    if [ "''${1:-}" = "--frontend" ]; then
      shift
      "$@" &
      pid=$!
      # Wait for the frontend's window, then make it what gamescope shows.
      for _ in $(seq 1 100); do
        tag_new "$FRONTEND"
        xprop -root GAMESCOPE_FOCUSABLE_APPS 2>/dev/null | grep -qE "= [0-9]" && break
        sleep 0.2
      done
      base "$FRONTEND"
      wait "$pid"
      exit $?
    fi

    # setsid gives the game its own process group. A background job of this
    # (non-interactive) shell isn't a group leader, so setsid execs in place
    # and $! is the game's pid, which is also its group id.
    setsid "$@" &
    pid=$!
    pgid_file="''${XDG_RUNTIME_DIR:-/tmp/famidrive-$(id -u)}/famidrive-game.pgid"
    mkdir -p "$(dirname "$pgid_file")"
    echo "$pid" > "$pgid_file"
    base "$GAME,$FRONTEND"   # the game on top, ES-DE underneath
    # Keep labelling while the game runs: many open their real window late
    # (Dolphin's render window comes after its main one).
    while kill -0 "$pid" 2>/dev/null; do
      tag_new "$GAME"
      sleep 0.5
    done
    rm -f "$pgid_file"
    base "$FRONTEND"
    wait "$pid"
  '';
}
