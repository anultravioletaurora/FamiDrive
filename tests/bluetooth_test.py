"""famidrive-bluetooth: names, which devices are controllers, and the
Settings entries, without BlueZ.

    python3 bluetooth_test.py path/to/famidrive_bluetooth.py
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_bluetooth", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Names(unittest.TestCase):
    def test_nintendo_names(self):
        self.assertEqual(m.friendly("Nintendo RVL-CNT-01"), "Wii Remote")
        self.assertEqual(m.friendly("Nintendo RVL-CNT-01-TR"), "Wii Remote Plus")
        self.assertEqual(m.friendly("Nintendo RVL-CNT-01-UC"), "Wii U Pro Controller")
        self.assertEqual(m.friendly("Nintendo RVL-WBC-01"), "Wii Balance Board")
        self.assertEqual(m.friendly("Pro Controller"), "Switch Pro Controller")

    def test_playstation_and_xbox(self):
        self.assertEqual(m.friendly("DualSense Wireless Controller"), "DualSense")
        self.assertEqual(m.friendly("Wireless Controller"), "DualShock 4")
        self.assertEqual(m.friendly("Xbox Wireless Controller"), "Xbox Wireless Controller")

    def test_unknown_keeps_its_name(self):
        self.assertEqual(m.friendly("8BitDo Ultimate 2 Wireless"), "8BitDo Ultimate 2 Wireless")
        self.assertEqual(m.friendly(""), "Controller")


class Controllers(unittest.TestCase):
    def test_gamepad_icon(self):
        self.assertTrue(m.is_controller({"Icon": "input-gaming", "Name": "x"}))

    def test_wii_remote_class(self):
        # A Wii Remote's class: peripheral, joystick.
        self.assertTrue(m.is_controller({"Class": 0x002504, "Name": "Nintendo RVL-CNT-01"}))

    def test_le_gamepad_appearance(self):
        self.assertTrue(m.is_controller({"Appearance": 0x03C4, "Name": "x"}))

    def test_not_headphones_or_keyboards(self):
        self.assertFalse(m.is_controller({"Icon": "audio-headset", "Class": 0x240404, "Name": "Headphones"}))
        self.assertFalse(m.is_controller({"Icon": "input-keyboard", "Class": 0x002540, "Name": "Keyboard K380"}))


class Entries(unittest.TestCase):
    def test_none_without_an_adapter(self):
        self.assertEqual(m.plan_entries(False, [("AA", "Nintendo RVL-CNT-01")]), {})

    def test_pair_and_one_forget_each(self):
        planned = m.plan_entries(True, [("AA", "Nintendo RVL-CNT-01"), ("BB", "Nintendo RVL-CNT-01"),
                                         ("CC", "DualSense Wireless Controller")])
        self.assertEqual(planned, {
            "Pair a Controller.setting": "bluetooth-pair",
            "Forget Wii Remote.setting": "bluetooth-forget AA",
            "Forget Wii Remote (2).setting": "bluetooth-forget BB",
            "Forget DualSense.setting": "bluetooth-forget CC",
        })

    def test_writes_ours_and_leaves_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Steam Settings.setting").write_text("steam")
            (d / "Forget Old Pad.setting").write_text("bluetooth-forget ZZ")
            m.write_entries(d, m.plan_entries(True, [("AA", "Wireless Controller")]))
            self.assertEqual(sorted(p.name for p in d.iterdir()),
                             ["Forget DualShock 4.setting", "Pair a Controller.setting", "Steam Settings.setting"])
            m.write_entries(d, m.plan_entries(False, []))
            self.assertEqual([p.name for p in d.iterdir()], ["Steam Settings.setting"])


if __name__ == "__main__":
    unittest.main()
