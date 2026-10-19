"""famidrive-record: record what's on the TV into the player's Recordings.

    famidrive-record start     start recording, unless already
    famidrive-record stop      stop, and toast where the recording went
    famidrive-record status    exit 0 and print the file while recording
    famidrive-record media     art in ES-DE for every recording, none for deleted ones

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

Each saved recording gets its art in ES-DE's Recordings list: a still from
it, as its screenshot and cover, and the recording itself as its video,
which Art Book Next plays in place of the still after a few seconds on it.
ES-DE finds a game's art by file name in downloaded_media/<system>/<kind>/,
never in the game list, so these go there. The session's start runs
`media` for recordings made before this, and to clear art left by ones the
player deleted.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, TypedDict


class Encoder(NamedTuple):
    name: str
    props: list[str]
    scale: list[str]   # what scales the picture to fit, before it
    caps: str          # the frames it takes


class State(TypedDict):
    """The recording under way, in state_file()."""
    pid: int
    path: str
    started: float


# gamescope's stream: its node's name, and its size when pw-dump says.
type Stream = tuple[str, tuple[int, int] | None]

GST_LAUNCH = "@gstLaunch@"
GST_INSPECT = "@gstInspect@"
GST_PLUGINS = "@gstPlugins@"
PW_DUMP = "@pwDump@"
FFMPEG = "@ffmpeg@"

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
#
# 1920x1080 exactly, with black borders when the TV isn't 16:9. Found on
# the first box 2026-10-16: with only the height set, vapostproc kept a
# width of its own, and the picture came out squashed.
SCALE_CPU = ["videoconvert", "!", "videoscale", "add-borders=true"]
ENCODERS = (
    Encoder("vah264enc", ["rate-control=cbr", "bitrate=12000"], ["vapostproc", "add-borders=true"], "video/x-raw(memory:VAMemory),format=NV12"),
    Encoder("vaapih264enc", ["rate-control=cbr", "bitrate=12000"], ["vaapipostproc", "force-aspect-ratio=true"], "video/x-raw(memory:VASurface),format=NV12"),
    Encoder("nvh264enc", ["rc-mode=cbr", "bitrate=12000"], SCALE_CPU, "video/x-raw,format=NV12"),
    Encoder("x264enc", ["speed-preset=veryfast", "tune=zerolatency", "bitrate=8000"], SCALE_CPU, "video/x-raw,format=NV12"),
)
FPS = 60
WIDTH, HEIGHT = 1920, 1080
STARTUP_SECONDS = 2.0    # how long a pipeline gets to fail before start says it's running
# How long it gets to finish the file after Ctrl-C, before it's ended
# outright. The MP4 is fragmented, so a recording ended that way still
# plays up to its last second. Found on the first box 2026-10-16: a stop
# took more than one press of Stop, and each press made its own toast.
STOP_SECONDS = 5.0
TOAST_ID = "famidrive-record"   # one toast per stop: "Saving recording", then the result in its place
# The still: this far in, past the "Recording" toast's slide in, or the
# first frame when a recording is shorter. 540 lines tall is plenty for
# the list's art, at a tenth of a 1080p frame's size.
STILL_AT = 3
STILL_HEIGHT = 540
# The kinds of art each recording gets. Screenshot is what FamiDrive's
# default layout (gamelist-list-metadata-screenshot-marquee) shows; cover
# is for the cover and grid layouts.
STILL_KINDS = ("screenshots", "covers")


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def state_file() -> Path:
    return runtime_dir() / "famidrive-record.json"


def recordings_dir() -> Path:
    """Where recordings go: FAMIDRIVE_RECORDINGS (for tests), else ~/Recordings."""
    return Path(os.environ.get("FAMIDRIVE_RECORDINGS") or Path.home() / "Recordings")


def media_dir() -> Path:
    """ES-DE's art for the Recordings system: FAMIDRIVE_RECORDINGS_MEDIA
    (for tests), else ~/ES-DE/downloaded_media/recordings."""
    return Path(os.environ.get("FAMIDRIVE_RECORDINGS_MEDIA")
                or Path.home() / "ES-DE/downloaded_media/recordings")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def current() -> State | None:
    """{"pid", "path"} of the recording under way, or None. A state file
    left by a recorder that's gone (a crash) is removed."""
    try:
        state: State = json.loads(state_file().read_text())
        pid = int(state["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not alive(pid):
        state_file().unlink(missing_ok=True)
        return None
    return state


def file_name(now: float | None = None) -> str:
    """A recording's name: the time it started, as 2026-10-16 21.04.33.mp4,
    which ES-DE then lists oldest first. Dots, not colons: a colon is out
    of place in a file name a player may copy to another computer."""
    return time.strftime("%Y-%m-%d %H.%M.%S", time.localtime(now)) + ".mp4"


def pick_encoder(exists: Callable[[str], bool]) -> Encoder | None:
    """The first of ENCODERS this box's GStreamer has: exists(name) says."""
    for encoder in ENCODERS:
        elements = [e for e in encoder.scale if e != "!" and "=" not in e]
        if all(exists(e) for e in (encoder.name, *elements)):
            return encoder
    return None


def gamescope_stream() -> Stream | None:
    """gamescope's PipeWire stream, as (node name, (width, height)), from
    pw-dump; None when it can't be found. The node is named for
    gamescope's binary, which isn't always "gamescope": under the
    capSysNice wrapper it's ".gamescope-wrapped" (first box,
    2026-10-17)."""
    try:
        out = subprocess.run([PW_DUMP], capture_output=True, text=True, timeout=5).stdout
        objects: object = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return find_stream(objects)


def mapping(value: object) -> dict[str, object]:
    """A JSON object from pw-dump, or {} for anything else."""
    return value if isinstance(value, dict) else {}


def listing(value: object) -> list[object]:
    """A JSON array from pw-dump, or [] for anything else."""
    return value if isinstance(value, list) else []


def find_stream(objects: object) -> Stream | None:
    for o in listing(objects):
        info = mapping(mapping(o).get("info"))
        props = mapping(info.get("props"))
        name = props.get("node.name") or ""
        if props.get("media.class") != "Video/Source" or not isinstance(name, str) or "gamescope" not in name:
            continue
        for fmt in listing(mapping(info.get("params")).get("EnumFormat")):
            size = mapping(mapping(fmt).get("size"))
            width, height = size.get("width"), size.get("height")
            if isinstance(width, int) and isinstance(height, int):
                return name, (width, height)
        return name, None
    return None


def fit(size: tuple[int, int] | None) -> tuple[int, int]:
    """The largest even size within WIDTH x HEIGHT with size's shape (the
    TV's); the scaler after it adds the borders."""
    if not size or not size[0] or not size[1]:
        return WIDTH, HEIGHT
    w, h = size
    scale = min(WIDTH / w, HEIGHT / h, 1.0)
    return max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2)


def pipeline(path: Path, encoder: Encoder, stream: Stream | None = None) -> list[str]:
    """gst-launch-1.0's arguments for a recording to path, from stream
    (gamescope_stream()). pipewiresrc stamps frames as they come
    (gamescope sends one only when the picture changes) and keeps sending
    the last one through a still screen; videorate makes that a steady
    FPS for the encoder and for players.

    The picture comes in GPU memory (a DMABuf) and OpenGL scales it to
    1080p before it's copied out. Found on the first box 2026-10-17: in
    ordinary memory, gamescope copies each 4K frame on the CPU, and the
    TV dropped from 120 frames a second to 60 while recording. No caps
    after pipewiresrc: glupload asks for the DMABuf itself, and with them
    gst-launch can't link the GL elements. OpenGL needs an exact size (it
    picked a width of 1 when left to keep the shape itself), hence fit().
    The queue after pipewiresrc drops frames rather than hold the stream
    up when the encoder falls behind, so the recording keeps to the
    clock.

    The queue before the encoder lets it work while the next frame is
    scaled. Found on the first box 2026-10-17: without it, each frame
    waited for both in turn, and the box's GPU encoder kept up with only
    about 41 frames a second, against 60 with it."""
    name, props, scale, caps = encoder
    node, size = stream or ("gamescope", None)
    w, h = fit(size)
    return [
        "-e",   # Ctrl-C ends the stream properly, so the MP4 is finished
        "pipewiresrc", f"target-object={node}", "do-timestamp=true", "keepalive-time=100",
        "!", "queue", "leaky=downstream", "max-size-buffers=4", "max-size-bytes=0", "max-size-time=0",
        "!", "glupload", "!", "glcolorconvert", "!", "glcolorscale", "!", "glcolorconvert", "!", "gldownload",
        "!", f"video/x-raw,format=NV12,width={w},height={h}",
        "!", *scale,
        "!", "videorate",
        "!", f"{caps},width={WIDTH},height={HEIGHT},pixel-aspect-ratio=1/1,framerate={FPS}/1",
        "!", "queue",
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


def gst_env() -> dict[str, str]:
    env = dict(os.environ)
    if not GST_PLUGINS.startswith("@"):
        env["GST_PLUGIN_SYSTEM_PATH_1_0"] = GST_PLUGINS
    # OpenGL without a window: the recorder draws nothing.
    env["GST_GL_PLATFORM"] = "egl"
    env["GST_GL_WINDOW"] = "surfaceless"
    return env


def gst_exists(name: str) -> bool:
    return subprocess.run([GST_INSPECT, "--exists", name], env=gst_env(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def toast(*args: str) -> None:
    """A toast through famidrive-toast, by name (it's on the session's
    PATH); never worth failing over."""
    exe = shutil.which("famidrive-toast")
    if exe:
        subprocess.run([exe, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def log(msg: str) -> None:
    print(f"famidrive-record: {msg}", file=sys.stderr, flush=True)


def still(video: Path, out: Path) -> bool:
    """A frame of the recording as a JPEG, STILL_AT seconds in, or its
    first when it's shorter than that (ffmpeg writes nothing past the
    end). Written beside and moved in, so ES-DE never reads half a file."""
    tmp = out.with_name(out.name + ".part")
    error = ""
    for at in (STILL_AT, 0):
        try:
            r = subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(video),
                                "-frames:v", "1", "-vf", f"scale=-2:{STILL_HEIGHT}", "-f", "image2", "-c:v", "mjpeg",
                                str(tmp)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
        except OSError as e:
            error = str(e)
            break
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(out)
            return True
        error = r.stderr.strip()
        tmp.unlink(missing_ok=True)
    log(f"couldn't take a still from {video}: {error}")
    return False


def link(target: Path, at: Path) -> None:
    if at.is_symlink() and os.readlink(at) == str(target):
        return
    at.parent.mkdir(parents=True, exist_ok=True)
    tmp = at.with_name(at.name + ".part")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    tmp.replace(at)


def add_media(video: Path) -> None:
    """One recording's art: the still as its screenshot and its cover, and
    the recording itself (a link to it) as its video."""
    m = media_dir()
    stem = video.stem
    shot = m / "screenshots" / (stem + ".jpg")
    shot.parent.mkdir(parents=True, exist_ok=True)
    if not shot.exists() and not still(video, shot):
        return
    for kind in STILL_KINDS[1:]:
        link(Path("..") / "screenshots" / shot.name, m / kind / shot.name)
    link(video, m / "videos" / video.name)


def has_media(video: Path) -> bool:
    m = media_dir()
    return (all((m / kind / (video.stem + ".jpg")).exists() for kind in STILL_KINDS)
            and (m / "videos" / video.name).exists())


def sync_media() -> None:
    """Art for each recording that has none (made before this, or a copy
    put in by hand), and none for a recording that's gone. The one being
    recorded right now is left until it's saved."""
    folder = recordings_dir()
    state = current()
    live = Path(state["path"]) if state else None
    videos = {v.stem: v for v in folder.glob("*.mp4") if v != live} if folder.is_dir() else {}
    for v in sorted(videos.values()):
        if not has_media(v):
            add_media(v)
    m = media_dir()
    for kind in (*STILL_KINDS, "videos"):
        for f in (m / kind).glob("*") if (m / kind).is_dir() else ():
            if f.name.endswith(".part") or Path(f.name).stem not in videos:
                f.unlink(missing_ok=True)


def start() -> int:
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
        proc = subprocess.Popen([GST_LAUNCH, *pipeline(path, encoder, gamescope_stream())], env=gst_env(),
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                start_new_session=True)
    # When it started, for the time so far in the Guide menu.
    state: State = {"pid": proc.pid, "path": str(path), "started": time.time()}
    state_file().write_text(json.dumps(state))
    log(f"recording to {path} with {encoder.name} (pid {proc.pid})")
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
    # The only sign of it over the game (the Guide menu has the rest), so
    # it's in the recording's first seconds.
    toast("--icon", "record", "Recording", "Stop it from the Guide menu.")
    return 0


def stop() -> int:
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
        add_media(path)
        # ES-DE reads its game lists once, at start, and nothing outside it
        # can make it read them again: its own Utilities menu can (2.1.2+).
        # Found on the first box 2026-10-16: a new recording wasn't in
        # Recordings.
        toast("--kind", "success", "--id", TOAST_ID, "Recording saved",
              "To see it in Recordings, pick Rescan ROM directory in the menu's Utilities.")
    else:
        toast("--kind", "alert", "--id", TOAST_ID, "Recording not saved", "Nothing was captured.")
    return 0


def main() -> None:
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
    if cmd == "media":
        sync_media()
        sys.exit(0)
    print("usage: famidrive-record start|stop|status|media", file=sys.stderr)
    sys.exit(64)


if __name__ == "__main__":
    main()
