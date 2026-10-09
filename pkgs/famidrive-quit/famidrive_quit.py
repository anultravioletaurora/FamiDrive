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

Which buttons are Select and Start: a pad with a kernel driver of its own
(xpad, hid-sony, hid-nintendo, ...) names them BTN_SELECT and BTN_START.
A pad the kernel only knows as a generic HID gamepad (hid-generic) gets
its buttons named in order instead, whatever they are. For those, SDL's
community controller database (SDL_GameControllerDB) says which numbered
buttons are back and start. Found on the second box 2026-10-08: on a
Razer Raiju Tournament Edition, "BTN_SELECT" and "BTN_START" were the
stick clicks, and Share + Options did nothing. A pad that gives no
USB ids (vendor and product 0, as a PowerA GameCube-style controller
for the Switch does over Bluetooth, named "Lic Pro Controller") is in
the database under its name instead, as SDL looks it up. Found on the
first box 2026-10-09: its - and + did nothing.

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
# SDL_GameControllerDB's gamecontrollerdb.txt (set by the package).
PADDB = os.environ.get("FAMIDRIVE_QUIT_PADDB", "@gamecontrollerdb@")
BTN_MISC, BTN_JOYSTICK, KEY_MAX = 0x100, 0x120, 0x2ff


def log(msg):
    print(f"famidrive-quit: {msg}", flush=True)


def le16(hexstr):
    """A GUID's little-endian 16-bit field, as a number."""
    return int(hexstr[2:4] + hexstr[0:2], 16)


def name_key(name):
    """How SDL 2 puts a pad without USB ids in its GUID: the name's first
    11 bytes and a NUL, where the ids would go."""
    return ("name", (name.encode()[:11] + b"\0").ljust(12, b"\0").hex())


def load_paddb(path):
    """(vendor, product) -> {platform: (back, start)} button numbers, from
    SDL_GameControllerDB, or name_key(name) -> the same for a pad with no
    USB ids. Only entries that give both as buttons."""
    db = {}
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return db
    for line in lines:
        fields = line.strip().split(",")
        if len(fields) < 3 or line.startswith("#") or len(fields[0]) != 32:
            continue
        guid = fields[0].lower()
        if guid[12:16] == "0000" and guid[20:24] == "0000":
            try:
                key = (le16(guid[8:12]), le16(guid[16:20]))
            except ValueError:
                continue
        else:
            key = ("name", guid[8:32])   # no USB ids: the name, as name_key makes it
        m = dict(f.split(":", 1) for f in fields[2:] if ":" in f)
        back, start = m.get("back", ""), m.get("start", "")
        if not (back[:1] == "b" and back[1:].isdigit() and start[:1] == "b" and start[1:].isdigit()):
            continue
        db.setdefault(key, {}).setdefault(m.get("platform", ""), (int(back[1:]), int(start[1:])))
    return db


def sdl_buttons(keys):
    """A device's key codes in the order SDL numbers its buttons on Linux:
    from BTN_JOYSTICK up, then the ones below it from BTN_MISC."""
    keys = sorted(set(keys))
    return [k for k in keys if BTN_JOYSTICK <= k <= KEY_MAX] + [k for k in keys if BTN_MISC <= k < BTN_JOYSTICK]


def combo_for(keys, vendor, product, driver, db, name=""):
    """The two key codes that are Select and Start on this device, or None
    if it has no such pair (not a pad, or a dongle's keyboard side)."""
    if driver == "hid-generic":
        # Numbered buttons. A Linux entry was made from the same numbering;
        # a Windows one numbers the HID report's buttons, which is the
        # order hid-generic gives them codes in.
        found = db.get(name_key(name) if (vendor, product) == (0, 0) else (vendor, product), {})
        pair = found.get("Linux") or found.get("Windows")
        order = sdl_buttons(keys)
        if pair and max(pair) < len(order):
            return {order[pair[0]], order[pair[1]]}
    # 2.4 GHz dongles often add keyboard and mouse interfaces next to the
    # pad (the 8BitDo one does). Only the interface with both buttons counts.
    return set(COMBO) if COMBO.issubset(keys) else None


def hid_driver(dev):
    """The kernel driver behind an input device (hid-generic, xpad, ...)."""
    try:
        return Path(f"/sys/class/input/{Path(dev.path).name}/device/device/driver").resolve().name
    except OSError:
        return None


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
    combos = {}         # fd -> its Select and Start key codes
    held = {}           # fd -> set of combo buttons currently down
    since = {}          # fd -> when the full combo went down (None = fired or not held)
    last_scan = 0.0
    db = load_paddb(PADDB)

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
                combo = combo_for(dev.capabilities().get(e.EV_KEY, []), dev.info.vendor,
                                  dev.info.product, hid_driver(dev), db, dev.name)
                if combo:
                    devices[dev.fd] = dev
                    combos[dev.fd] = combo
                    held[dev.fd] = set()
                    since[dev.fd] = None
                    names = "+".join(str(e.BTN.get(c) or e.KEY.get(c) or c) for c in sorted(combo))
                    log(f"watching {dev.name} ({path}), quitting on {names}")
                else:
                    dev.close()

        timeout = 0.1 if any(t is not None for t in since.values()) else RESCAN
        ready, _, _ = select.select(list(devices), [], [], timeout)
        for fd in ready:
            dev = devices[fd]
            try:
                for ev in dev.read():
                    if ev.type == e.EV_KEY and ev.code in combos[fd]:
                        if ev.value:
                            held[fd].add(ev.code)
                        else:
                            held[fd].discard(ev.code)
                            since[fd] = None
                        if held[fd] == combos[fd] and since[fd] is None:
                            since[fd] = time.monotonic()
            except OSError:
                # Unplugged, out of range or switched off.
                log(f"lost {dev.name}")
                del devices[fd], combos[fd], held[fd], since[fd]
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
