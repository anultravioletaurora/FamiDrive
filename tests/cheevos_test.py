"""famidrive-cheevos: signing in, emulator settings and unlock toasts, offline.

    python3 cheevos_test.py path/to/famidrive_cheevos.py
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()


def load(home):
    os.environ["HOME"] = str(home)
    spec = importlib.util.spec_from_file_location("famidrive_cheevos", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.c = load(self.home)
        self.pw = self.home / "pw"
        self.pw.write_text("hunter2\n")
        self.spec = {"username": "alice", "passwordFile": str(self.pw), "hardcore": False,
                     "retroarch": True, "dolphin": True, "pcsx2": True}

    def tearDown(self):
        self.tmp.cleanup()

    def test_retroarch_keys_set_and_others_kept(self):
        cfg = self.home / ".config/retroarch/retroarch.cfg"
        cfg.parent.mkdir(parents=True)
        cfg.write_text('video_fullscreen = "true"\ncheevos_enable = "false"\ncheevos_hardcore_mode_enable = "true"\n')
        self.c.configure(self.spec, "TOKEN")
        text = cfg.read_text()
        self.assertIn('video_fullscreen = "true"', text)
        self.assertIn('cheevos_enable = "true"', text)
        self.assertIn('cheevos_token = "TOKEN"', text)
        self.assertIn('cheevos_hardcore_mode_enable = "false"', text)
        self.assertIn('cheevos_visibility_unlock = "false"', text)
        self.assertEqual(text.count("cheevos_enable"), 1)

    def test_ini_section_added_or_updated(self):
        ini = self.home / ".config/dolphin-emu/RetroAchievements.ini"
        self.c.configure(self.spec, "TOKEN")
        self.assertIn("[Achievements]\nEnabled = True\nUsername = alice\nApiToken = TOKEN\nHardcoreEnabled = False", ini.read_text())
        ini.write_text("[Other]\nA = 1\n[Achievements]\nApiToken = OLD\nProgressEnabled = True\n[Later]\nB = 2\n")
        self.c.configure({**self.spec, "hardcore": True}, "NEW")
        text = ini.read_text()
        self.assertIn("ApiToken = NEW", text)
        self.assertIn("ProgressEnabled = True", text)
        self.assertIn("HardcoreEnabled = True", text)
        self.assertLess(text.index("HardcoreEnabled"), text.index("[Later]"))
        self.assertIn("[Other]\nA = 1", text)
        logger = (self.home / ".config/dolphin-emu/Logger.ini").read_text()
        self.assertIn("RetroAchievements = True", logger)
        self.assertIn("WriteToFile = True", logger)
        self.assertIn("Verbosity = 4", logger)
        pcsx2 = (self.home / ".config/PCSX2/inis/PCSX2.ini").read_text()
        self.assertIn("Token = NEW", pcsx2)
        self.assertIn("ChallengeMode = true", pcsx2)

    def test_only_the_emulators_the_box_has(self):
        self.c.configure({**self.spec, "dolphin": False, "pcsx2": False}, "T")
        self.assertFalse((self.home / ".config/dolphin-emu").exists())
        self.assertFalse((self.home / ".config/PCSX2").exists())

    def test_last_token_when_unreachable(self):
        self.c.store_state({"username": "alice", "token": "CACHED"})
        self.assertEqual(os.stat(self.c.STATE).st_mode & 0o777, 0o600)

        def down(u, p):
            raise self.c.requests.ConnectionError("offline")
        self.c.login = down
        self.assertEqual(self.c.token_for(self.spec), "CACHED")
        # Someone else's token is never reused.
        self.assertIsNone(self.c.token_for({**self.spec, "username": "bob"}))

    def test_fresh_token_is_kept(self):
        self.c.login = lambda u, p: "FRESH" if (u, p) == ("alice", "hunter2") else None
        self.assertEqual(self.c.token_for(self.spec), "FRESH")
        self.assertEqual(json.loads(self.c.STATE.read_text()), {"username": "alice", "token": "FRESH"})

    def test_unlock_toast(self):
        info = {"Title": "Jiggy Wiggy", "Description": "Collect your first Jiggy", "Points": 5}
        self.assertEqual(self.c.toast_args(("12", "Jiggy Wiggy"), info, "Banjo-Kazooie", "/logo.png"),
                         ["--kind", "achievement", "--icon", "/logo.png", "Jiggy Wiggy", "Collect your first Jiggy · 5 points"])
        # Without RetroAchievements' details: the title from the log, the game's name.
        self.assertEqual(self.c.toast_args(("12", "Jiggy Wiggy"), None, "Banjo-Kazooie", None),
                         ["--kind", "achievement", "Jiggy Wiggy", "Banjo-Kazooie"])

    def test_an_unrecognized_copy_is_an_alert_not_an_unlock(self):
        args = self.c.unsupported_args("Unsupported Game Version (Super Smash Bros. Melee)")
        self.assertEqual(args[:3], ["--kind", "alert", "No achievements for this copy"])
        self.assertIn("Super Smash Bros. Melee", args[3])
        self.assertIsNone(self.c.unsupported_args("Super Smash Bros. Melee"))

    def test_watching_a_log(self):
        log = self.home / "dolphin.log"
        log.write_text(
            '05:28:277 Core/AchievementManager.cpp:79 I[RetroAchievements]: Identified game: 1000009602 '
            '"Unsupported Game Version (Super Smash Bros. Melee)" (cc1d)\n'
            "05:33:525 Core/AchievementManager.cpp:79 I[RetroAchievements]: Awarding achievement 101000001: Unsupported Game Version\n")
        self.c.store_state({"username": "alice", "token": "T"})
        sent = []
        self.c.subprocess.run = lambda args, **kw: sent.append(args)
        lines = iter(log.read_text().splitlines(keepends=True))
        self.c.follow = lambda path, stop: lines
        self.c.cmd_watch(str(log), "gc", "Melee.iso")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1:3], ["--kind", "alert"])

    def test_log_lines(self):
        self.assertEqual(self.c.AWARD.search("[INFO] [RCHEEVOS] Awarding achievement 12345: Jiggy Wiggy").groups(),
                         ("12345", "Jiggy Wiggy"))
        self.assertEqual(self.c.GAME.search('[INFO] [RCHEEVOS] Identified game: 10210 "Banjo-Kazooie" (abc)').groups(),
                         ("10210", "Banjo-Kazooie"))

    def test_logo_from_es_de_media(self):
        d = self.home / "ES-DE/downloaded_media/n64/marquees"
        d.mkdir(parents=True)
        (d / "Banjo-Kazooie (U) [!].png").write_bytes(b"")
        self.assertTrue(self.c.logo("n64", "/roms/n64/Banjo-Kazooie (U) [!].z64").endswith("Banjo-Kazooie (U) [!].png"))
        self.assertIsNone(self.c.logo("n64", "/roms/n64/Other.z64"))

    def test_no_account_no_watching(self):
        self.assertEqual(self.c.cmd_watch(str(self.home / "log"), "n64", "x.z64"), 0)


if __name__ == "__main__":
    unittest.main()
