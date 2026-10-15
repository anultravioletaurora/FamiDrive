"""famidrive-hardware [check CONFIGURED | display | offload]

Which graphics cards this box has, read from the PCI bus (sysfs), and
the famidrive.gpu setting that suits them.

    famidrive-hardware            list the cards and the setting to use
    famidrive-hardware check X    at boot: warn when the box is set to X
                                  but has a card X doesn't drive
                                  (an Nvidia card without "nvidia")
    famidrive-hardware display    at session start, on a box with more
                                  than one card: the card the TV is on,
                                  as vendor:device for gamescope's
                                  --prefer-vk-device. Nothing (exit 1)
                                  with one card.
    famidrive-hardware offload    at session start: exit 0 when games
                                  should render on an Nvidia card that
                                  isn't the one the TV is on (a laptop's
                                  hybrid graphics), printing its
                                  vendor:device; exit 1 otherwise.

AMD and Intel cards both use Mesa, which every box has, so "auto" drives
them; only Nvidia's driver has to be chosen when the box is built.
"""

import os
import sys
from pathlib import Path

PCI = Path(os.environ.get("FAMIDRIVE_SYSFS", "/sys")) / "bus/pci/devices"
VENDORS = {"0x1002": "amd", "0x8086": "intel", "0x10de": "nvidia"}
NAMES = {"amd": "AMD", "intel": "Intel", "nvidia": "Nvidia"}


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def gpus():
    """Display controllers (PCI class 0x03), in bus order.

    Each one's vendor, its vendor:device id, the kernel driver bound to
    it, and its outputs' states ("connected", "disconnected"), from the
    DRM cards under it. A laptop's Nvidia card is often a 3D controller
    (0x0302) with no outputs at all: the Intel or AMD card has the
    screen, and the HDMI port, and shows what the Nvidia card renders.
    """
    found = []
    for dev in sorted(PCI.iterdir()) if PCI.is_dir() else []:
        cls, vendor, device = read(dev / "class"), read(dev / "vendor"), read(dev / "device")
        if not (cls and vendor and cls.startswith("0x03")):
            continue
        driver = dev / "driver"
        outputs = [read(c / "status") for card in sorted(dev.glob("drm/card*"))
                   for c in sorted(card.glob(card.name + "-*"))]
        found.append({
            "slot": dev.name,
            "vendor": VENDORS.get(vendor, f"unknown ({vendor})"),
            "id": f"{vendor[2:]}:{(device or '0x0000')[2:]}",
            "driver": driver.resolve().name if driver.exists() else None,
            "outputs": outputs,
            "boot_vga": read(dev / "boot_vga") == "1",
        })
    return found


def display(found):
    """The card the TV is on: one with a screen connected, else one with
    outputs at all (the TV may be off), else the one the firmware booted
    on. gamescope otherwise takes the first card Vulkan lists, which on
    a laptop can be the Nvidia card with nothing to show on."""
    for pick in (lambda g: "connected" in g["outputs"], lambda g: g["outputs"], lambda g: g["boot_vga"]):
        cards = [g for g in found if pick(g)]
        if cards:
            return cards[0]
    return found[0] if found else None


def offload(found):
    """The Nvidia card games should render on, when the TV is on another
    card and Nvidia's own driver drives this one (famidrive.gpu =
    "nvidia"). None otherwise: nouveau, or the TV on the Nvidia card."""
    shown = display(found)
    if shown is None or shown["vendor"] == "nvidia":
        return None
    return next((g for g in found if g["vendor"] == "nvidia" and g["driver"] == "nvidia"), None)


def suggested(found):
    return "nvidia" if any(g["vendor"] == "nvidia" for g in found) else "auto"


def cmd_list():
    found = gpus()
    if not found:
        print("No graphics card found on the PCI bus.")
        return
    shown = display(found) if len(found) > 1 else None
    for g in found:
        note = "  (the screen is on this one)" if g is shown else ""
        print(f"{g['slot']}  {NAMES.get(g['vendor'], g['vendor'])}{note}")
    if shown and shown["vendor"] != "nvidia" and any(g["vendor"] == "nvidia" for g in found):
        print("\nHybrid graphics: with \"nvidia\", games render on the Nvidia card and "
              f"the {NAMES.get(shown['vendor'], shown['vendor'])} card shows them.")
    print(f'\nSet in configuration.nix:  famidrive.gpu = "{suggested(found)}";')


def cmd_check(configured):
    vendors = {g["vendor"] for g in gpus()}
    if "nvidia" in vendors and configured != "nvidia":
        print('famidrive-hardware: this box has an Nvidia card, but famidrive.gpu is not "nvidia", '
              'so it has no Nvidia driver. Set famidrive.gpu = "nvidia"; in configuration.nix and rebuild.',
              file=sys.stderr)
        return 1
    if configured == "nvidia" and "nvidia" not in vendors:
        print('famidrive-hardware: famidrive.gpu is "nvidia", but no Nvidia card was found.', file=sys.stderr)
        return 1
    return 0


def cmd_display():
    found = gpus()
    if len(found) < 2:
        return 1
    print(display(found)["id"])
    return 0


def cmd_offload():
    card = offload(gpus())
    if card is None:
        return 1
    print(card["id"])
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        cmd_list()
    elif args[0] == "check" and len(args) == 2:
        # A mismatch is reported, not fatal: the box still boots.
        cmd_check(args[1])
    elif args == ["display"]:
        sys.exit(cmd_display())
    elif args == ["offload"]:
        sys.exit(cmd_offload())
    else:
        print(__doc__)
        sys.exit(64)


if __name__ == "__main__":
    main()
