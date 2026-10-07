"""famidrive-cheevos: each player's RetroAchievements, across their emulators.

    famidrive-cheevos setup SPEC.json
    famidrive-cheevos watch LOG SYSTEM ROM

setup (at the start of each player's session): signs in to
RetroAchievements with the player's username and password (the password
from their sops secret, never the Nix store) and writes the token it gets
back into each emulator, so none of them asks on the TV:

  - RetroArch (retroarch.cfg): every RetroArch-run system
  - Dolphin (RetroAchievements.ini): GameCube and Wii
  - PCSX2 (PCSX2.ini): PlayStation 2

The token is kept in ~/.local/state/famidrive/retroachievements.json, so a
session that starts with RetroAchievements unreachable still signs in.
One token serves every emulator: it's the account's, not an emulator's.

watch (beside each RetroArch and Dolphin game, from famidrive-launch):
reads the emulator's log as it's written and shows a toast (famidrive-toast) for
each unlock, with the achievement's description and points from
RetroAchievements and the game's logo from ES-DE's media (a trophy when
it has none). RetroArch's own unlock pop-up is turned off by setup, so
there's one, in the player's theme; Dolphin has no switch for its own.

SPEC (JSON, from Nix): {"username", "passwordFile", "hardcore",
"retroarch": bool, "dolphin": bool, "pcsx2": bool}.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

HOME = Path.home()
STATE = HOME / ".local/state/famidrive/retroachievements.json"
API = "https://retroachievements.org/dorequest.php"
# RetroAchievements asks every client to name itself.
AGENT = {"User-Agent": "FamiDrive/1.0 (famidrive-cheevos)"}
MEDIA = HOME / "ES-DE/downloaded_media"


# --- Signing in ----------------------------------------------------------------

def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def store_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    os.chmod(tmp, 0o600)
    tmp.replace(STATE)


def login(username, password):
    """The account's token from RetroAchievements (login2), or None."""
    r = requests.post(API, data={"r": "login2", "u": username, "p": password},
                      headers=AGENT, timeout=15)
    body = r.json() if r.content else {}
    if not body.get("Success") or not body.get("Token"):
        print(f"famidrive-cheevos: sign-in refused: {body.get('Error') or r.status_code}", file=sys.stderr)
        return None
    return body["Token"]


def token_for(spec):
    """A fresh token, or the last one when RetroAchievements can't be reached."""
    state = load_state()
    cached = state.get("token") if state.get("username") == spec["username"] else None
    try:
        password = Path(spec["passwordFile"]).read_text().strip()
    except OSError as e:
        print(f"famidrive-cheevos: no password ({e}); using the last sign-in", file=sys.stderr)
        return cached
    try:
        token = login(spec["username"], password)
    except (requests.RequestException, ValueError) as e:
        print(f"famidrive-cheevos: RetroAchievements unreachable ({e}); using the last sign-in", file=sys.stderr)
        return cached
    if token:
        store_state({"username": spec["username"], "token": token})
    return token


# --- Emulator settings -----------------------------------------------------------

def set_flat(path, keys):
    """RetroArch's `key = "value"` file: these keys set, the rest kept."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    left = dict(keys)
    out = []
    for line in lines:
        k = line.split("=", 1)[0].strip()
        if k in left:
            out.append(f'{k} = "{left.pop(k)}"')
        else:
            out.append(line)
    out += [f'{k} = "{v}"' for k, v in left.items()]
    path.write_text("\n".join(out) + "\n")


def set_ini(path, section, keys):
    """An INI file's [section]: these keys set (Key = Value), the rest kept."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    left = dict(keys)
    out, inside, seen = [], False, False

    def flush():
        out.extend(f"{k} = {v}" for k, v in left.items())
        left.clear()

    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if inside:
                flush()
            inside = s[1:-1] == section
            seen = seen or inside
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if inside and k in left:
            out.append(f"{k} = {left.pop(k)}")
        else:
            out.append(line)
    if inside:
        flush()
    if not seen:
        if out and out[-1].strip():
            out.append("")
        out.append(f"[{section}]")
        flush()
    path.write_text("\n".join(out) + "\n")


def configure(spec, token):
    user, hard = spec["username"], bool(spec.get("hardcore"))
    if spec.get("retroarch"):
        set_flat(HOME / ".config/retroarch/retroarch.cfg", {
            "cheevos_enable": "true",
            "cheevos_username": user,
            "cheevos_token": token,
            "cheevos_password": "",
            "cheevos_hardcore_mode_enable": "true" if hard else "false",
            # The unlock shows as a FamiDrive toast instead (watch).
            "cheevos_visibility_unlock": "false",
        })
    if spec.get("dolphin"):
        set_ini(HOME / ".config/dolphin-emu/RetroAchievements.ini", "Achievements", {
            "Enabled": "True",
            "Username": user,
            "ApiToken": token,
            "HardcoreEnabled": "True" if hard else "False",
        })
        # Its RetroAchievements log channel, at info level and to a file,
        # where watch reads unlocks. Every other channel stays as it was
        # (all off unless someone turned one on).
        logger = HOME / ".config/dolphin-emu/Logger.ini"
        set_ini(logger, "Logs", {"RetroAchievements": "True"})
        set_ini(logger, "Options", {"WriteToFile": "True", "Verbosity": "4"})
    if spec.get("pcsx2"):
        set_ini(HOME / ".config/PCSX2/inis/PCSX2.ini", "Achievements", {
            "Enabled": "true",
            "Username": user,
            "Token": token,
            "LoginTimestamp": str(int(time.time())),
            "ChallengeMode": "true" if hard else "false",
        })


def cmd_setup(spec_file):
    spec = json.loads(Path(spec_file).read_text())
    token = token_for(spec)
    if not token:
        print("famidrive-cheevos: not signed in; emulators keep what they had", file=sys.stderr)
        return 1
    configure(spec, token)
    return 0


# --- Unlocks ---------------------------------------------------------------------

AWARD = re.compile(r"Awarding achievement (\d+): (.*)")
GAME = re.compile(r'Identified game: (\d+) "(.*)"')


def achievements(game_id):
    """{id: {"Title", "Description", "Points"}} for a game, from
    RetroAchievements with the player's token; {} when it can't be had."""
    state = load_state()
    if not state.get("token"):
        return {}
    try:
        r = requests.post(API, data={"r": "patch", "u": state["username"], "t": state["token"], "g": game_id},
                          headers=AGENT, timeout=15)
        data = r.json().get("PatchData") or {}
    except (requests.RequestException, ValueError):
        return {}
    return {str(a["ID"]): a for a in data.get("Achievements") or []}


def logo(system, rom):
    """The game's logo in ES-DE's media (marquees), or None."""
    stem = Path(rom).stem
    for folder in ("marquees", "logos"):
        for ext in (".png", ".jpg", ".webp"):
            p = MEDIA / system / folder / (stem + ext)
            if p.exists():
                return str(p)
    return None


def toast_args(award, info, game, icon):
    title = award[1]
    detail = game or ""
    if info:
        title = info.get("Title") or title
        desc = info.get("Description") or ""
        points = info.get("Points")
        detail = " · ".join(x for x in (desc, f"{points} points" if points else "") if x)
    args = ["--kind", "achievement"]
    if icon:
        args += ["--icon", icon]
    return args + [title, detail]


def follow(path, stop):
    """Lines of a log as they're written, from its start (RetroArch makes
    it anew each launch), until stop() says so."""
    while not Path(path).exists():
        if stop():
            return
        time.sleep(0.5)
    with open(path, errors="replace") as f:
        while not stop():
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.3)


def cmd_watch(log, system, rom):
    if not load_state().get("token"):
        return 0   # this player has no RetroAchievements
    parent = os.getppid()
    icon = logo(system, rom)
    game, info = None, {}
    for line in follow(log, lambda: os.getppid() != parent):
        m = GAME.search(line)
        if m:
            game, info = m.group(2), achievements(m.group(1))
            continue
        m = AWARD.search(line)
        if m:
            subprocess.run(["famidrive-toast", *toast_args(m.groups(), info.get(m.group(1)), game, icon)],
                           check=False, timeout=5)
    return 0


def main():
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "setup" and len(args) == 1:
        sys.exit(cmd_setup(*args))
    if cmd == "watch" and len(args) == 3:
        sys.exit(cmd_watch(*args))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
