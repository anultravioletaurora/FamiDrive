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
{ writeShellApplication, xprop, xwininfo, xrestop, procps, util-linux, gnugrep, coreutils, socat, famidrive-status, famidrive-padmouse }:

writeShellApplication {
  name = "gamescope-fg";
  runtimeInputs = [ xprop xwininfo xrestop procps util-linux gnugrep coreutils socat famidrive-status famidrive-padmouse ];
  text = ''
    FRONTEND=1
    GAME=2
    STATUS=3   # famidrive-status, while a Steam game gets going
    run="''${XDG_RUNTIME_DIR:-/tmp/famidrive-$(id -u)}"
    mkdir -p "$run"

    base() { xprop -root -f GAMESCOPECTRL_BASELAYER_APPID 32c -set GAMESCOPECTRL_BASELAYER_APPID "$1"; }

    # The menu's music (the session plays the player's ES-DE/music through
    # mpv): paused while anything else is on screen, back when ES-DE is.
    music_paused() {
      [ -S "$run/famidrive-music.sock" ] || return 0
      printf '{"command": ["set_property", "pause", %s]}\n' "$1" \
        | socat - "UNIX-CONNECT:$run/famidrive-music.sock" > /dev/null 2>&1 || true
    }

    # Windows come and go between listing them and reading them. These
    # helpers never fail: under errexit, one window closing at the wrong
    # moment ended the whole script. Found on the first box 2026-10-05:
    # Cyberpunk's launcher windows did that, and ES-DE came back while
    # the game kept loading behind it.
    windows() {
      # gamescope's own 1x1 "steamcompmgr" window is never a candidate.
      xwininfo -root -children 2>/dev/null | awk '/^ +0x/ && !/"steamcompmgr"/ { print $1 }' || true
    }
    # A window's process: _NET_WM_PID when the app sets it, or else the X
    # server's own record of which client made the window (XRes, through
    # xrestop). Found on the first box 2026-10-06: Kodi never sets
    # _NET_WM_PID, so its window was never labelled and the screen stayed
    # black while it ran.
    window_pid() {
      local pid
      pid=$(xprop -id "$1" _NET_WM_PID 2>/dev/null | awk '/= / { print $3 }' || true)
      if [ -z "$pid" ]; then pid=$(xres_pid "$1"); fi
      echo "$pid"
    }
    xres_pid() {
      local wid line pid="" base=""
      wid=$(( $1 ))
      while IFS= read -r line; do
        case "$line" in
          *"( PID:"*) pid=''${line##*PID:}; pid=''${pid%%[!0-9]*} ;;
          *res_base*) base=$(( ''${line##*: } )) ;;
          *res_mask*)
            if [ -n "$pid" ] && [ "$(( wid & ~''${line##*: } ))" -eq "$base" ]; then
              echo "$pid"
              return
            fi
            ;;
        esac
      done < <(xrestop -b -m 1 2>/dev/null || true)
    }
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

    # Everything else (a game, Steam, Big Picture, the Media app) covers
    # ES-DE until it's gone, so the menu's music waits too.
    music_paused true
    trap 'music_paused false' EXIT

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
      status_pid=""   # the status screen's, while it's up (see below)
      # Put the game on top and stay until it's gone: until none of its
      # Steam processes (`SteamLaunch AppId=N --`) is left. Not the game's
      # install script, whose launcher is `SteamLaunch AppId=N Install=1`. Not one pid: Steam
      # may swap the process it started for another. Found on the first box
      # 2026-10-05: Cyberpunk's went through three in its first 40 s, and
      # following only the first handed the screen back to ES-DE while the
      # game played on behind it.
      follow() {
        # The status screen stays until the game's own window is up (or
        # three minutes, if a game never opens one gamescope can show).
        base "$appid,$GAME,$STATUS,769,$FRONTEND"   # Steam's windows above ES-DE, below the game
        [ -n "$status_pid" ] && status launching
        misses=0
        waited=0
        while [ "$misses" -lt 3 ]; do
          if [ -n "$status_pid" ]; then
            status_tag
            waited=$((waited + 1))
            if focusable "$appid" || [ "$waited" -ge 180 ]; then
              status_stop
            fi
          fi
          pid=$(pgrep -o -f "SteamLaunch AppId=$appid( --|$)" || true)
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
      pid=$(pgrep -o -f "SteamLaunch AppId=$appid( --|$)" || true)
      if [ -n "$pid" ]; then
        follow
        exit 0
      fi

      # The status screen (pkgs/famidrive-status): shown from the moment
      # the game is picked until its window is up, with what Steam is
      # doing (updating, processing shaders, waiting on a prompt, starting).
      # This writes the state; famidrive-status draws it.
      status_file="$run/famidrive-status.json"
      status() {
        printf '{"state": "%s", "detail": "%s"}\n' "$1" "''${2:-}" > "$status_file.new"
        mv "$status_file.new" "$status_file"
      }
      status_stop() {
        if [ -n "$status_pid" ]; then kill "$status_pid" 2>/dev/null || true; fi
        status_pid=""
        rm -f "$status_file"
      }
      # Whatever label the window already has: it's in the same session as
      # the outer gamescope-fg, whose loop may label it GAME first. Found on
      # the first box 2026-10-05: then the status screen stayed hidden and
      # Street Fighter 6 showed Steam's own shader dialog instead.
      status_tag() {
        for wid in $(windows); do
          if [ "$(window_pid "$wid")" = "$status_pid" ] \
              && ! xprop -id "$wid" STEAM_GAME 2>/dev/null | grep -q "= $STATUS$"; then
            tag "$wid" "$STATUS"
          fi
        done
      }
      focusable() { xprop -root GAMESCOPE_FOCUSABLE_APPS 2>/dev/null | grep -qE "[ ,]$1(,|$)"; }
      # descends PID ROOT: whether PID is ROOT or runs under it.
      descends() {
        p="$1"
        while [ -n "$p" ] && [ "$p" -gt 1 ]; do
          [ "$p" = "$2" ] && return 0
          p=$(awk '/^PPid:/ { print $2 }' "/proc/$p/status" 2>/dev/null || true)
        done
        return 1
      }
      # The windows of a game's first-time setup, labelled as the game so
      # they're shown and can be answered. Found on the first box
      # 2026-10-06: Star Wars Jedi: Survivor's install script runs the EA
      # app's installer, which waits on a "Let's go" button. Its window
      # carries no app id, so gamescope never showed it, and ES-DE came back
      # after three minutes over a setup still waiting.
      tag_install() {
        for wid in $(windows); do
          untagged "$wid" || continue
          xwininfo -id "$wid" 2>/dev/null | grep -q IsViewable || continue
          wpid=$(window_pid "$wid")
          [ -n "$wpid" ] || continue
          if descends "$wpid" "$1"; then tag "$wid" "$appid"; fi
        done
      }
      # The controller as a mouse and keyboard while Steam waits on a prompt
      # (famidrive-padmouse): Steam's own dialogs (a EULA, a cloud
      # conflict) take only a mouse. Found on the first box 2026-10-07:
      # GTA V Enhanced's EULA couldn't be accepted with a controller.
      pointer_pid=""
      pointer() {
        if [ "$1" = on ] && [ -z "$pointer_pid" ]; then
          famidrive-padmouse & pointer_pid=$!
        elif [ "$1" = off ] && [ -n "$pointer_pid" ]; then
          kill "$pointer_pid" 2>/dev/null || true
          pointer_pid=""
        fi
      }
      trap 'pointer off; status_stop; music_paused false' EXIT

      # This game's launch steps since the launch. Read whole, not piped into
      # grep -q, which under pipefail can fail on tail's SIGPIPE.
      since() { tail -n +"$((seen + 1))" "$log" 2>/dev/null | grep -F "GameAction [AppID $appid, " || true; }
      # While Steam gets the game going, the status screen is on top, then
      # Steam's own windows, then ES-DE. When Steam asks something (a
      # first-launch "which version?" picker, a EULA, the controller
      # prompt), its windows go on top instead, so the question can be
      # answered.
      status asking
      famidrive-status "$appid" "$status_file" &
      status_pid=$!
      base "$STATUS,769,$FRONTEND"
      steam -applaunch "$appid"

      # -applaunch only hands the game to the running Steam client and
      # returns. Wait for Steam's launcher (`reaper SteamLaunch AppId=N`),
      # or for Steam to log that the launch failed.
      #
      # No overall time limit: Steam may be updating the game, processing
      # its shaders, or running its first-time setup (which can wait on
      # someone answering it). Found on the first box 2026-10-05: shader processing
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
        steps=$(since)
        # The game's processes count only once Steam says it has started
        # the game. Found on the first box 2026-10-05: Steam runs a game's
        # install script (ProcessingInstallScript) through the same
        # `SteamLaunch AppId=N` launcher, before processing its shaders.
        # Taking that for the game showed "Starting", then handed the
        # screen back to ES-DE when the script ended, while Steam carried
        # on with the shaders behind it.
        if grep -qE "changed task to (WaitingGameWindow|Completed)" <<< "$steps"; then
          pid=$(pgrep -o -f "SteamLaunch AppId=$appid( --|$)" || true)
          [ -n "$pid" ] && break
        fi
        if grep -qE "changed task to Failed|LaunchApp failed" <<< "$steps"; then
          # Found on the first box 2026-10-05: when a game needs an update,
          # Steam may fail the launch (AppError_19) while the update itself
          # carries on. Wait for the update, then ask once more.
          if [ -z "$retried" ] && grep -q DownloadingDepots <<< "$steps"; then
            retried=1
            status updating
            base "$STATUS,769,$FRONTEND"
            while ! grep -qE '"StateFlags"[[:space:]]+"4"' "$manifest" 2>/dev/null; do
              status_tag
              sleep 0.5
            done
            seen=$(wc -l < "$log" 2>/dev/null || echo 0)
            idle=0
            last=""
            steam -applaunch "$appid"
            continue
          fi
          echo "gamescope-fg: Steam couldn't launch $appid; see $log" >&2
          err=$(grep -oE "AppError_[0-9]+" <<< "$steps" | tail -n 1 || true)
          status failed "Steam stopped the launch''${err:+ ($err)}."
          base "$STATUS,$FRONTEND"
          for _ in $(seq 1 10); do status_tag; sleep 0.5; done
          base "$FRONTEND"
          exit 1
        fi
        # Steam is busy while its last step is a long one that hasn't
        # finished: updating, processing shaders, or waiting on a prompt.
        now=$(tail -n 1 <<< "$steps")
        install=$(pgrep -o -f "SteamLaunch AppId=$appid Install=1" || true)
        case "$now" in
          *RunningInstallScript*) state=installing ;;
          *DownloadingDepots*) state=updating ;;
          *ProcessingShaderCache*) state=shaders ;;
          *"waiting for user response to CreatingProcess"*) state=asking ;;
          *"waiting for user response"*) state=prompt ;;
          *) state=asking ;;
        esac
        # Its launcher running counts too: picked again while an earlier
        # launch's setup still waits, Steam logs nothing new.
        if [ -n "$install" ] && [ "$state" = asking ]; then state=installing; fi
        status "$state"
        if [ "$state" = prompt ]; then pointer on; else pointer off; fi
        if [ "$state" = prompt ]; then
          base "769,$STATUS,$FRONTEND"
        elif [ "$state" = installing ]; then
          # Its windows over the status screen: they may ask something.
          [ -n "$install" ] && tag_install "$install"
          base "$appid,$STATUS,769,$FRONTEND"
        else
          base "$STATUS,769,$FRONTEND"
        fi
        status_tag
        if [ "$now" != "$last" ] || [ -n "$install" ]; then
          last="$now"
          idle=0
        elif ! grep -qE "DownloadingDepots|ProcessingShaderCache|RunningInstallScript|waiting for user response" <<< "$now"; then
          idle=$((idle + 1))
        fi
        sleep 0.5
      done
      pointer off   # the game has its pad to itself
      if [ -z "$pid" ]; then
        echo "gamescope-fg: Steam never started $appid" >&2
        status failed "Steam didn't start the game and stopped reporting progress."
        base "$STATUS,$FRONTEND"
        for _ in $(seq 1 10); do status_tag; sleep 0.5; done
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
