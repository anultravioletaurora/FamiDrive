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

SPEC (JSON, from Nix): {"theme": theme folder or null, "players":
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
# when the image can't be read, the kind's own.
ICONS = ("save", "warning", "trophy", "download", "info", "controller", "check")
KIND_ICON = {"notice": "info", "alert": "warning", "progress": "download", "achievement": "trophy",
             "success": "check"}
ICONS = ("save", "warning", "trophy", "download", "info", "controller")
KIND_ICON = {"notice": "info", "alert": "warning", "progress": "download", "achievement": "trophy"}
ALERT = (230, 160, 40, 255)
SUCCESS = (76, 187, 106, 255)
GOLD = (232, 184, 64, 255)
SECONDS = {"notice": 4.0, "alert": 7.0, "achievement": 6.0, "progress": 2.0, "success": 5.0}
STALE_PROGRESS = 120.0   # a progress toast nobody updates is let go
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


# --- The queue ----------------------------------------------------------------

class Queue:
    """Toasts waiting and showing, one at a time. Pure: the clock is passed in."""

    def __init__(self, hide=()):
        self.hide = set(hide)
        self.waiting = []
        self.current = None    # the toast on screen
        self.shown_at = None
        self.ends_at = None

    def add(self, toast, now):
        kind = toast.get("kind", "notice")
        if kind not in KINDS:
            kind = toast["kind"] = "notice"
        if kind in self.hide:
            return False
        toast["updated"] = now
        tid = toast.get("id")
        if tid:
            if self.current and self.current.get("id") == tid:
                self.current.update(toast)
                # An unfinished progress toast stays; anything else (done,
                # or turned into a success or alert) gets its own time.
                self.ends_at = self._end(self.current, now)
                return True
            for i, t in enumerate(self.waiting):
                if t.get("id") == tid:
                    self.waiting[i] = toast
                    return True
        self.waiting.append(toast)
        return True

    def _end(self, toast, now):
        if toast.get("kind") == "progress" and not toast.get("done"):
            return None   # until it's done
        return now + float(toast.get("seconds") or SECONDS[toast["kind"]])

    def tick(self, now):
        """Advance; returns (toast or None, its age in seconds, seconds left or None)."""
        if self.current:
            stale = (self.ends_at is None and now - self.current["updated"] > STALE_PROGRESS)
            if stale or (self.ends_at is not None and now >= self.ends_at):
                self.current = None
        if not self.current and self.waiting:
            self.current = self.waiting.pop(0)
            self.shown_at = now
            self.ends_at = self._end(self.current, now)
        if not self.current:
            return None, 0.0, None
        left = None if self.ends_at is None else self.ends_at - now
        return self.current, now - self.shown_at, left


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
    """{device path: name} for each joystick the kernel has (jsN)."""
    pads = {}
    for js in sorted((sys_class / "input").glob("js*")):
        try:
            dev = os.path.realpath(js / "device")
            pads[dev] = (Path(dev) / "name").read_text().strip() or "Controller"
        except OSError:
            continue
    return pads


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


def in_game():
    """Whether a game is running in this session (gamescope-fg's marker)."""
    return (sock_path().parent / "famidrive-game.pgid").exists()


def pad_changes(before, after, playing):
    """The toasts for pads that came and went between two scans."""
    toasts = []
    for dev, name in sorted(after.items()):
        if dev not in before:
            toasts.append({"kind": "notice", "icon": "controller", "title": "Controller connected", "detail": name})
    for dev, name in sorted(before.items()):
        if dev not in after:
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
        for t in pad_changes(before, after, in_game()) + battery_changes(warned, pad_batteries()):
            send(t)
        before = after


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
            pygame.draw.lines(c, clear, False, [(n * .29, n * .51), (n * .44, n * .66), (n * .72, n * .37)], max(4, n // 9))
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
        icon = toast.get("icon") or ""
        if icon and icon not in ICONS:
            img = image_icon(icon, size)
            if img:
                return img
            icon = ""
        name = icon or KIND_ICON.get(toast["kind"], "info")
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
        pygame.draw.rect(surf, colors["panel"], surf.get_rect(), border_radius=radius)
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

    def put(surf, pos):
        """Copy an RGBA surface into the window, premultiplied, as BGRA rows
        in chunks the X server takes in one request each."""
        s = surf.premul_alpha()
        data = pygame.image.tobytes(s, "BGRA")
        w, h = s.get_size()
        rows = max(1, 200_000 // (w * 4))
        for top in range(0, h, rows):
            n = min(rows, h - top)
            win.put_image(gc, pos[0], pos[1] + top, w, n, X.ZPixmap, 32, 0,
                          data[top * w * 4:(top + n) * w * 4])

    def clear(rect):
        if rect:
            put(pygame.Surface(rect[2:], pygame.SRCALPHA, 32), rect[:2])

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
    drawn = None   # (x, y, w, h) on screen now
    last = None    # what was drawn there, to skip redrawing a still toast
    colors, colors_for = None, None
    while True:
        now = time.monotonic()
        toast, age, left = queue.tick(now)
        busy = toast is not None
        ready, _, _ = select.select([*servers, xfd], [], [], 1 / 30 if busy else None)
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
                    queue.add(json.loads(line), time.monotonic())
                except ValueError:
                    pass
        if xfd in ready:
            while d.pending_events():
                d.next_event()   # also notices when gamescope has gone
        toast, age, left = queue.tick(time.monotonic())
        if toast is None:
            clear(drawn)
            drawn = last = None
            d.flush()
            continue
        if colors_for is not toast:   # the player's scheme, read once per toast
            colors, colors_for = theme_colors(theme, color_scheme(Path.home())), toast
        alpha = int(255 * max(0.0, min(age / FADE, 1.0, (left / FADE) if left is not None else 1.0)))
        moving = toast["kind"] == "progress" and toast.get("progress") is None and not toast.get("done")
        key = (json.dumps(toast, sort_keys=True), alpha)
        if key == last and not moving:
            continue
        last = key
        surf = render(toast, alpha, colors)
        px, py = place(me["position"], (sw, sh), (surf.get_width() - 2 * spread, surf.get_height() - 2 * spread), margin)
        pos = (px - spread, py - spread)
        rect = (*pos, *surf.get_size())
        if drawn and drawn != rect:
            clear(drawn)
        put(surf, pos)
        drawn = rect
        if snapshots and alpha == 255:   # FAMIDRIVE_TOAST_SNAPSHOT: each toast as a PNG, for docs and checks
            pygame.image.save(surf, str(Path(snapshots) / f"{int(time.time() * 1000)}.png"))
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
