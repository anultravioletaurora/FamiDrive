"""famidrive-clonehero songs SPEC_JSON | player SPEC_JSON | played SPEC_JSON

Clone Hero on a FamiDrive box (modules/famidrive/clonehero.nix).

songs: the box's song library, as the famidrive-library account. Each
  chart listed in famidrive.cloneHero.songs (a name and its Chorus Encore
  md5) is downloaded from Encore as a .sng file, the single-file format
  Clone Hero 1.1 plays. A changed md5 downloads again; with onlyListed,
  charts no longer listed are removed. Anything that changes the library
  bumps .famidrive-stamp. Spec: {"dir", "songs": {name: md5}, "onlyListed"}.

player: each time Clone Hero starts. Every FamiDrive player and
  a few guests get a Clone Hero profile (existing ones are never changed),
  and when the shared library has changed since this player last played,
  Clone Hero's song cache is cleared so it rescans. The box's controller
  bindings (below) replace the player's own. Spec: {"profiles": [names],
  "stamps": [library stamp files], "bindings": file or null}.

played: after Clone Hero exits. The player's controller bindings become
  the box's: they belong to the guitars plugged into this box, not to a
  person, so whoever binds a guitar binds it for everyone. Same spec.

Bindings are Rewired's entries (RewiredSaveData…) in Unity's prefs file:
one <pref> per line. Only those move; the rest of the file (window
settings, and a login token) stays the player's.
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ENCORE = os.environ.get("FAMIDRIVE_ENCORE", "https://files.enchor.us/{md5}.sng")   # tests point it at files
MARK = ".famidrive-songs.json"     # name -> md5 of what's in the folder
STAMP = ".famidrive-stamp"
HOME = Path.home() / ".clonehero"
# Clone Hero 1.1's own data: scores, the song cache, Unity's prefs.
UNITY = Path.home() / ".config/unity3d/srylain Inc_/Clone Hero"
PREFS = UNITY / "prefs"
BINDING = re.compile(r'^\s*<pref name="RewiredSaveData[^"]*"')

# A new profile's settings: Clone Hero's own defaults, as a profile it
# wrote on the first box (1.1).
PROFILE = {
    "dynamics_threshold": "100", "midi_device_id": "-1",
    "color_profile_name": "DefaultColors", "highway_name": "default",
    "highway_length": "100", "tilt_activation": "1", "note_speed": "7",
    "show_accuracy_display": "0", "alt_taps": "0", "square_tom_notes": "0",
    "drum_dynamics_hidden": "0", "show_displayname": "0", "is_bot": "0",
    "gamepad_mode": "0", "lefty_flip": "0", "controller_type": "0",
}


def log(msg):
    print(f"famidrive-clonehero: {msg}", file=sys.stderr, flush=True)


def safe(name):
    return re.sub(r'[/\\:*?"<>|]', "_", name).strip()


def download(md5, dest):
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(ENCORE.format(md5=md5), headers={"User-Agent": "FamiDrive"})
    with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    with open(part, "rb") as f:
        if f.read(6) != b"SNGPKG":
            part.unlink()
            raise RuntimeError("not a .sng file")
    part.rename(dest)


def cmd_songs(spec):
    lib = Path(spec["dir"])
    lib.mkdir(parents=True, exist_ok=True)
    try:
        have = json.loads((lib / MARK).read_text())
    except (OSError, ValueError):
        have = {}
    changed = False
    for name, md5 in sorted(spec["songs"].items()):
        md5 = md5.lower()
        dest = lib / f"{safe(name)}.sng"
        if have.get(name) == md5 and dest.exists():
            continue
        try:
            download(md5, dest)
        except (OSError, RuntimeError) as e:
            log(f"skipped {name} ({md5}): {e}")
            continue
        have[name] = md5
        changed = True
        log(f"added {name}")
        (lib / MARK).write_text(json.dumps(have, indent=2))   # survives being interrupted
    if spec.get("onlyListed", True):
        wanted = {f"{safe(n)}.sng" for n in spec["songs"]}
        for f in lib.glob("*.sng"):
            if f.name not in wanted:
                f.unlink()
                changed = True
                log(f"removed {f.stem}")
        have = {n: m for n, m in have.items() if n in spec["songs"]}
    for f in lib.glob("*.part"):
        f.unlink()
    (lib / MARK).write_text(json.dumps(have, indent=2))
    if changed or not (lib / STAMP).exists():
        (lib / STAMP).write_text(str(time.time()))


def seed_profiles(names):
    """Adds a profile for each name that has none. Appends raw sections,
    so Clone Hero's own formatting of the rest of the file is kept."""
    path = HOME / "profiles.ini"
    text = path.read_text(errors="replace") if path.exists() else ""
    have = set(re.findall(r"^player_name\s*=\s*(.*?)\s*$", text, re.M))
    used = [int(n) for n in re.findall(r"^\[profile(\d+)\]", text, re.M)]
    nxt = max(used) + 1 if used else 0
    add = []
    for name in names:
        if name in have:
            continue
        keys = dict(PROFILE, player_name=name)
        add.append(f"[profile{nxt}]\n" + "".join(f"{k} = {v}\n" for k, v in keys.items()))
        nxt += 1
    if add:
        HOME.mkdir(parents=True, exist_ok=True)
        sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        path.write_text(text + sep + "\n".join(add))
        log(f"profiles added: {', '.join(n for n in names if n not in have)}")


def library_stamp(stamps):
    parts = []
    for s in stamps:
        try:
            parts.append(Path(s).read_text().strip())
        except OSError:
            parts.append("")
    return "|".join(parts)


def bindings(lines):
    return [line for line in lines if BINDING.match(line)]


def prefs_lines():
    try:
        return PREFS.read_text(errors="replace").splitlines(keepends=True)
    except OSError:
        return []


def take_box_bindings(path):
    """The box's bindings into this player's prefs, in place of theirs.
    With none saved yet, the player's own are left alone."""
    try:
        box = bindings(Path(path).read_text().splitlines(keepends=True))
    except OSError:
        return
    if not box:
        return
    lines = [line for line in prefs_lines() if not BINDING.match(line)]
    if not lines:
        lines = ['<unity_prefs version_major="1" version_minor="1">\n', "</unity_prefs>\n"]
    end = next((i for i in range(len(lines) - 1, -1, -1) if "</unity_prefs>" in lines[i]), len(lines))
    new = lines[:end] + box + lines[end:]
    if new != prefs_lines():
        UNITY.mkdir(parents=True, exist_ok=True)
        PREFS.write_text("".join(new))


def cmd_played(spec):
    path = spec.get("bindings")
    if not path:
        return
    mine = bindings(prefs_lines())
    if not mine:
        return
    try:
        if Path(path).read_text() == "".join(mine):
            return
    except OSError:
        pass
    # Written in place: the folder is the library's, the file the group's.
    with open(path, "w") as f:
        f.write("".join(mine))
    log("controller bindings saved for everyone on this box")


def cmd_player(spec):
    seed_profiles(spec["profiles"])
    if spec.get("bindings"):
        take_box_bindings(spec["bindings"])
    # Rescan when the shared library changed since this player last
    # played: Clone Hero only looks for new songs when told to, or when
    # its cache is gone. Found on the first box 2026-10-06: 1.1 keeps the
    # cache with its Unity data, not in ~/.clonehero.
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "famidrive"
    seen = state / "clonehero-library"
    now = library_stamp(spec["stamps"])
    old = seen.read_text() if seen.exists() else None
    if now != old:
        for cache in [*UNITY.glob("songcache.bin"), *HOME.glob("songcache.bin")]:
            cache.unlink()
            log("song library changed: Clone Hero will rescan")
        state.mkdir(parents=True, exist_ok=True)
        seen.write_text(now)


def main():
    cmd, spec = sys.argv[1], json.loads(sys.argv[2])
    {"songs": cmd_songs, "player": cmd_player, "played": cmd_played}[cmd](spec)


if __name__ == "__main__":
    main()
