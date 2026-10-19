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
        # GPU memory from gamescope, scaled by OpenGL: no caps right after
        # pipewiresrc, so glupload can ask for a DMABuf.
        self.assertEqual(args[args.index("pipewiresrc") + 5], "queue")
        self.assertLess(args.index("glupload"), args.index("glcolorscale"))
        self.assertLess(args.index("gldownload"), args.index("vapostproc"))
        self.assertIn("video/x-raw,format=NV12,width=1920,height=1080", args)
        # Scaled to 1080p on the GPU, at a steady 60, then queued for the
        # encoder, so scaling and encoding run side by side.
        self.assertEqual(args[args.index("vah264enc") - 2], "queue")
        scaled = args.index("vah264enc") - 4   # before the queue
        self.assertEqual(args[scaled], "video/x-raw(memory:VAMemory),format=NV12,width=1920,height=1080,pixel-aspect-ratio=1/1,framerate=60/1")
        self.assertLess(args.index("vapostproc"), args.index("videorate"))
        # The TV's shape kept: borders, never a squashed picture.
        self.assertEqual(args[args.index("vapostproc") + 1], "add-borders=true")
        # A slow encoder drops frames, it doesn't hold the stream up.
        self.assertIn("leaky=downstream", args)

    def test_gamescopes_node_whatever_its_name(self):
        args = r.pipeline(Path("/x.mp4"), r.ENCODERS[0], (".gamescope-wrapped", (3840, 2160)))
        self.assertIn("target-object=.gamescope-wrapped", args)
        self.assertIn("target-object=gamescope", r.pipeline(Path("/x.mp4"), r.ENCODERS[0]))

    def test_opengl_keeps_the_tvs_shape_and_the_scaler_adds_borders(self):
        self.assertEqual(r.fit((3840, 2160)), (1920, 1080))
        self.assertEqual(r.fit((3440, 1440)), (1920, 802))   # ultrawide: borders above and below
        self.assertEqual(r.fit((1280, 800)), (1280, 800))     # never scaled up
        self.assertEqual(r.fit(None), (1920, 1080))
        args = r.pipeline(Path("/x.mp4"), r.ENCODERS[0], ("gamescope", (3440, 1440)))
        self.assertIn("video/x-raw,format=NV12,width=1920,height=802", args)

    def test_the_stream_found_in_pw_dump(self):
        dump = [
            {"type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "alsa_output", "media.class": "Audio/Sink"}}},
            {"type": "PipeWire:Interface:Node", "info": {
                "props": {"node.name": ".gamescope-wrapped", "media.class": "Video/Source"},
                "params": {"EnumFormat": [{"format": "BGRx", "size": {"width": 3840, "height": 2160}}]}}},
        ]
        self.assertEqual(r.find_stream(dump), (".gamescope-wrapped", (3840, 2160)))
        self.assertIsNone(r.find_stream(dump[:1]))

    def test_opengl_without_a_window(self):
        env = r.gst_env()
        self.assertEqual((env["GST_GL_PLATFORM"], env["GST_GL_WINDOW"]), ("egl", "surfaceless"))

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
        os.environ["FAMIDRIVE_RECORDINGS_MEDIA"] = str(self.dir / "media")

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



class Media(unittest.TestCase):
    """Each recording's art in ES-DE, with a stand-in ffmpeg that writes
    "frame at <seconds>" as the still, or nothing past a recording's end
    (its file's content, in seconds)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ)
        os.environ["XDG_RUNTIME_DIR"] = str(self.dir)
        os.environ["FAMIDRIVE_RECORDINGS"] = str(self.dir / "Recordings")
        os.environ["FAMIDRIVE_RECORDINGS_MEDIA"] = str(self.dir / "media")
        self.recordings = self.dir / "Recordings"
        self.recordings.mkdir()
        self.media = self.dir / "media"
        fake = self.dir / "ffmpeg"
        fake.write_text(
            "#!/bin/sh\n"
            "at=; video=; for a; do case \"$prev\" in -ss) at=$a ;; -i) video=$a ;; esac; prev=$a; out=$a; done\n"
            "[ \"$at\" -lt \"$(cat \"$video\")\" ] || [ \"$at\" = 0 ] || exit 0\n"
            "echo \"frame at $at\" > \"$out\"\n"
            f"echo \"$at\" >> {self.dir}/calls\n")
        fake.chmod(0o755)
        self.old, r.FFMPEG = r.FFMPEG, str(fake)

    def tearDown(self):
        r.FFMPEG = self.old
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def recording(self, name, seconds=60):
        p = self.recordings / name
        p.write_text(str(seconds))
        return p

    def test_a_still_as_screenshot_and_cover_and_the_recording_as_video(self):
        v = self.recording("2026-10-16 21.04.33.mp4")
        r.add_media(v)
        shot = self.media / "screenshots/2026-10-16 21.04.33.jpg"
        self.assertEqual(shot.read_text(), f"frame at {r.STILL_AT}\n")
        self.assertEqual((self.media / "covers/2026-10-16 21.04.33.jpg").read_text(), shot.read_text())
        self.assertEqual((self.media / "videos/2026-10-16 21.04.33.mp4").resolve(), v.resolve())
        self.assertEqual(list(self.media.rglob("*.part")), [])

    def test_a_short_recording_gets_its_first_frame(self):
        r.add_media(self.recording("a.mp4", seconds=1))
        self.assertEqual((self.media / "screenshots/a.jpg").read_text(), "frame at 0\n")

    def test_no_still_no_art(self):
        r.FFMPEG = str(self.dir / "missing")
        r.add_media(self.recording("a.mp4"))
        self.assertFalse((self.media / "videos/a.mp4").exists())
        self.assertFalse((self.media / "covers/a.jpg").exists())

    def test_sync_adds_whats_missing_once_and_clears_whats_gone(self):
        self.recording("old.mp4")
        gone = self.recording("gone.mp4")
        r.sync_media()
        gone.unlink()
        self.recording("new.mp4")
        r.sync_media()
        r.sync_media()   # nothing left to do
        names = sorted(str(p.relative_to(self.media)) for p in self.media.rglob("*") if not p.is_dir())
        self.assertEqual(names, ["covers/new.jpg", "covers/old.jpg", "screenshots/new.jpg",
                                 "screenshots/old.jpg", "videos/new.mp4", "videos/old.mp4"])
        self.assertEqual(len((self.dir / "calls").read_text().split()), 3)   # old, gone, new: each once

    def test_sync_leaves_the_one_being_recorded(self):
        live = self.recording("live.mp4")
        r.state_file().write_text(json.dumps({"pid": os.getpid(), "path": str(live)}))
        r.sync_media()
        self.assertFalse((self.media / "screenshots/live.jpg").exists())

    def test_stop_adds_the_art(self):
        p = subprocess.Popen([sys.executable, "-c",
                              "import signal, sys, time\n"
                              "signal.signal(signal.SIGINT, lambda *_: sys.exit(0))\n"
                              "time.sleep(30)\n"])
        threading.Thread(target=p.wait, daemon=True).start()
        time.sleep(0.3)
        v = self.recording("a.mp4")
        r.state_file().write_text(json.dumps({"pid": p.pid, "path": str(v)}))
        self.assertEqual(r.stop(), 0)
        self.assertTrue((self.media / "videos/a.mp4").exists())


if __name__ == "__main__":
    unittest.main()
