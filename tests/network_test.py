"""famidrive-network: nmcli's output, the Settings entries and passwords
typed in ES-DE's game-info editor, without NetworkManager.

    python3 network_test.py path/to/famidrive_network.py
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_network", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

GAMELIST = """<?xml version="1.0"?>
<gameList>
\t<game>
\t\t<path>./Wi-Fi: Home 5G.setting</path>
\t\t<name>Wi-Fi: Home 5G</name>
\t\t<sortname>hunter2 &amp; more</sortname>
\t\t<playcount>1</playcount>
\t</game>
\t<game>
\t\t<path>./Steam Settings.setting</path>
\t\t<name>Steam Settings</name>
\t\t<sortname>0</sortname>
\t</game>
</gameList>
"""


class Terse(unittest.TestCase):
    def test_escaped_colons(self):
        self.assertEqual(m.split_terse(r"*:Cafe\: Upstairs:WPA2:72"), ["*", "Cafe: Upstairs", "WPA2", "72"])
        self.assertEqual(m.split_terse(r"GENERAL.HWADDR:AA\:BB\:CC"), ["GENERAL.HWADDR", "AA:BB:CC"])


class Entries(unittest.TestCase):
    DEVICES = [("wlan0", "wifi", "connected"), ("enp2s0", "ethernet", "unavailable"), ("lo", "loopback", "unmanaged")]

    def test_networks_ports_and_forgets(self):
        networks = [("", "Neighbor", "WPA2", "40"), ("*", "Home", "WPA2 WPA3", "60"),
                    ("", "Home", "WPA2 WPA3", "80"), ("", "", "WPA2", "90"),
                    ("", "Cafe/Guest", "", "50")]
        planned = m.plan_entries(self.DEVICES, networks, ["Home", "Old Place"])
        self.assertEqual(list(planned), [
            "Wi-Fi: Home (connected).setting", "Wi-Fi: CafeGuest.setting", "Wi-Fi: Neighbor.setting",
            "Forget Wi-Fi: Home.setting", "Forget Wi-Fi: Old Place.setting", "Ethernet.setting"])
        self.assertEqual(planned["Wi-Fi: CafeGuest.setting"], "network-wifi\nCafe/Guest\n")
        self.assertEqual(planned["Forget Wi-Fi: Old Place.setting"], "network-forget\nOld Place")
        self.assertEqual(planned["Ethernet.setting"], "network-ethernet\nenp2s0")

    def test_no_wifi_adapter_no_wifi_entries(self):
        planned = m.plan_entries([("eno1", "ethernet", "connected"), ("eno2", "ethernet", "connected")], [], ["Home"])
        self.assertEqual(list(planned), ["Ethernet.setting", "Ethernet 2.setting"])

    def test_writes_ours_and_leaves_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Pair a Controller.setting").write_text("bluetooth-pair")
            (d / "Wi-Fi: Gone.setting").write_text("network-wifi\nGone\n")
            m.write_entries(d, {"Ethernet.setting": "network-ethernet\neno1"})
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["Ethernet.setting", "Pair a Controller.setting"])


class Passwords(unittest.TestCase):
    def test_typed_as_sort_name_then_wiped(self):
        with tempfile.TemporaryDirectory() as d:
            g = Path(d) / "gamelist.xml"
            g.write_text(GAMELIST)
            self.assertEqual(m.typed_password(g, "Wi-Fi: Home 5G.setting"), "hunter2 & more")
            self.assertIsNone(m.typed_password(g, "Wi-Fi: Elsewhere.setting"))
            self.assertTrue(m.wipe_passwords(g))
            self.assertIsNone(m.typed_password(g, "Wi-Fi: Home 5G.setting"))
            self.assertNotIn("hunter2", g.read_text())
            self.assertIn("<sortname>0</sortname>", g.read_text())   # Steam Settings' own stays
            self.assertFalse(m.wipe_passwords(g))

    def test_no_game_list_yet(self):
        self.assertIsNone(m.typed_password(Path("/nonexistent/gamelist.xml"), "Wi-Fi: X.setting"))
        self.assertFalse(m.wipe_passwords(Path("/nonexistent/gamelist.xml")))

    def test_key_management(self):
        self.assertIsNone(m.key_mgmt(""))
        self.assertIsNone(m.key_mgmt("--"))
        self.assertEqual(m.key_mgmt("WPA2"), "wpa-psk")
        self.assertEqual(m.key_mgmt("WPA2 WPA3"), "wpa-psk")
        self.assertEqual(m.key_mgmt("WPA3"), "sae")
        self.assertEqual(m.key_mgmt("WPA2 802.1X"), "wpa-eap")


class Ethernet(unittest.TestCase):
    def test_no_cable(self):
        title, detail = m.describe_ethernet({"WIRED-PROPERTIES.CARRIER": "off", "GENERAL.HWADDR": "6C:3C:8C:00:00:01"})
        self.assertEqual(title, "No cable in the Ethernet port")
        self.assertIn("6C:3C:8C:00:00:01", detail)

    def test_connected(self):
        title, detail = m.describe_ethernet({
            "WIRED-PROPERTIES.CARRIER": "on", "GENERAL.STATE": "100 (connected)", "GENERAL.HWADDR": "AA:BB",
            "IP4.ADDRESS": "192.168.1.20/24", "CAPABILITIES.SPEED": "1000 Mb/s"})
        self.assertEqual(title, "Ethernet connected")
        self.assertEqual(detail, "Address 192.168.1.20 · 1000 Mb/s · hardware AA:BB")


if __name__ == "__main__":
    unittest.main()
