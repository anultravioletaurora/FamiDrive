"""famidrive-generate LANE SOURCE_DIR OUT_DIR

Rewrite OUT_DIR so it holds exactly one placeholder per installed game in
SOURCE_DIR. Each placeholder's *content* is the launch ID that famidrive-launch
hands to the real launcher. Its filename is the display name ES-DE shows.
"""

import re
import sys
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


def gog(src):
    # TODO: gogdl-cli's installed-games manifest format and location.
    return iter(())


def minecraft(src):
    # instances/<id>/instance.cfg; the folder name is the ID --launch takes.
    for cfg in src.glob("*/instance.cfg"):
        name = re.search(r"^name=(.+)$", cfg.read_text(errors="replace"), re.M)
        yield (name.group(1) if name else cfg.parent.name), cfg.parent.name


LANES = {"steam": (steam, ".steam"), "gog": (gog, ".gog"), "minecraft": (minecraft, ".prism")}


def safe(name):
    return re.sub(r'[/\\:*?"<>|]', "_", name).strip()


def main():
    lane, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    reader, ext = LANES[lane]
    out.mkdir(parents=True, exist_ok=True)

    wanted = {safe(name) + ext: launch_id for name, launch_id in reader(src)}
    for existing in out.glob("*" + ext):
        if existing.name not in wanted:
            existing.unlink()  # uninstalled: drop the entry
    for filename, launch_id in wanted.items():
        p = out / filename
        if not p.exists() or p.read_text() != launch_id:
            p.write_text(launch_id)


if __name__ == "__main__":
    main()
