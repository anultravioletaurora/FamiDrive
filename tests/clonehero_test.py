"""famidrive-clonehero, against made-up charts and homes.

    python3 clonehero_test.py path/to/famidrive_clonehero.py

Charts come from a folder (file:// in place of Chorus Encore).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1))


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.encore = self.dir / "encore"
        self.encore.mkdir()
        (self.encore / "aaaa.sng").write_bytes(b"SNGPKG song a")
        (self.encore / "bbbb.sng").write_bytes(b"SNGPKG song b")
        (self.encore / "bad0.sng").write_bytes(b"<html>not found</html>")
        self.lib = self.dir / "library/songs"
        self.home = self.dir / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, cmd, spec):
        env = {**os.environ, "HOME": str(self.home),
               "FAMIDRIVE_ENCORE": f"file://{self.encore}/{{md5}}.sng"}
        env.pop("XDG_STATE_HOME", None)
        r = subprocess.run([sys.executable, str(SCRIPT), cmd, json.dumps(spec)],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stderr

    def songs(self, songs, only=True):
        return self.run_tool("songs", {"dir": str(self.lib), "songs": songs, "onlyListed": only})

    def test_songs_downloaded_and_removed(self):
        self.songs({"AFI - Miss Murder": "AAAA", "Song: B": "bbbb"})
        self.assertEqual((self.lib / "AFI - Miss Murder.sng").read_bytes(), b"SNGPKG song a")
        self.assertTrue((self.lib / "Song_ B.sng").exists())
        stamp = (self.lib / ".famidrive-stamp").read_text()
        # Unchanged: nothing downloaded, the stamp stays.
        self.songs({"AFI - Miss Murder": "aaaa", "Song: B": "bbbb"})
        self.assertEqual((self.lib / ".famidrive-stamp").read_text(), stamp)
        # One dropped: removed, and the stamp moves.
        self.songs({"AFI - Miss Murder": "aaaa"})
        self.assertFalse((self.lib / "Song_ B.sng").exists())
        self.assertNotEqual((self.lib / ".famidrive-stamp").read_text(), stamp)

    def test_new_md5_downloads_again(self):
        self.songs({"Song": "aaaa"})
        self.songs({"Song": "bbbb"})
        self.assertEqual((self.lib / "Song.sng").read_bytes(), b"SNGPKG song b")

    def test_not_a_chart_is_skipped(self):
        err = self.songs({"Broken": "bad0", "Good": "aaaa"})
        self.assertIn("skipped Broken", err)
        self.assertFalse((self.lib / "Broken.sng").exists())
        self.assertFalse(list(self.lib.glob("*.part")))
        self.assertTrue((self.lib / "Good.sng").exists())

    def test_profiles_added_never_changed(self):
        ch = self.home / ".clonehero"
        ch.mkdir()
        (ch / "profiles.ini").write_text("[profile0]\nnote_speed = 9\nplayer_name = Alice\nlefty_flip = 1\n")
        self.run_tool("player", {"profiles": ["Alice", "Bob", "Guest 1"], "stamps": []})
        text = (ch / "profiles.ini").read_text()
        self.assertIn("[profile0]\nnote_speed = 9\nplayer_name = Alice\nlefty_flip = 1\n", text)
        self.assertIn("[profile1]\n", text)
        self.assertIn("player_name = Bob\n", text)
        self.assertIn("[profile2]\n", text)
        self.assertIn("player_name = Guest 1\n", text)
        self.assertEqual(text.count("player_name = Alice"), 1)
        # Again: nothing more.
        self.run_tool("player", {"profiles": ["Alice", "Bob", "Guest 1"], "stamps": []})
        self.assertEqual((ch / "profiles.ini").read_text(), text)

    def test_cache_cleared_when_library_changes(self):
        ch = self.home / ".clonehero"
        ch.mkdir()
        cache = ch / "songcache.bin"
        stamp = self.dir / "stamp"
        stamp.write_text("1")
        spec = {"profiles": [], "stamps": [str(stamp)]}
        cache.write_bytes(b"cache")
        self.run_tool("player", spec)          # first session: rescan
        self.assertFalse(cache.exists())
        cache.write_bytes(b"cache")
        self.run_tool("player", spec)          # nothing changed: kept
        self.assertTrue(cache.exists())
        stamp.write_text("2")
        self.run_tool("player", spec)          # library changed: rescan
        self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
