"""romm-agent: the parts that don't need a RomM server.

    python3 romm_agent_test.py path/to/romm_agent.py

Each test loads the agent fresh, as a player with their own home and
config, the way famidrive-launch and the session run it.
"""

import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

AGENT = Path(sys.argv.pop(1)).read_text()
EDEN_ROOT = "~/.local/share/eden/nand/user/save/0000000000000000"
PROFILES = ".local/share/eden/nand/system/save/8000000000000010/su/avators/profiles.dat"


def eden_profiles_dat(*uids):
    """A profiles.dat as Eden writes it: a 0x10 header, 8 users of 0xC8."""
    users = b""
    for uid in uids:
        users += uid + uid + bytes(8) + b"Eden".ljust(0x20, b"\0") + bytes(0x80)
    return bytes(0x10) + users + bytes(0xC8 * (8 - len(uids)))


class Box:
    """A player's home and a shared library, in a temp folder."""

    def __init__(self, base, name, **cfg):
        self.home = base / name
        self.home.mkdir(parents=True, exist_ok=True)
        self.data = base / "library"
        self.cfg = {
            "url": "https://romm.example.org", "tokenFile": "/dev/null",
            "owner": name, "displayName": name.title(), "deviceName": "box",
            "dataDir": str(self.data), "playerRoms": str(self.home / ".local/share/famidrive/roms"),
            "gamelistDir": str(self.home / "ES-DE/gamelists"),
            "systems": {
                "switch": {"rommPlatform": "switch", "saveSync": True, "emulator": "eden",
                           "saveLayout": {"kind": "eden-title-id", "root": EDEN_ROOT}},
                "gc": {"rommPlatform": "ngc", "saveSync": True, "emulator": "dolphin",
                       "extensions": [".iso", ".rvz", ".gcz", ".ciso"],
                       "saveLayout": {"kind": "dolphin-gci-folder", "root": "~/.local/share/dolphin-emu/GC"}},
                "snes": {"rommPlatform": "snes", "saveSync": True, "emulator": "retroarch-snes9x",
                         "saveLayout": {"kind": "retroarch-srm", "root": "~/.config/retroarch/saves"}},
            },
        }
        self.cfg.update(cfg)

    def agent(self):
        cfg = self.home / "romm.json"
        cfg.write_text(json.dumps(self.cfg))
        os.environ["HOME"] = str(self.home)
        os.environ["ROMM_AGENT_CONFIG"] = str(cfg)
        os.environ.pop("XDG_STATE_HOME", None)
        os.environ.pop("CREDENTIALS_DIRECTORY", None)
        g = {"__name__": "romm_agent"}
        exec(compile(AGENT, "romm_agent.py", "exec"), g)
        return g


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------ Eden profiles

    def test_eden_folder_name(self):
        # Eden names a user's save folder by the ID's high 64 bits, then its low.
        a = Box(self.base, "alice").agent()
        uid = bytes(range(16))
        self.assertEqual(a["eden_folder"](uid), "0F0E0D0C0B0A09080706050403020100")

    def test_eden_profile_read_from_eden(self):
        box = Box(self.base, "alice")
        p = box.home / PROFILES
        p.parent.mkdir(parents=True)
        p.write_bytes(eden_profiles_dat(bytes(range(16)), bytes(range(16, 32))))
        a = box.agent()
        self.assertEqual(a["eden_users"](), ["0F0E0D0C0B0A09080706050403020100",
                                             "1F1E1D1C1B1A19181716151413121110"])
        self.assertEqual(a["eden_profile"](), "0F0E0D0C0B0A09080706050403020100")
        # The user Eden runs games as wins.
        (box.home / ".config/eden").mkdir(parents=True)
        (box.home / ".config/eden/qt-config.ini").write_text("[System]\ncurrent_user\\default=false\ncurrent_user=1\n")
        self.assertEqual(box.agent()["eden_profile"](), "1F1E1D1C1B1A19181716151413121110")

    def test_eden_profile_override(self):
        box = Box(self.base, "alice", edenProfileId="aaaabbbbccccddddeeeeffff00001111")
        self.assertEqual(box.agent()["eden_profile"](), "AAAABBBBCCCCDDDDEEEEFFFF00001111")

    def test_eden_profile_made_for_new_player(self):
        a = Box(self.base, "alice").agent()
        a["cmd_eden_profile"]()
        raw = a["EDEN_PROFILES"].read_bytes()
        self.assertEqual(len(raw), 0x10 + 8 * 0xC8)
        self.assertEqual(raw[0x38:0x3D], b"Alice")
        users = a["eden_users"]()
        self.assertEqual(len(users), 1)
        # Derived from the RomM username: the same on each of their boxes.
        b = Box(self.base / "other-box", "alice").agent()
        b["cmd_eden_profile"]()
        self.assertEqual(b["eden_users"](), users)
        # An Eden that already has profiles is left alone.
        a["EDEN_PROFILES"].write_bytes(eden_profiles_dat(bytes(range(16))))
        a["cmd_eden_profile"]()
        self.assertEqual(a["eden_users"](), ["0F0E0D0C0B0A09080706050403020100"])

    # ------------------------------------------------------------ save archives

    def test_switch_save_moves_between_profiles(self):
        # One player, two boxes, a different Eden profile ID on each.
        one = Box(self.base / "one", "alice", edenProfileId="11111111111111111111111111111111")
        two = Box(self.base / "two", "alice", edenProfileId="22222222222222222222222222222222")
        a = one.agent()
        _, root, lay = a["layout"]("switch")
        (root / lay["profile"] / "01007EF00011E000/0").mkdir(parents=True)
        (root / lay["profile"] / "01007EF00011E000/0/game_data.sav").write_bytes(b"save")
        rels = [f"{lay['profile']}/01007EF00011E000"]
        digest = a["files_hash"](root, rels, lay)
        blob, manifest = a["pack"]("switch", {"title_id": "01007EF00011E000"}, root, rels, digest, lay)
        self.assertEqual(manifest["paths"], ["@profile/01007EF00011E000"])
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            self.assertNotIn("1111", " ".join(tar.getnames()))

        b = two.agent()
        _, root2, lay2 = b["layout"]("switch")
        b["unpack"](blob, root2, lay2)
        self.assertEqual((root2 / "22222222222222222222222222222222/01007EF00011E000/0/game_data.sav").read_bytes(), b"save")
        # The same save hashes the same on both boxes, so it isn't pushed again.
        self.assertEqual(b["files_hash"](root2, ["22222222222222222222222222222222/01007EF00011E000"], lay2), digest)
        # Archives that name a profile ID outright land in this box's too.
        self.assertEqual(b["from_archive"](lay2, "11111111111111111111111111111111/X"),
                         "22222222222222222222222222222222/X")

    def test_other_systems_keep_their_paths(self):
        a = Box(self.base, "alice").agent()
        _, _, lay = a["layout"]("snes")
        self.assertEqual(a["to_archive"](lay, "Game.srm"), "Game.srm")
        self.assertEqual(a["from_archive"](lay, "Game.srm"), "Game.srm")

    # ------------------------------------------------------------ the library and players

    def test_folder_rom_launches_its_game_file(self):
        # A multi-file ROM as RomM sends GameCube games: the game, its .m3u
        # (listing everything), a modded copy in hack/, and macOS litter.
        box = Box(self.base, "alice")
        a = box.agent()
        folder = box.data / "roms/gc/Mario Party 4"
        (folder / "hack").mkdir(parents=True)
        (folder / "Mario Party 4.iso").write_bytes(b"x" * 100)
        (folder / "hack/Mario Party 4 (DX).iso").write_bytes(b"x" * 500)
        (folder / "Mario Party 4.m3u").write_text("._.DS_Store\nhack/Mario Party 4 (DX).iso\nMario Party 4.iso\n")
        (folder / "._.DS_Store").write_bytes(b"x" * 1000)
        link = a["launchable"](folder, "gc")
        self.assertEqual(link, box.data / "roms/gc/Mario Party 4.iso")
        self.assertEqual(os.readlink(link), "Mario Party 4/Mario Party 4.iso")
        self.assertTrue((folder / "noload.txt").exists())
        self.assertEqual(a["launchable"](link, "gc"), link)       # a plain file is itself
        self.assertEqual(a["launchable"](folder, "gc"), link)     # again: same link

    def test_gamecube_ids_from_romm(self):
        a = Box(self.base, "alice").agent()
        self.assertEqual(a["romm_title_id"]("gc", "474D5045"), "GMPE")
        self.assertEqual(a["romm_title_id"]("gc", "GMPE01"), "GMPE01")
        self.assertEqual(a["romm_title_id"]("switch", "0100000000010000"), "0100000000010000")
        # A short one is completed from the disc; a full one from RomM is kept.
        a["derive_id"] = lambda system, path: "GMPE01"
        a["title_id"].__globals__["derive_id"] = a["derive_id"]
        self.assertEqual(a["title_id"]("gc", {"title_id": "474D5045"}, {}, "x.iso"), "GMPE01")
        self.assertEqual(a["title_id"]("gc", {"title_id": "GALE01"}, {}, "x.iso"), "GALE01")

    def test_single_file_in_its_own_folder(self):
        # RomM keeps "Mario Party 7/Mario Party 7.iso" as a single-file ROM
        # whose fs_name is the folder's.
        box = Box(self.base, "alice")
        a = box.agent()
        got = []
        a["fetch_rom"].__globals__["download"] = lambda s, path, dest, *rest, **kw: got.append((path, dest))
        rom = {"id": 222, "fs_name": "Mario Party 7", "has_multiple_files": False,
               "files": [{"file_name": "Mario Party 7.iso"}]}
        gc = box.data / "roms/gc"
        gc.mkdir(parents=True)
        (gc / "Mario Party 7").write_bytes(b"pulled before")
        dest = a["fetch_rom"](None, rom, "gc")
        self.assertEqual(dest, gc / "Mario Party 7.iso")
        self.assertEqual(dest.read_bytes(), b"pulled before")      # renamed, not fetched again
        self.assertEqual(got, [("/roms/222/content/Mario Party 7", gc / "Mario Party 7.iso")])
        # From RomM's ROM list, `files` comes empty: the ROM's own page has it.
        (gc / "Shrek Superslam").write_bytes(b"pulled before")
        a["fetch_rom"].__globals__["get"] = lambda s, path, **kw: type("R", (), {
            "json": lambda self: {"files": [{"file_name": "Shrek SuperSlam.iso"}]} if path == "/roms/245" else {}})()
        rom = {"id": 245, "fs_name": "Shrek Superslam", "has_multiple_files": False,
               "has_nested_single_file": True, "files": []}
        self.assertEqual(a["fetch_rom"](None, rom, "gc"), gc / "Shrek SuperSlam.iso")
        self.assertEqual((gc / "Shrek SuperSlam.iso").read_bytes(), b"pulled before")
        # A dot in the name isn't an extension; RomM's fs_extension says.
        (gc / "Super Smash Bros. Melee").write_bytes(b"pulled before")
        rom = {"id": 254, "fs_name": "Super Smash Bros. Melee", "fs_extension": "", "has_multiple_files": False,
               "files": [{"file_name": "Super Smash Bros. Melee.iso"}]}
        self.assertEqual(a["fetch_rom"](None, rom, "gc"), gc / "Super Smash Bros. Melee.iso")
        # A file named with its extension stays as it is.
        rom = {"id": 1, "fs_name": "Game.sfc", "fs_extension": "sfc", "has_multiple_files": False, "files": [{"file_name": "Game.sfc"}]}
        self.assertEqual(a["fetch_rom"](None, rom, "gc"), gc / "Game.sfc")

    def test_a_folder_with_extras_downloads_only_the_game(self):
        box = Box(self.base, "library", tokenFile=None)
        a = box.agent()
        got = []
        g = a["fetch_rom"].__globals__
        g["download"] = lambda s, path, dest, sha1=None, size=None, params=None: got.append((path, dest.name, sha1, size, params))
        files = [{"id": 187, "file_name": "AC HD Texture Pack.zip", "sha1_hash": "aaa", "file_size_bytes": 90},
                 {"id": 188, "file_name": "Animal Crossing (USA) (Deluxe).iso", "sha1_hash": "bbb", "file_size_bytes": 34},
                 {"id": 189, "file_name": "Animal Crossing.ciso", "sha1_hash": "ccc", "file_size_bytes": 31}]
        rom = {"id": 186, "fs_name": "Animal Crossing", "fs_extension": "", "has_nested_single_file": True,
               "has_multiple_files": False, "sha1_hash": "ccc", "fs_size_bytes": 156, "files": files}
        dest = a["fetch_rom"](None, rom, "gc")
        self.assertEqual(dest.name, "Animal Crossing.ciso")
        self.assertEqual(got, [("/roms/186/content/Animal Crossing.ciso", "Animal Crossing.ciso", "ccc", 31,
                                {"file_ids": 189})])

    def test_hex_id_kept_from_an_earlier_pull_is_fixed(self):
        a = Box(self.base, "alice").agent()
        a["title_id"].__globals__["derive_id"] = lambda system, path: "GP7E01"
        self.assertEqual(a["title_id"]("gc", {"title_id": "47503745"}, {"title_id": "47503745"}, "x.iso"), "GP7E01")
        self.assertEqual(a["title_id"]("gc", {"title_id": "47503745"}, {"title_id": "GP7E01"}, "x.iso"), "GP7E01")

    def test_times_compared_as_times(self):
        a = Box(self.base, "alice").agent()
        self.assertTrue(a["same_time"]("2026-10-06T08:55:20.372044+00:00", "2026-10-06T03:55:20.372044-05:00"))
        self.assertFalse(a["same_time"]("2026-10-06T08:55:20+00:00", "2026-10-06T08:56:20+00:00"))
        self.assertFalse(a["same_time"](None, "2026-10-06T08:55:20+00:00"))

    def test_unpushed_local_save(self):
        box = Box(self.base, "alice")
        a = box.agent()
        card = box.home / ".local/share/dolphin-emu/GC/USA/Card A"
        card.mkdir(parents=True)
        (card / "01-GMPE-MARIPA4BOX0.gci").write_bytes(b"v1")
        _, root, lay = a["layout"]("gc")
        entry = {"title_id": "GMPE01"}
        digest = a["files_hash"](root, ["USA/Card A/01-GMPE-MARIPA4BOX0.gci"], lay)
        self.assertTrue(a["unpushed"]("gc", entry, root, lay, "x.iso"))     # never pushed
        entry["pushed"] = digest
        self.assertFalse(a["unpushed"]("gc", entry, root, lay, "x.iso"))    # RomM has it
        (card / "01-GMPE-MARIPA4BOX0.gci").write_bytes(b"v2")
        self.assertTrue(a["unpushed"]("gc", entry, root, lay, "x.iso"))     # played since

    def test_conflict_copy_uploaded_once(self):
        # RomM has a newer save from another box; this box's changed too.
        box = Box(self.base, "alice")
        a = box.agent()
        key = str(box.data / "roms/gc/Mario Party 4.iso")
        a["save_index"]({key: {"id": 216, "system": "gc", "title_id": "GMPE01"}})
        a["store_saves"]({key: {"pushed": "old", "server_updated_at": "2026-10-06T08:00:00+00:00"}})
        card = box.home / ".local/share/dolphin-emu/GC/USA/Card A"
        card.mkdir(parents=True)
        (card / "01-GMPE-MARIPA4BOX0.gci").write_bytes(b"mine")
        posts = []

        class Resp:
            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

            def raise_for_status(self):
                pass

        class Session:
            def post(self, url, params, **kw):
                posts.append(params["slot"])
                assert params["autocleanup"] == "true" and params["autocleanup_limit"] == 3, params
                return Resp({"updated_at": "2026-10-06T09:30:00+00:00"})
        g = a["cmd_save_push"].__globals__
        g["session"] = lambda: Session()
        g["device_id"] = lambda s: "dev"
        g["server_save"] = lambda s, dev, rom_id: {"updated_at": "2026-10-06T09:00:00+00:00"}
        a["cmd_save_push"]("gc", key, learn=False)
        a["cmd_save_push"]("gc", key, learn=False)      # the next reconcile
        self.assertEqual(posts, ["famidrive-conflict-box"])
        (card / "01-GMPE-MARIPA4BOX0.gci").write_bytes(b"mine, played more")
        a["cmd_save_push"]("gc", key, learn=False)      # changed again: a new copy
        self.assertEqual(posts, ["famidrive-conflict-box", "famidrive-conflict-box"])

    def test_save_state_follows_a_rename(self):
        box = Box(self.base, "alice")
        a = box.agent()
        gc = box.data / "roms/gc"
        new7, newm = str(gc / "Mario Party 7.iso"), str(gc / "Super Smash Bros. Melee.iso")
        a["save_index"]({new7: {"id": 222, "system": "gc", "title_id": "GP7E01"},
                         newm: {"id": 254, "system": "gc", "title_id": "GALE01"}})
        # State from before the rename: one from before ids were kept, one with.
        a["store_saves"]({str(gc / "Mario Party 7"): {"pushed": "a", "server_updated_at": "t7"},
                          str(gc / "Melee, old name"): {"id": 254, "pushed": "b", "server_updated_at": "tm"}})
        self.assertEqual(a["entry_for"](new7)["server_updated_at"], "t7")
        self.assertEqual(a["entry_for"](newm)["server_updated_at"], "tm")
        saves = a["load_saves"]()
        self.assertEqual(a["my_state"](saves, new7, 222)["pushed"], "a")
        self.assertNotIn(str(gc / "Mario Party 7"), saves)       # moved, not copied
        # The new name already has state of its own (a conflict copy pushed
        # before the fix): the sync from before the rename is merged in.
        news = str(gc / "Shrek Superslam.iso")
        a["save_index"]({news: {"id": 245, "system": "gc", "title_id": "G2RE52"}})
        a["store_saves"]({str(gc / "Shrek Superslam"): {"pushed": "old", "server_updated_at": "t1"},
                          news: {"conflict_pushed": "c"}})
        e = a["entry_for"](news)
        self.assertEqual((e["server_updated_at"], e["pushed"], e["conflict_pushed"]), ("t1", "old", "c"))

    def test_app_saves_round_trip(self):
        # Clone Hero: fixed files under the home, under a RomM entry found
        # by name, and pushed by reconcile like any ROM's.
        paths = [".config/unity3d/srylain Inc_/Clone Hero/scoredata.bin", ".clonehero/profiles.ini"]
        box = Box(self.base, "alice", apps={"clonehero": {
            "rom": "Clone Hero", "emulator": "clonehero",
            "saveLayout": {"kind": "files", "root": "~", "paths": paths}}})
        a = box.agent()
        for rel in paths:
            (box.home / rel).parent.mkdir(parents=True, exist_ok=True)
            (box.home / rel).write_text(f"mine: {rel}")
        uploads, searches = [], []

        class Resp:
            def __init__(self, data=None, content=b""):
                self.data, self.content = data, content

            def json(self):
                return self.data

            def raise_for_status(self):
                pass

        class Session:
            def post(self, url, params, files, **kw):
                uploads.append((params["rom_id"], params["slot"], files["saveFile"][1]))
                return Resp({"updated_at": "2026-10-06T10:00:00+00:00"})
        g = a["cmd_save_push"].__globals__
        g["session"] = lambda: Session()
        g["device_id"] = lambda s: "dev"
        g["server_save"] = lambda s, dev, rom_id: None
        g["all_roms"] = lambda s, params: searches.append(params) or [
            {"id": 7, "name": "Clone Hero Live"}, {"id": 9, "name": "Clone Hero"}]
        a["cmd_reconcile"]()
        a["cmd_reconcile"]()                     # unchanged: not sent again
        self.assertEqual([(r, s) for r, s, _ in uploads], [(9, "famidrive")])
        self.assertEqual(len(searches), 1)       # the id is kept
        # Another box: the archive unpacks to the same places.
        other = Box(self.base, "alice-elsewhere", apps=box.cfg["apps"])
        b = other.agent()
        g = b["cmd_save_pull"].__globals__
        g["session"] = lambda: Session()
        g["device_id"] = lambda s: "dev"
        g["app_id"] = lambda name: 9
        g["server_save"] = lambda s, dev, rom_id: {"id": 1, "updated_at": "2026-10-06T10:00:00+00:00"}
        g["get"] = lambda s, path, **kw: Resp(content=uploads[0][2])
        b["cmd_save_pull"]("clonehero", "app:clonehero")
        self.assertFalse(b["SNAPSHOT"].exists())   # no scan of the whole home
        for rel in paths:
            self.assertEqual((other.home / rel).read_text(), f"mine: {rel}")

    def test_gamelist_has_romms_metadata_and_keeps_the_players(self):
        box = Box(self.base, "alice")
        a = box.agent()
        melee = {"id": 254, "name": "Super Smash Bros. Melee", "summary": "Fight & win",
                 "metadatum": {"genres": ["Fighting", "Platform"], "developers": ["HAL Laboratory"],
                               "publishers": ["Nintendo"], "player_count": "1-4",
                               "first_release_date": 1006300800000, "average_rating": 94.37}}
        a["write_gamelist"]("gc", [(Path("Super Smash Bros. Melee.iso"), melee)])
        lib = box.data / "gamelists/gc/gamelist.xml"
        game = {c.tag: c.text for c in __import__("xml.etree.ElementTree").etree.ElementTree.parse(lib).getroot().find("game")}
        self.assertEqual(game["path"], "./Super Smash Bros. Melee.iso")
        self.assertEqual(game["desc"], "Fight & win")
        self.assertEqual((game["genre"], game["developer"], game["publisher"], game["players"]),
                         ("Fighting, Platform", "HAL Laboratory", "Nintendo", "1-4"))
        self.assertEqual((game["releasedate"], game["rating"]), ("20011121T000000", "0.94"))
        # The player's copy: an old scraped name, a favorite, play counts,
        # a game only they have, and a folder entry.
        mine = box.home / "ES-DE/gamelists/gc/gamelist.xml"
        mine.parent.mkdir(parents=True)
        mine.write_text("<gameList><game><path>./Super Smash Bros. Melee.iso</path><name>Melee (scraped)</name>"
                        "<favorite>true</favorite><playcount>12</playcount></game>"
                        "<game><path>./Homebrew.dol</path><name>Homebrew</name></game>"
                        "<folder><path>./Hacks</path><name>Hacks</name></folder></gameList>")
        merged = __import__("xml.etree.ElementTree").etree.ElementTree.fromstring(a["merge_gamelist"](lib, mine))
        games = {g.findtext("path"): g for g in merged.findall("game")}
        self.assertEqual(games["./Super Smash Bros. Melee.iso"].findtext("name"), "Super Smash Bros. Melee")
        self.assertEqual(games["./Super Smash Bros. Melee.iso"].findtext("favorite"), "true")
        self.assertEqual(games["./Super Smash Bros. Melee.iso"].findtext("playcount"), "12")
        self.assertEqual(len(games["./Super Smash Bros. Melee.iso"].findall("name")), 1)
        self.assertIn("./Homebrew.dol", games)
        self.assertEqual(merged.find("folder").findtext("name"), "Hacks")

    def test_media_in_esdes_layout_with_romms_cover_link_as_fallback(self):
        box = Box(self.base, "library", tokenFile=None)
        a = box.agent()
        asked = []

        class Resp:
            def __init__(self, code, kind, body=b""):
                self.status_code, self.headers, self.content = code, {"content-type": kind}, body

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise a["requests"].HTTPError(str(self.status_code))

        def fake_get(url, timeout=None, **kw):
            asked.append(url)
            if url.endswith("cover/big.png") or url.endswith("cover/small.png"):
                return Resp(404, "text/html")      # RomM lists it, has no file
            if "steamgriddb" in url:
                return Resp(200, "image/png", b"cover")
            return Resp(200, "image/jpeg", b"shot")

        class Session:
            get = staticmethod(fake_get)
        g = a["fetch_media"].__globals__
        g["requests"] = type("R", (), {"get": staticmethod(fake_get), "RequestException": Exception})
        rom = {"id": 254, "updated_at": "t1",
               "path_cover_large": "/assets/romm/resources/roms/19/254/cover/big.png?ts=x",
               "path_cover_small": "/assets/romm/resources/roms/19/254/cover/small.png?ts=x",
               "url_cover": "https://cdn2.steamgriddb.com/grid/abc.png",
               "merged_screenshots": ["/assets/romm/resources/roms/19/254/screenshots/0.jpg"]}
        a["fetch_media"](Session(), rom, "gc", Path("Super Smash Bros. Melee.iso"))
        media = box.data / "media/gc"
        self.assertEqual((media / "covers/Super Smash Bros. Melee.png").read_bytes(), b"cover")
        self.assertEqual((media / "screenshots/Super Smash Bros. Melee.jpg").read_bytes(), b"shot")
        self.assertNotIn("?ts", "".join(asked))
        asked.clear()
        a["fetch_media"](Session(), rom, "gc", Path("Super Smash Bros. Melee.iso"))
        self.assertEqual(asked, [])                 # unchanged in RomM: not fetched again

    def test_gamecube_saves_found_by_id(self):
        box = Box(self.base, "alice")
        a = box.agent()
        card = box.home / ".local/share/dolphin-emu/GC/USA/Card A"
        card.mkdir(parents=True)
        (card / "01-GMPE-MARIPA4BOX0.gci").write_bytes(b"s")
        (card / "01-GALE-SuperSmashBros0110290334.gci").write_bytes(b"s")
        self.assertEqual(a["save_paths"]("gc", {"title_id": "GMPE01"}, "x.iso"), ["USA/Card A/01-GMPE-MARIPA4BOX0.gci"])
        self.assertEqual(a["save_paths"]("gc", {"title_id": "GMPE"}, "x.iso"), ["USA/Card A/01-GMPE-MARIPA4BOX0.gci"])

    def test_rom_paths_from_a_players_folder(self):
        box = Box(self.base, "alice")
        a = box.agent()
        mine = box.home / ".local/share/famidrive/roms/snes/Game.sfc"
        self.assertEqual(a["library_path"](str(mine)), str(box.data / "roms/snes/Game.sfc"))
        self.assertEqual(a["library_path"](str(box.data / "roms/snes/Game.sfc")), str(box.data / "roms/snes/Game.sfc"))

    def test_save_state_is_per_player(self):
        alice, bob = Box(self.base, "alice"), Box(self.base, "bob")
        key = str(alice.data / "roms/snes/Game.sfc")
        a = alice.agent()
        a["save_index"]({key: {"id": 7, "system": "snes", "title_id": None}})
        a["store_saves"]({key: {"pushed": "abc", "learned": ["Game.srm"]}})
        self.assertEqual(a["entry_for"](key)["pushed"], "abc")
        self.assertTrue(str(a["SAVES"]).startswith(str(alice.home)))
        b = bob.agent()
        self.assertIsNone(b["entry_for"](key).get("pushed"))
        self.assertEqual(b["entry_for"](key)["id"], 7)

    def test_gamelists_merged_once_per_library_change(self):
        box = Box(self.base, "alice")
        a = box.agent()
        src = box.data / "gamelists/snes/gamelist.xml"
        src.parent.mkdir(parents=True)
        game = "<gameList><game><path>./a.sfc</path><name>{}</name></game></gameList>"
        src.write_text(game.format("v1"))
        a["cmd_gamelists"]()
        dest = box.home / "ES-DE/gamelists/snes/gamelist.xml"
        self.assertIn("<name>v1</name>", dest.read_text())
        # ES-DE's own edits (favorites, play counts) survive...
        dest.write_text("<gameList><game><path>./a.sfc</path><name>v1</name>"
                        "<favorite>true</favorite></game></gameList>")
        a["cmd_gamelists"]()
        self.assertIn("<favorite>true</favorite>", dest.read_text())
        # ...and the library's next one is merged in, keeping them.
        src.write_text(game.format("v2"))
        os.utime(src, (src.stat().st_atime, src.stat().st_mtime + 10))
        a["cmd_gamelists"]()
        self.assertIn("<name>v2</name>", dest.read_text())
        self.assertIn("<favorite>true</favorite>", dest.read_text())

    def texture_zip(self, path, names):
        import zipfile
        with zipfile.ZipFile(path, "w") as z:
            for n in names:
                z.writestr(n, n.encode())

    def test_texture_packs_unpacked_with_or_without_their_id_folder(self):
        box = Box(self.base, "library", tokenFile=None)
        a = box.agent()
        with_id, without, other = (self.base / n for n in ("a.zip", "b.zip", "c.zip"))
        self.texture_zip(with_id, ["GAFE01/tex1_64x64_aa.png", "GAFE01/sub/tex1_8x8_bb.png"])
        self.texture_zip(without, ["tex1_64x64_cc.png", "__MACOSX/._tex1_64x64_cc.png"])
        self.texture_zip(other, ["Riivolution/patch.xml"])
        dest = box.data / "textures/gc/GAFE01"
        self.assertTrue(a["unpack_textures"](with_id, dest / "A"))
        self.assertTrue((dest / "A/tex1_64x64_aa.png").exists())
        self.assertTrue((dest / "A/sub/tex1_8x8_bb.png").exists())
        self.assertTrue(a["unpack_textures"](without, dest / "B"))
        self.assertTrue((dest / "B/tex1_64x64_cc.png").exists())
        self.assertFalse(a["unpack_textures"](other, dest / "C"))
        self.assertFalse((dest / "C").exists())

    def test_texture_packs_follow_romm(self):
        box = Box(self.base, "library", tokenFile=None)
        a = box.agent()
        zips = {}
        files = [{"id": 33013, "category": "mod", "file_name": "ac hd textures v17.zip", "sha1_hash": "s1"},
                 {"id": 33011, "category": "mod", "file_name": ".nfs.20051657.b4b8", "sha1_hash": "x"},
                 {"id": 189, "category": "game", "file_name": "Animal Crossing.ciso", "sha1_hash": "g"}]
        rom = {"id": 186, "fs_name": "Animal Crossing", "updated_at": "t1"}

        class Resp:
            def json(self):
                return {"files": files}
        g = a["sync_textures"].__globals__
        g["get"] = lambda s, path, **kw: Resp()
        g["download"] = lambda s, path, dest, sha1=None, size=None, params=None: (
            zips.setdefault("asked", []).append((path, params)),
            dest.parent.mkdir(parents=True, exist_ok=True),
            self.texture_zip(dest, ["GAFE01/tex1_1x1_" + sha1 + ".png"]))
        a["sync_textures"](None, rom, "gc", "GAFE01")
        pack = box.data / "textures/gc/GAFE01/ac hd textures v17"
        self.assertTrue((pack / "tex1_1x1_s1.png").exists())
        self.assertEqual(zips["asked"], [("/roms/186/content/ac hd textures v17.zip", {"file_ids": 33013})])
        a["sync_textures"](None, rom, "gc", "GAFE01")          # unchanged in RomM: nothing asked
        self.assertEqual(len(zips["asked"]), 1)
        files[0]["sha1_hash"] = "s2"                            # a new version of the pack
        a["sync_textures"](None, dict(rom, updated_at="t2"), "gc", "GAFE01")
        self.assertTrue((pack / "tex1_1x1_s2.png").exists())
        self.assertFalse((pack / "tex1_1x1_s1.png").exists())
        del files[0]                                            # gone from RomM
        a["sync_textures"](None, dict(rom, updated_at="t3"), "gc", "GAFE01")
        self.assertFalse((box.data / "textures/gc/GAFE01").exists())

    def test_texture_packs_linked_into_each_players_dolphin(self):
        box = Box(self.base, "alice")
        shared = box.data / "textures/gc/GAFE01/pack"
        shared.mkdir(parents=True)
        a = box.agent()
        mine = box.home / ".local/share/dolphin-emu/Load/Textures"
        (mine / "GAF").mkdir(parents=True)                      # set up by hand before
        (mine / "GAF/tex1_old.png").write_text("old")
        (mine / "GUG").mkdir()                                  # another game's: untouched
        a["cmd_textures"]()
        self.assertEqual(Path(os.readlink(mine / "GAFE01")), box.data / "textures/gc/GAFE01")
        self.assertFalse((mine / "GAF").exists())
        self.assertEqual((mine.parent / "Textures-before-romm/GAF/tex1_old.png").read_text(), "old")
        self.assertTrue((mine / "GUG").is_dir())
        import shutil
        shutil.rmtree(box.data / "textures/gc/GAFE01")          # the library dropped it
        a["cmd_textures"]()
        self.assertFalse(os.path.lexists(mine / "GAFE01"))

    def test_an_archive_is_checked_by_size_not_romms_hash(self):
        box = Box(self.base, "library", tokenFile=None)
        a = box.agent()

        class Resp:
            status_code = 200

            def __enter__(self):
                return self

            def __exit__(self, *e):
                pass

            def raise_for_status(self):
                pass

            def iter_content(self, n):
                yield b"zipbytes"

        class Session:
            def get(self, *a, **kw):
                return Resp()
        dest = self.base / "pack.zip"
        # RomM's hash is of what's inside: it never matches the zip's own.
        self.assertTrue(a["download"](Session(), "/x", dest, "inner-hash", 8))
        self.assertEqual(dest.read_bytes(), b"zipbytes")
        with self.assertRaises(RuntimeError):
            a["download"](Session(), "/x", self.base / "short.zip", "inner-hash", 9)
        with self.assertRaises(RuntimeError):               # a ROM's hash still counts
            a["download"](Session(), "/x", self.base / "game.iso", "not-its-hash", 8)

    def test_library_token_from_systemd(self):
        box = Box(self.base, "library", tokenFile=None)
        creds = self.base / "creds"
        creds.mkdir()
        (creds / "romm-token").write_text("rmm_secret\n")
        a = box.agent()
        os.environ["CREDENTIALS_DIRECTORY"] = str(creds)
        try:
            self.assertEqual(a["session"]().headers["Authorization"], "Bearer rmm_secret")
        finally:
            del os.environ["CREDENTIALS_DIRECTORY"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
