"""famidrive-generate: menu entries and Steam's art, without Steam.

    python3 generators_test.py path/to/famidrive_generate.py

Each test runs the tool as a player with their own home. Nothing reaches
the network: store details are cached up front, and art comes from a
made-up Steam library cache.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.steamapps = self.home / ".local/share/Steam/steamapps"
        self.steamapps.mkdir(parents=True)
        self.out = self.home / "roms/steam"

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *args],
                           env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def install(self, appid, name, art=True):
        (self.steamapps / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n}}\n')
        if art:
            cache = self.steamapps.parent / "appcache/librarycache" / str(appid)
            cache.mkdir(parents=True)
            (cache / "library_600x900.jpg").write_bytes(b"cover " + name.encode())
            (cache / "logo.png").write_bytes(b"\x89PNG logo")
            (cache / "library_hero.jpg").write_bytes(b"hero")

    def store(self, appid, data):
        cache = self.home / ".cache/famidrive/steam"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{appid}.json").write_text(json.dumps(data))

    def test_steam_games_get_steams_art_and_details(self):
        self.install(212910, "Call of Duty: Black Ops II")
        self.store(212910, {
            "name": "Call of Duty®: Black Ops II", "short_description": "Pushing the boundaries of",
            "about_the_game": "<p>Pushing the boundaries of what fans expect.</p><br><img src='x'>Another sentence here. And a third",
            "developers": ["Treyarch"], "publishers": ["Activision"],
            "genres": [{"description": "Action"}], "release_date": {"date": "Nov 12, 2012"},
            "metacritic": {"score": 83}})
        media = self.home / "ES-DE/downloaded_media/steam"
        (media / "covers").mkdir(parents=True)
        (media / "covers/Call of Duty_ Black Ops II.jpg").write_bytes(b"scraped, wrong game")
        gamelist = self.home / "ES-DE/gamelists/steam/gamelist.xml"
        gamelist.parent.mkdir(parents=True)
        gamelist.write_text("""<?xml version="1.0"?>
<gameList>
\t<game>
\t\t<path>./Call of Duty_ Black Ops II.steam</path>
\t\t<name>Call of Duty: Black Ops</name>
\t\t<playcount>4</playcount>
\t\t<favorite>true</favorite>
\t</game>
</gameList>
""")
        self.run_tool("steam", str(self.steamapps), str(self.out))
        self.run_tool("steam-media", str(self.steamapps), str(self.out))
        stem = "Call of Duty_ Black Ops II"
        self.assertEqual((media / "covers" / f"{stem}.jpg").read_bytes(), b"cover Call of Duty: Black Ops II")
        self.assertTrue((media / "marquees" / f"{stem}.png").exists())
        self.assertTrue((media / "fanart" / f"{stem}.jpg").exists())
        aside = self.home / "ES-DE/downloaded_media-before-steam/steam/covers" / f"{stem}.jpg"
        self.assertEqual(aside.read_bytes(), b"scraped, wrong game")
        game = ET.parse(gamelist).getroot().find("game")
        self.assertEqual(game.findtext("name"), "Call of Duty: Black Ops II")   # the manifest's
        self.assertEqual(game.findtext("developer"), "Treyarch")
        self.assertEqual(game.findtext("desc"), "Pushing the boundaries of what fans expect. Another sentence here. And a third")
        self.assertEqual(game.findtext("releasedate"), "20121112T000000")
        self.assertEqual(game.findtext("rating"), "0.83")
        self.assertEqual(game.findtext("playcount"), "4")       # the player's own, kept
        self.assertEqual(game.findtext("favorite"), "true")
        before = gamelist.read_bytes()
        self.run_tool("steam-media", str(self.steamapps), str(self.out))  # again: nothing changes
        self.assertEqual(gamelist.read_bytes(), before)
        self.assertEqual(len(list((media / "covers").iterdir())), 1)

    def test_art_in_newer_steams_hashed_folders(self):
        self.install(3527290, "PEAK", art=False)
        cache = self.steamapps.parent / "appcache/librarycache/3527290"
        (cache / "480bd879ac737921bfa2529a6fea15961267ad21").mkdir(parents=True)
        (cache / "480bd879ac737921bfa2529a6fea15961267ad21/library_capsule.jpg").write_bytes(b"peak cover")
        self.store(3527290, {})
        self.run_tool("steam", str(self.steamapps), str(self.out))
        self.run_tool("steam-media", str(self.steamapps), str(self.out))
        self.assertEqual((self.home / "ES-DE/downloaded_media/steam/covers/PEAK.jpg").read_bytes(), b"peak cover")

    def heroic_config(self, extra=None):
        heroic = self.home / ".config/heroic"
        files = {
            "gog_store/installed.json": {"installed": [
                {"appName": "1207658924", "platform": "windows", "install_path": "/x"},
                {"appName": "1", "is_dlc": True}]},
            "store_cache/gog_library.json": {"games": [{"app_name": "1207658924", "title": "Hollow Knight: Voidheart"}]},
            "legendaryConfig/legendary/installed.json": {"Fortnite": {"app_name": "Fortnite", "title": "Fortnite"}},
            "nile_config/nile/installed.json": [{"id": "amzn1.adg.product.abc", "path": "/y"}],
            "store_cache/nile_library.json": {"library": [{"app_name": "amzn1.adg.product.abc", "title": "Some Prime Game"}]},
        }
        files.update(extra or {})
        for path, data in files.items():
            (heroic / path).parent.mkdir(parents=True, exist_ok=True)
            (heroic / path).write_text(json.dumps(data))
        return heroic

    def test_heroic_games_go_in_desktop(self):
        heroic = self.heroic_config()
        desktop = self.home / "roms/desktop"
        desktop.mkdir(parents=True)
        (desktop / "Uninstalled.epic").write_text("gone")
        (desktop / "Clone Hero.port").write_text("clonehero")   # not Heroic's
        self.run_tool("heroic", str(heroic), str(desktop))
        self.assertEqual((desktop / "Hollow Knight_ Voidheart.gog").read_text(), "1207658924")
        self.assertEqual((desktop / "Fortnite.epic").read_text(), "Fortnite")
        self.assertEqual((desktop / "Some Prime Game.amazon").read_text(), "amzn1.adg.product.abc")
        self.assertFalse((desktop / "Uninstalled.epic").exists())
        self.assertTrue((desktop / "Clone Hero.port").exists())

    def test_heroic_never_signed_in_gives_no_entries(self):
        desktop = self.home / "roms/desktop"
        self.run_tool("heroic", str(self.home / ".config/heroic"), str(desktop))
        self.assertEqual(list(desktop.iterdir()), [])

    def test_heroic_games_move_from_their_old_systems(self):
        heroic = self.heroic_config()
        roms = self.home / "roms"
        (roms / "gog").mkdir(parents=True)
        (roms / "gog/Hollow Knight_ Voidheart.gog").write_text("1207658924")
        lists = self.home / "ES-DE/gamelists"
        (lists / "gog").mkdir(parents=True)
        (lists / "gog/gamelist.xml").write_text(
            '<?xml version="1.0"?><gameList><game><path>./Hollow Knight_ Voidheart.gog</path>'
            '<playcount>7</playcount><favorite>true</favorite></game></gameList>')
        (lists / "desktop").mkdir(parents=True)
        (lists / "desktop/gamelist.xml").write_text(
            '<?xml version="1.0"?><gameList><game><path>./Clone Hero.port</path><playcount>2</playcount></game></gameList>')
        self.run_tool("heroic", str(heroic), str(roms / "desktop"))
        self.assertFalse((roms / "gog/Hollow Knight_ Voidheart.gog").exists())
        games = {g.findtext("path"): g for g in ET.parse(lists / "desktop/gamelist.xml").getroot().iter("game")}
        self.assertEqual(games["./Hollow Knight_ Voidheart.gog"].findtext("playcount"), "7")
        self.assertEqual(games["./Clone Hero.port"].findtext("playcount"), "2")
        self.assertFalse((lists / "gog/gamelist.xml").exists())

    def test_heroic_games_get_heroics_name_details_and_art(self):
        square = self.home / "square.jpg"
        square.write_bytes(b"cover")
        background = self.home / "bg.png"
        background.write_bytes(b"\x89PNG background")
        heroic = self.heroic_config({"store_cache/gog_library.json": {"games": [{
            "app_name": "1207658924", "title": "Hollow Knight: Voidheart", "developer": "Team Cherry",
            "art_square": square.as_uri(), "art_background": background.as_uri(),
            "extra": {"about": {"description": "Forge your own path\r\n in <b>Hallownest</b>."},
                      "genres": ["Action", "Adventure"]}}]}})
        desktop = self.home / "roms/desktop"
        self.run_tool("heroic", str(heroic), str(desktop))
        lists = self.home / "ES-DE/gamelists/desktop"
        lists.mkdir(parents=True)
        (lists / "gamelist.xml").write_text(
            '<?xml version="1.0"?><gameList><game><path>./Hollow Knight_ Voidheart.gog</path>'
            '<name>Old</name><playcount>3</playcount></game></gameList>')
        self.run_tool("heroic-media", str(heroic), str(desktop))
        game = next(g for g in ET.parse(lists / "gamelist.xml").getroot().iter("game")
                    if g.findtext("path") == "./Hollow Knight_ Voidheart.gog")
        self.assertEqual(game.findtext("name"), "Hollow Knight: Voidheart")
        self.assertEqual(game.findtext("desc"), "Forge your own path in Hallownest.")
        self.assertEqual(game.findtext("developer"), "Team Cherry")
        self.assertEqual(game.findtext("genre"), "Action, Adventure")
        self.assertEqual(game.findtext("playcount"), "3")
        media = self.home / "ES-DE/downloaded_media/desktop"
        self.assertEqual((media / "covers/Hollow Knight_ Voidheart.jpg").read_bytes(), b"cover")
        self.assertEqual((media / "fanart/Hollow Knight_ Voidheart.png").read_bytes(), b"\x89PNG background")

    def test_a_game_the_store_doesnt_know_still_gets_its_art(self):
        self.install(1, "Some Delisted Game")
        self.store(1, {})
        self.run_tool("steam", str(self.steamapps), str(self.out))
        self.run_tool("steam-media", str(self.steamapps), str(self.out))
        self.assertTrue((self.home / "ES-DE/downloaded_media/steam/covers/Some Delisted Game.jpg").exists())
        self.assertFalse((self.home / "ES-DE/gamelists/steam/gamelist.xml").exists())


if __name__ == "__main__":
    unittest.main()
