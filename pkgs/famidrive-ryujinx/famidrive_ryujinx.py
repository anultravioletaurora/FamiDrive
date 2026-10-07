"""famidrive-ryujinx: Ryujinx (Ryubing) for the Switch games that need it.

    famidrive-ryujinx setup SPEC            before each Ryujinx launch
    famidrive-ryujinx save-in TITLE_ID      Eden's save -> Ryujinx's
    famidrive-ryujinx save-out TITLE_ID     Ryujinx's save -> Eden's

Every other Switch game runs in Eden, and Eden's save folder stays the
one RomM syncs from. A game run in Ryujinx (HewDraw Remix's Smash
Ultimate: its Skyline plugins don't run in Eden) is bridged through it:
its save is copied into Ryujinx before the game and back after, so the
same save follows the player whichever emulator runs it.

SPEC (JSON): {"root": Ryujinx's data folder, "library": the library's
Switch folder, "faceButtons": "labels" | "positions", "edenKeys": the
player's Eden keys folder, "edenFirmware": Eden's installed firmware, "defaults": a full
Config.json to start from, "sdl": the libSDL2 Ryujinx uses}. Paths may
start with ~.
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path.home() / ".config/Ryujinx"
STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "famidrive-ryujinx.json"
PLAYERS = 8


# ---------------------------------------------------------------- settings

def locked(spec):
    """The Config.json keys FamiDrive sets. Everything else stays the
    player's (and Ryujinx's)."""
    return {
        # Updates and DLC from RomM, beside each game in the library.
        "game_dirs": [spec["library"]],
        "autoload_dirs": [spec["library"]],
        "start_fullscreen": True,
        "show_confirm_exit": False,
        "check_updates_on_start": False,
        "enable_discord_integration": False,
        "show_console": False,
        "hide_cursor": 2,               # always
        "docked_mode": True,
        "enable_keyboard": False,
        "remember_window_state": False,
    }


def gamepads(sdl_path):
    """Connected gamepads as Ryujinx names them: "<n>-<SDL GUID as a .NET
    Guid>", n counting up for a second pad of the same model, in SDL's
    device order (Ryujinx.Input.SDL2's GenerateGamepadId)."""
    class Guid(ctypes.Structure):
        _fields_ = [("data", ctypes.c_uint8 * 16)]
    try:
        sdl = ctypes.CDLL(sdl_path)
    except OSError:
        return []
    sdl.SDL_JoystickGetDeviceGUID.restype = Guid
    sdl.SDL_JoystickGetDeviceGUID.argtypes = [ctypes.c_int]
    sdl.SDL_JoystickNameForIndex.restype = ctypes.c_char_p
    sdl.SDL_JoystickNameForIndex.argtypes = [ctypes.c_int]
    if sdl.SDL_Init(0x200) != 0:        # SDL_INIT_JOYSTICK
        return []
    try:
        ids, out = [], []
        for i in range(sdl.SDL_NumJoysticks()):
            raw = bytes(sdl.SDL_JoystickGetDeviceGUID(i).data)
            if raw == bytes(16):
                continue
            guid = str(uuid.UUID(bytes_le=raw))     # .NET's Guid(byte[]) layout
            n = 0
            while f"{n}-{guid}" in ids:
                n += 1
            ids.append(f"{n}-{guid}")
            name = (sdl.SDL_JoystickNameForIndex(i) or b"").decode(errors="replace")
            out.append((ids[-1], name))
        return out
    finally:
        sdl.SDL_Quit()


def pad_config(pad_id, name, player, face):
    """Ryujinx's own default for a gamepad (InputViewModel's
    LoadDefaultConfiguration), with A/B/X/Y by FamiDrive's faceButtons:
    "labels" keeps the pad's printed letters, "positions" the Switch's
    places (Ryujinx's own default for non-Nintendo pads)."""
    swap = face == "positions" and "Nintendo" not in name
    return {
        "left_joycon_stick": {"joystick": "Left", "invert_stick_x": False, "invert_stick_y": False,
                              "rotate90_cw": False, "stick_button": "LeftStick"},
        "right_joycon_stick": {"joystick": "Right", "invert_stick_x": False, "invert_stick_y": False,
                               "rotate90_cw": False, "stick_button": "RightStick"},
        "deadzone_left": 0.1, "deadzone_right": 0.1, "range_left": 1.0, "range_right": 1.0,
        "trigger_threshold": 0.5,
        "motion": {"motion_backend": "GamepadDriver", "sensitivity": 100, "gyro_deadzone": 1,
                   "enable_motion": True},
        "rumble": {"strong_rumble": 1.0, "weak_rumble": 1.0, "enable_rumble": True},
        "left_joycon": {"button_minus": "Minus", "button_l": "LeftShoulder", "button_zl": "LeftTrigger",
                        "button_sl": "Unbound", "button_sr": "Unbound", "dpad_up": "DpadUp",
                        "dpad_down": "DpadDown", "dpad_left": "DpadLeft", "dpad_right": "DpadRight"},
        "right_joycon": {"button_plus": "Plus", "button_r": "RightShoulder", "button_zr": "RightTrigger",
                         "button_sl": "Unbound", "button_sr": "Unbound",
                         "button_x": "Y" if swap else "X", "button_b": "A" if swap else "B",
                         "button_y": "X" if swap else "Y", "button_a": "B" if swap else "A"},
        "version": 1,
        "backend": "GamepadSDL2",
        "id": pad_id,
        "name": name,
        "controller_type": "ProController",
        "player_index": f"Player{player}",
    }


def write_config(spec, pads):
    cfg_file = ROOT / "Config.json"
    try:
        cfg = json.loads(cfg_file.read_text())
    except (OSError, ValueError):
        cfg = json.loads(Path(spec["defaults"]).read_text())
    cfg.update(locked(spec))
    # The pads connected now, player 1 first. Without any, Ryujinx's own
    # list stays (it may be a player's hand-made one).
    if pads:
        cfg["input_config"] = [pad_config(pid, name, i + 1, spec["faceButtons"])
                               for i, (pid, name) in enumerate(pads[:PLAYERS])]
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = cfg_file.with_name("Config.json.part")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(cfg_file)


def copy_keys(spec):
    dest = ROOT / "system"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("prod.keys", "title.keys"):
        src = Path(spec["edenKeys"]).expanduser() / name
        if src.is_file() and (not (dest / name).exists() or (dest / name).read_bytes() != src.read_bytes()):
            shutil.copyfile(src, dest / name)


def link_firmware(spec):
    """Eden's installed firmware, in Ryujinx's layout: each NCA as
    registered/<name>.nca/00. Hard links where they can be (the same
    disk), so it costs no space. Only when Ryujinx has none yet."""
    src = Path(spec["edenFirmware"]).expanduser()
    dest = ROOT / "bis/system/Contents/registered"
    if not src.is_dir() or (dest.is_dir() and any(dest.iterdir())):
        return
    dest.mkdir(parents=True, exist_ok=True)
    for nca in src.glob("*.nca"):
        d = dest / nca.name
        d.mkdir(exist_ok=True)
        try:
            os.link(nca, d / "00")
        except OSError:
            shutil.copyfile(nca, d / "00")


def cmd_setup(spec_json):
    spec = json.loads(spec_json)
    write_config(spec, gamepads(spec["sdl"]))
    copy_keys(spec)
    link_firmware(spec)


# ---------------------------------------------------------------- saves

def ryujinx_save(tid):
    """Ryujinx's save folder for a game, or None. Saves are numbered
    folders under bis/user/save/; each one's ExtraData0 starts with the
    title ID (little-endian). VERIFY on the first Ryujinx save."""
    want = int(tid, 16).to_bytes(8, "little")
    base = ROOT / "bis/user/save"
    for d in sorted(base.iterdir()) if base.is_dir() else []:
        extra = d / "ExtraData0"
        try:
            if extra.is_file() and extra.read_bytes()[:8] == want:
                return d
        except OSError:
            pass
    return None


def eden_save(tid):
    """Eden's folder for the game's save, from the RomM agent (which knows
    the player's Eden profile). None for a player without RomM."""
    try:
        r = subprocess.run(["romm-agent", "eden-save", tid], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(r.stdout.strip()) if r.stdout.strip() else None


def replace_dir(src, dest):
    tmp = dest.with_name(dest.name + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, symlinks=True)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def cmd_save_in(tid):
    tid = tid.upper()
    eden, ryu = eden_save(tid), ryujinx_save(tid)
    state = load_state()
    state[tid] = {"existed": ryu is not None}
    save_state(state)
    if eden is None or ryu is None or not eden.is_dir():
        return
    # 0 is the committed copy; Ryujinx makes the working copy (1) from it.
    replace_dir(eden, ryu / "0")
    shutil.rmtree(ryu / "1", ignore_errors=True)


def cmd_save_out(tid):
    tid = tid.upper()
    eden, ryu = eden_save(tid), ryujinx_save(tid)
    existed = load_state().get(tid, {}).get("existed", True)
    if eden is None or ryu is None or not (ryu / "0").is_dir():
        return
    if not existed and eden.is_dir():
        # Ryujinx made this save on its first run of the game, so it's
        # new, not the player's. Theirs goes in for next time instead.
        print(f"famidrive-ryujinx: first run of {tid} in Ryujinx; your save is there from the next launch",
              file=sys.stderr)
        replace_dir(eden, ryu / "0")
        shutil.rmtree(ryu / "1", ignore_errors=True)
        return
    eden.parent.mkdir(parents=True, exist_ok=True)
    replace_dir(ryu / "0", eden)


def main():
    cmd, *args = sys.argv[1:] or ["help"]
    commands = {"setup": cmd_setup, "save-in": cmd_save_in, "save-out": cmd_save_out}
    if cmd not in commands:
        print(__doc__)
        sys.exit(64)
    commands[cmd](*args)


if __name__ == "__main__":
    main()
