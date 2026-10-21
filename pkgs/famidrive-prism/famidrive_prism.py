"""famidrive-prism SPEC_JSON
famidrive-prism fullscreen INSTANCE_DIR

Brings Prism Launcher instances in line with famidrive.minecraft. Runs at
activation, as the box's user. Only what the flake declares is touched:

- prismlauncher.cfg: the launcher-wide keys in "launcher".
- each instance's instance.cfg: name, Java, memory, server to join.
- mmc-pack.json: the Minecraft and Fabric versions. Rewritten only when
  they change; Prism fills in the rest (LWJGL and friends) itself.
- .minecraft/mods: the declared mods. FamiDrive remembers which jars are
  its own (.famidrive-mods) and replaces only those; mods added by hand
  stay.
- .minecraft/servers.dat: the declared servers are added or updated (by
  address). Servers added in-game stay.

Instances that aren't declared are left alone, worlds included. Each
player gets only the instances declared for them (`players`). One that
FamiDrive made (.famidrive-instance, or a name declared on the box,
"declared") but that's no longer this player's is moved to
famidrive-removed/, worlds and all, never deleted.

"fullscreen" runs at every Minecraft launch, for any instance, declared
or not: it sets fullscreen:true in the instance's options.txt. On a TV
box every instance should start fullscreen; windowed, gamescope stretches
a small window to the TV at a low resolution.
"""

import gzip
import json
import shutil
import struct
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import NotRequired, TypedDict

MARK = ".famidrive-instance"   # in an instance FamiDrive made


class Server(TypedDict):
    name: str
    address: str


class Instance(TypedDict):
    minecraft: str
    fabricLoader: str | None
    servers: list[Server]
    join: str | None
    memory: int | None
    java: str
    mods: list[str]


class Spec(TypedDict):
    """What minecraft.nix passes."""
    root: str
    launcher: dict[str, str]
    instances: dict[str, Instance]
    declared: NotRequired[list[str]]


class Component(TypedDict):
    uid: str
    version: str
    important: NotRequired[bool]


def set_keys(path: Path, keys: Mapping[str, str | int], section: str = "[General]") -> None:
    """Set key=value lines in a Prism .cfg, keeping everything else."""
    lines = path.read_text().split("\n") if path.exists() else [section]
    for key, value in keys.items():
        line = f"{key}={value}"
        for i, existing in enumerate(lines):
            if existing.split("=", 1)[0] == key:
                lines[i] = line
                break
        else:
            lines.insert(len(lines) - 1 if lines and lines[-1] == "" else len(lines), line)
    path.write_text("\n".join(lines))


# --- servers.dat: uncompressed NBT, a root compound holding "servers", a
# list of compounds. Only the tag types it uses are written; any others
# are read past and kept as they were.

# A value as read: a string (8), a list (9: its items' tag and the items),
# a compound (10: name -> (tag, value)), or any other tag's raw bytes.
type NbtValue = str | bytes | NbtList | NbtCompound
type NbtList = tuple[int, list[NbtValue]]
type NbtCompound = dict[str, tuple[int, NbtValue]]


class Nbt:
    def __init__(self, data: bytes) -> None:
        self.b, self.i = data, 0

    def take(self, n: int) -> bytes:
        out = self.b[self.i:self.i + n]
        self.i += n
        return out

    def string(self) -> str:
        n: int = struct.unpack(">H", self.take(2))[0]
        return self.take(n).decode("utf-8", "replace")

    def payload(self, tag: int) -> NbtValue:
        """(tag, value): the value as Python data, or raw bytes for tags
        servers.dat doesn't use."""
        start = self.i
        sizes = {1: 1, 2: 2, 3: 4, 4: 8, 5: 4, 6: 8}
        if tag in sizes:
            self.take(sizes[tag])
        elif tag == 7:
            self.take(struct.unpack(">i", self.take(4))[0])
        elif tag == 8:
            return self.string()
        elif tag == 9:
            item = self.take(1)[0]
            count = struct.unpack(">i", self.take(4))[0]
            return (item, [self.payload(item) for _ in range(count)])
        elif tag == 10:
            out: NbtCompound = {}
            while True:
                t = self.take(1)[0]
                if t == 0:
                    return out
                key = self.string()
                out[key] = (t, self.payload(t))
        elif tag == 11:
            self.take(4 * struct.unpack(">i", self.take(4))[0])
        elif tag == 12:
            self.take(8 * struct.unpack(">i", self.take(4))[0])
        else:
            raise ValueError(f"unknown NBT tag {tag}")
        return self.b[start:self.i]   # raw, written back as is


def nbt_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def nbt_payload(value: NbtValue) -> bytes:
    """Each kind of value is the tag it was read as (see NbtValue)."""
    if isinstance(value, str):
        return nbt_string(value)
    if isinstance(value, tuple):
        item, items = value
        return bytes([item]) + struct.pack(">i", len(items)) + b"".join(nbt_payload(v) for v in items)
    if isinstance(value, dict):
        return b"".join(bytes([t]) + nbt_string(k) + nbt_payload(v) for k, (t, v) in value.items()) + b"\0"
    return value   # raw bytes kept from reading


def update_servers(path: Path, wanted: list[Server]) -> None:
    servers: list[NbtValue] = []
    if path.exists():
        data = path.read_bytes()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        nbt = Nbt(data)
        nbt.take(1)
        nbt.string()
        root = nbt.payload(10)
        listed = root.get("servers") if isinstance(root, dict) else None
        if listed and isinstance(listed[1], tuple):
            servers = listed[1][1]
    for want in wanted:
        entry = next((s for s in servers if isinstance(s, dict) and s.get("ip", (8, ""))[1] == want["address"]),
                     None)
        if not isinstance(entry, dict):
            entry = {}
            servers.append(entry)
        entry["name"] = (8, want["name"])
        entry["ip"] = (8, want["address"])
    new_root: NbtCompound = {"servers": (9, (10, servers))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes([10]) + nbt_string("") + nbt_payload(new_root))


def set_options(path: Path, options: dict[str, str]) -> None:
    """Set key:value lines in Minecraft's options.txt. A new file holding
    only these is fine: Minecraft fills in the rest on its first start."""
    lines = path.read_text().split("\n") if path.exists() else []
    for key, value in options.items():
        line = f"{key}:{value}"
        for i, existing in enumerate(lines):
            if existing.split(":", 1)[0] == key:
                lines[i] = line
                break
        else:
            lines.insert(len(lines) - 1 if lines and lines[-1] == "" else len(lines), line)
    path.write_text("\n".join(lines))


def update_pack(path: Path, minecraft: str, fabric: str | None) -> None:
    want = {"net.minecraft": minecraft}
    if fabric:
        want["net.fabricmc.fabric-loader"] = fabric
    have: dict[str, str | None]
    try:
        pack: list[dict[str, str]] = json.loads(path.read_text())["components"]
        have = {c["uid"]: c.get("version") for c in pack}
    except (OSError, ValueError, KeyError):
        have = {}
    same = all(have.get(k) == v for k, v in want.items())
    if same and (fabric or "net.fabricmc.fabric-loader" not in have):
        return   # Prism's own resolved file; leave it
    components: list[Component] = [{"important": True, "uid": "net.minecraft", "version": minecraft}]
    if fabric:
        components.append({"uid": "net.fabricmc.fabric-loader", "version": fabric})
    path.write_text(json.dumps({"components": components, "formatVersion": 1}, indent=4))


def update_mods(mods_dir: Path, jars: list[str]) -> None:
    mods_dir.mkdir(parents=True, exist_ok=True)
    manifest = mods_dir / ".famidrive-mods"
    old = manifest.read_text().split("\n") if manifest.exists() else []
    names = {Path(j).name.split("-", 1)[1] for j in jars}   # store paths are <hash>-<name>
    for name in old:
        if name and name not in names:
            (mods_dir / name).unlink(missing_ok=True)
    for jar in jars:
        target = mods_dir / Path(jar).name.split("-", 1)[1]
        if not target.exists() or target.stat().st_size != Path(jar).stat().st_size:
            shutil.copyfile(jar, target)   # a copy: Prism renames mods to disable them
            target.chmod(0o644)
    manifest.write_text("\n".join(sorted(names)))


def main() -> None:
    if sys.argv[1] == "fullscreen":
        d = Path(sys.argv[2])
        if d.is_dir():
            (d / ".minecraft").mkdir(exist_ok=True)
            set_options(d / ".minecraft/options.txt", {"fullscreen": "true"})
        return
    spec: Spec = json.loads(sys.argv[1])
    root = Path(spec["root"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    set_keys(root / "prismlauncher.cfg", spec["launcher"])
    instances = root / "instances"
    if instances.is_dir():
        for d in instances.iterdir():
            # By name too: instances made before the mark existed have none.
            # Found on the first box 2026-10-06: the second player kept the
            # first player's instance.
            ours = (d / MARK).exists() or d.name in spec.get("declared", [])
            if ours and d.name not in spec["instances"]:
                # Moved aside rather than deleted: it may hold worlds.
                gone = root / "famidrive-removed" / f"{d.name} ({time.strftime('%Y-%m-%d %H%M%S')})"
                gone.parent.mkdir(exist_ok=True)
                d.rename(gone)
                print(f"famidrive-prism: {d.name} isn't this player's any more, moved to {gone}", file=sys.stderr)
    for name, inst in spec["instances"].items():
        d = instances / name
        (d / ".minecraft").mkdir(parents=True, exist_ok=True)
        (d / MARK).touch()
        set_keys(d / "instance.cfg", {
            "InstanceType": "OneSix",
            "name": name,
            "OverrideJavaLocation": "true",
            "JavaPath": inst["java"],
            **({"OverrideMemory": "true", "MaxMemAlloc": inst["memory"]} if inst["memory"] else {}),
            "JoinServerOnLaunch": "true" if inst["join"] else "false",
            "JoinServerOnLaunchAddress": inst["join"] or "",
        })
        update_pack(d / "mmc-pack.json", inst["minecraft"], inst["fabricLoader"])
        update_mods(d / ".minecraft/mods", inst["mods"])
        if inst["servers"]:
            update_servers(d / ".minecraft/servers.dat", inst["servers"])


if __name__ == "__main__":
    main()
