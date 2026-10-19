"""famidrive-kodi prepare SPEC_JSON | library SPEC_JSON

Kodi on a FamiDrive box (modules/famidrive/media.nix), as each player.

prepare: before Kodi starts. The box's media folders (famidrive.media.kodi
  .sources), and folders in the player's own home (.homeFolders: their
  Recordings), go into Kodi's sources.xml next to any the player added, and
  FamiDrive's add-ons are switched on in Kodi's add-on database. Add-on
  settings FamiDrive knows (JellyCon's server) go into each add-on's
  settings.xml; the rest of each file stays the player's.

library: while Kodi runs (started in the background by the Media entry).
  Kodi keeps what each folder holds ("Movies", "TV shows") and which
  scraper reads it in its video database, not in sources.xml, and only
  makes that database once it's running. So this waits for it, sets each
  folder's content and scraper (what "Set content" does by hand), and
  asks Kodi to scan, so new files on the drive turn up on their own.

Spec: {"sources": {name: {"path", "content"}},
       "homeFolders": {name: {"path" (under $HOME), "type": "videos"|"pictures"}},
       "addons": [ids], "addonSettings": {addon id: {setting id: value}}}.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

type Content = Literal["movies", "tvshows"]
type HomeKind = Literal["videos", "pictures"]
type SettingValue = str | int | bool


class Source(TypedDict):
    path: str
    content: Content


class HomeFolder(TypedDict):
    path: str
    type: HomeKind


class Spec(TypedDict):
    """What media.nix passes: see the docstring above."""
    sources: dict[str, Source]
    homeFolders: NotRequired[dict[str, HomeFolder]]
    addons: NotRequired[list[str]]
    addonSettings: NotRequired[dict[str, dict[str, SettingValue]]]


class Scan(TypedDict):
    scraper: str
    recursive: int


KODI = Path(os.environ.get("KODI_HOME") or Path.home() / ".kodi")
USERDATA = KODI / "userdata"
DATABASE = USERDATA / "Database"

# Kodi's own scrapers (shipped with Kodi), and how it scans each kind of
# folder: movies anywhere under it, a TV show per folder.
CONTENT: dict[Content, Scan] = {
    "movies": {"scraper": "metadata.themoviedb.org.python", "recursive": 2147483647},
    "tvshows": {"scraper": "metadata.tvshows.themoviedb.org.python", "recursive": 0},
}


def log(msg: str) -> None:
    print(f"famidrive-kodi: {msg}", file=sys.stderr, flush=True)


def folder(path: str) -> str:
    return path if path.endswith("/") else path + "/"


# sources.xml's section for each kind of home folder.
SECTION: dict[HomeKind, str] = {"videos": "video", "pictures": "pictures"}


def home_sources(folders: dict[str, HomeFolder] | None, kind: HomeKind) -> dict[str, str]:
    """The player's home folders of one kind, as {name: path}. One that
    isn't there yet (no screenshots taken) is left out until it is: Kodi
    would show it as a source it can't open."""
    found: dict[str, str] = {}
    for name, f in (folders or {}).items():
        path = Path.home() / f["path"]
        if f["type"] == kind and path.is_dir():
            found[name] = str(path)
    return found


def merge_section(root: ET.Element, section: str, sources: dict[str, str]) -> None:
    """Puts these {name: path} sources in one section of sources.xml. A
    player's own sources stay; one with the same name or path as one of
    these is replaced by it."""
    el = root.find(section)
    if el is None:
        el = ET.SubElement(root, section)
        ET.SubElement(el, "default", pathversion="1")
    ours = {folder(p) for p in sources.values()}
    for src in list(el.findall("source")):
        if src.findtext("name") in sources or folder(src.findtext("path") or "") in ours:
            el.remove(src)
    for name, p in sorted(sources.items()):
        src = ET.SubElement(el, "source")
        ET.SubElement(src, "name").text = name
        ET.SubElement(src, "path", pathversion="1").text = folder(p)
        ET.SubElement(src, "allowsharing").text = "true"


def write_sources(sources: dict[str, Source], home_folders: dict[str, HomeFolder] | None = None) -> None:
    """The box's folders and the player's home folders into sources.xml.
    Videos: the box's (scanned into the library, cmd_library) and the
    player's (Recordings: no content set, so Kodi lists their files under
    Videos > Files rather than looking them up as films). Pictures: the
    player's, in Kodi's Pictures."""
    path = USERDATA / "sources.xml"
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("sources")
    for kind, section in SECTION.items():
        wanted = home_sources(home_folders, kind)
        if kind == "videos":
            wanted.update({name: s["path"] for name, s in sources.items()})
        if wanted:
            merge_section(root, section, wanted)
    before = path.read_bytes() if path.exists() else None
    ET.indent(root)
    after = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    if after != before:
        USERDATA.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)


def newest(pattern: str) -> Path | None:
    """Kodi's current database of a kind: MyVideos131.db, Addons33.db, …"""
    found = sorted(DATABASE.glob(pattern), key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    return found[-1] if found else None


def enable_addons(ids: list[str]) -> None:
    """Add-ons come from Nix, outside Kodi's own installer, which can
    leave them switched off. Before Kodi's first run there's no database
    yet: Kodi adds them itself, and the next start switches them on."""
    db = newest("Addons*.db")
    if not db or not ids:
        return
    with sqlite3.connect(db, timeout=10) as c:
        for addon in ids:
            c.execute("UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=?", (addon,))


def set_content(db: Path, sources: dict[str, Source]) -> None:
    with sqlite3.connect(db, timeout=10) as c:
        for s in sources.values():
            kind = CONTENT[s["content"]]
            path = folder(s["path"])
            row = c.execute("SELECT idPath FROM path WHERE strPath=?", (path,)).fetchone()
            if row is None:
                c.execute("INSERT INTO path (strPath, dateAdded) VALUES (?, datetime('now'))", (path,))
                row = c.execute("SELECT idPath FROM path WHERE strPath=?", (path,)).fetchone()
            # The same columns Kodi's own "Set content" writes. Empty
            # settings: the scraper's defaults.
            c.execute("UPDATE path SET strContent=?, strScraper=?, scanRecursive=?, useFolderNames=0,"
                      " strSettings='', noUpdate=0, exclude=0 WHERE idPath=?",
                      (s["content"], kind["scraper"], kind["recursive"], row[0]))


def set_addon_settings(addon: str, values: dict[str, SettingValue]) -> None:
    """Sets these settings in an add-on's userdata/addon_data/<id>/
    settings.xml, in either of Kodi's formats (version 2's
    <setting id="x">value</setting>, or the older value="..."
    attribute). Every other setting stays as it is."""
    path = USERDATA / "addon_data" / addon / "settings.xml"
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("settings", version="2")
    v2 = root.get("version") == "2"
    found = {s.get("id"): s for s in root.findall("setting")}
    for key, value in values.items():
        el = found.get(key)
        if el is None:
            el = ET.SubElement(root, "setting", id=key)
        if v2:
            el.text = str(value)
            el.attrib.pop("default", None)   # "default" means unset to Kodi
        else:
            el.set("value", str(value))
    before = path.read_bytes() if path.exists() else None
    ET.indent(root)
    after = ET.tostring(root, encoding="utf-8") + b"\n"
    if after != before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)


def cmd_prepare(spec: Spec) -> None:
    if spec["sources"] or spec.get("homeFolders"):
        write_sources(spec["sources"], spec.get("homeFolders"))
    enable_addons(spec.get("addons", []))
    for addon, values in (spec.get("addonSettings") or {}).items():
        set_addon_settings(addon, values)


def cmd_library(spec: Spec, wait: float = 120) -> None:
    sources = spec["sources"]
    if not sources:
        return
    deadline = time.time() + wait
    db = newest("MyVideos*.db")
    while db is None and time.time() < deadline:
        time.sleep(2)
        db = newest("MyVideos*.db")
    if db is None:
        log("Kodi's video database never appeared; folders not set up")
        return
    time.sleep(3)   # let Kodi finish making it
    set_content(db, sources)
    # A drive that isn't plugged in is skipped, not scanned as empty
    # (scanning never removes; only "Clean library" does).
    if not any(Path(s["path"]).is_dir() for s in sources.values()):
        log("no media folder is there right now; nothing to scan")
        return
    # Kodi's EventServer, on by default and only on this machine.
    subprocess.run(["kodi-send", "--action=UpdateLibrary(video)"], check=False,
                   stdout=subprocess.DEVNULL)


def main() -> None:
    cmd = sys.argv[1]
    spec: Spec = json.loads(sys.argv[2])
    {"prepare": cmd_prepare, "library": cmd_library}[cmd](spec)


if __name__ == "__main__":
    main()
