"""famidrive-steam-config SETTINGS_JSON

Writes FamiDrive's Steam settings into Steam's own config files:

- compatTools: {game: tool}, the per-game Proton choice ("Force the use of
  a specific Steam Play compatibility tool"), into config.vdf's
  CompatToolMapping. A game is a name (as Steam shows it) or an app id.
  App id "0" is Steam's own id for "Enable Steam Play for all other
  titles" (famidrive.steam.protonDefault): every other entry is a pin for
  one real game and wins over it.
- steamInput: false turns Steam Input off for every installed game (the
  per-game "Disable Steam Input"), in each Steam user's localconfig.vdf,
  except the games in steamInputGames (names or app ids), which get it on.
  true leaves Steam's own choice alone.
- launchOptions: {game: options}, each game's launch options, in each
  Steam user's localconfig.vdf. What it sets is remembered (STATE): a
  game taken out of the list later gets its launch options cleared,
  unless they were changed in Steam since.
- guideFocusesSteam: false turns off Steam's "Guide Button Focuses Steam"
  (Controller_CheckGuideButton, in each Steam user's localconfig.vdf).
  Guide is FamiDrive's menu; with it on, Steam reacted to Guide too, with
  its sounds behind the menu (first box, 2026-10-12).

Steam rewrites both files when it exits, so this only sticks while Steam
isn't running: the session runs it just before starting Steam.

Narrow text edits, not a VDF round trip: a parser rewrites the rest of the
file too (tabs, escaped newlines), and Steam owns that. The first time it
changes a file, it keeps the original next to it as *.famidrive-backup.
"""

import json
import re
import sys
from pathlib import Path
from typing import TypedDict


class Settings(TypedDict, total=False):
    """SETTINGS_JSON: see the docstring above."""
    compatTools: dict[str, str]
    steamInput: bool
    steamInputGames: list[str]
    launchOptions: dict[str, str]
    guideFocusesSteam: bool


# A block in a VDF file: its key's line and its '}' line.
type Span = tuple[int, int]

STEAM = Path.home() / ".local/share/Steam"
STATE = Path.home() / ".local/share/famidrive/steam-launch-options.json"

# Steam installs its own tools as apps too (keep in step with
# famidrive-generators).
STEAM_TOOLS = re.compile(r"^(Proton|Steam Linux Runtime|Steamworks Common Redistributables)\b")


# CompatToolMapping's priorities, as Steam writes them: 250 for a tool
# forced on one game, 75 for "all other titles" (app id "0"). Valve's own
# mappings, like Steam Linux Runtime for a native game, are 90, so the
# default has to stay under them, not just under a game's pin. Found on
# the first box 2026-10-13: with "0" at 250, GE-Proton outranked them
# all. Steam treated native games and its own Steam Linux Runtime 4.0 as
# Windows apps, swapped their depots, and left the runtime with none,
# deleting its files. Every Proton built on it (GE-Proton 11, Proton
# Experimental) then failed to launch with AppError_51 (compat_log.txt:
# "Steam Linux Runtime 4.0" unsupported version 0).
GAME_PRIORITY = "250"
DEFAULT_PRIORITY = "75"


def log(msg: str) -> None:
    print(f"famidrive-steam-config: {msg}", file=sys.stderr)


def installed() -> dict[str, str]:
    """Installed games: lowercased name -> app id, in every library."""
    libraries = [STEAM / "steamapps"]
    try:
        folders = (STEAM / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        libraries += [Path(p) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', folders)]
    except OSError:
        pass
    games: dict[str, str] = {}
    for lib in libraries:
        for acf in lib.glob("appmanifest_*.acf"):
            text = acf.read_text(errors="replace")
            appid = re.search(r'"appid"\s+"(\d+)"', text)
            name = re.search(r'"name"\s+"([^"]+)"', text)
            if appid and name and not STEAM_TOOLS.match(name.group(1)):
                games[name.group(1).lower()] = appid.group(1)
    return games


class Vdf:
    """A VDF file as lines, edited in place."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines = path.read_text(errors="replace").split("\n")
        self.original = list(self.lines)

    def block_end(self, i: int) -> int:
        """Index of the '}' closing the block whose '{' is at line i."""
        depth = 0
        for j in range(i, len(self.lines)):
            depth += self.lines[j].count("{") - self.lines[j].count("}")
            if depth == 0:
                return j
        raise SystemExit(f"famidrive-steam-config: unbalanced {self.path}")

    def find(self, key: str, depth: int | None = None) -> Span | None:
        """(key line, its '}' line) of the first block named key, or None.
        depth: only at this many tabs of indent (0 = top level)."""
        for i in range(len(self.lines) - 1):
            line = self.lines[i]
            if depth is not None and len(line) - len(line.lstrip("\t")) != depth:
                continue
            if line.strip().lower() == f'"{key.lower()}"' and self.lines[i + 1].strip() == "{":
                return i, self.block_end(i + 1)
        return None

    def children(self, head: int, close: int) -> dict[str, Span]:
        """{name: (key line, '}' line)} of the blocks directly inside a block."""
        out: dict[str, Span] = {}
        i = head + 2
        while i < close:
            if self.lines[i + 1].strip() == "{":
                end = self.block_end(i + 1)
                out[self.lines[i].strip().strip('"')] = (i, end)
                i = end + 1
            else:
                i += 1
        return out

    def indent(self, head: int) -> str:
        line = self.lines[head]
        return line[:len(line) - len(line.lstrip())] + "\t"

    def save(self) -> None:
        if self.lines == self.original:
            return
        backup = self.path.with_name(self.path.name + ".famidrive-backup")
        if not backup.exists():
            backup.write_text("\n".join(self.original))
        self.path.write_text("\n".join(self.lines))


def set_compat_tools(wanted: dict[str, str]) -> None:
    path = STEAM / "config/config.vdf"
    if not path.exists():
        return   # Steam hasn't been set up yet; next session
    vdf = Vdf(path)
    found = vdf.find("CompatToolMapping")
    if found is None:
        # Steam writes the section the first time any game is forced to a tool.
        log("no CompatToolMapping in config.vdf yet")
        return
    head, close = found
    for appid, (i, end) in sorted(vdf.children(head, close).items(), key=lambda c: -c[1][0]):
        if appid in wanted:
            del vdf.lines[i:end + 1]   # bottom up, so earlier indexes stay put
    ind = vdf.indent(head)
    new: list[str] = []
    for appid, tool in wanted.items():
        new += [f'{ind}"{appid}"', f"{ind}{{",
                f'{ind}\t"name"\t\t"{tool}"',
                f'{ind}\t"config"\t\t""',
                f'{ind}\t"priority"\t\t"{DEFAULT_PRIORITY if appid == "0" else GAME_PRIORITY}"',
                f"{ind}}}"]
    vdf.lines[head + 2:head + 2] = new
    vdf.save()


def vdf_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def set_app_keys(wanted: dict[str, dict[str, str]], depth: int) -> None:
    """wanted: {appid: {key: value}}, set in each game's own settings.
    localconfig.vdf has two per-game "apps" blocks: depth 1
    (UserLocalConfigStore > apps) holds Steam Input's setting, depth 4
    (> Software > Valve > Steam > apps) launch options and play stats."""
    for path in STEAM.glob("userdata/*/config/localconfig.vdf"):
        vdf = Vdf(path)
        found = vdf.find("apps", depth=depth)
        if found is None:
            log(f"no apps section in {path}; skipped")
            continue
        head, close = found
        have = vdf.children(head, close)
        ind = vdf.indent(head)
        # Bottom up, so earlier indexes stay put.
        for appid in sorted(wanted, key=lambda a: -have[a][0] if a in have else 0):
            if appid not in have:
                vdf.lines[head + 2:head + 2] = [f'{ind}"{appid}"', f"{ind}{{", f"{ind}}}"]
                have = vdf.children(head, vdf.block_end(head + 1))
            i, end = have[appid]
            for key, value in wanted[appid].items():
                line = f'{ind}\t"{key}"\t\t"{vdf_string(value)}"'
                for j in range(i + 2, end):
                    if vdf.lines[j].strip().startswith(f'"{key}"'):
                        vdf.lines[j] = line
                        break
                else:
                    vdf.lines.insert(i + 2, line)
                    end += 1
        vdf.save()


def clear_app_keys(stale: dict[str, dict[str, str]], depth: int) -> None:
    """stale: {appid: {key: value}}. Each key that still has that value
    is emptied; one changed since (by the player, in Steam) stays."""
    for path in STEAM.glob("userdata/*/config/localconfig.vdf"):
        vdf = Vdf(path)
        found = vdf.find("apps", depth=depth)
        if found is None:
            continue
        head, close = found
        ind = vdf.indent(head)
        for appid, (i, end) in vdf.children(head, close).items():
            for key, value in stale.get(appid, {}).items():
                for j in range(i + 2, end):
                    if vdf.lines[j].strip() == f'"{key}"\t\t"{vdf_string(value)}"':
                        vdf.lines[j] = f'{ind}\t"{key}"\t\t""'
        vdf.save()


def set_top_key(key: str, value: str) -> None:
    """A key straight inside UserLocalConfigStore, in each localconfig.vdf.
    Steam writes it at the end of the file once it's changed in Steam."""
    for path in STEAM.glob("userdata/*/config/localconfig.vdf"):
        vdf = Vdf(path)
        line = f'\t"{key}"\t\t"{vdf_string(value)}"'
        for i, old in enumerate(vdf.lines):
            if old.startswith(f'\t"{key}"\t'):
                vdf.lines[i] = line
                break
        else:
            end = max((i for i, old in enumerate(vdf.lines) if old.rstrip() == "}"), default=None)
            if end is None:
                log(f"no end to {path}; skipped")
                continue
            vdf.lines.insert(end, line)
        vdf.save()


def read_state() -> dict[str, str]:
    """{app id: the launch options this set last time}."""
    try:
        state: dict[str, str] = json.loads(STATE.read_text())
        return state
    except (OSError, ValueError):
        return {}


def main() -> None:
    settings: Settings = json.loads(sys.argv[1])
    games: dict[str, str] | None = None

    def appid(game: str) -> str | None:
        """A game's app id from its name or id; None if not installed."""
        nonlocal games
        if game.isdigit():
            return game
        games = installed() if games is None else games
        if game.lower() not in games:
            log(f"{game!r} isn't installed; skipped")
        return games.get(game.lower())

    wanted: dict[str, str] = {}
    for game, tool in settings.get("compatTools", {}).items():
        a = appid(game)
        if a:
            wanted[a] = tool
    if wanted:
        set_compat_tools(wanted)

    keys: dict[str, dict[str, str]] = {}   # Steam Input
    if settings.get("steamInput") is False:
        # UseSteamControllerConfig "0" is "Disable Steam Input". "2" is what
        # the games Steam Input was working for had before FamiDrive.
        games = installed() if games is None else games
        keys = {a: {"UseSteamControllerConfig": "0"} for a in games.values()}
        for game in settings.get("steamInputGames", []):
            a = appid(game)
            if a:
                keys[a] = {"UseSteamControllerConfig": "2"}
    if keys:
        set_app_keys(keys, depth=1)

    if settings.get("guideFocusesSteam") is False:
        set_top_key("Controller_CheckGuideButton", "0")

    keys = {}   # launch options
    for game, options in settings.get("launchOptions", {}).items():
        a = appid(game)
        if a:
            keys[a] = {"LaunchOptions": options}
    before = read_state()
    stale = {a: {"LaunchOptions": o} for a, o in before.items()
             if keys.get(a, {}).get("LaunchOptions") != o}
    if stale:
        clear_app_keys(stale, depth=4)
    if keys:
        set_app_keys(keys, depth=4)
    now = {a: k["LaunchOptions"] for a, k in keys.items()}
    if now != before:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(now))


if __name__ == "__main__":
    main()
