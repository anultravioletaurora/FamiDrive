"""famidrive-padmouse: the controller as a mouse and keyboard, while it runs.

gamescope-fg runs this while Steam waits on a prompt over a launch (a
game's EULA, a cloud save conflict, a CD key). Those are Steam client
windows, made for a mouse: no controller navigation, and no keyboard focus
to Tab through. Found on the first box 2026-10-07: GTA V Enhanced's EULA
could only be accepted with a mouse.

While it runs, every connected pad also drives a virtual mouse and
keyboard (uinput). The pads aren't grabbed: the quit combo, Steam and the
game still see them.

    left stick      the pointer (slow near the middle, fast at the edge)
    right stick     scroll
    A               click        B   Esc
    X               Tab          Y   Space
    L1 / R1         Shift+Tab / Tab (between a dialog's buttons)
    d-pad           arrow keys
    Start           Enter, on release, unless Select is held (Select +
                    Start is the quit combo, not "OK")

It stops on SIGTERM, when gamescope-fg sees the prompt answered.
"""

import select
import signal
import sys
import time

TICK = 1 / 120         # pointer updates per second
SPEED = 2600.0         # pixels per second at full tilt
DEADZONE = 0.18
SCROLL_EVERY = 0.09    # seconds between wheel clicks at full tilt


def curve(v, dz=DEADZONE):
    """A stick's -1..1 as -1..1 movement: nothing in the dead zone, then
    squared, for fine control near the middle."""
    a = abs(v)
    if a <= dz:
        return 0.0
    m = ((a - dz) / (1 - dz)) ** 2
    return m if v > 0 else -m


def norm(value, info):
    """An axis' raw value as -1..1 around its middle."""
    mid = (info.max + info.min) / 2
    half = (info.max - info.min) / 2 or 1
    return max(-1.0, min(1.0, (value - mid) / half))


def is_pad(dev, ecodes):
    caps = dev.capabilities()
    return ecodes.BTN_SOUTH in caps.get(ecodes.EV_KEY, []) and ecodes.EV_ABS in caps


def main():
    import evdev
    from evdev import ecodes as e

    # Pad button -> (keys pressed together). Click is BTN_LEFT.
    buttons = {
        e.BTN_SOUTH: (e.BTN_LEFT,),
        e.BTN_EAST: (e.KEY_ESC,),
        e.BTN_WEST: (e.KEY_TAB,),
        e.BTN_NORTH: (e.KEY_SPACE,),
        e.BTN_TR: (e.KEY_TAB,),
        e.BTN_TL: (e.KEY_LEFTSHIFT, e.KEY_TAB),
        e.BTN_DPAD_UP: (e.KEY_UP,), e.BTN_DPAD_DOWN: (e.KEY_DOWN,),
        e.BTN_DPAD_LEFT: (e.KEY_LEFT,), e.BTN_DPAD_RIGHT: (e.KEY_RIGHT,),
    }
    hats = {(e.ABS_HAT0X, -1): e.KEY_LEFT, (e.ABS_HAT0X, 1): e.KEY_RIGHT,
            (e.ABS_HAT0Y, -1): e.KEY_UP, (e.ABS_HAT0Y, 1): e.KEY_DOWN}
    keys = {k for ks in buttons.values() for k in ks} | set(hats.values()) | {e.KEY_ENTER, e.BTN_RIGHT}
    ui = evdev.UInput({e.EV_KEY: sorted(keys), e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]},
                      name="FamiDrive pad pointer")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    pads, sticks, held, hat_held = {}, {}, set(), {}
    acc = [0.0, 0.0]
    last_scroll = 0.0
    next_scan = 0.0

    def scan():
        for path in evdev.list_devices():
            if path in pads:
                continue
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            if dev.name == "FamiDrive pad pointer" or not is_pad(dev, e):
                dev.close()
                continue
            pads[path] = dev
            sticks[path] = {"x": 0.0, "y": 0.0, "rx": 0.0, "ry": 0.0,
                            "info": {c: i for c, i in dev.capabilities(absinfo=True).get(e.EV_ABS, [])}}

    def tap(codes, down):
        for c in codes if down else reversed(codes):
            ui.write(e.EV_KEY, c, 1 if down else 0)
        ui.syn()

    try:
        last = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= next_scan:
                scan()
                next_scan = now + 2
            ready, _, _ = select.select(list(pads.values()), [], [], TICK)
            for dev in ready:
                try:
                    events = list(dev.read())
                except OSError:   # unplugged
                    pads.pop(dev.path, None)
                    sticks.pop(dev.path, None)
                    continue
                st = sticks[dev.path]
                for ev in events:
                    if ev.type == e.EV_KEY:
                        if ev.code in (e.BTN_SELECT, e.BTN_START):
                            if ev.value:
                                held.add(ev.code)
                            else:
                                if ev.code == e.BTN_START and e.BTN_SELECT not in held:
                                    tap((e.KEY_ENTER,), True)
                                    tap((e.KEY_ENTER,), False)
                                held.discard(ev.code)
                        elif ev.code in buttons and ev.value in (0, 1):
                            tap(buttons[ev.code], ev.value == 1)
                    elif ev.type == e.EV_ABS:
                        info = st["info"].get(ev.code)
                        if ev.code in (e.ABS_HAT0X, e.ABS_HAT0Y):
                            prev = hat_held.pop((dev.path, ev.code), None)
                            if prev:
                                tap((prev,), False)
                            key = hats.get((ev.code, ev.value))
                            if key:
                                hat_held[(dev.path, ev.code)] = key
                                tap((key,), True)
                        elif info is not None:
                            name = {e.ABS_X: "x", e.ABS_Y: "y", e.ABS_RX: "rx", e.ABS_RY: "ry"}.get(ev.code)
                            if name:
                                st[name] = norm(ev.value, info)
            dt, last = now - last, now
            dx = sum(curve(s["x"]) for s in sticks.values())
            dy = sum(curve(s["y"]) for s in sticks.values())
            acc[0] += dx * SPEED * dt
            acc[1] += dy * SPEED * dt
            mx, my = int(acc[0]), int(acc[1])
            if mx or my:
                acc[0] -= mx
                acc[1] -= my
                ui.write(e.EV_REL, e.REL_X, mx)
                ui.write(e.EV_REL, e.REL_Y, my)
                ui.syn()
            sy = sum(curve(s["ry"]) for s in sticks.values())
            if sy and now - last_scroll >= SCROLL_EVERY / max(abs(sy), 0.2):
                ui.write(e.EV_REL, e.REL_WHEEL, -1 if sy > 0 else 1)
                ui.syn()
                last_scroll = now
    finally:
        ui.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(__doc__)
    try:
        main()
    except OSError as err:   # no /dev/uinput access, say: the prompt is then mouse-only, as before
        print(f"famidrive-padmouse: {err}", file=sys.stderr)
