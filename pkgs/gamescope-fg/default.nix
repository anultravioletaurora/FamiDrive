# Window focus without Steam (base-os.md "The real cost: window focus").
#
# gamescope runs in Steam mode (-e). In that mode it only shows windows
# carrying a STEAM_GAME app id, and which app is on top is chosen by the
# GAMESCOPECTRL_BASELAYER_APPID list on the root window, a job Steam
# normally does. Here this script does it. Found on the first box 2026-10-05:
# without it, ES-DE ran fine but gamescope showed a black screen, because
# nothing was "focusable".
#
#   gamescope-fg --frontend CMD...   ES-DE: tag its windows FRONTEND, make it the base layer
#   gamescope-fg CMD...              a game: tag its windows GAME and put it on top of
#                                    the frontend until CMD exits
#   gamescope-fg --steam APPID       a Steam game: launch it through the running Steam
#                                    client, put it on top, and wait until it exits
#   gamescope-fg --steam bigpicture  Steam's own UI (per-game Proton, launch options,
#                                    downloads), on top until it's closed
#
# Only windows from the program's own session are tagged (each runs under
# setsid, matched by _NET_WM_PID). Found on the first box 2026-10-05: tagging
# every untagged window also caught Steam's hidden helper windows, which
# would then come up over a game.
#
# While a game runs, famidrive-quit (the Select + Start combo) finds it
# through $XDG_RUNTIME_DIR: famidrive-game.pgid holds a game's process
# group; famidrive-game.tree holds a Steam game's root process, whose
# whole tree gets closed (it isn't in a group of its own);
# famidrive-game.close holds a command to run instead of killing anything
# (Big Picture: closing it must not take the Steam client with it).
{ writeShellApplication, xprop, xwininfo, procps, util-linux, gnugrep, coreutils }:

writeShellApplication {
  name = "gamescope-fg";
  runtimeInputs = [ xprop xwininfo procps util-linux gnugrep coreutils ];
  text = ''
    FRONTEND=1
    GAME=2
    run="''${XDG_RUNTIME_DIR:-/tmp/famidrive-$(id -u)}"
    mkdir -p "$run"

    base() { xprop -root -f GAMESCOPECTRL_BASELAYER_APPID 32c -set GAMESCOPECTRL_BASELAYER_APPID "$1"; }

    # Windows come and go between listing them and reading them. These
    # helpers never fail: under errexit, one window closing at the wrong
    # moment ended the whole script. Found on the first box 2026-10-05:
    # Cyberpunk's launcher windows did that, and ES-DE came back while
    # the game kept loading behind it.
    windows() {
      # gamescope's own 1x1 "steamcompmgr" window is never a candidate.
      xwininfo -root -children 2>/dev/null | awk '/^ +0x/ && !/"steamcompmgr"/ { print $1 }' || true
    }
    window_pid() { xprop -id "$1" _NET_WM_PID 2>/dev/null | awk '/= / { print $3 }' || true; }
    untagged() { ! xprop -id "$1" STEAM_GAME 2>/dev/null | grep -q " = "; }
    tag() { xprop -id "$1" -f STEAM_GAME 32c -set STEAM_GAME "$2" 2>/dev/null || true; }

    # tag_session ID SID: label untagged windows whose process is in session SID.
    tag_session() {
      for wid in $(windows); do
        untagged "$wid" || continue
        wpid=$(window_pid "$wid")
        [ -n "$wpid" ] || continue
        [ "$(ps -o sid= -p "$wpid" 2>/dev/null | tr -d ' ')" = "$2" ] || continue
        tag "$wid" "$1"
      done
    }

    if [ "''${1:-}" = "--frontend" ]; then
      shift
      setsid "$@" &
      pid=$!
      # Wait for the frontend's window, then make it what gamescope shows.
      for _ in $(seq 1 100); do
        tag_session "$FRONTEND" "$pid"
        xprop -root GAMESCOPE_FOCUSABLE_APPS 2>/dev/null | grep -qE "[ ,]$FRONTEND(,|$)" && break
        sleep 0.2
      done
      base "$FRONTEND"
      wait "$pid"
      exit $?
    fi

    if [ "''${1:-}" = "--steam" ] && [ "''${2:-}" = "bigpicture" ]; then
      echo "steam steam://close/bigpicture" > "$run/famidrive-game.close"
      steam steam://open/bigpicture
      base "769,$FRONTEND"   # 769: the app id Steam gives its own windows
      bp_shown() {
        wid=$(xwininfo -root -children 2>/dev/null | awk '/"Steam Big Picture Mode"/ { print $1; exit }' || true)
        [ -n "$wid" ] && xwininfo -id "$wid" 2>/dev/null | grep -q IsViewable
      }
      for _ in $(seq 1 120); do bp_shown && break; sleep 0.5; done
      # Closing Big Picture (its own Exit, or Select + Start) hides the window.
      while bp_shown; do sleep 1; done
      rm -f "$run/famidrive-game.close"
      base "$FRONTEND"
      exit 0
    fi

    if [ "''${1:-}" = "--steam" ]; then
      appid="$2"
      log="$HOME/.local/share/Steam/logs/console_log.txt"
      # Games in the default library only; others don't get the update retry.
      manifest="$HOME/.local/share/Steam/steamapps/appmanifest_$appid.acf"
      seen=$(wc -l < "$log" 2>/dev/null || echo 0)
      # Put the game on top and stay until it's gone: until none of its
      # Steam processes (`SteamLaunch AppId=N`) is left. Not one pid: Steam
      # may swap the process it started for another. Found on the first box
      # 2026-10-05: Cyberpunk's went through three in its first 40 s, and
      # following only the first handed the screen back to ES-DE while the
      # game played on behind it.
      follow() {
        base "$appid,$GAME,769,$FRONTEND"   # Steam's windows above ES-DE, below the game
        misses=0
        while [ "$misses" -lt 3 ]; do
          pid=$(pgrep -o -f "SteamLaunch AppId=$appid( |$)" || true)
          if [ -z "$pid" ]; then
            misses=$((misses + 1))
          else
            misses=0
            echo "$pid" > "$run/famidrive-game.tree"
          fi
          # Steam's game windows normally come labelled with the app id. Any
          # that don't get it from the SteamGameId their process was started with.
          for wid in $(windows); do
            untagged "$wid" || continue
            wpid=$(window_pid "$wid")
            [ -n "$wpid" ] || continue
            tr '\0' '\n' < "/proc/$wpid/environ" 2>/dev/null | grep -qx "SteamGameId=$appid" && tag "$wid" "$appid"
          done
          sleep 1
        done
        rm -f "$run/famidrive-game.tree"
        base "$FRONTEND"
      }

      # Picked again while it's still running (say ES-DE came back over
      # it): bring it back instead of asking Steam, which would refuse.
      pid=$(pgrep -o -f "SteamLaunch AppId=$appid( |$)" || true)
      if [ -n "$pid" ]; then
        follow
        exit 0
      fi

      # This game's launch steps since the launch. Read whole, not piped into
      # grep -q, which under pipefail can fail on tail's SIGPIPE.
      since() { tail -n +"$((seen + 1))" "$log" 2>/dev/null | grep -F "GameAction [AppID $appid, " || true; }
      # While Steam gets the game going, its own windows go above ES-DE:
      # a first-launch "which version?" picker, a EULA or an error would
      # otherwise wait unseen behind it. With no Steam window up, gamescope
      # falls through to ES-DE.
      base "769,$FRONTEND"
      steam -applaunch "$appid"

      # -applaunch only hands the game to the running Steam client and
      # returns. Wait for Steam's launcher (`reaper SteamLaunch AppId=N`),
      # or for Steam to log that the launch failed.
      #
      # No overall time limit: Steam may be updating the game or processing
      # its shaders. Found on the first box 2026-10-05: shader processing
      # alone took up to 5 min 41 s, past the old five-minute limit, and
      # ES-DE came back over a launch that was still going. The only limit
      # is on silence: two minutes with no launch step logged and no game
      # (Steam ignored the request, or the game died before its launcher
      # was seen). Select + Start gives up at any time.
      pid=""
      retried=""
      idle=0
      last=""
      while [ "$idle" -lt 240 ]; do
        pid=$(pgrep -o -f "SteamLaunch AppId=$appid( |$)" || true)
        [ -n "$pid" ] && break
        steps=$(since)
        if grep -qE "changed task to Failed|LaunchApp failed" <<< "$steps"; then
          # Found on the first box 2026-10-05: when a game needs an update,
          # Steam may fail the launch (AppError_19) while the update itself
          # carries on. Wait for the update, then ask once more.
          if [ -z "$retried" ] && grep -q DownloadingDepots <<< "$steps"; then
            retried=1
            while ! grep -qE '"StateFlags"[[:space:]]+"4"' "$manifest" 2>/dev/null; do
              sleep 0.5
            done
            seen=$(wc -l < "$log" 2>/dev/null || echo 0)
            idle=0
            last=""
            steam -applaunch "$appid"
            continue
          fi
          echo "gamescope-fg: Steam couldn't launch $appid; see $log" >&2
          base "$FRONTEND"
          exit 1
        fi
        # Steam is busy while its last step is a long one that hasn't
        # finished: updating, processing shaders, or waiting on a prompt.
        now=$(tail -n 1 <<< "$steps")
        if [ "$now" != "$last" ]; then
          last="$now"
          idle=0
        elif ! grep -qE "DownloadingDepots|ProcessingShaderCache|waiting for user response" <<< "$now"; then
          idle=$((idle + 1))
        fi
        sleep 0.5
      done
      if [ -z "$pid" ]; then
        echo "gamescope-fg: Steam never started $appid" >&2
        base "$FRONTEND"
        exit 1
      fi

      follow
      exit 0
    fi

    # setsid gives the game its own session and process group. A background
    # job of this (non-interactive) shell isn't a group leader, so setsid
    # execs in place and $! is the game's pid, session id and group id.
    setsid "$@" &
    pid=$!
    echo "$pid" > "$run/famidrive-game.pgid"
    base "$GAME,$FRONTEND"   # the game on top, ES-DE underneath
    # Keep labelling while the game runs: many open their real window late
    # (Dolphin's render window comes after its main one).
    while kill -0 "$pid" 2>/dev/null; do
      tag_session "$GAME" "$pid"
      sleep 0.5
    done
    # The tree file too: a quit kills a Steam launch's script (in this
    # group) before it can clean up after itself.
    rm -f "$run/famidrive-game.pgid" "$run/famidrive-game.tree"
    base "$FRONTEND"
    wait "$pid"
  '';
}
