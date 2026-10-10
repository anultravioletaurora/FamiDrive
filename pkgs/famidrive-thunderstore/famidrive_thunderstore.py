"""famidrive-thunderstore SPEC_JSON

Brings a player's BepInEx mods from Thunderstore in line with their
config (players.<name>.thunderstore). Runs at activation, as the player,
on packages Nix has already fetched. Spec:

    {"games": {appid: {"bepinex": {"package", "zip"},
                       "mods": {id: zip}, "onlyListed": bool}}}

where an id is Thunderstore's Author-Name-Version, the same ids a
dedicated server's mod list or an r2modman profile uses.

For each game, in the player's own Steam library:

- BepInEx itself (the game's BepInExPack) is unpacked into the game's
  folder, again only when its version changes. Whatever folder the pack
  keeps BepInEx in (BepInExPack_Valheim/, BepInExPack/) is the game's
  folder.
- Each mod goes where r2modman would put it: its plugins/, patchers/ and
  core/ folders into BepInEx/<folder>/<Author-Name>/, its config/ into
  BepInEx/config/ (never over a config that's already there), and
  anything else into BepInEx/plugins/<Author-Name>/.
- onlyListed: plugins and patchers that aren't listed (and didn't come
  with BepInEx) are moved to BepInEx/plugins-off/ and patchers-off/, not
  deleted, so the game matches a server's pack exactly.
- A mod that needs another (its manifest's dependencies) that isn't
  listed is logged: dependencies aren't added for you.

Nothing happens for a game until it's installed through Steam. A game
taken out of the config keeps its files; its launch options (which load
BepInEx) are cleared by famidrive-steam-config, so it starts unmodded.
"""

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

STEAM = Path.home() / ".local/share/Steam"
MARK = ".famidrive-version"
NOT_FILES = ("manifest.json", "icon.png", "README.md", "CHANGELOG.md", "LICENSE")


def log(msg):
    print(f"famidrive-thunderstore: {msg}", file=sys.stderr)


def game_dir(appid):
    libraries = [STEAM / "steamapps"]
    try:
        folders = (STEAM / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        libraries += [Path(p) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', folders)]
    except OSError:
        pass
    for lib in libraries:
        try:
            text = (lib / f"appmanifest_{appid}.acf").read_text(errors="replace")
        except OSError:
            continue
        m = re.search(r'"installdir"\s+"([^"]+)"', text)
        if m and (lib / "common" / m.group(1)).is_dir():
            return lib / "common" / m.group(1)
    return None


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def extract(zf, member, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)
    if target.suffix == ".sh":
        target.chmod(0o755)


def pack_root(names):
    """The folder in a BepInExPack's zip that holds BepInEx/ ("" for the
    zip's top level), or None."""
    for n in sorted((n.replace("\\", "/") for n in names), key=len):
        if n.startswith("BepInEx/core/"):
            return ""
        i = n.find("/BepInEx/core/")
        if i >= 0:
            return n[:i + 1]
    return None


def install_bepinex(game, package, zip_path):
    """Returns the names BepInEx itself puts in plugins/."""
    with zipfile.ZipFile(zip_path) as zf:
        prefix = pack_root(zf.namelist())
        if prefix is None:
            raise ValueError(f"{package} has no BepInEx/core")
        rel = {}
        for m in zf.namelist():
            path = m.replace("\\", "/")
            if path.startswith(prefix) and not path.endswith("/") and path not in NOT_FILES:
                rel[m] = path[len(prefix):]
        shipped = {r.split("/")[2] for r in rel.values()
                   if r.startswith("BepInEx/plugins/") and len(r.split("/")) > 3}
        if read(game / "BepInEx" / MARK) != package:
            for m, r in rel.items():
                extract(zf, m, game / r)
            (game / "BepInEx" / MARK).write_text(package)
            log(f"{game.name}: {package}")
    return shipped


def dependencies(zip_path):
    """Author-Name of each package a mod's manifest says it needs."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8-sig"))
    except (KeyError, ValueError, OSError, zipfile.BadZipFile):
        return []
    return [d.rsplit("-", 1)[0] for d in manifest.get("dependencies", []) if d.count("-") >= 2]


def install_mod(game, ident, zip_path):
    """Returns the plugins/ entry name the mod lives under."""
    author, name, version = ident.rsplit("-", 2)
    folder = f"{author}-{name}"
    bep = game / "BepInEx"
    if read(bep / "plugins" / folder / MARK) == version:
        return folder
    for kind in ("plugins", "patchers", "core"):
        shutil.rmtree(bep / kind / folder, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as zf:
        for m in zf.namelist():
            path = m.replace("\\", "/")   # some are zipped on Windows with \ paths
            if path.endswith("/"):
                continue
            top, _, rest = path.partition("/")
            if top in ("plugins", "patchers", "core") and rest:
                extract(zf, m, bep / top / folder / rest)
            elif top == "config" and rest:
                if not (bep / "config" / rest).exists():
                    extract(zf, m, bep / "config" / rest)
            elif path in NOT_FILES:
                continue
            else:
                extract(zf, m, bep / "plugins" / folder / path)
    (bep / "plugins" / folder).mkdir(parents=True, exist_ok=True)
    (bep / "plugins" / folder / MARK).write_text(version)
    log(f"{game.name}: {ident}")
    return folder


def turn_off_unlisted(game, keep):
    for kind in ("plugins", "patchers"):
        here, off = game / "BepInEx" / kind, game / "BepInEx" / f"{kind}-off"
        for entry in sorted(here.iterdir()) if here.is_dir() else []:
            if entry.name in keep or entry.name.startswith("."):
                continue
            off.mkdir(exist_ok=True)
            target = off / entry.name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            entry.rename(target)
            log(f"{game.name}: turned off {kind}/{entry.name} (moved to BepInEx/{kind}-off)")


def sync_game(appid, g):
    game = game_dir(appid)
    if game is None:
        log(f"{appid} isn't installed through Steam; skipped")
        return
    keep = install_bepinex(game, g["bepinex"]["package"], g["bepinex"]["zip"])
    listed = {ident.rsplit("-", 1)[0] for ident in g["mods"]}
    listed.add(g["bepinex"]["package"].rsplit("-", 1)[0])
    for ident, z in g["mods"].items():
        keep.add(install_mod(game, ident, z))
        missing = [d for d in dependencies(z) if d not in listed]
        if missing:
            log(f"{game.name}: {ident} needs {', '.join(missing)}, which isn't listed")
    if g["onlyListed"]:
        turn_off_unlisted(game, keep)


def main():
    spec = json.loads(sys.argv[1])
    failed = False
    for appid, g in spec["games"].items():
        try:
            sync_game(appid, g)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            log(f"{appid}: {e}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
