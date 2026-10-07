"""romm-agent: the box's only link to RomM.

The library, shared by every player (run as famidrive-library):
    romm-agent pull                    mirror the library (or one collection), write gamelists
    romm-agent firmware                pull each platform's firmware

Each player's own (run as that player):
    romm-agent gamelists               copy the library's newest gamelists into ES-DE
    romm-agent firmware-install        run emulator firmware installs (keys, PS3 firmware)
    romm-agent eden-profile            give a new Eden this player's profile, before it first runs
    romm-agent textures                link the library's Dolphin texture packs and Switch mods into this player's emulators
    romm-agent eden-gamedir            point this player's Eden at the library's Switch folder (updates, DLC)
    romm-agent eden-save TITLE_ID      print where this player's Eden keeps that game's save
    romm-agent switch-dlc ROM          the game's DLC files and their content IDs, as JSON
    romm-agent save-pull SYSTEM ROM    newest save for ROM -> local (pre-launch)
    romm-agent save-push SYSTEM ROM    local save for ROM -> RomM (post-exit)
    romm-agent reconcile               push every local save RomM doesn't have yet

Apps that aren't ROMs (Clone Hero) sync the same way, as `save-pull APP
app:APP`: their saves go up under a RomM entry found by name (`apps` in
the config), so they sit in RomM with every other game's.

Config: $ROMM_AGENT_CONFIG, or /etc/famidrive/romm/<user>.json for
whoever runs it (romm-agent.nix writes one per player, and library.json).

`reconcile` doubles as the one-time import: copy old saves into each
emulator's save folder, run it, and RomM gets them in FamiDrive's format
under the token's user.

Endpoints checked against RomM 5.3.1's /openapi.json (2026-10-05). What
the server actually *returns* (field values, title_id formats per
platform, Range support) is still unconfirmed until it runs once against
a real server; those spots say VERIFY.
"""

import getpass
import hashlib
import fcntl
import io
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CFG = json.loads(Path(os.environ.get("ROMM_AGENT_CONFIG")
                      or f"/etc/famidrive/romm/{getpass.getuser()}.json").read_text())
BASE = CFG["url"].rstrip("/")
API = BASE + "/api"
DATA = Path(CFG["dataDir"])
# Box art and screenshots, in ES-DE's own layout (<system>/covers/<game>.png),
# so each player's ES-DE reads them straight from here (frontend.nix links
# its downloaded_media/<system> to MEDIA/<system>).
MEDIA = DATA / "media"
MEDIA_STATE = DATA / "media.json"   # rom id -> RomM's updated_at when fetched
# Dolphin HD texture packs: zips in a game's mod/ folder in RomM, unpacked
# once here (<system>/<game ID>/<pack>/), linked into each player's Dolphin.
TEXTURES = DATA / "textures"
TEXTURES_STATE = DATA / "textures.json"   # rom id -> RomM's updated_at, packs
DOLPHIN_TEXTURES = Path.home() / ".local/share/dolphin-emu/Load/Textures"
GAME_ID = re.compile(r"[A-Z0-9]{3}(?:[A-Z0-9]{3})?")
# Switch mods: zips in a game's mod/ folder in RomM, unpacked once here
# (switch/<title ID>/<mod>/) in an SD card's layout, linked into each
# player's Eden (load/ and sdmc/).
MODS = DATA / "mods"
MODS_STATE = DATA / "mods.json"   # rom id -> RomM's updated_at, mods
SWITCH_ID = re.compile(r"0100[0-9A-F]{12}")
GAMELISTS = DATA / "gamelists"  # the library's; each player's ES-DE gets a copy
# Shared, written by `pull` only: local ROM path -> {id, system, title_id}
INDEX = DATA / "index.json"
# Each player's own, in their home: this box as their RomM device, and
# what they've pushed of each ROM's save (learned save paths, last hash).
STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "romm-agent"
DEVICE = STATE / "device.json"
SAVES = STATE / "saves.json"
SNAPSHOT = STATE / "save-snapshot.json"  # pre-launch mtimes for learn-by-diff

# Eden (Switch). Profiles live in a binary profiles.dat: a 0x10 header,
# then 8 users of 0xC8 bytes each (16-byte ID, the ID again, 8-byte
# creation time, 32-byte nickname, 0x80 bytes of extra data). Seen on a
# real Eden 0.2.1 box. A user's saves are in a folder named by their ID's
# two 64-bit halves, high half first. Settings' current_user picks which
# user games run as.
EDEN = Path.home() / ".local/share/eden"
EDEN_PROFILES = EDEN / "nand/system/save/8000000000000010/su/avators/profiles.dat"
EDEN_CONFIG = Path.home() / ".config/eden/qt-config.ini"
EDEN_LOAD = EDEN / "load"
EDEN_SD = EDEN / "sdmc"
# Ryujinx (Ryubing), for the few Switch games run there (ryujinx.nix).
RYUJINX = Path.home() / ".config/Ryujinx"
EDEN_USER = 0xC8
# In save archives, Eden's profile folder is written as this, and becomes
# the box's own profile when unpacked: the same player's profile can have
# a different ID on each box.
PROFILE_SLOT = "@profile"
# Device saves: a game's save that belongs to the console, not a profile
# (Animal Crossing: New Horizons keeps its island there, Mario Kart 8
# Deluxe part of its data). Eden keeps them under an all-zero user ID.
# Found on the first box 2026-10-06.
EDEN_DEVICE = "0" * 32

# Every FamiDrive save lives in this RomM slot. The sync API pairs saves on
# (rom_id, slot), so a stable name keeps one box's pushes and another's
# pulls talking about the same save.
SLOT = "famidrive"
PAGE = 500

EP_ROMS = "/roms"                                      # paginated, ?collection_id= optional
EP_ROM = "/roms/{id}"
EP_ROM_CONTENT = "/roms/{id}/content/{file_name}"      # multi-file ROMs come back as a zip
EP_ROM_IDENTITY = "/roms/{id}/identity"                # PUT title_id back (needs roms.write)
EP_COLLECTIONS = "/collections"
EP_PLATFORMS = "/platforms"
EP_FIRMWARE = "/firmware"                              # ?platform_id=
EP_FIRMWARE_CONTENT = "/firmware/{id}/content/{file_name}"
EP_DEVICES = "/devices"
EP_SAVES = "/saves"                                    # GET ?rom_id=&device_id= / POST multipart
EP_SAVE_CONTENT = "/saves/{id}/content"


def session():
    s = requests.Session()
    # The library pull gets its token from systemd (LoadCredential).
    creds = os.environ.get("CREDENTIALS_DIRECTORY")
    token_file = Path(creds) / "romm-token" if creds else Path(CFG["tokenFile"])
    token = token_file.read_text().strip()
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def get(s, path, **kw):
    r = s.get(API + path, timeout=60, **kw)
    r.raise_for_status()
    return r


def system_for(rom):
    """RomM platform -> this box's system. RomM has a display slug and a
    folder slug (psx is `ps` vs `psx`, for one); either may match."""
    slugs = {rom.get("platform_fs_slug"), rom.get("platform_slug")}
    for name, sysdef in CFG["systems"].items():
        if sysdef["rommPlatform"] in slugs:
            return name
    return None


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


ARCHIVES = {".zip", ".7z", ".rar"}
# path -> [size, mtime_ns, sha1] of files already checked. Found on the
# first box 2026-10-06: every pull re-read the whole library (121 GB) to
# hash files it had checked the pull before.
HASHES = DATA / "hashes.json"


def known_sha1(path):
    """A file's sha1, read again only if it changed since it was hashed."""
    try:
        cache = json.loads(HASHES.read_text())
    except (OSError, ValueError):
        cache = {}
    st = path.stat()
    have = cache.get(str(path))
    if have and have[0] == st.st_size and have[1] == st.st_mtime_ns:
        return have[2]
    digest = sha1(path)
    cache[str(path)] = [st.st_size, st.st_mtime_ns, digest]
    try:
        HASHES.write_text(json.dumps(cache))
    except OSError:
        pass   # a player's run can't write the library's cache; fine
    return digest


def download(s, path, dest, expected_sha1=None, expected_size=None, params=None):
    """Resumable download: a 40 GB ISO must not restart from zero."""
    if dest.suffix.lower() in ARCHIVES:
        # RomM hashes what's inside an archive (so a zipped ROM matches its
        # known checksums), not the archive itself: only the size can be
        # checked. Found on the first box 2026-10-06, with a texture pack.
        expected_sha1 = None
    if dest.exists():
        if expected_sha1 and known_sha1(dest) == expected_sha1:
            return False
        if not expected_sha1 and (expected_size is None or dest.stat().st_size == expected_size):
            return False
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with s.get(API + path, headers=headers, params=params, stream=True, timeout=60) as r:
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"  # 200 = no Range support, start over
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(part, mode) as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    if expected_sha1 and known_sha1(part) != expected_sha1:
        part.unlink()
        raise RuntimeError(f"hash mismatch for {dest}, discarded")
    # By size: archives (RomM's hash is of their contents), and single
    # files fetched by id that RomM has no hash for (Switch content).
    by_size = dest.suffix.lower() in ARCHIVES or (not expected_sha1 and params)
    if by_size and expected_size and part.stat().st_size != expected_size:
        part.unlink()
        raise RuntimeError(f"size mismatch for {dest}, discarded")
    part.rename(dest)
    if expected_sha1:
        try:   # the hash just checked is the finished file's: keep it
            cache = json.loads(HASHES.read_text())
            cache[str(dest)] = cache.pop(str(part))
            HASHES.write_text(json.dumps(cache))
        except (OSError, ValueError, KeyError):
            pass
    return True


def device_id(s):
    """Register this box as one of the owner's RomM devices, once."""
    if DEVICE.exists():
        return json.loads(DEVICE.read_text())["device_id"]
    r = s.post(API + EP_DEVICES, timeout=60, json={
        "name": CFG["deviceName"],
        "hostname": socket.gethostname(),
        "platform": "linux",
        "client": "famidrive",
        "sync_mode": "api",
        "allow_existing": True,   # re-registering after a wipe reuses the device
    })
    r.raise_for_status()
    dev = r.json()
    DEVICE.parent.mkdir(parents=True, exist_ok=True)
    DEVICE.write_text(json.dumps(dev, indent=2))
    return dev["device_id"]


# ---------------------------------------------------------------- library


def all_roms(s, params):
    offset = 0
    while True:
        page = get(s, EP_ROMS, params={
            **params, "limit": PAGE, "offset": offset,
            "with_char_index": "false", "with_filter_values": "false",
            "with_rom_id_index": "false",
        }).json()
        yield from page["items"]
        offset += len(page["items"])
        if not page["items"] or (page.get("total") is not None and offset >= page["total"]):
            return


def library(s):
    """Every ROM, or one collection's when `collection` is set, and only
    the platforms in `platforms` when that's set (both can be)."""
    params = {}
    if CFG.get("collection"):
        cols = get(s, EP_COLLECTIONS).json()
        col = next(c for c in cols if c["name"] == CFG["collection"])
        params["collection_id"] = col["id"]
    if CFG.get("platforms"):
        wanted = set(CFG["platforms"])
        params["platform_ids"] = [p["id"] for p in get(s, EP_PLATFORMS).json()
                                  if wanted & {p.get("fs_slug"), p.get("slug")}]
        if not params["platform_ids"]:
            return iter(())
    return all_roms(s, params)


VERSION = re.compile(r"\bv(\d+(?:\.\d+)*)", re.I)


def newest(files):
    """The highest-versioned of several updates for one game ("… update
    v3.0.5.nsp" over v3.0.4); all of them when versions can't be read."""
    def version(f):
        m = VERSION.search(f["file_name"])
        return tuple(int(x) for x in m.group(1).split(".")) if m else None
    if len(files) < 2 or any(version(f) is None for f in files):
        return files
    return [max(files, key=version)]


def fetch_with_content(s, rom, system, categories):
    """A game whose folder in RomM holds more than the game: an update/
    and a dlc/ folder (RomM's file categories), say, for a Switch game.
    Each wanted file is fetched on its own (file_ids), never the folder as
    one zip: RomM has no hashes for these, and a 500 GB library must
    resume file by file. The folder keeps RomM's layout, which is what
    Eden reads updates and DLC from (ext_content_from_game_dirs), so they
    load for every player without installing anything. Returns the
    folder, or None when RomM has no game file for it (only an update)."""
    files = get(s, EP_ROM.format(id=rom["id"])).json().get("files") or []
    exts = {e.lower() for e in CFG["systems"][system].get("extensions", [])}
    games = [f for f in files if f.get("category") == "game"
             and Path(f["file_name"]).suffix.lower() in exts and not f["file_name"].startswith(".")]
    if not games:
        return None
    wanted = [(max(games, key=lambda f: f.get("file_size_bytes") or 0), Path())]
    for cat in categories:
        found = [f for f in files if f.get("category") == cat and Path(f["file_name"]).suffix.lower() in exts]
        wanted += [(f, Path(cat)) for f in (newest(found) if cat == "update" else found)]
    folder = DATA / "roms" / system / rom["fs_name"]
    keep = set()
    for f, sub in wanted:
        dest = folder / sub / f["file_name"]
        keep.add(dest)
        download(s, EP_ROM_CONTENT.format(id=rom["id"], file_name=f["file_name"]), dest,
                 f.get("sha1_hash") or None, f.get("file_size_bytes"), params={"file_ids": f["id"]})
    # An update RomM has replaced (or a DLC it dropped) goes, so the
    # library doesn't keep every version.
    for cat in categories:
        for old in (folder / cat).glob("*") if (folder / cat).is_dir() else []:
            if old.is_file() and old not in keep and not old.name.endswith(".part"):
                old.unlink()
    return folder


def fetch_rom(s, rom, system):
    """Single-file ROMs land as-is. Multi-file ROMs (Switch updates/DLC,
    PS3 and Wii U folders, multi-disc sets) come back from RomM as a zip and
    are unpacked into a folder of the same name. VERIFY per platform that
    ES-DE launches the folder the way each emulator expects."""
    categories = CFG["systems"][system].get("contentCategories") or []
    if categories and not rom.get("fs_extension"):
        folder = fetch_with_content(s, rom, system, categories)
        if folder is None:
            raise RuntimeError("RomM has no game file for it (only updates or DLC)")
        return folder
    dest = DATA / "roms" / system / rom["fs_name"]
    path = EP_ROM_CONTENT.format(id=rom["id"], file_name=rom["fs_name"])
    if not rom.get("has_multiple_files"):
        # A single file kept in a folder of its own: RomM's fs_name is the
        # folder's ("Mario Party 7", fs_extension empty), the file's is in
        # `files` ("Mario Party 7.iso"). RomM's fs_extension, not the name:
        # "Super Smash Bros. Melee" looks like it ends in ". Melee". Found on the first box 2026-10-06: without the
        # extension, ES-DE didn't list the game.
        files = rom.get("files") or []
        if not files and not rom.get("fs_extension") and rom.get("has_nested_single_file"):
            # RomM's ROM list sends `files` empty; the ROM's own page has
            # them. Found on the first box 2026-10-06.
            files = get(s, EP_ROM.format(id=rom["id"])).json().get("files") or []
        main = main_file(rom, files) if not rom.get("fs_extension") else None
        params = None
        size = rom.get("fs_size_bytes")
        if main:
            named = dest.with_name(main["file_name"])
            if dest.is_file() and not named.exists():
                dest.rename(named)   # pulled before under the folder's name
            dest = named
            if len(files) > 1:
                # The folder holds more than the game (a texture pack, a
                # hack): RomM serves the whole folder as a zip unless asked
                # for one file. Found on the first box 2026-10-06: Animal
                # Crossing's zip never matched the game's hash.
                path = EP_ROM_CONTENT.format(id=rom["id"], file_name=main["file_name"])
                params = {"file_ids": main["id"]}
                size = main.get("file_size_bytes")
        download(s, path, dest, rom.get("sha1_hash"), size, params=params)
        return dest
    done = dest / ".famidrive-complete"
    if done.exists():
        return dest
    archive = dest.with_name(dest.name + ".zip")
    download(s, path, archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    archive.unlink()
    done.touch()
    return dest


def main_file(rom, files):
    """The game's own file among a folder's: the one RomM's hash for the
    ROM is of, or the only one."""
    named = [f for f in files if f.get("file_name")]
    if len(named) == 1:
        return named[0]
    return next((f for f in named if f.get("sha1_hash") and f["sha1_hash"] == rom.get("sha1_hash")), None)


def launch_file(folder, system):
    """The file in a multi-file ROM's folder the emulator opens: the
    largest one at its top level with one of the system's extensions.
    Not RomM's .m3u, which lists every file, extras and all. Found on the
    first box 2026-10-06: GameCube folders held the game, a hack/ folder
    with a modded copy, and a stray ._.DS_Store, all in the .m3u."""
    exts = {e.lower() for e in CFG["systems"][system].get("extensions", [])} - {".m3u"}
    files = [p for p in folder.iterdir()
             if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in exts]
    return max(files, key=lambda p: p.stat().st_size) if files else None


def launchable(dest, system):
    """What ES-DE lists and launches for a ROM. A folder becomes a link
    next to it, named after it, to its launch file, and the folder itself
    is hidden from ES-DE (noload.txt), so the menu shows a game, not a
    folder to open."""
    if not dest.is_dir():
        return dest
    main = launch_file(dest, system)
    if main is None:
        return dest   # nothing recognizable: ES-DE shows the folder
    (dest / "noload.txt").touch()
    link = dest.with_name(dest.name + main.suffix)
    target = f"{dest.name}/{main.name}"
    if not (link.is_symlink() and os.readlink(link) == target):
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
    return link


def romm_title_id(system, tid):
    """RomM's title_id, in the form the save layouts use. Found on the
    first box 2026-10-06: RomM gave GameCube IDs as hex ("474D5045" for
    GMPE), and only the first four characters."""
    if tid and system in ("gc", "wii") and re.fullmatch(r"(?:[0-9A-Fa-f]{2}){4,6}", tid):
        try:
            text = bytes.fromhex(tid).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            return tid
        if text.isalnum():
            return text
    return tid


def switch_game_id(tid):
    return bool(tid) and re.fullmatch(r"0100[0-9A-Fa-f]{12}", tid) is not None


def title_id(system, rom, prev, path):
    """RomM's ID (rule 2), else what this box had, else read from the ROM.
    GameCube and Wii saves are named by the full six-character ID (game
    and maker), so a shorter one from RomM is completed from the disc."""
    tid = romm_title_id(system, rom.get("title_id"))
    had = romm_title_id(system, prev.get("title_id"))
    if system == "switch":
        # Only a game's own ID (0100…000-style) names its save folder.
        # Found on the first box 2026-10-06: RomM had 0105661981816000.
        tid = tid if switch_game_id(tid) else None
        had = had if switch_game_id(had) else None
    if system in ("gc", "wii") and (not tid or len(tid) != 6):
        # What this box worked out before counts only if it's complete:
        # an earlier pull may have kept RomM's hex as it was.
        return (had if had and len(had) == 6 else None) or derive_id(system, path) or tid
    return tid or had or derive_id(system, path)


def media_url(rel):
    """A RomM asset path, without its cache-busting ?ts=."""
    return BASE + rel.split("?")[0] if rel.startswith("/") else rel


def fetch_one(s, urls, dest_stem):
    """The first of `urls` that downloads, saved as dest_stem.<ext>, in
    place of any other extension's copy. RomM's own files go through its
    session; outside links (its SteamGridDB cover) without our token."""
    for url in urls:
        if not url:
            continue
        try:
            r = (s if url.startswith(BASE) else requests).get(url, timeout=60)
            r.raise_for_status()
        except requests.RequestException:
            continue
        kind = r.headers.get("content-type", "").split(";")[0]
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(kind)
        if not ext:
            continue
        dest_stem.parent.mkdir(parents=True, exist_ok=True)
        for old in dest_stem.parent.glob(dest_stem.name + ".*"):
            old.unlink()
        Path(str(dest_stem) + ext).write_bytes(r.content)
        return True
    return False


def fetch_media(s, rom, system, rel):
    """Cover and screenshot for one game, where ES-DE looks for them:
    MEDIA/<system>/covers/<game>.png, <game> being its file's path in the
    system folder without the extension. Fetched again only when RomM's
    entry changed. Found on the first box 2026-10-06: RomM listed
    covers it had no file for (404), so its cover link is the fallback."""
    state = json.loads(MEDIA_STATE.read_text()) if MEDIA_STATE.exists() else {}
    key = str(rom["id"])
    stem = Path(rel).with_suffix("")
    have = state.get(key)
    if have and have.get("updated_at") == rom.get("updated_at") and have.get("stem") == str(stem):
        return
    root = MEDIA / system
    got = fetch_one(s, [media_url(rom["path_cover_large"]) if rom.get("path_cover_large") else None,
                        media_url(rom["path_cover_small"]) if rom.get("path_cover_small") else None,
                        rom.get("url_cover")], root / "covers" / stem)
    shots = rom.get("merged_screenshots") or []
    fetch_one(s, [media_url(shots[0])] if shots else [], root / "screenshots" / stem)
    if got:
        state[key] = {"updated_at": rom.get("updated_at"), "stem": str(stem)}
        MEDIA_STATE.write_text(json.dumps(state, indent=2))


def dolphin_systems():
    return [n for n, d in CFG["systems"].items() if d.get("emulator") == "dolphin"]


def unpack_textures(archive, dest):
    """A Dolphin texture pack zip into dest. Packs usually hold one folder
    named for the game's ID (GAFE01, or GAF for every region); that folder
    is dropped, since dest is already the game's. False if the zip has no
    Dolphin textures (tex1_...) in it: some other kind of mod."""
    with zipfile.ZipFile(archive) as z:
        files = [i for i in z.infolist() if not i.is_dir()]
        if not any(Path(i.filename).name.startswith("tex1_") for i in files):
            return False
        tops = {i.filename.split("/")[0] for i in files}
        prefix = ""
        if len(tops) == 1 and all("/" in i.filename for i in files) and GAME_ID.fullmatch(next(iter(tops))):
            prefix = next(iter(tops)) + "/"
        tmp = dest.with_name(dest.name + ".unpacking")
        shutil.rmtree(tmp, ignore_errors=True)
        for i in files:
            rel = Path(i.filename[len(prefix):] if i.filename.startswith(prefix) else i.filename)
            if rel.is_absolute() or ".." in rel.parts or rel.name.startswith("._"):
                continue
            out = tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(out, "wb") as f:
                shutil.copyfileobj(src, f, 1 << 20)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return True


def eden_systems():
    return [n for n, d in CFG["systems"].items() if d.get("emulator") == "eden"]


def unpack_switch_mod(archive, dest, tid):
    """A Switch mod zip into dest, in an SD card's layout: the game's code
    and files under atmosphere/contents/<title ID>/ (exefs, romfs), and
    anything else as it is (ARCropolis's ultimate/mods/...). A yuzu-style
    mod (exefs/ and romfs/ at the top) is moved under its title ID. One
    folder around it all (the release's name) is dropped. False if it has
    none of these: not a Switch mod."""
    sd_tops = {"atmosphere", "ultimate", "exefs", "romfs"}
    with zipfile.ZipFile(archive) as z:
        files = [i for i in z.infolist() if not i.is_dir()
                 and not i.filename.startswith("__MACOSX/") and not Path(i.filename).name.startswith("._")]
        tops = {i.filename.split("/")[0] for i in files}
        prefix = ""
        if len(tops) == 1 and all("/" in i.filename for i in files) and next(iter(tops)).lower() not in sd_tops:
            prefix = next(iter(tops)) + "/"
        out = []
        for i in files:
            rel = Path(i.filename[len(prefix):])
            if rel.is_absolute() or ".." in rel.parts or len(rel.parts) < 2:
                continue
            top = rel.parts[0].lower()
            if top in ("exefs", "romfs"):
                rel = Path("atmosphere/contents", tid, top, *rel.parts[1:])
            elif top == "atmosphere":
                rel = Path("atmosphere", *rel.parts[1:])
            elif top not in sd_tops:
                continue
            out.append((i, rel))
        if not out:
            return False
        tmp = dest.with_name(dest.name + ".unpacking")
        shutil.rmtree(tmp, ignore_errors=True)
        for i, rel in out:
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(path, "wb") as f:
                shutil.copyfileobj(src, f, 1 << 20)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return True


def sync_textures(s, rom, system, tid):
    """This game's texture packs (Dolphin) or mods (Switch) from RomM: zips
    in its mod/ folder, when the game changed in RomM since the last look.
    A pack whose file changed is unpacked again; one gone from RomM is
    removed."""
    if system in dolphin_systems() and tid and GAME_ID.fullmatch(tid):
        root, state_file = TEXTURES, TEXTURES_STATE

        def unpack(archive, dest):
            return unpack_textures(archive, dest)
        kind = "texture pack"
    elif system in eden_systems() and tid and SWITCH_ID.fullmatch(tid):
        root, state_file = MODS, MODS_STATE

        def unpack(archive, dest):
            return unpack_switch_mod(archive, dest, tid)
        kind = "mod"
    else:
        return
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    key = str(rom["id"])
    have = state.get(key, {})
    if have.get("updated_at") == rom.get("updated_at"):
        return
    files = get(s, EP_ROM.format(id=rom["id"])).json().get("files") or []
    mods = [f for f in files if f.get("category") == "mod"
            and f["file_name"].lower().endswith(".zip") and not f["file_name"].startswith(".")]
    game = root / system / tid
    packs, keep = have.get("packs", {}), {}
    for f in mods:
        fid, old = str(f["id"]), have.get("packs", {}).get(str(f["id"]))
        if old and old.get("sha1") == f.get("sha1_hash") and (game / old["dir"]).is_dir():
            keep[fid] = old
            continue
        tmp = root / ".download" / f"{fid}.zip"
        download(s, EP_ROM_CONTENT.format(id=rom["id"], file_name=f["file_name"]), tmp,
                 f.get("sha1_hash"), f.get("file_size_bytes"), params={"file_ids": f["id"]})
        name = re.sub(r'[/\\:*?"<>|]', "_", Path(f["file_name"]).stem).strip() or fid
        if old:
            shutil.rmtree(game / old["dir"], ignore_errors=True)
        game.mkdir(parents=True, exist_ok=True)
        if unpack(tmp, game / name):
            keep[fid] = {"sha1": f.get("sha1_hash"), "dir": name}
            print(f"{kind} for {rom['fs_name']}: {f['file_name']}", file=sys.stderr)
        else:
            print(f"{f['file_name']} ({rom['fs_name']}) isn't a {kind} FamiDrive knows; left in RomM", file=sys.stderr)
        tmp.unlink(missing_ok=True)
    for fid, old in packs.items():
        if fid not in keep:
            shutil.rmtree(game / old["dir"], ignore_errors=True)
    if game.is_dir() and not any(game.iterdir()):
        game.rmdir()
    state[key] = {"updated_at": rom.get("updated_at"), "packs": keep}
    state_file.write_text(json.dumps(state, indent=2))


def cmd_textures():
    """Each of the library's texture packs, linked into this player's
    Dolphin as Load/Textures/<game ID>. A folder this player had there for
    the same game (by its full or 3-letter ID) is moved to
    Textures-before-romm, so Dolphin doesn't load two copies. Links to
    packs the library no longer has are removed."""
    shared = {}
    for system in dolphin_systems():
        if (TEXTURES / system).is_dir():
            shared.update({d.name: d for d in (TEXTURES / system).iterdir()
                           if d.is_dir() and GAME_ID.fullmatch(d.name)})
    DOLPHIN_TEXTURES.mkdir(parents=True, exist_ok=True)
    for p in DOLPHIN_TEXTURES.iterdir():
        if p.is_symlink() and str(os.readlink(p)).startswith(str(TEXTURES)) and p.name not in shared:
            p.unlink()
    before = DOLPHIN_TEXTURES.parent / "Textures-before-romm"
    for tid, d in sorted(shared.items()):
        for old in {DOLPHIN_TEXTURES / tid, DOLPHIN_TEXTURES / tid[:3]}:
            if old.exists() and not old.is_symlink():
                before.mkdir(exist_ok=True)
                dest = before / old.name
                if dest.exists():
                    dest = before / f"{old.name}.{int(time.time())}"
                old.rename(dest)
        link = DOLPHIN_TEXTURES / tid
        if link.is_symlink() and os.readlink(link) == str(d):
            continue
        if link.is_symlink():
            link.unlink()
        link.symlink_to(d)
    if eden_systems():
        link_switch_mods()


def link_switch_mods():
    """Each of the library's Switch mods, in this player's emulators.

    Eden: the game's part (atmosphere/contents/<title ID>) as
    load/<title ID>/<mod>, which Eden lists in the game's Add-ons, and the
    rest (ARCropolis's ultimate/mods/...) on its SD card, linked file by
    file: ARCropolis and the like write their own files beside them. A
    mod built on Skyline plugins (romfs/skyline/plugins, as HewDraw Remix
    is) is left out: Eden, like yuzu before it, can't run them, and the
    game crashes as it starts. Found on the first box 2026-10-07: Smash
    Ultimate with HDR hit a fatal error 4 s in.

    Ryujinx, for the games run there (switch.ryujinx.games): every mod,
    Skyline ones too, as mods/contents/<title ID>/<mod> and on its own
    SD card.

    A file of the player's own in the way is kept as <name>.before-romm.
    Links to what the library no longer has are removed."""
    ryujinx_games = {t.upper() for t in CFG.get("ryujinxGames") or []}
    targets = [(EDEN_LOAD, EDEN_SD, None)]
    if ryujinx_games:
        targets.append((RYUJINX / "mods/contents", RYUJINX / "sdcard", ryujinx_games))
    want = {}
    for system in eden_systems():
        for game in (MODS / system).iterdir() if (MODS / system).is_dir() else []:
            if not (game.is_dir() and SWITCH_ID.fullmatch(game.name)):
                continue
            for mod in game.iterdir():
                if not mod.is_dir():
                    continue
                code = mod / "atmosphere/contents" / game.name
                skyline = (code / "romfs/skyline/plugins").is_dir()
                for load, sd, games in targets:
                    if games is None and skyline:
                        print(f"{mod.name} needs Skyline, which Eden can't run; not added", file=sys.stderr)
                        continue
                    if games is not None and game.name.upper() not in games:
                        continue
                    if code.is_dir():
                        want[load / game.name / mod.name] = code
                    for dirpath, dirs, names in os.walk(mod):
                        rel = Path(dirpath).relative_to(mod)
                        if rel.parts[:1] == ("atmosphere",):
                            dirs[:] = []
                            continue
                        for n in names:
                            want[sd / rel / n] = Path(dirpath) / n
    for load, sd, _ in targets + [(RYUJINX / "mods/contents", RYUJINX / "sdcard", None)]:
        for base in (load, sd):
            for dirpath, dirs, names in os.walk(base):
                for n in dirs + names:
                    p = Path(dirpath) / n
                    if p.is_symlink() and os.readlink(p).startswith(str(MODS) + "/") and p not in want:
                        p.unlink()
    for link, target in want.items():
        if link.is_symlink():
            if os.readlink(link) == str(target):
                continue
            link.unlink()
        elif link.exists():
            link.rename(link.with_name(link.name + ".before-romm"))
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)


def cmd_pull():
    s = session()
    old = load_index()
    index, by_system, folders = {}, {}, set()
    for rom in library(s):
        system = system_for(rom)
        if system is None:
            continue  # a platform this box doesn't run (PC, iOS, ...)
        try:
            dest = fetch_rom(s, rom, system)
        except (requests.RequestException, RuntimeError, zipfile.BadZipFile) as e:
            print(f"skipped {rom['fs_name']}: {e}", file=sys.stderr)
            continue
        launch = launchable(dest, system)
        if dest != launch:
            folders.add(str(dest))
        prev = old.get(str(launch), {})
        tid = title_id(system, rom, prev, launch)
        if tid and not rom.get("title_id"):
            teach_romm(s, rom["id"], tid)
        index[str(launch)] = {"id": rom["id"], "system": system, "title_id": tid,
                              "name": rom.get("name") or rom.get("fs_name_no_ext")}
        try:
            rel = Path(launch).relative_to(DATA / "roms" / system)
        except ValueError:
            rel = Path(Path(launch).name)
        try:
            sync_textures(s, rom, system, tid)
        except (requests.RequestException, RuntimeError, OSError, zipfile.BadZipFile) as e:
            print(f"texture packs for {rom['fs_name']} skipped: {e}", file=sys.stderr)
        fetch_media(s, rom, system, rel)
        by_system.setdefault(system, []).append((rel, rom))
        save_index(index)  # a 800 GB first pull survives being interrupted

    for system, entries in by_system.items():
        write_gamelist(system, entries)

    # Deletion policy is undecided (roms.md). Report orphans and never delete.
    local = {str(p) for p in (DATA / "roms").glob("*/*")
             if p.parent.name in CFG["systems"] and not p.name.endswith(".part")}
    for orphan in sorted(local - set(index) - folders):
        print(f"not in RomM anymore (kept): {orphan}", file=sys.stderr)


def teach_romm(s, rom_id, tid):
    """Write an ID this box worked out back to RomM, so no other box has to.
    Needs the token to carry roms.write; quietly skipped without it."""
    try:
        s.put(API + EP_ROM_IDENTITY.format(id=rom_id), json={"title_id": tid}, timeout=60)
    except requests.RequestException:
        pass


# What a gamelist's game gets from RomM. Everything else in a player's
# copy (favorite, playcount, lastplayed, hidden, ...) is theirs, and kept.
FROM_ROMM = ("name", "desc", "rating", "releasedate", "developer", "publisher", "genre", "players")


def game_metadata(rom):
    """ES-DE's gamelist fields from RomM's metadata."""
    m = rom.get("metadatum") or {}
    fields = {"name": rom.get("name") or rom.get("fs_name_no_ext"), "desc": rom.get("summary") or ""}
    if m.get("average_rating"):
        fields["rating"] = f"{min(m['average_rating'], 100) / 100:.2f}"
    if m.get("first_release_date"):
        day = datetime.fromtimestamp(m["first_release_date"] / 1000, tz=timezone.utc)
        fields["releasedate"] = day.strftime("%Y%m%dT000000")
    for field, key in (("developer", "developers"), ("publisher", "publishers"), ("genre", "genres")):
        if m.get(key):
            fields[field] = ", ".join(m[key][:2] if field != "genre" else m[key])
    if m.get("player_count"):
        fields["players"] = m["player_count"]
    return fields


def write_gamelist(system, entries):
    out = GAMELISTS / system / "gamelist.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    games = []
    for rel, rom in entries:
        fields = {"path": f"./{rel}", **game_metadata(rom)}
        games.append("  <game>\n" + "".join(
            f"    <{k}>{escape(str(v))}</{k}>\n" for k, v in fields.items()) + "  </game>\n")
    out.write_text('<?xml version="1.0"?>\n<gameList>\n'
                   + "".join(games) + "</gameList>\n")


def merge_gamelist(library, mine):
    """The library's gamelist, with this player's own fields kept: RomM
    has the say on what a game is, the player on how they've played it.
    Games only the player's copy has stay too."""
    lib_root = ET.parse(library).getroot()
    try:
        my_root = ET.parse(mine).getroot()
    except (OSError, ET.ParseError):
        my_root = ET.Element("gameList")
    mine_by_path = {g.findtext("path"): g for g in my_root.findall("game")}
    out = ET.Element("gameList")
    for game in lib_root.findall("game"):
        path = game.findtext("path")
        merged = ET.SubElement(out, "game")
        for child in game:
            merged.append(child)
        old = mine_by_path.pop(path, None)
        if old is not None:
            for child in old:
                if child.tag != "path" and child.tag not in FROM_ROMM and child.tag != "image":
                    merged.append(child)
    for left in mine_by_path.values():
        out.append(left)
    for other in my_root:
        if other.tag != "game":   # ES-DE's <folder> entries
            out.append(other)
    ET.indent(out)
    return b'<?xml version="1.0"?>\n' + ET.tostring(out, encoding="utf-8") + b"\n"


# ---------------------------------------------------------------- firmware

INSTALLERS = {
    # No PS3 entry: RPCS3 installs firmware only through its window, which
    # asks "Install?" first and says "Success" after, and both wait for a
    # click. Found on the first box 2026-10-06: run at each session start,
    # under ES-DE, the window never showed and RPCS3 waited forever, a new
    # one every session; offscreen it installed nothing. Until there's a
    # way without the window (#48), install it once from RPCS3 itself.
    # Eden reads prod.keys/title.keys from its keys dir (seen on Eden 0.2.1).
    # Firmware goes into nand/system; installing it non-interactively: TODO.
    "switch": lambda d: [
        (Path.home() / ".local/share/eden/keys").mkdir(parents=True, exist_ok=True),
        *[(Path.home() / ".local/share/eden/keys" / k.name).write_bytes(k.read_bytes())
          for k in d.glob("*.keys")],
    ],
}


def cmd_firmware():
    s = session()
    platforms = {}
    for p in get(s, EP_PLATFORMS).json():
        platforms[p["fs_slug"]] = p["id"]
        platforms.setdefault(p["slug"], p["id"])
    wanted = set(CFG["firmwarePlatforms"])
    for system, sysdef in CFG["systems"].items():
        slug = sysdef["rommPlatform"]
        if slug not in wanted or slug not in platforms:
            continue
        target = firmware_dir(system, sysdef)
        for fw in get(s, EP_FIRMWARE, params={"platform_id": platforms[slug]}).json():
            download(s, EP_FIRMWARE_CONTENT.format(id=fw["id"], file_name=fw["file_name"]),
                     target / fw["file_name"], fw.get("sha1_hash"), fw.get("file_size_bytes"))


def firmware_dir(system, sysdef):
    # RetroArch cores share one system dir, so their firmware lands flat
    # in firmware/retroarch; everything else gets firmware/<slug>.
    return DATA / "firmware" / (sysdef.get("firmwareDir") or sysdef["rommPlatform"])


def cmd_firmware_install():
    """Install the library's firmware into this player's emulators, again
    whenever the library's copy changes. Run at the start of each session."""
    for system, install in INSTALLERS.items():
        sysdef = CFG["systems"].get(system)
        if not sysdef:
            continue
        target = firmware_dir(system, sysdef)
        files = sorted(p for p in target.glob("*") if p.is_file()) if target.is_dir() else []
        if not files:
            continue
        stamp = json.dumps([[p.name, p.stat().st_size, int(p.stat().st_mtime)] for p in files])
        marker = STATE / f"firmware-{system}.json"
        if marker.exists() and marker.read_text() == stamp:
            continue
        install(target)
        STATE.mkdir(parents=True, exist_ok=True)
        marker.write_text(stamp)


def cmd_gamelists():
    """Merge each system's gamelist from the library into this player's
    ES-DE, when the library has written a newer one since the last time:
    RomM's metadata in, the player's favorites and play counts kept.
    ES-DE rewrites its own copy (play counts, favorites) in between."""
    copied_file = STATE / "gamelists.json"
    copied = json.loads(copied_file.read_text()) if copied_file.exists() else {}
    for src in sorted(GAMELISTS.glob("*/gamelist.xml")):
        system, mtime = src.parent.name, src.stat().st_mtime
        if copied.get(system) == mtime:
            continue
        dest = Path(CFG["gamelistDir"]) / system / "gamelist.xml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(merge_gamelist(src, dest))
        copied[system] = mtime
    STATE.mkdir(parents=True, exist_ok=True)
    copied_file.write_text(json.dumps(copied, indent=2))


# ---------------------------------------------------------------- game IDs
#
# roms.md "Mapping saves to games". IDs are only needed to pick which
# local files belong to a ROM when pushing. Pulling a save never needs
# one, because the archive carries its own relative paths and manifest.


def toast(*args):
    """A toast on the TV (famidrive-toast), when the player's session has
    one to show it. Never fails the caller."""
    exe = shutil.which("famidrive-toast")
    if exe:
        try:
            subprocess.run([exe, *args], timeout=5, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass


def game_name(key, entry):
    """The game's name from RomM, or its file's without the tags."""
    return entry.get("name") or re.sub(r"\s*[\(\[].*$", "", Path(key).stem) or Path(key).name


def load_index():
    return json.loads(INDEX.read_text()) if INDEX.exists() else {}


def save_index(index):
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=2))


def load_saves():
    return json.loads(SAVES.read_text()) if SAVES.exists() else {}


def store_saves(saves):
    """Written whole and then put in place, so another run never reads a
    half-written file."""
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = SAVES.with_name(SAVES.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(saves, indent=2))
    tmp.replace(SAVES)


def app_id(name):
    """RomM's id for an app's entry (an entry added by hand, so its
    saves have somewhere to live), found by its name once and kept."""
    saves = load_saves()
    key = f"app:{name}"
    if saves.get(key, {}).get("id"):
        return saves[key]["id"]
    want = CFG["apps"][name]["rom"]
    s = session()
    found = [r for r in all_roms(s, {"search_term": want})
             if want in (r.get("name"), r.get("fs_name_no_ext"), r.get("fs_name"))]
    if not found:
        raise RuntimeError(f"RomM has no entry named {want!r} for {name}'s saves")
    saves.setdefault(key, {})["id"] = found[0]["id"]
    store_saves(saves)
    return found[0]["id"]


def target(system):
    """A system's, or an app's, definition from the config."""
    return CFG["systems"].get(system) or CFG.get("apps", {})[system]


def library_path(rom_path):
    """The library's path for a ROM. ES-DE hands over paths in the
    player's own ROM folder, whose systems are links into the library."""
    p = Path(rom_path)
    if CFG.get("playerRoms"):
        try:
            return str(DATA / "roms" / p.relative_to(CFG["playerRoms"]))
        except ValueError:
            pass
    return str(p)


def iso_member(iso, member):
    """Extract one file from an ISO via 7-Zip, without unpacking 40 GB."""
    r = subprocess.run(["7zz", "e", "-so", str(iso), member],
                       capture_output=True, check=False)
    return r.stdout if r.returncode == 0 else None


def sfo_title_id(sfo):
    """TITLE_ID out of a PS3 PARAM.SFO (fixed little-endian layout)."""
    _, _, key_tab, data_tab, count = struct.unpack_from("<4sIIII", sfo, 0)
    for i in range(count):
        key_off, _, length, _, data_off = struct.unpack_from("<HHIII", sfo, 20 + i * 16)
        key = sfo[key_tab + key_off:].split(b"\0", 1)[0]
        if key == b"TITLE_ID":
            return sfo[data_tab + data_off:data_tab + data_off + length].rstrip(b"\0").decode()
    return None


SWITCH_TID = re.compile(r"\[(0100[0-9A-Fa-f]{12})\]")


def pfs0_names(path):
    """The file names inside an NSP (a PFS0 archive), from its header."""
    with open(path, "rb") as f:
        head = f.read(16)
        if len(head) < 16 or head[:4] != b"PFS0":
            return []
        count, strings = struct.unpack_from("<II", head, 4)
        if count > 100000 or strings > 1 << 24:
            return []
        entries = f.read(count * 0x18)
        table = f.read(strings)
    names = []
    for i in range(count):
        _, _, at, _ = struct.unpack_from("<QQII", entries, i * 0x18)
        end = table.find(b"\0", at)
        names.append(table[at:end if end >= 0 else None].decode("utf-8", "replace"))
    return names


def switch_title_id(game):
    """A Switch game's title ID from its NSP: a ticket is named after its
    rights ID, which starts with the title ID. RomM's Switch file names
    don't carry it (found on the first box 2026-10-06). An XCI has no
    tickets; then its update's (update/*.nsp, title ID + 0x800) gives the
    game's."""
    def from_tickets(path, update=False):
        for name in pfs0_names(path):
            m = re.fullmatch(r"([0-9A-Fa-f]{16})[0-9A-Fa-f]{16}\.tik", name)
            if m:
                tid = m.group(1).upper()
                return tid[:-3] + "000" if update else tid
        return None
    try:
        tid = from_tickets(game)
        if tid:
            return tid
        for upd in sorted((game.parent / "update").glob("*.nsp")):
            tid = from_tickets(upd, update=True)
            if tid:
                return tid
    except OSError:
        pass
    return None


def eden_header_key():
    """The NCA header key from this player's Eden keys, or None."""
    try:
        text = (EDEN / "keys" / "prod.keys").read_text(errors="replace")
    except OSError:
        return None
    m = re.search(r"^header_key\s*=\s*([0-9A-Fa-f]{64})\s*$", text, re.M)
    return bytes.fromhex(m.group(1)) if m else None


def nca_header(f, offset, key):
    """(title ID, content type) from an NCA's header: its first 0xC00
    bytes are AES-XTS encrypted with the header key, in 0x200-byte
    sectors whose tweak is the sector number, big-endian. After the NCA3
    magic at 0x200: the content type at 0x205 (0 program, 1 meta,
    2 control, 3 manual, 4 data, 5 public data: a DLC's content) and the
    title ID at 0x210."""
    f.seek(offset)
    raw = f.read(0x400)
    if len(raw) < 0x400:
        return None
    plain = b"".join(
        Cipher(algorithms.AES(key), modes.XTS(n.to_bytes(16, "big"))).decryptor().update(raw[n * 0x200:(n + 1) * 0x200])
        for n in range(2))
    if plain[0x200:0x204] not in (b"NCA3", b"NCA2"):
        return None
    return "%016X" % struct.unpack_from("<Q", plain, 0x210)[0], plain[0x205]


def nca_program_id(f, offset, key):
    header = nca_header(f, offset, key)
    return header[0] if header else None


def cmd_switch_dlc(rom):
    """A Switch game's DLC from the library, for an emulator that needs it
    listed (Ryujinx's dlc.json): each NSP in the dlc/ folder beside the
    game, with its content NCAs (public data) and their title IDs, read
    with this player's Eden keys. JSON on stdout."""
    key = eden_header_key()
    folder = Path(rom).resolve().parent / "dlc"
    out = []
    for nsp in sorted(folder.glob("*.nsp")) if key and folder.is_dir() else []:
        ncas = []
        with open(nsp, "rb") as f:
            for name, at in pfs_entries(f, 0, b"PFS0", 0x18):
                header = nca_header(f, at, key) if name.endswith(".nca") else None
                if header and header[1] == 5:
                    ncas.append({"name": name, "title_id": header[0]})
        if ncas:
            out.append({"path": str(nsp), "ncas": ncas})
    print(json.dumps(out))


def pfs_entries(f, offset, magic, entry_size):
    """(name, data offset) of each file in a PFS0 or HFS0 at offset."""
    f.seek(offset)
    head = f.read(16)
    if head[:4] != magic:
        return []
    count, strings = struct.unpack_from("<II", head, 4)
    if count > 100000 or strings > 1 << 24:
        return []
    table_at = offset + 16 + count * entry_size
    entries = f.read(count * entry_size)
    f.seek(table_at)
    table = f.read(strings)
    data_at = table_at + strings
    out = []
    for i in range(count):
        at, _size, name_at = struct.unpack_from("<QQI", entries, i * entry_size)
        end = table.find(b"\0", name_at)
        out.append((table[name_at:end if end >= 0 else None].decode("utf-8", "replace"), data_at + at))
    return out


def switch_title_id_from_ncas(game, key):
    """A Switch game's title ID from its NCAs' headers, for an NSP or XCI
    without tickets (a cartridge dump). The base game's is the commonest
    one ending in 000. Found on the first box 2026-10-06: 17 of 67 games
    had no ticket to read it from."""
    ids = []
    with open(game, "rb") as f:
        # By what's in the file, not its name: Mario Tennis Aces in the
        # first box's RomM is an XCI named .nsp.
        f.seek(0x100)
        if f.read(4) == b"HEAD":
            f.seek(0x130)
            root, = struct.unpack("<Q", f.read(8))
            secure = dict(pfs_entries(f, root, b"HFS0", 0x40)).get("secure")
            ncas = pfs_entries(f, secure, b"HFS0", 0x40) if secure is not None else []
        else:
            ncas = pfs_entries(f, 0, b"PFS0", 0x18)
        for name, at in ncas:
            if name.endswith(".nca"):
                tid = nca_program_id(f, at, key)
                if tid:
                    ids.append(tid)
    base = [i for i in ids if i.endswith("000")]
    return max(set(base), key=base.count) if base else None


def derive_id(system, rom_path):
    """Local fallback when RomM has no title_id. None means learn by diff."""
    try:
        if system in ("gc", "wii"):
            out = subprocess.run(["dolphin-tool", "header", "-i", str(rom_path)],
                                 capture_output=True, text=True, check=True).stdout
            m = re.search(r"Game ID:\s*(\w{6})", out)  # VERIFY output format
            return m.group(1) if m else None
        if system == "ps2":
            cnf = iso_member(rom_path, "SYSTEM.CNF")
            m = cnf and re.search(rb"BOOT2\s*=\s*cdrom0:\\(\w{4})_(\d{3})\.(\d{2})", cnf)
            return f"{m[1].decode()}-{m[2].decode()}{m[3].decode()}" if m else None
        if system == "ps3":
            sfo = iso_member(rom_path, "PS3_GAME/PARAM.SFO")
            return sfo_title_id(sfo) if sfo else None
        if system == "switch":
            # Scene-style names carry it: "Game [01006BB00C6F0000][v0].nsp".
            # 62 of the TV box's 114 Switch files do.
            m = SWITCH_TID.search(Path(rom_path).name)
            if m:
                return m.group(1).upper()
            # Else the NSP's ticket, or its update's, next to it.
            return switch_title_id(Path(rom_path).resolve())
    except (subprocess.CalledProcessError, struct.error, FileNotFoundError):
        pass
    return None  # xbox360 and anything unreadable: rule 3


# ---------------------------------------------------------------- save layouts

DOLPHIN_REGION = {"E": "USA", "P": "EUR", "J": "JAP"}


def eden_folder(uid):
    lo, hi = int.from_bytes(uid[:8], "little"), int.from_bytes(uid[8:16], "little")
    return f"{hi:016X}{lo:016X}"


def eden_users():
    """Eden's users' save folder names, in profiles.dat's order."""
    try:
        raw = EDEN_PROFILES.read_bytes()
    except OSError:
        return []
    users = []
    for i in range(8):
        uid = raw[0x10 + i * EDEN_USER:0x10 + i * EDEN_USER + 16]
        if len(uid) == 16 and any(uid):
            users.append(eden_folder(uid))
    return users


def eden_profile():
    """The profile this player's Switch games save under: the one set in
    the module (players.<name>.edenProfileId), or else the user Eden runs
    games as."""
    if CFG.get("edenProfileId"):
        return CFG["edenProfileId"].upper()
    users = eden_users()
    if not users:
        return None
    try:
        m = re.search(r"^current_user=(\d+)$", EDEN_CONFIG.read_text(errors="replace"), re.M)
    except OSError:
        m = None
    i = int(m.group(1)) if m else 0
    return users[i] if i < len(users) else users[0]


def cmd_eden_gamedir():
    """This player's Eden reads the library's Switch folder, deep-scanned,
    for the updates and DLC beside each game (ext_content_from_game_dirs).
    Added to Eden's game folder list (a Qt settings array) if it isn't
    there; the player's other folders stay. Before Eden's first run there
    is no config: one with just this folder, which Eden fills in."""
    folder = str(DATA / "roms" / "switch")
    try:
        text = EDEN_CONFIG.read_text(errors="replace")
    except OSError:
        text = ""
    if re.search(rf"^Paths\\gamedirs\\\d+\\path={re.escape(folder)}$", text, re.M):
        return
    m = re.search(r"^Paths\\gamedirs\\size=(\d+)$", text, re.M)
    n = int(m.group(1)) + 1 if m else 1
    entry = (f"Paths\\gamedirs\\{n}\\path={folder}\n"
             f"Paths\\gamedirs\\{n}\\deep_scan\\default=false\n"
             f"Paths\\gamedirs\\{n}\\deep_scan=true\n"
             f"Paths\\gamedirs\\{n}\\expanded\\default=true\n"
             f"Paths\\gamedirs\\{n}\\expanded=true\n")
    if m:
        text = text[:m.start()] + f"Paths\\gamedirs\\size={n}\n" + entry + text[m.end() + 1:]
    elif "[UI]" in text:
        text = text.replace("[UI]\n", f"[UI]\nPaths\\gamedirs\\size={n}\n" + entry, 1)
    else:
        text += f"\n[UI]\nPaths\\gamedirs\\size={n}\n" + entry
    EDEN_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    EDEN_CONFIG.write_text(text)


def cmd_eden_profile():
    """Before this player's Eden first starts: give it one user, named
    after the player, with an ID derived from their RomM username, so a
    new box comes up with the same profile ID as the player's others.
    An Eden that already has profiles is left alone."""
    if EDEN_PROFILES.exists():
        return
    uid = hashlib.sha256(f"famidrive-eden:{CFG['owner']}".encode()).digest()[:16]
    # The Switch allows 10-character nicknames.
    name = (CFG.get("displayName") or CFG["owner"])[:10].encode()[:31]
    user = uid + uid + struct.pack("<Q", int(time.time())) + name.ljust(0x20, b"\0") + bytes(0x80)
    EDEN_PROFILES.parent.mkdir(parents=True, exist_ok=True)
    EDEN_PROFILES.write_bytes(bytes(0x10) + user + bytes(EDEN_USER * 7))


def to_archive(lay, rel):
    """A save path as it's stored in RomM: no box-specific profile ID."""
    if lay["kind"] == "eden-title-id" and lay.get("profile"):
        first, sep, rest = rel.partition("/")
        if first.upper() == lay["profile"].upper():
            return PROFILE_SLOT + sep + rest
    return rel


def from_archive(lay, rel):
    """A save path from RomM, put under this box's own profile. Also
    takes archives that name a profile ID outright."""
    if lay["kind"] == "eden-title-id":
        first, sep, rest = rel.partition("/")
        if first == EDEN_DEVICE:
            return rel   # the console's, the same on every box
        if first == PROFILE_SLOT or re.fullmatch(r"[0-9A-Fa-f]{32}", first):
            if not lay.get("profile"):
                raise RuntimeError("Eden has no profile here yet")
            return lay["profile"] + sep + rest
    return rel


def layout(system):
    lay = dict(target(system)["saveLayout"])
    # Profiles are the player's own (players.<name> in the module).
    if lay["kind"] == "eden-title-id":
        lay["profile"] = eden_profile()
    elif lay["kind"] == "xenia-content":
        lay["profile"] = CFG.get("xeniaXuid")
    return lay["kind"], Path(lay["root"]).expanduser(), lay


def cmd_eden_save(tid):
    """Where this player's Eden keeps a game's save (the profile's
    folder for it, existing or not). A Switch game run in Ryujinx instead
    is bridged through it (famidrive-ryujinx), so its save still syncs
    from the one place."""
    systems = eden_systems()
    if not systems:
        sys.exit("no Eden system on this box")
    _, root, lay = layout(systems[0])
    print(root / lay["profile"] / tid.upper())


def save_paths(system, entry, rom_path):
    """Files/dirs under the layout root that make up this ROM's save.

    Returns paths relative to the root, or None when the ID is unknown
    and nothing has been learned yet (rule 3 will fill it in).
    """
    kind, root, lay = layout(system)
    tid = entry.get("title_id")
    found = []

    if kind == "retroarch-srm":
        # RetroArch names the save after the file it was given, which is
        # the game's real path (emulators.nix), not ES-DE's link to it.
        found = [Path(rom_path).resolve().stem + ".srm"]
    elif kind == "dolphin-gci-folder" and tid:
        card = Path(DOLPHIN_REGION.get(tid[3], "USA")) / "Card A"
        maker = tid[4:6] or "??"   # a game-only ID still finds its saves
        found = [str(card / p.name) for p in (root / card).glob(f"{maker}-{tid[:4]}-*.gci")]
    elif kind == "dolphin-wii-title" and tid:
        found = [f"00010000/{tid[:4].encode().hex()}/data"]
    elif kind == "pcsx2-folder-memcard" and tid:
        card = Path(lay.get("card", "Mcd001.ps2"))
        found = [str(card / p.name) for p in (root / card).glob(f"B?{tid}*")]
    elif kind == "rpcs3-savedata" and tid:
        found = [p.name for p in root.glob(f"{tid}*")]
    elif kind == "eden-title-id" and tid and lay.get("profile"):
        # Revised 2026-10-05 (Eden, not Ryubing): one folder per game, named by
        # title ID, under the profile's folder. Seen on a real Eden 0.2.1 box.
        # Plus the game's device save, if it has one.
        found = [f"{lay['profile']}/{tid.upper()}", f"{EDEN_DEVICE}/{tid.upper()}"]
    elif kind == "xenia-content" and tid:
        found = [f"{lay['profile']}/{tid}/00000001"]
    elif kind == "files":
        found = list(lay["paths"])   # fixed files under the root (apps)

    found = [f for f in found if (root / f).exists()]
    return found or entry.get("learned") or None


def snapshot(root):
    return {str(p.relative_to(root)): p.stat().st_mtime
            for p in root.rglob("*") if p.is_file()} if root.exists() else {}


def learn_by_diff(root, before, depth=1):
    """Rule 3: save entries that changed during the session, `depth`
    levels down: 2 for Eden, whose top level is a whole profile (every
    game's saves), never one game's."""
    changed = {"/".join(Path(rel).parts[:depth]) for rel, mt in snapshot(root).items()
               if before.get(rel) != mt and len(Path(rel).parts) > depth}
    return sorted(changed)


def files_hash(root, rels, lay):
    """Hash of the save's actual contents, so an unchanged save is never
    re-uploaded (a tar.gz's own bytes change with every pack). Paths go
    in as they're archived, so the same save hashes the same on every box."""
    h = hashlib.sha256()
    for rel in sorted(rels):
        p = root / rel
        for f in sorted([p] if p.is_file() else [x for x in p.rglob("*") if x.is_file()]):
            h.update(to_archive(lay, str(f.relative_to(root))).encode() + b"\0")
            h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- save archives
#
# One RomM save per ROM = a tar.gz of the relevant paths (relative to the
# emulator's save root) + famidrive-manifest.json.


def pack(system, entry, root, rels, digest, lay):
    buf = io.BytesIO()
    manifest = {
        "system": system,
        "title_id": entry.get("title_id"),
        "paths": [to_archive(lay, r) for r in rels],
        "files_sha256": digest,
        "device": CFG["deviceName"],
        "owner": CFG["owner"],
        "packed_at": int(time.time()),
    }
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in rels:
            tar.add(root / rel, arcname=to_archive(lay, rel))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("famidrive-manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue(), manifest


def unpack(blob, root, lay):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        manifest = json.load(tar.extractfile("famidrive-manifest.json"))
        members = [m for m in tar.getmembers() if m.name != "famidrive-manifest.json"]
        for m in members:
            m.name = from_archive(lay, m.name)
        root.mkdir(parents=True, exist_ok=True)
        tar.extractall(root, members=members, filter="data")  # refuses ../ escapes
    return manifest


# ---------------------------------------------------------------- save commands


def same_time(a, b):
    """RomM gives the same moment in UTC after an upload and in the
    server's zone when listing. Found on the first box 2026-10-06:
    compared as text, every push looked like a conflict."""
    if not a or not b:
        return a == b
    try:
        return datetime.fromisoformat(a) == datetime.fromisoformat(b)
    except ValueError:
        return a == b


def unpushed(system, entry, root, lay, key):
    """Whether this box has a save for the ROM that RomM doesn't: one
    that changed since it was last pushed or pulled."""
    rels = save_paths(system, entry, key)
    return bool(rels) and files_hash(root, rels, lay) != entry.get("pushed")


def my_state(saves, key, rom_id):
    """This player's save state for a ROM, following it across a rename
    of its file: by RomM id, or for state from before ids were kept, by
    the name without the extension added since. Found on the first box
    2026-10-06: renamed games looked never synced, and their saves went
    up as conflicts."""
    mine = saves.setdefault(key, {})
    if "server_updated_at" in mine:
        return mine
    # Merged in, not just taken: the new name may already have state of
    # its own (a conflict copy pushed before this fix), but not the sync.
    index = load_index()
    for old in list(saves):
        if old == key or old in index or old.startswith("app:"):
            continue
        state = saves[old]
        if state.get("id") == rom_id or (state.get("id") is None and Path(old).name == Path(key).stem):
            for k, v in saves.pop(old).items():
                mine.setdefault(k, v)
            break
    return mine


def entry_for(key):
    """The library's entry for a ROM, with this player's save state on top."""
    if key.startswith("app:"):
        entry = {"id": app_id(key[4:]), "system": key[4:]}
    else:
        entry = dict(load_index()[key])
    mine = dict(my_state(load_saves(), key, entry["id"]))
    entry.update({k: v for k, v in mine.items() if k != "title_id"})
    entry["title_id"] = entry.get("title_id") or mine.get("title_id")
    if not entry["title_id"] and entry.get("system") == "switch" and not key.startswith("app:"):
        # The library can't read every Switch game's ID (no keys there);
        # this player's Eden has them. Worked out once, kept with the
        # player's save state.
        tid, hk = None, eden_header_key()
        if hk:
            try:
                tid = switch_title_id_from_ncas(Path(key).resolve(), hk)
            except (OSError, struct.error, ValueError):
                tid = None
        if tid:
            entry["title_id"] = tid
            saves = load_saves()
            my_state(saves, key, entry["id"])["title_id"] = tid
            store_saves(saves)
    return entry


def server_save(s, dev, rom_id):
    """The newest save in FamiDrive's slot for this ROM, or None."""
    saves = get(s, EP_SAVES, params={"rom_id": rom_id, "device_id": dev}).json()
    ours = [x for x in saves if x.get("slot") == SLOT]
    return max(ours, key=lambda x: x["updated_at"]) if ours else None


def cmd_save_pull(system, rom_path):
    kind, root, lay = layout(system)
    key = library_path(rom_path)
    STATE.mkdir(parents=True, exist_ok=True)
    # For rule 3 at push time; fixed files need no learning. Found on the
    # first box 2026-10-06: Clone Hero's root is the home folder, and
    # snapshotting all of it (Steam, songs) took 24 s before every launch.
    learns = kind != "files"
    if learns:
        SNAPSHOT.write_text(json.dumps(snapshot(root)))

    s = session()
    dev = device_id(s)
    entry = entry_for(key)
    newest = server_save(s, dev, entry["id"])
    if not newest:
        return
    if same_time(newest["updated_at"], entry.get("server_updated_at")):
        return   # RomM's is the one this box already has
    if unpushed(system, entry, root, lay, key):
        # Never overwrite a save RomM hasn't got. The push after the game
        # sends it up (beside RomM's, if RomM's changed meanwhile).
        print(f"local save for {rom_path} is newer than RomM knows; kept", file=sys.stderr)
        return
    blob = get(s, EP_SAVE_CONTENT.format(id=newest["id"]), params={"device_id": dev}).content
    try:
        manifest = unpack(blob, root, lay)
    except tarfile.ReadError:
        # A raw save uploaded by hand through RomM's web page, not a
        # FamiDrive archive. Restoring those isn't built yet (roms.md).
        print(f"save {newest['id']} isn't a FamiDrive archive, left alone", file=sys.stderr)
        return

    # The manifest can teach this box an ID it couldn't work out itself.
    saves = load_saves()
    e = my_state(saves, key, entry["id"])
    e["id"] = entry["id"]
    e["title_id"] = entry.get("title_id") or manifest.get("title_id")
    e["learned"] = entry.get("learned") or [from_archive(lay, p) for p in manifest.get("paths", [])]
    e["pushed"] = manifest.get("files_sha256")
    e["server_updated_at"] = newest["updated_at"]
    store_saves(saves)

    if learns:
        SNAPSHOT.write_text(json.dumps(snapshot(root)))  # don't count the restore as play


def save_is_empty(root, rels):
    """True when every file of the save has no bytes in it (or there are
    no files at all): something made the files and never wrote them."""
    for rel in rels:
        p = root / rel
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else []
        if any(f.stat().st_size > 0 for f in files):
            return False
    return True


def cmd_save_push(system, rom_path, learn=True):
    kind, root, lay = layout(system)
    key = library_path(rom_path)
    entry = entry_for(key)
    saves = load_saves()
    mine = my_state(saves, key, entry["id"])
    mine["id"] = entry["id"]

    rels = save_paths(system, entry, key)
    if rels is None and learn and SNAPSHOT.exists():
        rels = learn_by_diff(root, json.loads(SNAPSHOT.read_text()),
                             depth=2 if kind == "eden-title-id" else 1) or None
        if rels:
            mine["learned"] = rels
            store_saves(saves)
    if not rels:
        return  # nothing saved yet, or nothing we can attribute
    if save_is_empty(root, rels):
        # Found on the first box 2026-10-07: with the disk full,
        # RetroArch made Pepsiman.srm and couldn't write to it, and the
        # empty file went up as the save, ahead of the real one after.
        print(f"{rom_path}: save is empty, not uploaded", file=sys.stderr)
        return

    digest = files_hash(root, rels, lay)
    if digest == entry.get("pushed"):
        return  # RomM already has exactly this

    s = session()
    dev = device_id(s)
    slot = SLOT
    newest = server_save(s, dev, entry["id"])
    if newest and not same_time(newest["updated_at"], entry.get("server_updated_at")):
        # Another box pushed since this one last pulled. Keep both; never
        # silently overwrite. The copy here goes up beside it for a human,
        # once per version of it: found on the first box 2026-10-06, the
        # 15-minute reconcile uploaded the same conflict copy every time.
        if mine.get("conflict_pushed") == digest:
            return
        slot = f"{SLOT}-conflict-{CFG['deviceName']}"
        print(f"conflict on {rom_path}: uploaded to slot {slot}", file=sys.stderr)

    blob, _ = pack(system, entry, root, rels, digest, lay)
    name = f"{system}-{entry.get('title_id') or entry['id']}.famidrive.tar.gz"
    r = s.post(API + EP_SAVES, timeout=120,
               params={"rom_id": entry["id"], "slot": slot, "device_id": dev,
                       "emulator": target(system).get("emulator"),
                       "overwrite": "true",
                       # RomM keeps the newest N in this slot and deletes the
                       # rest (per user, game and slot: saves uploaded by
                       # hand, in other slots, are never touched).
                       "autocleanup": "true",
                       "autocleanup_limit": CFG.get("saveHistory", 3)},
               files={"saveFile": (name, blob)})
    r.raise_for_status()
    if slot == SLOT:
        mine["pushed"] = digest
        mine["server_updated_at"] = r.json().get("updated_at")
        mine.pop("conflict_pushed", None)
        toast("--kind", "notice", "--icon", "save", "Saved to RomM", game_name(key, entry))
    else:
        mine["conflict_pushed"] = digest
        toast("--kind", "alert", "Save kept beside a newer one",
              f"{game_name(key, entry)}: another box saved since this one last loaded. RomM has both.")
    store_saves(saves)


def cmd_reconcile():
    # Backstop for pushes a crash skipped, and the one-time import of old
    # saves. Unchanged saves are skipped by content hash. No learn-by-diff:
    # the snapshot belongs to whatever session ran last, not to every ROM.
    for rom_path, entry in load_index().items():
        if CFG["systems"].get(entry["system"], {}).get("saveSync"):
            try:
                cmd_save_push(entry["system"], rom_path, learn=False)
            except requests.RequestException as e:
                print(f"push failed for {rom_path}: {e}", file=sys.stderr)
    for name in CFG.get("apps", {}):
        try:
            cmd_save_push(name, f"app:{name}", learn=False)
        except (requests.RequestException, RuntimeError) as e:
            print(f"push failed for {name}: {e}", file=sys.stderr)


SAVE_COMMANDS = {"reconcile", "save-pull", "save-push"}


def main():
    cmd, *args = sys.argv[1:] or ["help"]
    commands = {
        "pull": cmd_pull, "firmware": cmd_firmware, "reconcile": cmd_reconcile,
        "save-pull": cmd_save_pull, "save-push": cmd_save_push,
        "gamelists": cmd_gamelists, "firmware-install": cmd_firmware_install,
        "eden-profile": cmd_eden_profile, "textures": cmd_textures,
        "eden-gamedir": cmd_eden_gamedir, "eden-save": cmd_eden_save,
        "switch-dlc": cmd_switch_dlc,
    }
    if cmd not in commands:
        print(__doc__)
        sys.exit(64)
    if cmd in SAVE_COMMANDS:
        # One save sync at a time per player: the 15-minute reconcile and
        # the push after a game can start in the same second. Found on the
        # first box 2026-10-06: both uploaded the same save, and one read
        # saves.json while the other was writing it.
        STATE.mkdir(parents=True, exist_ok=True)
        with open(STATE / "lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            commands[cmd](*args)
        return
    commands[cmd](*args)


if __name__ == "__main__":
    main()
