"""famidrive-steam-config SETTINGS_JSON

Writes FamiDrive's Steam settings into Steam's own config files:

- compatTools: {game: tool}, the per-game Proton choice ("Force the use of
  a specific Steam Play compatibility tool"), into config.vdf's
  CompatToolMapping. A game is a name (as Steam shows it) or an app id.
- steamInput: false turns Steam Input off for every installed game (the
  per-game "Disable Steam Input"), in each Steam user's localconfig.vdf,
  except the games in steamInputGames (names or app ids), which get it on.
  true leaves Steam's own choice alone.

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

STEAM = Path.home() / ".local/share/Steam"

# Steam installs its own tools as apps too (keep in step with
# famidrive-generators).
STEAM_TOOLS = re.compile(r"^(Proton|Steam Linux Runtime|Steamworks Common Redistributables)\b")


def log(msg):
    print(f"famidrive-steam-config: {msg}", file=sys.stderr)


def installed():
    """Installed games: lowercased name -> app id, in every library."""
    libraries = [STEAM / "steamapps"]
    try:
        folders = (STEAM / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        libraries += [Path(p) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', folders)]
    except OSError:
        pass
    games = {}
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

    def __init__(self, path):
        self.path = path
        self.lines = path.read_text(errors="replace").split("\n")
        self.original = list(self.lines)

    def block_end(self, i):
        """Index of the '}' closing the block whose '{' is at line i."""
        depth = 0
        for j in range(i, len(self.lines)):
            depth += self.lines[j].count("{") - self.lines[j].count("}")
            if depth == 0:
                return j
        raise SystemExit(f"famidrive-steam-config: unbalanced {self.path}")

    def find(self, key, depth=None):
        """(key line, its '}' line) of the first block named key, or None.
        depth: only at this many tabs of indent (0 = top level)."""
        for i in range(len(self.lines) - 1):
            line = self.lines[i]
            if depth is not None and len(line) - len(line.lstrip("\t")) != depth:
                continue
            if line.strip().lower() == f'"{key.lower()}"' and self.lines[i + 1].strip() == "{":
                return i, self.block_end(i + 1)
        return None

    def children(self, head, close):
        """{name: (key line, '}' line)} of the blocks directly inside a block."""
        out, i = {}, head + 2
        while i < close:
            if self.lines[i + 1].strip() == "{":
                end = self.block_end(i + 1)
                out[self.lines[i].strip().strip('"')] = (i, end)
                i = end + 1
            else:
                i += 1
        return out

    def indent(self, head):
        return re.match(r"\s*", self.lines[head]).group(0) + "\t"

    def save(self):
        if self.lines == self.original:
            return
        backup = self.path.with_name(self.path.name + ".famidrive-backup")
        if not backup.exists():
            backup.write_text("\n".join(self.original))
        self.path.write_text("\n".join(self.lines))


def set_compat_tools(wanted):
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
    new = []
    for appid, tool in wanted.items():
        new += [f'{ind}"{appid}"', f"{ind}{{",
                f'{ind}\t"name"\t\t"{tool}"',
                f'{ind}\t"config"\t\t""',
                f'{ind}\t"priority"\t\t"250"',
                f"{ind}}}"]
    vdf.lines[head + 2:head + 2] = new
    vdf.save()


def set_steam_input(wanted):
    """wanted: {appid: "0" (off) or "2" (on)}."""
    # localconfig.vdf: UserLocalConfigStore > apps > <appid> >
    # UseSteamControllerConfig. "0" is "Disable Steam Input". "2" is what
    # the games Steam Input was working for had before FamiDrive.
    for path in STEAM.glob("userdata/*/config/localconfig.vdf"):
        vdf = Vdf(path)
        # Depth 1: the per-game settings. Deeper "apps" blocks are other things.
        found = vdf.find("apps", depth=1)
        if found is None:
            log(f"no apps section in {path}; skipped")
            continue
        head, close = found
        have = vdf.children(head, close)
        ind = vdf.indent(head)
        # Bottom up, so earlier indexes stay put.
        for appid in sorted(wanted, key=lambda a: -have[a][0] if a in have else 0):
            line = f'{ind}\t"UseSteamControllerConfig"\t\t"{wanted[appid]}"'
            if appid in have:
                i, end = have[appid]
                for j in range(i + 2, end):
                    if vdf.lines[j].strip().startswith('"UseSteamControllerConfig"'):
                        vdf.lines[j] = line
                        break
                else:
                    vdf.lines.insert(i + 2, line)
            else:
                vdf.lines[head + 2:head + 2] = [f'{ind}"{appid}"', f"{ind}{{", line, f"{ind}}}"]
        vdf.save()


def main():
    settings = json.loads(sys.argv[1])
    games = None

    def appid(game):
        """A game's app id from its name or id; None if not installed."""
        nonlocal games
        if game.isdigit():
            return game
        games = installed() if games is None else games
        if game.lower() not in games:
            log(f"{game!r} isn't installed; skipped")
        return games.get(game.lower())

    wanted = {}
    for game, tool in settings.get("compatTools", {}).items():
        a = appid(game)
        if a:
            wanted[a] = tool
    if wanted:
        set_compat_tools(wanted)

    if settings.get("steamInput") is False:
        games = installed() if games is None else games
        wanted = {a: "0" for a in games.values()}
        for game in settings.get("steamInputGames", []):
            a = appid(game)
            if a:
                wanted[a] = "2"
        set_steam_input(wanted)


if __name__ == "__main__":
    main()
