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
    def titles(self, shown):
        return [t["title"] for t, _, _ in shown]

    def test_up_to_three_at_once_then_in_order(self):
        q = t.Queue()
        for n in "abcd":
            q.add({"kind": "notice", "title": n}, 0)
        self.assertEqual(self.titles(q.tick(0)), ["a", "b", "c"])
        self.assertEqual(self.titles(q.tick(4.1)), ["d"])
        self.assertEqual(q.tick(9), [])

    def test_a_long_progress_toast_holds_one_slot_not_all(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "pull", "title": "Downloading", "progress": 0.1}, 0)
        q.add({"kind": "notice", "title": "Saved"}, 1)
        self.assertEqual(self.titles(q.tick(1)), ["Downloading", "Saved"])
        q.add({"kind": "progress", "id": "pull", "title": "Downloading", "progress": 0.5}, 30)
        shown = q.tick(60)
        self.assertEqual(self.titles(shown), ["Downloading"])
        self.assertEqual((shown[0][0]["progress"], shown[0][2]), (0.5, None))   # stays while unfinished

    def test_progress_turns_into_success_in_place(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "pull", "title": "Downloading games", "progress": 0.6}, 0)
        q.tick(0)
        q.add({"kind": "success", "id": "pull", "title": "Library updated", "detail": "2 new games fetched from RomM"}, 10)
        (toast, _, left), = q.tick(10)
        self.assertEqual((toast["kind"], toast["title"]), ("success", "Library updated"))
        self.assertAlmostEqual(left, t.SECONDS["success"])
        self.assertEqual(q.tick(10 + t.SECONDS["success"] + 0.1), [])

    def test_a_success_is_always_the_checkmark(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "pull", "icon": "download", "title": "Downloading games"}, 0)
        q.tick(0)
        q.add({"kind": "success", "id": "pull", "title": "Library updated"}, 1)
        (toast, _, _), = q.tick(1)
        self.assertEqual(t.icon_name(toast), "check")
        self.assertEqual(t.icon_name({"kind": "success", "icon": "save"}), "check")
        self.assertEqual(t.icon_name({"kind": "progress"}), "download")
        self.assertEqual(t.icon_name({"kind": "notice", "icon": "save"}), "save")
        self.assertIn("check", t.ICONS)

    def test_alerts_and_achievements_go_ahead_of_waiting_notices(self):
        q = t.Queue(slots=1)
        q.add({"kind": "notice", "title": "first"}, 0)
        q.tick(0)
        q.add({"kind": "notice", "title": "n1"}, 0)
        q.add({"kind": "notice", "title": "n2"}, 0)
        q.add({"kind": "alert", "title": "battery"}, 0)
        q.add({"kind": "achievement", "title": "unlock"}, 0)
        self.assertEqual([w["title"] for w in q.waiting], ["battery", "unlock", "n1", "n2"])

    def test_a_forgotten_progress_toast_goes(self):
        q = t.Queue()
        q.add({"kind": "progress", "id": "x", "title": "Stuck"}, 0)
        self.assertTrue(q.tick(100))
        self.assertEqual(q.tick(t.STALE_PROGRESS + 1), [])

    def test_waiting_progress_is_replaced_not_repeated(self):
        q = t.Queue(slots=1)
        q.add({"kind": "notice", "title": "first"}, 0)
        q.tick(0)
        q.add({"kind": "progress", "id": "p", "title": "1"}, 0)
        q.add({"kind": "progress", "id": "p", "title": "2"}, 0)
        self.assertEqual([w["title"] for w in q.waiting], ["2"])

    def test_hidden_kinds_and_unknown_kinds(self):
        q = t.Queue(hide=["progress"])
        self.assertFalse(q.add({"kind": "progress", "title": "x"}, 0))
        self.assertTrue(q.add({"kind": "sparkles", "title": "y"}, 0))
        self.assertEqual(q.tick(0)[0][0]["kind"], "notice")


class Stacking(unittest.TestCase):
    def test_up_from_the_bottom_down_from_the_top(self):
        screen, sizes = (1920, 1080), [(500, 100), (500, 150), (500, 80)]
        self.assertEqual(t.layout("bottom-right", screen, sizes, 40, 16),
                         [(1380, 892), (1380, 726), (1380, 630)])
        self.assertEqual(t.layout("top-left", screen, sizes, 40, 16),
                         [(40, 40), (40, 156), (40, 322)])
        self.assertEqual(t.layout("top-left", screen, [], 40, 16), [])


class Notifications(unittest.TestCase):
    def test_markup_stripped(self):
        self.assertEqual(t.strip_markup("<b>Cyberpunk</b> &amp; more"), "Cyberpunk & more")

    def test_a_plain_notification(self):
        self.assertEqual(t.from_notification("Heroic", 0, "", "Cyberpunk 2077", "Installed", {}, 7),
                         {"kind": "notice", "title": "Cyberpunk 2077", "detail": "Installed", "id": "fdo-7"})

    def test_critical_is_an_alert_and_value_is_progress(self):
        self.assertEqual(t.from_notification("x", 0, "", "Failed", "", {"urgency": ("y", 2)}, 1)["kind"], "alert")
        p = t.from_notification("x", 3, "", "Downloading", "", {"value": ("i", 40)}, 9)
        self.assertEqual((p["kind"], p["progress"], p["done"], p["id"]), ("progress", 0.4, False, "fdo-3"))

    def test_an_image_on_the_box_is_the_icon(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            self.assertEqual(t.from_notification("x", 0, "file://" + f.name, "Hi", "", {}, 1)["icon"], f.name)
        self.assertNotIn("icon", t.from_notification("x", 0, "dialog-information", "Hi", "", {}, 1))


class Controllers(unittest.TestCase):
    def test_pads_and_batteries_from_sys(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            hid = root / "devices/hid0"
            (hid / "input/input5").mkdir(parents=True)
            (hid / "input/input5/name").write_text("Xbox Wireless Controller\n")
            (root / "class/input").mkdir(parents=True)
            (root / "class/input/js0").mkdir()
            os.symlink(hid / "input/input5", root / "class/input/js0/device")
            ps = root / "class/power_supply/xpadneo_battery"
            ps.mkdir(parents=True)
            (ps / "scope").write_text("Device\n")
            (ps / "capacity").write_text("15\n")
            os.symlink(hid, ps / "device")
            laptop = root / "class/power_supply/BAT0"
            laptop.mkdir()
            (laptop / "scope").write_text("System\n")
            pads = t.connected_pads(root / "class")
            self.assertEqual(list(pads.values()), ["Xbox Wireless Controller"])
            self.assertEqual(list(t.pad_batteries(root / "class").values()), [("Xbox Wireless Controller", 15)])

    def test_connected_and_disconnected(self):
        a = {"/d/1": "8BitDo Ultimate 2"}
        b = {"/d/2": "Xbox Wireless Controller"}
        toasts = t.pad_changes(a, b, playing=False)
        self.assertEqual([(x["title"], x["detail"]) for x in toasts],
                         [("Controller connected", "Xbox Wireless Controller"), ("Controller disconnected", "8BitDo Ultimate 2")])
        gone = t.pad_changes(b, {}, playing=True)[0]
        self.assertEqual(gone["kind"], "alert")
        self.assertIn("Select + Start", gone["detail"])

    def test_low_battery_once_until_charged(self):
        warned = set()
        self.assertEqual(len(t.battery_changes(warned, {"x": ("Pad", 18)})), 1)
        self.assertEqual(t.battery_changes(warned, {"x": ("Pad", 12)}), [])
        t.battery_changes(warned, {"x": ("Pad", 80)})
        self.assertEqual(len(t.battery_changes(warned, {"x": ("Pad", 19)})), 1)


class Sockets(unittest.TestCase):
    def test_a_live_socket_is_left_alone_and_a_dead_one_replaced(self):
        import socket
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.sock"
            first = t.listen(path, 0o600)
            self.assertIsNotNone(first)
            self.assertIsNone(t.listen(path, 0o600))   # live: not taken over
            first.close()                               # dead file left behind
            second = t.listen(path, 0o600)
            self.assertIsNotNone(second)
            t.release([(path, os.stat(path).st_ino)])
            self.assertFalse(path.exists())
            second.close()
            del socket


class Sending(unittest.TestCase):
    def test_arguments(self):
        self.assertEqual(t.parse_send(["--kind", "progress", "--id", "p", "--progress", "1.5", "Pulling", "2", "of", "5"]),
                         {"kind": "progress", "id": "p", "progress": 1.0, "title": "Pulling", "detail": "2 of 5"})
        with self.assertRaises(SystemExit):
            t.parse_send(["--done"])

    def test_outside_a_session_it_reaches_the_tv_through_the_shared_folder(self):
        import socket
        import threading
        with tempfile.TemporaryDirectory() as d:
            shared = Path(d) / "shared"
            shared.mkdir()
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(str(shared / "alice.sock"))
            srv.listen(1)
            got = []

            def accept():
                conn, _ = srv.accept()
                with conn:
                    got.append(conn.recv(65536))
            th = threading.Thread(target=accept)
            th.start()
            old_shared, old_env = t.SHARED, os.environ.get("XDG_RUNTIME_DIR")
            t.SHARED = shared
            os.environ["XDG_RUNTIME_DIR"] = str(Path(d) / "no-session")
            try:
                t.send({"kind": "progress", "title": "Downloading games"})
            finally:
                t.SHARED = old_shared
                if old_env is None:
                    os.environ.pop("XDG_RUNTIME_DIR", None)
                else:
                    os.environ["XDG_RUNTIME_DIR"] = old_env
            th.join(5)
            srv.close()
            self.assertIn(b"Downloading games", got[0])

    def test_no_daemon_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(SCRIPT), "Hello"], capture_output=True, text=True,
                               env={**os.environ, "XDG_RUNTIME_DIR": d})
        self.assertEqual(r.returncode, 0)
        self.assertIn("no toast daemon", r.stderr)


if __name__ == "__main__":
    unittest.main()
