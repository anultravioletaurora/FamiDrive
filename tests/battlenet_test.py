"""famidrive-battlenet: a Battle.net game launched for the player.

    python3 battlenet_test.py path/to/famidrive_battlenet.py

Each test runs the tool against a made-up Lutris database, Battle.net
log and /proc, with a made-up nsenter that records what it was asked to
run and, like Battle.net, starts the game.
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()

READY = ("I [GSAccountProvider] {Main} Login triggered. entityId=1\n"
         "I [Frontend] {Main} Attempting to show main window.\n")
LAUNCH = "I [GameLaunchController] {Main} LaunchBinary: uid=zeus\n"


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lutris = self.root / "lutris"
        (self.lutris / "games").mkdir(parents=True)
        self.prefix = self.root / "Games/battlenet"
        self.logs = self.prefix / "drive_c/users/steamuser/AppData/Local/Battle.net/Logs"
        self.logs.mkdir(parents=True)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.sent = self.root / "sent"
        con = sqlite3.connect(self.lutris / "pga.db")
        con.execute("CREATE TABLE games (id INTEGER, slug TEXT, configpath TEXT)")
        con.executemany("INSERT INTO games VALUES (?, ?, ?)", [
            (1, "battlenet", "battlenet-standard-1"),
            (2, "call-of-duty-black-ops-cold-war", "cold-war-2"),
            (3, "hollow-knight", "hollow-knight-3"),
        ])
        con.commit()
        con.close()
        exe = "drive_c/Program Files (x86)/Battle.net/Battle.net.exe"
        self.config("battlenet-standard-1", f"game:\n  exe: drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe\n  prefix: {self.prefix}\n")
        self.config("cold-war-2", f"game:\n  args: --exec=\"launch ZEUS\"\n  exe: {exe}\n  prefix: {self.prefix}\n")
        self.config("hollow-knight-3", "game:\n  exe: hollow_knight.x86_64\n")
        # The running Battle.net, and one of its Chromium helpers.
        self.process(4190540, ["C:\\Program Files (x86)\\Battle.net\\Battle.net.exe", "--exec=launch ZEUS"],
                     [f"STEAM_COMPAT_DATA_PATH={self.prefix}", "WINESERVERSOCKET=17", "PATH=/proton/files/bin"])
        self.process(4192860, ["C:\\Program Files (x86)\\Battle.net\\Battle.net.exe", "--type=gpu-process"],
                     [f"STEAM_COMPAT_DATA_PATH={self.prefix}"])
        self.nsenter = self.root / "nsenter"
        self.nsenter.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> {self.sent}\necho ---- >> {self.sent}\n"
                                f"[ -e {self.root}/ignore ] || printf '{LAUNCH}' >> \"$(ls -t {self.logs}/battle.net-*.log | head -1)\"\n")
        self.nsenter.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, name, text):
        (self.lutris / "games" / f"{name}.yml").write_text(text)

    def process(self, pid, argv, env):
        d = self.proc / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        (d / "environ").write_bytes(b"\0".join(e.encode() for e in env) + b"\0")

    def log(self, text):
        (self.logs / "battle.net-20261015T064419.log").write_text(
            "I [Main] {Main} Command line arguments: {[0]=--exec=launch ZEUS}\n" + text)

    def run_tool(self, game_id):
        env = {**os.environ, "FAMIDRIVE_NSENTER": str(self.nsenter), "FAMIDRIVE_PROC": str(self.proc)}
        started = time.monotonic()
        r = subprocess.run([sys.executable, str(SCRIPT), "play", str(self.lutris), str(game_id)],
                           env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r, time.monotonic() - started

    def sends(self):
        return self.sent.read_text().split("----\n")[:-1] if self.sent.exists() else []

    def test_signed_in_battlenet_is_sent_the_launch_beside_itself(self):
        self.log(READY)
        self.run_tool(2)
        sends = self.sends()
        self.assertEqual(len(sends), 1)
        args = sends[0].splitlines()
        self.assertEqual(args[:6], ["-t", "4190540", "-U", "-m", "--preserve-credentials", "--"])
        self.assertIn(f"STEAM_COMPAT_DATA_PATH={self.prefix}", args)
        self.assertIn("PATH=/proton/files/bin", args)
        self.assertNotIn("WINESERVERSOCKET=17", args)   # the running Battle.net's own
        self.assertEqual(args[-3:], ["wine", "C:\\Program Files (x86)\\Battle.net\\Battle.net.exe", "--exec=launch ZEUS"])

    def test_tries_again_then_gives_up(self):
        self.log(READY)
        (self.root / "ignore").touch()
        r, _ = self.run_tool(2)
        self.assertEqual(len(self.sends()), 3)
        self.assertIn("didn't start the game", r.stderr)

    def test_nothing_when_battlenet_starts_the_game_itself(self):
        self.log(READY + LAUNCH)
        _, took = self.run_tool(2)
        self.assertEqual(self.sends(), [])
        self.assertLess(took, 5)

    def test_nothing_for_battlenet_itself_or_another_game(self):
        self.log(READY)
        for game in (1, 3, 99):
            _, took = self.run_tool(game)
            self.assertLess(took, 5)
        self.assertEqual(self.sends(), [])

    def test_nothing_once_battlenet_has_closed(self):
        self.log(READY)
        for d in self.proc.iterdir():
            for f in d.iterdir():
                f.unlink()
            d.rmdir()
        self.run_tool(2)
        self.assertEqual(self.sends(), [])


if __name__ == "__main__":
    unittest.main()
