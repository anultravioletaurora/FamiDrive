"""famidrive-record: names, the encoder it picks, its pipeline and its state, without GStreamer.

    python3 record_test.py path/to/famidrive_record.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_record", SCRIPT)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class Names(unittest.TestCase):
    def test_named_by_when_it_started_oldest_first(self):
        t = time.mktime((2026, 10, 16, 21, 4, 33, 0, 0, -1))
        self.assertEqual(r.file_name(t), "2026-10-16 21.04.33.mp4")
        self.assertLess(r.file_name(t), r.file_name(t + 60))


class Encoder(unittest.TestCase):
    def test_the_gpus_encoder_first(self):
        self.assertEqual(r.pick_encoder(lambda n: True)[0], "vah264enc")
        cpu = ("videoconvert", "videoscale")
        self.assertEqual(r.pick_encoder(lambda n: n in ("nvh264enc", "x264enc", *cpu))[0], "nvh264enc")

    def test_an_encoder_whose_scaler_is_missing_is_passed_over(self):
        # The va encoder without the va scaler (an older plugin set).
        self.assertEqual(r.pick_encoder(lambda n: n in ("vah264enc", "x264enc", "videoconvert", "videoscale"))[0], "x264enc")

    def test_the_cpu_when_there_is_no_other(self):
        self.assertEqual(r.pick_encoder(lambda n: n in ("x264enc", "videoconvert", "videoscale"))[0], "x264enc")
        self.assertIsNone(r.pick_encoder(lambda n: False))


class Pipeline(unittest.TestCase):
    def test_gamescopes_stream_and_the_sound_into_one_mp4(self):
        args = r.pipeline(Path("/home/a/Recordings/x y.mp4"), r.ENCODERS[0])
        self.assertEqual(args[0], "-e")
        self.assertIn("target-object=gamescope", args)
        self.assertIn("device=@DEFAULT_MONITOR@", args)
        self.assertIn("location=/home/a/Recordings/x y.mp4", args)   # one argument, spaces and all
        self.assertIn("fragment-duration=1000", args)
        self.assertEqual(args[args.index("vah264enc") + 1], "rate-control=cbr")
        self.assertIn("video/x-raw,format=NV12", args)   # gamescope's own conversion
        # Scaled to 1080p on the GPU, at a steady 60, straight into the encoder.
        scaled = args.index("vah264enc") - 2   # before its "!"
        self.assertEqual(args[scaled], "video/x-raw(memory:VAMemory),format=NV12,width=1920,height=1080,pixel-aspect-ratio=1/1,framerate=60/1")
        self.assertLess(args.index("vapostproc"), args.index("videorate"))
        # The TV's shape kept: borders, never a squashed picture.
        self.assertEqual(args[args.index("vapostproc") + 1], "add-borders=true")
        # A slow encoder drops frames, it doesn't hold the stream up.
        self.assertIn("leaky=downstream", args)

    def test_the_cpu_scales_for_the_others(self):
        args = r.pipeline(Path("/x.mp4"), r.pick_encoder(lambda n: n in ("x264enc", "videoconvert", "videoscale")))
        self.assertLess(args.index("videoscale"), args.index("x264enc"))
        self.assertIn("video/x-raw,format=NV12,width=1920,height=1080,pixel-aspect-ratio=1/1,framerate=60/1", args)
        self.assertEqual(args[-1], "mux.")


class State(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ)
        os.environ["XDG_RUNTIME_DIR"] = str(self.dir)
        os.environ["FAMIDRIVE_RECORDINGS"] = str(self.dir / "Recordings")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def test_not_recording(self):
        self.assertIsNone(r.current())
        self.assertEqual(r.stop(), 0)

    def test_a_live_recorder(self):
        r.state_file().write_text(json.dumps({"pid": os.getpid(), "path": "/x.mp4"}))
        self.assertEqual(r.current()["path"], "/x.mp4")

    def test_a_dead_recorders_state_is_cleared(self):
        p = subprocess.Popen(["true"])
        p.wait()
        r.state_file().write_text(json.dumps({"pid": p.pid, "path": "/x.mp4"}))
        self.assertIsNone(r.current())
        self.assertFalse(r.state_file().exists())

    def test_a_recorder_that_ignores_ctrl_c_is_ended_anyway(self):
        p = subprocess.Popen([sys.executable, "-c",
                              "import signal, time\n"
                              "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                              "time.sleep(30)\n"])
        threading.Thread(target=p.wait, daemon=True).start()
        time.sleep(0.3)
        r.state_file().write_text(json.dumps({"pid": p.pid, "path": str(self.dir / "a.mp4")}))
        old, r.STOP_SECONDS = r.STOP_SECONDS, 0.5
        try:
            self.assertEqual(r.stop(), 0)
        finally:
            r.STOP_SECONDS = old
        time.sleep(0.2)
        self.assertIsNotNone(p.returncode)

    def test_stop_is_claimed_at_once(self):
        # While one stop waits for the file, the menu sees no recording and
        # a second stop does nothing.
        p = subprocess.Popen([sys.executable, "-c",
                              "import signal, time\n"
                              "signal.signal(signal.SIGINT, lambda *_: time.sleep(1) or exit(0))\n"
                              "time.sleep(30)\n"])
        threading.Thread(target=p.wait, daemon=True).start()
        time.sleep(0.3)
        r.state_file().write_text(json.dumps({"pid": p.pid, "path": str(self.dir / "a.mp4")}))
        first = threading.Thread(target=r.stop)
        first.start()
        time.sleep(0.3)
        self.assertIsNone(r.current())
        self.assertEqual(r.stop(), 0)
        first.join()

    def test_stop_ends_the_recorder_with_ctrl_c(self):
        # A stand-in for gst-launch: exits cleanly on SIGINT, as -e does.
        p = subprocess.Popen([sys.executable, "-c",
                              "import signal, sys, time\n"
                              "signal.signal(signal.SIGINT, lambda *_: sys.exit(0))\n"
                              "time.sleep(30)\n"])
        # Reaped as soon as it exits, as the real one (not stop's child) is.
        threading.Thread(target=p.wait, daemon=True).start()
        time.sleep(0.3)
        out = self.dir / "Recordings" / "a.mp4"
        out.parent.mkdir()
        out.write_bytes(b"x")
        r.state_file().write_text(json.dumps({"pid": p.pid, "path": str(out)}))
        self.assertEqual(r.stop(), 0)
        self.assertEqual(p.returncode, 0)
        self.assertFalse(r.state_file().exists())


if __name__ == "__main__":
    unittest.main()
