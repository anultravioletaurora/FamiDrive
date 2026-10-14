"""famidrive-steam-offline, against a made-up appinfo.vdf.

    python3 steam_offline_test.py path/to/famidrive_steam_offline.py
"""

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1))

# Category lists as Steam has them for real games (first box, 2026-10-14).
GAMES = {
    1091500: [2, 22, 23, 28, 29, 45, 46],          # Cyberpunk 2077
    1172380: [2, 22, 28, 29, 42, 43, 45, 46],      # STAR WARS Jedi: Fallen Order™
    413150: [1, 2, 9, 22, 23, 24, 28, 38, 39],     # Stardew Valley
    331670: [1, 2, 9, 18, 22, 23, 37, 39, 41],     # The Jackbox Party Pack
    2357570: [1, 9, 22, 27, 36, 38, 49],           # Overwatch®
    5000: [22, 28],                                # no Single-player label
}


def appinfo(version, games):
    """A minimal appinfo.vdf: each game's common/category, in version 28
    (keys inline) or 29 (keys in a string table)."""
    strings = []

    def key(k):
        if version == 28:
            return k.encode() + b"\0"
        if k not in strings:
            strings.append(k)
        return struct.pack("<I", strings.index(k))

    def tree(d):
        out = b""
        for k, v in d.items():
            if isinstance(v, dict):
                out += b"\0" + key(k) + tree(v)
            else:
                out += b"\1" + key(k) + v.encode() + b"\0"
        return out + b"\x08"

    records = b""
    for appid, cats in games.items():
        body = tree({"appinfo": {"appid": str(appid), "common": {
            "type": "Game", "category": {f"category_{c}": "1" for c in cats}}}})
        body = bytes(4 + 4 + 8 + 20 + 4 + 20) + body
        records += struct.pack("<II", appid, len(body)) + body
    records += struct.pack("<I", 0)
    if version == 28:
        return struct.pack("<II", 0x07564428, 1) + records
    table = struct.pack("<I", len(strings)) + b"".join(s.encode() + b"\0" for s in strings)
    return struct.pack("<IIq", 0x07564429, 1, 16 + len(records)) + records + table


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "appinfo.vdf"

    def tearDown(self):
        self.tmp.cleanup()

    def offline(self, appid):
        r = subprocess.run([sys.executable, SCRIPT, str(appid)], capture_output=True, text=True,
                           env={**os.environ, "FAMIDRIVE_STEAM_APPINFO": str(self.file)})
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r.returncode == 0

    def test_single_player_only_is_offline(self):
        for version in (28, 29):
            self.file.write_bytes(appinfo(version, GAMES))
            self.assertTrue(self.offline(1091500))
            self.assertTrue(self.offline(1172380), "Remote Play on TV isn't playing online")

    def test_any_multiplayer_keeps_running(self):
        self.file.write_bytes(appinfo(29, GAMES))
        self.assertFalse(self.offline(413150), "online co-op")
        self.assertFalse(self.offline(331670), "couch only, but Jackbox's server is online")
        self.assertFalse(self.offline(2357570), "no Single-player at all")

    def test_unsure_keeps_running(self):
        self.file.write_bytes(appinfo(29, GAMES))
        self.assertFalse(self.offline(5000), "no Single-player label")
        self.assertFalse(self.offline(999), "not in the cache")
        self.file.write_bytes(b"\x27\x44\x56\x07" + bytes(12))
        self.assertFalse(self.offline(1091500), "a version it can't read")
        self.file.write_bytes(appinfo(29, GAMES)[:40])
        self.assertFalse(self.offline(1091500), "cut short")
        self.file.unlink()
        self.assertFalse(self.offline(1091500), "no cache")

    def test_usage(self):
        r = subprocess.run([sys.executable, SCRIPT, "Cyberpunk"], capture_output=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
