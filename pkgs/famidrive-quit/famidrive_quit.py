"""famidrive-quit: hold Select + Start on any controller to quit the game.

The same way out of every emulator, Steam game and the Media app, with no
per-emulator hotkey setup. gamescope-fg starts each game in its own process
group and writes that group's id to $XDG_RUNTIME_DIR/famidrive-game.pgid.
This watches every gamepad (read-only, never grabbed, so the game still
sees every press), and when Select + Start are held for HOLD seconds it
asks the game to close (SIGTERM), then force-closes it (SIGKILL) if it's
still there after GRACE seconds. ES-DE comes back when the game is gone.

Runs for the life of the session: started by famidrive-session, and exits
when that goes away.
"""

import os
import select
import signal
import threading
import time
from pathlib import Path

import evdev
from evdev import ecodes as e

HOLD = 1.0      # seconds both buttons must stay down
GRACE = 5.0     # seconds between "please close" and "close now"
RESCAN = 2.0    # seconds between looks for newly connected controllers

PGID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/famidrive-{os.getuid()}") / "famidrive-game.pgid"
COMBO = {e.BTN_SELECT, e.BTN_START}


def log(msg):
    print(f"famidrive-quit: {msg}", flush=True)


def is_gamepad(dev):
    # 2.4 GHz dongles often add keyboard and mouse interfaces next to the
    # pad (the 8BitDo one does). Only the interface with both buttons counts.
    keys = dev.capabilities().get(e.EV_KEY, [])
    return COMBO.issubset(keys)


def quit_game():
    try:
        pgid = int(PGID_FILE.read_text().strip())
    except (OSError, ValueError):
        log("combo held, but no game is running")
        return
    log(f"quitting game (process group {pgid})")
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return

    def force():
        deadline = time.monotonic() + GRACE
        while time.monotonic() < deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.2)
        log(f"game ignored SIGTERM for {GRACE:.0f}s, killing it")
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass

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
