"""famidrive-picker SPEC_JSON

"Who's playing?": the screen a box with more than one player starts on.
It runs as greetd's greeter, inside a gamescope of its own, and is the
whole login: pick a player and greetd starts their session (the same
FamiDrive session a one-player box autologins into). Settings → Switch
Player in ES-DE ends a session, and greetd brings this back.

SPEC_JSON (session.nix): {"players": [{"user", "displayName",
"isGuest"}], "session": [command...], "last": file remembering who
played last, "theme": the ES-DE theme's folder or null}.

Left and right (D-pad, stick or arrow keys) to choose, A, Start or Enter
to play. It draws in ES-DE's look, in the theme's own fonts, like
famidrive-status.
"""

import json
import os
import re
import socket
import struct
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "x11")   # gamescope's Xwayland
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402
from pygame._sdl2 import controller  # noqa: E402

WHITE = (255, 255, 255)
DIM = (153, 153, 153)        # the theme's help text
PANEL = (17, 17, 17, 230)    # its help bar
ERROR = (255, 140, 120)
# One color per player, in order; the guest is grey.
COLORS = [(214, 92, 120), (84, 140, 214), (96, 176, 120), (226, 160, 72),
          (150, 110, 210), (72, 178, 184), (210, 120, 72), (170, 170, 90)]
GUEST = (110, 110, 110)
STICK = 16000                # how far the stick goes before it counts


def log(msg):
    print(f"famidrive-picker: {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- greetd
#
# greetd's IPC: each message is a 32-bit length (native byte order) and
# then that much JSON, over the socket in $GREETD_SOCK.

class Greetd:
    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(os.environ["GREETD_SOCK"])

    def ask(self, msg):
        data = json.dumps(msg).encode()
        self.sock.sendall(struct.pack("=I", len(data)) + data)
        size = struct.unpack("=I", self._read(4))[0]
        return json.loads(self._read(size))

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("greetd closed the connection")
            buf += chunk
        return buf


def start(user, session):
    """Log `user` in and hand greetd their session. Returns an error
    message, or None once greetd has it (then this should exit)."""
    if "GREETD_SOCK" not in os.environ:
        log(f"not under greetd; would start {session} as {user}")
        return None
    g = Greetd()
    reply = g.ask({"type": "create_session", "username": user})
    # Players need no password (session.nix's PAM rule). Anything that
    # still asks for one can't be answered from a controller.
    while reply["type"] == "auth_message":
        if reply.get("auth_message_type") in ("info", "error"):
            log(f"PAM: {reply.get('auth_message')}")
            reply = g.ask({"type": "post_auth_message_response"})
        else:
            g.ask({"type": "cancel_session"})
            return "This player needs a password, which can't be typed here."
    if reply["type"] != "success":
        g.ask({"type": "cancel_session"})
        return reply.get("description") or "greetd couldn't log in."
    reply = g.ask({"type": "start_session", "cmd": session, "env": []})
    if reply["type"] != "success":
        g.ask({"type": "cancel_session"})
        return reply.get("description") or "greetd couldn't start the session."
    return None


# ---------------------------------------------------------------- drawing

def theme_fonts(theme):
    """(regular, light) font files the theme uses for game names and for
    descriptions. Art Book Next names them in theme.xml's <variables> as
    fontRegular and fontLight; other themes fall back to ES-DE's default."""
    if not theme:
        return None, None
    try:
        text = (Path(theme) / "theme.xml").read_text(errors="replace")
    except OSError:
        return None, None
    names = dict(re.findall(r"<(font\w+)>([^<]+)</font\w+>", text))
    regular = names.get("fontRegular")
    light = names.get("fontLight", regular)
    return (Path(theme) / regular if regular else None), (Path(theme) / light if light else None)


def font(path, size):
    try:
        if path:
            return pygame.font.Font(str(path), size)
    except (FileNotFoundError, OSError):
        pass
    return pygame.font.Font(None, int(size * 1.3))


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    players = spec["players"]
    last = read(spec["last"])
    selected = next((i for i, p in enumerate(players) if p["user"] == last), 0)

    pygame.init()
    controller.init()
    display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    # A plain 32-bit canvas, copied to the display: with HDR on,
    # gamescope's surface is 10 bits per channel, and anti-aliased text
    # drawn straight onto it comes out as solid blocks (famidrive-status).
    screen = pygame.Surface(display.get_size(), 0, 32)
    pygame.display.set_caption("FamiDrive")
    pygame.mouse.set_visible(False)
    w, h = display.get_size()
    u = h / 1080   # layout unit: sizes below are for 1080p

    regular, light = theme_fonts(spec.get("theme"))
    title_f = font(regular, int(64 * u))
    initial_f = font(regular, int(110 * u))
    name_f = font(regular, int(40 * u))
    body_f = font(light, int(28 * u))
    help_f = font(regular, int(24 * u))

    background = pygame.Surface((w, h), 0, 32)
    for y in range(h):   # a dark vertical gradient
        c = int(28 - 20 * y / h)
        pygame.draw.line(background, (c, c, c + 4), (0, y), (w, y))

    pads = {}
    stick_held = False
    error = ""
    busy = False

    def choose():
        nonlocal error, busy
        p = players[selected]
        busy, error = True, ""
        draw()
        err = start(p["user"], spec["session"])
        if err is None:
            try:
                Path(spec["last"]).write_text(p["user"])
            except OSError:
                pass
            sys.exit(0)
        log(err)
        busy, error = False, err

    def move(step):
        nonlocal selected, error
        selected = (selected + step) % len(players)
        error = ""

    def draw():
        screen.blit(background, (0, 0))
        title = title_f.render("Who's playing?", True, WHITE)
        screen.blit(title, ((w - title.get_width()) // 2, int(h * 0.20)))

        size = int(220 * u)
        gap = int(90 * u)
        n = len(players)
        # Smaller circles if there are more players than fit.
        if n * size + (n - 1) * gap > w - int(200 * u):
            size = int((w - int(200 * u) - (n - 1) * gap) / n)
        row = n * size + (n - 1) * gap
        x = (w - row) // 2
        cy = int(h * 0.48)
        for i, p in enumerate(players):
            cx = x + size // 2
            r = size // 2
            on = i == selected
            if on:
                r = int(r * 1.08)
                pygame.draw.circle(screen, WHITE, (cx, cy), r + int(10 * u))
                pygame.draw.circle(screen, (16, 16, 18), (cx, cy), r + int(4 * u))
            color = GUEST if p["isGuest"] else COLORS[i % len(COLORS)]
            if not on:
                color = tuple(int(c * 0.6) for c in color)
            pygame.draw.circle(screen, color, (cx, cy), r)
            letter = initial_f.render(p["displayName"][:1].upper(), True, WHITE)
            screen.blit(letter, (cx - letter.get_width() // 2, cy - letter.get_height() // 2))
            name = name_f.render(p["displayName"], True, WHITE if on else DIM)
            screen.blit(name, (cx - name.get_width() // 2, cy + size // 2 + int(40 * u)))
            x += size + gap

        line = "Starting…" if busy else error
        if line:
            msg = body_f.render(line, True, ERROR if error and not busy else DIM)
            screen.blit(msg, ((w - msg.get_width()) // 2, int(h * 0.76)))

        # ES-DE's help bar, bottom right.
        hint = help_f.render("A   PLAY", True, DIM)
        bar = pygame.Surface((hint.get_width() + int(48 * u), hint.get_height() + int(24 * u)), pygame.SRCALPHA)
        bar.fill(PANEL)
        bar.blit(hint, (int(24 * u), int(12 * u)))
        screen.blit(bar, (w - bar.get_width() - int(40 * u), h - bar.get_height() - int(40 * u)))

        display.blit(screen, (0, 0))
        pygame.display.flip()

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if busy:
                continue
            if event.type == pygame.CONTROLLERDEVICEADDED:
                try:
                    pads[event.device_index] = controller.Controller(event.device_index)
                except pygame.error as e:
                    log(f"controller {event.device_index}: {e}")
            elif event.type == pygame.CONTROLLERBUTTONDOWN:
                if event.button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
                    move(-1)
                elif event.button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
                    move(1)
                elif event.button in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START):
                    choose()
            elif event.type == pygame.CONTROLLERAXISMOTION and event.axis == pygame.CONTROLLER_AXIS_LEFTX:
                if abs(event.value) < STICK // 2:
                    stick_held = False
                elif abs(event.value) > STICK and not stick_held:
                    stick_held = True
                    move(1 if event.value > 0 else -1)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    move(-1)
                elif event.key == pygame.K_RIGHT:
                    move(1)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    choose()
        draw()
        clock.tick(30)


if __name__ == "__main__":
    main()
