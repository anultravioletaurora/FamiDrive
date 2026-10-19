"""famidrive-generate: menu entries and Steam's art, without Steam.

    python3 generators_test.py path/to/famidrive_generate.py

Each test runs the tool as a player with their own home. Nothing reaches
the network: store details are cached up front, and art comes from a
made-up Steam library cache.
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

    def test_heroic_games_go_in_their_stores_systems(self):
        heroic = self.heroic_config()
        roms = self.home / "roms"
        (roms / "epic").mkdir(parents=True)
        (roms / "epic/Uninstalled.epic").write_text("gone")
        (roms / "desktop").mkdir(parents=True)
        (roms / "desktop/Clone Hero.port").write_text("clonehero")   # not Heroic's
        self.run_tool("heroic", str(heroic), str(roms), "gog", "epic", "amazon")
        self.assertEqual((roms / "desktop/Hollow Knight_ Voidheart.gog").read_text(), "1207658924")
        self.assertEqual((roms / "epic/Fortnite.epic").read_text(), "Fortnite")
        self.assertEqual((roms / "desktop/Some Prime Game.amazon").read_text(), "amzn1.adg.product.abc")
        self.assertFalse((roms / "epic/Uninstalled.epic").exists())
        self.assertTrue((roms / "desktop/Clone Hero.port").exists())

    def test_heroic_lists_only_the_stores_it_runs(self):
        heroic = self.heroic_config()
        roms = self.home / "roms"
        (roms / "desktop").mkdir(parents=True)
        (roms / "desktop/Hollow Knight_ Voidheart.gog").write_text("1207658924")
        self.run_tool("heroic", str(heroic), str(roms), "epic")
        self.assertTrue((roms / "epic/Fortnite.epic").exists())
        self.assertEqual(list((roms / "desktop").iterdir()), [])

    def test_heroic_never_signed_in_gives_no_entries(self):
        roms = self.home / "roms"
        self.run_tool("heroic", str(self.home / ".config/heroic"), str(roms), "gog", "epic", "amazon")
        self.assertEqual([p for p in roms.rglob("*") if p.is_file()], [])

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
        self.run_tool("heroic", str(heroic), str(roms), "gog", "epic", "amazon")
        self.assertFalse((roms / "gog/Hollow Knight_ Voidheart.gog").exists())
        games = {g.findtext("path"): g for g in ET.parse(lists / "desktop/gamelist.xml").getroot().iter("game")}
        self.assertEqual(games["./Hollow Knight_ Voidheart.gog"].findtext("playcount"), "7")
        self.assertEqual(games["./Clone Hero.port"].findtext("playcount"), "2")
        self.assertEqual(ET.parse(lists / "gog/gamelist.xml").getroot().findall("game"), [])

    def test_epic_games_move_from_desktop_to_epic(self):
        heroic = self.heroic_config()
        roms = self.home / "roms"
        (roms / "desktop").mkdir(parents=True)
        (roms / "desktop/Fortnite.epic").write_text("Fortnite")
        lists = self.home / "ES-DE/gamelists"
        (lists / "desktop").mkdir(parents=True)
        (lists / "desktop/gamelist.xml").write_text(
            '<?xml version="1.0"?><gameList><game><path>./Fortnite.epic</path><favorite>true</favorite></game>'
            '<game><path>./Clone Hero.port</path><playcount>2</playcount></game></gameList>')
        covers = self.home / "ES-DE/downloaded_media/desktop/covers"
        covers.mkdir(parents=True)
        (covers / "Fortnite.jpg").write_bytes(b"cover")
        self.run_tool("heroic", str(heroic), str(roms), "epic")
        self.assertFalse((roms / "desktop/Fortnite.epic").exists())
        self.assertTrue((roms / "epic/Fortnite.epic").exists())
        epic = {g.findtext("path"): g for g in ET.parse(lists / "epic/gamelist.xml").getroot().iter("game")}
        self.assertEqual(epic["./Fortnite.epic"].findtext("favorite"), "true")
        desktop = [g.findtext("path") for g in ET.parse(lists / "desktop/gamelist.xml").getroot().iter("game")]
        self.assertEqual(desktop, ["./Clone Hero.port"])
        self.assertEqual((self.home / "ES-DE/downloaded_media/epic/covers/Fortnite.jpg").read_bytes(), b"cover")

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
        roms = self.home / "roms"
        self.run_tool("heroic", str(heroic), str(roms), "gog")
        lists = self.home / "ES-DE/gamelists/desktop"
        lists.mkdir(parents=True)
        (lists / "gamelist.xml").write_text(
            '<?xml version="1.0"?><gameList><game><path>./Hollow Knight_ Voidheart.gog</path>'
            '<name>Old</name><playcount>3</playcount></game></gameList>')
        self.run_tool("heroic-media", str(heroic), str(roms), "gog")
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

    def lutris_db(self, games, hidden=()):
        data = self.home / ".local/share/lutris"
        data.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(data / "pga.db")
        con.executescript("""
            CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, runner TEXT,
                                installed INTEGER, service TEXT);
            CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE games_categories (game_id INTEGER, category_id INTEGER);
            INSERT INTO categories VALUES (1, '.hidden');""")
        con.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?)", games)
        con.executemany("INSERT INTO games_categories VALUES (?, 1)", [(i,) for i in hidden])
        con.commit()
        con.close()
        return data

    def test_lutris_games_go_in_the_lutris_system(self):
        data = self.lutris_db([
            (1, "Call of Duty: Black Ops Cold War", "call-of-duty-black-ops-cold-war", "wine", 1, None),
            (2, "Not Installed", "not-installed", "wine", 0, "gog"),
            (3, "A Steam Game", "a-steam-game", "steam", 1, "steam"),
            (4, "Hidden Game", "hidden-game", "wine", 1, "gog"),
            (5, "Hollow Knight", "hollow-knight", "linux", 1, "gog"),
        ], hidden=[4])
        (data / "coverart").mkdir()
        (data / "coverart/call-of-duty-black-ops-cold-war.jpg").write_bytes(b"cover")
        out = self.home / "roms/lutris"
        out.mkdir(parents=True)
        (out / "Uninstalled.lutris").write_text("9")
        self.run_tool("lutris", str(data), str(out))
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["Call of Duty_ Black Ops Cold War.lutris", "Hollow Knight.lutris"])
        self.assertEqual((out / "Call of Duty_ Black Ops Cold War.lutris").read_text(), "1")
        game = next(ET.parse(self.home / "ES-DE/gamelists/lutris/gamelist.xml").getroot().iter("game"))
        self.assertEqual(game.findtext("name"), "Call of Duty: Black Ops Cold War")
        self.assertEqual((self.home / "ES-DE/downloaded_media/lutris/covers/Call of Duty_ Black Ops Cold War.jpg")
                         .read_bytes(), b"cover")

    def lutris_page(self, slug, data):
        cache = self.home / ".cache/famidrive/lutris"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{slug}.json").write_text(json.dumps(data))

    def test_lutris_games_get_lutris_nets_details_and_steams_when_on_steam(self):
        data = self.lutris_db([
            (1, "Call of Duty: Black Ops Cold War", "call-of-duty-black-ops-cold-war", "wine", 1, None),
            (2, "Fallout: New Vegas Ultimate Edition", "fallout-new-vegas-ultimate-edition", "wine", 1, "gog"),
            (3, "Not on lutris.net", "not-on-lutris-net", "wine", 1, None),
        ])
        cover = self.home / "cover.jpg"
        cover.write_bytes(b"lutris.net cover")
        self.lutris_page("call-of-duty-black-ops-cold-war", {
            "description": "The iconic Black Ops series is back.", "genres": [{"name": "FPS"}],
            "year": 2020, "steamid": 1985810, "coverart": cover.as_uri()})
        self.lutris_page("fallout-new-vegas-ultimate-edition", {
            "description": "Welcome to Vegas.\r\nNew Vegas.", "year": 2010, "steamid": None,
            "genres": [{"name": "RPG"}, {"name": "Open World"}], "coverart": cover.as_uri()})
        self.lutris_page("not-on-lutris-net", {})
        self.store(1985810, {"short_description": "Black Ops Cold War drops fans into the Cold War.",
                             "developers": ["Treyarch", "Raven Software"], "publishers": ["Activision"],
                             "genres": [{"description": "Action"}], "release_date": {"date": "Mar 8, 2023"}})
        cache = self.steamapps.parent / "appcache/librarycache/1985810"
        cache.mkdir(parents=True)
        (cache / "logo.png").write_bytes(b"\x89PNG logo")
        (cache / "library_hero.jpg").write_bytes(b"hero")
        (cache / "library_600x900.jpg").write_bytes(b"steam cover")
        (data / "coverart").mkdir()
        (data / "coverart/call-of-duty-black-ops-cold-war.jpg").write_bytes(b"lutris cover")
        out = self.home / "roms/lutris"
        self.run_tool("lutris", str(data), str(out))
        self.run_tool("lutris-media", str(data), str(out))
        games = {g.findtext("path"): g for g in
                 ET.parse(self.home / "ES-DE/gamelists/lutris/gamelist.xml").getroot().iter("game")}
        cw = games["./Call of Duty_ Black Ops Cold War.lutris"]
        self.assertEqual(cw.findtext("name"), "Call of Duty: Black Ops Cold War")
        self.assertEqual(cw.findtext("desc"), "Black Ops Cold War drops fans into the Cold War.")
        self.assertEqual(cw.findtext("developer"), "Treyarch, Raven Software")
        self.assertEqual(cw.findtext("genre"), "Action")
        # The game's year, not when it came to Steam.
        self.assertEqual(cw.findtext("releasedate"), "20200101T000000")
        fnv = games["./Fallout_ New Vegas Ultimate Edition.lutris"]
        self.assertEqual(fnv.findtext("desc"), "Welcome to Vegas. New Vegas.")
        self.assertEqual(fnv.findtext("genre"), "RPG, Open World")
        self.assertEqual(fnv.findtext("releasedate"), "20100101T000000")
        self.assertIsNone(games["./Not on lutris.net.lutris"].find("desc"))
        media = self.home / "ES-DE/downloaded_media/lutris"
        # Lutris's own cover stays; Steam's logo and hero come with it.
        self.assertEqual((media / "covers/Call of Duty_ Black Ops Cold War.jpg").read_bytes(), b"lutris cover")
        self.assertEqual((media / "marquees/Call of Duty_ Black Ops Cold War.png").read_bytes(), b"\x89PNG logo")
        self.assertEqual((media / "fanart/Call of Duty_ Black Ops Cold War.jpg").read_bytes(), b"hero")
        self.assertEqual((media / "covers/Fallout_ New Vegas Ultimate Edition.jpg").read_bytes(), b"lutris.net cover")

    def test_a_launcher_tops_its_stores_system_after_favorites(self):
        out = self.home / "roms/lutris"
        out.mkdir(parents=True)
        (out / "Diablo IV.lutris").write_text("2")
        gamelist = self.home / "ES-DE/gamelists/lutris/gamelist.xml"
        gamelist.parent.mkdir(parents=True)
        gamelist.write_text('<?xml version="1.0"?>\n<gameList>\n\t<game>\n\t\t<path>./Diablo IV.lutris</path>\n'
                            '\t\t<name>Diablo IV</name>\n\t\t<favorite>true</favorite>\n\t</game>\n</gameList>\n')
        self.run_tool("launcher", str(out), "Lutris", "lutris")
        self.run_tool("launcher", str(out), "Lutris", "lutris")
        self.assertEqual((out / "Lutris.setting").read_text(), "lutris")
        games = {g.findtext("path"): g for g in ET.parse(gamelist).getroot().iter("game")}
        self.assertEqual(len(games), 2)
        self.assertEqual(games["./Lutris.setting"].findtext("sortname"), "0")
        # The player's favorite is left alone, and still listed first.
        self.assertEqual(games["./Diablo IV.lutris"].findtext("favorite"), "true")
        self.assertIsNone(games["./Diablo IV.lutris"].find("sortname"))

    def test_lutris_never_opened_gives_no_entries(self):
        out = self.home / "roms/lutris"
        self.run_tool("lutris", str(self.home / ".local/share/lutris"), str(out))
        self.assertEqual(list(out.iterdir()), [])

    def test_lutris_database_unreadable_keeps_the_entries(self):
        data = self.home / ".local/share/lutris"
        data.mkdir(parents=True)
        (data / "pga.db").write_bytes(b"not a database")
        out = self.home / "roms/lutris"
        out.mkdir(parents=True)
        (out / "Kept.lutris").write_text("1")
        r = subprocess.run([sys.executable, str(SCRIPT), "lutris", str(data), str(out)],
                           env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((out / "Kept.lutris").exists())

    def test_a_game_the_store_doesnt_know_still_gets_its_art(self):
        self.install(1, "Some Delisted Game")
        self.store(1, {})
        self.run_tool("steam", str(self.steamapps), str(self.out))
        self.run_tool("steam-media", str(self.steamapps), str(self.out))
        self.assertTrue((self.home / "ES-DE/downloaded_media/steam/covers/Some Delisted Game.jpg").exists())
        self.assertFalse((self.home / "ES-DE/gamelists/steam/gamelist.xml").exists())


if __name__ == "__main__":
    unittest.main()
