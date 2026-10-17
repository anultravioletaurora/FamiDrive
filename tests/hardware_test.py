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

    def card(self, slot, vendor, cls="0x030000", device="0x1234", driver=None, outputs=(), boot_vga=None, n=0):
        """A card, with its DRM outputs: {"HDMI-A-1": "connected", ...}."""
        d = self.sys / "bus/pci/devices" / slot
        d.mkdir(parents=True)
        (d / "vendor").write_text(vendor + "\n")
        (d / "device").write_text(device + "\n")
        (d / "class").write_text(cls + "\n")
        if boot_vga is not None:
            (d / "boot_vga").write_text(f"{int(boot_vga)}\n")
        if driver:
            target = self.sys / "bus/pci/drivers" / driver
            target.mkdir(parents=True, exist_ok=True)
            (d / "driver").symlink_to(target)
        card = d / "drm" / f"card{n}"
        card.mkdir(parents=True)
        for name, status in dict(outputs).items():
            (card / f"card{n}-{name}").mkdir()
            (card / f"card{n}-{name}" / "status").write_text(status + "\n")

    def laptop(self, nvidia_driver="nvidia"):
        """The Intel card has every output; the Nvidia card is a 3D
        controller with none, as on many laptops."""
        self.card("0000:01:00.0", "0x10de", "0x030200", "0x1fb6", nvidia_driver, n=0)
        self.card("0000:00:02.0", "0x8086", device="0x46a6", driver="i915", boot_vga=True, n=1,
                  outputs={"eDP-1": "connected", "HDMI-A-1": "connected", "DP-1": "disconnected"})

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

    def test_one_card_needs_no_choosing(self):
        self.card("0000:03:00.0", "0x1002", driver="amdgpu", outputs={"HDMI-A-1": "connected"})
        r = self.run_tool("display")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(self.run_tool("offload").returncode, 1)

    def test_the_first_and_second_box_change_nothing(self):
        # One AMD card (the first box), one Intel card (the second): no
        # card to prefer, so gamescope's command line stays as it was.
        for slot, vendor in (("0000:03:00.0", "0x1002"), ("0000:00:02.0", "0x8086")):
            with self.subTest(vendor=vendor):
                self.tearDown()
                self.setUp()
                self.card(slot, vendor, outputs={"HDMI-A-1": "connected"})
                self.assertEqual(self.run_tool("display").returncode, 1)
                self.assertEqual(self.run_tool("offload").returncode, 1)

    def test_a_desktop_with_amds_cpu_graphics_on_uses_the_tvs_card(self):
        # A Ryzen's own graphics left on beside a Radeon card: the TV's card
        # for gamescope, whichever Vulkan lists first, and no offload.
        self.card("0000:03:00.0", "0x1002", device="0x744c", driver="amdgpu", n=0,
                  outputs={"HDMI-A-1": "connected"})
        self.card("0000:10:00.0", "0x1002", device="0x164e", driver="amdgpu", boot_vga=True, n=1,
                  outputs={"HDMI-A-1": "disconnected"})
        self.assertEqual(self.run_tool("display").stdout, "1002:744c\n")
        self.assertEqual(self.run_tool("offload").returncode, 1)

    def test_a_laptop_renders_on_nvidia_and_shows_on_intel(self):
        self.laptop()
        self.assertEqual(self.run_tool("display").stdout, "8086:46a6\n")
        r = self.run_tool("offload")
        self.assertEqual((r.returncode, r.stdout), (0, "10de:1fb6\n"))
        listing = self.run_tool().stdout
        self.assertIn("Intel  (the screen is on this one)", listing)
        self.assertIn("Hybrid graphics", listing)
        self.assertIn('famidrive.gpu = "nvidia";', listing)

    def test_no_offload_without_nvidias_driver(self):
        self.laptop(nvidia_driver="nouveau")
        self.assertEqual(self.run_tool("display").stdout, "8086:46a6\n")
        self.assertEqual(self.run_tool("offload").returncode, 1)

    def test_a_desktop_with_the_tv_on_nvidia_uses_it_for_both(self):
        # An Intel CPU's own graphics left on, the TV on the Nvidia card.
        self.card("0000:00:02.0", "0x8086", device="0x3e92", driver="i915", boot_vga=True, n=0,
                  outputs={"HDMI-A-1": "disconnected", "DP-1": "disconnected"})
        self.card("0000:01:00.0", "0x10de", device="0x2684", driver="nvidia", n=1,
                  outputs={"HDMI-A-1": "connected", "DP-1": "disconnected"})
        self.assertEqual(self.run_tool("display").stdout, "10de:2684\n")
        self.assertEqual(self.run_tool("offload").returncode, 1)

    def test_with_nothing_connected_the_card_with_outputs_wins(self):
        # The TV is off: no output is connected, and only Intel has any.
        self.card("0000:01:00.0", "0x10de", "0x030200", "0x1fb6", "nvidia", n=0)
        self.card("0000:00:02.0", "0x8086", device="0x46a6", driver="i915", n=1,
                  outputs={"HDMI-A-1": "disconnected"})
        self.assertEqual(self.run_tool("display").stdout, "8086:46a6\n")
        self.assertEqual(self.run_tool("offload").returncode, 0)

    def test_with_no_outputs_read_the_boot_card_wins(self):
        # The drivers haven't made their DRM cards yet.
        self.card("0000:01:00.0", "0x10de", "0x030200", "0x1fb6", n=0)
        self.card("0000:00:02.0", "0x8086", device="0x46a6", boot_vga=True, n=1)
        self.assertEqual(self.run_tool("display").stdout, "8086:46a6\n")


if __name__ == "__main__":
    unittest.main()
