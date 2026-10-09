"""famidrive-bluetooth: pair and forget Bluetooth controllers from the couch.

    famidrive-bluetooth entries DIR     Settings entries for this box (session start)
    famidrive-bluetooth pair [SECONDS]  find a controller in pairing mode and pair it
    famidrive-bluetooth forget ADDRESS  forget a paired controller

No screens of its own: the entries are ES-DE games in the Settings system,
drawn by the player's theme like any other, and what happens while pairing
shows as toasts (famidrive-toast), also in the theme's look.

`entries` writes "Pair a Controller" and one "Forget <name>" per paired
controller into DIR (the player's Settings folder), each a .setting file
holding what settings.nix runs for it, and removes its old ones. A box
with no Bluetooth adapter gets none, so the entries only show where
pairing can work. ES-DE reads the folder when it starts, so a controller
paired or forgotten changes the list from the next session.

`pair` scans until a controller in pairing mode shows up, then pairs,
trusts and connects it in one step: no list to pick from, so a player whose
only other controller is a keyboard, or a pad they're about to put away,
can still do it. It talks to BlueZ over D-Bus, with an agent that accepts
without a PIN (controllers don't use one; Wii Remotes get theirs from
BlueZ's wiimote plugin).
"""

import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path

BLUEZ = "org.bluez"
AGENT_PATH = "/org/famidrive/bluetooth_agent"
PREFIX = "bluetooth-"           # what entries' files hold; anything else isn't ours
PAIR_ENTRY = "Pair a Controller"

# How each kind goes into pairing mode, shown in turn while scanning.
HINTS = [
    "Wii Remote: press the red sync button",
    "DualSense or DualShock 4: hold Create (Share) + PS",
    "Xbox controller: hold the pair button on top",
    "Switch Pro Controller: hold the sync button on top",
    "8BitDo: hold the pair button, or as its manual says",
]

# Bluetooth names -> what a player calls them. First match wins.
NAMES = [
    (r"^Nintendo RVL-CNT-01-TR$", "Wii Remote Plus"),
    (r"^Nintendo RVL-CNT-01-UC$", "Wii U Pro Controller"),
    (r"^Nintendo RVL-CNT-01$", "Wii Remote"),
    (r"^Nintendo RVL-WBC-01$", "Wii Balance Board"),
    (r"^DualSense Edge", "DualSense Edge"),
    (r"^DualSense", "DualSense"),
    (r"^Wireless Controller$", "DualShock 4"),
    (r"^PLAYSTATION\(R\)3 Controller$", "DualShock 3"),
    (r"^Xbox (Wireless|Elite|Adaptive)", None),     # already a good name
    (r"^Pro Controller$", "Switch Pro Controller"),
    (r"^Joy-Con \(L\)$", "Joy-Con (L)"),
    (r"^Joy-Con \(R\)$", "Joy-Con (R)"),
]
CONTROLLER_NAMES = re.compile(r"RVL-CNT|RVL-WBC|DualSense|Wireless Controller|PLAYSTATION|Xbox|Pro Controller|Joy-Con|8BitDo|Gamepad|Controller", re.I)


def log(msg):
    print(f"famidrive-bluetooth: {msg}", file=sys.stderr, flush=True)


def friendly(name):
    """The name a player knows a controller by, from its Bluetooth name."""
    name = (name or "").strip()
    for pattern, nice in NAMES:
        if re.search(pattern, name):
            return nice or name
    return name or "Controller"


def is_controller(props):
    """A Device1's properties look like a game controller: BlueZ's gamepad
    icon, a Bluetooth Classic class of joystick or gamepad, a Bluetooth LE
    appearance of either, or a name that's one."""
    if props.get("Icon") == "input-gaming":
        return True
    cls = props.get("Class")
    if cls is not None and (cls >> 8) & 0x1F == 0x05 and (cls >> 2) & 0x0F in (1, 2):
        return True   # peripheral: joystick (Wii Remotes) or gamepad
    if props.get("Appearance") in (0x03C3, 0x03C4):
        return True
    return bool(CONTROLLER_NAMES.search(props.get("Name") or props.get("Alias") or ""))


def safe(name):
    """A name fit for a file name (ES-DE shows the file's name)."""
    return re.sub(r'[/\\:*?"<>|]', "", name).strip() or "Controller"


def plan_entries(has_adapter, paired):
    """{file name: contents} for the Settings folder. `paired` is a list
    of (address, name) for paired controllers, in order."""
    if not has_adapter:
        return {}
    out = {f"{PAIR_ENTRY}.setting": f"{PREFIX}pair"}
    for address, name in paired:
        base, n = f"Forget {safe(friendly(name))}", 1
        while f"{base}.setting" in out:   # two of the same kind
            n += 1
            base = f"Forget {safe(friendly(name))} ({n})"
        out[f"{base}.setting"] = f"{PREFIX}forget {address}"
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


def toast(*args):
    """A toast on the TV. Never fails the caller."""
    exe = shutil.which("famidrive-toast")
    if exe:
        try:
            subprocess.run([exe, *args], timeout=5, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass


# ---------------------------------------------------------------- BlueZ

def unwrap(props):
    return {k: getattr(v, "value", v) for k, v in props.items()}


async def system_bus():
    from dbus_next.aio import MessageBus
    from dbus_next import BusType
    return await MessageBus(bus_type=BusType.SYSTEM).connect()


async def managed_objects(bus):
    intro = await bus.introspect(BLUEZ, "/")
    om = bus.get_proxy_object(BLUEZ, "/", intro).get_interface("org.freedesktop.DBus.ObjectManager")
    objs = await om.call_get_managed_objects()
    return {path: {iface: unwrap(p) for iface, p in ifaces.items()} for path, ifaces in objs.items()}


async def iface(bus, path, name):
    intro = await bus.introspect(BLUEZ, path)
    return bus.get_proxy_object(BLUEZ, path, intro).get_interface(name)


def first_adapter(objs):
    return next((p for p, i in sorted(objs.items()) if "org.bluez.Adapter1" in i), None)


def devices(objs, adapter):
    return [(p, i["org.bluez.Device1"]) for p, i in sorted(objs.items())
            if "org.bluez.Device1" in i and i["org.bluez.Device1"].get("Adapter") == adapter]


def paired_controllers(objs, adapter):
    return [(d["Address"], d.get("Alias") or d.get("Name")) for _, d in devices(objs, adapter)
            if d.get("Paired") and is_controller(d)]


def make_agent():
    from dbus_next.service import ServiceInterface, method

    class Agent(ServiceInterface):
        """Accepts everything a controller asks: there's no one to type a
        PIN or confirm a number on a TV, and controllers don't need it."""
        def __init__(self):
            super().__init__("org.bluez.Agent1")

        @method()
        def Release(self):
            pass

        @method()
        def RequestPinCode(self, device: "o") -> "s":
            return "0000"

        @method()
        def DisplayPinCode(self, device: "o", pincode: "s"):
            pass

        @method()
        def RequestPasskey(self, device: "o") -> "u":
            return 0

        @method()
        def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
            pass

        @method()
        def RequestConfirmation(self, device: "o", passkey: "u"):
            pass

        @method()
        def RequestAuthorization(self, device: "o"):
            pass

        @method()
        def AuthorizeService(self, device: "o", uuid: "s"):
            pass

        @method()
        def Cancel(self):
            pass

    return Agent()


async def pair(seconds):
    from dbus_next import Variant
    from dbus_next.errors import DBusError

    bus = await system_bus()
    objs = await managed_objects(bus)
    adapter = first_adapter(objs)
    if not adapter:
        toast("--kind", "alert", "--icon", "controller", "No Bluetooth on this box",
              "A USB Bluetooth adapter, or an M.2 Wi-Fi and Bluetooth card, adds it.")
        return 1

    bus.export(AGENT_PATH, make_agent())
    manager = await iface(bus, "/org/bluez", "org.bluez.AgentManager1")
    await manager.call_register_agent(AGENT_PATH, "NoInputNoOutput")
    await manager.call_request_default_agent(AGENT_PATH)

    ad = await iface(bus, adapter, "org.bluez.Adapter1")
    props = await iface(bus, adapter, "org.freedesktop.DBus.Properties")
    await props.call_set("org.bluez.Adapter1", "Powered", Variant("b", True))
    try:
        await ad.call_set_discovery_filter({"Transport": Variant("s", "auto")})
    except DBusError as e:
        log(f"discovery filter: {e.text}")
    await ad.call_start_discovery()
    log("scanning")

    found = None
    loop = asyncio.get_running_loop()
    start = loop.time()
    hint = -1
    try:
        while loop.time() - start < seconds:
            elapsed = loop.time() - start
            if int(elapsed // 4) != hint:
                hint = int(elapsed // 4)
                toast("--kind", "progress", "--id", "bluetooth-pair", "--icon", "controller",
                      "--progress", f"{elapsed / seconds:.2f}",
                      "Looking for a controller in pairing mode", HINTS[hint % len(HINTS)])
            objs = await managed_objects(bus)
            # Seen in this scan (RSSI) and not paired yet: in pairing mode now.
            ready = [(p, d) for p, d in devices(objs, adapter)
                     if not d.get("Paired") and "RSSI" in d and is_controller(d)]
            if ready:
                found = ready[0]
                break
            await asyncio.sleep(1)
    finally:
        try:
            await ad.call_stop_discovery()
        except DBusError:
            pass

    if not found:
        toast("--kind", "progress", "--id", "bluetooth-pair", "--done", "--icon", "controller",
              "No controller found", "")
        toast("--kind", "alert", "--icon", "controller", "No controller found",
              "Nothing was in pairing mode. Try Pair a Controller again.")
        await manager.call_unregister_agent(AGENT_PATH)
        return 1

    path, d = found
    name = friendly(d.get("Alias") or d.get("Name"))
    log(f"pairing {d.get('Address')} ({d.get('Name')})")
    toast("--kind", "progress", "--id", "bluetooth-pair", "--icon", "controller",
          "--progress", "0.95", f"Pairing {name}", "")
    dev = await iface(bus, path, "org.bluez.Device1")
    dprops = await iface(bus, path, "org.freedesktop.DBus.Properties")
    try:
        try:
            await dev.call_pair()
        except DBusError as e:
            if "AlreadyExists" not in e.type:
                raise
        await dprops.call_set("org.bluez.Device1", "Trusted", Variant("b", True))
        await dev.call_connect()
    except DBusError as e:
        log(f"pairing failed: {e.type}: {e.text}")
        toast("--kind", "progress", "--id", "bluetooth-pair", "--done", "--icon", "controller",
              f"Couldn't pair {name}", "")
        toast("--kind", "alert", "--icon", "controller", f"Couldn't pair {name}",
              "Put it in pairing mode again and try once more.")
        return 1
    finally:
        try:
            await manager.call_unregister_agent(AGENT_PATH)
        except DBusError:
            pass

    toast("--kind", "progress", "--id", "bluetooth-pair", "--done", "--icon", "controller",
          f"{name} paired", "")
    toast("--kind", "notice", "--icon", "controller", f"{name} paired",
          "It reconnects on its own from now on.")
    return 0


async def forget(address):
    bus = await system_bus()
    objs = await managed_objects(bus)
    adapter = first_adapter(objs)
    match = [(p, d) for p, d in devices(objs, adapter) if d.get("Address", "").upper() == address.upper()]
    if not match:
        toast("--kind", "notice", "--icon", "controller", "Already forgotten",
              "That controller isn't paired any more.")
        return 0
    path, d = match[0]
    name = friendly(d.get("Alias") or d.get("Name"))
    ad = await iface(bus, adapter, "org.bluez.Adapter1")
    await ad.call_remove_device(path)
    toast("--kind", "notice", "--icon", "controller", f"{name} forgotten",
          "Pair it again from Settings to use it.")
    return 0


async def entries(folder):
    try:
        bus = await system_bus()
        objs = await managed_objects(bus)
    except Exception as e:   # no BlueZ, no bus: no pairing on this box
        log(f"no Bluetooth: {e}")
        objs = {}
    adapter = first_adapter(objs)
    write_entries(folder, plan_entries(adapter is not None, paired_controllers(objs, adapter) if adapter else []))
    return 0


def main():
    args = sys.argv[1:]
    if args[:1] == ["entries"] and len(args) == 2:
        return asyncio.run(entries(args[1]))
    if args[:1] == ["pair"] and len(args) <= 2:
        return asyncio.run(pair(int(args[1]) if len(args) == 2 else 60))
    if args[:1] == ["forget"] and len(args) == 2:
        return asyncio.run(forget(args[1]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
