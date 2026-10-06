"""romm-agent: the box's only link to RomM.

The library, shared by every player (run as famidrive-library):
    romm-agent pull                    mirror the library (or one collection), write gamelists
    romm-agent firmware                pull each platform's firmware

Each player's own (run as that player):
    romm-agent gamelists               copy the library's newest gamelists into ES-DE
    romm-agent firmware-install        run emulator firmware installs (keys, PS3 firmware)
    romm-agent eden-profile            give a new Eden this player's profile, before it first runs
    romm-agent save-pull SYSTEM ROM    newest save for ROM -> local (pre-launch)
    romm-agent save-push SYSTEM ROM    local save for ROM -> RomM (post-exit)
    romm-agent reconcile               push every local save RomM doesn't have yet

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
import io
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import requests

CFG = json.loads(Path(os.environ.get("ROMM_AGENT_CONFIG")
                      or f"/etc/famidrive/romm/{getpass.getuser()}.json").read_text())
BASE = CFG["url"].rstrip("/")
API = BASE + "/api"
DATA = Path(CFG["dataDir"])
MEDIA = DATA / "media"
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
EDEN_USER = 0xC8
# In save archives, Eden's profile folder is written as this, and becomes
# the box's own profile when unpacked: the same player's profile can have
# a different ID on each box.
PROFILE_SLOT = "@profile"

# Every FamiDrive save lives in this RomM slot. The sync API pairs saves on
# (rom_id, slot), so a stable name keeps one box's pushes and another's
# pulls talking about the same save.
SLOT = "famidrive"
PAGE = 500

EP_ROMS = "/roms"                                      # paginated, ?collection_id= optional
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


def download(s, path, dest, expected_sha1=None, expected_size=None, params=None):
    """Resumable download: a 40 GB ISO must not restart from zero."""
    if dest.exists():
        if expected_sha1 and sha1(dest) == expected_sha1:
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
    if expected_sha1 and sha1(part) != expected_sha1:
        part.unlink()
        raise RuntimeError(f"hash mismatch for {dest}, discarded")
    part.rename(dest)
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
    """Every ROM, or one collection's when `collection` is set."""
    params = {}
    if CFG.get("collection"):
        cols = get(s, EP_COLLECTIONS).json()
        col = next(c for c in cols if c["name"] == CFG["collection"])
        params["collection_id"] = col["id"]
    return all_roms(s, params)


def fetch_rom(s, rom, system):
    """Single-file ROMs land as-is. Multi-file ROMs (Switch updates/DLC,
    PS3 and Wii U folders, multi-disc sets) come back from RomM as a zip and
    are unpacked into a folder of the same name. VERIFY per platform that
    ES-DE launches the folder the way each emulator expects."""
    dest = DATA / "roms" / system / rom["fs_name"]
    path = EP_ROM_CONTENT.format(id=rom["id"], file_name=rom["fs_name"])
    if not rom.get("has_multiple_files"):
        download(s, path, dest, rom.get("sha1_hash"), rom.get("fs_size_bytes"))
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


def title_id(system, rom, prev, path):
    """RomM's ID (rule 2), else what this box had, else read from the ROM.
    GameCube and Wii saves are named by the full six-character ID (game
    and maker), so a shorter one from RomM is completed from the disc."""
    tid = romm_title_id(system, rom.get("title_id"))
    if system in ("gc", "wii") and (not tid or len(tid) != 6):
        return prev.get("title_id") or derive_id(system, path) or tid
    return tid or prev.get("title_id") or derive_id(system, path)


def fetch_cover(s, rom, system):
    """Box art for ES-DE, from RomM's own scrape. Best-effort."""
    rel = rom.get("path_cover_large") or rom.get("path_cover_small")
    if not rel:
        return None
    out = MEDIA / system / f"{rom['id']}{Path(rel.split('?')[0]).suffix or '.png'}"
    if out.exists():
        return out
    try:
        r = s.get(BASE + rel if rel.startswith("/") else rel, timeout=60)  # VERIFY: path or URL
        r.raise_for_status()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        return out
    except requests.RequestException:
        return None


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
        index[str(launch)] = {"id": rom["id"], "system": system, "title_id": tid}
        by_system.setdefault(system, []).append((launch, rom, fetch_cover(s, rom, system)))
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


def write_gamelist(system, entries):
    out = GAMELISTS / system / "gamelist.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    games = []
    for dest, rom, cover in entries:
        image = f"    <image>{escape(str(cover))}</image>\n" if cover else ""
        games.append(
            "  <game>\n"
            f"    <path>./{escape(dest.name)}</path>\n"
            f"    <name>{escape(rom.get('name') or dest.stem)}</name>\n"
            f"    <desc>{escape(rom.get('summary') or '')}</desc>\n"
            f"{image}"
            "  </game>\n"
        )
    out.write_text('<?xml version="1.0"?>\n<gameList>\n'
                   + "".join(games) + "</gameList>\n")


# ---------------------------------------------------------------- firmware

INSTALLERS = {
    # RPCS3 installs firmware from the PUP. Re-run when RomM's copy changes.
    "ps3": lambda d: [subprocess.run(["rpcs3", "--installfw", str(p)], check=True)
                      for p in d.glob("*.PUP")],
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
    """Copy each system's gamelist from the library into this player's
    ES-DE, when the library has written a newer one since the last copy.
    ES-DE rewrites its own copy (play counts, favorites) in between."""
    copied_file = STATE / "gamelists.json"
    copied = json.loads(copied_file.read_text()) if copied_file.exists() else {}
    for src in sorted(GAMELISTS.glob("*/gamelist.xml")):
        system, mtime = src.parent.name, src.stat().st_mtime
        if copied.get(system) == mtime:
            continue
        dest = Path(CFG["gamelistDir"]) / system / "gamelist.xml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        copied[system] = mtime
    STATE.mkdir(parents=True, exist_ok=True)
    copied_file.write_text(json.dumps(copied, indent=2))


# ---------------------------------------------------------------- game IDs
#
# roms.md "Mapping saves to games". IDs are only needed to pick which
# local files belong to a ROM when pushing. Pulling a save never needs
# one, because the archive carries its own relative paths and manifest.


def load_index():
    return json.loads(INDEX.read_text()) if INDEX.exists() else {}


def save_index(index):
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=2))


def load_saves():
    return json.loads(SAVES.read_text()) if SAVES.exists() else {}


def store_saves(saves):
    STATE.mkdir(parents=True, exist_ok=True)
    SAVES.write_text(json.dumps(saves, indent=2))


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
            return m.group(1).upper() if m else None
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
        if first == PROFILE_SLOT or re.fullmatch(r"[0-9A-Fa-f]{32}", first):
            if not lay.get("profile"):
                raise RuntimeError("Eden has no profile here yet")
            return lay["profile"] + sep + rest
    return rel


def layout(system):
    lay = dict(CFG["systems"][system]["saveLayout"])
    # Profiles are the player's own (players.<name> in the module).
    if lay["kind"] == "eden-title-id":
        lay["profile"] = eden_profile()
    elif lay["kind"] == "xenia-content":
        lay["profile"] = CFG.get("xeniaXuid")
    return lay["kind"], Path(lay["root"]).expanduser(), lay


def save_paths(system, entry, rom_path):
    """Files/dirs under the layout root that make up this ROM's save.

    Returns paths relative to the root, or None when the ID is unknown
    and nothing has been learned yet (rule 3 will fill it in).
    """
    kind, root, lay = layout(system)
    tid = entry.get("title_id")
    found = []

    if kind == "retroarch-srm":
        found = [Path(rom_path).stem + ".srm"]
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
        found = [f"{lay['profile']}/{tid.upper()}"]
    elif kind == "xenia-content" and tid:
        found = [f"{lay['profile']}/{tid}/00000001"]

    found = [f for f in found if (root / f).exists()]
    return found or entry.get("learned") or None


def snapshot(root):
    return {str(p.relative_to(root)): p.stat().st_mtime
            for p in root.rglob("*") if p.is_file()} if root.exists() else {}


def learn_by_diff(root, before):
    """Rule 3: top-level save entries that changed during the session."""
    changed = {Path(rel).parts[0] for rel, mt in snapshot(root).items()
               if before.get(rel) != mt}
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


def entry_for(key):
    """The library's entry for a ROM, with this player's save state on top."""
    entry = dict(load_index()[key])
    mine = load_saves().get(key, {})
    entry.update({k: v for k, v in mine.items() if k != "title_id"})
    entry["title_id"] = entry.get("title_id") or mine.get("title_id")
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
    SNAPSHOT.write_text(json.dumps(snapshot(root)))  # for rule 3 at push time

    s = session()
    dev = device_id(s)
    entry = entry_for(key)
    newest = server_save(s, dev, entry["id"])
    if not newest:
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
    e = saves.setdefault(key, {})
    e["title_id"] = entry.get("title_id") or manifest.get("title_id")
    e["learned"] = entry.get("learned") or [from_archive(lay, p) for p in manifest.get("paths", [])]
    e["pushed"] = manifest.get("files_sha256")
    e["server_updated_at"] = newest["updated_at"]
    store_saves(saves)

    SNAPSHOT.write_text(json.dumps(snapshot(root)))  # don't count the restore as play


def cmd_save_push(system, rom_path, learn=True):
    kind, root, lay = layout(system)
    key = library_path(rom_path)
    entry = entry_for(key)
    saves = load_saves()
    mine = saves.setdefault(key, {})

    rels = save_paths(system, entry, key)
    if rels is None and learn and SNAPSHOT.exists():
        rels = learn_by_diff(root, json.loads(SNAPSHOT.read_text())) or None
        if rels:
            mine["learned"] = rels
            store_saves(saves)
    if not rels:
        return  # nothing saved yet, or nothing we can attribute

    digest = files_hash(root, rels, lay)
    if digest == entry.get("pushed"):
        return  # RomM already has exactly this

    s = session()
    dev = device_id(s)
    slot = SLOT
    newest = server_save(s, dev, entry["id"])
    if newest and newest["updated_at"] != entry.get("server_updated_at"):
        # Another box pushed since this one last pulled. Keep both; never
        # silently overwrite. The copy here goes up beside it for a human.
        slot = f"{SLOT}-conflict-{CFG['deviceName']}"
        print(f"conflict on {rom_path}: uploaded to slot {slot}", file=sys.stderr)

    blob, _ = pack(system, entry, root, rels, digest, lay)
    name = f"{system}-{entry.get('title_id') or entry['id']}.famidrive.tar.gz"
    r = s.post(API + EP_SAVES, timeout=120,
               params={"rom_id": entry["id"], "slot": slot, "device_id": dev,
                       "emulator": CFG["systems"][system].get("emulator"),
                       "overwrite": "true"},
               files={"saveFile": (name, blob)})
    r.raise_for_status()
    if slot == SLOT:
        mine["pushed"] = digest
        mine["server_updated_at"] = r.json().get("updated_at")
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


def main():
    cmd, *args = sys.argv[1:] or ["help"]
    commands = {
        "pull": cmd_pull, "firmware": cmd_firmware, "reconcile": cmd_reconcile,
        "save-pull": cmd_save_pull, "save-push": cmd_save_push,
        "gamelists": cmd_gamelists, "firmware-install": cmd_firmware_install,
        "eden-profile": cmd_eden_profile,
    }
    if cmd not in commands:
        print(__doc__)
        sys.exit(64)
    commands[cmd](*args)


if __name__ == "__main__":
    main()
