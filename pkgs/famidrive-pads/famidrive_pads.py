"""famidrive-pads: bind the controllers connected right now in Dolphin and Eden.

    famidrive-pads dolphin SPEC.json
    famidrive-pads eden SPEC.json
    famidrive-pads cemu SPEC.json
    famidrive-pads sdl-mappings GAMECONTROLLERDB.txt

Run by famidrive-launch just before a GameCube, Wii or Switch game. Both
emulators bind a controller by identity (Dolphin by SDL name, Eden by
GUID and raw button numbers), so a binding made for one pad does nothing
for another. Found on the first box 2026-10-07: with the 8BitDo flat, the
Xbox controller worked in Steam and RetroArch but not in Dolphin or Eden.

Each emulator is asked about the pads through its own SDL library (the
spec names it), with the hints that emulator sets, so names, GUIDs and
raw button numbers come out the way it will see them.

Modern pads come first, GameCube controllers on the official adapter
(USB 057e:0337, one pad per controller plugged in) after them: picking up
any pad makes it player 1, and the adapter's controllers fill the next
players and ports. Decided 2026-10-07. SDL lists the adapter's first.

dolphin: each GameCube port set to "gamepad" (controllers.gamecube.ports)
gets the next connected pad, by the name and per-name index Dolphin uses
(SDL/<n>/<name>). Ports naming a model keep it. With faceButtons
"labels", each of those ports also gets A, B, X and Y from the labels SDL
gives that pad's buttons: SDL names them by place (Button S is the bottom
one), and a Nintendo-labelled pad has its B at the bottom and A on the
right. Found on the first box 2026-10-09: on a PowerA GameCube-style
controller for the Switch, A was B and X was Y. The rest stay as Nix wrote
them (SDL's standard gamepad names, the same for every pad).

eden: each connected pad becomes a player, port order, with every binding
built the way Eden's own automatic mapping builds it
(SDLDriver::GetSingleControllerMapping in Eden 0.2.1): Eden's SDL driver
asks SDL which raw button, axis or hat each Switch button is on. Face
buttons follow controllers.faceButtons: "labels" puts the Switch's A on
the pad's A, "positions" on the right-hand button, as Eden does. Players
past the last pad are disconnected. With no pad connected, nothing
changes.

cemu: the first pad becomes the Wii U GamePad (controllerProfiles/
controller0.xml), with Cemu's own default mapping for an SDL controller
(VPADController::set_default_mapping, Cemu 2.6), face buttons per
controllers.faceButtons. Cemu reads pads through SDL's game-controller
layer, so the mapping names SDL's buttons, not raw ones; the pad is named
by Cemu's uuid, <n>_<SDL GUID> (CRC kept), n counting pads of that GUID.
More players, as Wii U Pro Controllers, aren't set up yet.

sdl-mappings: prints the SDL_GAMECONTROLLERCONFIG lines, from SDL's
community database, for the pads connected now, each under the GUID the
pad has here (SDL 2's older form, as Godot 3 makes it), for games whose
own copy of the database is too old to know them. Only the connected
pads: the whole database is far over the size an environment variable
may have. Found on the first box 2026-10-09: SuperTux Party (Godot 3.2,
2021) didn't know the 8BitDo Ultimate 2.

SPEC (JSON, from Nix):
  dolphin: {"sdl": libSDL3 path, "ports": [...], "adapter": bool, "faceButtons": ..., "config": GCPadNew.ini}
  eden:    {"sdl": libSDL2 path, "faceButtons": "labels"|"positions", "config": qt-config.ini}
  cemu:    {"sdl": libSDL2 path, "faceButtons": ..., "config": controllerProfiles/controller0.xml}
"""

import ctypes
import json
import os
import sys
from pathlib import Path


# --- INI files, edited in place -------------------------------------------------

def set_ini(path, section, keys):
    """These keys set in [section] (Key = Value or Key=Value, as the file
    has them), everything else kept as it is."""
    path = Path(path)
    lines = path.read_text(errors="replace").splitlines() if path.exists() else []
    sep = "=" if any("=" in ln and " = " not in ln for ln in lines) else " = "
    left = dict(keys)
    out, inside, seen = [], False, False

    def flush():
        out.extend(f"{k}{sep}{v}" for k, v in left.items())
        left.clear()

    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if inside:
                flush()
            inside = s[1:-1] == section
            seen = seen or inside
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if inside and k in left:
            out.append(f"{k}{sep}{left.pop(k)}")
        else:
            out.append(line)
    if inside:
        flush()
    if not seen:
        out += ["", f"[{section}]"]
        flush()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n")


# --- Dolphin (SDL3) --------------------------------------------------------------

GC_ADAPTER = (0x057E, 0x0337)
# SDL 3's face buttons by place (SDL_GAMEPAD_BUTTON_SOUTH up), as Dolphin
# names them, and its SDL_GamepadButtonLabel numbers for A, B, X and Y.
PLACES = ("S", "E", "W", "N")
LABELS = {1: "A", 2: "B", 3: "X", 4: "Y"}
XBOX_LABELS = {"A": "S", "B": "E", "X": "W", "Y": "N"}


def modern_first(pads):
    """Pads with the adapter's GameCube controllers moved after the rest,
    each group in SDL's order."""
    return sorted(pads, key=lambda p: p["adapter"])


def sdl3_pads(lib, gc_adapter):
    """Connected gamepads as Dolphin names them (SDL_GetGamepadName, with
    Dolphin's hints), each with its Dolphin device string: SDL/<n>/<name>,
    n counting pads of that name in SDL's order, the order Dolphin adds
    them in."""
    sdl = ctypes.CDLL(lib)
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    for k, v in {"SDL_JOYSTICK_HIDAPI_GAMECUBE": "0" if gc_adapter else "1",
                 "SDL_JOYSTICK_ENHANCED_REPORTS": "1",
                 "SDL_JOYSTICK_HIDAPI_COMBINE_JOY_CONS": "1",
                 "SDL_JOYSTICK_HIDAPI_VERTICAL_JOY_CONS": "0"}.items():
        sdl.SDL_SetHint(k.encode(), v.encode())
    if not sdl.SDL_Init(0x200 | 0x2000):   # JOYSTICK | GAMEPAD
        return []
    try:
        sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
        sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
        sdl.SDL_GetGamepadVendorForID.restype = ctypes.c_uint16
        sdl.SDL_GetGamepadProductForID.restype = ctypes.c_uint16
        sdl.SDL_GetGamepadButtonLabelForType.argtypes = [ctypes.c_int, ctypes.c_int]
        count = ctypes.c_int(0)
        ids = sdl.SDL_GetGamepads(ctypes.byref(count))
        pads = []
        for i in range(count.value):
            name = (sdl.SDL_GetGamepadNameForID(ids[i]) or b"Unknown").decode(errors="replace")
            usb = (sdl.SDL_GetGamepadVendorForID(ids[i]), sdl.SDL_GetGamepadProductForID(ids[i]))
            nth = sum(1 for p in pads if p["name"] == name)
            kind = sdl.SDL_GetGamepadTypeForID(ids[i])
            labels = {LABELS[n]: place for b, place in enumerate(PLACES)
                      if (n := sdl.SDL_GetGamepadButtonLabelForType(kind, b)) in LABELS}
            pads.append({"name": name, "device": f"SDL/{nth}/{name}", "adapter": usb == GC_ADAPTER,
                         "labels": labels})
        sdl.SDL_free(ids)
        return pads
    finally:
        sdl.SDL_Quit()


def dolphin_devices(ports, pads):
    """{port index: Dolphin device string} for each "gamepad" port: the
    next pad, modern pads first."""
    free = [p["device"] for p in modern_first(pads)]
    return {i: free.pop(0) for i, p in enumerate(ports) if p == "gamepad" and free}


def dolphin_face(pad, face):
    """A pad's GameCube A, B, X and Y in Dolphin, by the labels on it, when
    faceButtons is "labels". A pad whose buttons SDL gives no A/B/X/Y
    labels (a PlayStation pad's are shapes) is taken as Xbox-labelled, as
    Nix writes it. With "positions", nothing: Nix's places stay."""
    if face != "labels":
        return {}
    labels = pad.get("labels") or {}
    if set(labels) != set(XBOX_LABELS):
        labels = XBOX_LABELS
    return {f"Buttons/{k}": f"`Button {labels[k]}`" for k in ("A", "B", "X", "Y")}


def cmd_dolphin(spec):
    pads = sdl3_pads(spec["sdl"], spec.get("adapter", False))
    by_device = {p["device"]: p for p in pads}
    for i, device in dolphin_devices(spec["ports"], pads).items():
        face = dolphin_face(by_device[device], spec.get("faceButtons", "labels"))
        set_ini(spec["config"], f"GCPad{i + 1}", {"Device": device, **face})
    return 0


# --- Eden (SDL2) ----------------------------------------------------------------

# SDL2's GameController enums.
BUTTON = {"a": 0, "b": 1, "x": 2, "y": 3, "back": 4, "guide": 5, "start": 6,
          "leftstick": 7, "rightstick": 8, "leftshoulder": 9, "rightshoulder": 10,
          "dpup": 11, "dpdown": 12, "dpleft": 13, "dpright": 14, "misc1": 15}
AXIS = {"leftx": 0, "lefty": 1, "rightx": 2, "righty": 3, "lefttrigger": 4, "righttrigger": 5}
HAT = {1: "up", 2: "right", 4: "down", 8: "left"}


class _Hat(ctypes.Structure):
    _fields_ = [("hat", ctypes.c_int), ("hat_mask", ctypes.c_int)]


class _Value(ctypes.Union):
    _fields_ = [("button", ctypes.c_int), ("axis", ctypes.c_int), ("hat", _Hat)]


class _Bind(ctypes.Structure):
    _fields_ = [("bindType", ctypes.c_int), ("value", _Value)]


class _Guid(ctypes.Structure):
    _fields_ = [("data", ctypes.c_uint8 * 16)]


def switch_buttons(face):
    """Eden's button names -> SDL's, Eden's own default (GetDefaultButtonBinding)
    with the face buttons by label or by position."""
    by_label = face == "labels"
    return {
        "button_a": "a" if by_label else "b", "button_b": "b" if by_label else "a",
        "button_x": "x" if by_label else "y", "button_y": "y" if by_label else "x",
        "button_lstick": "leftstick", "button_rstick": "rightstick",
        "button_l": "leftshoulder", "button_r": "rightshoulder",
        "button_plus": "start", "button_minus": "back",
        "button_dleft": "dpleft", "button_dup": "dpup", "button_dright": "dpright", "button_ddown": "dpdown",
        "button_slleft": "leftshoulder", "button_srleft": "rightshoulder",
        "button_slright": "leftshoulder", "button_srright": "rightshoulder",
        "button_home": "guide", "button_screenshot": "misc1",
    }


def eden_binding(port, guid, bind):
    """One binding in Eden's own format (BuildParamPackageForBinding), from
    an SDL bind: (type, number, hat mask). None for an unbound button."""
    kind, n, mask = bind
    head = f"engine:sdl,port:{port},guid:{guid},"
    if kind == 1:
        return head + f"button:{n}"
    if kind == 2:
        return head + f"axis:{n},threshold:0.500000,invert:+"
    if kind == 3 and mask in HAT:
        return head + f"hat:{n},direction:{HAT[mask]}"
    return None


def eden_stick(port, guid, x, y):
    return (f"engine:sdl,port:{port},guid:{guid},axis_x:{x},axis_y:{y},"
            "offset_x:-0.000000,offset_y:0.000000,invert_x:+,invert_y:+,deadzone:0.150000")


def sdl2_pads(lib):
    """Each connected game controller: its Eden GUID (SDL's, with the name
    CRC zeroed, as Eden's GetGUID does), its Eden port (its place among
    pads with that GUID) and SDL's bind for every button and axis. With
    Eden's hints: no HIDAPI Xbox driver, no button labels."""
    sdl = ctypes.CDLL(lib)
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    for k, v in {"SDL_JOYSTICK_RAWINPUT": "0", "SDL_ACCELEROMETER_AS_JOYSTICK": "0",
                 "SDL_JOYSTICK_HIDAPI_PS4_RUMBLE": "1", "SDL_JOYSTICK_HIDAPI_PS5_RUMBLE": "1",
                 "SDL_JOYSTICK_HIDAPI_JOY_CONS": "0", "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
                 "SDL_GAMECONTROLLER_USE_BUTTON_LABELS": "0", "SDL_JOYSTICK_HIDAPI_XBOX": "0"}.items():
        sdl.SDL_SetHint(k.encode(), v.encode())
    if sdl.SDL_Init(0x200 | 0x2000) < 0:   # JOYSTICK | GAMECONTROLLER
        return []
    sdl.SDL_JoystickGetDeviceGUID.restype = _Guid
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    sdl.SDL_GameControllerGetBindForButton.restype = _Bind
    sdl.SDL_GameControllerGetBindForButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerGetBindForAxis.restype = _Bind
    sdl.SDL_GameControllerGetBindForAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
    sdl.SDL_JoystickGetDeviceVendor.restype = ctypes.c_uint16
    sdl.SDL_JoystickGetDeviceProduct.restype = ctypes.c_uint16
    pads = []
    try:
        for i in range(sdl.SDL_NumJoysticks()):
            if not sdl.SDL_IsGameController(i):
                continue
            raw = bytearray(sdl.SDL_JoystickGetDeviceGUID(i).data)
            raw[2:4] = b"\0\0"   # Eden clears the name CRC
            guid = raw.hex()
            gc = sdl.SDL_GameControllerOpen(i)
            if not gc:
                continue

            def b(x):
                return (x.bindType, x.value.hat.hat if x.bindType == 3 else x.value.button, x.value.hat.hat_mask)
            binds = {k: b(sdl.SDL_GameControllerGetBindForButton(gc, v)) for k, v in BUTTON.items()}
            binds.update({k: b(sdl.SDL_GameControllerGetBindForAxis(gc, v)) for k, v in AXIS.items()})
            sdl.SDL_GameControllerClose(gc)
            port = sum(1 for p in pads if p["guid"] == guid)
            usb = (sdl.SDL_JoystickGetDeviceVendor(i), sdl.SDL_JoystickGetDeviceProduct(i))
            pads.append({"guid": guid, "port": port, "binds": binds, "adapter": usb == GC_ADAPTER})
    finally:
        sdl.SDL_Quit()
    return modern_first(pads)


def eden_keys(pads, face):
    """qt-config.ini's [Controls] keys for these pads, player 1 first.
    Every key with its \\default=false, without which Eden ignores it."""
    keys = {}

    def put(k, v):
        keys[k + "\\default"] = "false"
        keys[k] = v

    names = switch_buttons(face)
    for n, pad in enumerate(pads[:8]):
        p, g, binds = f"player_{n}_", pad["guid"], pad["binds"]
        put(p + "type", "0")              # Pro Controller
        put(p + "connected", "true")
        for key, sdl_name in names.items():
            bound = eden_binding(pad["port"], g, binds[sdl_name])
            put(p + key, f'"{bound}"' if bound else "[empty]")
        for key, axis in (("button_zl", "lefttrigger"), ("button_zr", "righttrigger")):
            bound = eden_binding(pad["port"], g, binds[axis])
            put(p + key, f'"{bound}"' if bound else "[empty]")
        lx, ly, rx, ry = (binds[a] for a in ("leftx", "lefty", "rightx", "righty"))
        if lx[0] == 2 and ly[0] == 2:
            put(p + "lstick", f'"{eden_stick(pad["port"], g, lx[1], ly[1])}"')
        if rx[0] == 2 and ry[0] == 2:
            put(p + "rstick", f'"{eden_stick(pad["port"], g, rx[1], ry[1])}"')
    for n in range(len(pads), 8):
        if n:
            put(f"player_{n}_connected", "false")
    return keys


def cmd_eden(spec):
    pads = sdl2_pads(spec["sdl"])
    if not pads:
        return 0   # no pad now: whatever was bound stays
    set_ini(os.path.expanduser(spec["config"]), "Controls", eden_keys(pads, spec.get("faceButtons", "labels")))
    return 0


# --- Cemu (SDL2) ----------------------------------------------------------------

# The Wii U GamePad's buttons (VPADController::ButtonId) and Cemu's controller
# inputs (Buttons2): kButton0-31 are SDL's game-controller buttons by number.
VPAD = {"A": 1, "B": 2, "X": 3, "Y": 4, "L": 5, "R": 6, "ZL": 7, "ZR": 8, "Plus": 9, "Minus": 10,
        "Up": 11, "Down": 12, "Left": 13, "Right": 14, "StickL": 15, "StickR": 16,
        "StickL_Up": 17, "StickL_Down": 18, "StickL_Left": 19, "StickL_Right": 20,
        "StickR_Up": 21, "StickR_Down": 22, "StickR_Left": 23, "StickR_Right": 24, "Home": 27}
CEMU = {"AxisXP": 38, "AxisYP": 39, "RotationXP": 40, "RotationYP": 41, "TriggerXP": 42, "TriggerYP": 43,
        "AxisXN": 44, "AxisYN": 45, "RotationXN": 46, "RotationYN": 47}


def cemu_mapping(face):
    """{GamePad button: Cemu input}, Cemu's default for an SDL controller,
    whose face buttons go by position (A on SDL's B, the right-hand
    button); "labels" puts them on the buttons printed A, B, X, Y."""
    by_label = face == "labels"
    m = {"A": 0 if by_label else 1, "B": 1 if by_label else 0, "X": 2 if by_label else 3, "Y": 3 if by_label else 2,
         "L": 9, "R": 10, "ZL": CEMU["TriggerXP"], "ZR": CEMU["TriggerYP"], "Plus": 6, "Minus": 4,
         "Up": 11, "Down": 12, "Left": 13, "Right": 14, "StickL": 7, "StickR": 8,
         "StickL_Up": CEMU["AxisYN"], "StickL_Down": CEMU["AxisYP"],
         "StickL_Left": CEMU["AxisXN"], "StickL_Right": CEMU["AxisXP"],
         "StickR_Up": CEMU["RotationYN"], "StickR_Down": CEMU["RotationYP"],
         "StickR_Left": CEMU["RotationXN"], "StickR_Right": CEMU["RotationXP"], "Home": 5}
    return {VPAD[k]: v for k, v in m.items()}


def cemu_profile(pad, face):
    """A controllerProfiles XML for the GamePad on this pad, as Cemu saves one."""
    from xml.sax.saxutils import escape
    entries = "".join(f"\t\t\t<entry>\n\t\t\t\t<mapping>{k}</mapping>\n\t\t\t\t<button>{v}</button>\n\t\t\t</entry>\n"
                      for k, v in sorted(cemu_mapping(face).items()))
    dz = "\t\t\t<deadzone>0.15</deadzone>\n\t\t\t<range>1</range>\n"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<emulated_controller>\n\t<type>Wii U GamePad</type>\n'
            f"\t<controller>\n\t\t<api>SDLController</api>\n\t\t<uuid>{pad['uuid']}</uuid>\n"
            f"\t\t<display_name>{escape(pad['name'])}</display_name>\n\t\t<rumble>1</rumble>\n"
            f"\t\t<axis>\n{dz}\t\t</axis>\n\t\t<rotation>\n{dz}\t\t</rotation>\n\t\t<trigger>\n{dz}\t\t</trigger>\n"
            f"\t\t<mappings>\n{entries}\t\t</mappings>\n\t</controller>\n</emulated_controller>\n")


def cemu_pads(lib):
    """Connected game controllers as Cemu lists them (SDLControllerProvider,
    with its hints): uuid <n>_<SDL GUID>, SDL's game-controller name."""
    sdl = ctypes.CDLL(lib)
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    for k in ("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "SDL_JOYSTICK_HIDAPI_PS4", "SDL_JOYSTICK_HIDAPI_PS5",
              "SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "SDL_JOYSTICK_HIDAPI_GAMECUBE",
              "SDL_JOYSTICK_HIDAPI_SWITCH", "SDL_JOYSTICK_HIDAPI_JOY_CONS", "SDL_JOYSTICK_HIDAPI_STADIA",
              "SDL_JOYSTICK_HIDAPI_STEAM", "SDL_JOYSTICK_HIDAPI_LUNA"):
        sdl.SDL_SetHint(k.encode(), b"1")
    if sdl.SDL_Init(0x200 | 0x2000) < 0:
        return []
    sdl.SDL_JoystickGetDeviceGUID.restype = _Guid
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    sdl.SDL_GameControllerName.restype = ctypes.c_char_p
    sdl.SDL_GameControllerName.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
    sdl.SDL_JoystickGetDeviceVendor.restype = ctypes.c_uint16
    sdl.SDL_JoystickGetDeviceProduct.restype = ctypes.c_uint16
    pads, seen = [], {}
    try:
        for i in range(sdl.SDL_NumJoysticks()):
            if sdl.SDL_JoystickGetDeviceType(i) != 1:   # SDL_JOYSTICK_TYPE_GAMECONTROLLER
                continue
            guid = bytes(sdl.SDL_JoystickGetDeviceGUID(i).data).hex()
            n = seen.get(guid, 0)
            seen[guid] = n + 1
            gc = sdl.SDL_GameControllerOpen(i)
            name = (sdl.SDL_GameControllerName(gc) or b"").decode(errors="replace") if gc else ""
            if gc:
                sdl.SDL_GameControllerClose(gc)
            usb = (sdl.SDL_JoystickGetDeviceVendor(i), sdl.SDL_JoystickGetDeviceProduct(i))
            pads.append({"uuid": f"{n}_{guid}", "name": name or f"Controller {len(pads) + 1}", "adapter": usb == GC_ADAPTER})
    finally:
        sdl.SDL_Quit()
    return modern_first(pads)


def cmd_cemu(spec):
    pads = cemu_pads(spec["sdl"])
    if not pads:
        return 0
    path = Path(spec["config"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cemu_profile(pads[0], spec.get("faceButtons", "labels")))
    return 0


# --- SDL mappings for old games ------------------------------------------------

def connected_joysticks(devices_text):
    """(bus, vendor, product, version) of each joystick in
    /proc/bus/input/devices, as hex strings, in order, once each."""
    found = []
    for block in devices_text.split("\n\n"):
        ids = handlers = None
        for line in block.splitlines():
            if line.startswith("I:"):
                ids = dict(kv.split("=", 1) for kv in line[2:].split())
            elif line.startswith("H:"):
                handlers = line.split("=", 1)[1].split()
        if ids and handlers and any(h.startswith("js") for h in handlers):
            key = tuple(ids.get(k, "0").lower().zfill(4) for k in ("Bus", "Vendor", "Product", "Version"))
            if key not in found:
                found.append(key)
    return found


def le16(h):
    return h[2:4] + h[0:2]


def legacy_guid(bus, vendor, product, version):
    """SDL 2's GUID for an evdev pad before the name CRC was added: bus,
    vendor, product and version, little-endian, each followed by zeroes."""
    return "".join(le16(x) + "0000" for x in (bus, vendor, product, version))


def sdl_mappings(db_text, joysticks):
    """The database's Linux line for each joystick, under its GUID here:
    the same version if there's one, else any with that vendor and product."""
    lines = [line.strip() for line in db_text.splitlines()
             if "platform:Linux" in line and len(line.split(",", 1)[0]) == 32 and not line.startswith("#")]
    out = []
    for bus, vendor, product, version in joysticks:
        guid = legacy_guid(bus, vendor, product, version)
        same = [line for line in lines if line[:20] == guid[:20]]
        best = [line for line in same if line[:32] == guid] or same
        if best:
            out.append(guid + best[0][32:])
    return out


def cmd_sdl_mappings(db, devices="/proc/bus/input/devices"):
    print("\n".join(sdl_mappings(Path(db).read_text(errors="replace"),
                                 connected_joysticks(Path(devices).read_text(errors="replace")))))
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "sdl-mappings":
        sys.exit(cmd_sdl_mappings(sys.argv[2]))
    if len(sys.argv) != 3 or sys.argv[1] not in ("dolphin", "eden", "cemu"):
        sys.exit(__doc__)
    spec = json.loads(Path(sys.argv[2]).read_text() if os.path.exists(sys.argv[2]) else sys.argv[2])
    spec["config"] = os.path.expanduser(spec["config"])
    sys.exit({"dolphin": cmd_dolphin, "eden": cmd_eden, "cemu": cmd_cemu}[sys.argv[1]](spec))


if __name__ == "__main__":
    main()
