"""famidrive-quit: which buttons are Select and Start, no devices.

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
"""


class Combo(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(DB)
        self.db = m.load_paddb(f.name)

    def test_reads_ids_from_the_guid(self):
        self.assertEqual(self.db[(0x1532, 0x1007)], {"Windows": (8, 9)})
        self.assertEqual(self.db[(0x0079, 0x0011)], {"Linux": (8, 9), "Windows": (4, 5)})
        self.assertNotIn((0xaaaa, 0xbbbb), self.db)   # start isn't a button

    def test_generic_pad_uses_the_database(self):
        # Share and Options, not the stick clicks that are "SELECT"/"START".
        self.assertEqual(m.combo_for(RAIJU, 0x1532, 0x1007, "hid-generic", self.db), {0x138, 0x139})

    def test_linux_entry_comes_first(self):
        keys = list(range(0x120, 0x12c))   # a joystick: BTN_TRIGGER up
        self.assertEqual(m.combo_for(keys, 0x0079, 0x0011, "hid-generic", self.db), {0x128, 0x129})

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


if __name__ == "__main__":
    unittest.main()
