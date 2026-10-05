"""famidrive-quit: hold Select + Start on any controller to quit the game.

The same way out of every emulator, Steam game and the Media app, with no
per-emulator hotkey setup. gamescope-fg starts each game in its own process
group and writes that group's id to $XDG_RUNTIME_DIR/famidrive-game.pgid.
A Steam game is started by the Steam client instead, so for those it writes
the game's root process to famidrive-game.tree, and the whole tree under it
is closed. Something that must be closed politely instead (Steam's Big
Picture, which is the Steam client itself) leaves a command in
famidrive-game.close, and that is run instead. This watches every gamepad (read-only, never grabbed, so the game still
sees every press), and when Select + Start are held for HOLD seconds it
asks the game to close (SIGTERM), then force-closes it (SIGKILL) if it's
still there after GRACE seconds. ES-DE comes back when the game is gone.

Runs for the life of the session: started by famidrive-session, and exits
when that goes away.
"""

import os
import select
import shlex
import signal
import subprocess
import threading
import time
from pathlib import Path

import evdev
from evdev import ecodes as e

HOLD = 1.0      # seconds both buttons must stay down
GRACE = 5.0     # seconds between "please close" and "close now"
RESCAN = 2.0    # seconds between looks for newly connected controllers

RUN = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/famidrive-{os.getuid()}")
PGID_FILE = RUN / "famidrive-game.pgid"
TREE_FILE = RUN / "famidrive-game.tree"
CLOSE_FILE = RUN / "famidrive-game.close"
COMBO = {e.BTN_SELECT, e.BTN_START}


def log(msg):
    print(f"famidrive-quit: {msg}", flush=True)


def is_gamepad(dev):
    # 2.4 GHz dongles often add keyboard and mouse interfaces next to the
    # pad (the 8BitDo one does). Only the interface with both buttons counts.
    keys = dev.capabilities().get(e.EV_KEY, [])
    return COMBO.issubset(keys)


def read_pid(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def tree(root):
    """root and every process under it, children before parents."""
    children = {}
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        children.setdefault(ppid, []).append(int(d.name))
    out, todo = [], [root]
    while todo:
        pid = todo.pop()
        out.append(pid)
        todo.extend(children.get(pid, []))
    return out[::-1]


def signal_all(targets, sig):
    """Send sig to each target; return whether any of them still exists."""
    alive = False
    for kind, n in targets:
        try:
            (os.killpg if kind == "group" else os.kill)(n, sig)
            alive = True
        except ProcessLookupError:
            pass
    return alive


def quit_game():
    try:
        close = CLOSE_FILE.read_text().strip()
    except OSError:
        close = ""
    if close:
        log(f"closing: {close}")
        subprocess.Popen(shlex.split(close), start_new_session=True)
        return

    targets = []
    pgid = read_pid(PGID_FILE)
    root = read_pid(TREE_FILE)
    # A Steam game first: its launcher script is what the pgid file points at.
    # The tree is listed once, now: if the root exits first, its children
    # are re-parented and could no longer be found under it.
    if root:
        targets += [("pid", pid) for pid in tree(root)]
    if pgid:
        targets.append(("group", pgid))
    if not targets:
        log("combo held, but no game is running")
        return
    log(f"quitting game (tree {root}, group {pgid})")
    if not signal_all(targets, signal.SIGTERM):
        return

    def force():
        deadline = time.monotonic() + GRACE
        while time.monotonic() < deadline:
            if not signal_all(targets, 0):
                return
            time.sleep(0.2)
        log(f"game ignored SIGTERM for {GRACE:.0f}s, killing it")
        signal_all(targets, signal.SIGKILL)

    threading.Thread(target=force, daemon=True).start()


def main():
    parent = os.getppid()
    devices = {}        # fd -> InputDevice
    held = {}           # fd -> set of combo buttons currently down
    since = {}          # fd -> when the full combo went down (None = fired or not held)
    last_scan = 0.0

    while True:
        # The session (gamescope-fg) is our parent; when it's gone, so are we.
        if os.getppid() != parent:
            return

        now = time.monotonic()
        if now - last_scan >= RESCAN:
            last_scan = now
            known = {d.path for d in devices.values()}
            for path in evdev.list_devices():
                if path in known:
                    continue
                try:
                    dev = evdev.InputDevice(path)
                except OSError:
                    continue
                if is_gamepad(dev):
                    devices[dev.fd] = dev
                    held[dev.fd] = set()
                    since[dev.fd] = None
                    log(f"watching {dev.name} ({path})")
                else:
                    dev.close()

        timeout = 0.1 if any(t is not None for t in since.values()) else RESCAN
        ready, _, _ = select.select(list(devices), [], [], timeout)
        for fd in ready:
            dev = devices[fd]
            try:
                for ev in dev.read():
                    if ev.type == e.EV_KEY and ev.code in COMBO:
                        if ev.value:
                            held[fd].add(ev.code)
                        else:
                            held[fd].discard(ev.code)
                            since[fd] = None
                        if held[fd] == COMBO and since[fd] is None:
                            since[fd] = time.monotonic()
            except OSError:
                # Unplugged, out of range or switched off.
                log(f"lost {dev.name}")
                del devices[fd], held[fd], since[fd]
                try:
                    dev.close()
                except OSError:
                    pass

        now = time.monotonic()
        for fd, t in since.items():
            if t is not None and now - t >= HOLD:
                since[fd] = None   # once per hold; let go to fire again
                held[fd] = set()
                quit_game()


if __name__ == "__main__":
    main()
