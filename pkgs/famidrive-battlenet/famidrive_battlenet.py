"""famidrive-battlenet play LUTRIS_DATA_DIR GAME_ID

Runs beside a Lutris launch and puts the player in a Battle.net game
instead of Battle.net's page for it.

A Battle.net game in Lutris is Battle.net.exe with --exec="launch <code>"
(Lutris's install scripts, such as Black Ops Cold War's). Battle.net
ignores that on a cold start: it signs in and shows the game's page,
and waits for Play. Found on the first box 2026-10-15, in Battle.net's
own log: "Command line arguments: --exec=launch ZEUS", then no
LaunchBinary until Play was pressed, every time. Sent again to a
Battle.net that's up, the same command launches the game at once: a
second Battle.net.exe finds the first ("IPC ShMem mode=client") and
hands it on.

The second one has to run where the first one does. Lutris runs it
through umu, in a sandbox with a /tmp of its own, where Wine keeps the
socket to its server; a second umu-run makes a new sandbox, and its
Battle.net.exe found no Battle.net and started another. So this joins
the running Battle.net's user and mount namespaces (nsenter) and runs
Proton's wine there, with Battle.net's own environment.

So: wait for this launch's Battle.net to sign in and show its window,
then send the launch, and again if the game doesn't start, until it
does. Nothing at all for a Lutris game that isn't a Battle.net one, or
when Battle.net starts the game by itself.
"""

import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import yaml

NSENTER = os.environ.get("FAMIDRIVE_NSENTER", "@nsenter@")
PROC = Path(os.environ.get("FAMIDRIVE_PROC", "/proc"))

WAIT_FOR_SIGN_IN = 600   # seconds: a sign-in can need the player (a security check)
SETTLE = 3               # seconds after the window shows, before the first send
TRIES = 3
WAIT_FOR_GAME = 15       # seconds after each send

# What Battle.net's log says. The window shows once it has signed in.
SIGNED_IN = "Login triggered"
WINDOW = "Attempting to show main window"
LAUNCHED = "LaunchBinary"

# Settings in Battle.net's own environment that belong to that one
# process: Wine's handle on its server, and its loader's.
PROCESS_ONLY = ("WINESERVERSOCKET=", "WINELOADERNOEXEC=", "WINEPRELOADRESERVE=")


def battlenet_game(lutris_dir, game_id):
    """(prefix, the --exec argument) for a Battle.net game, or None."""
    try:
        con = sqlite3.connect(f"{(lutris_dir / 'pga.db').as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            row = con.execute("SELECT configpath FROM games WHERE id = ?", (int(game_id),)).fetchone()
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return None
    if not row or not row[0]:
        return None
    # Game configs are beside the database, unless an older Lutris left
    # them in ~/.config/lutris (lutris/settings.py).
    games = lutris_dir / "games"
    if not games.is_dir():
        games = Path.home() / ".config/lutris/games"
    try:
        game = (yaml.safe_load((games / f"{row[0]}.yml").read_text()) or {}).get("game") or {}
    except (OSError, yaml.YAMLError):
        return None
    exe, args, prefix = str(game.get("exe") or ""), str(game.get("args") or ""), game.get("prefix")
    m = re.search(r'--exec=("[^"]*"|\S+)', args)
    if not m or not prefix or Path(exe.replace("\\", "/")).name.lower() != "battle.net.exe":
        return None
    return Path(prefix), "--exec=" + m.group(1).strip('"')


def newest_log(prefix, since):
    """This launch's Battle.net log: the newest one started since."""
    logs = [p for p in prefix.glob("drive_c/users/*/AppData/Local/Battle.net/Logs/battle.net-*.log")
            if p.stat().st_mtime >= since]
    return max(logs, key=lambda p: p.stat().st_mtime, default=None)


def read(path):
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def battlenet_process(prefix):
    """The running Battle.net's pid, in this prefix: the main process,
    not one of its Chromium helpers (--type=...)."""
    for d in PROC.iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = (d / "cmdline").read_bytes().split(b"\0")
            env = (d / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        cmd = argv[0].decode(errors="replace").replace("\\", "/")
        if not cmd.lower().endswith("/battle.net.exe") or any(a.startswith(b"--type=") for a in argv[1:]):
            continue
        for e in env:
            if e.startswith(b"STEAM_COMPAT_DATA_PATH=") and Path(e[23:].decode()).resolve() == prefix.resolve():
                return int(d.name), env
    return None


def send(pid, env, exec_arg):
    """Battle.net.exe exec_arg, beside the running Battle.net."""
    keep = [e.decode(errors="replace") for e in env if e and not e.startswith(tuple(p.encode() for p in PROCESS_ONLY))]
    cmd = [NSENTER, "-t", str(pid), "-U", "-m", "--preserve-credentials", "--",
           "env", "-i", *keep, "wine", "C:\\Program Files (x86)\\Battle.net\\Battle.net.exe", exec_arg]
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"famidrive-battlenet: couldn't send {exec_arg}: {e}", file=sys.stderr)


def play(lutris_dir, game_id, sleep=time.sleep, clock=time.time):
    game = battlenet_game(lutris_dir, game_id)
    if game is None:
        return
    prefix, exec_arg = game
    started = clock() - 2
    log = None
    while clock() - started < WAIT_FOR_SIGN_IN:
        # Newest each time: Battle.net can restart itself (an update).
        log = newest_log(prefix, started)
        text = read(log) if log else ""
        if LAUNCHED in text:
            return   # Battle.net started it by itself
        if SIGNED_IN in text and WINDOW in text:
            break
        sleep(1)
    else:
        return
    sleep(SETTLE)
    for _ in range(TRIES):
        if LAUNCHED in read(log):
            return
        running = battlenet_process(prefix)
        if running is None:
            return   # Battle.net closed
        send(*running, exec_arg)
        for _ in range(WAIT_FOR_GAME):
            if LAUNCHED in read(log):
                return
            sleep(1)
    print(f"famidrive-battlenet: Battle.net didn't start the game after {TRIES} tries", file=sys.stderr)


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "play":
        sys.exit("usage: famidrive-battlenet play LUTRIS_DATA_DIR GAME_ID")
    play(Path(sys.argv[2]), sys.argv[3])


if __name__ == "__main__":
    main()
