"""famidrive-steam-config, against made-up Steam config files.

    python3 steam_config_test.py path/to/famidrive_steam_config.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1))

CONFIG = """"InstallConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"CompatToolMapping"
\t\t\t\t{
\t\t\t\t\t"252950"
\t\t\t\t\t{
\t\t\t\t\t\t"name"\t\t"proton_9"
\t\t\t\t\t\t"config"\t\t""
\t\t\t\t\t\t"priority"\t\t"250"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}"""

LOCALCONFIG = """"UserLocalConfigStore"
{
\t"apps"
\t{
\t\t"550"
\t\t{
\t\t\t"UseSteamControllerConfig"\t\t"2"
\t\t}
\t}
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"892970"
\t\t\t\t\t{
\t\t\t\t\t\t"LaunchOptions"\t\t"old"
\t\t\t\t\t\t"Playtime"\t\t"100"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}"""


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        steam = self.home / ".local/share/Steam"
        (steam / "config").mkdir(parents=True)
        (steam / "config/config.vdf").write_text(CONFIG)
        (steam / "userdata/1/config").mkdir(parents=True)
        (steam / "userdata/1/config/localconfig.vdf").write_text(LOCALCONFIG)
        (steam / "steamapps").mkdir()
        for appid, name in [("252950", "Rocket League"), ("550", "Left 4 Dead 2"),
                            ("892970", "Valheim"), ("1493710", "Proton Experimental")]:
            (steam / f"steamapps/appmanifest_{appid}.acf").write_text(
                f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n}}\n')
        self.config = steam / "config/config.vdf"
        self.local = steam / "userdata/1/config/localconfig.vdf"

    def tearDown(self):
        self.tmp.cleanup()

    def run_settings(self, settings):
        r = subprocess.run([sys.executable, str(SCRIPT), json.dumps(settings)],
                           env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def block(self, text, key):
        lines = text.split("\n")
        i = next(n for n, line in enumerate(lines) if line.strip() == f'"{key}"')
        depth, out = 0, []
        for line in lines[i + 1:]:
            depth += line.count("{") - line.count("}")
            out.append(line)
            if depth == 0:
                break
        return "\n".join(out)

    def test_compat_tool_by_name(self):
        self.run_settings({"compatTools": {"Rocket League": "proton_experimental"}})
        text = self.config.read_text()
        self.assertIn('"name"\t\t"proton_experimental"', self.block(text, "252950"))
        self.assertNotIn("proton_9", text)
        self.assertTrue(self.config.with_name("config.vdf.famidrive-backup").exists())

    def test_steam_input_off_except_listed(self):
        self.run_settings({"steamInput": False, "steamInputGames": ["Left 4 Dead 2"]})
        text = self.local.read_text()
        self.assertIn('"UseSteamControllerConfig"\t\t"2"', self.block(text, "550"))
        valheim = text.split('"apps"')[1]   # the depth-1 apps block comes first
        self.assertIn('"892970"', valheim.split('"Software"')[0])
        self.assertNotIn('"1493710"', text)   # Steam's own tools aren't games

    def test_launch_options_in_steams_block(self):
        self.run_settings({"launchOptions": {"Valheim": './start_game_bepinex.sh %command%',
                                             "252950": 'A="b" %command%'}})
        text = self.local.read_text()
        steam_apps = text.split('"Software"')[1]
        self.assertIn('"LaunchOptions"\t\t"./start_game_bepinex.sh %command%"', steam_apps)
        self.assertIn('"Playtime"\t\t"100"', steam_apps)
        self.assertIn('"LaunchOptions"\t\t"A=\\"b\\" %command%"', steam_apps)
        self.assertNotIn("LaunchOptions", text.split('"Software"')[0])

    def test_launch_options_taken_out_are_cleared(self):
        self.run_settings({"launchOptions": {"Valheim": "./start_game_bepinex.sh %command%"}})
        self.run_settings({"launchOptions": {}})
        steam_apps = self.local.read_text().split('"Software"')[1]
        self.assertIn('"LaunchOptions"\t\t""', steam_apps)
        self.assertIn('"Playtime"\t\t"100"', steam_apps)

    def test_launch_options_changed_in_steam_stay(self):
        self.run_settings({"launchOptions": {"Valheim": "./start_game_bepinex.sh %command%"}})
        self.local.write_text(self.local.read_text().replace("./start_game_bepinex.sh %command%", "mine"))
        self.run_settings({"launchOptions": {}})
        self.assertIn('"LaunchOptions"\t\t"mine"', self.local.read_text())

    def test_launch_options_never_set_stay(self):
        self.run_settings({"launchOptions": {}})
        self.assertIn('"LaunchOptions"\t\t"old"', self.local.read_text())

    def test_unchanged_files_untouched(self):
        self.run_settings({"launchOptions": {"Not Installed": "x"}})
        self.assertEqual(self.local.read_text(), LOCALCONFIG)
        self.assertFalse(self.local.with_name("localconfig.vdf.famidrive-backup").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
