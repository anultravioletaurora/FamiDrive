"""famidrive-valheim, against a made-up Steam install and Thunderstore zips.

    python3 valheim_test.py path/to/famidrive_valheim.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1))


def zip_of(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return str(path)


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        apps = self.home / ".local/share/Steam/steamapps"
        (apps / "common/Valheim").mkdir(parents=True)
        (apps / "appmanifest_892970.acf").write_text('"AppState"\n{\n\t"appid"\t\t"892970"\n\t"installdir"\t\t"Valheim"\n}\n')
        self.game = apps / "common/Valheim"
        self.bepinex = zip_of(self.home / "bepinex.zip", {
            "BepInExPack_Valheim/start_game_bepinex.sh": "#!/bin/sh\n",
            "BepInExPack_Valheim/BepInEx/core/BepInEx.dll": "core",
            "BepInExPack_Valheim/BepInEx/plugins/Shipped/Shipped.dll": "shipped",
            "manifest.json": "{}",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def run_spec(self, mods, only_listed=True):
        spec = {"bepinex": {"version": "5.4.2351", "zip": self.bepinex}, "mods": mods, "onlyListed": only_listed}
        r = subprocess.run([sys.executable, str(SCRIPT), json.dumps(spec)],
                           env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stderr

    def test_install(self):
        mod = zip_of(self.home / "mod.zip", {
            "plugins\\Mod.dll": "mod",            # zipped on Windows
            "config/mod.cfg": "default",
            "manifest.json": "{}", "icon.png": "", "README.md": "",
            "Extra.dll": "extra",
        })
        self.run_spec({"Someone-Mod-1.0.0": mod})
        bep = self.game / "BepInEx"
        self.assertTrue((self.game / "start_game_bepinex.sh").stat().st_mode & 0o111)
        self.assertEqual((bep / "core/BepInEx.dll").read_text(), "core")
        self.assertEqual((bep / "plugins/Someone-Mod/Mod.dll").read_text(), "mod")
        self.assertEqual((bep / "plugins/Someone-Mod/Extra.dll").read_text(), "extra")
        self.assertFalse((bep / "plugins/Someone-Mod/manifest.json").exists())
        self.assertEqual((bep / "config/mod.cfg").read_text(), "default")

    def test_config_kept_and_unlisted_turned_off(self):
        bep = self.game / "BepInEx"
        (bep / "config").mkdir(parents=True)
        (bep / "config/mod.cfg").write_text("mine")
        (bep / "plugins/Old").mkdir(parents=True)
        (bep / "plugins/.nextcloudsync.log").write_text("")
        mod = zip_of(self.home / "mod.zip", {"plugins/Mod.dll": "mod", "config/mod.cfg": "default"})
        self.run_spec({"Someone-Mod-1.0.0": mod})
        self.assertEqual((bep / "config/mod.cfg").read_text(), "mine")
        self.assertTrue((bep / "plugins-off/Old").is_dir())
        self.assertTrue((bep / "plugins/.nextcloudsync.log").exists())
        self.assertTrue((bep / "plugins/Shipped").is_dir())   # came with BepInEx

    def test_new_version_replaces_old(self):
        v1 = zip_of(self.home / "v1.zip", {"plugins/Old.dll": "1"})
        v2 = zip_of(self.home / "v2.zip", {"plugins/New.dll": "2"})
        self.run_spec({"Someone-Mod-1.0.0": v1})
        self.run_spec({"Someone-Mod-2.0.0": v2})
        plugin = self.game / "BepInEx/plugins/Someone-Mod"
        self.assertFalse((plugin / "Old.dll").exists())
        self.assertEqual((plugin / "New.dll").read_text(), "2")

    def test_not_installed(self):
        (self.home / ".local/share/Steam/steamapps/appmanifest_892970.acf").unlink()
        self.assertIn("isn't installed", self.run_spec({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
