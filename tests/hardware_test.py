"""famidrive-hardware: graphics cards from a made-up PCI bus.

    python3 hardware_test.py path/to/famidrive_hardware.py
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def card(self, slot, vendor, cls="0x030000"):
        d = self.sys / "bus/pci/devices" / slot
        d.mkdir(parents=True)
        (d / "vendor").write_text(vendor + "\n")
        (d / "class").write_text(cls + "\n")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env={**os.environ, "FAMIDRIVE_SYSFS": str(self.sys)})

    def test_amd_and_intel_need_nothing_chosen(self):
        self.card("0000:03:00.0", "0x1002")
        self.card("0000:00:02.0", "0x8086")
        self.card("0000:00:1f.3", "0x8086", "0x040300")      # audio, not a card
        r = self.run_tool()
        self.assertIn("AMD", r.stdout)
        self.assertIn("Intel", r.stdout)
        self.assertIn('famidrive.gpu = "auto";', r.stdout)
        self.assertEqual(self.run_tool("check", "auto").stderr, "")

    def test_an_nvidia_card_without_its_driver_is_reported(self):
        self.card("0000:01:00.0", "0x10de")
        self.assertIn('famidrive.gpu = "nvidia";', self.run_tool().stdout)
        r = self.run_tool("check", "auto")
        self.assertEqual(r.returncode, 0)                    # reported, not fatal
        self.assertIn("Nvidia card", r.stderr)
        self.assertEqual(self.run_tool("check", "nvidia").stderr, "")


if __name__ == "__main__":
    unittest.main()
