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

    def test_face_buttons_by_the_pads_labels(self):
        xbox = {"labels": {"A": "S", "B": "E", "X": "W", "Y": "N"}}
        switch = {"labels": {"B": "S", "A": "E", "Y": "W", "X": "N"}}
        playstation = {"labels": {}}
        self.assertEqual(m.dolphin_face(xbox, "labels"), {"Buttons/A": "`Button S`", "Buttons/B": "`Button E`",
                                                          "Buttons/X": "`Button W`", "Buttons/Y": "`Button N`"})
        self.assertEqual(m.dolphin_face(switch, "labels"), {"Buttons/A": "`Button E`", "Buttons/B": "`Button S`",
                                                            "Buttons/X": "`Button N`", "Buttons/Y": "`Button W`"})
        self.assertEqual(m.dolphin_face(playstation, "labels"), m.dolphin_face(xbox, "labels"))
        self.assertEqual(m.dolphin_face(switch, "positions"), {})

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


class Cemu(unittest.TestCase):
    def test_gamepad_profile_in_cemus_format(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(m.cemu_profile({"uuid": "0_" + GUID, "name": "Xbox <360>"}, "labels"))
        self.assertEqual(root.findtext("type"), "Wii U GamePad")
        c = root.find("controller")
        self.assertEqual((c.findtext("api"), c.findtext("uuid"), c.findtext("display_name")),
                         ("SDLController", "0_" + GUID, "Xbox <360>"))
        maps = {int(e.findtext("mapping")): int(e.findtext("button")) for e in c.find("mappings")}
        self.assertEqual(maps[1], 0)    # A on the button printed A
        self.assertEqual(maps[7], 42)   # ZL on the left trigger
        self.assertEqual(maps[17], 45)  # left stick up: the axis' negative Y
        self.assertEqual(maps[27], 5)   # Home on Guide

    def test_positions_is_cemus_own_default(self):
        self.assertEqual(m.cemu_mapping("positions")[1], 1)   # A on the right-hand button
        self.assertEqual(m.cemu_mapping("positions")[3], 3)   # X on the top button



DEVICES = """I: Bus=0003 Vendor=289b Product=0080 Version=0101
N: Name="raphnet technologies 1-player WUSBMote v2.2"
H: Handlers=event5 js0

I: Bus=0003 Vendor=2dc8 Product=310b Version=0114
N: Name="8BitDo Ultimate 2 Wireless Controller"
H: Handlers=event6 js1

I: Bus=0003 Vendor=2dc8 Product=310b Version=0114
N: Name="8BitDo 8BitDo Ultimate 2 Wireless Controller for PC Keyboard"
H: Handlers=sysrq kbd event7
"""
DB = """# a comment
03000000c82d00000b31000014010000,8BitDo Ultimate 2,a:b0,b:b1,platform:Linux,
03000000c82d00000b31000099990000,8BitDo Ultimate 2 (other version),a:b9,platform:Linux,
03000000c82d00000b31000000000000,8BitDo Ultimate 2,a:b1,platform:Windows,
030000005e0400008e02000014010000,Xbox 360,a:b0,platform:Linux,
"""


class SdlMappings(unittest.TestCase):
    def test_joysticks_only_once_each(self):
        self.assertEqual(m.connected_joysticks(DEVICES),
                         [("0003", "289b", "0080", "0101"), ("0003", "2dc8", "310b", "0114")])

    def test_the_connected_pads_linux_line_under_its_guid(self):
        out = m.sdl_mappings(DB, m.connected_joysticks(DEVICES))
        self.assertEqual(out, ["03000000c82d00000b31000014010000,8BitDo Ultimate 2,a:b0,b:b1,platform:Linux,"])

    def test_another_version_borrows_the_line(self):
        out = m.sdl_mappings(DB, [("0003", "2dc8", "310b", "0200")])
        self.assertEqual(out[0].split(",")[0], "03000000c82d00000b31000000020000")
        self.assertIn("8BitDo Ultimate 2", out[0])

if __name__ == "__main__":
    unittest.main()
