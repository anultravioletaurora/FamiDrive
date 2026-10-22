"""famidrive-steam-offline APPID

Exits 0 when Steam's own labels say the game has nothing online, so the
Guide menu can freeze it (SIGSTOP) as it does an emulator; 1 otherwise,
and then the menu leaves it running. Freezing an online game drops it off
its server, so anything unsure is 1: no label, a game Steam's cache
doesn't have, a cache this can't read.

The labels are the store's categories ("Single-player", "Online Co-op"),
which Steam keeps for every game it knows in appcache/appinfo.vdf. Offline
here means Single-player and none of the multiplayer ones. Not just "no
online ones": couch-only games look the same as Jackbox, which runs a
server the players' phones join (read on the first box 2026-10-14).

appinfo.vdf is binary: a header, then one record per app, each a binary
KeyValues tree. Versions 28 and 29 (Steam's since 2024) are read; 29 keeps
the keys in a string table at the end of the file, 28 inline.
"""

import os
import struct
import sys
from pathlib import Path

APPINFO = Path(os.environ.get("FAMIDRIVE_STEAM_APPINFO") or Path.home() / ".local/share/Steam/appcache/appinfo.vdf")

V28, V29 = 0x07564428, 0x07564429

SINGLE_PLAYER = 2
# Steam's category ids for playing with someone else: Multi-player, Co-op,
# MMO, Shared/Split Screen, Cross-Platform Multiplayer, Online PvP,
# Shared/Split Screen PvP, Online Co-op, Shared/Split Screen Co-op, LAN PvP,
# LAN Co-op, PvP. A game with any of them keeps running. Remote Play (41-44)
# isn't here: STAR WARS Jedi: Fallen Order™, single-player only, has
# Remote Play on TV.
MULTIPLAYER = {1, 9, 20, 24, 27, 36, 37, 38, 39, 47, 48, 49}

# Each record, after its app id and size: info state, last updated, PICS
# token, SHA-1 of the text form, change number, SHA-1 of the binary form.
RECORD_HEADER = 4 + 4 + 8 + 20 + 4 + 20

# A binary KeyValues tree: each value a string, a number or another tree.
type KeyValues = dict[str, KeyValue]
type KeyValue = str | int | KeyValues


def log(msg: str) -> None:
    print(f"famidrive-steam-offline: {msg}", file=sys.stderr)


class Reader:
    def __init__(self, data: bytes) -> None:
        self.d = data
        magic, = struct.unpack_from("<I", data, 0)
        if magic not in (V28, V29):
            raise ValueError(f"unknown appinfo.vdf version {magic:#x}")
        self.strings: list[str] | None = None
        self.start = 8
        if magic == V29:
            offset: int
            offset, = struct.unpack_from("<q", data, 8)
            self.start = 16
            count: int
            count, = struct.unpack_from("<I", data, offset)
            p, strings = offset + 4, []
            for _ in range(count):
                s, p = self._cstr(p)
                strings.append(s)
            self.strings = strings

    def _cstr(self, p: int) -> tuple[str, int]:
        end = self.d.index(b"\0", p)
        return self.d[p:end].decode("utf-8", "replace"), end + 1

    def _key(self, p: int) -> tuple[str, int]:
        if self.strings is None:
            return self._cstr(p)
        i: int
        i, = struct.unpack_from("<I", self.d, p)
        return self.strings[i], p + 4

    def _tree(self, p: int) -> tuple[KeyValues, int]:
        out: KeyValues = {}
        while True:
            kind = self.d[p]
            p += 1
            if kind == 8:
                return out, p
            key, p = self._key(p)
            value: KeyValue
            if kind == 0:
                value, p = self._tree(p)
            elif kind == 1:
                value, p = self._cstr(p)
            elif kind == 2:
                value, = struct.unpack_from("<i", self.d, p)
                p += 4
            elif kind == 7:
                value, = struct.unpack_from("<Q", self.d, p)
                p += 8
            else:
                raise ValueError(f"unknown KeyValues type {kind}")
            out[key] = value

    def app(self, appid: int) -> KeyValues | None:
        """One app's tree, or None when the cache doesn't have it."""
        p = self.start
        while True:
            this: int
            size: int
            this, = struct.unpack_from("<I", self.d, p)
            if this == 0:
                return None
            size, = struct.unpack_from("<I", self.d, p + 4)
            if this == appid:
                return self._tree(p + 8 + RECORD_HEADER)[0]
            p += 8 + size


def subtree(tree: KeyValues, key: str) -> KeyValues | None:
    """tree[key] when it's a tree of its own."""
    value = tree.get(key)
    return value if isinstance(value, dict) else None


def categories(info: KeyValues) -> set[int]:
    common = subtree(subtree(info, "appinfo") or info, "common") or {}
    cats = set()
    for key in subtree(common, "category") or {}:
        try:
            cats.add(int(key.rsplit("_", 1)[1]))
        except (IndexError, ValueError):
            pass
    return cats


def offline(appid: int) -> bool:
    try:
        info = Reader(APPINFO.read_bytes()).app(appid)
    except (OSError, ValueError, IndexError, struct.error) as e:
        log(f"can't read {APPINFO}: {e}")
        return False
    if info is None:
        log(f"{appid} isn't in Steam's cache")
        return False
    cats = categories(info)
    return SINGLE_PLAYER in cats and not cats & MULTIPLAYER


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print((__doc__ or "").split("\n\n")[0], file=sys.stderr)
        sys.exit(2)
    sys.exit(0 if offline(int(sys.argv[1])) else 1)


if __name__ == "__main__":
    main()
