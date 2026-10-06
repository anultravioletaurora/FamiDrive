"""famidrive-prism: instances per player, without Prism.

    python3 prism_test.py path/to/famidrive_prism.py

Each test runs the tool as a player with their own home.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()


def instance(**kw):
    return {"minecraft": "26.2", "fabricLoader": None, "servers": [], "join": None,
            "memory": None, "java": "/bin/java", "mods": [], **kw}


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.root = self.home / ".local/share/PrismLauncher"

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, instances, declared=()):
        spec = {"root": "~/.local/share/PrismLauncher", "launcher": {"CloseAfterLaunch": "true"},
                "instances": instances, "declared": list(declared)}
        r = subprocess.run([sys.executable, str(SCRIPT), json.dumps(spec)],
                           env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_instance_no_longer_theirs_is_moved_aside(self):
        self.run_tool({"Friends Server": instance(join="mc.example.org")})
        made = self.root / "instances/Friends Server"
        self.assertIn("JoinServerOnLaunchAddress=mc.example.org", (made / "instance.cfg").read_text())
        (made / ".minecraft/saves/My World").mkdir(parents=True)
        # One of the player's own, made in Prism: never touched.
        mine = self.root / "instances/My Own"
        mine.mkdir()
        self.run_tool({})
        self.assertFalse(made.exists())
        self.assertTrue(mine.exists())
        kept = list((self.root / "famidrive-removed").iterdir())
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].name.startswith("Friends Server ("))
        self.assertTrue((kept[0] / ".minecraft/saves/My World").is_dir())   # worlds kept

    def test_an_unmarked_one_declared_for_someone_else_is_moved_too(self):
        # Made before FamiDrive marked its instances: no .famidrive-instance.
        old = self.root / "instances/Friends Server"
        (old / ".minecraft").mkdir(parents=True)
        self.run_tool({}, declared=["Friends Server"])
        self.assertFalse(old.exists())
        self.assertEqual(len(list((self.root / "famidrive-removed").iterdir())), 1)

    def test_still_theirs_stays(self):
        self.run_tool({"Friends Server": instance()})
        self.run_tool({"Friends Server": instance()})
        self.assertTrue((self.root / "instances/Friends Server/instance.cfg").exists())
        self.assertFalse((self.root / "famidrive-removed").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
