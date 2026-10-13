"""famidrive-toast: small notices over whatever's on the TV.

    famidrive-toast daemon SPEC.json PLAYER
    famidrive-toast [--kind notice|alert|progress|achievement] [--id ID]
                    [--progress 0..1] [--done] [--icon NAME|IMAGE] [--seconds N]
                    TITLE [DETAIL]

Every toast has an icon, left of the text: --icon names a drawn one (save,
warning, trophy, download, info) or gives an image, such as a game's logo
for an achievement. Without one, each kind has its own: info for a notice,
warning for an alert, download for progress, trophy for an achievement.

The daemon runs once per player session, before ES-DE. It draws into a
transparent window on gamescope's Steam overlay layer (STEAM_OVERLAY),
which gamescope composites over everything, so a toast shows over the
menu, a game or Kodi without ever taking focus or input. Not the external
overlay layer: gamescope shows one external overlay at a time, and that
one is MangoHud's (mangoapp). Found on the first box 2026-10-07: with the
toast window there, MangoHud didn't show at all.

Anything in the session sends one by running famidrive-toast, which hands
the toast to the daemon over $XDG_RUNTIME_DIR/famidrive-toast.sock and
returns at once. Without a daemon (an SSH login, a box with no TV session)
it says so on stderr and still exits 0: a toast is never worth failing
the caller for.

Toasts show one at a time, in order. A progress toast with an --id is
updated in place by the next one with the same id, and closes after
--done. They're drawn in the player's ES-DE theme: its fonts (theme.xml's
fontRegular and fontLight, like the status screen) and the colors of the
color scheme the player picked in ES-DE (colors.xml's statusBackgroundColor,
statusColor, helpTextColor), with ES-DE's dark look where a theme has none.

SPEC (JSON, from Nix): {"theme": theme folder or null, "recordings": bool, "players":
{user: {"position": "bottom-right", "hide": [kinds]}}, "default": {...}}.
"""

import json
import os
import re
import socket
import sys
import time
from pathlib import Path

KINDS = ("notice", "alert", "progress", "achievement", "success")
POSITIONS = ("top-left", "top-center", "top-right", "middle-left", "middle-right",
             "bottom-left", "bottom-center", "bottom-right")
# Every toast has an icon: --icon names one of these (drawn here, in the
# theme's text color), or gives an image (a game's logo). Without one, or
# when the image can't be read, the kind's own. A success is always the
# checkmark.
ICONS = ("save", "warning", "trophy", "download", "info", "controller", "check", "music", "record")
KIND_ICON = {"notice": "info", "alert": "warning", "progress": "download", "achievement": "trophy",
             "success": "check"}
ALERT = (230, 160, 40, 255)
SUCCESS = (76, 187, 106, 255)
GOLD = (232, 184, 64, 255)
SECONDS = {"notice": 4.0, "alert": 7.0, "achievement": 6.0, "progress": 2.0, "success": 5.0}
STALE_PROGRESS = 120.0
DIM = (0, 0, 0, 165)   # over the game while the menu is up
BLUR_RADIUS = 18       # gamescope's blur of the game behind the menu (its most is 19)
BLUR_FADE_MS = 200
# The panel slides in from the right over this long, easing out: quick
# at first, settling gently, no bounce (a spring's overshoot was more
# than wanted, first box 2026-10-13).
SLIDE_SECONDS = 0.28
SWAP_SECONDS = 0.22    # the buttons sliding over to the quit question and back
COUNTDOWN = 3          # seconds counted down before a recording starts
RECORD_ITEMS = {"Start recording": "Record", "Stop recording": "Stop"}   # the menu item, and its button's label
RED = (226, 60, 60, 255)   # the record button's dot, and the one beside Stop while recording

MAX_SHOWN = 3          # toasts on screen at once, stacked from the corner
URGENT = ("alert", "achievement")   # a progress toast nobody updates is let go
FADE = 0.25

# ES-DE's own dark look, for a theme that names no colors.
DEFAULT_COLORS = {
    "panel": (17, 17, 17, 238),
    "text": (255, 255, 255, 255),
    "dim": (153, 153, 153, 255),
}


# Where the box's own services (the library pull, which runs as its own
# account, outside any session) reach whoever is on the TV: each session's
# daemon also listens here, group famidrive (overlays.nix makes the folder).
SHARED = Path("/run/famidrive-toast")


def sock_path():
    """This session's socket: in its runtime folder, or for an account
    without one (the greeter, which runs "Who's playing?"), in /tmp."""
    run = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not os.path.isdir(run):
        return Path("/tmp") / f"famidrive-toast-{os.getuid()}.sock"
    return Path(run) / "famidrive-toast.sock"


def read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


# --- The player's theme ---------------------------------------------------

def opaque(color):
    """A theme's panel color half again as opaque: a see-through theme
    color (Art Book Next's) let a busy game show through the text. Found
    on the first box 2026-10-12."""
    return (*color[:3], min(255, int(color[3] * 1.5)))


def ease_out(p):
    """How far along a slide is (0..1) at fraction p of its time: a cubic
    ease-out."""
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def hex_color(value):
    """ES-DE's RRGGBB or RRGGBBAA, as an RGBA tuple; None if it isn't one."""
    v = (value or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", v):
        return None
    if len(v) == 6:
        v += "ff"
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4, 6))


def color_scheme(home):
    """The color scheme the player picked in ES-DE, or None."""
    m = re.search(r'<string name="ThemeColorScheme" value="([^"]*)"',
                  read(Path(home) / "ES-DE/settings/es_settings.xml"))
    return m.group(1) if m else None


def theme_colors(theme, scheme):
    """Panel, text and dim colors from the theme's colors.xml, for the
    picked scheme (or the file's first), falling back to ES-DE's dark look.
    A scheme can be named in several blocks (Art Book Next has one for
    its colors and another for its art variants); later ones add to and
    override earlier ones, as in ES-DE."""
    colors = dict(DEFAULT_COLORS)
    if not theme:
        return colors
    text = read(Path(theme) / "colors.xml")
    blocks = re.findall(r'<colorScheme name="([^"]*)">(.*?)</colorScheme>', text, re.S)
    chosen = [body for names, body in blocks
              if scheme and scheme in [n.strip() for n in names.split(",")]]
    if not chosen and blocks:
        chosen = [blocks[0][1]]
    found = {}
    for body in chosen:
        found.update(re.findall(r"<(\w+)>([^<]*)</\1>", body))
    for key, var in (("panel", "statusBackgroundColor"), ("text", "statusColor"),
                     ("dim", "helpTextColor")):
        c = hex_color(found.get(var))
        if c:
            colors[key] = c
    return colors


def theme_fonts(theme):
    """(regular, light) font files the theme uses for names and for
    descriptions; None where it names none (ES-DE's default font then)."""
    if not theme:
        return None, None
    names = dict(re.findall(r"<(font\w+)>([^<]+)</font\w+>", read(Path(theme) / "theme.xml")))
    regular = names.get("fontRegular")
    light = names.get("fontLight", regular)
    return (Path(theme) / regular if regular else None), (Path(theme) / light if light else None)


def player_spec(spec, player):
    s = dict(spec.get("default") or {})
    s.update((spec.get("players") or {}).get(player) or {})
    if s.get("position") not in POSITIONS:
        s["position"] = "bottom-right"
    s["hide"] = [k for k in s.get("hide") or [] if k in KINDS]
    return s


# --- Where a toast goes -----------------------------------------------------

def place(position, screen, size, margin):
    """Top-left corner for a toast of `size` at `position` on `screen`.
    The bottom margin is larger: ES-DE themes keep their help bar there."""
    (sw, sh), (w, h) = screen, size
    vert, horiz = position.split("-")
    x = {"left": margin, "center": (sw - w) // 2, "right": sw - w - margin}[horiz]
    y = {"top": margin, "middle": (sh - h) // 2, "bottom": sh - h - int(margin * 2.2)}[vert]
    return x, y


def layout(position, screen, sizes, margin, gap):
    """Top-left corners for a stack of toasts (`sizes`, oldest first): the
    oldest at `position`, the rest stacked away from the screen's edge,
    upward from the bottom, downward from the top or middle."""
    if not sizes:
        return []
    up = position.startswith("bottom")
    x0, y = place(position, screen, sizes[0], margin)
    out = [(x0, y)]
    for prev, size in zip(sizes, sizes[1:]):
        x, _ = place(position, screen, size, margin)
        y = y - size[1] - gap if up else y + prev[1] + gap
        out.append((x, y))
    return out


def icon_name(toast):
    """One of ICONS, or an image's path. A progress toast turned into a
    success in place keeps the icon it was sent with, so a success's is
    decided here, not taken from it."""
    kind = toast.get("kind", "notice")
    if kind == "success":
        return "check"
    return toast.get("icon") or KIND_ICON.get(kind, "info")


# --- The queue ----------------------------------------------------------------


class Queue:
    """Toasts waiting and showing, up to `slots` at once (a stack in the
    corner), oldest first. Pure: the clock is passed in.

    A toast with an id is updated in place, showing or waiting. Alerts and
    achievements go ahead of waiting notices, so a controller going flat
    or an unlock isn't stuck behind a burst of "Saved" toasts. A progress
    toast keeps showing until it's done, and the others come and go around
    it (one at a time, before: a long library pull held every other toast
    back until it finished)."""

    def __init__(self, hide=(), slots=MAX_SHOWN):
        self.hide = set(hide)
        self.slots = slots
        self.waiting = []
        self.showing = []   # {"toast", "shown_at", "ends_at"}, oldest first

    def add(self, toast, now):
        kind = toast.get("kind", "notice")
        if kind not in KINDS:
            kind = toast["kind"] = "notice"
        if kind in self.hide:
            return False
        toast["updated"] = now
        tid = toast.get("id")
        if tid:
            for shown in self.showing:
                if shown["toast"].get("id") == tid:
                    shown["toast"].update(toast)
                    # An unfinished progress toast stays; anything else (done,
                    # or turned into a success or alert) gets its own time.
                    shown["ends_at"] = self._end(shown["toast"], now)
                    return True
            for i, t in enumerate(self.waiting):
                if t.get("id") == tid:
                    self.waiting[i] = toast
                    return True
        if kind in URGENT:
            at = next((i for i, t in enumerate(self.waiting) if t["kind"] not in URGENT), len(self.waiting))
            self.waiting.insert(at, toast)
        else:
            self.waiting.append(toast)
        return True

    def _end(self, toast, now):
        if toast.get("kind") == "progress" and not toast.get("done"):
            return None   # until it's done
        return now + float(toast.get("seconds") or SECONDS[toast["kind"]])

    def tick(self, now):
        """Advance; returns [(toast, its age, seconds left or None)], oldest first."""
        def gone(shown):
            if shown["ends_at"] is None:
                return now - shown["toast"]["updated"] > STALE_PROGRESS
            return now >= shown["ends_at"]
        self.showing = [x for x in self.showing if not gone(x)]
        while self.waiting and len(self.showing) < self.slots:
            t = self.waiting.pop(0)
            self.showing.append({"toast": t, "shown_at": now, "ends_at": self._end(t, now)})
        return [(x["toast"], now - x["shown_at"], None if x["ends_at"] is None else x["ends_at"] - now)
                for x in self.showing]


# --- Sending --------------------------------------------------------------

def parse_send(argv):
    toast, words = {"kind": "notice"}, []
    it = iter(argv)
    for a in it:
        if a == "--kind":
            toast["kind"] = next(it, "notice")
        elif a == "--id":
            toast["id"] = next(it, "")
        elif a == "--progress":
            toast["progress"] = max(0.0, min(1.0, float(next(it, "0"))))
        elif a == "--icon":
            toast["icon"] = next(it, "")
        elif a == "--seconds":
            toast["seconds"] = float(next(it, "4"))
        elif a == "--done":
            toast["done"] = True
        else:
            words.append(a)
    if not words:
        raise SystemExit("usage: famidrive-toast [--kind K] [--id ID] [--progress F] [--done] [--icon NAME|IMAGE] TITLE [DETAIL]")
    toast["title"] = words[0]
    if len(words) > 1:
        toast["detail"] = " ".join(words[1:])
    return toast


def send_to(path, toast):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect(str(path))
        s.sendall(json.dumps(toast).encode() + b"\n")


def send(toast):
    """To this session's daemon; from outside a session (a system service),
    to every player's session on the TV through the shared folder."""
    try:
        send_to(sock_path(), toast)
        return
    except OSError as e:
        err = e
    sent = 0
    for path in sorted(SHARED.glob("*.sock")) if SHARED.is_dir() else []:
        try:
            send_to(path, toast)
            sent += 1
        except OSError:
            pass
    if not sent:
        print(f"famidrive-toast: no toast daemon ({err}): {toast.get('title')}", file=sys.stderr)


# --- Desktop notifications ---------------------------------------------------
#
# Apps on the box (Heroic, and anything else that uses libnotify or
# Electron's notifications) send desktop notifications over D-Bus to
# whatever owns org.freedesktop.Notifications. In the TV session that's
# the toast daemon, so they show as toasts too.

def strip_markup(text):
    """The spec's body markup (<b>, <i>, <a href>...) and entities, gone."""
    text = re.sub(r"<[^>]+>", "", text or "")
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        text = text.replace(a, b)
    return text.strip()


def from_notification(app, replaces, icon, summary, body, hints, nid):
    """A toast from a Notify call. Hints are {name: (signature, value)}.
    Critical urgency is an alert; a "value" hint (0-100) is progress,
    updated in place under the same notification id."""
    hint = {k: v[1] if isinstance(v, tuple) else v for k, v in (hints or {}).items()}
    toast = {"kind": "notice", "title": strip_markup(summary) or app or "Notification"}
    detail = strip_markup(body)
    if detail:
        toast["detail"] = detail
    if hint.get("urgency") == 2:
        toast["kind"] = "alert"
    if isinstance(hint.get("value"), int):
        toast["kind"] = "progress"
        toast["progress"] = max(0, min(100, hint["value"])) / 100
        toast["done"] = hint["value"] >= 100
    image = hint.get("image-path") or hint.get("image_path") or icon or ""
    if image.startswith("file://"):
        image = image[7:]
    if image.startswith("/") and Path(image).exists():
        toast["icon"] = image
    toast["id"] = f"fdo-{replaces or nid}"
    return toast


def serve_notifications():
    """Own org.freedesktop.Notifications on the session bus and hand each
    notification to the daemon as a toast. Returns quietly when there's no
    bus, jeepney, or another notification daemon already."""
    try:
        from jeepney import HeaderFields, MessageType, new_error, new_method_return
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection
        conn = open_dbus_connection(bus="SESSION")
        if conn.send_and_get_reply(message_bus.RequestName("org.freedesktop.Notifications", 4)).body[0] != 1:
            print("famidrive-toast: another notification daemon is running", file=sys.stderr)
            return
    except Exception as e:   # no session bus: toasts still work without it
        print(f"famidrive-toast: no desktop notifications ({e})", file=sys.stderr)
        return
    next_id = 1
    while True:
        msg = conn.receive()
        if msg.header.message_type != MessageType.method_call:
            continue
        member = msg.header.fields.get(HeaderFields.member)
        if member == "Notify":
            app, replaces, icon, summary, body, _actions, hints, _timeout = msg.body
            nid = replaces or next_id
            if not replaces:
                next_id += 1
            send(from_notification(app, replaces, icon, summary, body, hints, nid))
            conn.send(new_method_return(msg, "u", (nid,)))
        elif member == "GetCapabilities":
            conn.send(new_method_return(msg, "as", (["body"],)))
        elif member == "GetServerInformation":
            conn.send(new_method_return(msg, "ssss", ("famidrive-toast", "FamiDrive", "1", "1.2")))
        elif member == "CloseNotification":
            conn.send(new_method_return(msg))
        else:
            conn.send(new_error(msg, "org.freedesktop.DBus.Error.UnknownMethod"))


# --- Controllers ------------------------------------------------------------
#
# Controllers coming and going, and running low, as toasts: on "Who's
# playing?", in the menu and in a game, in place of ES-DE's own pop-ups
# (InputDeviceNotifications, off). Read from the kernel's joystick devices
# and their batteries, so any pad counts, whatever drives it.

SYS = Path("/sys/class")
LOW = 20   # percent: warn once at or below, again after charging past LOW + 10


def connected_pads(sys_class=SYS):
    """{device path: name} for each controller the kernel has a joystick
    (jsN) for. A controller with more than one joystick counts once, by
    its first: a DualSense's motion sensors are a joystick of their own,
    and got a "Controller disconnected" toast of their own (first box,
    2026-10-09)."""
    pads = {}
    for js in sorted((sys_class / "input").glob("js*")):
        try:
            dev = Path(os.path.realpath(js / "device"))
            name = (dev / "name").read_text().strip() or "Controller"
        except OSError:
            continue
        number = int(dev.name[5:]) if dev.name[5:].isdigit() else 0   # inputN
        pads.setdefault(str(dev.parent), []).append((number, name))
    return {parent: min(found)[1] for parent, found in pads.items()}


def pad_batteries(sys_class=SYS):
    """{power supply: (pad name, percent)} for batteries that belong to a
    device (scope Device) with a joystick-like input under it."""
    out = {}
    for ps in sorted((sys_class / "power_supply").glob("*")):
        try:
            if (ps / "scope").read_text().strip() != "Device":
                continue
            cap = int((ps / "capacity").read_text().strip())
        except (OSError, ValueError):
            continue
        names = sorted(Path(os.path.realpath(ps / "device")).glob("input/input*/name"))
        if names:
            out[str(ps)] = (names[0].read_text().strip() or "Controller", cap)
    return out


def pad_status(sys_class=SYS):
    """[(name, battery percent or None)] for each connected controller,
    for the menu. A battery is matched to its pad by the device both hang
    off; a pad that reports none (the 8BitDo's 2.4 GHz dongle under xpad,
    a wired pad) has None."""
    levels = {}
    for ps in sorted((sys_class / "power_supply").glob("*")):
        try:
            if (ps / "scope").read_text().strip() != "Device":
                continue
            levels[os.path.realpath(ps / "device")] = int((ps / "capacity").read_text().strip())
        except (OSError, ValueError):
            continue
    # connected_pads keys a pad by its .../input folder, one below the
    # device its battery hangs off.
    return [(name, levels.get(str(Path(dev).parent))) for dev, name in connected_pads(sys_class).items()]


def in_game():
    """Whether a game is running in this session (gamescope-fg's marker)."""
    return (sock_path().parent / "famidrive-game.pgid").exists()


def game_mode():
    """What the Guide menu does with the running game (a system's
    guideMenu, written by the launch): "freeze" or "block". "block" when
    the launch said nothing."""
    try:
        words = (sock_path().parent / "famidrive-game.menu").read_text().split()
    except OSError:
        return "block"
    return words[0] if words and words[0] in ("freeze", "block") else "block"


def recording_since():
    """When famidrive-record's recording in this session started (as
    time.time()), or None if it isn't recording: its state file, with a
    recorder that's still there. A state file from before it said when is
    taken as written at the start."""
    path = sock_path().parent / "famidrive-record.json"
    try:
        state = json.loads(path.read_text())
        os.kill(int(state["pid"]), 0)
        return float(state.get("started") or path.stat().st_mtime)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def recording():
    return recording_since() is not None


def elapsed(seconds):
    """A recording's length so far, as 0:42 or 1:02:03."""
    m, s = divmod(max(0, int(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def pulse(seconds):
    """How bright the dot beside Stop is: full and dull by turns, half a
    second each, so a whole pulse a second."""
    return 1.0 if int(max(0, seconds) * 2) % 2 == 0 else 0.35


def record(cmd):
    """famidrive-record start or stop, by name from PATH (a fix to it then
    doesn't restart the TV), in the background: stopping waits for the
    file to be finished, and the daemon has the screen to draw meanwhile."""
    import subprocess
    import threading

    def run():
        try:
            subprocess.run(["famidrive-record", cmd], stdin=subprocess.DEVNULL)
        except OSError as e:
            print(f"famidrive-toast: couldn't run famidrive-record ({e})", file=sys.stderr)
    threading.Thread(target=run, daemon=True).start()


def pausable():
    """Whether the running thing is a game, to pause: not Steam's Big
    Picture or the voice client, which leave a polite way to close them
    instead (famidrive-game.close)."""
    try:
        return not (sock_path().parent / "famidrive-game.close").read_text().strip()
    except OSError:
        return True


IDLE_OFF = "famidrive-idle-off.json"   # pads famidrive-quit just switched off for being idle


def idle_off(run=None, now=None):
    """{pad name: idle minutes} for pads famidrive-quit switched off in the
    last minute (its famidrive-idle-off.json)."""
    try:
        found = json.loads(((run or sock_path().parent) / IDLE_OFF).read_text())
    except (OSError, ValueError):
        return {}
    now = time.time() if now is None else now
    return {o["name"]: o.get("minutes") for o in found if isinstance(o, dict) and now - o.get("at", 0) < 60}


def pad_changes(before, after, playing, switched_off=None):
    """The toasts for pads that came and went between two scans. A pad
    famidrive-quit switched off for being idle (switched_off: {name:
    minutes}) gets a plain notice saying so, in a game too: the player is
    likely to pick it up again and play on, not quit."""
    toasts = []
    switched_off = switched_off or {}
    for dev, name in sorted(after.items()):
        if dev not in before:
            toasts.append({"kind": "notice", "icon": "controller", "title": "Controller connected", "detail": name})
    for dev, name in sorted(before.items()):
        if dev not in after and name in switched_off:
            minutes = switched_off[name]
            idle = f"was idle for {minutes:g} minutes" if minutes else "was idle"
            toasts.append({"kind": "notice", "icon": "controller", "title": "Controller switched off",
                           "detail": f"{name} {idle}. Turn it back on to keep playing."})
        elif dev not in after:
            detail = name
            if playing:
                detail += ". To play on with another controller, quit with Select + Start and start the game again."
            toasts.append({"kind": "alert" if playing else "notice", "icon": "controller",
                           "title": "Controller disconnected", "detail": detail})
    return toasts


def battery_changes(warned, now):
    """Low-battery toasts, once per pad until it's charged again."""
    toasts = []
    for ps, (name, cap) in now.items():
        if cap <= LOW and ps not in warned:
            warned.add(ps)
            toasts.append({"kind": "alert", "icon": "controller", "title": "Controller battery low",
                           "detail": f"{name}: {cap}%"})
        elif cap > LOW + 10:
            warned.discard(ps)
    return toasts


def watch_controllers(interval=1.5):
    """Scan for pads every so often and toast what changed. Pads already
    connected when the session starts aren't announced."""
    before, warned = connected_pads(), set()
    while True:
        time.sleep(interval)
        after = connected_pads()
        for t in pad_changes(before, after, in_game(), idle_off()) + battery_changes(warned, pad_batteries()):
            send(t)
        before = after


# --- The Guide menu -----------------------------------------------------------
#
# Guide (the Xbox or PS button) opens FamiDrive's menu over whatever's on
# the TV, drawn on this daemon's window like the toasts, in a panel on the
# right, the side toasts show on. famidrive-quit watches the pads, grabs
# them while the menu is open so the game doesn't see the presses, and
# sends each one here as a command: {"menu": "open" | "up" | "down" |
# "left" | "right" | "select" | "back" | "close"}. The reply says whether
# the menu is still open, and what famidrive-quit should do ("quit").
#
# With recordings on (famidrive.recordings), the menu also starts and
# stops a recording of the screen (famidrive-record). "Start recording"
# closes the menu and counts down from 3 in the middle of the screen
# first, so the menu and the countdown aren't in the recording. While it
# records, the menu has Stop in its place, with a red dot pulsing beside
# it and the time so far; nothing shows over the game, but a "Recording"
# toast as it starts (famidrive-record). Found on the first box
# 2026-10-16: a dot over the game, in a window on gamescope's external
# overlay layer (left out of the recording), made the game itself look
# worse and run slower while recording. That layer is one more for
# gamescope to show, and it then drew the whole picture itself, every
# frame, instead of handing the game to the TV as it was. The Steam
# overlay layer, where the toasts are, is in the recording.

class Menu:
    """The menu's state. Pure: whether a game is running, whether it's one
    to pause, and its guideMenu are passed in.

    In a game: Resume, and Quit game, which asks first, since anything not
    saved is lost. Out of one: Close. A "freeze" game (an emulator) is
    stopped while the menu is open; a "block" one (an online game) keeps
    running, with the pads taken from it. With recordings on, Start
    recording (or Stop recording, while one is under way) is a half-width
    button above them, drawn as Record (or Stop); the menu still opens on
    Resume or Close."""

    def __init__(self, recordings=False):
        self.recordings = recordings
        self.recording = False
        self.open = False
        self.view = "main"   # or "confirm": Quit game's "are you sure?"
        self.items = []
        self.sel = 0
        self.playing = False
        self.mode, self.note = "block", ""

    def _main(self):
        self.view = "main"
        record = ["Stop recording" if self.recording else "Start recording"] if self.recordings else []
        self.items = [*record, "Resume", "Quit game"] if self.playing else [*record, "Close"]

    def command(self, cmd, playing, pausable=True, mode="block", recording=False):
        if cmd == "open":
            self.open, self.sel, self.playing, self.recording = True, 0, playing, recording
            # Big Picture and the voice client aren't games to pause.
            self.mode = mode if playing and pausable else "none"
            self.note = {"freeze": "Game paused", "block": "The game keeps running"}.get(self.mode, "")
            self._main()
            self.sel = self.items.index("Resume" if playing else "Close")
            return self.state()
        if not self.open:
            return self.state()
        item = self.items[self.sel]
        if cmd == "close" or (cmd == "back" and self.view == "main"):
            self.open = False
        elif cmd == "back" or (cmd == "select" and item == "Cancel"):
            self._main()
            self.sel = self.items.index("Quit game")
        elif cmd == "up":
            self.sel = max(0, self.sel - 1)
        elif cmd == "down":
            self.sel = min(len(self.items) - 1, self.sel + 1)
        elif cmd == "select" and item == "Quit game":
            self.view, self.items, self.sel = "confirm", ["Cancel", "Quit"], 0
        elif cmd == "select" and item == "Quit":
            self.open = False
            return {"open": False, "do": "quit"}
        elif cmd == "select" and item in ("Start recording", "Stop recording"):
            # Done by the daemon itself; famidrive-quit only acts on "quit".
            self.open = False
            return {"open": False, "do": "record" if item == "Start recording" else "stop-recording"}
        elif cmd == "select":   # Resume, Close
            self.open = False
        return self.state()

    def state(self):
        return {"open": self.open}


# --- The daemon -------------------------------------------------------------

def live(path):
    """Whether a daemon answers on this socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(str(path))
        return True
    except OSError:
        return False


def listen(path, mode):
    """A listening socket at path, unless a live daemon already has it
    (None then): only a dead one left behind is replaced. Found on the
    first box 2026-10-07: a second daemon took the player's shared socket
    over and left a dead file there when it stopped, so the library pull's
    toasts were refused."""
    if os.path.exists(path):
        if live(path):
            return None
        os.unlink(path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(path, mode)
    srv.listen(8)
    return srv


def release(paths):
    """Remove the sockets this daemon made, if they're still its own."""
    for path, ino in paths:
        try:
            if os.stat(path).st_ino == ino:
                os.unlink(path)
        except OSError:
            pass


def daemon(spec_file, player):
    import select

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # pygame only draws; X shows
    import pygame
    from Xlib import X, Xatom, display as xdisplay

    spec = json.loads(read(spec_file) or "{}")
    me = player_spec(spec, player)
    theme = spec.get("theme")
    queue = Queue(me["hide"])
    # Not on "Who's playing?": nobody's session to record into yet.
    menu = Menu(recordings=bool(spec.get("recordings")) and player != "greeter")

    pygame.font.init()
    d = xdisplay.Display()
    scr = d.screen()
    sw, sh = scr.width_in_pixels, scr.height_in_pixels
    u = sh / 1080

    # A 32-bit visual, so everything outside the toast is see-through.
    visual = next(v.visual_id for depth in scr.allowed_depths if depth.depth == 32
                  for v in depth.visuals if v.visual_class == X.TrueColor)
    cmap = scr.root.create_colormap(visual, X.AllocNone)
    win = scr.root.create_window(0, 0, sw, sh, 0, 32, X.InputOutput, visual,
                                 background_pixel=0, border_pixel=0, colormap=cmap,
                                 override_redirect=True, event_mask=X.ExposureMask)
    win.set_wm_name("famidrive-toast")
    win.change_property(d.intern_atom("STEAM_OVERLAY"), Xatom.CARDINAL, 32, [1])
    win.map()
    gc = win.create_gc()
    fill_gc = win.create_gc()   # for solid fills the X server does itself
    d.flush()

    def fnt(path, size):
        try:
            if path:
                return pygame.font.Font(str(path), size)
        except (FileNotFoundError, OSError):
            pass
        return pygame.font.Font(None, int(size * 1.3))

    regular, light = theme_fonts(theme)
    title_f, detail_f, small_f = fnt(regular, int(30 * u)), fnt(light, int(24 * u)), fnt(regular, int(18 * u))
    # The menu is read from the couch, so it's bigger and heavier than a
    # toast: the theme's regular font throughout, never its light one.
    # Found on the first box 2026-10-13: Art Book Next's light font
    # (Mulish Light) was hard to read from 10 feet, and pygame's made-up
    # bold on top of its regular one looked blocky.
    m_title, m_body, m_small = fnt(regular, int(34 * u)), fnt(regular, int(28 * u)), fnt(regular, int(22 * u))
    m_label = m_body
    count_f = fnt(regular, int(150 * u))
    pad, gap, radius = int(22 * u), int(18 * u), int(14 * u)
    width = int(600 * u)
    margin = int(40 * u)

    def image_icon(path, size):
        """An image fitted into size x size, centered, keeping its shape (a
        game's logo is usually wide). Copied onto a 32-bit surface first:
        smoothscale takes no palette images, and there's no display to
        convert() for."""
        try:
            img = pygame.image.load(path)
        except (pygame.error, FileNotFoundError, OSError):
            return None
        rgba = pygame.Surface(img.get_size(), pygame.SRCALPHA, 32)
        rgba.blit(img, (0, 0))
        w, h = img.get_size()
        k = size / max(w, h)
        fitted = pygame.transform.smoothscale(rgba, (max(1, int(w * k)), max(1, int(h * k))))
        out = pygame.Surface((size, size), pygame.SRCALPHA, 32)
        out.blit(fitted, ((size - fitted.get_width()) // 2, (size - fitted.get_height()) // 2))
        return out

    def stroke(c, color, points, w):
        """A thick polyline with round ends and joins. pygame's own thick
        lines end in flat, slanted cuts and leave a notch at each join,
        which read as clipped at a toast's size."""
        r = w / 2
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            dx, dy = x1 - x0, y1 - y0
            k = r / max(1e-6, (dx * dx + dy * dy) ** .5)
            ox, oy = -dy * k, dx * k
            pygame.draw.polygon(c, color, [(x0 + ox, y0 + oy), (x1 + ox, y1 + oy), (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)])
        for x, y in points:
            pygame.draw.circle(c, color, (x, y), r)

    def drawn_icon(name, size, color):
        """One of ICONS, drawn at 4x and scaled down, for smooth edges."""
        n = size * 4
        c = pygame.Surface((n, n), pygame.SRCALPHA, 32)
        clear = (0, 0, 0, 0)
        lw = max(4, n // 14)
        if name == "save":   # a floppy disk
            body = pygame.Rect(n * .12, n * .12, n * .76, n * .76)
            pygame.draw.rect(c, color, body, border_radius=n // 14)
            pygame.draw.polygon(c, clear, [(body.right - n * .16, body.top), (body.right, body.top), (body.right, body.top + n * .16)])
            pygame.draw.rect(c, clear, (n * .30, n * .12, n * .36, n * .22))              # the shutter's opening
            pygame.draw.rect(c, color, (n * .52, n * .15, n * .09, n * .16))              # its slot
            pygame.draw.rect(c, clear, (n * .24, n * .50, n * .52, n * .32), border_radius=n // 40)   # the label
            for k in (.59, .69):
                pygame.draw.line(c, color, (n * .32, n * k), (n * .68, n * k), max(2, lw // 2))
        elif name == "warning":   # a triangle with an exclamation mark
            pygame.draw.polygon(c, color, [(n * .5, n * .08), (n * .95, n * .88), (n * .05, n * .88)])
            pygame.draw.rect(c, clear, (n * .455, n * .34, n * .09, n * .30), border_radius=n // 30)
            pygame.draw.circle(c, clear, (n * .5, n * .75), n * .055)
        elif name == "trophy":   # a cup with handles on a stand
            pygame.draw.arc(c, color, (n * .08, n * .2, n * .3, n * .3), 1.2, 4.6, lw)
            pygame.draw.arc(c, color, (n * .62, n * .2, n * .3, n * .3), -1.45, 1.95, lw)
            pygame.draw.rect(c, color, (n * .24, n * .1, n * .52, n * .22))
            pygame.draw.ellipse(c, color, (n * .24, n * .1, n * .52, n * .5))
            pygame.draw.rect(c, color, (n * .45, n * .55, n * .1, n * .18))
            pygame.draw.rect(c, color, (n * .3, n * .72, n * .4, n * .08), border_radius=n // 40)
            pygame.draw.rect(c, color, (n * .24, n * .8, n * .52, n * .1), border_radius=n // 40)
        elif name == "controller":   # a gamepad: body, grips, d-pad, two buttons
            pygame.draw.rect(c, color, (n * .14, n * .30, n * .72, n * .34), border_radius=int(n * .17))
            pygame.draw.circle(c, color, (n * .26, n * .62), n * .14)
            pygame.draw.circle(c, color, (n * .74, n * .62), n * .14)
            pygame.draw.rect(c, clear, (n * .21, n * .44, n * .16, n * .05))
            pygame.draw.rect(c, clear, (n * .265, n * .385, n * .05, n * .16))
            pygame.draw.circle(c, clear, (n * .66, n * .43), n * .04)
            pygame.draw.circle(c, clear, (n * .74, n * .51), n * .04)
        elif name == "check":   # a checkmark in a circle
            pygame.draw.circle(c, color, (n * .5, n * .5), n * .44)
            stroke(c, clear, [(n * .29, n * .51), (n * .44, n * .66), (n * .72, n * .37)], max(4, n // 9))
        elif name == "music":   # two beamed eighth notes
            for x in (.30, .74):
                pygame.draw.ellipse(c, color, (n * (x - .19), n * .66, n * .22, n * .17))
                pygame.draw.rect(c, color, (n * (x - .02), n * .20, n * .05, n * .56))
            pygame.draw.polygon(c, color, [(n * .28, n * .20), (n * .79, n * .10), (n * .79, n * .22), (n * .28, n * .32)])
        elif name == "record":   # a ring around a dot
            pygame.draw.circle(c, color, (n * .5, n * .5), n * .44, lw)
            pygame.draw.circle(c, RED, (n * .5, n * .5), n * .26)
        elif name == "stop":   # a rounded square
            pygame.draw.rect(c, color, (n * .2, n * .2, n * .6, n * .6), border_radius=n // 10)
        elif name == "download":   # an arrow down into a tray
            pygame.draw.rect(c, color, (n * .43, n * .08, n * .14, n * .42))
            pygame.draw.polygon(c, color, [(n * .25, n * .46), (n * .75, n * .46), (n * .5, n * .70)])
            pygame.draw.lines(c, color, False, [(n * .12, n * .62), (n * .12, n * .88), (n * .88, n * .88), (n * .88, n * .62)], lw)
        else:   # info: an "i" in a circle
            pygame.draw.circle(c, color, (n * .5, n * .5), n * .44)
            pygame.draw.circle(c, clear, (n * .5, n * .30), n * .065)
            pygame.draw.rect(c, clear, (n * .44, n * .42, n * .12, n * .34), border_radius=n // 40)
        return pygame.transform.smoothscale(c, (size, size))

    def icon_for(toast, size, colors):
        name = icon_name(toast)
        if name not in ICONS:
            img = image_icon(name, size)
            if img:
                return img
            name = KIND_ICON.get(toast["kind"], "info")
        color = {"warning": ALERT, "trophy": GOLD, "check": SUCCESS}.get(name, colors["text"])
        return drawn_icon(name, size, color)

    def render(toast, alpha, colors):
        isz = int(64 * u)
        img = icon_for(toast, isz, colors)
        text_w = width - 2 * pad - isz - gap
        header = {"achievement": "Achievement unlocked", "alert": None}.get(toast["kind"])
        lines = []
        if header:
            lines.append((small_f, header.upper(), colors["dim"]))
        lines.append((title_f, toast.get("title", ""), colors["text"]))
        for line in wrap(toast.get("detail", ""), detail_f, text_w)[:3]:
            lines.append((detail_f, line, colors["dim"]))
        text_h = sum(f.get_linesize() for f, _, _ in lines)
        bar_h = int(8 * u) if toast["kind"] == "progress" else 0
        inner = max(isz, text_h + (gap + bar_h if bar_h else 0))
        surf = pygame.Surface((width, inner + 2 * pad), pygame.SRCALPHA, 32)
        pygame.draw.rect(surf, opaque(colors["panel"]), surf.get_rect(), border_radius=radius)
        if toast["kind"] in ("alert", "achievement", "success"):
            accent = {"alert": ALERT, "achievement": GOLD, "success": SUCCESS}[toast["kind"]]
            pygame.draw.rect(surf, accent, (0, radius, int(5 * u), surf.get_height() - 2 * radius))
        surf.blit(img, (pad, pad + (inner - isz) // 2))
        x = pad + isz + gap
        y = pad + (inner - text_h - (gap + bar_h if bar_h else 0)) // 2
        for f, s, c in lines:
            s = ellipsize(s, f, text_w)
            surf.blit(f.render(s, True, c), (x, y))
            y += f.get_linesize()
        if bar_h:
            y += gap
            # The track is the text color, faint: a theme's own grey can be
            # the text color itself (Art Book Next's OLED scheme).
            pygame.draw.rect(surf, (*colors["text"][:3], 60), (x, y, text_w, bar_h), border_radius=bar_h // 2)
            p = 1.0 if toast.get("done") else toast.get("progress")
            if p is None:   # no fraction: a block that slides back and forth
                seg = text_w // 4
                t = (time.monotonic() % 1.6) / 1.6
                pos = int((text_w - seg) * (1 - abs(2 * t - 1)))
                pygame.draw.rect(surf, colors["text"], (x + pos, y, seg, bar_h), border_radius=bar_h // 2)
            elif p > 0:
                pygame.draw.rect(surf, colors["text"], (x, y, max(bar_h, int(text_w * p)), bar_h), border_radius=bar_h // 2)
        surf = with_shadow(surf)
        if alpha < 255:
            surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        return surf

    spread, drop = int(28 * u), int(8 * u)
    shadows = {}

    def with_shadow(panel):
        """The panel over a soft shadow, a little below it, so it stands
        off whatever's behind it. The result is `spread` larger on every
        side; place() still lines up the panel itself."""
        w, h = panel.get_size()
        size = (w + 2 * spread, h + 2 * spread)
        if (w, h) not in shadows:
            sh = pygame.Surface(size, pygame.SRCALPHA, 32)
            pygame.draw.rect(sh, (0, 0, 0, 160), (spread, spread + drop, w, h), border_radius=radius)
            shadows.clear()
            shadows[(w, h)] = pygame.transform.gaussian_blur(sh, spread // 2)
        out = shadows[(w, h)].copy()
        out.blit(panel, (spread, spread))
        return out

    def bgra(color):
        """One pixel of color, premultiplied, the way put sends it."""
        px = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        px.fill(color)
        return pygame.image.tobytes(px.premul_alpha(), "BGRA")

    def put(surf, pos, target=None, skip=None, prev=None):
        """Copy an RGBA surface into the window (or a pixmap), premultiplied,
        as BGRA rows in chunks the X server takes in one request each.
        skip: a color the target is already filled with; chunks that are
        only that color aren't sent. Found on the first box 2026-10-13:
        sending a 4K screen's worth of pixels made the menu come out
        noticeably after the blur behind it. prev: what was last sent to
        the same place; chunks that haven't changed aren't sent either.
        Returns what was sent, for the next one's prev."""
        s = surf.premul_alpha()
        data = pygame.image.tobytes(s, "BGRA")
        w, h = s.get_size()
        rows = max(1, 200_000 // (w * 4))
        solid = bgra(skip) * (w * rows) if skip else None
        for top in range(0, h, rows):
            n = min(rows, h - top)
            chunk = data[top * w * 4:(top + n) * w * 4]
            if (solid and chunk == solid[:len(chunk)]) or (prev and chunk == prev[top * w * 4:(top + n) * w * 4]):
                continue
            (target or win).put_image(gc, pos[0], pos[1] + top, w, n, X.ZPixmap, 32, 0, chunk)
        return data

    def fill_solid(target, color, rect):
        """Fill a rect with one color on the X server: nothing sent but the
        rect, however big."""
        b, g, r, a = bgra(color)
        fill_gc.change(foreground=(a << 24) | (r << 16) | (g << 8) | b)
        target.fill_rectangle(fill_gc, *rect)

    def clear(rect):
        if rect:
            fill_solid(win, (0, 0, 0, 0), rect)

    def fill(surf, color, rect, r=0):
        """A filled rounded rect blended onto surf: drawing straight onto a
        32-bit surface replaces its pixels, alpha and all, which would cut a
        see-through hole in the panel for a faint fill."""
        tmp = pygame.Surface(rect[2:], pygame.SRCALPHA, 32)
        pygame.draw.rect(tmp, color, tmp.get_rect(), border_radius=r)
        surf.blit(tmp, rect[:2])

    def on_text(text):
        """Text on a highlight the theme's text color: black on a light
        one, white on a dark one. The panel's own color, used before,
        could be a grey nearly as light (first box, 2026-10-13)."""
        r, g, b = text[:3]
        return (17, 17, 17) if 0.299 * r + 0.587 * g + 0.114 * b > 128 else (255, 255, 255)

    def render_menu(pads, colors):
        """The menu's panel: the screen's full height, on the right. Also
        returns the rows its buttons (and the quit question) are drawn in,
        which slide when the buttons change."""
        pw, m = int(640 * u), int(40 * u)
        text, dim = colors["text"], colors["dim"]
        faint = (*text[:3], 30)
        surf = pygame.Surface((pw, sh), pygame.SRCALPHA, 32)
        surf.fill(opaque(colors["panel"]))
        y = m
        surf.blit(m_title.render(time.strftime("%-I:%M %p"), True, text), (m, y))
        y += m_title.get_linesize() + int(30 * u)

        surf.blit(m_small.render("CONTROLLERS", True, dim), (m, y))
        y += m_small.get_linesize() + int(12 * u)
        if not pads:
            surf.blit(m_body.render("No controllers connected", True, dim), (m, y))
            y += m_body.get_linesize() + int(24 * u)
        tg, ip, isz = int(14 * u), int(16 * u), int(40 * u)
        tw, th = (pw - 2 * m - tg) // 2, int(180 * u)
        shown = pads[:8]
        for i, (name, level) in enumerate(shown):
            tile = pygame.Surface((tw, th), pygame.SRCALPHA, 32)
            fill(tile, faint, (0, 0, tw, th), radius)
            tile.blit(drawn_icon("controller", isz, text), (ip, ip))
            if level is not None:
                pct = m_label.render(f"{level}%", True, text)
                tile.blit(pct, (tw - ip - pct.get_width(), ip + (isz - pct.get_height()) // 2))
            ly = ip + isz + int(8 * u)
            for line in wrap(name, m_small, tw - 2 * ip)[:2]:
                tile.blit(m_small.render(ellipsize(line, m_small, tw - 2 * ip), True, text), (ip, ly))
                ly += m_small.get_linesize()
            if level is None:   # the 8BitDo's dongle, a wired pad: the kernel gives no level
                note = m_small.render("No battery level", True, dim)
                tile.blit(note, (ip, th - ip - note.get_height()))
            else:
                bh, bw = int(8 * u), tw - 2 * ip
                fill(tile, (*text[:3], 60), (ip, th - ip - bh, bw, bh), bh // 2)
                fill(tile, ALERT if level <= LOW else SUCCESS,
                     (ip, th - ip - bh, max(bh, bw * level // 100), bh), bh // 2)
            surf.blit(tile, (m + (i % 2) * (tw + tg), y + (i // 2) * (th + tg)))
        y += (len(shown) + 1) // 2 * (th + tg) + int(24 * u)

        top = y
        if menu.view == "main" and menu.note:
            surf.blit(m_body.render(menu.note, True, dim), (m, y))
            y += m_body.get_linesize() + int(10 * u)
        elif menu.view == "confirm":
            surf.blit(m_title.render("Quit the game?", True, text), (m, y))
            y += m_title.get_linesize()
            for line in wrap("Any unsaved progress will be lost.", m_body, pw - 2 * m):
                surf.blit(m_body.render(line, True, dim), (m, y))
                y += m_body.get_linesize()
            y += int(18 * u)
        bh = int(68 * u)
        for i, item in enumerate(menu.items):
            on = i == menu.sel
            ink = on_text(text) if on else text
            if item in RECORD_ITEMS:
                # Half the width, an icon and a word: a quick action, not
                # one of the menu's choices about the game.
                tw = (pw - 2 * m - int(14 * u)) // 2
                fill(surf, text if on else faint, (m, y, tw, bh), int(10 * u))
                isz = int(36 * u)
                icon = drawn_icon("record" if item == "Start recording" else "stop", isz, ink)
                label = m_label.render(RECORD_ITEMS[item], True, ink)
                x = m + (tw - isz - int(14 * u) - label.get_width()) // 2
                surf.blit(icon, (x, y + (bh - isz) // 2))
                surf.blit(label, (x + isz + int(14 * u), y + (bh - label.get_height()) // 2))
                since = recording_since() if item == "Stop recording" else None
                if since is not None:
                    # Beside it, the other half: that it's live, and for how long.
                    t = time.time() - since
                    r = int(11 * u)
                    dot = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA, 32)
                    pygame.draw.circle(dot, (*RED[:3], int(255 * pulse(t))), (r, r), r)
                    clock = m_label.render(elapsed(t), True, text)
                    x = m + tw + int(14 * u) + int(24 * u)
                    surf.blit(dot, (x, y + bh // 2 - r))
                    surf.blit(clock, (x + 2 * r + int(14 * u), y + (bh - clock.get_height()) // 2))
            else:
                fill(surf, text if on else faint, (m, y, pw - 2 * m, bh), int(10 * u))
                label = m_label.render(item, True, ink)
                surf.blit(label, (m + int(24 * u), y + (bh - label.get_height()) // 2))
            y += bh + int(12 * u)

        g = int(40 * u)
        x, gy = m, sh - m - g
        for letter, what in (("A", "Select"), ("B", "Back")):
            pygame.draw.circle(surf, text, (x + g // 2, gy + g // 2), g // 2)
            glyph = m_small.render(letter, True, on_text(text))
            surf.blit(glyph, (x + (g - glyph.get_width()) // 2, gy + (g - glyph.get_height()) // 2))
            label = m_body.render(what, True, dim)
            surf.blit(label, (x + g + int(10 * u), gy + (g - label.get_height()) // 2))
            x += g + int(10 * u) + label.get_width() + int(32 * u)
        return surf, (top, gy - int(24 * u))

    def render_count(n, colors):
        """The countdown before a recording: the number in a round panel,
        in the middle of the screen."""
        size = int(240 * u)
        surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
        pygame.draw.circle(surf, opaque(colors["panel"]), (size // 2, size // 2), size // 2)
        digit = count_f.render(str(n), True, colors["text"])
        surf.blit(digit, ((size - digit.get_width()) // 2, (size - digit.get_height()) // 2))
        return surf

    def menu_key(pads):
        since = recording_since() if "Stop recording" in menu.items else None
        live = None if since is None else int((time.time() - since) * 2)   # the dot's pulse and the time so far
        return (menu.view, menu.sel, menu.note, tuple(menu.items), tuple(pads), time.strftime("%-I:%M"), live)

    def dim_at(k):
        """The dim at k of its full strength (it fades in and out with the
        panel), as a solid fill."""
        return (*DIM[:3], int(DIM[3] * max(0.0, min(1.0, k))))

    def draw_menu(sheet, before):
        """Redraw the settled menu if it changed; returns what's drawn now.
        Drawn into the panel's pixmap, then copied onto the screen in one
        go, so it never shows half drawn. When the buttons change to the
        quit question or back, that part of the panel slides instead."""
        pads = pad_status()
        key = menu_key(pads)
        if key == before:
            return before
        colors = theme_colors(theme, color_scheme(Path.home()))
        panel, band = render_menu(pads, colors)
        if menu.view != sheet["view"]:
            start_swap(sheet, panel, band, colors, forward=menu.view == "confirm")
        sheet["view"], sheet["surf"], sheet["band"] = menu.view, panel, band
        sheet["data"] = put(panel, (0, 0), sheet["pix"], prev=sheet["data"])
        if not sheet.get("swap"):
            win.copy_area(gc, sheet["pix"], 0, 0, sheet["pw"], sh, sw - sheet["pw"], 0)
        return key

    def start_swap(sheet, new, band, colors, forward):
        """The old buttons and the new ones side by side in a pixmap, the
        new ones to the right going forward (to the quit question) and to
        the left coming back; each frame shows a window onto it that moves
        across, so one set slides out as the other slides in."""
        pw = sheet["pw"]
        top, bottom = band[0], max(band[1], sheet["band"][1])
        top = min(top, sheet["band"][0])
        h = bottom - top
        pix = win.create_pixmap(2 * pw, h, 32)
        color = opaque(colors["panel"])
        fill_solid(pix, color, (0, 0, 2 * pw, h))
        old = sheet["surf"].subsurface((0, top, pw, h))
        first, second = (old, new.subsurface((0, top, pw, h))) if forward else (new.subsurface((0, top, pw, h)), old)
        put(first, (0, 0), pix, skip=color)
        put(second, (pw, 0), pix, skip=color)
        sheet["swap"] = {"pix": pix, "t0": time.monotonic(), "top": top, "h": h, "forward": forward}

    def swap_step(sheet):
        sw_ = sheet["swap"]
        p = (time.monotonic() - sw_["t0"]) / SWAP_SECONDS
        k = ease_out(p)
        off = int(round(sheet["pw"] * (k if sw_["forward"] else 1 - k)))
        win.copy_area(gc, sw_["pix"], off, 0, sheet["pw"], sw_["h"], sw - sheet["pw"], sw_["top"])
        if p >= 1:
            sw_["pix"].free()
            sheet["swap"] = None
            win.copy_area(gc, sheet["pix"], 0, 0, sheet["pw"], sh, sw - sheet["pw"], 0)

    def open_menu():
        """Start the panel's slide in. The panel goes to the X server once,
        as a pixmap, and each frame of the slide is a copy from it there,
        with the dim filled in by the X server as it fades in. Only the
        panel's rows with something on them are sent."""
        pads = pad_status()
        colors = theme_colors(theme, color_scheme(Path.home()))
        panel, band = render_menu(pads, colors)
        pw = panel.get_width()
        pix = win.create_pixmap(pw, sh, 32)
        fill_solid(pix, opaque(colors["panel"]), (0, 0, pw, sh))
        data = put(panel, (0, 0), pix, skip=opaque(colors["panel"]))
        return {"t0": time.monotonic(), "pw": pw, "pix": pix, "phase": "in", "view": menu.view,
                "surf": panel, "band": band, "swap": None, "key": menu_key(pads), "data": data}

    def slide_step(sl):
        """One frame of the panel sliding in (ease-out) or out (ease-in, so
        it leaves the way it came), with the dim fading along; True once
        it's done."""
        p = (time.monotonic() - sl["t0"]) / SLIDE_SECONDS
        k = ease_out(p) if sl["phase"] == "in" else 1 - ease_out(1 - min(p, 1))
        shown = k if sl["phase"] == "in" else 1 - k
        x = sw - int(round(sl["pw"] * shown))
        fill_solid(win, dim_at(shown), (0, 0, x, sh))
        if x < sw:
            win.copy_area(gc, sl["pix"], 0, 0, sw - x, sh, x, 0)
        return p >= 1

    def end_sheet(sl):
        if sl:
            sl["pix"].free()
            if sl.get("swap"):
                sl["swap"]["pix"].free()

    root = scr.root
    focus_atom, cardinal = d.intern_atom("STEAM_INPUT_FOCUS"), Xatom.CARDINAL
    blur = {k: d.intern_atom(k) for k in ("GAMESCOPE_BLUR_MODE", "GAMESCOPE_BLUR_RADIUS", "GAMESCOPE_BLUR_FADE_DURATION")}

    def over_game(on):
        """While the menu is up, gamescope blurs the game behind it (blur
        mode 2 is always, 0 off). The menu never takes the game's focus
        (STEAM_INPUT_FOCUS, as Steam's overlay does): a fullscreen game
        minimizes itself when it loses focus, and nothing under gamescope
        restores it. Found on the first box 2026-10-13: Rocket League
        went black for good, and Minecraft (GLFW) stayed minimized, at
        its 10 frames a second for a minimized window."""
        win.change_property(focus_atom, cardinal, 32, [0])
        root.change_property(blur["GAMESCOPE_BLUR_RADIUS"], cardinal, 32, [BLUR_RADIUS])
        root.change_property(blur["GAMESCOPE_BLUR_FADE_DURATION"], cardinal, 32, [BLUR_FADE_MS])
        root.change_property(blur["GAMESCOPE_BLUR_MODE"], cardinal, 32, [2 if on else 0])
        d.flush()

    over_game(False)   # a daemon that died with the menu up left them on

    path = sock_path()
    srv = listen(path, 0o600)
    if srv is None:
        print("famidrive-toast: a toast daemon is already running in this session", file=sys.stderr)
        return
    servers, mine = [srv], [(path, os.stat(path).st_ino)]
    if SHARED.is_dir() and os.access(SHARED, os.W_OK) and not os.environ.get("FAMIDRIVE_TOAST_NO_SHARED"):
        shared = SHARED / f"{player}.sock"
        try:
            pub = listen(shared, 0o660)   # the folder's group (famidrive) can send
            if pub:
                servers.append(pub)
                mine.append((shared, os.stat(shared).st_ino))
        except OSError as e:
            print(f"famidrive-toast: no shared socket ({e})", file=sys.stderr)
    import atexit
    import signal
    atexit.register(release, mine)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # the session ending: clean up too
    import threading
    threading.Thread(target=serve_notifications, daemon=True).start()
    threading.Thread(target=watch_controllers, daemon=True).start()
    xfd = d.fileno()
    snapshots = os.environ.get("FAMIDRIVE_TOAST_SNAPSHOT")
    drawn = None   # (x, y, w, h) of the stack on screen now
    menu_drawn = None   # what the menu showed when last drawn, while it's up
    sheet = None        # the menu's panel on the X server, and its slide in
    last = None    # what was drawn, to skip redrawing a still stack
    colors, rendered, ys = {}, {}, {}   # per toast: its scheme, its last render, its animated y
    countdown = None   # when a recording starts, while the countdown is up
    count_drawn = None   # (number, rect) of the countdown on screen now
    gap = int(16 * u)
    while True:
        now = time.monotonic()
        # Also while something is still drawn: the last toasts to go are
        # cleared on the pass after they expire. Waiting for the next
        # event first left them on screen until another toast came, for
        # good in a game (first box, 2026-10-09).
        # While the menu is up, toasts wait (the queue isn't ticked) and
        # show once it's closed; the menu redraws for the clock and
        # batteries every second.
        busy = menu.open or sheet is not None or countdown is not None or bool(queue.tick(now)) or drawn is not None
        moving = sheet and (sheet["phase"] != "still" or sheet["swap"])
        wait = 1 / 60 if moving else 1.0 if menu.open else 1 / 30 if busy else None
        if menu.open and wait == 1.0 and "Stop recording" in menu.items:
            # On the half second, so the dot beside Stop pulses evenly.
            since = recording_since()
            if since is not None:
                wait = 0.5 - (time.time() - since) % 0.5 + 0.01
        ready, _, _ = select.select([*servers, xfd], [], [], wait)
        for server in (x for x in servers if x in ready):
            conn, _ = server.accept()
            with conn:
                conn.settimeout(1)
                buf = b""
                try:
                    while chunk := conn.recv(65536):
                        buf += chunk
                except OSError:
                    pass
                for line in buf.splitlines():
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    if "menu" not in msg:
                        # The menu lists the controllers already: no toast
                        # for one coming or going under it, to show later.
                        if not (menu.open and msg.get("icon") == "controller"):
                            queue.add(msg, time.monotonic())
                    elif server is srv:   # the session's own socket only, not the shared one
                        if msg["menu"] == "open":
                            countdown = None   # the menu opened over it: the recording isn't started
                        reply = menu.command(msg["menu"], in_game(), pausable(), game_mode(), recording())
                        if reply.get("do") == "record":
                            # Once the menu has slid away and the blur faded.
                            countdown = time.monotonic() + SLIDE_SECONDS + COUNTDOWN
                        elif reply.get("do") == "stop-recording":
                            record("stop")
                        try:
                            conn.sendall(json.dumps(reply).encode() + b"\n")
                        except OSError:
                            pass
        if xfd in ready:
            while d.pending_events():
                d.next_event()   # also notices when gamescope has gone
        if menu.open and sheet and sheet["phase"] == "out":   # opened again while leaving
            end_sheet(sheet)
            sheet = None
            menu_drawn = None
        if menu.open:
            if menu_drawn is None:   # just opened
                over_game(True)
                sheet = open_menu()
                menu_drawn = sheet["key"]
            if sheet["phase"] == "in" and slide_step(sheet):
                sheet["phase"] = "still"
            if sheet["phase"] == "still":   # changes made while it slid in show once it's settled
                if sheet["swap"]:
                    swap_step(sheet)
                else:
                    menu_drawn = draw_menu(sheet, menu_drawn)
            d.flush()
            continue
        if sheet and sheet["phase"] != "out":   # just closed: slide it back out
            over_game(False)   # the game gets its focus back now, and the blur fades
            if sheet["swap"]:
                sheet["swap"]["pix"].free()
                sheet["swap"] = None
            sheet["phase"], sheet["t0"] = "out", time.monotonic()
        if sheet:
            if not slide_step(sheet):
                d.flush()
                continue
            end_sheet(sheet)
            sheet = None
            clear((0, 0, sw, sh))
            menu_drawn = drawn = last = None
        if count_drawn and countdown is None:   # cancelled: the menu was opened over it
            clear(count_drawn[1])
            count_drawn = None
        if countdown is not None:
            # Toasts wait under the countdown, as they do under the menu.
            left = countdown - time.monotonic()
            if left > 0:
                n = min(COUNTDOWN, int(left) + 1)
                if not count_drawn or count_drawn[0] != n:
                    clear(drawn)
                    drawn = last = None
                    surf = render_count(n, theme_colors(theme, color_scheme(Path.home())))
                    pos = ((sw - surf.get_width()) // 2, (sh - surf.get_height()) // 2)
                    put(surf, pos)
                    count_drawn = (n, (*pos, *surf.get_size()))
                d.flush()
                continue
            # Cleared and on the TV before the first frame is captured.
            if count_drawn:
                clear(count_drawn[1])
            d.flush()
            d.sync()
            countdown = count_drawn = None
            record("start")
        shown = queue.tick(time.monotonic())
        live = {id(t) for t, _, _ in shown}
        for cache in (colors, rendered, ys):
            for k in [k for k in cache if k not in live]:
                del cache[k]
        if not shown:
            clear(drawn)
            drawn = last = None
            d.flush()
            continue
        surfs, moving = [], False
        for toast, age, left in shown:
            k = id(toast)
            if k not in colors:   # the player's scheme, read once per toast
                colors[k] = theme_colors(theme, color_scheme(Path.home()))
            alpha = int(255 * max(0.0, min(age / FADE, 1.0, (left / FADE) if left is not None else 1.0)))
            sig = (json.dumps(toast, sort_keys=True), alpha)
            indeterminate = toast["kind"] == "progress" and toast.get("progress") is None and not toast.get("done")
            moving = moving or indeterminate
            if indeterminate or rendered.get(k, (None,))[0] != sig:
                rendered[k] = (sig, render(toast, alpha, colors[k]))
            surfs.append((toast, rendered[k][1]))
        sizes = [(sf.get_width() - 2 * spread, sf.get_height() - 2 * spread) for _, sf in surfs]
        spots = []
        for (toast, sf), (tx, ty) in zip(surfs, layout(me["position"], (sw, sh), sizes, margin, gap)):
            y = ys.get(id(toast), ty)
            if abs(ty - y) > 1:   # glide to its new place in the stack
                y += (ty - y) * 0.3
                moving = True
            else:
                y = ty
            ys[id(toast)] = y
            spots.append((tx - spread, int(y) - spread))
        key = (tuple(rendered[id(t)][0] for t, _ in surfs), tuple(spots))
        if key == last and not moving:
            continue
        last = key
        # One canvas over everything the stack covers now and covered
        # before, so leftovers are cleared in the same put.
        rects = [(x, y, sf.get_width(), sf.get_height()) for (x, y), (_, sf) in zip(spots, surfs)]
        now_box = (min(r[0] for r in rects), min(r[1] for r in rects),
                   max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects))
        box = now_box if not drawn else (min(now_box[0], drawn[0]), min(now_box[1], drawn[1]),
                                         max(now_box[2], drawn[0] + drawn[2]), max(now_box[3], drawn[1] + drawn[3]))
        box = (max(0, box[0]), max(0, box[1]), min(sw, box[2]), min(sh, box[3]))
        canvas = pygame.Surface((box[2] - box[0], box[3] - box[1]), pygame.SRCALPHA, 32)
        for (x, y), (_, sf) in zip(spots, surfs):
            canvas.blit(sf, (x - box[0], y - box[1]))
        put(canvas, box[:2])
        drawn = (now_box[0], now_box[1], now_box[2] - now_box[0], now_box[3] - now_box[1])
        if snapshots and not moving and all(sig[1] == 255 for sig, _ in (rendered[id(t)] for t, _ in surfs)):
            pygame.image.save(canvas, str(Path(snapshots) / f"{int(time.time() * 1000)}.png"))
        d.flush()


def wrap(text, f, width):
    lines, line = [], ""
    for word in (text or "").split():
        test = f"{line} {word}".strip()
        if f.size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def ellipsize(text, f, width):
    if f.size(text)[0] <= width:
        return text
    while text and f.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…"


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        daemon(sys.argv[2], sys.argv[3])
    else:
        send(parse_send(sys.argv[1:]))


if __name__ == "__main__":
    main()
