"""famidrive-valheim SPEC_JSON

Brings Valheim's BepInEx mods in line with famidrive.valheim. Runs at
activation, as the box's user, on Thunderstore packages Nix has already
fetched. Spec: {"bepinex": {"version", "zip"}, "mods": {id: zip},
"onlyListed": bool}, where an id is Thunderstore's Author-Name-Version.

- BepInEx itself (denikson's BepInExPack_Valheim) is unpacked into the
  game's folder, again only when its version changes.
- Each mod goes where r2modman would put it: its plugins/, patchers/ and
  core/ folders into BepInEx/<folder>/<Author-Name>/, its config/ into
  BepInEx/config/ (never over a config that's already there), and
  anything else into BepInEx/plugins/<Author-Name>/.
- onlyListed: plugins and patchers that aren't listed (and didn't come
  with BepInEx) are moved to BepInEx/plugins-off/ and patchers-off/, not
  deleted, so the game matches a
  server's pack exactly.

Nothing happens until Valheim is installed through Steam.
"""

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

STEAM = Path.home() / ".local/share/Steam"
APPID = "892970"
MARK = ".famidrive-version"


def log(msg):
    print(f"famidrive-valheim: {msg}", file=sys.stderr)


def game_dir():
    libraries = [STEAM / "steamapps"]
    try:
        folders = (STEAM / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        libraries += [Path(p) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', folders)]
    except OSError:
        pass
    for lib in libraries:
        try:
            text = (lib / f"appmanifest_{APPID}.acf").read_text(errors="replace")
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


def install_bepinex(game, version, zip_path):
    """Returns the names BepInEx itself puts in plugins/."""
    prefix = "BepInExPack_Valheim/"
    with zipfile.ZipFile(zip_path) as zf:
        files = [m for m in zf.namelist() if m.startswith(prefix) and not m.endswith("/")]
        shipped = {m[len(prefix):].split("/")[2] for m in files
                   if m[len(prefix):].startswith("BepInEx/plugins/")}
        if read(game / "BepInEx" / MARK) != version:
            for m in files:
                extract(zf, m, game / m[len(prefix):])
            (game / "BepInEx" / MARK).write_text(version)
            log(f"BepInEx {version}")
    return shipped


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
            elif path in ("manifest.json", "icon.png", "README.md", "CHANGELOG.md", "LICENSE"):
                continue
            else:
                extract(zf, m, bep / "plugins" / folder / path)
    (bep / "plugins" / folder).mkdir(parents=True, exist_ok=True)
    (bep / "plugins" / folder / MARK).write_text(version)
    log(f"{ident}")
    return folder


def main():
    spec = json.loads(sys.argv[1])
    game = game_dir()
    if game is None:
        log("Valheim isn't installed; skipped")
        return
    keep = install_bepinex(game, spec["bepinex"]["version"], spec["bepinex"]["zip"])
    keep |= {install_mod(game, ident, z) for ident, z in spec["mods"].items()}
    if spec["onlyListed"]:
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
                log(f"turned off {kind}/{entry.name} (moved to BepInEx/{kind}-off)")


if __name__ == "__main__":
    main()
