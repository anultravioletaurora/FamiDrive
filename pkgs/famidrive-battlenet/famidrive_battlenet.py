"""famidrive-battlenet play LUTRIS_DATA_DIR GAME_ID
famidrive-battlenet games LUTRIS_DATA_DIR

play runs beside a Lutris launch and puts the player in a Battle.net game
instead of Battle.net's page for it.

A Battle.net game in Lutris is Battle.net.exe with --exec="launch <code>"
(Lutris's install scripts, such as Black Ops Cold War's). Battle.net
ignores that on a cold start: it signs in and shows the game's page,
and waits for Play. Found on the first box 2026-10-15, in Battle.net's
own log: "Command line arguments: --exec=launch ZEUS", then no
LaunchBinary until Play was pressed, every time. Sent again to a
Battle.net that's up, the same command launches the game at once: a
second Battle.net.exe finds the first ("IPC ShMem mode=client") and
hands it on.

The second one has to run where the first one does. Lutris runs it
through umu, in a sandbox with a /tmp of its own, where Wine keeps the
socket to its server; a second umu-run makes a new sandbox, and its
Battle.net.exe found no Battle.net and started another. So this joins
the running Battle.net's user and mount namespaces (nsenter) and runs
Proton's wine there, with Battle.net's own environment.

So: wait for this launch's Battle.net to sign in and show its window,
then send the launch, and again if the game doesn't start, until it
does. Nothing at all for a Lutris game that isn't a Battle.net one, or
when Battle.net starts the game by itself.

games gives each game Battle.net has installed a Lutris entry of its own,
so it's in the Lutris system once it's installed from Battle.net, with no
Lutris installer to run for it. Lutris's installers for Battle.net games
("for an existing install of Battle.net") add nothing else: the same
prefix, and Battle.net.exe with --exec="launch <code>". Battle.net lists
what it has installed in ProgramData/Battle.net/Agent/aggregate.json, by
its own ID (Black Ops Cold War's is "zeus", on the first box 2026-10-15).
An entry made here goes when Battle.net no longer lists its game, as an
uninstalled game (Lutris keeps those, and FamiDrive doesn't show them).
A game that already has an entry, from a Lutris installer, gets no
second one.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import yaml

NSENTER = os.environ.get("FAMIDRIVE_NSENTER", "@nsenter@")
PROC = Path(os.environ.get("FAMIDRIVE_PROC", "/proc"))

WAIT_FOR_SIGN_IN = 600   # seconds: a sign-in can need the player (a security check)
SETTLE = 3               # seconds after the window shows, before the first send
TRIES = 3
WAIT_FOR_GAME = 15       # seconds after each send

# What Battle.net's log says. The window shows once it has signed in.
SIGNED_IN = "Login triggered"
WINDOW = "Attempting to show main window"
LAUNCHED = "LaunchBinary"

# Settings in Battle.net's own environment that belong to that one
# process: Wine's handle on its server, and its loader's.
PROCESS_ONLY = ("WINESERVERSOCKET=", "WINELOADERNOEXEC=", "WINEPRELOADRESERVE=")


# Battle.net's ID for a game (aggregate.json's product_id) -> the code
# --exec="launch ..." takes, and the game's name with its punctuation (the
# file has "Call of Duty Black Ops Cold War"). From Playnite's Battle.net
# library (BattleNetGames.cs, MIT), 2026-10-15, where they're InternalId
# and ProductId. A game that's not here: its ID in capitals, the way most
# codes are, and Battle.net's name.
GAMES = {
    "wow": ("WoW", "World of Warcraft"),
    "diablo3": ("D3", "Diablo III"),
    "s2": ("S2", "StarCraft II"),
    "s1": ("S1", "StarCraft"),
    "hs_beta": ("WTCG", "Hearthstone"),
    "heroes": ("Hero", "Heroes of the Storm"),
    "prometheus": ("Pro", "Overwatch 2"),
    "viper": ("VIPR", "Call of Duty: Black Ops 4"),
    "odin": ("ODIN", "Call of Duty: Modern Warfare"),
    "w3": ("W3", "Warcraft III: Reforged"),
    "lazarus": ("LAZR", "Call of Duty: Modern Warfare 2 Campaign Remastered"),
    "zeus": ("ZEUS", "Call of Duty: Black Ops Cold War"),
    "wlby": ("WLBY", "Crash Bandicoot 4: It's About Time"),
    "osi": ("OSI", "Diablo II: Resurrected"),
    "rtro": ("RTRO", "Blizzard Arcade Collection"),
    "fore": ("FORE", "Call of Duty: Vanguard"),
    "anbs": ("ANBS", "Diablo Immortal"),
    "auks": ("AUKS", None),   # Call of Duty's own app: Battle.net's name for it
    "fen": ("Fen", "Diablo IV"),
    "fenris": ("Fen", "Diablo IV"),
    "d1": ("D1", "Diablo"),
    "w1r": ("W1R", "Warcraft: Remastered"),
    "w2r": ("W2R", "Warcraft II: Remastered"),
    "w1": ("W1", "Warcraft: Orcs & Humans"),
    "w2": ("W2", "Warcraft II: Battle.net Edition"),
    "gryphon": ("GRY", "Warcraft Rumble"),
    "aris": ("ARIS", "DOOM: The Dark Ages"),
    "scorpio": ("SCOR", "Sea of Thieves"),
    "arkansas": ("ARK", "The Outer Worlds 2"),
    "libra": ("LBRA", "Tony Hawk's Pro Skater 3 + 4"),
    "pinta": ("PNTA", "Call of Duty: Modern Warfare III"),
    "aqua": ("AQUA", "Avowed"),
}

# The installer_slug of an entry made here, so it's told apart from one a
# Lutris installer made.
MADE_HERE = "famidrive-battlenet"
BATTLENET_EXE = "drive_c/Program Files (x86)/Battle.net/Battle.net.exe"


def game_configs(lutris_dir):
    """Where Lutris keeps its game configs: beside the database, unless an
    older Lutris left them in ~/.config/lutris (lutris/settings.py)."""
    games = lutris_dir / "games"
    return games if games.is_dir() else Path.home() / ".config/lutris/games"


def load_config(path):
    try:
        return yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None


def exec_code(args):
    m = re.search(r'--exec=("[^"]*"|\S+)', args or "")
    return m.group(1).strip('"') if m else None


def battlenet_game(lutris_dir, game_id):
    """(prefix, the --exec argument) for a Battle.net game, or None."""
    try:
        con = sqlite3.connect(f"{(lutris_dir / 'pga.db').as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            row = con.execute("SELECT configpath FROM games WHERE id = ?", (int(game_id),)).fetchone()
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return None
    if not row or not row[0]:
        return None
    game = ((load_config(game_configs(lutris_dir) / f"{row[0]}.yml") or {}).get("game")) or {}
    exe, prefix = str(game.get("exe") or ""), game.get("prefix")
    code = exec_code(str(game.get("args") or ""))
    if not code or not prefix or Path(exe.replace("\\", "/")).name.lower() != "battle.net.exe":
        return None
    return Path(prefix), "--exec=" + code


def newest_log(prefix, since):
    """This launch's Battle.net log: the newest one started since."""
    logs = [p for p in prefix.glob("drive_c/users/*/AppData/Local/Battle.net/Logs/battle.net-*.log")
            if p.stat().st_mtime >= since]
    return max(logs, key=lambda p: p.stat().st_mtime, default=None)


def read(path):
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def battlenet_process(prefix):
    """The running Battle.net's pid, in this prefix: the main process,
    not one of its Chromium helpers (--type=...)."""
    for d in PROC.iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = (d / "cmdline").read_bytes().split(b"\0")
            env = (d / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        cmd = argv[0].decode(errors="replace").replace("\\", "/")
        if not cmd.lower().endswith("/battle.net.exe") or any(a.startswith(b"--type=") for a in argv[1:]):
            continue
        for e in env:
            if e.startswith(b"STEAM_COMPAT_DATA_PATH=") and Path(e[23:].decode()).resolve() == prefix.resolve():
                return int(d.name), env
    return None


def send(pid, env, exec_arg):
    """Battle.net.exe exec_arg, beside the running Battle.net."""
    keep = [e.decode(errors="replace") for e in env if e and not e.startswith(tuple(p.encode() for p in PROCESS_ONLY))]
    cmd = [NSENTER, "-t", str(pid), "-U", "-m", "--preserve-credentials", "--",
           "env", "-i", *keep, "wine", "C:\\Program Files (x86)\\Battle.net\\Battle.net.exe", exec_arg]
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"famidrive-battlenet: couldn't send {exec_arg}: {e}", file=sys.stderr)


def play(lutris_dir, game_id, sleep=time.sleep, clock=time.time):
    game = battlenet_game(lutris_dir, game_id)
    if game is None:
        return
    prefix, exec_arg = game
    started = clock() - 2
    log = None
    while clock() - started < WAIT_FOR_SIGN_IN:
        # Newest each time: Battle.net can restart itself (an update).
        log = newest_log(prefix, started)
        text = read(log) if log else ""
        if LAUNCHED in text:
            return   # Battle.net started it by itself
        if SIGNED_IN in text and WINDOW in text:
            break
        sleep(1)
    else:
        return
    sleep(SETTLE)
    for _ in range(TRIES):
        if LAUNCHED in read(log):
            return
        running = battlenet_process(prefix)
        if running is None:
            return   # Battle.net closed
        send(*running, exec_arg)
        for _ in range(WAIT_FOR_GAME):
            if LAUNCHED in read(log):
                return
            sleep(1)
    print(f"famidrive-battlenet: Battle.net didn't start the game after {TRIES} tries", file=sys.stderr)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


def installed_by_battlenet(prefix):
    """{Battle.net's ID: its name} for each game Battle.net has installed
    in this prefix, or None when it can't say (not run yet, or writing)."""
    try:
        data = json.loads((prefix / "drive_c/ProgramData/Battle.net/Agent/aggregate.json").read_text())
    except (OSError, ValueError):
        return None
    return {str(g["product_id"]).lower(): str(g.get("name") or g["product_id"])
            for g in data.get("installed") or [] if isinstance(g, dict) and g.get("product_id")}


def games(lutris_dir, clock=time.time):
    """A Lutris entry for each game Battle.net has installed."""
    db = lutris_dir / "pga.db"
    if not db.exists():
        return
    configs = game_configs(lutris_dir)
    try:
        con = sqlite3.connect(db, timeout=10)
    except sqlite3.Error as e:
        print(f"famidrive-battlenet: can't open {db}: {e}", file=sys.stderr)
        return
    try:
        with con:
            rows = con.execute("SELECT id, slug, installer_slug, configpath, installed FROM games").fetchall()
            config = {r[0]: ((load_config(configs / f"{r[3]}.yml") or {}) if r[3] else {}) for r in rows}
            # Battle.net itself, in each prefix it's installed in: an entry
            # that starts Battle.net and no game.
            apps = {}
            for i, slug, installer, path, installed in rows:
                game = config[i].get("game") or {}
                exe = Path(str(game.get("exe") or "").replace("\\", "/")).name.lower()
                if installed and game.get("prefix") and exe in ("battle.net.exe", "battle.net launcher.exe") \
                        and not exec_code(str(game.get("args") or "")):
                    apps.setdefault(Path(game["prefix"]).resolve(), (installer, config[i]))
            for prefix, (app_installer, app_config) in apps.items():
                found = installed_by_battlenet(prefix)
                if found is None:
                    continue
                # What already has an entry here: its code, any case.
                have = {}
                for i, slug, installer, path, installed in rows:
                    game = config[i].get("game") or {}
                    code = exec_code(str(game.get("args") or ""))
                    if code and game.get("prefix") and Path(game["prefix"]).resolve() == prefix:
                        have.setdefault(code.lower(), (i, installer, installed))
                wanted = {}
                for product, bnet_name in found.items():
                    code, name = GAMES.get(product, (product.upper(), None))
                    wanted["launch " + code.lower()] = (code, name or bnet_name)
                for key, (code, name) in wanted.items():
                    if key in have:
                        i, installer, installed = have[key]
                        if installer == MADE_HERE and not installed:
                            con.execute("UPDATE games SET installed = 1 WHERE id = ?", (i,))
                        continue
                    add(con, configs, prefix, code, name, app_installer, app_config, clock)
                for key, (i, installer, installed) in have.items():
                    if installer == MADE_HERE and installed and key not in wanted:
                        con.execute("UPDATE games SET installed = 0 WHERE id = ?", (i,))
    except sqlite3.Error as e:
        print(f"famidrive-battlenet: can't update {db}: {e}", file=sys.stderr)
    finally:
        con.close()


def add(con, configs, prefix, code, name, app_installer, app_config, clock):
    """A Lutris entry like the one Lutris's installer for the game makes
    (Black Ops Cold War's, on the first box 2026-10-15): Battle.net's
    prefix and its runner settings, and its Battle.net.exe with the code."""
    slug = slugify(name)
    now = int(clock())
    path = f"{slug}-{MADE_HERE}-{now}"
    entry = {
        "game": {"arch": (app_config.get("game") or {}).get("arch", "win64"),
                 "args": f'--exec="launch {code}"', "exe": BATTLENET_EXE, "prefix": str(prefix)},
        "game_slug": slug,
        "name": name,
        "requires": app_installer,
        "slug": f"{slug}-{MADE_HERE}",
        "version": "Battle.net",
    }
    for runner in ("system", "wine"):
        if app_config.get(runner):
            entry[runner] = app_config[runner]
    configs.mkdir(parents=True, exist_ok=True)
    (configs / f"{path}.yml").write_text(yaml.safe_dump(entry, sort_keys=False))
    con.execute("""INSERT INTO games (name, sortname, slug, installer_slug, parent_slug, platform,
                       runner, directory, lastplayed, installed, installed_at, configpath,
                       has_custom_banner, has_custom_icon, has_custom_coverart_big, playtime)
                   VALUES (?, '', ?, ?, ?, 'Windows', 'wine', ?, 0, 1, ?, ?, 0, 0, 0, 0.0)""",
                (name, slug, MADE_HERE, app_installer, str(prefix), now, path))


def main():
    usage = "usage: famidrive-battlenet play LUTRIS_DATA_DIR GAME_ID | games LUTRIS_DATA_DIR"
    if len(sys.argv) == 4 and sys.argv[1] == "play":
        play(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "games":
        games(Path(sys.argv[2]))
    else:
        sys.exit(usage)


if __name__ == "__main__":
    main()
