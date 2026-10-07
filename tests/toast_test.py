"""famidrive-toast: the theme's colors, placement and the queue, without a display.

    python3 toast_test.py path/to/famidrive_toast.py
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_toast", SCRIPT)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class Theme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hex_colors(self):
        self.assertEqual(t.hex_color("111111ee"), (17, 17, 17, 238))
        self.assertEqual(t.hex_color("ffffff"), (255, 255, 255, 255))
        self.assertIsNone(t.hex_color("white"))
        self.assertIsNone(t.hex_color(None))

    def test_the_players_scheme_from_every_block_that_names_it(self):
        (self.dir / "colors.xml").write_text("""<theme>
          <colorScheme name="dark-original,custom"><variables>
            <statusBackgroundColor>111111ee</statusBackgroundColor><statusColor>ffffff</statusColor>
          </variables></colorScheme>
          <colorScheme name="oled-screenshots,oled-original"><variables>
            <statusBackgroundColor>000000ee</statusBackgroundColor><helpTextColor>999999</helpTextColor>
          </variables></colorScheme>
          <colorScheme name="dark-original,oled-original"><variables>
            <statusColor>eeeeee</statusColor>
          </variables></colorScheme>
        </theme>""")
        c = t.theme_colors(self.dir, "oled-original")
        self.assertEqual(c["panel"], (0, 0, 0, 238))
        self.assertEqual(c["text"], (238, 238, 238, 255))
        self.assertEqual(c["dim"], (153, 153, 153, 255))
        # Unknown scheme: the file's first block. No theme: ES-DE's dark look.
        self.assertEqual(t.theme_colors(self.dir, "nope")["panel"], (17, 17, 17, 238))
        self.assertEqual(t.theme_colors(None, None), t.DEFAULT_COLORS)

    def test_scheme_from_es_settings(self):
        (self.dir / "ES-DE/settings").mkdir(parents=True)
        (self.dir / "ES-DE/settings/es_settings.xml").write_text(
            '<string name="ThemeColorScheme" value="oled-original" />')
        self.assertEqual(t.color_scheme(self.dir), "oled-original")
        self.assertIsNone(t.color_scheme(self.dir / "missing"))

    def test_fonts_from_theme_xml(self):
        (self.dir / "theme.xml").write_text("<fontRegular>./f/R.ttf</fontRegular><fontLight>./f/L.ttf</fontLight>")
        self.assertEqual(t.theme_fonts(self.dir), (self.dir / "./f/R.ttf", self.dir / "./f/L.ttf"))
        self.assertEqual(t.theme_fonts(None), (None, None))


class Placement(unittest.TestCase):
    def test_each_corner(self):
        screen, size, m = (1920, 1080), (500, 100), 40
        self.assertEqual(t.place("top-left", screen, size, m), (40, 40))
        self.assertEqual(t.place("top-center", screen, size, m), (710, 40))
        self.assertEqual(t.place("middle-left", screen, size, m), (40, 490))
        # The bottom keeps clear of the theme's help bar.
        self.assertEqual(t.place("bottom-right", screen, size, m), (1380, 1080 - 100 - 88))

    def test_player_overrides_the_box(self):
        spec = {"default": {"position": "top-left", "hide": ["progress"]},
                "players": {"alice": {"position": "bottom-right"}, "bob": {"position": "sideways"}}}
        self.assertEqual(t.player_spec(spec, "alice"), {"position": "bottom-right", "hide": ["progress"]})
        self.assertEqual(t.player_spec(spec, "guest")["position"], "top-left")
        self.assertEqual(t.player_spec(spec, "bob")["position"], "bottom-right")


class Queue(unittest.TestCase):
    def test_one_at_a_time_in_order(self):
        q = t.Queue()
        q.add({"kind": "notice", "title": "a"}, 0)
        q.add({"kind": "notice", "title": "b"}, 0)
        self.assertEqual(q.tick(0)[0]["title"], "a")
        self.assertEqual(q.tick(3)[0]["title"], "a")
        self.assertEqual(q.tick(4.1)[0]["title"], "b")
        self.assertIsNone(q.tick(9)[0])

    def test_progress_updates_in_place_until_done(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "pull", "title": "Downloading", "progress": 0.1}, 0)
        q.add({"kind": "notice", "title": "after"}, 1)
        self.assertEqual(q.tick(1)[0]["progress"], 0.1)
        q.add({"kind": "progress", "id": "pull", "title": "Downloading", "progress": 0.5}, 30)
        toast, _, left = q.tick(60)
        self.assertEqual((toast["progress"], left), (0.5, None))     # stays while unfinished
        q.add({"kind": "progress", "id": "pull", "title": "Done", "done": True}, 61)
        self.assertEqual(q.tick(62)[0]["title"], "Done")
        self.assertEqual(q.tick(63.1)[0]["title"], "after")

    def test_a_forgotten_progress_toast_goes(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "x", "title": "Stuck"}, 0)
        self.assertIsNotNone(q.tick(100)[0])
        self.assertIsNone(q.tick(t.STALE_PROGRESS + 1)[0])

    def test_waiting_progress_is_replaced_not_repeated(self):
        q = t.Queue()
        q.add({"kind": "notice", "title": "first"}, 0)
        q.tick(0)
        q.add({"kind": "progress", "id": "p", "title": "1"}, 0)
        q.add({"kind": "progress", "id": "p", "title": "2"}, 0)
        self.assertEqual([w["title"] for w in q.waiting], ["2"])

    def test_hidden_kinds_and_unknown_kinds(self):
        q = t.Queue(hide=["progress"])
        self.assertFalse(q.add({"kind": "progress", "title": "x"}, 0))
        self.assertTrue(q.add({"kind": "sparkles", "title": "y"}, 0))
        self.assertEqual(q.tick(0)[0]["kind"], "notice")


class Sending(unittest.TestCase):
    def test_arguments(self):
        self.assertEqual(t.parse_send(["--kind", "progress", "--id", "p", "--progress", "1.5", "Pulling", "2", "of", "5"]),
                         {"kind": "progress", "id": "p", "progress": 1.0, "title": "Pulling", "detail": "2 of 5"})
        with self.assertRaises(SystemExit):
            t.parse_send(["--done"])

    def test_no_daemon_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(SCRIPT), "Hello"], capture_output=True, text=True,
                               env={**os.environ, "XDG_RUNTIME_DIR": d})
        self.assertEqual(r.returncode, 0)
        self.assertIn("no toast daemon", r.stderr)


if __name__ == "__main__":
    unittest.main()
