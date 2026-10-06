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

Instances that aren't declared are left alone, worlds included.

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
from pathlib import Path


def set_keys(path, keys, section="[General]"):
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

class Nbt:
    def __init__(self, data):
        self.b, self.i = data, 0

    def take(self, n):
        out = self.b[self.i:self.i + n]
        self.i += n
        return out

    def string(self):
        n = struct.unpack(">H", self.take(2))[0]
        return self.take(n).decode("utf-8", "replace")

    def payload(self, tag):
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
            out = {}
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


def nbt_string(s):
    raw = s.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def nbt_payload(tag, value):
    if tag == 8:
        return nbt_string(value)
    if tag == 9:
        item, items = value
        return bytes([item]) + struct.pack(">i", len(items)) + b"".join(nbt_payload(item, v) for v in items)
    if tag == 10:
        return b"".join(bytes([t]) + nbt_string(k) + nbt_payload(t, v) for k, (t, v) in value.items()) + b"\0"
    return value   # raw bytes kept from reading


def update_servers(path, wanted):
    servers = []
    if path.exists():
        data = path.read_bytes()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        nbt = Nbt(data)
        nbt.take(1)
        nbt.string()
        root = nbt.payload(10)
        servers = root.get("servers", (9, (10, [])))[1][1]
    for want in wanted:
        entry = next((s for s in servers if s.get("ip", (8, ""))[1] == want["address"]), None)
        if entry is None:
            entry = {}
            servers.append(entry)
        entry["name"] = (8, want["name"])
        entry["ip"] = (8, want["address"])
    root = {"servers": (9, (10, servers))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes([10]) + nbt_string("") + nbt_payload(10, root))


def set_options(path, options):
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


def update_pack(path, minecraft, fabric):
    want = {"net.minecraft": minecraft}
    if fabric:
        want["net.fabricmc.fabric-loader"] = fabric
    try:
        have = {c["uid"]: c.get("version") for c in json.loads(path.read_text())["components"]}
    except (OSError, ValueError, KeyError):
        have = {}
    same = all(have.get(k) == v for k, v in want.items())
    if same and (fabric or "net.fabricmc.fabric-loader" not in have):
        return   # Prism's own resolved file; leave it
    components = [{"important": True, "uid": "net.minecraft", "version": minecraft}]
    if fabric:
        components.append({"uid": "net.fabricmc.fabric-loader", "version": fabric})
    path.write_text(json.dumps({"components": components, "formatVersion": 1}, indent=4))


def update_mods(mods_dir, jars):
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


def main():
    if sys.argv[1] == "fullscreen":
        d = Path(sys.argv[2])
        if d.is_dir():
            (d / ".minecraft").mkdir(exist_ok=True)
            set_options(d / ".minecraft/options.txt", {"fullscreen": "true"})
        return
    spec = json.loads(sys.argv[1])
    root = Path(spec["root"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    set_keys(root / "prismlauncher.cfg", spec["launcher"])
    for name, inst in spec["instances"].items():
        d = root / "instances" / name
        (d / ".minecraft").mkdir(parents=True, exist_ok=True)
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
