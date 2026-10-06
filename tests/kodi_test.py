"""famidrive-kodi: sources and video database setup, with no Kodi.

    python3 kodi_test.py path/to/famidrive_kodi.py

Each test runs the tool as a player with their own home, and stands in
for Kodi by making its databases with the tables Kodi 21 makes.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()

# Kodi 21's own CREATE TABLE statements (read off its binary).
PATH_TABLE = ("CREATE TABLE path ( idPath integer primary key, strPath text, strContent text,"
              " strScraper text, strHash text, scanRecursive integer, useFolderNames bool,"
              " strSettings text, noUpdate bool, exclude bool, allAudio bool, dateAdded text,"
              " idParentPath integer)")
INSTALLED_TABLE = ("CREATE TABLE installed (id INTEGER PRIMARY KEY, addonID TEXT UNIQUE, enabled BOOLEAN,"
                   " installDate TEXT, lastUpdated TEXT, lastUsed TEXT, origin TEXT NOT NULL DEFAULT '',"
                   " disabledReason INTEGER NOT NULL DEFAULT 0)")


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.media = Path(self.tmp.name) / "media"
        self.db = self.home / ".kodi/userdata/Database"
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        # A stand-in kodi-send that records what it was asked.
        (self.bin / "kodi-send").write_text(f"#!/bin/sh\necho \"$@\" >> {self.tmp.name}/sent\n")
        (self.bin / "kodi-send").chmod(0o755)
        self.spec = {"sources": {
            "Movies": {"path": str(self.media / "movies"), "content": "movies"},
            "TV Shows": {"path": str(self.media / "tv") + "/", "content": "tvshows"},
        }, "addons": ["plugin.video.jellyfin"]}

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, cmd, spec):
        env = {**os.environ, "HOME": str(self.home), "PATH": f"{self.bin}:{os.environ['PATH']}"}
        env.pop("KODI_HOME", None)
        r = subprocess.run([sys.executable, str(SCRIPT), cmd, json.dumps(spec)],
                           env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stderr

    def sent(self):
        p = Path(self.tmp.name) / "sent"
        return p.read_text() if p.exists() else ""

    def test_sources_merged_with_the_players_own(self):
        userdata = self.home / ".kodi/userdata"
        userdata.mkdir(parents=True)
        (userdata / "sources.xml").write_text(
            "<sources><video><default pathversion=\"1\"/>"
            "<source><name>Mine</name><path pathversion=\"1\">/home/me/videos/</path></source>"
            f"<source><name>Old name</name><path pathversion=\"1\">{self.media}/movies/</path></source>"
            "</video><music><source><name>Tunes</name><path>/music/</path></source></music></sources>")
        self.run_tool("prepare", self.spec)
        root = ET.parse(userdata / "sources.xml").getroot()
        video = {s.findtext("name"): s.findtext("path") for s in root.find("video").findall("source")}
        self.assertEqual(video, {"Mine": "/home/me/videos/", "Movies": f"{self.media}/movies/",
                                 "TV Shows": f"{self.media}/tv/"})
        self.assertEqual(root.find("music/source/name").text, "Tunes")
        before = (userdata / "sources.xml").read_bytes()
        self.run_tool("prepare", self.spec)                 # again: unchanged
        self.assertEqual((userdata / "sources.xml").read_bytes(), before)

    def test_addons_switched_on_once_kodi_has_its_database(self):
        self.run_tool("prepare", self.spec)                 # first run: no database yet, fine
        self.db.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db / "Addons33.db") as c:
            c.execute(INSTALLED_TABLE)
            c.execute("INSERT INTO installed (addonID, enabled, disabledReason) VALUES ('plugin.video.jellyfin', 0, 1)")
            c.execute("INSERT INTO installed (addonID, enabled) VALUES ('something.else', 0)")
        self.run_tool("prepare", self.spec)
        with sqlite3.connect(self.db / "Addons33.db") as c:
            rows = dict(c.execute("SELECT addonID, enabled FROM installed"))
        self.assertEqual(rows, {"plugin.video.jellyfin": 1, "something.else": 0})

    def test_folders_get_content_and_a_scan(self):
        (self.media / "movies").mkdir(parents=True)
        self.db.mkdir(parents=True)
        with sqlite3.connect(self.db / "MyVideos131.db") as c:
            c.execute(PATH_TABLE)
            c.execute("INSERT INTO path (strPath) VALUES (?)", (f"{self.media}/tv/",))   # Kodi saw it already
        with sqlite3.connect(self.db / "MyVideos121.db") as c:                         # an older Kodi's
            c.execute(PATH_TABLE)
        self.run_tool("library", self.spec)
        with sqlite3.connect(self.db / "MyVideos131.db") as c:
            rows = {r[0]: r[1:] for r in c.execute(
                "SELECT strPath, strContent, strScraper, scanRecursive, exclude FROM path")}
        self.assertEqual(rows, {
            f"{self.media}/tv/": ("tvshows", "metadata.tvshows.themoviedb.org.python", 0, 0),
            f"{self.media}/movies/": ("movies", "metadata.themoviedb.org.python", 2147483647, 0),
        })
        self.assertIn("UpdateLibrary(video)", self.sent())

    def test_no_scan_with_the_drive_unplugged(self):
        self.db.mkdir(parents=True)
        with sqlite3.connect(self.db / "MyVideos131.db") as c:
            c.execute(PATH_TABLE)
        self.run_tool("library", self.spec)
        self.assertEqual(self.sent(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
