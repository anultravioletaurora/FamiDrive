"""famidrive-pads: Dolphin ports and Eden bindings from made-up pads, no SDL.

    python3 pads_test.py path/to/famidrive_pads.py
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_pads", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# SDL binds as famidrive-pads reads them: (type, number, hat mask).
XBOX = {"a": (1, 0, 0), "b": (1, 1, 0), "x": (1, 2, 0), "y": (1, 3, 0), "back": (1, 6, 0), "guide": (1, 8, 0),
        "start": (1, 7, 0), "leftstick": (1, 9, 0), "rightstick": (1, 10, 0), "leftshoulder": (1, 4, 0),
        "rightshoulder": (1, 5, 0), "dpup": (3, 0, 1), "dpdown": (3, 0, 4), "dpleft": (3, 0, 8),
        "dpright": (3, 0, 2), "misc1": (0, 0, 0), "leftx": (2, 0, 0), "lefty": (2, 1, 0),
        "rightx": (2, 3, 0), "righty": (2, 4, 0), "lefttrigger": (2, 2, 0), "righttrigger": (2, 5, 0)}
GUID = "050000005e0400008e02000030110000"


class Dolphin(unittest.TestCase):
    def test_modern_pads_first_then_the_adapter(self):
        pads = [{"device": "SDL/0/Nintendo GameCube Controller", "adapter": True},
                {"device": "SDL/1/Nintendo GameCube Controller", "adapter": True},
                {"device": "SDL/0/Xbox 360 Controller", "adapter": False}]
        self.assertEqual(m.dolphin_devices(["gamepad", "8bitdo-ultimate-2", "gamepad", "gamepad"], pads),
                         {0: "SDL/0/Xbox 360 Controller", 2: "SDL/0/Nintendo GameCube Controller",
                          3: "SDL/1/Nintendo GameCube Controller"})
        self.assertEqual(m.dolphin_devices(["gamepad"], []), {})

    def test_ini_keeps_spaces_and_other_keys(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "GCPadNew.ini"
            f.write_text("[GCPad1]\nButtons/A = `Button S`\n[GCPad2]\nDevice = SDL/0/Old\n")
            m.set_ini(f, "GCPad1", {"Device": "SDL/0/Xbox 360 Controller"})
            m.set_ini(f, "GCPad2", {"Device": "SDL/0/New"})
            self.assertEqual(f.read_text(), "[GCPad1]\nButtons/A = `Button S`\nDevice = SDL/0/Xbox 360 Controller\n"
                             "[GCPad2]\nDevice = SDL/0/New\n")


class Eden(unittest.TestCase):
    def keys(self, face="labels", n=1):
        return m.eden_keys([{"guid": GUID, "port": i, "binds": XBOX, "adapter": False} for i in range(n)], face)

    def test_bindings_in_edens_format(self):
        k = self.keys()
        head = f"engine:sdl,port:0,guid:{GUID},"
        self.assertEqual(k["player_0_button_a"], f'"{head}button:0"')
        self.assertEqual(k["player_0_button_a\\default"], "false")
        self.assertEqual(k["player_0_button_zl"], f'"{head}axis:2,threshold:0.500000,invert:+"')
        self.assertEqual(k["player_0_button_dleft"], f'"{head}hat:0,direction:left"')
        self.assertEqual(k["player_0_button_home"], f'"{head}button:8"')
        self.assertEqual(k["player_0_button_screenshot"], "[empty]")
        self.assertIn("axis_x:3,axis_y:4", k["player_0_rstick"])
        self.assertEqual(k["player_0_connected"], "true")

    def test_face_buttons_by_position(self):
        k = self.keys("positions")
        self.assertTrue(k["player_0_button_a"].endswith('button:1"'))   # the right-hand button
        self.assertTrue(k["player_0_button_x"].endswith('button:3"'))

    def test_players_past_the_pads_are_disconnected(self):
        k = self.keys(n=2)
        self.assertIn("port:1,", k["player_1_button_a"])
        self.assertEqual(k["player_2_connected"], "false")
        self.assertNotIn("player_0_connected\\default", [x for x in k if x.startswith("player_8")])

    def test_qt_ini_style_kept(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "qt-config.ini"
            f.write_text("[Controls]\nplayer_0_connected=true\n\n[UI]\nx=1\n")
            m.set_ini(f, "Controls", {"player_0_type": "0", "player_0_connected": "true"})
            text = f.read_text()
            self.assertIn("player_0_type=0", text)
            self.assertLess(text.index("player_0_type"), text.index("[UI]"))


if __name__ == "__main__":
    unittest.main()
