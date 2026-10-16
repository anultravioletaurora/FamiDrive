"""famidrive-record: record what's on the TV into the player's Recordings.

    famidrive-record start     start recording, unless already
    famidrive-record stop      stop, and toast where the recording went
    famidrive-record status    exit 0 and print the file while recording

The Guide menu's "Start recording" runs `start` after its countdown, and
"Stop recording" runs `stop`; the session's end runs `stop` too, so a
recording is never left half written.

The picture is gamescope's own PipeWire stream (a Video/Source node named
"gamescope", src/pipewire.cpp): the focused window with the Steam overlay
layer over it (toasts, the Guide menu), in SDR, tone-mapped the way
gamescope's screenshots are. The sound is the default output's monitor.
Both go through GStreamer into an MP4 in ~/Recordings, named by the time
it started, which the Recordings system in ES-DE lists.

The MP4 is fragmented (a fragment a second), so a recording cut short (the
session killed, the box losing power) still plays up to its last second.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

GST_LAUNCH = "@gstLaunch@"
GST_INSPECT = "@gstInspect@"
GST_PLUGINS = "@gstPlugins@"

# H.264 encoders, best first: the GPU's own encoder (VA-API on AMD and
# Intel, NVENC on Nvidia), else x264 on the CPU. The va plugin is the
# newer of the two VA-API ones; gst-vaapi is kept as a fallback for older
# drivers. Each with its settings, what scales the picture down for it,
# and the caps it takes the picture in. The VA-API ones scale on the GPU.
#
# Recordings are 1080p, whatever the TV: gamescope's stream is the
# output's own size (a smaller one can only be asked for through its own
# pipewire property, which GStreamer can't set). Found on the first box
# 2026-10-16: 4K recordings, converted on the CPU, came out choppy. They
# had a steady 60 frames a second, but most likely few of their own:
# gamescope skips a frame when the recorder hasn't handed its buffer
# back yet ("out of buffers", pipewire.cpp), so many would be
# videorate's repeats.
SCALE_CPU = ["videoconvert", "!", "videoscale"]
ENCODERS = (
    ("vah264enc", ["rate-control=cbr", "bitrate=12000"], ["vapostproc"], "video/x-raw(memory:VAMemory),format=NV12"),
    ("vaapih264enc", ["rate-control=cbr", "bitrate=12000"], ["vaapipostproc"], "video/x-raw(memory:VASurface),format=NV12"),
    ("nvh264enc", ["rc-mode=cbr", "bitrate=12000"], SCALE_CPU, "video/x-raw,format=NV12"),
    ("x264enc", ["speed-preset=veryfast", "tune=zerolatency", "bitrate=8000"], SCALE_CPU, "video/x-raw,format=NV12"),
)
FPS = 60
HEIGHT = 1080   # the width follows the TV's shape
STARTUP_SECONDS = 2.0    # how long a pipeline gets to fail before start says it's running
# How long it gets to finish the file after Ctrl-C, before it's ended
# outright. The MP4 is fragmented, so a recording ended that way still
# plays up to its last second. Found on the first box 2026-10-16: a stop
# took more than one press of Stop, and each press made its own toast.
STOP_SECONDS = 5.0
TOAST_ID = "famidrive-record"   # one toast per stop: "Saving recording", then the result in its place


def runtime_dir():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def state_file():
    return runtime_dir() / "famidrive-record.json"


def recordings_dir():
    """Where recordings go: FAMIDRIVE_RECORDINGS (for tests), else ~/Recordings."""
    return Path(os.environ.get("FAMIDRIVE_RECORDINGS") or Path.home() / "Recordings")


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def current():
    """{"pid", "path"} of the recording under way, or None. A state file
    left by a recorder that's gone (a crash) is removed."""
    try:
        state = json.loads(state_file().read_text())
        pid = int(state["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not alive(pid):
        state_file().unlink(missing_ok=True)
        return None
    return state


def file_name(now=None):
    """A recording's name: the time it started, as 2026-10-16 21.04.33.mp4,
    which ES-DE then lists oldest first. Dots, not colons: a colon is out
    of place in a file name a player may copy to another computer."""
    return time.strftime("%Y-%m-%d %H.%M.%S", time.localtime(now)) + ".mp4"


def pick_encoder(exists):
    """The first of ENCODERS this box's GStreamer has: exists(name) says."""
    for encoder in ENCODERS:
        if all(exists(e) for e in (encoder[0], *encoder[2][::2])):
            return encoder
    return None


def pipeline(path, encoder):
    """gst-launch-1.0's arguments for a recording to path. pipewiresrc
    stamps frames as they come (gamescope sends one only when the picture
    changes) and keeps sending the last one through a still screen;
    videorate makes that a steady FPS for the encoder and for players.

    NV12 from gamescope: it converts on the GPU, and it's half the size
    of its other format. The queue after it drops frames rather than hold
    the stream up when the encoder falls behind, so the recording keeps
    to the clock."""
    name, props, scale, caps = encoder
    return [
        "-e",   # Ctrl-C ends the stream properly, so the MP4 is finished
        "pipewiresrc", "target-object=gamescope", "do-timestamp=true", "keepalive-time=100",
        "!", "video/x-raw,format=NV12",
        "!", "queue", "leaky=downstream", "max-size-buffers=4", "max-size-bytes=0", "max-size-time=0",
        "!", *scale,
        "!", "videorate",
        "!", f"{caps},height={HEIGHT},pixel-aspect-ratio=1/1,framerate={FPS}/1",
        "!", name, *props,
        "!", "h264parse",
        "!", "queue",
        "!", "mp4mux", "name=mux", "fragment-duration=1000",
        "!", "filesink", f"location={path}",
        "pulsesrc", "device=@DEFAULT_MONITOR@",
        "!", "queue",
        "!", "audioconvert",
        "!", "audioresample",
        "!", "avenc_aac", "bitrate=192000",
        "!", "aacparse",
        "!", "queue",
        "!", "mux.",
    ]


def gst_env():
    env = dict(os.environ)
    if not GST_PLUGINS.startswith("@"):
        env["GST_PLUGIN_SYSTEM_PATH_1_0"] = GST_PLUGINS
    return env


def gst_exists(name):
    return subprocess.run([GST_INSPECT, "--exists", name], env=gst_env(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def toast(*args):
    """A toast through famidrive-toast, by name (it's on the session's
    PATH); never worth failing over."""
    exe = shutil.which("famidrive-toast")
    if exe:
        subprocess.run([exe, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def log(msg):
    print(f"famidrive-record: {msg}", file=sys.stderr, flush=True)


def start():
    if current():
        log("already recording")
        return 0
    encoder = pick_encoder(gst_exists)
    if not encoder:
        log("no H.264 encoder in GStreamer")
        toast("--kind", "alert", "Couldn't start recording", "No video encoder was found.")
        return 1
    folder = recordings_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name()
    logfile = runtime_dir() / "famidrive-record.log"
    with open(logfile, "w") as out:
        proc = subprocess.Popen([GST_LAUNCH, *pipeline(path, encoder)], env=gst_env(),
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                start_new_session=True)
    state_file().write_text(json.dumps({"pid": proc.pid, "path": str(path)}))
    log(f"recording to {path} with {encoder[0]} (pid {proc.pid})")
    deadline = time.monotonic() + STARTUP_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            state_file().unlink(missing_ok=True)
            log(f"GStreamer quit at once ({proc.returncode}); see {logfile}")
            if path.exists() and path.stat().st_size == 0:
                path.unlink()
            toast("--kind", "alert", "Couldn't start recording",
                  "The screen couldn't be captured.")
            return 1
        time.sleep(0.1)
    return 0


def stop():
    state = current()
    if not state:
        return 0
    # Claimed first: from here on it isn't recording, for the Guide menu
    # (which offers Record again) and for a second stop (which does
    # nothing), while this one waits for the file to be finished.
    state_file().unlink(missing_ok=True)
    pid, path = int(state["pid"]), Path(state["path"])
    toast("--kind", "progress", "--id", TOAST_ID, "Saving recording")
    # SIGINT is gst-launch's Ctrl-C: with -e it sends end-of-stream and
    # exits once the MP4 is finished.
    for sig, wait in ((signal.SIGINT, STOP_SECONDS), (signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
        if not alive(pid):
            break
        if sig != signal.SIGINT:
            log(f"GStreamer didn't finish in time; sending {sig.name}")
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + wait
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
    if path.exists() and path.stat().st_size > 0:
        # ES-DE reads its game lists once, at start, and nothing outside it
        # can make it read them again: its own Utilities menu can (2.1.2+).
        # Found on the first box 2026-10-16: a new recording wasn't in
        # Recordings.
        toast("--kind", "success", "--id", TOAST_ID, "Recording saved",
              "To see it in Recordings, pick Rescan ROM directory in the menu's Utilities.")
    else:
        toast("--kind", "alert", "--id", TOAST_ID, "Recording not saved", "Nothing was captured.")
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start":
        sys.exit(start())
    if cmd == "stop":
        sys.exit(stop())
    if cmd == "status":
        state = current()
        if state:
            print(state["path"])
        sys.exit(0 if state else 1)
    print("usage: famidrive-record start|stop|status", file=sys.stderr)
    sys.exit(64)


if __name__ == "__main__":
    main()
