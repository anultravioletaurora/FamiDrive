"""famidrive-quit: which buttons are Select, Start and Guide, and how
presses become menu commands, no devices.

    python3 quit_test.py path/to/famidrive_quit.py
"""

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

# evdev isn't needed for these: a stand-in with the two codes used.
ecodes = types.SimpleNamespace(BTN_SELECT=0x13a, BTN_START=0x13b, BTN={}, KEY={})
sys.modules["evdev"] = types.SimpleNamespace(ecodes=ecodes)
sys.modules["evdev.ecodes"] = ecodes

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_quit", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# The Raiju Tournament Edition (1532:1007) under hid-generic: 14 buttons,
# BTN_SOUTH (0x130) up in HID order. SDL_GameControllerDB has a Windows
# entry for it, with back and start as buttons 8 and 9.
RAIJU = list(range(0x130, 0x13e))
DB = """# a comment
03000000321500000710000000000000,Razer Raiju TE,a:b1,b:b2,back:b8,start:b9,x:b0,y:b3,platform:Windows,
03000000790000001100000010010000,Retro NES pad,a:b1,b:b2,back:b8,start:b9,platform:Linux,
03000000790000001100000000000000,Retro NES pad,a:b2,b:b1,back:b4,start:b5,platform:Windows,
030000005e0400008e02000014010000,Xbox 360,a:b0,back:b6,start:b7,platform:Linux,
03000000aaaa0000bbbb000000000000,Axis start,back:b6,start:a2,platform:Linux,
050000004c69632050726f20436f6e00,Nintendo Switch Controller,a:b0,b:b1,back:b8,start:b9,x:b2,y:b3,platform:Linux,
"""
# A PowerA GameCube-style controller for the Switch over Bluetooth: no USB
# ids, 16 buttons from BTN_SOUTH, - and + the 9th and 10th (Switch order).
POWERA = list(range(0x130, 0x140))


class Combo(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(DB)
        self.db = m.load_paddb(f.name)

    def test_reads_ids_from_the_guid(self):
        self.assertEqual(self.db[(0x1532, 0x1007)], {"Windows": {"a": 1, "b": 2, "back": 8, "start": 9}})
        self.assertEqual({k: (v["back"], v["start"]) for k, v in self.db[(0x0079, 0x0011)].items()},
                         {"Linux": (8, 9), "Windows": (4, 5)})
        self.assertNotIn((0xaaaa, 0xbbbb), self.db)   # start isn't a button

    def test_generic_pad_uses_the_database(self):
        # Share and Options, not the stick clicks that are "SELECT"/"START".
        self.assertEqual(m.combo_for(RAIJU, 0x1532, 0x1007, "hid-generic", self.db), {0x138, 0x139})

    def test_linux_entry_comes_first(self):
        keys = list(range(0x120, 0x12c))   # a joystick: BTN_TRIGGER up
        self.assertEqual(m.combo_for(keys, 0x0079, 0x0011, "hid-generic", self.db), {0x128, 0x129})

    def test_pad_without_ids_found_by_name(self):
        self.assertEqual(m.name_key("Lic Pro Controller"), ("name", "4c69632050726f20436f6e00"))
        self.assertEqual(self.db[m.name_key("Lic Pro Controller")]["Linux"]["back"], 8)
        self.assertEqual(m.combo_for(POWERA, 0, 0, "hid-generic", self.db, "Lic Pro Controller"), {0x138, 0x139})
        # Another pad without ids isn't taken for it.
        self.assertEqual(m.combo_for(POWERA, 0, 0, "hid-generic", self.db, "Some Pad"), {0x13a, 0x13b})

    def test_own_driver_keeps_its_names(self):
        keys = [0x130, 0x131, 0x133, 0x134, 0x136, 0x137, 0x13a, 0x13b, 0x13c, 0x13d, 0x13e]
        self.assertEqual(m.combo_for(keys, 0x045e, 0x028e, "xpad", self.db), {0x13a, 0x13b})

    def test_unknown_generic_pad_falls_back(self):
        self.assertEqual(m.combo_for(RAIJU, 0x1234, 0x5678, "hid-generic", self.db), {0x13a, 0x13b})
        self.assertIsNone(m.combo_for([0x110, 0x111], 0x1234, 0x5678, "hid-generic", self.db))

    def test_not_a_pad(self):
        self.assertIsNone(m.combo_for([30, 31, 32], 0x046d, 0xc53f, "logitech-djreceiver", self.db))

    def test_sdl_order(self):
        self.assertEqual(m.sdl_buttons([0x13b, 0x100, 0x120, 0x130]), [0x120, 0x130, 0x13b, 0x100])

    def test_missing_database(self):
        self.assertEqual(m.load_paddb("/nonexistent"), {})

    def test_menu_buttons(self):
        xpad = [0x130, 0x131, 0x133, 0x134, 0x13a, 0x13b, 0x13c]
        self.assertEqual(m.menu_buttons(xpad, 0x2dc8, 0x310b, "xpad", self.db),
                         {"guide": 0x13c, "a": 0x130, "b": 0x131, "start": 0x13b, "back": 0x13a})
        # The Raiju's entry has no guide: A, B, Start and Select, by number.
        self.assertEqual(m.menu_buttons(RAIJU, 0x1532, 0x1007, "hid-generic", self.db),
                         {"a": 0x131, "b": 0x132, "start": 0x139, "back": 0x138})
        self.assertEqual(m.menu_buttons(RAIJU, 0x1234, 0x5678, "hid-generic", self.db), {})


XPAD = {"guide": 0x13c, "a": 0x130, "b": 0x131}
STICKS = {m.ABS_X: (-32768, 32767), m.ABS_Y: (-32768, 32767)}


class Nav(unittest.TestCase):
    def test_buttons(self):
        nav = m.PadNav(XPAD, STICKS)
        self.assertEqual(nav.feed(m.EV_KEY, 0x130, 1), "select")
        self.assertIsNone(nav.feed(m.EV_KEY, 0x130, 0))   # letting go does nothing
        self.assertEqual(nav.feed(m.EV_KEY, 0x131, 1), "back")
        self.assertEqual(nav.feed(m.EV_KEY, 0x13c, 1), "close")
        self.assertEqual(nav.feed(m.EV_KEY, 0x221, 1), "down")   # BTN_DPAD_DOWN

    def test_hat(self):
        nav = m.PadNav(XPAD, STICKS)
        self.assertEqual(nav.feed(m.EV_ABS, m.ABS_HAT0Y, -1), "up")
        self.assertIsNone(nav.feed(m.EV_ABS, m.ABS_HAT0Y, 0))
        self.assertEqual(nav.feed(m.EV_ABS, m.ABS_HAT0X, 1), "right")

    def test_stick_moves_once_per_push(self):
        nav = m.PadNav(XPAD, STICKS)
        self.assertIsNone(nav.feed(m.EV_ABS, m.ABS_Y, 12000))          # not far enough
        self.assertEqual(nav.feed(m.EV_ABS, m.ABS_Y, 30000), "down")
        self.assertIsNone(nav.feed(m.EV_ABS, m.ABS_Y, 32767))          # still held
        self.assertIsNone(nav.feed(m.EV_ABS, m.ABS_Y, 5000))           # back near the middle
        self.assertEqual(nav.feed(m.EV_ABS, m.ABS_Y, 31000), "down")
        # A 0..255 stick (hid-generic) is read from its own range.
        nav = m.PadNav({}, {m.ABS_Y: (0, 255)})
        self.assertEqual(nav.feed(m.EV_ABS, m.ABS_Y, 0), "up")


class LetGo(unittest.TestCase):
    def test_held_buttons_and_pushed_axes(self):
        axes = {m.ABS_X: (20000, -32768, 32767), m.ABS_Y: (0, -32768, 32767),
                m.ABS_Z: (200, 0, 255), m.ABS_HAT0X: (-1, -1, 1)}
        self.assertEqual(m.let_go([0x130], axes, "xpad"),
                         [(m.EV_KEY, 0x130, 0), (m.EV_ABS, m.ABS_X, 0), (m.EV_ABS, m.ABS_Z, 0),
                          (m.EV_ABS, m.ABS_HAT0X, 0)])

    def test_generic_pad_z_may_be_a_stick(self):
        self.assertEqual(m.let_go([], {m.ABS_Z: (200, 0, 255)}, "hid-generic"), [(m.EV_ABS, m.ABS_Z, 127)])
        self.assertEqual(m.let_go([], {m.ABS_Z: (127, 0, 255)}, "hid-generic"), [])


class Mode(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(m.parse_mode("freeze\n"), ("freeze", "start"))
        self.assertEqual(m.parse_mode("pause select\n"), ("pause", "select"))
        self.assertEqual(m.parse_mode(""), ("pause", "start"))
        self.assertEqual(m.parse_mode("focus\n"), ("pause", "start"))   # unknown: the safe one

    def test_select_isnt_a_menu_button(self):
        nav = m.PadNav({"start": 0x13b, "back": 0x13a, "a": 0x130}, {})
        self.assertIsNone(nav.feed(m.EV_KEY, 0x13a, 1))
        self.assertEqual(nav.feed(m.EV_KEY, 0x130, 1), "select")


class PressStart(unittest.TestCase):
    def test_presses_and_lets_go(self):
        sent = []
        dev = type("Pad", (), {"name": "Pad", "write": lambda self, *ev: sent.append(ev),
                               "syn": lambda self: sent.append("syn")})()
        m.press(dev, 0x13b, "Start", hold=0)
        self.assertEqual(sent, [(m.EV_KEY, 0x13b, 1), "syn", (m.EV_KEY, 0x13b, 0), "syn"])


class AskMenu(unittest.TestCase):
    def test_reply_and_no_daemon(self):
        import socket
        import threading
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "toast.sock"
            self.assertEqual(m.ask_menu("open", path), {})
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(str(path))
            srv.listen(1)
            got = []

            def serve():
                conn, _ = srv.accept()
                with conn:
                    buf = b""
                    while chunk := conn.recv(4096):
                        buf += chunk
                    got.append(buf)
                    conn.sendall(b'{"open": true}\n')

            threading.Thread(target=serve).start()
            self.assertEqual(m.ask_menu("open", path), {"open": True})
            self.assertEqual(got, [b'{"menu": "open"}\n'])
            srv.close()


if __name__ == "__main__":
    unittest.main()
