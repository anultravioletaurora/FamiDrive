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
        a["fetch_rom"].__globals__["download"] = lambda s, path, dest, *rest: got.append((path, dest))
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
        # A file named with its extension stays as it is.
        rom = {"id": 1, "fs_name": "Game.sfc", "has_multiple_files": False, "files": [{"file_name": "Game.sfc"}]}
        self.assertEqual(a["fetch_rom"](None, rom, "gc"), gc / "Game.sfc")

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

    def test_gamelists_copied_once_per_library_change(self):
        box = Box(self.base, "alice")
        a = box.agent()
        src = box.data / "gamelists/snes/gamelist.xml"
        src.parent.mkdir(parents=True)
        src.write_text("<gameList>v1</gameList>")
        a["cmd_gamelists"]()
        dest = box.home / "ES-DE/gamelists/snes/gamelist.xml"
        self.assertEqual(dest.read_text(), "<gameList>v1</gameList>")
        # ES-DE's own edits (favorites, play counts) survive...
        dest.write_text("<gameList>favorites</gameList>")
        a["cmd_gamelists"]()
        self.assertEqual(dest.read_text(), "<gameList>favorites</gameList>")
        # ...until the library writes a new one.
        src.write_text("<gameList>v2</gameList>")
        os.utime(src, (src.stat().st_atime, src.stat().st_mtime + 10))
        a["cmd_gamelists"]()
        self.assertEqual(dest.read_text(), "<gameList>v2</gameList>")

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
