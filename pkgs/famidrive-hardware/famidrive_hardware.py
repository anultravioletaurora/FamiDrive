"""famidrive-hardware [check CONFIGURED]

Which graphics cards this box has, read from the PCI bus (sysfs), and
the famidrive.gpu setting that suits them.

    famidrive-hardware            list the cards and the setting to use
    famidrive-hardware check X    at boot: warn when the box is set to X
                                  but has a card X doesn't drive
                                  (an Nvidia card without "nvidia")

AMD and Intel cards both use Mesa, which every box has, so "auto" drives
them; only Nvidia's driver has to be chosen when the box is built.
"""

import os
import sys
from pathlib import Path

PCI = Path(os.environ.get("FAMIDRIVE_SYSFS", "/sys")) / "bus/pci/devices"
VENDORS = {"0x1002": "amd", "0x8086": "intel", "0x10de": "nvidia"}
NAMES = {"amd": "AMD", "intel": "Intel", "nvidia": "Nvidia"}


def gpus():
    """Display controllers (PCI class 0x03), by vendor, in bus order."""
    found = []
    for dev in sorted(PCI.iterdir()) if PCI.is_dir() else []:
        try:
            cls = (dev / "class").read_text().strip()
            vendor = (dev / "vendor").read_text().strip()
        except OSError:
            continue
        if cls.startswith("0x03"):
            found.append((dev.name, VENDORS.get(vendor, f"unknown ({vendor})")))
    return found


def suggested(found):
    return "nvidia" if any(v == "nvidia" for _, v in found) else "auto"


def cmd_list():
    found = gpus()
    if not found:
        print("No graphics card found on the PCI bus.")
        return
    for slot, vendor in found:
        print(f"{slot}  {NAMES.get(vendor, vendor)}")
    print(f'\nSet in configuration.nix:  famidrive.gpu = "{suggested(found)}";')


def cmd_check(configured):
    found = gpus()
    vendors = {v for _, v in found}
    if "nvidia" in vendors and configured != "nvidia":
        print('famidrive-hardware: this box has an Nvidia card, but famidrive.gpu is not "nvidia", '
              'so it has no Nvidia driver. Set famidrive.gpu = "nvidia"; in configuration.nix and rebuild.',
              file=sys.stderr)
        return 1
    if configured == "nvidia" and "nvidia" not in vendors:
        print('famidrive-hardware: famidrive.gpu is "nvidia", but no Nvidia card was found.', file=sys.stderr)
        return 1
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        cmd_list()
    elif args[0] == "check" and len(args) == 2:
        # A mismatch is reported, not fatal: the box still boots.
        cmd_check(args[1])
    else:
        print(__doc__)
        sys.exit(64)


if __name__ == "__main__":
    main()
