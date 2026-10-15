"""famidrive-generate LANE SOURCE_DIR OUT_DIR
famidrive-generate heroic HEROIC_CONFIG_DIR ROMS_DIR STORE...
famidrive-generate lutris LUTRIS_DATA_DIR OUT_DIR
famidrive-generate steam-media STEAMAPPS_DIR OUT_DIR
famidrive-generate heroic-media HEROIC_CONFIG_DIR ROMS_DIR STORE...
famidrive-generate launcher SYSTEM_DIR NAME ID

Rewrite OUT_DIR so it holds exactly one placeholder per installed game in
SOURCE_DIR. Each placeholder's *content* is the launch ID that famidrive-launch
hands to the real launcher. Its filename is the display name ES-DE shows.

heroic writes the installed games of each STORE Heroic Games Launcher
runs on this box (gog, epic, amazon) into that store's system folder
under ROMS_DIR: Epic's into the Epic system, GOG's and Amazon's into
Desktop, one extension per store (.gog, .epic, .amazon). A store not
named has its entries taken out: its games go through Lutris instead,
or not at all.

lutris writes each game Lutris has installed into the Lutris system's
folder (.lutris, the file holding Lutris's ID for the game), with its
real name in the game list and Lutris's own cover art.

steam-media gives those Steam placeholders Steam's own art and details,
by app ID: the cover, logo and hero image Steam keeps on disk for its
library (fetched from Steam's CDN when it hasn't), and the description,
developer, publisher, genres and release date from the Steam store.

heroic-media does the same for Heroic's games, from Heroic's own store
cache: the store's name for the game (a file name can't have a ":"), its
description, developer and genres, and its cover and background images.

launcher puts a launcher's own entry (NAME.setting, holding ID) in its
store's system folder, at the top of the list: Lutris in Lutris, Steam
Settings in Steam. Its sort name does that; ES-DE still lists a
player's favorites first.
"""

import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


# Steam installs its own tools as apps too. Found on the first box
# 2026-10-05: Proton versions and the Linux runtimes showed up as games.
STEAM_TOOLS = re.compile(r"^(Proton|Steam Linux Runtime|Steamworks Common Redistributables)\b")


def steam(src):
    # steamapps/appmanifest_<appid>.acf: Valve KeyValues, "key" "value" pairs
    for acf in src.glob("appmanifest_*.acf"):
        text = acf.read_text(errors="replace")
        appid = re.search(r'"appid"\s+"(\d+)"', text)
        name = re.search(r'"name"\s+"([^"]+)"', text)
        if appid and name and not STEAM_TOOLS.match(name.group(1)):
            yield name.group(1), appid.group(1)


# Heroic Games Launcher (~/.config/heroic), read from Heroic 2.22's
# source on 2026-10-07. Installed games, per store:
#   GOG:    gog_store/installed.json, {"installed": [{"appName", ...}]}
#   Epic:   legendaryConfig/legendary/installed.json, {appName: {"title", ...}}
#   Amazon: nile_config/nile/installed.json, [{"id", ...}]
# and each store's library, with titles, in store_cache/<store>_library.json
# (GOG's under "games", Epic's and Amazon's under "library"), entries with
# "app_name" and "title". VERIFY against a signed-in Heroic.
HEROIC_STORES = {
    "gog": ("gog_store/installed.json", "gog_library", "games"),
    "epic": ("legendaryConfig/legendary/installed.json", "legendary_library", "library"),
    "amazon": ("nile_config/nile/installed.json", "nile_library", "library"),
}
# The ES-DE system each store's Heroic games are in. Art Book Next has art
# for Epic, so Epic is its own system; it has none for GOG or Amazon.
HEROIC_SYSTEMS = {"gog": "desktop", "epic": "epic", "amazon": "desktop"}


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def heroic(src, store):
    installed_file, cache, key = HEROIC_STORES[store]
    installed = read_json(src / installed_file)
    if isinstance(installed, dict) and "installed" in installed:
        installed = installed["installed"]
    if isinstance(installed, dict):          # Epic: keyed by app name
        apps = {name: (info or {}).get("title") for name, info in installed.items()
                if not (info or {}).get("is_dlc")}
    elif isinstance(installed, list):        # GOG and Amazon
        apps = {(g.get("appName") or g.get("id")): None for g in installed
                if isinstance(g, dict) and not g.get("is_dlc")}
    else:
        return
    library = read_json(src / "store_cache" / f"{cache}.json") or {}
    titles = {g.get("app_name"): g.get("title") for g in library.get(key) or [] if isinstance(g, dict)}
    for app, title in apps.items():
        if app:
            yield title or titles.get(app) or app, app


# Lutris (~/.local/share/lutris), read from Lutris 0.5.23's source on
# 2026-10-13. pga.db is SQLite: its games table has id, name, slug,
# runner, installed and service; a game the player hid is in the
# ".hidden" category (categories, games_categories). Lutris downloads a
# portrait cover for each game to coverart/<slug>.jpg.
LUTRIS_HIDDEN = """
    SELECT 1 FROM games_categories gc JOIN categories c ON c.id = gc.category_id
    WHERE gc.game_id = games.id AND c.name = '.hidden'"""


def lutris_games(src):
    """(id, name, slug) of each installed game, or None when Lutris's
    database can't be read right now (Lutris writing it): the entries
    then stay as they are, instead of all going."""
    db = src / "pga.db"
    if not db.exists():
        return []   # Lutris never opened: no games
    import sqlite3
    try:
        con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            # A Steam game Lutris lists starts through Steam, and it's in
            # the Steam system already.
            return con.execute(f"""
                SELECT id, name, slug FROM games
                WHERE installed = 1 AND coalesce(runner, '') != 'steam'
                  AND NOT EXISTS ({LUTRIS_HIDDEN})""").fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        print(f"famidrive-generate: can't read {db}: {e}", file=sys.stderr)
        return None


def lutris(src, out):
    games = lutris_games(src)
    if games is None:
        sys.exit(1)
    games = [(name or slug or str(i), str(i), slug) for i, name, slug in games]
    write_placeholders(out, ".lutris", [(name, i) for name, i, _ in games])
    # The real name (a file name can't have a ":"), and Lutris's cover.
    fields = {}
    for name, _, slug in games:
        stem = safe(name)
        fields[stem + ".lutris"] = {"name": name}
        cover = src / "coverart" / f"{slug}.jpg"
        if slug and cover.is_file() and cover.stat().st_size > 0 \
                and not any((ESDE / "downloaded_media/lutris/covers").glob(glob_escape(stem) + ".*")):
            put_media("covers", stem, cover.read_bytes(), ".jpg", "lutris")
    write_gamelist("lutris", merge_gamelist(ESDE / "gamelists/lutris/gamelist.xml", fields, ("name",)))


def minecraft(src):
    # instances/<id>/instance.cfg; the folder name is the ID --launch takes.
    for cfg in src.glob("*/instance.cfg"):
        name = re.search(r"^name=(.+)$", cfg.read_text(errors="replace"), re.M)
        yield (name.group(1) if name else cfg.parent.name), cfg.parent.name


LANES = {"steam": (steam, ".steam"), "minecraft": (minecraft, ".prism")}


def safe(name):
    return re.sub(r'[/\\:*?"<>|]', "_", name).strip()


# ---------------------------------------------------------------- Steam art

ESDE = Path.home() / "ES-DE"
CACHE = Path.home() / ".cache/famidrive/steam"   # store details, one JSON per app
STORE = "https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
CDN = ["https://shared.steamstatic.com/store_item_assets/steam/apps/{appid}/{name}",
       "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{name}"]
# ES-DE's media folder -> Steam's library images, best first. Seen on
# the first box 2026-10-07, Steam keeps them in
# appcache/librarycache/<appid>/, either directly or each in a subfolder
# named by a hash; older clients kept <appid>_<name> beside them. Newer
# games' portrait cover is library_capsule.jpg.
ART = {
    "covers": ["library_600x900_2x.jpg", "library_600x900.jpg", "library_capsule.jpg"],
    "marquees": ["logo.png"],
    "fanart": ["library_hero.jpg"],
}
# The fields Steam has the say on. The player's own (favorite, playcount,
# lastplayed, hidden, ...) are never touched.
FROM_STEAM = ("name", "desc", "developer", "publisher", "genre", "releasedate", "rating")
STORE_BUDGET = 150   # store lookups per run; Steam allows about 200 per 5 minutes


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "FamiDrive"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def store_details(appid, budget):
    """The store's details for appid, cached for good: a game's
    description and credits don't change. None when the store has none
    (tools, delisted games) or can't be reached."""
    cached = CACHE / f"{appid}.json"
    if cached.exists():
        data = json.loads(cached.read_text())
        return data or None
    if budget[0] <= 0:
        return None
    budget[0] -= 1
    try:
        reply = json.loads(fetch(STORE.format(appid=appid))).get(str(appid), {})
    except (OSError, ValueError):
        return None   # try again next run
    data = reply.get("data") if reply.get("success") else {}
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(data or {}))
    return data or None


def release_date(text):
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y%m%dT000000")
        except ValueError:
            pass
    return None


def description(details):
    """The store's short description, or, when Steam cut that off
    mid-sentence, the start of its "About this game" text, to the end of
    a sentence."""
    short = html_text(details.get("short_description") or "")
    if not short or short[-1] in ".!?)\"'”…":
        return short
    about = html_text(details.get("about_the_game") or "")
    if len(about) <= len(short):
        return short
    cut = about[:1200]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return about if len(about) <= 1200 else (cut[:end + 1] if end > len(short) // 2 else cut + "…")


def html_text(text):
    text = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def steam_fields(details, name):
    # The name is Steam's for this app, from its manifest: the store gives
    # some apps their parent game's (Black Ops II's multiplayer app is
    # "Call of Duty: Black Ops II" there), and two entries can't share one.
    fields = {"name": name,
              "desc": description(details),
              "developer": ", ".join(details.get("developers") or []),
              "publisher": ", ".join(details.get("publishers") or []),
              "genre": ", ".join(g["description"] for g in details.get("genres") or [] if g.get("description")),
              "releasedate": release_date((details.get("release_date") or {}).get("date") or "")}
    score = (details.get("metacritic") or {}).get("score")
    if score:
        fields["rating"] = f"{score / 100:g}"
    return {k: v.strip() for k, v in fields.items() if v and v.strip()}


def library_image(steamapps, appid, names):
    cache = steamapps.parent / "appcache/librarycache"
    for name in names:
        for p in [cache / appid / name, cache / f"{appid}_{name}", *sorted((cache / appid).glob(f"*/{name}"))]:
            if p.is_file() and p.stat().st_size > 0:
                return p.read_bytes()
    for name in names:
        for url in CDN:
            try:
                return fetch(url.format(appid=appid, name=name))
            except OSError:
                pass
    return None


def put_media(kind, stem, data, ext, system="steam"):
    """One image into ES-DE's media folder for a system (Steam's, or the
    one a Heroic or Lutris game is in). Art already there for the game (scraped
    before) is moved to downloaded_media-before-steam, not deleted."""
    folder = ESDE / "downloaded_media" / system / kind
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (stem + ext)
    for old in folder.glob(glob_escape(stem) + ".*"):
        if not old.name.endswith(".part"):
            aside = ESDE / "downloaded_media-before-steam" / system / kind
            aside.mkdir(parents=True, exist_ok=True)
            old.rename(aside / old.name)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.rename(dest)


def glob_escape(s):
    return re.sub(r"([*?\[])", r"[\1]", s)


def steam_media(steamapps, out):
    """Steam's art and details for every Steam placeholder in out."""
    games = {p.stem: p.read_text().strip() for p in out.glob("*.steam")}
    manifest_names = {appid: name for name, appid in steam(steamapps)}
    state_file = CACHE / "media.json"   # appid -> media kinds done
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    budget = [STORE_BUDGET]
    fields = {}
    for stem, appid in sorted(games.items()):
        details = store_details(appid, budget)
        if details:
            fields[stem] = steam_fields(details, manifest_names.get(appid, stem))
        done = set(state.get(appid, []))
        for kind, files in ART.items():
            if kind in done and any((ESDE / "downloaded_media/steam" / kind).glob(glob_escape(stem) + ".*")):
                continue
            data = library_image(steamapps, appid, files)
            if data:
                put_media(kind, stem, data, ".png" if data[:4] == b"\x89PNG" else ".jpg")
                done.add(kind)
        shots = (details or {}).get("screenshots") or []
        if "screenshots" not in done and shots:
            try:
                put_media("screenshots", stem, fetch(shots[0]["path_full"]), ".jpg")
                done.add("screenshots")
            except (OSError, KeyError):
                pass
        state[appid] = sorted(done)
    CACHE.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))
    gamelist = ESDE / "gamelists/steam/gamelist.xml"
    merged = merge_gamelist(gamelist, {f"{stem}.steam": f for stem, f in fields.items()}, FROM_STEAM)
    if merged is not None:
        gamelist.parent.mkdir(parents=True, exist_ok=True)
        tmp = gamelist.with_name("gamelist.xml.part")
        tmp.write_bytes(merged)
        tmp.rename(gamelist)


def write_gamelist(system, merged):
    if merged is None:
        return
    gamelist = ESDE / "gamelists" / system / "gamelist.xml"
    gamelist.parent.mkdir(parents=True, exist_ok=True)
    tmp = gamelist.with_name("gamelist.xml.part")
    tmp.write_bytes(merged)
    tmp.rename(gamelist)


def merge_gamelist(gamelist, fields, keys):
    """A player's game list with the store's fields (keys) set for each
    entry, by file name: the store has the say on what a game is, the
    player on how they've played it. None when nothing changed."""
    try:
        root = ET.parse(gamelist).getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("gameList")
    by_path = {g.findtext("path"): g for g in root.findall("game")}
    changed = False
    for filename, f in sorted(fields.items()):
        path = f"./{filename}"
        game = by_path.get(path)
        if game is None:
            game = ET.SubElement(root, "game")
            ET.SubElement(game, "path").text = path
            changed = True
        for tag in keys:
            el = game.find(tag)
            if tag not in f:
                continue
            if el is None:
                el = ET.SubElement(game, tag)
            if el.text != f[tag]:
                el.text = f[tag]
                changed = True
    if not changed:
        return None
    ET.indent(root, space="\t")
    return b'<?xml version="1.0"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"


# ---------------------------------------------------------------- Heroic's art

# ES-DE's media folder -> Heroic's image for the game, from its store
# cache: a portrait cover (art_square), the wide one (art_cover), the
# background. GOG's images server sends any of its images as JPEG when
# asked for .jpg (some are WebP).
HEROIC_ART = {"covers": "art_square", "screenshots": "art_cover",
              "fanart": "art_background", "marquees": "art_logo"}
FROM_HEROIC = ("name", "desc", "developer", "genre")


def cut_description(text, limit=1200):
    text = html_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end > limit // 2 else cut + "…"


def heroic_fields(game):
    extra = game.get("extra") or {}
    about = extra.get("about") or {}
    fields = {"name": game.get("title") or "",
              "desc": cut_description(about.get("description") or about.get("shortDescription")
                                      or game.get("description") or ""),
              "developer": game.get("developer") or "",
              "genre": ", ".join(g for g in extra.get("genres") or [] if isinstance(g, str))}
    return {k: v.strip() for k, v in fields.items() if v and v.strip()}


def image_url(url):
    if "images.gog.com/" in url:
        url = re.sub(r"\.(webp|png)(?=$|\?)", ".jpg", url)
    return url


def heroic_media(src, roms, stores):
    """Heroic's names, details and art for every entry of these stores,
    in each store's system."""
    fields = {}
    for store in stores:
        _, cache, key = HEROIC_STORES[store]
        system = HEROIC_SYSTEMS[store]
        library = read_json(src / "store_cache" / f"{cache}.json") or {}
        games = {str(g.get("app_name")): g for g in library.get(key) or [] if isinstance(g, dict)}
        for entry in sorted((roms / system).glob(f"*.{store}")):
            game = games.get(entry.read_text().strip())
            if not game:
                continue
            fields.setdefault(system, {})[entry.name] = heroic_fields(game)
            for kind, k in HEROIC_ART.items():
                url = game.get(k)
                if not url or any((ESDE / "downloaded_media" / system / kind).glob(glob_escape(entry.stem) + ".*")):
                    continue
                try:
                    data = fetch(image_url(url))
                except OSError:
                    continue   # next run
                put_media(kind, entry.stem, data, ".png" if data[:4] == b"\x89PNG" else ".jpg", system)
    for system, f in fields.items():
        write_gamelist(system, merge_gamelist(ESDE / "gamelists" / system / "gamelist.xml", f, FROM_HEROIC))


def heroic_moved(roms):
    """Each store's Heroic games into the system they're in now, from the
    ones they were in before: a system per store until 2026-10-10, then
    all three in Desktop, then Epic's back in an Epic system on
    2026-10-13. The old placeholders go; their game list entries (play
    counts, favorites) and art follow the game."""
    for store, system in HEROIC_SYSTEMS.items():
        for old in {store, "desktop"} - {system}:
            for p in (roms / old).glob(f"*.{store}"):
                p.unlink()
            move_entries(old, system, f".{store}")


def move_entries(old, new, ext):
    """Game list entries and art for one extension's games, from one
    system to another."""
    old_list = ESDE / "gamelists" / old / "gamelist.xml"
    try:
        old_root = ET.parse(old_list).getroot()
    except (OSError, ET.ParseError):
        return
    moving = [g for g in old_root.findall("game") if (g.findtext("path") or "").endswith(ext)]
    if not moving:
        return
    new_list = ESDE / "gamelists" / new / "gamelist.xml"
    try:
        root = ET.parse(new_list).getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("gameList")
    have = {g.findtext("path") for g in root.findall("game")}
    for g in moving:
        old_root.remove(g)
        if g.findtext("path") not in have:
            root.append(g)
    for r, path in ((root, new_list), (old_root, old_list)):
        ET.indent(r, space="\t")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'<?xml version="1.0"?>\n' + ET.tostring(r, encoding="utf-8") + b"\n")
    stems = {Path(g.findtext("path")).stem for g in moving}
    for kind_dir in (ESDE / "downloaded_media" / old).glob("*"):
        for f in list(kind_dir.glob("*")):
            dest = ESDE / "downloaded_media" / new / kind_dir.name / f.name
            if f.stem in stems and not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                f.rename(dest)


def launcher(folder, name, launch_id):
    entry = folder / f"{name}.setting"
    folder.mkdir(parents=True, exist_ok=True)
    if not entry.exists() or entry.read_text() != launch_id:
        entry.write_text(launch_id)
    gamelist = ESDE / "gamelists" / folder.name / "gamelist.xml"
    write_gamelist(folder.name, merge_gamelist(gamelist, {entry.name: {"sortname": "0"}}, ("sortname",)))


def main():
    if sys.argv[1] == "steam-media":
        started = time.monotonic()
        steam_media(Path(sys.argv[2]), Path(sys.argv[3]))
        print(f"Steam art and details: {time.monotonic() - started:.0f} s", file=sys.stderr)
        return
    if sys.argv[1] == "heroic-media":
        started = time.monotonic()
        heroic_media(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
        print(f"Heroic art and details: {time.monotonic() - started:.0f} s", file=sys.stderr)
        return
    if sys.argv[1] == "launcher":
        launcher(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
        return
    lane, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if lane == "heroic":
        stores = sys.argv[4:]
        heroic_moved(out)
        for store, system in HEROIC_SYSTEMS.items():
            write_placeholders(out / system, "." + store, heroic(src, store) if store in stores else [])
        return
    if lane == "lutris":
        lutris(src, out)
        return
    reader, ext = LANES[lane]
    write_placeholders(out, ext, reader(src))


def write_placeholders(out, ext, games):
    out.mkdir(parents=True, exist_ok=True)
    wanted = {safe(name) + ext: launch_id for name, launch_id in games}
    for existing in out.glob("*" + ext):
        if existing.name not in wanted:
            existing.unlink()  # uninstalled: drop the entry
    for filename, launch_id in wanted.items():
        p = out / filename
        if not p.exists() or p.read_text() != launch_id:
            p.write_text(launch_id)


if __name__ == "__main__":
    main()
