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

A Bluetooth pad left idle for FAMIDRIVE_IDLE_MINUTES (the player's
controllerIdleMinutes; unset or empty: never) is disconnected, which
switches it off, after a toast a minute before that says so: pressing
anything keeps it. Only Bluetooth: a 2.4 GHz dongle's or a USB pad can't
be switched off from here, and keeps its own sleep timer. Idle means no
button and no real stick movement: a held pad reports its sticks' jitter
all the time.

Runs for the life of the session: started by famidrive-session, and exits
when that goes away.
"""

import json
import os
import re
import select
import shlex
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, TypedDict

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
BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 0x136, 0x137, 0x138, 0x139
# SDL_GameControllerDB's names for the shoulders and triggers, and the
# menu's.
SHOULDERS = {"leftshoulder": "lb", "rightshoulder": "rb", "lefttrigger": "lt", "righttrigger": "rt"}
BTN_DPAD = {0x220: "up", 0x221: "down", 0x222: "left", 0x223: "right"}
ABS_X, ABS_Y, ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE = 0x00, 0x01, 0x02, 0x05, 0x09, 0x0a
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
HATS = range(0x10, 0x18)
TRIGGERS = (ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE)
# Steam Input's virtual pad. It's grabbed with the rest, but its presses
# are the real pad's again, so they don't move the menu twice.
STEAM_VIRTUAL = (0x28de, 0x11ff)
TOAST_SOCK = RUN / "famidrive-toast.sock"
BLUETOOTH = os.environ.get("FAMIDRIVE_QUIT_BLUETOOTH", "@famidrivebluetooth@")
BUS_BLUETOOTH = 0x05
WARN_BEFORE = 60.0  # seconds: the "going to sleep" toast, before an idle pad is let go

# A pad in SDL_GameControllerDB: its (vendor, product), or name_key(name)
# for one with no USB ids; and each platform's {role: button number} for it.
type PadKey = tuple[int, int] | tuple[str, str]
type PadDb = dict[PadKey, dict[str, dict[str, int]]]
# An axis' (min, max), by its code.
type Ranges = dict[int, tuple[int, int]]
# An input event: (type, code, value).
type Event = tuple[int, int, int]
type Target = tuple[Literal["pid", "group"], int]


class MenuReply(TypedDict, total=False):
    """The toast daemon's answer to a menu command."""
    open: bool
    do: str


def log(msg: str) -> None:
    print(f"famidrive-quit: {msg}", flush=True)


def le16(hexstr: str) -> int:
    """A GUID's little-endian 16-bit field, as a number."""
    return int(hexstr[2:4] + hexstr[0:2], 16)


def name_key(name: str) -> tuple[str, str]:
    """How SDL 2 puts a pad without USB ids in its GUID: the name's first
    11 bytes and a NUL, where the ids would go."""
    return ("name", (name.encode()[:11] + b"\0").ljust(12, b"\0").hex())


def load_paddb(path: str) -> PadDb:
    """(vendor, product) -> {platform: {role: button number}} from
    SDL_GameControllerDB (roles: back, start, guide, a, b, and the
    shoulders and triggers when they're buttons), or
    name_key(name) -> the same for a pad with no USB ids. Only entries
    that give back and start as buttons."""
    db: PadDb = {}
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return db
    for line in lines:
        fields = line.strip().split(",")
        if len(fields) < 3 or line.startswith("#") or len(fields[0]) != 32:
            continue
        guid = fields[0].lower()
        key: PadKey
        if guid[12:16] == "0000" and guid[20:24] == "0000":
            try:
                key = (le16(guid[8:12]), le16(guid[16:20]))
            except ValueError:
                continue
        else:
            key = ("name", guid[8:32])   # no USB ids: the name, as name_key makes it
        m = {k: v for k, _, v in (f.partition(":") for f in fields[2:] if ":" in f)}
        roles = {r: int(m[r][1:]) for r in ("back", "start", "guide", "a", "b", *SHOULDERS)
                 if m.get(r, "")[:1] == "b" and m[r][1:].isdigit()}
        if "back" not in roles or "start" not in roles:
            continue
        db.setdefault(key, {}).setdefault(m.get("platform", ""), roles)
    return db


def sdl_buttons(codes: Iterable[int]) -> list[int]:
    """A device's key codes in the order SDL numbers its buttons on Linux:
    from BTN_JOYSTICK up, then the ones below it from BTN_MISC."""
    keys = sorted(set(codes))
    return [k for k in keys if BTN_JOYSTICK <= k <= KEY_MAX] + [k for k in keys if BTN_MISC <= k < BTN_JOYSTICK]


def combo_for(keys: list[int], vendor: int, product: int, driver: str | None, db: PadDb,
              name: str = "") -> set[int] | None:
    """The two key codes that are Select and Start on this device, or None
    if it has no such pair (not a pad, or a dongle's keyboard side)."""
    if driver == "hid-generic":
        found = generic_roles(keys, vendor, product, db, name)
        if "back" in found and "start" in found:
            return {found["back"], found["start"]}
    # 2.4 GHz dongles often add keyboard and mouse interfaces next to the
    # pad (the 8BitDo one does). Only the interface with both buttons counts.
    return set(COMBO) if COMBO.issubset(keys) else None


def generic_roles(keys: list[int], vendor: int, product: int, db: PadDb, name: str = "") -> dict[str, int]:
    """{role: key code} for a hid-generic pad, from the database. Its
    buttons are numbered: a Linux entry was made from the same numbering;
    a Windows one numbers the HID report's buttons, which is the order
    hid-generic gives them codes in."""
    key: PadKey = name_key(name) if (vendor, product) == (0, 0) else (vendor, product)
    found = db.get(key, {})
    roles = found.get("Linux") or found.get("Windows") or {}
    order = sdl_buttons(keys)
    return {r: order[n] for r, n in roles.items() if n < len(order)}


def menu_buttons(keys: list[int], vendor: int, product: int, driver: str | None, db: PadDb,
                 name: str = "") -> dict[str, int]:
    """{"guide", "a", "b", "lb", "rb", "lt", "rt": key code} on this
    device, as far as it has them. A pad with a driver of its own names
    them; a hid-generic one is looked up like its Select and Start. The
    shoulders and triggers are for a manual in the menu (zoom, first and
    last page)."""
    if driver == "hid-generic":
        found = generic_roles(keys, vendor, product, db, name)
        return {r: found[s] for s, r in {"guide": "guide", "a": "a", "b": "b", **SHOULDERS}.items() if s in found}
    named = {"guide": BTN_MODE, "a": BTN_SOUTH, "b": BTN_EAST,
             "lb": BTN_TL, "rb": BTN_TR, "lt": BTN_TL2, "rt": BTN_TR2}
    return {r: c for r, c in named.items() if c in keys}


class PadNav:
    """One pad's events as menu commands: up, down, left, right (d-pad,
    hat or left stick), select (A), back (B), close (Guide), and lb, rb,
    lt, rt (the shoulders and triggers). A stick counts once per push: it
    has to come back near the middle before it moves the menu again. So
    does an analog trigger, read only on a pad with a driver of its own
    (analog_triggers): a hid-generic pad's ABS_Z can be a stick."""

    PUSH, BACK = 0.6, 0.3

    def __init__(self, buttons: dict[str, int], ranges: Ranges, analog_triggers: bool = False) -> None:
        self.keys = {c: {"guide": "close", "a": "select", "b": "back"}.get(r, r) for r, c in buttons.items()}
        self.ranges = ranges      # {abs code: (min, max)}
        self.pushed: dict[int, str] = {}   # stick axis -> the direction it's held in
        self.triggers = {ABS_Z: "lt", ABS_RZ: "rt"} if analog_triggers else {}

    def feed(self, etype: int, code: int, value: int) -> str | None:
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
        if code in self.triggers and code in self.ranges:
            lo, hi = self.ranges[code]
            x = (value - lo) / max(1, hi - lo)
            if x < self.BACK:
                self.pushed.pop(code, None)
            elif x > self.PUSH and code not in self.pushed:
                self.pushed[code] = self.triggers[code]
                return self.triggers[code]
        return None


def at_rest(code: int, lo: int, hi: int, driver: str | None) -> int:
    """Where an axis sits untouched: a hat at 0, a trigger at its low end,
    a stick in the middle. A hid-generic pad's ABS_Z can be a stick, so
    only a pad with its own driver gets its triggers put at the low end."""
    if code in HATS:
        return 0
    if code in TRIGGERS and driver != "hid-generic" and lo >= 0:
        return lo
    return int((lo + hi) / 2)


def let_go(held: Iterable[int], axes: dict[int, tuple[int, int, int]], driver: str | None) -> list[Event]:
    """The events that let go of every held button and put every axis at
    rest: [(type, code, value)]. axes: {code: (value, min, max)}."""
    out = [(EV_KEY, c, 0) for c in sorted(held)]
    for code, (value, lo, hi) in sorted(axes.items()):
        rest = at_rest(code, lo, hi, driver)
        if value != rest:
            out.append((EV_ABS, code, rest))
    return out


class Activity:
    """Whether a pad's events are someone using it. Every button counts,
    and a hat; a stick or trigger only when it has moved a real distance
    since it last counted. Found on the first box 2026-10-13: a held
    8BitDo Ultimate 2 reported its sticks' jitter many times a second."""

    MOVE = 0.15   # of the axis's range

    def __init__(self, ranges: Ranges) -> None:
        self.ranges = ranges           # {abs code: (min, max)}
        self.at: dict[int, int] = {}   # abs code -> where it was when it last counted

    def feed(self, etype: int, code: int, value: int) -> bool:
        if etype == EV_KEY:
            return True
        if etype != EV_ABS or code not in self.ranges:
            return False
        if code in HATS:
            return value != 0
        lo, hi = self.ranges[code]
        last = self.at.setdefault(code, at_rest(code, lo, hi, ""))
        if abs(value - last) >= self.MOVE * max(1, hi - lo):
            self.at[code] = value
            return True
        return False


def idle_minutes(text: str | None) -> float | None:
    """FAMIDRIVE_IDLE_MINUTES as seconds, or None for never."""
    try:
        minutes = float(text or "")
    except (TypeError, ValueError):
        return None
    return minutes * 60 if minutes > 0 else None


def idle_step(idle: float, timeout: float | None, warned: bool) -> str | None:
    """What to do about a pad idle for `idle` seconds: "warn", "off" or
    None. timeout None: never."""
    if timeout is None:
        return None
    if idle >= timeout:
        return "off"
    if idle >= timeout - WARN_BEFORE and not warned:
        return "warn"
    return None


def bluetooth_address(dev: "evdev.InputDevice") -> str | None:
    """A Bluetooth pad's address (its evdev "uniq"), or None."""
    uniq = (dev.uniq or "").strip()
    if dev.info.bustype == BUS_BLUETOOTH and re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", uniq):
        return uniq
    return None


def send_toast(toast: dict[str, str], path: Path | None = None) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(path or TOAST_SOCK))
            s.sendall(json.dumps(toast).encode() + b"\n")
    except OSError:
        pass


def ask_menu(command: str, path: Path | None = None) -> MenuReply:
    """Hand the toast daemon a menu command; its reply ({"open": bool, and
    "do": "quit" when the player picked Quit game}), or {} without one."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(path or TOAST_SOCK))
            s.sendall(json.dumps({"menu": command}).encode() + b"\n")
            s.shutdown(socket.SHUT_WR)
            buf = b""
            while chunk := s.recv(4096):
                buf += chunk
        reply: MenuReply = json.loads(buf.decode() or "{}")
        return reply
    except (OSError, ValueError):
        return {}


def hid_driver(dev: "evdev.InputDevice") -> str | None:
    """The kernel driver behind an input device (hid-generic, xpad, ...)."""
    try:
        return Path(f"/sys/class/input/{Path(dev.path).name}/device/device/driver").resolve().name
    except OSError:
        return None


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def tree(root: int) -> list[int]:
    """root and every process under it, children before parents."""
    children: dict[int, list[int]] = {}
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


def signal_all(targets: list[Target], sig: int) -> bool:
    """Send sig to each target; return whether any of them still exists."""
    alive = False
    for kind, n in targets:
        try:
            (os.killpg if kind == "group" else os.kill)(n, sig)
            alive = True
        except ProcessLookupError:
            pass
    return alive


def game_targets() -> list[Target]:
    """The running game's processes: [("pid", n) or ("group", n)]."""
    targets: list[Target] = []
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


def parse_mode(text: str | None) -> str:
    """famidrive-game.menu's guideMenu: "freeze" or "block" ("block" when
    it says nothing else: never freeze a game that may be online)."""
    words = (text or "").split()
    return words[0] if words and words[0] in ("freeze", "block") else "block"


def game_mode() -> str:
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


def freeze_game(on: bool) -> None:
    """Stop the game (SIGSTOP) while the menu is open, and let it go on
    (SIGCONT) after: a "freeze" game's pause (an emulator, an offline PC
    game). Whatever the game had open, its own pause menu included, stays
    as it was: FamiDrive can't see a game's menus, and pressing its pause
    key (tried first, on the first box 2026-10-13) closed one already open.
    Stopped, it reads no pad either: Dolphin had kept reading a DualShock 4
    under the menu, through its hidraw device, which no grab covers."""
    targets = game_targets()
    log(("freezing" if on else "thawing") + f" the game ({len(targets)} targets)")
    signal_all(targets, signal.SIGSTOP if on else signal.SIGCONT)


def quit_game() -> None:
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

    def force() -> None:
        deadline = time.monotonic() + GRACE
        while time.monotonic() < deadline:
            if not signal_all(targets, 0):
                return
            time.sleep(0.2)
        log(f"game ignored SIGTERM for {GRACE:.0f}s, killing it")
        signal_all(targets, signal.SIGKILL)

    threading.Thread(target=force, daemon=True).start()


def grab(dev: "evdev.InputDevice", driver: str | None) -> None:
    """Let go of everything held on dev, for every reader, then take it."""
    try:
        caps = dev.capabilities()
        axes: dict[int, tuple[int, int, int]] = {}
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


def ungrab(dev: "evdev.InputDevice") -> None:
    try:
        dev.ungrab()
    except OSError:
        pass


def main() -> None:
    parent = os.getppid()
    devices: dict[int, evdev.InputDevice] = {}   # fd -> InputDevice
    combos: dict[int, set[int]] = {}             # fd -> its Select and Start key codes
    held: dict[int, set[int]] = {}               # fd -> set of combo buttons currently down
    since: dict[int, float | None] = {}          # fd -> when the full combo went down (None = fired or not held)
    navs: dict[int, PadNav | None] = {}          # fd -> PadNav, or None for a pad whose presses are another's
    drivers: dict[int, str | None] = {}          # fd -> its kernel driver
    guides: dict[int, int | None] = {}           # fd -> its Guide key code, if it has one
    frozen = False                               # whether the menu stopped the game
    menu = False                                 # whether the menu is open, and every pad grabbed
    guide_down: set[int] = set()                 # fds whose Guide went down while the menu was closed
    activity: dict[int, Activity] = {}           # fd -> Activity
    used: dict[int, float] = {}                  # fd -> when someone last used it
    warned: dict[int, bool] = {}                 # fd -> whether the "going to sleep" toast is out
    addresses: dict[int, str | None] = {}        # fd -> its Bluetooth address, for a Bluetooth pad
    idle_after = idle_minutes(os.environ.get("FAMIDRIVE_IDLE_MINUTES"))
    last_scan = 0.0
    db = load_paddb(PADDB)

    def close_menu() -> None:
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
                    navs[fd] = None if (dev.info.vendor, dev.info.product) == STEAM_VIRTUAL else PadNav(buttons, ranges, driver != "hid-generic")
                    activity[fd], used[fd], warned[fd] = Activity(ranges), now, False
                    addresses[fd] = bluetooth_address(dev)
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
                    if activity[fd].feed(ev.type, ev.code, ev.value):
                        used[fd], warned[fd] = time.monotonic(), False
                    if ev.type == e.EV_KEY and ev.code in combos[fd]:
                        if ev.value:
                            held[fd].add(ev.code)
                        else:
                            held[fd].discard(ev.code)
                            since[fd] = None
                        if held[fd] == combos[fd] and since[fd] is None:
                            since[fd] = time.monotonic()
                    if menu:
                        nav = navs[fd]
                        command = nav.feed(ev.type, ev.code, ev.value) if nav else None
                        if command:
                            reply = ask_menu(command)
                            if not reply.get("open"):
                                close_menu()
                                log("menu closed")
                                if reply.get("do") == "quit":
                                    quit_game()
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
                            for fd2, dev2 in devices.items():
                                grab(dev2, drivers[fd2])
            except OSError:
                # Unplugged, out of range or switched off.
                log(f"lost {dev.name}")
                for table in (devices, combos, held, since, navs, drivers, guides, activity, used, warned, addresses):
                    del table[fd]
                try:
                    dev.close()
                except OSError:
                    pass

        now = time.monotonic()
        for fd, address in addresses.items():
            if address is None or idle_after is None:
                continue
            step = idle_step(now - used[fd], idle_after, warned[fd])
            if step == "warn":
                warned[fd] = True
                send_toast({"kind": "alert", "icon": "controller", "id": f"idle-{address}",
                            "title": "Controller going to sleep", "detail": "Press any button to keep it on"})
            elif step == "off":
                used[fd] = now   # once; it goes away when it's off
                log(f"{devices[fd].name} idle for {idle_after / 60:g} min, switching it off")
                subprocess.Popen([BLUETOOTH, "disconnect", address], start_new_session=True)

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
