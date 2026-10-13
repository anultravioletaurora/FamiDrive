"""famidrive-quit: hold Select + Start on any controller to quit the game,
and press Guide for FamiDrive's menu.

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

Guide (the Xbox button, the PS button, the 8BitDo's heart: BTN_MODE
under the pad's own driver) opens FamiDrive's menu when it's let go. The
toast daemon draws the menu and keeps its state; this sends it the
presses (famidrive-toast's socket, one JSON line each way). While the
menu is open every pad is grabbed (EVIOCGRAB), so the game stops seeing
them: a press meant for the menu never also jumps or shoots. Before the
grab, whatever is held is let go and the sticks are centered for every
reader of the pad, the game too, so a character walking when Guide was
pressed doesn't keep walking under the menu. A grab only covers evdev:
a game that reads a pad's hidraw device itself (SDL's own drivers for
PlayStation and Switch pads, Steam Input) still sees it.

Runs for the life of the session: started by famidrive-session, and exits
when that goes away.
"""

import json
import os
import select
import shlex
import signal
import socket
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
MENU_FILE = RUN / "famidrive-game.menu"   # the game's guideMenu, from its launch
COMBO = {e.BTN_SELECT, e.BTN_START}
# SDL_GameControllerDB's gamecontrollerdb.txt (set by the package).
PADDB = os.environ.get("FAMIDRIVE_QUIT_PADDB", "@gamecontrollerdb@")
BTN_MISC, BTN_JOYSTICK, KEY_MAX = 0x100, 0x120, 0x2ff
# Event and code numbers from linux/input-event-codes.h, as numbers so the
# pure parts below need no evdev.
EV_KEY, EV_ABS = 0x01, 0x03
BTN_SOUTH, BTN_EAST, BTN_MODE = 0x130, 0x131, 0x13c
BTN_DPAD = {0x220: "up", 0x221: "down", 0x222: "left", 0x223: "right"}
ABS_X, ABS_Y, ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE = 0x00, 0x01, 0x02, 0x05, 0x09, 0x0a
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
HATS = range(0x10, 0x18)
TRIGGERS = (ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE)
# Steam Input's virtual pad. It's grabbed with the rest, but its presses
# are the real pad's again, so they don't move the menu twice.
STEAM_VIRTUAL = (0x28de, 0x11ff)
TOAST_SOCK = RUN / "famidrive-toast.sock"
HOLD_PRESS = 0.1    # seconds Esc is held for the game, a few of its frames
KEY_ESC = 1


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
    """(vendor, product) -> {platform: {role: button number}} from
    SDL_GameControllerDB (roles: back, start, guide, a, b), or
    name_key(name) -> the same for a pad with no USB ids. Only entries
    that give back and start as buttons."""
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
        roles = {r: int(m[r][1:]) for r in ("back", "start", "guide", "a", "b")
                 if m.get(r, "")[:1] == "b" and m[r][1:].isdigit()}
        if "back" not in roles or "start" not in roles:
            continue
        db.setdefault(key, {}).setdefault(m.get("platform", ""), roles)
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
        found = generic_roles(keys, vendor, product, db, name)
        if "back" in found and "start" in found:
            return {found["back"], found["start"]}
    # 2.4 GHz dongles often add keyboard and mouse interfaces next to the
    # pad (the 8BitDo one does). Only the interface with both buttons counts.
    return set(COMBO) if COMBO.issubset(keys) else None


def generic_roles(keys, vendor, product, db, name=""):
    """{role: key code} for a hid-generic pad, from the database. Its
    buttons are numbered: a Linux entry was made from the same numbering;
    a Windows one numbers the HID report's buttons, which is the order
    hid-generic gives them codes in."""
    found = db.get(name_key(name) if (vendor, product) == (0, 0) else (vendor, product), {})
    roles = found.get("Linux") or found.get("Windows") or {}
    order = sdl_buttons(keys)
    return {r: order[n] for r, n in roles.items() if n < len(order)}


def menu_buttons(keys, vendor, product, driver, db, name=""):
    """{"guide", "a", "b": key code} on this device, as far as it has them.
    A pad with a driver of its own names them; a hid-generic one is looked
    up like its Select and Start."""
    if driver == "hid-generic":
        found = generic_roles(keys, vendor, product, db, name)
        return {r: found[r] for r in ("guide", "a", "b") if r in found}
    named = {"guide": BTN_MODE, "a": BTN_SOUTH, "b": BTN_EAST}
    return {r: c for r, c in named.items() if c in keys}


class PadNav:
    """One pad's events as menu commands: up, down, left, right (d-pad,
    hat or left stick), select (A), back (B), close (Guide). A stick
    counts once per push: it has to come back near the middle before it
    moves the menu again."""

    PUSH, BACK = 0.6, 0.3

    def __init__(self, buttons, ranges):
        self.keys = {c: {"guide": "close", "a": "select", "b": "back"}[r] for r, c in buttons.items()}
        self.ranges = ranges      # {abs code: (min, max)}
        self.pushed = {}          # stick axis -> the direction it's held in

    def feed(self, etype, code, value):
        if etype == EV_KEY and value == 1:
            return self.keys.get(code) or BTN_DPAD.get(code)
        if etype != EV_ABS:
            return None
        if code in (ABS_HAT0X, ABS_HAT0Y):
            if value:
                return {(ABS_HAT0X, -1): "left", (ABS_HAT0X, 1): "right",
                        (ABS_HAT0Y, -1): "up", (ABS_HAT0Y, 1): "down"}[(code, 1 if value > 0 else -1)]
            return None
        if code in (ABS_X, ABS_Y) and code in self.ranges:
            lo, hi = self.ranges[code]
            x = (2 * (value - lo) / max(1, hi - lo)) - 1
            if abs(x) < self.BACK:
                self.pushed.pop(code, None)
            elif abs(x) > self.PUSH and code not in self.pushed:
                way = {(ABS_X, False): "left", (ABS_X, True): "right",
                       (ABS_Y, False): "up", (ABS_Y, True): "down"}[(code, x > 0)]
                self.pushed[code] = way
                return way
        return None


def at_rest(code, lo, hi, driver):
    """Where an axis sits untouched: a hat at 0, a trigger at its low end,
    a stick in the middle. A hid-generic pad's ABS_Z can be a stick, so
    only a pad with its own driver gets its triggers put at the low end."""
    if code in HATS:
        return 0
    if code in TRIGGERS and driver != "hid-generic" and lo >= 0:
        return lo
    return int((lo + hi) / 2)


def let_go(held, axes, driver):
    """The events that let go of every held button and put every axis at
    rest: [(type, code, value)]. axes: {code: (value, min, max)}."""
    out = [(EV_KEY, c, 0) for c in sorted(held)]
    for code, (value, lo, hi) in sorted(axes.items()):
        rest = at_rest(code, lo, hi, driver)
        if value != rest:
            out.append((EV_ABS, code, rest))
    return out


def ask_menu(command, path=None):
    """Hand the toast daemon a menu command; its reply ({"open": bool, and
    "do": "quit", or "resume" to press Esc to back out of the game's own
    pause menu}), or {} without one."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(path or TOAST_SOCK))
            s.sendall(json.dumps({"menu": command}).encode() + b"\n")
            s.shutdown(socket.SHUT_WR)
            buf = b""
            while chunk := s.recv(4096):
                buf += chunk
        return json.loads(buf.decode() or "{}")
    except (OSError, ValueError):
        return {}


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


def game_targets():
    """The running game's processes: [("pid", n) or ("group", n)]."""
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
    return targets


def parse_mode(text):
    """famidrive-game.menu's guideMenu: "freeze" or "pause" ("pause" when
    it says nothing else)."""
    words = (text or "").split()
    return words[0] if words and words[0] in ("freeze", "pause") else "pause"


def game_mode():
    """What the menu does with the running game: its guideMenu, or "none"
    with no game, or for Steam's Big Picture and the voice client, which
    leave a polite way to close them instead (famidrive-game.close) and
    aren't games."""
    try:
        if not game_targets() or CLOSE_FILE.read_text().strip():
            return "none"
    except OSError:
        pass
    try:
        return parse_mode(MENU_FILE.read_text())
    except OSError:
        return parse_mode("")


def freeze_game(on):
    """Stop the game (SIGSTOP) while the menu is open, and let it go on
    (SIGCONT) after: an emulator's pause. Found on the first box
    2026-10-13: Dolphin kept reading a DualShock 4 under the menu, through
    its hidraw device, which no grab covers; stopped, it reads nothing."""
    targets = game_targets()
    log(("freezing" if on else "thawing") + f" the game ({len(targets)} targets)")
    signal_all(targets, signal.SIGSTOP if on else signal.SIGCONT)


def make_keys():
    """A virtual keyboard with just Esc, made once, as the session starts,
    so gamescope has it before it's needed. None without /dev/uinput."""
    try:
        return evdev.UInput({EV_KEY: [KEY_ESC]}, name="FamiDrive keys")
    except Exception as err:   # no uinput access: PC games just aren't paused
        log(f"no virtual keyboard, so no pausing PC games: {err}")
        return None


def tap_esc(keys, wait=0.0, still=lambda: True):
    """Esc for a "pause" game (a PC one), on FamiDrive's own keyboard: as
    the menu opens, for the game's own pause menu, and as it closes, to
    back out of it. Esc is a PC game's pause and back key, whatever pad it
    uses (Cyberpunk 2077's pause is Select on a pad, but Esc too). Not a
    button pressed on the pad itself: the pad's next report of its own
    buttons undid it within a millisecond, before the game looked. Found
    on the first box 2026-10-13. Held a few of the game's frames; dropped
    once still() says it's no longer wanted (the menu opened again)."""
    def go():
        time.sleep(wait)
        if not keys or not still():
            return
        try:
            keys.write(EV_KEY, KEY_ESC, 1)
            keys.syn()
            time.sleep(HOLD_PRESS)
            keys.write(EV_KEY, KEY_ESC, 0)
            keys.syn()
            log("pressed Esc for the game")
        except OSError as err:
            log(f"couldn't press Esc: {err}")

    threading.Thread(target=go, daemon=True).start()


def quit_game():
    try:
        close = CLOSE_FILE.read_text().strip()
    except OSError:
        close = ""
    if close:
        log(f"closing: {close}")
        subprocess.Popen(shlex.split(close), start_new_session=True)
        return

    targets = game_targets()
    if not targets:
        log("combo held, but no game is running")
        return
    log(f"quitting game ({targets[0]}...)")
    if not signal_all(targets, signal.SIGTERM):
        return
    signal_all(targets, signal.SIGCONT)   # a frozen game can't act on SIGTERM

    def force():
        deadline = time.monotonic() + GRACE
        while time.monotonic() < deadline:
            if not signal_all(targets, 0):
                return
            time.sleep(0.2)
        log(f"game ignored SIGTERM for {GRACE:.0f}s, killing it")
        signal_all(targets, signal.SIGKILL)

    threading.Thread(target=force, daemon=True).start()


def grab(dev, driver):
    """Let go of everything held on dev, for every reader, then take it."""
    try:
        caps = dev.capabilities()
        axes = {}
        for code, info in caps.get(e.EV_ABS, []):
            axes[code] = (dev.absinfo(code).value, info.min, info.max)
        for etype, code, value in let_go(dev.active_keys(), axes, driver):
            dev.write(etype, code, value)
        dev.syn()
    except OSError as err:   # opened read-only: the grab still stops new presses
        log(f"couldn't let go of {dev.name}'s buttons: {err}")
    try:
        dev.grab()
    except OSError as err:
        log(f"couldn't grab {dev.name}: {err}")


def ungrab(dev):
    try:
        dev.ungrab()
    except OSError:
        pass


def main():
    parent = os.getppid()
    devices = {}        # fd -> InputDevice
    combos = {}         # fd -> its Select and Start key codes
    held = {}           # fd -> set of combo buttons currently down
    since = {}          # fd -> when the full combo went down (None = fired or not held)
    navs = {}           # fd -> PadNav, or None for a pad whose presses are another's
    drivers = {}        # fd -> its kernel driver
    guides = {}         # fd -> its Guide key code, if it has one
    frozen = False      # whether the menu stopped the game
    menu = False        # whether the menu is open, and every pad grabbed
    guide_down = set()  # fds whose Guide went down while the menu was closed
    last_scan = 0.0
    db = load_paddb(PADDB)
    keys = make_keys()

    def close_menu():
        nonlocal menu, frozen
        menu = False
        guide_down.clear()
        for dev in devices.values():
            ungrab(dev)
        if frozen:
            freeze_game(False)
            frozen = False

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
                keys = dev.capabilities().get(e.EV_KEY, [])
                driver = hid_driver(dev)
                combo = combo_for(keys, dev.info.vendor, dev.info.product, driver, db, dev.name)
                if combo:
                    fd = dev.fd
                    devices[fd] = dev
                    combos[fd] = combo
                    held[fd] = set()
                    since[fd] = None
                    drivers[fd] = driver
                    buttons = menu_buttons(keys, dev.info.vendor, dev.info.product, driver, db, dev.name)
                    guides[fd] = buttons.get("guide")
                    ranges = {c: (i.min, i.max) for c, i in dev.capabilities().get(e.EV_ABS, [])}
                    navs[fd] = None if (dev.info.vendor, dev.info.product) == STEAM_VIRTUAL else PadNav(buttons, ranges)
                    names = "+".join(str(e.BTN.get(c) or e.KEY.get(c) or c) for c in sorted(combo))
                    menu_on = "" if guides[fd] is None else ", menu on Guide"
                    log(f"watching {dev.name} ({path}), quitting on {names}{menu_on}")
                    if menu:
                        grab(dev, driver)
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
                    if menu:
                        command = navs[fd] and navs[fd].feed(ev.type, ev.code, ev.value)
                        if command:
                            reply = ask_menu(command)
                            if not reply.get("open"):
                                close_menu()
                                log("menu closed")
                                if reply.get("do") == "quit":
                                    quit_game()
                                elif reply.get("do") == "resume":
                                    tap_esc(keys, still=lambda: not menu)
                    elif ev.type == e.EV_KEY and ev.code == guides[fd] and ev.value == 1:
                        guide_down.add(fd)
                    elif ev.type == e.EV_KEY and ev.code == guides[fd] and ev.value == 0 and fd in guide_down:
                        # On letting go: the game has seen the press and
                        # the release, so Guide isn't left held down in it.
                        # Only a press that began with the menu closed: the
                        # Guide press that closed it lets go here too, and
                        # opened it again. Found on the first box
                        # 2026-10-12: Guide flickered the menu instead of
                        # closing it.
                        guide_down.discard(fd)
                        if ask_menu("open").get("open"):
                            menu = True
                            log("menu opened")
                            mode = game_mode()
                            if mode == "freeze":
                                freeze_game(True)
                                frozen = True
                            elif mode == "pause":
                                tap_esc(keys)
                            for fd2, dev2 in devices.items():
                                grab(dev2, drivers[fd2])
            except OSError:
                # Unplugged, out of range or switched off.
                log(f"lost {dev.name}")
                for table in (devices, combos, held, since, navs, drivers, guides):
                    del table[fd]
                try:
                    dev.close()
                except OSError:
                    pass

        now = time.monotonic()
        for fd, t in since.items():
            if t is not None and now - t >= HOLD:
                since[fd] = None   # once per hold; let go to fire again
                held[fd] = set()
                if menu:
                    ask_menu("close")
                    close_menu()
                quit_game()


if __name__ == "__main__":
    main()
