"""famidrive-nexusmods: each player's Nexus Mods collections, downloaded
with their own premium API key and installed in their Steam games.

    famidrive-nexusmods sync SPEC.json
    famidrive-nexusmods fetch SPEC.json
    famidrive-nexusmods plan SPEC.json [--compare DEPLOYMENT.json]
    famidrive-nexusmods uninstall SPEC.json APPID

sync (what the player's service runs, at boot and at each rebuild that
changes their mods): makes each game's mods what the spec says. Games
that are no longer in it get their mods removed, and what those mods had
replaced put back. For each game in it: fetch, plan, then install, once
every file is here, if what's installed isn't already this. A changed
spec (another collection, a new revision, other choices) means the old
install comes out first. A game that's running is waited for; one that
isn't installed in Steam is skipped until it is; one whose mods Vortex
manages (vortex.deployment.json in its folder) is left alone.

fetch: for each game in the spec, the pinned revision of its collection
(the curator's list of mods and files, in the collection's own archive),
then every file it lists, into the player's cache. Each file is checked
against the MD5 the collection gives, and kept: a second run downloads
only what's missing. Downloading straight from a program needs a premium
Nexus Mods account (a free one gets a 403 for each file, and has to click
"Slow download" on the website instead); FamiDrive doesn't work around
that. Progress shows as a toast.

plan: where each downloaded file would go in the game's folder, written
to the cache as JSON. Nothing is installed yet. A collection gives exact
places for some mods (its "hashes", for mods the curator installed by
hand); for the rest, the game's own rules decide, as Vortex's extension
for that game does. Only Cyberpunk 2077 has rules so far. With
--compare, the plan is checked against a Vortex deployment manifest
(vortex.deployment.json in the game's folder): which files both put in
the same place, and which only one does.

install: the plan's files into the game's folder, in order: each
collection after the one before it, and in a collection, by its install
phases and its "after" rules; where two mods have the same file, the
later one's wins. A file that was already there (the game's own, or one
the player made) is moved to a backup first. Every file put there is
recorded, in ~/.local/share/famidrive/nexusmods/installed/<app id>.json,
as it goes, so an install cut short comes out cleanly too.

SPEC (JSON, from Nix):
  {"apiKeyFile": path or null, "cache": folder,
   "games": {"<Steam app id>": {"collections": [{"slug": "...", "revision": N}, ...],
                                "choices": {"<mod name>": ["<option>", ...]}}}}
"""

import hashlib
import json
import os
import posixpath
import re
import base64
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import xxhash

API = "https://api.nexusmods.com"
GRAPHQL = API + "/v2/graphql"
BSDTAR = os.environ.get("FAMIDRIVE_BSDTAR", "@bsdtar@")
# The Unarchiver, for what libarchive can't unpack: solid RAR archives.
# Found on the first box 2026-10-10, in NakeyJakey's New Vegas.
UNAR = os.environ.get("FAMIDRIVE_UNAR", "@unar@")
TOAST = "@toast@"
STATE = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "famidrive/nexusmods"
STEAM = Path.home() / ".local/share/Steam"
APP = {"Application-Name": "FamiDrive", "Application-Version": "1", "User-Agent": "FamiDrive (famidrive-nexusmods)"}


def log(msg):
    print(f"famidrive-nexusmods: {msg}", flush=True)


def toast(*args):
    try:
        subprocess.run([TOAST, *args], timeout=5, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- Nexus Mods ------------------------------------------------------------------

class Nexus:
    def __init__(self, key):
        self.s = requests.Session()
        self.s.headers.update(APP)
        self.s.headers["apikey"] = key

    def graphql(self, query, **variables):
        r = self.s.post(GRAPHQL, json={"query": query, "variables": variables}, timeout=60)
        r.raise_for_status()
        out = r.json()
        if out.get("errors"):
            raise RuntimeError(out["errors"][0].get("message", "GraphQL error"))
        return out["data"]

    def revision(self, slug, revision):
        """The revision's game, name, the API path of its archive, and each
        file's download name by file id."""
        d = self.graphql("""query($slug: String!, $revision: Int) {
            collectionRevision(slug: $slug, revision: $revision) {
              revisionNumber downloadLink collection { name game { domainName } }
              modFiles { fileId file { uri } } } }""",
                         slug=slug, revision=revision)["collectionRevision"]
        return {"domain": d["collection"]["game"]["domainName"], "name": d["collection"]["name"],
                "link": d["downloadLink"],
                "files": {str(f["fileId"]): f["file"]["uri"] for f in d["modFiles"] if f.get("file")}}

    def link(self, path):
        """The first CDN address from a download_link answer."""
        r = self.s.get(API + path, timeout=60)
        if r.status_code == 403:
            raise PermissionError("Nexus Mods refused the download: direct downloads need a premium account")
        r.raise_for_status()
        out = r.json()
        links = out.get("download_links", out) if isinstance(out, dict) else out
        return links[0]["URI"]

    def file_link(self, domain, mod, file):
        return self.link(f"/v1/games/{domain}/mods/{mod}/files/{file}/download_link.json")

    def download(self, url, dest, md5=None):
        """To dest, through a .part file; checked against md5 when given."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        with requests.get(url, stream=True, timeout=120, headers=APP) as r:
            r.raise_for_status()
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        if md5 and md5_of(part) != md5:
            part.unlink()
            raise ValueError(f"{dest.name}: doesn't match the collection's checksum")
        part.replace(dest)


# --- The cache ---------------------------------------------------------------------

def collection_file(cache, slug, revision):
    return Path(cache) / "collections" / f"{slug}-{revision}.json"


def wabbajack_file(cache, slug, revision):
    return Path(cache) / "collections" / f"{slug}-{revision}.wabbajack"


def names_file(cache, slug, revision):
    return Path(cache) / "collections" / f"{slug}-{revision}.names.json"


def mod_file(cache, domain, source):
    """Where a mod's archive is kept: by file id and MD5, so a changed file
    under the same id is fetched again."""
    return Path(cache) / "files" / domain / f"{source['fileId']}-{source.get('md5') or 'nomd5'}"


def nexus_mods(collection):
    """The collection's mods that come from Nexus, and the others (a
    website or a file the player supplies), which can't be fetched."""
    mods = collection.get("mods", [])
    return ([m for m in mods if m.get("source", {}).get("type") == "nexus"],
            [m for m in mods if m.get("source", {}).get("type") != "nexus"])


def collections_of(game):
    """A game's collections, in install order."""
    return list(game.get("collections") or ([game["collection"]] if game.get("collection") else []))


def fetch_game(nx, cache, appid, game):
    status = 0
    for c in collections_of(game):
        status |= fetch_collection(nx, cache, appid, c["slug"], c["revision"])
    return status


def fetch_collection(nx, cache, appid, slug, revision):
    cfile = collection_file(cache, slug, revision)
    wfile = wabbajack_file(cache, slug, revision)
    if not cfile.exists() and not wfile.exists():
        info = nx.revision(slug, revision)
        archive = cfile.with_suffix(".7z")
        archive.parent.mkdir(parents=True, exist_ok=True)
        nx.download(nx.link(info["link"]), archive)
        members = set(members_of(archive) or [])
        if "modlist" in members and "collection.json" not in members:
            archive.replace(wfile)   # a Wabbajack list: kept whole, its own files are in it
        else:
            data = subprocess.run([BSDTAR, "-xOf", str(archive), "collection.json"], check=True, capture_output=True).stdout
            cfile.write_bytes(data)
            names_file(cache, slug, revision).write_text(json.dumps(info["files"]))
            archive.unlink()
    if wfile.exists():
        return fetch_wabbajack(nx, cache, appid, slug, revision)
    collection = json.loads(cfile.read_text())
    name = collection.get("info", {}).get("name", slug)
    mods, other = nexus_mods(collection)
    missing = [m for m in mods if not mod_file(cache, m["domainName"], m["source"]).exists()]
    log(f"{name} (revision {revision}): {len(mods) - len(missing)} of {len(mods)} files here")
    failed = []
    for i, m in enumerate(missing, 1):
        src = m["source"]
        toast("--kind", "progress", "--id", f"nexusmods-{appid}", "--progress", f"{i / len(missing):.3f}",
              "Downloading mods", f"{name}: {m['name']} ({i} of {len(missing)})")
        try:
            nx.download(nx.file_link(m["domainName"], src["modId"], src["fileId"]),
                        mod_file(cache, m["domainName"], src), src.get("md5"))
        except PermissionError as e:
            log(str(e))
            toast("--kind", "alert", "--id", f"nexusmods-{appid}", "Mods not downloaded", str(e))
            return 1
        except (requests.RequestException, ValueError, OSError) as e:
            log(f"{m['name']}: {e}")
            failed.append(m["name"])
    if other:
        log("not on Nexus Mods, so not downloaded: " + ", ".join(m["name"] for m in other))
    if missing:
        done = len(missing) - len(failed)
        toast("--kind", "alert" if failed else "success", "--id", f"nexusmods-{appid}", "--done",
              "Mods downloaded" if not failed else "Some mods didn't download",
              f"{name}: {done} of {len(missing)}" + (f", {len(failed)} failed" if failed else ""))
    return 1 if failed else 0


def cmd_fetch(spec):
    key = Path(spec["apiKeyFile"]).read_text().strip()
    nx = Nexus(key)
    cache = Path(os.path.expanduser(spec["cache"]))
    status = 0
    for appid, game in spec.get("games", {}).items():
        try:
            status |= fetch_game(nx, cache, appid, game)
        except (requests.RequestException, RuntimeError, PermissionError, subprocess.CalledProcessError, OSError) as e:
            log(f"{appid}: {e}")
            status = 1
    return status


# --- Where files go ----------------------------------------------------------------

def norm(path):
    """An archive member or Vortex path as a relative POSIX path."""
    return posixpath.normpath(path.replace("\\", "/")).lstrip("/")


def files_only(members):
    """The files among an archive's members: some ZIPs list their folders
    without a trailing slash, so a member that's another's parent is one."""
    paths = [norm(m) for m in members if m and not m.endswith("/")]
    parents = {posixpath.dirname(p) for p in paths}
    while "" in parents:
        parents.discard("")
    for p in list(parents):
        while p:
            p = posixpath.dirname(p)
            parents.add(p)
    return [p for p in paths if p not in parents]


def mod_name(download, fallback):
    """A mod's name the way Vortex makes it from the file's download name:
    without its extension and the version and upload time after it (up to
    five numbers, so a long version leaves the mod id on: "reset
    attributes-9240-1-0-0-4-1728625012.zip" is "reset attributes-9240")."""
    if not download:
        return fallback
    stem = download.rsplit(".", 1)[0] if "." in download else download
    return re.sub(r"(-\d+){1,5}$", "", stem) or stem


# Cyberpunk 2077: the folders a mod's files go in, under the game's own.
CP_ROOTS = {"archive", "bin", "engine", "r6", "red4ext", "mods", "tools"}
CP_ARCHIVE = (".archive", ".xl")
CP_TWEAK = (".yaml", ".yml", ".tweak")
CET = "bin/x64/plugins/cyber_engine_tweaks/mods"


def cyberpunk_layout(members, mod_name):
    """[(member, destination)] for a Cyberpunk 2077 mod's archive, the way
    Vortex's Cyberpunk extension places the common kinds:

    - already laid out from the game's folder (archive/, bin/, r6/, ...,
      maybe inside one folder of its own): as it is
    - a REDmod (a folder with info.json): mods/<folder>/
    - a Cyber Engine Tweaks mod (a folder with init.lua): CET's mods/<folder>/
    - loose .archive and .xl files: archive/pc/mod/
    - redscript (.reds): r6/scripts/<its folder, or the mod's name>/
    - TweakXL tweaks (.yaml, .tweak): r6/tweaks/
    - a RED4ext plugin (.dll): red4ext/plugins/<its name>/

    Anything else in an archive without those (readmes, pictures) is left
    out."""
    files = files_only(members)
    # Laid out from the game's folder: the deepest common folder above the
    # first root folder each file has.
    prefixes = set()
    for f in files:
        parts = f.split("/")
        for i, p in enumerate(parts[:-1]):
            if p.lower() in CP_ROOTS:
                prefixes.add(tuple(parts[:i]))
                break
    if len(prefixes) == 1:
        prefix = list(prefixes)[0]
        n = len(prefix)
        out = []
        for f in files:
            if tuple(f.split("/")[:n]) != prefix:
                continue
            dest = "/".join(f.split("/")[n:])
            # Scripts straight in r6/scripts get a folder of their own.
            if dest.lower().startswith("r6/scripts/") and dest.count("/") == 2:
                dest = f"r6/scripts/{mod_name}/{posixpath.basename(dest)}"
            out.append((f, dest))
        return out

    out, taken = [], set()

    def take(f, dest):
        if f not in taken:
            taken.add(f)
            out.append((f, dest))

    def folder_of(marker):
        return {posixpath.dirname(f) for f in files if posixpath.basename(f).lower() == marker}

    for folder in sorted(folder_of("info.json")):
        name = posixpath.basename(folder) or mod_name
        for f in files:
            if folder == "" or f.startswith(folder + "/"):
                take(f, f"mods/{name}/{f[len(folder) + 1:] if folder else f}")
    for folder in sorted(folder_of("init.lua")):
        name = posixpath.basename(folder) or mod_name
        for f in files:
            if folder == "" or f.startswith(folder + "/"):
                take(f, f"{CET}/{name}/{f[len(folder) + 1:] if folder else f}")
    reds = [f for f in files if f.lower().endswith(".reds") and f not in taken]
    if reds:
        tops = {f.split("/")[0] for f in reds}
        if len(tops) == 1 and "/" in reds[0]:
            for f in reds:
                take(f, f"r6/scripts/{f}")
        else:
            for f in reds:
                take(f, f"r6/scripts/{mod_name}/{posixpath.basename(f)}")
    for f in files:
        low = f.lower()
        if f in taken:
            continue
        if low.endswith(CP_ARCHIVE):
            take(f, f"archive/pc/mod/{posixpath.basename(f)}")
        elif low.endswith(CP_TWEAK):
            take(f, f"r6/tweaks/{posixpath.basename(f)}")
        elif low.endswith(".dll"):
            stem = posixpath.basename(f)[:-4]
            take(f, f"red4ext/plugins/{stem}/{posixpath.basename(f)}")
    return out


LAYOUTS = {"cyberpunk2077": cyberpunk_layout}


# --- FOMOD installers --------------------------------------------------------------

def fomod_config(files):
    """The member that's the archive's FOMOD installer, if it has one."""
    found = [f for f in files if f.lower().endswith("fomod/moduleconfig.xml")]
    return min(found, key=len) if found else None


def local(tag):
    return tag.rsplit("}", 1)[-1]


def kids(node, name):
    return [c for c in node if local(c.tag) == name]


def fomod_pick(group, wanted):
    """The plugins chosen in one group: the names wanted, if any of them are
    here; otherwise what the installer marks Required or Recommended, and
    for a group that must have one, its first plugin."""
    plugins = [p for ps in kids(group, "plugins") for p in kids(ps, "plugin")]
    names = {p.get("name", "").strip(): p for p in plugins}
    if wanted is not None:
        chosen = [names[n] for n in wanted if n in names]
        if chosen:
            return chosen
    kind = group.get("type", "SelectAny")
    if kind == "SelectAll":
        return plugins

    def marked(p):
        types = [t.get("name") for td in kids(p, "typeDescriptor") for t in kids(td, "type")]
        return any(t in ("Required", "Recommended") for t in types)
    chosen = [p for p in plugins if marked(p)]
    if kind in ("SelectExactlyOne", "SelectAtMostOne"):
        chosen = chosen[:1]
    if not chosen and kind in ("SelectExactlyOne", "SelectAtLeastOne") and plugins:
        chosen = plugins[:1]
    return chosen


def fomod_layout(files, config_member, xml_bytes, choices=None):
    """[(member, destination)] from a FOMOD installer.

    choices: the curator's, from the collection ([{"name": step, "groups":
    [{"name": group, "choices": [{"name": plugin}]}]}]), or a player's
    ({plugin name, ...}, matched in any group). Without, the installer's
    own defaults. Conditional installs on flags are followed; ones that
    depend on other files or the game's version are left out."""
    root = ET.fromstring(xml_bytes)
    base = posixpath.dirname(posixpath.dirname(config_member))   # the folder fomod/ is in
    by_lower = {f.lower(): f for f in files}
    out, flags = [], {}

    def add(node):
        for item in node:
            kind = local(item.tag)
            src = norm(item.get("source", ""))
            dest = norm(item.get("destination", "")) if item.get("destination") is not None else None
            full = posixpath.join(base, src) if base else src
            if kind == "file":
                f = by_lower.get(full.lower())
                if f:
                    out.append((f, dest if dest not in (None, ".", "") else posixpath.basename(src)))
            elif kind == "folder":
                pre = full.lower().rstrip("/") + "/"
                for low, f in by_lower.items():
                    if low.startswith(pre):
                        rel = f[len(pre):]
                        out.append((f, posixpath.join(dest, rel) if dest not in (None, ".", "") else rel))

    def wanted_for(step, group):
        if isinstance(choices, (set, frozenset)):
            return choices
        if not choices:
            return None
        for st in choices:
            if st.get("name", "").strip() == step:
                for g in st.get("groups", []):
                    if g.get("name", "").strip() == group:
                        return [c.get("name", "").strip() for c in g.get("choices", [])]
        return None

    for req in kids(root, "requiredInstallFiles"):
        add(req)
    for steps in kids(root, "installSteps"):
        for step in kids(steps, "installStep"):
            for groups in kids(step, "optionalFileGroups"):
                for group in kids(groups, "group"):
                    for plugin in fomod_pick(group, wanted_for(step.get("name", "").strip(), group.get("name", "").strip())):
                        for fl in kids(plugin, "files"):
                            add(fl)
                        for cf in kids(plugin, "conditionFlags"):
                            for flag in kids(cf, "flag"):
                                flags[flag.get("name")] = (flag.text or "").strip()
    for cond in kids(root, "conditionalFileInstalls"):
        for patterns in kids(cond, "patterns"):
            for pattern in kids(patterns, "pattern"):
                for deps in kids(pattern, "dependencies"):
                    tests = []
                    for d in deps:
                        if local(d.tag) == "flagDependency":
                            tests.append(flags.get(d.get("flag")) == (d.get("value") or ""))
                        else:
                            tests.append(False)
                    ok = any(tests) if deps.get("operator") == "Or" else (all(tests) and bool(tests))
                    if ok:
                        for fl in kids(pattern, "files"):
                            add(fl)
    return out


def from_hashes(members, hashes):
    """[(member, destination)] from a collection's exact list: each place
    gets the member with the same name and the most of the path in common."""
    files = files_only(members)
    out = []
    for h in hashes:
        dest = norm(h["path"])
        name = posixpath.basename(dest).lower()
        same = [f for f in files if posixpath.basename(f).lower() == name]
        if not same:
            continue

        def common(f):
            a, b = f.lower().split("/")[::-1], dest.lower().split("/")[::-1]
            n = 0
            while n < min(len(a), len(b)) and a[n] == b[n]:
                n += 1
            return n
        out.append((max(same, key=common), dest))
    return out


def place(mod, members, download=None, read=None, picks=None):
    """(status, [(member, destination)]) for one mod's archive, its
    download name (for the folder some kinds go in) if known. read(member)
    gives a member's bytes, for a FOMOD installer; picks, the player's
    choices for it (plugin names)."""
    if mod.get("hashes"):
        return "exact", from_hashes(members, mod["hashes"])
    files = files_only(members)
    config = fomod_config(files)
    if config and read is not None:
        choices = mod.get("choices", {}).get("options") if mod.get("choices") else None
        if picks:
            choices = set(picks)
        placed = fomod_layout(files, config, read(config), choices)
        return ("installer" if placed else "unknown"), placed
    layout = LAYOUTS.get(mod.get("domainName"))
    if layout is None:
        return "unknown", []
    placed = layout(members, mod_name(download, mod.get("name", "mod")))
    return ("rules" if placed else "unknown"), placed


def read_member(archive, member):
    r = subprocess.run([BSDTAR, "-xOf", str(archive), member], capture_output=True)
    if r.returncode == 0:
        return r.stdout
    return subprocess.run([UNAR, "-q", "-o", "-", str(archive), member], check=True, capture_output=True).stdout


def members_of(archive):
    r = subprocess.run([BSDTAR, "-tf", str(archive)], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.splitlines()
    r = subprocess.run([os.path.join(os.path.dirname(UNAR), "lsar"), str(archive)], capture_output=True, text=True)
    return r.stdout.splitlines()[1:] if r.returncode == 0 else None   # lsar's first line names the archive


def install_order(collection, mods):
    """A collection's mods in the order they go in: by install phase, then
    each moved after the mods its "after" rules name."""
    by_logical = {}
    for m in mods:
        by_logical[m["source"].get("logicalFilename") or m["name"]] = m["name"]
        by_logical[m["name"]] = m["name"]
    after = {}
    for r in collection.get("modRules", []):
        if r.get("type") == "after":
            a = by_logical.get(r.get("source", {}).get("logicalFileName"))
            b = by_logical.get(r.get("reference", {}).get("logicalFileName"))
            if a and b and a != b:
                after.setdefault(a, set()).add(b)
    names = [m["name"] for m in mods]
    order = sorted(names, key=lambda n: (next(m.get("phase", 0) for m in mods if m["name"] == n), names.index(n)))
    for _ in range(len(order)):   # a few passes settle chains; a cycle stops after len(order)
        moved = False
        for n, deps in after.items():
            for d in deps:
                if n in order and d in order and order.index(d) > order.index(n):
                    order.remove(n)
                    order.insert(order.index(d) + 1, n)
                    moved = True
        if not moved:
            break
    rank = {n: i for i, n in enumerate(order)}
    return sorted(mods, key=lambda m: rank[m["name"]])


def plan_game(cache, appid, game):
    plan = {"appid": appid, "collections": collections_of(game), "choices": game.get("choices", {}), "mods": []}
    for c in collections_of(game):
        if wabbajack_file(cache, c["slug"], c["revision"]).exists():
            plan["mods"] += plan_wabbajack(cache, c["slug"], c["revision"])
            plan["wabbajack"] = {"slug": c["slug"], "revision": c["revision"]}
        else:
            plan["mods"] += plan_collection(cache, c["slug"], c["revision"], game)
    return plan


def plan_collection(cache, slug, revision, game):
    collection = json.loads(collection_file(cache, slug, revision).read_text())
    mods, other = nexus_mods(collection)
    try:
        names = json.loads(names_file(cache, slug, revision).read_text())
    except (OSError, ValueError):
        names = {}
    plan = {"mods": []}
    for m in install_order(collection, mods):
        archive = mod_file(cache, m["domainName"], m["source"])
        entry = {"name": m["name"], "collection": slug, "modId": m["source"]["modId"],
                 "fileId": m["source"]["fileId"], "archive": str(archive)}
        members = members_of(archive) if archive.exists() else None
        if members is None:
            entry.update(status="missing", files=[])
        else:
            status, placed = place(m, members, names.get(str(m["source"]["fileId"])),
                                   lambda member, a=archive: read_member(a, member),
                                   game.get("choices", {}).get(m["name"]))
            entry.update(status=status, files=[{"from": a, "to": b} for a, b in placed])
        plan["mods"].append(entry)
    for m in other:
        plan["mods"].append({"name": m["name"], "collection": slug, "status": "not-on-nexus", "files": []})
    return plan["mods"]


# --- Wabbajack lists ---------------------------------------------------------------
#
# A Wabbajack list (some Nexus Mods collections are one: the collection's
# archive holds a `modlist` instead of a collection.json) builds a Mod
# Organizer 2 folder: every mod in mods/<name>/, as it lies in the game's
# Data folder, and profiles/<name>/ with the order (modlist.txt), plugins
# and INIs. FamiDrive builds the mods and the profile the same way, then
# installs them into the game itself in the profile's order, so the game
# needs neither MO2 nor its virtual file system, and starts from Steam,
# Heroic or ES-DE as it is. What it does (`$type`s): FromArchive (a file
# out of a download, or out of an archive inside one), InlineFile (a file
# shipped in the list), PatchedFromArchive (a download's file with an
# OctoDiff patch from the list). RemappedInlineFile is MO2's own settings,
# not needed. Others (CreateBSA, TransformedTexture) aren't handled yet:
# a list using them says so and isn't installed.

# Wabbajack's game names -> Nexus Mods' domains.
WJ_GAMES = {
    "FalloutNewVegas": "newvegas", "Fallout3": "fallout3", "Fallout4": "fallout4",
    "SkyrimSpecialEdition": "skyrimspecialedition", "Skyrim": "skyrim", "Oblivion": "oblivion",
    "Morrowind": "morrowind", "Enderal": "enderal", "EnderalSpecialEdition": "enderalspecialedition",
    "Starfield": "starfield", "Cyberpunk2077": "cyberpunk2077", "BaldursGate3": "baldursgate3",
}
WJ_DONE = {"FromArchive", "InlineFile", "PatchedFromArchive", "RemappedInlineFile"}


def wj_type(x):
    return x["$type"].split(",")[0]


def wj_hash(path):
    """Wabbajack's file hash: xxHash64, little-endian, in base64."""
    h = xxhash.xxh64()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(struct.pack("<Q", h.intdigest())).decode()


def wj_hash_bytes(data):
    return base64.b64encode(struct.pack("<Q", xxhash.xxh64(data).intdigest())).decode()


def wj_modlist(cache, slug, revision):
    data = subprocess.run([BSDTAR, "-xOf", str(wabbajack_file(cache, slug, revision)), "modlist"],
                          check=True, capture_output=True).stdout
    return json.loads(data)


def wj_inline(cache, slug, revision, source_id):
    return subprocess.run([BSDTAR, "-xOf", str(wabbajack_file(cache, slug, revision)), source_id],
                          check=True, capture_output=True).stdout


def wj_archive_file(cache, archive):
    """Where one of the list's downloads is kept, by its hash."""
    key = base64.b64decode(archive["Hash"]).hex()
    st = archive["State"]
    if wj_type(st) == "NexusDownloader":
        return Path(cache) / "files" / WJ_GAMES.get(st["GameName"], st["GameName"].lower()) / f"{st['FileID']}-wj{key}"
    return Path(cache) / "files" / "http" / f"{key}-{archive['Name']}"


def fetch_wabbajack(nx, cache, appid, slug, revision):
    ml = wj_modlist(cache, slug, revision)
    name = ml.get("Name", slug)
    unknown = {wj_type(d) for d in ml["Directives"]} - WJ_DONE
    if unknown:
        log(f"{name}: uses Wabbajack steps FamiDrive doesn't do yet: {', '.join(sorted(unknown))}")
        return 1
    missing = [a for a in ml["Archives"] if not wj_archive_file(cache, a).exists()]
    log(f"{name} (revision {revision}, Wabbajack): {len(ml['Archives']) - len(missing)} of {len(ml['Archives'])} files here")
    failed = []
    for i, a in enumerate(missing, 1):
        st, dest = a["State"], wj_archive_file(cache, a)
        toast("--kind", "progress", "--id", f"nexusmods-{appid}", "--progress", f"{i / len(missing):.3f}",
              "Downloading mods", f"{name}: {st.get('Name') or a['Name']} ({i} of {len(missing)})")
        try:
            if wj_type(st) == "NexusDownloader":
                url = nx.file_link(WJ_GAMES.get(st["GameName"], st["GameName"].lower()), st["ModID"], st["FileID"])
            elif wj_type(st) == "HttpDownloader":
                url = st["Url"]
            else:
                raise ValueError(f"can't download from {wj_type(st)}")
            nx.download(url, dest)
            if wj_hash(dest) != a["Hash"]:
                dest.unlink()
                raise ValueError("doesn't match the list's checksum")
        except PermissionError as e:
            log(str(e))
            toast("--kind", "alert", "--id", f"nexusmods-{appid}", "Mods not downloaded", str(e))
            return 1
        except (requests.RequestException, ValueError, OSError) as e:
            log(f"{a['Name']}: {e}")
            failed.append(a["Name"])
    if missing:
        toast("--kind", "alert" if failed else "success", "--id", f"nexusmods-{appid}", "--done",
              "Mods downloaded" if not failed else "Some mods didn't download",
              f"{name}: {len(missing) - len(failed)} of {len(missing)}" + (f", {len(failed)} failed" if failed else ""))
    return 1 if failed else 0


def octodiff(base, delta):
    """A file from an OctoDiff delta (Wabbajack's patches) and the file it
    was made from: a header, then copy-from-base and new-data commands."""
    if delta[:9] != b"OCTODELTA":
        raise ValueError("not an OctoDiff delta")
    i = 10                     # magic, version
    n, shift = 0, 0            # the hash algorithm's name, .NET 7-bit length first
    while True:
        b = delta[i]
        i += 1
        n |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            break
    i += n
    i += 4 + struct.unpack_from("<i", delta, i)[0]   # the base's hash
    if delta[i:i + 3] != b">>>":
        raise ValueError("OctoDiff delta: no end of header")
    i += 3
    out = bytearray()
    while i < len(delta):
        cmd = delta[i]
        i += 1
        if cmd == 0x60:
            start, length = struct.unpack_from("<qq", delta, i)
            i += 16
            out += base[start:start + length]
        elif cmd == 0x80:
            (length,) = struct.unpack_from("<q", delta, i)
            i += 8
            out += delta[i:i + length]
            i += length
        else:
            raise ValueError(f"OctoDiff delta: unknown command {cmd:#x}")
    return bytes(out)


def wj_tree(cache, slug, revision):
    return STATE / "wabbajack" / f"{slug}-{revision}"


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def build_wabbajack(cache, slug, revision, progress=None):
    """The list's mods/ and profiles/ folders, built once into the player's
    data (~/.local/share/famidrive/nexusmods/wabbajack/<slug>-<revision>)."""
    tree = wj_tree(cache, slug, revision)
    if (tree / ".complete").exists():
        return tree
    ml = wj_modlist(cache, slug, revision)
    by_hash = {a["Hash"]: a for a in ml["Archives"]}
    wanted = [d for d in ml["Directives"] if norm(d["To"]).split("/")[0].lower() in ("mods", "profiles")]
    for d in wanted:
        if wj_type(d) == "InlineFile":
            dst = tree / norm(d["To"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(wj_inline(cache, slug, revision, d["SourceDataID"]))
    groups = {}
    for d in wanted:
        if wj_type(d) in ("FromArchive", "PatchedFromArchive"):
            groups.setdefault(d["ArchiveHashPath"][0], []).append(d)
    work = STATE / "tmp"
    work.mkdir(parents=True, exist_ok=True)

    def done(d):   # built before, by a run that stopped partway
        f = tree / norm(d["To"])
        return f.exists() and f.stat().st_size == d.get("Size", -1)
    for n, (h, ds) in enumerate(groups.items(), 1):
        archive = wj_archive_file(cache, by_hash[h])
        if progress:
            progress(n, len(groups), by_hash[h].get("Name", ""))
        ds = [d for d in ds if not done(d)]
        if not ds:
            continue
        with tempfile.TemporaryDirectory(dir=work) as tmp:
            files = {k.lower(): v for k, v in extracted(archive, tmp).items()}
            nested = {}
            for d in ds:
                hp = d["ArchiveHashPath"]
                if len(hp) == 3:   # a file in an archive inside the download
                    inner = norm(hp[1]).lower()
                    if inner not in nested:
                        into = Path(tmp) / f".nested-{len(nested)}"
                        into.mkdir()
                        nested[inner] = {k.lower(): v for k, v in extracted(files[inner], into).items()}
                    src = nested[inner].get(norm(hp[2]).lower())
                else:
                    src = files.get(norm(hp[1]).lower())
                if src is None:
                    raise RuntimeError(f"{by_hash[h].get('Name')}: {'/'.join(hp[1:])} isn't in it")
                dst = tree / norm(d["To"])
                if wj_type(d) == "PatchedFromArchive":
                    data = octodiff(src.read_bytes(), wj_inline(cache, slug, revision, d["PatchID"]))
                    if wj_hash_bytes(data) != d["Hash"]:
                        raise RuntimeError(f"{d['To']}: the patched file doesn't match the list")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(data)
                else:
                    link_or_copy(src, dst)
    (tree / ".complete").write_text(json.dumps({"slug": slug, "revision": revision}))
    return tree


def mo2_profile(tree):
    profiles = sorted(p for p in (tree / "profiles").iterdir() if p.is_dir())
    return next((p for p in profiles if p.name == "Default"), profiles[0])


def mo2_order(profile):
    """The profile's enabled mods, lowest priority first (MO2's modlist.txt
    lists the highest first; separators and the game's own DLC, `*`, aren't
    mods)."""
    lines = (profile / "modlist.txt").read_text(errors="replace").splitlines()
    return [ln[1:] for ln in reversed(lines) if ln.startswith("+") and not ln.endswith("_separator")]


def plan_wabbajack(cache, slug, revision):
    """Each enabled mod's files into the game's Data folder, in the
    profile's order (a later mod's file wins), from the built folders."""
    tree = wj_tree(cache, slug, revision)
    if not (tree / ".complete").exists():
        return [{"name": f"{slug} (Wabbajack, not built yet)", "status": "missing", "files": []}]
    mods = []
    for name in mo2_order(mo2_profile(tree)):
        folder = tree / "mods" / name
        files = [p for p in folder.rglob("*") if p.is_file()] if folder.is_dir() else []
        mods.append({"name": name, "collection": slug, "dir": str(folder), "status": "rules",
                     "files": [{"from": str(p.relative_to(folder)), "to": "Data/" + str(p.relative_to(folder))}
                               for p in files if str(p.relative_to(folder)).lower() != "meta.ini"]})
    return mods


# --- The game's folder -----------------------------------------------------------

def steam_libraries(steam=None):
    """Every Steam library folder (libraryfolders.vdf), the default first."""
    steam = Path(steam or STEAM)
    libs = [steam]
    try:
        text = (steam / "steamapps/libraryfolders.vdf").read_text(errors="replace")
    except OSError:
        return libs
    for path in re.findall(r'"path"\s+"([^"]+)"', text):
        p = Path(path.replace("\\\\", "\\"))
        if p not in libs:
            libs.append(p)
    return libs


HEROIC = Path.home() / ".config/heroic"


def heroic_game(key, heroic=None):
    """A GOG game Heroic installed ("gog:<GOG id>"): its entry in Heroic's
    gog_store/installed.json, or None."""
    heroic = Path(heroic or HEROIC)
    try:
        installed = json.loads((heroic / "gog_store/installed.json").read_text()).get("installed", [])
    except (OSError, ValueError):
        return None
    return next((g for g in installed if str(g.get("appName")) == key.split(":", 1)[1]), None)


def game_dir(appid, steam=None, heroic=None):
    """The installed game's folder, or None. A Steam game (by app id): its
    appmanifest says where, and StateFlags 4 is fully installed (not
    mid-download or update). A GOG game ("gog:<id>"): Heroic's record."""
    if str(appid).startswith("gog:"):
        g = heroic_game(appid, heroic)
        return Path(g["install_path"]) if g and g.get("install_path") else None
    for lib in steam_libraries(steam):
        acf = lib / "steamapps" / f"appmanifest_{appid}.acf"
        try:
            text = acf.read_text(errors="replace")
        except OSError:
            continue
        flags = re.search(r'"StateFlags"\s+"(\d+)"', text)
        folder = re.search(r'"installdir"\s+"([^"]+)"', text)
        if folder and flags and int(flags.group(1)) == 4:
            return lib / "steamapps/common" / folder.group(1)
    return None


def prefix_of(appid, root, steam=None, heroic=None):
    """The game's Windows prefix (drive_c's parent), or None: Steam's
    compatdata beside its library, or the one Heroic's settings name for
    a GOG game (a Proton one keeps it in pfx/)."""
    if str(appid).startswith("gog:"):
        heroic = Path(heroic or HEROIC)
        name = appid.split(":", 1)[1]
        try:
            conf = json.loads((heroic / "GamesConfig" / f"{name}.json").read_text()).get(name, {})
        except (OSError, ValueError):
            return None
        p = Path(conf["winePrefix"]) if conf.get("winePrefix") else None
    else:
        p = Path(root).parents[1] / "compatdata" / str(appid)   # <library>/steamapps/compatdata/<id>
    if p is None:
        return None
    return p / "pfx" if (p / "pfx").is_dir() else p


def game_running(appid, root=None):
    """Whether the game is running: for Steam, its launcher (`reaper
    SteamLaunch AppId=N`); for a GOG game, a program from its folder."""
    if str(appid).startswith("gog:"):
        if root is None:
            return False
        needle = Path(root).name.encode()
        for cmd in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                text = cmd.read_bytes()
            except OSError:
                continue
            if needle in text and b".exe" in text.lower():
                return True
        return False
    needle = f"AppId={appid}".encode()
    for cmd in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            parts = cmd.read_bytes().split(b"\0")
        except OSError:
            continue
        if b"SteamLaunch" in parts and needle in parts:
            return True
    return False


def resolve(root, rel, listings=None):
    """rel under root, following the case of folders already there: Linux
    is case-sensitive, a game under Proton isn't, so "R6/Scripts" from one
    mod and "r6/scripts" from another must be the same folder."""
    cur = Path(root)
    for part in rel.split("/"):
        nxt = cur / part
        if cur.is_dir():
            names = listings.get(cur) if listings is not None else None
            if names is None or part not in names:   # not seen yet, or made since: look again
                names = {c.name for c in cur.iterdir()}
                if listings is not None:
                    listings[cur] = names
            if part not in names:
                low = part.lower()
                nxt = cur / next((n for n in names if n.lower() == low), part)
        cur = nxt
    return cur


# --- Installing ----------------------------------------------------------------------

def installed_file(appid):
    return STATE / "installed" / f"{str(appid).replace(':', '-')}.json"


def read_installed(appid, cache=None):
    """What's installed for a game, or None. Also the first box's one-off
    install (2026-10-10), recorded in the cache before this existed."""
    for f in [installed_file(appid)] + ([Path(cache) / "installed" / f"{appid}.json"] if cache else []):
        try:
            m = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if "want" not in m and "collection" in m:   # the one-off's record
            m["want"] = {"collections": [{"slug": m["collection"], "revision": m["revision"]}], "choices": {}}
            m["complete"] = True
        m["_path"] = str(f)
        return m
    return None


def save_installed(appid, record):
    out = installed_file(appid)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    tmp.write_text(json.dumps({k: v for k, v in record.items() if k != "_path"}, indent=1))
    tmp.replace(out)


def want_of(game):
    """What a game's mods should be, to compare with what's installed."""
    return {"collections": [{"slug": c["slug"], "revision": c["revision"]} for c in collections_of(game)],
            "choices": game.get("choices", {})}


def winners(plan):
    """dest (lower case) -> index of the last mod in the plan writing it."""
    wins = {}
    for i, m in enumerate(plan["mods"]):
        for f in m["files"]:
            wins[f["to"].lower()] = i
    return wins


def extracted(archive, into):
    """Unpack an archive; {normalised member path: file} (a ZIP made on
    Windows can unpack with backslashes in its names)."""
    r = subprocess.run([BSDTAR, "-xf", str(archive), "-C", str(into)], capture_output=True)
    if r.returncode != 0:
        shutil.rmtree(into, ignore_errors=True)
        Path(into).mkdir(parents=True)
        subprocess.run([UNAR, "-q", "-D", "-o", str(into), "-f", str(archive)], check=True, capture_output=True)
    out = {}
    for p in Path(into).rglob("*"):
        if p.is_file():
            out[norm(str(p.relative_to(into)))] = p
    return out


def install(plan, root, appid, want, progress=None):
    """The plan's files into root, recorded as it goes."""
    backup = STATE / "backup" / str(appid)
    record = {"appid": appid, "root": str(root), "want": want, "backup": str(backup),
              "files": [], "replaced": [], "outside": [], "complete": False}
    save_installed(appid, record)
    wins = winners(plan)
    work = STATE / "tmp"
    work.mkdir(parents=True, exist_ok=True)
    mods = [m for m in plan["mods"] if m["files"]]
    listings = {}   # folder -> its names, so 60000 files don't each list their folders
    ours = set()
    for n, m in enumerate(mods, 1):
        i = plan["mods"].index(m)
        if progress:
            progress(n, len(mods), m["name"])
        with tempfile.TemporaryDirectory(dir=work) as tmp:
            # A built folder (a Wabbajack list's mod) is linked from, and
            # stays; an archive is unpacked and its files moved.
            from_dir = Path(m["dir"]) if m.get("dir") else None
            files = {} if from_dir else extracted(m["archive"], tmp)
            for f in m["files"]:
                if wins[f["to"].lower()] != i:
                    continue   # a later mod has this file
                src = from_dir / f["from"] if from_dir else files.get(norm(f["from"]))
                if src is None or not src.exists():
                    log(f"{m['name']}: {f['from']} isn't in its archive")
                    continue
                dst = resolve(root, f["to"], listings)
                rel = str(dst.relative_to(root))
                if dst.exists() and rel not in ours:
                    bk = backup / rel
                    bk.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(dst, bk)
                    record["replaced"].append(rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                if from_dir:
                    link_or_copy(src, dst)
                else:
                    shutil.move(str(src), str(dst))
                if rel not in ours:
                    ours.add(rel)
                    record["files"].append(rel)
        save_installed(appid, record)
    record["complete"] = True
    save_installed(appid, record)
    return record


def uninstall(record):
    """Take an install out: its files removed, what they replaced put
    back, and folders they left empty removed."""
    root = Path(record["root"])
    backup = Path(record.get("backup") or "")
    folders = set()
    for rel in record.get("files", []):
        p = root / rel
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        folders.add(p.parent)
    for rel in record.get("replaced", []):
        bk = backup / "replaced" / rel if (backup / "replaced" / rel).exists() else backup / rel
        if bk.exists():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            os.replace(bk, root / rel)
    for o in record.get("outside", []):   # files outside the game's folder (its prefix's INIs)
        Path(o["path"]).unlink(missing_ok=True)
        if o.get("backup") and Path(o["backup"]).exists():
            os.replace(o["backup"], o["path"])
    for folder in sorted(folders, key=lambda p: -len(p.parts)):
        while folder != root and root in folder.parents:
            try:
                folder.rmdir()
            except OSError:
                break
            folder = folder.parent
    Path(record["_path"]).unlink(missing_ok=True)


# --- After installing: what a game needs beyond its mods --------------------------

def place_root_file(record, root, rel, data=None, src=None):
    """One file into the game's folder, recorded like a mod's (what was
    there backed up first)."""
    dst = resolve(root, rel)
    rel = str(dst.relative_to(root))
    if dst.exists() and rel not in record["files"]:
        bk = Path(record["backup"]) / rel
        bk.parent.mkdir(parents=True, exist_ok=True)
        os.replace(dst, bk)
        record["replaced"].append(rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src is not None:
        shutil.copyfile(src, dst)
    else:
        dst.write_bytes(data)
    if rel not in record["files"]:
        record["files"].append(rel)
    return dst


def place_outside(record, path, data):
    """A file outside the game's folder (in its prefix), recorded with a
    backup of what was there."""
    path = Path(path)
    entry = {"path": str(path), "backup": None}
    if path.exists() and not any(o["path"] == str(path) for o in record["outside"]):
        bk = Path(record["backup"]) / "outside" / str(path).lstrip("/")
        bk.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, bk)
        entry["backup"] = str(bk)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if not any(o["path"] == str(path) for o in record["outside"]):
        record["outside"].append(entry)


def windows_user(prefix):
    """The prefix's user folder: Proton's steamuser, or Wine's (the Linux
    user's name)."""
    users = Path(prefix) / "drive_c/users"
    if (users / "steamuser").is_dir():
        return users / "steamuser"
    return next((u for u in sorted(users.iterdir()) if u.is_dir() and u.name != "Public"), users / "steamuser")


def ini_merge(base, tweaks):
    """INI text with another's keys set over it, section by section, keeping
    the rest as it was (MO2's INI tweaks)."""
    lines = base.splitlines()
    section = None
    pending = {}
    names = {}   # section, lower case -> as the tweaks spell it
    for ln in tweaks.splitlines():
        t = ln.strip()
        if t.startswith("[") and t.endswith("]"):
            section = t[1:-1].lower()
            names[section] = t[1:-1]
        elif "=" in t and section is not None and not t.startswith(";"):
            k, v = t.split("=", 1)
            pending.setdefault(section, {})[k.strip().lower()] = (k.strip(), v.strip())
    out, section = [], None
    for ln in lines:
        t = ln.strip()
        if t.startswith("[") and t.endswith("]"):
            for k, v in pending.pop(section, {}).values() if section is not None else []:
                out.append(f"{k}={v}")
            section = t[1:-1].lower()
        elif "=" in t and section in pending and t.split("=", 1)[0].strip().lower() in pending[section]:
            k, v = pending[section].pop(t.split("=", 1)[0].strip().lower())
            ln = f"{k}={v}"
        out.append(ln)
    for k, v in pending.pop(section, {}).values() if section is not None else []:
        out.append(f"{k}={v}")
    for sec, kv in pending.items():
        out.append(f"[{names.get(sec, sec)}]")
        out += [f"{k}={v}" for k, v in kv.values()]
    return "\n".join(out) + "\n"


# An empty BSA (version 104: Fallout 3 and New Vegas), for the profile's
# "Fallout - Invalidation.bsa", which MO2 makes so loose files win over
# the game's own archives.
EMPTY_BSA = b"BSA\0" + struct.pack("<8I", 104, 36, 3, 0, 0, 0, 0, 0)

# The 4GB Patcher's Python version (Nexus Mods, newvegas mod 62552, file
# 1000080719, "4GB Python Patcher" 1.5): makes FalloutNV.exe use 4 GB and
# load xNVSE (nvse_steam_loader.dll) itself. Only this exact script runs.
NV_PATCHER = {"mod": 62552, "file": 1000080719, "name": "PyNVPatch.py",
              "sha256": "dbb841ba2ab5dd9979282b8029b87e703475b5264441b4ee18243c2e91b39849"}


def newvegas(record, root, prefix, profile, extras, nx, cache):
    """New Vegas beyond its mods: xNVSE, the 4GB patch, the launcher out
    of the way, the profile's INIs and plugins in the prefix, and the
    plugins' order (New Vegas orders them by file date)."""
    # xNVSE, from its release (pinned in Nix), into the game's folder.
    with tempfile.TemporaryDirectory(dir=STATE / "tmp") as tmp:
        for rel, src in extracted(extras["xnvse"], tmp).items():
            if not rel.lower().endswith(".pdb"):
                place_root_file(record, root, rel, src=src)
    # The 4GB patch, by its author's script, on the original exe.
    exe = resolve(root, "FalloutNV.exe")
    script = Path(cache) / "files/newvegas" / f"{NV_PATCHER['file']}-{NV_PATCHER['name']}"
    if not script.exists():
        archive = script.with_suffix(".7z")
        nx.download(nx.file_link("newvegas", NV_PATCHER["mod"], NV_PATCHER["file"]), archive)
        script.write_bytes(read_member(archive, NV_PATCHER["name"]))
        archive.unlink()
    if hashlib.sha256(script.read_bytes()).hexdigest() != NV_PATCHER["sha256"]:
        raise RuntimeError("the 4GB patcher isn't the one FamiDrive knows; not run")
    original = exe.read_bytes()
    place_root_file(record, root, "FalloutNV.exe", data=original)   # backs up the original, recorded
    r = subprocess.run([sys.executable, str(script)], cwd=root, input="\n", capture_output=True, text=True)
    log(f"newvegas: 4GB patcher: {(r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else r.returncode}")
    if exe.read_bytes() == original:
        raise RuntimeError("the 4GB patcher didn't patch FalloutNV.exe (an unknown version?)")
    if (root / "FalloutNV_backup.exe").exists() and "FalloutNV_backup.exe" not in record["files"]:
        record["files"].append("FalloutNV_backup.exe")
    # Steam (and GOG) start FalloutNVLauncher.exe, a settings window: the
    # patched game takes its place, so a launch goes straight in.
    if resolve(root, "FalloutNVLauncher.exe").exists():
        place_root_file(record, root, "FalloutNVLauncher.exe", src=exe)
    # Archive invalidation, as MO2 does it.
    place_root_file(record, root, "Data/Fallout - Invalidation.bsa", data=EMPTY_BSA)
    # The profile's INIs and plugins, where the game reads them.
    if prefix is None:
        raise RuntimeError("no prefix for the game yet: start it once, then rebuild")
    user = windows_user(prefix)
    docs = user / "Documents/My Games/FalloutNV"
    tweaks = (profile / "initweaks.ini").read_text(errors="replace") if (profile / "initweaks.ini").exists() else ""
    for src, name in (("fallout.ini", "Fallout.ini"), ("falloutprefs.ini", "FalloutPrefs.ini"), ("falloutcustom.ini", "FalloutCustom.ini")):
        if (profile / src).exists():
            text = (profile / src).read_text(errors="replace")
            if name == "Fallout.ini" and tweaks:
                text = ini_merge(text, tweaks)
            place_outside(record, docs / name, text.encode())
    plugins = (profile / "plugins.txt").read_bytes()
    place_outside(record, user / "AppData/Local/FalloutNV/plugins.txt", plugins)
    # Plugin order by date, from loadorder.txt.
    order = [ln.strip() for ln in (profile / "loadorder.txt").read_text(errors="replace").splitlines()
             if ln.strip() and not ln.startswith("#")]
    start = 946684800   # 2000-01-01, a minute apart
    for i, name in enumerate(order):
        f = resolve(root, "Data/" + name)
        if f.exists():
            os.utime(f, (start + 60 * i, start + 60 * i))


GAME_SETUP = {"newvegas": newvegas}


def sync_game(nx, cache, appid, game, wait=60, extras=None):
    want = want_of(game)
    have = read_installed(appid, cache)
    if have and have.get("want") == want and have.get("complete"):
        return 0
    status = fetch_game(nx, cache, appid, game)
    if status:
        log(f"{appid}: not every file is here yet; installing once they are")
        return 1
    for c in collections_of(game):   # Wabbajack lists: their mods built from the downloads first
        if wabbajack_file(cache, c["slug"], c["revision"]).exists():
            def building(n, total, name):
                toast("--kind", "progress", "--id", f"nexusmods-{appid}", "--progress", f"{n / total:.3f}",
                      "Building mods", f"{name} ({n} of {total})")
            build_wabbajack(cache, c["slug"], c["revision"], building)
    plan = plan_game(cache, appid, game)
    if status or any(m["status"] == "missing" for m in plan["mods"]):
        log(f"{appid}: not every file is here yet; installing once they are")
        return 1
    root = game_dir(appid)
    if root is None:
        log(f"{appid}: the game isn't installed in Steam (or is updating); its mods wait for it")
        return 0
    if (root / "vortex.deployment.json").exists():
        log(f"{appid}: Vortex manages this game's mods (vortex.deployment.json); left alone")
        toast("--kind", "alert", "--id", f"nexusmods-{appid}", "Mods not installed",
              "Vortex manages this game's mods. Remove its install first.")
        return 1
    while game_running(appid, root):
        log(f"{appid}: the game is running; installing its mods once it's closed")
        time.sleep(wait)
    if have:
        log(f"{appid}: taking out the mods installed before")
        uninstall(have)
    names = ", ".join(c["slug"] for c in want["collections"])

    def progress(n, total, name):
        toast("--kind", "progress", "--id", f"nexusmods-{appid}", "--progress", f"{n / total:.3f}",
              "Installing mods", f"{name} ({n} of {total})")
    record = install(plan, root, appid, want, progress)
    if plan.get("wabbajack"):
        wj = plan["wabbajack"]
        domain = WJ_GAMES.get(wj_modlist(cache, wj["slug"], wj["revision"]).get("GameType"), "")
        setup = GAME_SETUP.get(domain)
        if setup:
            record["complete"] = False
            setup(record, root, prefix_of(appid, root), mo2_profile(wj_tree(cache, wj["slug"], wj["revision"])),
                  extras or {}, nx, cache)
            record["complete"] = True
        save_installed(appid, record)
    log(f"{appid}: installed {len(record['files'])} files from {names}; {len(record['replaced'])} replaced (backed up)")
    toast("--kind", "success", "--id", f"nexusmods-{appid}", "--done", "Mods installed",
          f"{len(record['files'])} files")
    return 0


def cmd_sync(spec):
    cache = Path(os.path.expanduser(spec["cache"]))
    games = spec.get("games", {})
    status = 0
    # Games no longer listed: their mods come out.
    for f in sorted(set((STATE / "installed").glob("*.json")) | set((cache / "installed").glob("*.json"))):
        appid = f.stem
        if appid in {installed_file(k).stem for k in games}:   # "gog:1" is kept as gog-1.json
            continue
        have = read_installed(appid, cache)
        if not have:
            continue
        while game_running(appid, have.get("root")):
            time.sleep(60)
        uninstall(have)
        log(f"{appid}: mods removed")
        toast("--kind", "notice", "--id", f"nexusmods-{appid}", "Mods removed", f"{len(have.get('files', []))} files")
    if not games:
        return status
    nx = Nexus(Path(spec["apiKeyFile"]).read_text().strip())
    for appid, game in games.items():
        try:
            status |= sync_game(nx, cache, appid, game, extras=spec.get("extras", {}))
        except (requests.RequestException, RuntimeError, PermissionError, subprocess.CalledProcessError, OSError) as e:
            log(f"{appid}: {e}")
            status = 1
    return status


def cmd_uninstall(spec, appid):
    have = read_installed(appid, Path(os.path.expanduser(spec["cache"])))
    if not have:
        log(f"{appid}: no mods installed by FamiDrive")
        return 0
    uninstall(have)
    log(f"{appid}: mods removed")
    return 0


def compare(plan, deployment):
    """Files the plan and a Vortex deployment both put in the same place,
    and those only one of them has (case-insensitive, as on Windows)."""
    ours = {f["to"].lower() for m in plan["mods"] for f in m["files"]}
    theirs = {norm(f["relPath"]).lower() for f in deployment.get("files", [])}
    return {"both": len(ours & theirs), "onlyPlan": sorted(ours - theirs), "onlyVortex": sorted(theirs - ours)}


def summary(plan):
    counts = {}
    for m in plan["mods"]:
        counts[m["status"]] = counts.get(m["status"], 0) + 1
    files = sum(len(m["files"]) for m in plan["mods"])
    return f"{len(plan['mods'])} mods, {files} files placed; " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))


def cmd_plan(spec, compare_with=None):
    cache = Path(os.path.expanduser(spec["cache"]))
    for appid, game in spec.get("games", {}).items():
        plan = plan_game(cache, appid, game)
        out = cache / "plans" / f"{appid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=1))
        log(f"{appid}: {summary(plan)} -> {out}")
        if compare_with:
            c = compare(plan, json.loads(Path(compare_with).read_text()))
            log(f"{appid}: same place as Vortex: {c['both']}; only in the plan: {len(c['onlyPlan'])}; "
                f"only Vortex: {len(c['onlyVortex'])}")
            for label, paths in (("only in the plan", c["onlyPlan"]), ("only Vortex", c["onlyVortex"])):
                for p in paths[:15]:
                    log(f"  {label}: {p}")
    return 0


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("sync", "fetch", "plan", "uninstall"):
        raise SystemExit(__doc__.split("\n\n")[1])
    spec = json.loads(Path(args[1]).read_text())
    if args[0] == "sync":
        sys.exit(cmd_sync(spec))
    if args[0] == "fetch":
        sys.exit(cmd_fetch(spec))
    if args[0] == "uninstall":
        sys.exit(cmd_uninstall(spec, args[2]))
    compare_with = args[args.index("--compare") + 1] if "--compare" in args else None
    sys.exit(cmd_plan(spec, compare_with))


if __name__ == "__main__":
    main()
