"""famidrive-network: Wi-Fi and Ethernet from ES-DE's Settings.

    famidrive-network entries DIR   Settings entries for this box (session start)
    famidrive-network launch FILE   what an entry does when it's launched

No screens of its own, like famidrive-bluetooth: the entries are ES-DE
games in the Settings system, drawn by the player's theme, and what happens
shows as toasts in the theme's look.

`entries` writes into DIR (the player's Settings folder), one .setting file
each, and removes its old ones:

  Wi-Fi: <network>              each network in range, strongest first
  Wi-Fi: <network> (connected)  the one the box is on
  Forget Wi-Fi: <network>       each one the box remembers
  Ethernet                      each wired port (Ethernet 2, ... if more)

ES-DE reads the folder when it starts, so the list is as it was then.

Launching a network joins it. A network with a password needs it typed
first, and ES-DE's only text box a player can reach is in its game-info
editor: Select on the network, "Edit this game's metadata", the password as
its Sort name, Save, then launch it. This reads it from ES-DE's game list,
joins with it, and wipes it from the list (again at the next session start,
since ES-DE may write the list back from memory). The network is saved for
the whole box, so it's there before anyone picks a player too.

Launching Ethernet shows its state: cable or not, address, speed and the
port's hardware address, and connects it if a cable is in but it isn't up.

Lists come from nmcli; joining goes to NetworkManager over D-Bus, so the
password is never on a command line other players could see.
"""

import asyncio
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PREFIX = "network-"   # what entries' files start with; anything else isn't ours
MAX_NETWORKS = 15
GAMELIST = Path.home() / "ES-DE/gamelists/settings/gamelist.xml"
NM = "org.freedesktop.NetworkManager"
ACTIVATED, FAILED = 100, 120   # NMDeviceState


def log(msg):
    print(f"famidrive-network: {msg}", file=sys.stderr, flush=True)


def toast(*args):
    """A toast on the TV. Never fails the caller."""
    exe = shutil.which("famidrive-toast")
    if exe:
        try:
            subprocess.run([exe, *args], timeout=5, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass


# ---------------------------------------------------------------- nmcli

def split_terse(line):
    """One line of `nmcli -t`: fields split on ':', with '\\:' and '\\\\'
    inside a field."""
    fields, cur, i = [], "", 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur += line[i + 1]
            i += 2
            continue
        if c == ":":
            fields.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    fields.append(cur)
    return fields


def nmcli(*args):
    exe = shutil.which("nmcli")
    if not exe:
        return None
    r = subprocess.run([exe, "-t", *args], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        log(f"nmcli {' '.join(args)}: {r.stderr.strip()}")
        return None
    return [split_terse(line) for line in r.stdout.splitlines() if line]


def safe(name):
    """A name fit for a file name (ES-DE shows the file's name)."""
    return re.sub(r'[/\\:*?"<>|\n\r\t]', "", name).strip()


def plan_entries(devices, networks, saved):
    """{file name: contents}. devices: [(device, type, state)]; networks:
    [(in_use, ssid, security, signal)] as nmcli lists them; saved: names
    of remembered Wi-Fi connections."""
    out = {}
    wifi = any(t == "wifi" for _, t, _ in devices)
    if wifi:
        # One entry per network name: several access points can share one.
        best = {}
        for in_use, ssid, security, signal in networks:
            if not safe(ssid):
                continue
            sig = int(signal) if signal.isdigit() else 0
            on, sec, top = best.get(ssid, (False, security, -1))
            best[ssid] = (on or in_use == "*", sec, max(top, sig))
        ranked = sorted(best.items(), key=lambda kv: (not kv[1][0], -kv[1][2], kv[0].lower()))
        for ssid, (on, security, _) in ranked[:MAX_NETWORKS]:
            label = f"Wi-Fi: {safe(ssid)}" + (" (connected)" if on else "")
            out[f"{label}.setting"] = f"{PREFIX}wifi\n{ssid}\n{security}"
        for name in saved:
            if safe(name):
                out[f"Forget Wi-Fi: {safe(name)}.setting"] = f"{PREFIX}forget\n{name}"
    wired = [d for d, t, _ in devices if t == "ethernet"]
    for i, dev in enumerate(wired):
        label = "Ethernet" if i == 0 else f"Ethernet {i + 1}"
        out[f"{label}.setting"] = f"{PREFIX}ethernet\n{dev}"
    return out


def write_entries(folder, planned):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for f in folder.glob("*.setting"):
        try:
            ours = f.read_text().startswith(PREFIX)
        except OSError:
            continue
        if ours and f.name not in planned:
            f.unlink()
    for name, what in planned.items():
        p = folder / name
        if not p.exists() or p.read_text() != what:
            p.write_text(what)


# ---------------------------------------------------------------- passwords in ES-DE's game list

def typed_password(gamelist, entry_name):
    """The Sort name typed for an entry in ES-DE's game-info editor, or None."""
    try:
        root = ET.parse(gamelist).getroot()
    except (OSError, ET.ParseError):
        return None
    for game in root.iter("game"):
        if (game.findtext("path") or "").lstrip("./") == entry_name:
            value = game.findtext("sortname")
            return value if value else None
    return None


def wipe_passwords(gamelist):
    """Removes every Sort name typed for a Wi-Fi entry. True if any went."""
    try:
        tree = ET.parse(gamelist)
    except (OSError, ET.ParseError):
        return False
    changed = False
    for game in tree.getroot().iter("game"):
        if (game.findtext("path") or "").lstrip("./").startswith("Wi-Fi: "):
            for s in game.findall("sortname"):
                game.remove(s)
                changed = True
    if changed:
        tmp = Path(str(gamelist) + ".famidrive-tmp")
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        tmp.chmod(0o600)
        tmp.replace(gamelist)
    return changed


# ---------------------------------------------------------------- joining, over D-Bus

def key_mgmt(security):
    """NetworkManager's key-mgmt for nmcli's SECURITY column, or None for
    an open network."""
    s = security.upper()
    if not s or s == "--":
        return None
    if "WPA3" in s and "WPA2" not in s and "WPA1" not in s:
        return "sae"
    if "802.1X" in s:
        return "wpa-eap"
    return "wpa-psk"


async def join(device, ssid, security, password):
    """Join a new network with its password, saved for the whole box.
    Returns an error message, or None."""
    from dbus_next.aio import MessageBus
    from dbus_next import BusType, Variant

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    async def proxy(path, iface):
        intro = await bus.introspect(NM, path)
        return bus.get_proxy_object(NM, path, intro).get_interface(iface)

    nm = await proxy("/org/freedesktop/NetworkManager", NM)
    dev_path = await nm.call_get_device_by_ip_iface(device)
    settings = {
        "connection": {"id": Variant("s", ssid), "type": Variant("s", "802-11-wireless")},
        "802-11-wireless": {"ssid": Variant("ay", ssid.encode())},
    }
    mgmt = key_mgmt(security)
    if mgmt == "wpa-eap":
        return "Networks that sign in with a username (WPA Enterprise) aren't supported yet."
    if mgmt:
        settings["802-11-wireless-security"] = {"key-mgmt": Variant("s", mgmt), "psk": Variant("s", password)}
    await nm.call_add_and_activate_connection(settings, dev_path, "/")
    dev = await proxy(dev_path, "org.freedesktop.NetworkManager.Device")
    for _ in range(40):
        state = await dev.get_state()
        if state == ACTIVATED:
            return None
        if state == FAILED:
            break
        await asyncio.sleep(0.5)
    return "The password may be wrong, or the network out of reach."


# ---------------------------------------------------------------- launching

def wifi_device():
    for dev, typ, _ in nmcli("-f", "DEVICE,TYPE,STATE", "device", "status") or []:
        if typ == "wifi":
            return dev
    return None


def saved_wifi():
    return [name for name, typ in (nmcli("-f", "NAME,TYPE", "connection", "show") or [])
            if typ == "802-11-wireless"]


def active_wifi():
    return [name for name, typ in (nmcli("-f", "NAME,TYPE", "connection", "show", "--active") or [])
            if typ == "802-11-wireless"]


def launch_wifi(entry_name, ssid, security):
    if ssid in active_wifi():
        device = wifi_device()
        info = ethernet_status(device) if device else {}
        address = info.get("IP4.ADDRESS", "").split("/")[0]
        toast("--kind", "notice", "--icon", "info", "--seconds", "10", f"Connected to {ssid}",
              f"Address {address}" if address else "")
        return 0
    if ssid in saved_wifi():
        toast("--kind", "progress", "--id", "network", "--icon", "info", f"Joining {ssid}", "")
        ok = nmcli("connection", "up", "id", ssid) is not None
        toast("--kind", "progress", "--id", "network", "--done", "--icon", "info",
              f"Joined {ssid}" if ok else f"Couldn't join {ssid}", "")
        if not ok:
            toast("--kind", "alert", f"Couldn't join {ssid}",
                  f"It may be out of reach. Forget Wi-Fi: {ssid}, then join again with its password.")
        return 0 if ok else 1
    password = None
    if key_mgmt(security):
        password = typed_password(GAMELIST, entry_name)
        if not password:
            toast("--kind", "alert", "--seconds", "15", f"{ssid} needs its password",
                  "Press Select on it, Edit this game's metadata, type the password as its Sort name, Save, then launch it again.")
            return 1
    device = wifi_device()
    if not device:
        toast("--kind", "alert", "No Wi-Fi on this box", "")
        return 1
    toast("--kind", "progress", "--id", "network", "--icon", "info", f"Joining {ssid}", "")
    try:
        err = asyncio.run(join(device, ssid, security, password or ""))
    except Exception as e:   # D-Bus refusals arrive as several error types
        log(f"joining: {e}")
        err = "NetworkManager refused it."
    wipe_passwords(GAMELIST)
    toast("--kind", "progress", "--id", "network", "--done", "--icon", "info",
          f"Joined {ssid}" if not err else f"Couldn't join {ssid}", "")
    if err:
        toast("--kind", "alert", f"Couldn't join {ssid}", err)
        # A failed new network isn't kept, so the next try starts clean.
        nmcli("connection", "delete", "id", ssid)
        return 1
    toast("--kind", "notice", "--icon", "check", f"Joined {ssid}", "The box remembers it from now on.")
    return 0


def launch_forget(name):
    ok = nmcli("connection", "delete", "id", name) is not None
    toast("--kind", "notice", "--icon", "info", f"Forgot {name}" if ok else "Already forgotten",
          "Join it again from Settings to use it." if ok else "")
    return 0


def ethernet_status(dev):
    """A port's state, address, speed and hardware address (nmcli device show)."""
    info = {}
    for row in nmcli("-f", "GENERAL.STATE,GENERAL.HWADDR,WIRED-PROPERTIES.CARRIER,CAPABILITIES.SPEED,IP4.ADDRESS,IP4.GATEWAY",
                     "device", "show", dev) or []:
        if len(row) >= 2:
            info.setdefault(row[0].split("[")[0], ":".join(row[1:]))
    return info


def describe_ethernet(info):
    mac = info.get("GENERAL.HWADDR", "")
    if info.get("WIRED-PROPERTIES.CARRIER") == "off":
        return "No cable in the Ethernet port", f"Hardware address {mac}".strip()
    state = info.get("GENERAL.STATE", "")
    address = info.get("IP4.ADDRESS", "").split("/")[0]
    speed = info.get("CAPABILITIES.SPEED", "")
    if state.startswith("100") and address:
        parts = [f"Address {address}", speed if speed and speed != "unknown" else "", f"hardware {mac}" if mac else ""]
        return "Ethernet connected", " · ".join(p for p in parts if p)
    return "Ethernet not connected", f"Hardware address {mac}".strip()


def launch_ethernet(dev):
    title, detail = describe_ethernet(ethernet_status(dev))
    if title == "Ethernet not connected":
        nmcli("device", "connect", dev)
        title, detail = describe_ethernet(ethernet_status(dev))
    toast("--kind", "notice", "--icon", "info", "--seconds", "10", title, detail)
    return 0


def launch(path):
    lines = Path(path).read_text().split("\n")
    kind = lines[0][len(PREFIX):] if lines[0].startswith(PREFIX) else ""
    if kind == "wifi" and len(lines) >= 2:
        return launch_wifi(Path(path).name, lines[1], lines[2] if len(lines) > 2 else "")
    if kind == "forget" and len(lines) >= 2:
        return launch_forget(lines[1])
    if kind == "ethernet" and len(lines) >= 2:
        return launch_ethernet(lines[1])
    log(f"{path}: not a network entry")
    return 2


def entries(folder):
    wipe_passwords(GAMELIST)
    devices = nmcli("-f", "DEVICE,TYPE,STATE", "device", "status")
    if devices is None:   # no NetworkManager: nothing to offer
        write_entries(folder, {})
        return 0
    devices = [tuple(d[:3]) for d in devices if len(d) >= 3]
    networks = []
    if any(t == "wifi" for _, t, _ in devices):
        networks = [tuple(n[:4]) for n in (nmcli("-f", "IN-USE,SSID,SECURITY,SIGNAL", "device", "wifi", "list") or [])
                    if len(n) >= 4]
    write_entries(folder, plan_entries(devices, networks, saved_wifi()))
    return 0


def main():
    args = sys.argv[1:]
    if args[:1] == ["entries"] and len(args) == 2:
        return entries(args[1])
    if args[:1] == ["launch"] and len(args) == 2:
        return launch(args[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    os.umask(0o077)
    sys.exit(main())
