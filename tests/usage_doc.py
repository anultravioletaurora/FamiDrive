"""USAGE.md, from FamiDrive's option declarations.

    python3 usage_doc.py OPTIONS_JSON > docs/USAGE.md

OPTIONS_JSON is what tests/default.nix writes from a box's options (name,
type, description, default, example, readOnly). The `usage-doc` check
runs this and fails when USAGE.md differs, so the page can't drift from
the options: change an option's description, not this page.
"""

import json
import sys

# Sections, in the order a new box is set up. An option goes in the
# first section whose prefix it starts with; anything new that matches
# none lands in "Everything else" until it's given a place here.
SECTIONS = [
    ("The box", ["famidrive.enable", "famidrive.lanes", "famidrive.dataDir", "famidrive.localRoms"],
     "What the box is: on or off, which kinds of games it carries, and where its shared library lives."),
    ("Players", ["famidrive.players", "famidrive.primaryPlayer", "famidrive.guest"],
     "Who plays. Each player is a Linux account and a RomM user of their own."),
    ("Servers", ["famidrive.endpoints"],
     "Your servers' addresses. None has a default: they're yours, not FamiDrive's. Each is only "
     "read when the feature that uses it is on, so a box that doesn't use one doesn't set it."),
    ("RomM", ["famidrive.romm"],
     "The game library, firmware and console saves, from your own [RomM](https://github.com/rommapp/romm). "
     "Optional: a box can also run from ROM folders already on it (`localRoms`)."),
    ("Hardware", ["famidrive.gpu"],
     "The box's graphics card. AMD is tested, Intel should just work, Nvidia is untested."),
    ("TV and session", ["famidrive.display", "famidrive.session", "famidrive.cec", "famidrive.boot"],
     "The picture, and what happens to the TV on a rebuild."),
    ("Menu", ["famidrive.esde"], "ES-DE, the menu everything launches from."),
    ("Switch", ["famidrive.switch"], "Switch games that run in Ryujinx instead of Eden."),
    ("Controllers", ["famidrive.controllers"],
     "How controllers reach the emulators. Per-controller results are in [CONTROLLERS.md](CONTROLLERS.md)."),
    ("Steam", ["famidrive.steam"], "The Steam lane (`lanes` has `\"steam\"`)."),
    ("Media", ["famidrive.media"], "Video apps in ES-DE's Media system."),
    ("Clone Hero", ["famidrive.cloneHero"], "Clone Hero, in the Desktop system."),
    ("YARG", ["famidrive.yarg"],
     "YARG (Yet Another Rhythm Game), in the Desktop system, playing the same songs as Clone Hero."),
    ("osu!", ["famidrive.osu"], "osu! (lazer), in the Desktop system."),
    ("Tux games", ["famidrive.superTuxKart", "famidrive.superTux", "famidrive.superTuxParty",
                   "famidrive.superTuxAdvance", "famidrive.extremeTuxRacer", "famidrive.tuxPaint"],
     "Free games starring Tux, in the Desktop system: SuperTuxKart, SuperTux, SuperTux Party, "
     "SuperTux Advance, Extreme Tux Racer and Tux Paint."),
    ("Miis", ["famidrive.miis"], "Miis, made in each console's own editor and synced with RomM."),
    ("Space Cadet Pinball", ["famidrive.spaceCadetPinball"],
     "3D Pinball Space Cadet, in the Ports system, playing your own copy of the game's files."),
    ("Minecraft", ["famidrive.minecraft"],
     "Minecraft through Prism Launcher, in the Desktop system (`lanes` has `\"minecraft\"`)."),
    ("PC saves", ["famidrive.pcSaves"], "Syncing PC games' saves that Steam Cloud doesn't."),
    ("Online play", ["famidrive.online"], "Emulator netplay, through the servers in Servers."),
    ("Systems", ["famidrive.systems"],
     "The systems in ES-DE's menu. FamiDrive fills these in for every console it supports; most "
     "boxes never set them."),
]
OTHER = ("Everything else", [], "")


def section_of(name):
    for sec in SECTIONS:
        if any(name == p or name.startswith(p + ".") for p in sec[1]):
            return sec
    return OTHER


def anchor(title):
    return "".join(c for c in title.lower().replace(" ", "-") if c.isalnum() or c == "-")


def value(v):
    """A default or example, as Nix."""
    if isinstance(v, dict) and v.get("_type") in ("literalExpression", "literalMD"):
        text = v["text"]
        if v["_type"] == "literalMD":
            return text.strip()
    else:
        text = json.dumps(v)
    text = text.strip()
    if "\n" in text:
        return "\n\n  ```nix\n" + "\n".join("  " + line for line in text.splitlines()) + "\n  ```"
    return f"`{text}`"


def render(options):
    by_section = {}
    for o in sorted(options, key=lambda o: o["name"].lower()):
        by_section.setdefault(section_of(o["name"])[0], []).append(o)
    order = [s for s in SECTIONS + [OTHER] if s[0] in by_section]
    out = [
        "# Usage",
        "",
        "Every option a box's `configuration.nix` can set, under `famidrive.`. For",
        "setting up a box, start with [Using it](../README.md#using-it) in the README.",
        "",
        "Options without a default have to be set when the feature that uses them",
        "is on; every other option is optional.",
        "",
        "<!-- Generated from the option declarations by tests/usage_doc.py. CI",
        "     fails when this file is out of date. To change it, change the",
        "     option's description, then regenerate on an x86_64-linux machine:",
        "     nix build .#checks.x86_64-linux.usage-doc.doc && cp result docs/USAGE.md -->",
        "",
        "## Contents",
        "",
    ]
    out += [f"- [{title}](#{anchor(title)})" for title, _, _ in order]
    for sec in order:
        title, _, intro = sec
        if out[-1] != "":
            out.append("")
        out += [f"## {title}", ""]
        if intro:
            out += [intro, ""]
        for o in by_section[title]:
            out += [f"### `{o['name']}`", ""]
            desc = (o.get("description") or "").strip()
            if desc:
                out += [desc, ""]
            out.append(f"- **Type:** {o['type']}")
            if o.get("readOnly"):
                out.append("- **Read-only:** set by FamiDrive")
            if "default" in o and o["default"] is not None:
                out.append(f"- **Default:** {value(o['default'])}")
            elif o.get("hasDefault"):
                out.append("- **Default:** `null`")
            else:
                out.append("- **Default:** none; required when used")
            if o.get("example") is not None:
                out.append(f"- **Example:** {value(o['example'])}")
            out.append("")
    while out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(json.loads(open(sys.argv[1]).read())))
