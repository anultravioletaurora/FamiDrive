"""famidrive-kodi prepare SPEC_JSON | library SPEC_JSON

Kodi on a FamiDrive box (modules/famidrive/media.nix), as each player.

prepare: before Kodi starts. The box's media folders (famidrive.media.kodi
  .sources) go into Kodi's sources.xml next to any the player added, and
  FamiDrive's add-ons are switched on in Kodi's add-on database.

library: while Kodi runs (started in the background by the Media entry).
  Kodi keeps what each folder holds ("Movies", "TV shows") and which
  scraper reads it in its video database, not in sources.xml, and only
  makes that database once it's running. So this waits for it, sets each
  folder's content and scraper (what "Set content" does by hand), and
  asks Kodi to scan, so new files on the drive turn up on their own.

Spec: {"sources": {name: {"path", "content"}}, "addons": [ids]}.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

KODI = Path(os.environ.get("KODI_HOME") or Path.home() / ".kodi")
USERDATA = KODI / "userdata"
DATABASE = USERDATA / "Database"

# Kodi's own scrapers (shipped with Kodi), and how it scans each kind of
# folder: movies anywhere under it, a TV show per folder.
CONTENT = {
    "movies": {"scraper": "metadata.themoviedb.org.python", "recursive": 2147483647},
    "tvshows": {"scraper": "metadata.tvshows.themoviedb.org.python", "recursive": 0},
}


def log(msg):
    print(f"famidrive-kodi: {msg}", file=sys.stderr, flush=True)


def folder(path):
    return path if path.endswith("/") else path + "/"


def write_sources(sources):
    """Merges the box's folders into sources.xml's <video> section. A
    player's own sources stay; one with a box folder's name or path is
    replaced by the box's."""
    path = USERDATA / "sources.xml"
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("sources")
    video = root.find("video")
    if video is None:
        video = ET.SubElement(root, "video")
        ET.SubElement(video, "default", pathversion="1")
    ours = {folder(s["path"]) for s in sources.values()}
    for src in list(video.findall("source")):
        if src.findtext("name") in sources or folder(src.findtext("path") or "") in ours:
            video.remove(src)
    for name, s in sorted(sources.items()):
        src = ET.SubElement(video, "source")
        ET.SubElement(src, "name").text = name
        ET.SubElement(src, "path", pathversion="1").text = folder(s["path"])
        ET.SubElement(src, "allowsharing").text = "true"
    before = path.read_bytes() if path.exists() else None
    ET.indent(root)
    after = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    if after != before:
        USERDATA.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)


def newest(pattern):
    """Kodi's current database of a kind: MyVideos131.db, Addons33.db, …"""
    found = sorted(DATABASE.glob(pattern), key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    return found[-1] if found else None


def enable_addons(ids):
    """Add-ons come from Nix, outside Kodi's own installer, which can
    leave them switched off. Before Kodi's first run there's no database
    yet: Kodi adds them itself, and the next start switches them on."""
    db = newest("Addons*.db")
    if not db or not ids:
        return
    with sqlite3.connect(db, timeout=10) as c:
        for addon in ids:
            c.execute("UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=?", (addon,))


def set_content(db, sources):
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


def cmd_prepare(spec):
    if spec["sources"]:
        write_sources(spec["sources"])
    enable_addons(spec.get("addons", []))


def cmd_library(spec, wait=120):
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


def main():
    cmd, spec = sys.argv[1], json.loads(sys.argv[2])
    {"prepare": cmd_prepare, "library": cmd_library}[cmd](spec)


if __name__ == "__main__":
    main()
