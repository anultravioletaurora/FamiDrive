"""famidrive-ryujinx: Ryujinx's config and the save bridge, without Ryujinx.

    python3 ryujinx_test.py path/to/famidrive_ryujinx.py

Each test runs the tool as a player with their own home. romm-agent is a
stand-in on PATH that prints where Eden keeps the game's save.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
SMASH = "01006A800016E000"


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.ryu = self.home / ".config/Ryujinx"
        self.eden = self.home / "eden-save" / SMASH
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        agent = bin_dir / "romm-agent"
        agent.write_text(f"#!/bin/sh\necho {self.eden}\n")
        agent.chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        self.env.pop("XDG_STATE_HOME", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def ryujinx_save(self, files, n="0000000000000001"):
        d = self.ryu / "bis/user/save" / n
        (d / "0").mkdir(parents=True)
        (d / "ExtraData0").write_bytes(int(SMASH, 16).to_bytes(8, "little") + bytes(56))
        for name, text in files.items():
            (d / "0" / name).write_text(text)
        return d

    def test_setup_keeps_the_players_settings_and_sets_famidrives(self):
        defaults = self.home / "defaults.json"
        defaults.write_text(json.dumps({"version": 70, "res_scale": 1, "start_fullscreen": False,
                                        "input_config": [{"backend": "WindowKeyboard"}]}))
        keys = self.home / ".local/share/eden/keys"
        keys.mkdir(parents=True)
        (keys / "prod.keys").write_text("header_key = 00")
        firmware = self.home / ".local/share/eden/nand/system/Contents/registered"
        firmware.mkdir(parents=True)
        (firmware / "abc.nca").write_bytes(b"nca")
        spec = {"library": "/lib/switch", "faceButtons": "labels", "edenKeys": "~/.local/share/eden/keys",
                "edenFirmware": "~/.local/share/eden/nand/system/Contents/registered",
                "defaults": str(defaults), "sdl": "/nonexistent/libSDL2.so"}
        self.run_tool("setup", json.dumps(spec))
        cfg = json.loads((self.ryu / "Config.json").read_text())
        self.assertEqual(cfg["game_dirs"], ["/lib/switch"])
        self.assertTrue(cfg["start_fullscreen"])
        self.assertEqual(cfg["res_scale"], 1)
        self.assertEqual(cfg["input_config"], [{"backend": "WindowKeyboard"}])   # no pads seen: left alone
        self.assertEqual((self.ryu / "system/prod.keys").read_text(), "header_key = 00")
        self.assertEqual((self.ryu / "bis/system/Contents/registered/abc.nca/00").read_bytes(), b"nca")
        cfg["res_scale"] = 2                                                     # the player's own change
        (self.ryu / "Config.json").write_text(json.dumps(cfg))
        self.run_tool("setup", json.dumps(spec))
        self.assertEqual(json.loads((self.ryu / "Config.json").read_text())["res_scale"], 2)

    def test_a_pads_buttons_follow_face_buttons(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fr", SCRIPT)
        fr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fr)
        labels = fr.pad_config("0-x", "8BitDo Ultimate 2", 1, "labels")["right_joycon"]
        self.assertEqual((labels["button_a"], labels["button_b"]), ("A", "B"))
        positions = fr.pad_config("0-x", "8BitDo Ultimate 2", 1, "positions")["right_joycon"]
        self.assertEqual((positions["button_a"], positions["button_b"]), ("B", "A"))

    def test_the_save_goes_into_ryujinx_and_comes_back(self):
        self.eden.mkdir(parents=True)
        (self.eden / "save.dat").write_text("unlocked everything")
        ryu = self.ryujinx_save({"save.dat": "old"})
        (ryu / "1").mkdir()
        self.run_tool("save-in", SMASH)
        self.assertEqual((ryu / "0/save.dat").read_text(), "unlocked everything")
        self.assertFalse((ryu / "1").exists())
        (ryu / "0/save.dat").write_text("played in Ryujinx")
        self.run_tool("save-out", SMASH)
        self.assertEqual((self.eden / "save.dat").read_text(), "played in Ryujinx")

    def test_a_first_run_doesnt_replace_the_players_save(self):
        self.eden.mkdir(parents=True)
        (self.eden / "save.dat").write_text("unlocked everything")
        self.run_tool("save-in", SMASH)                    # Ryujinx has no save for it yet
        ryu = self.ryujinx_save({"save.dat": "fresh"})     # the game makes one
        r = self.run_tool("save-out", SMASH)
        self.assertIn("first run", r.stderr)
        self.assertEqual((self.eden / "save.dat").read_text(), "unlocked everything")
        self.assertEqual((ryu / "0/save.dat").read_text(), "unlocked everything")


if __name__ == "__main__":
    unittest.main()
