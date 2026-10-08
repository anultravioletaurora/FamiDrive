# Controllers

This page records which controllers have been tried on a FamiDrive box,
how each one connects, and how it did in each place it can be used. It
works like [COMPATIBILITY.md](COMPATIBILITY.md): add results whenever you
test, and keep the old notes when a status changes.

Every result comes from the test box in COMPATIBILITY.md unless an entry
says otherwise.

The goal: if a controller exists, within reason, it should work on a
FamiDrive box and feel welcome there. Half the fun of a PC under the TV
is the range of things you can plug into it: arcade sticks, guitars,
wheels, old consoles' pads on adapters. A controller nobody has tried
yet is listed below as ❔ until someone does.

**Status:**

- ✅ **Works**: no setup beyond pairing or plugging it in.
- 🟡 **Works, with a catch**: the catch is noted.
- ❌ **Doesn't work**.
- ❔ **Untested**.
- — **Doesn't apply** (for example, Wii Remotes in Steam games).

## At a glance

| Controller | Connection | ES-DE menus | RetroArch | Dolphin (GameCube) | Dolphin (Wii) | Eden (Switch) | Steam games | Rumble | Select + Start quits |
|---|---|---|---|---|---|---|---|---|---|
| [8BitDo Ultimate 2](#8bitdo-ultimate-2-24-ghz) | 2.4 GHz dongle | ✅ | ✅ | ✅ | ✅ as a GameCube pad | ✅ (Eden and Ryujinx) | ✅ | ✅ Dolphin | ✅ |
| [8BitDo Ultimate 2](#8bitdo-ultimate-2-bluetooth) | Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Xbox Wireless Controller](#xbox-wireless-controller) | Bluetooth | ✅ | ❔ | ❔ | ❔ | ❔ | ✅ | ❔ | ❔ |
| [DualShock 4](#dualshock-4) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [DualSense](#dualsense) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Wii Remote](#wii-remote) | Bluetooth, through Dolphin | — | — | — | ✅ | — | — | ❔ | ❔ |
| [Wii Balance Board](#wii-balance-board) | Bluetooth, through Dolphin | — | — | — | ❔ | — | — | — | — |
| [GameCube controller on the official adapter](#gamecube-controllers-on-the-official-adapter) | USB adapter | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Wii guitar on a Raphnet adapter](#wii-guitar-on-a-raphnet-adapter) | USB adapter | ✅ | — | — | — | — | — | — | ❔ |
| [Xbox 360 guitar](#xbox-360-guitar) | ❔ | ❔ | — | — | — | — | — | — | ❔ |

Clone Hero results for the guitars are in their own entries below.

## Contents

- [8BitDo Ultimate 2 (2.4 GHz)](#8bitdo-ultimate-2-24-ghz)
- [8BitDo Ultimate 2 (Bluetooth)](#8bitdo-ultimate-2-bluetooth)
- [Xbox Wireless Controller](#xbox-wireless-controller)
- [DualShock 4](#dualshock-4)
- [DualSense](#dualsense)
- [Wii Remote](#wii-remote)
- [Wii Balance Board](#wii-balance-board)
- [GameCube controllers on the official adapter](#gamecube-controllers-on-the-official-adapter)
- [Wii guitar on a Raphnet adapter](#wii-guitar-on-a-raphnet-adapter)
- [Xbox 360 guitar](#xbox-360-guitar)
- [Racing wheels](#racing-wheels)
- [Typing on the TV](#typing-on-the-tv)
- [What to test](#what-to-test)

## 8BitDo Ultimate 2 (2.4 GHz)

This is the house controller, and FamiDrive knows it by name
(`knownPads."8bitdo-ultimate-2"` in `modules/famidrive/controllers.nix`).

- **Connection:**
  - With the switch in the 2.4G position, the dongle is USB `2dc8:310b`
    (X-input mode) and the kernel's `xpad` driver handles it. SDL and
    the kernel both call it "8BitDo Ultimate 2 Wireless Controller".
  - The dongle also shows up as a keyboard and a mouse (`hid-generic`).
    FamiDrive's controller tools skip those two.
  - Once, the dongle came up as `2dc8:6013`, a different mode, instead.
    Switch it back to X-input mode.
- **ES-DE menus:** ✅ No setup.
- **RetroArch:** ✅ nixpkgs' joypad autoconfig has this dongle
  (`8BitDo_Ultimate_2_Wireless_USB.cfg`).
  - Mario Party 3 (N64): the 8BitDo was picked up right away.
  - With the core's own layout, X acted as the N64's B and the right
    trigger did nothing. FamiDrive now maps N64 buttons by label and
    makes both triggers Z (`controllers.faceButtons`). The fix hasn't
    been tried on the TV yet.
- **Dolphin, GameCube:** ✅ Set on a port from Nix
  (`controllers.gamecube.ports`).
  - Face buttons go by label.
  - Played: Melee, Double Dash, Mario Party 4, Animal Crossing.
  - Rumble works.
  - Before FamiDrive set the ports, an old `Dolphin.ini` had every port
    on the Wii U adapter, so Dolphin ignored the pad.
- **Dolphin, Wii:** ✅ As a GameCube controller in a game that takes them.
  Brawl played perfectly, rumble included.
- **Eden:** ✅ Breath of the Wild and Animal Crossing: New Horizons.
  - Eden's automatic mapping swapped every face button.
  - FamiDrive rewrites this pad's bindings (by its GUID) so the buttons
    go by label.
- **Steam games:** ✅ Steam Input is off. Two at once worked in Street
  Fighter 6 and Rocket League. In Rocket League, which pad is switched on
  first doesn't decide who's player 1.
  [Need for Speed Heat](COMPATIBILITY.md#need-for-speed-heat): the right
  glyphs and strong rumble.
- **Kodi:** ✅ with FamiDrive's button map, 2026-10-06. At first Kodi saw
  the pad but had no button map for it, so it ignored the pad and kept
  offering to set it up. FamiDrive now gives every player's Kodi a map for
  it: the Xbox 360 pad's layout, which is the same under `xpad`.
- **Still to check:**
  - how the analog triggers feel for GameCube L/R
  - a pad going to sleep mid-game and waking up again
  - rumble in Steam games

## 8BitDo Ultimate 2 (Bluetooth)

❔ Untested. In Bluetooth mode the pad reports a different name, so
FamiDrive's known-pad entry (and so the Eden face-button fix and Dolphin
ports set by its short name) doesn't match it yet.

## Xbox Wireless Controller

Over Bluetooth.

- **2026-10-07, ES-DE and Steam:** ✅ It drove the menu, then
  [Titanfall 2](COMPATIBILITY.md#titanfall-2), with Steam Input off
  (FamiDrive's default). Every button did what was expected, the game
  showed Xbox glyphs, and the controller could tab to and press a
  launch dialog's OK.

- **Driver:** xpadneo, which the test box's host config turns on
  (`hardware.xpadneo.enable`). FamiDrive doesn't add it itself. Under
  xpadneo the pad reports as `045e:028e`.
- **Kodi:** ❌ at first. Kodi saw it ("Xbox Wireless Controller", 11
  buttons, 9 axes) but had no button map for it. FamiDrive now gives each
  player's Kodi one: the same buttons and first eight axes as `xpad`, plus
  xpadneo's profile switch as a ninth axis. Not yet tried that way. Rumble and the Share button are the usual reasons people add
xpadneo, so test those first.

## DualShock 4

❔ Untested. The kernel driver is `hid-playstation` on recent kernels.
SDL knows the pad. Things to note:

- the touchpad, which can show up as a mouse
- the light bar
- whether FamiDrive's controller tools need to skip its motion-sensor
  device

## DualSense

❔ Untested. Same notes as the DualShock 4, plus the adaptive triggers
and haptics, which need USB or game support over Bluetooth.

## Wii Remote

✅ Real Wii Remotes, connected to Dolphin over Bluetooth by pressing
1 + 2.

- Wii Sports bowling worked with two remotes as two players
  (`controllers.wii.remotes = [ "real" … ]`).
- **Still to check:** the remote's speaker (`controllers.wii.speaker`),
  rumble, and Bluetooth passthrough with a Wii-compatible adapter
  (`controllers.wii.bluetoothPassthrough`).

## Wii Balance Board

❔ The option exists (`controllers.wii.balanceBoard`) but there are no
results yet.

## GameCube controllers on the official adapter

The adapter is the Wii U / Switch GameCube adapter. The controllers are
the official Smash Ultimate ones.

❔ Untested. A GameCube port set to `"adapter"` passes the controller
through to Dolphin, and FamiDrive installs Dolphin's udev rules for it.
The adapter has been plugged into the test box but not used.

To test:

- the adapter's two modes: Wii U, and PC (where it acts as an ordinary
  HID gamepad)
- the menus
- other emulators, in PC mode
- rumble, which needs the adapter's second USB plug for power

- **Ryujinx (Switch):** ❌ not seen (2026-10-07). Ryujinx uses its own
  bundled SDL, which doesn't pick up the official adapter, so Smash
  Ultimate in Ryujinx can't use GameCube controllers yet. Dolphin and the
  system's SDL see it fine.

## Wii guitar on a Raphnet adapter

A Wii Les Paul on a Raphnet WUSBMote v2.2 (USB `289b:0080`). The adapter
presents the guitar as an ordinary USB gamepad.

- **ES-DE menus:** ✅ Recognized.
- **Buttons:** the frets are buttons 0–4. Buttons 6 and 7 look like strum
  or minus and plus, but that isn't confirmed.
- **Hub:** the adapter failed with "Cannot enable" on a VIA USB hub and
  worked on another hub, so the hub was the problem.
- **Clone Hero:** ✅ Bound and played on Expert, 2026-10-06. FamiDrive
  saves bindings for the whole box (`cloneHero.sharedBindings`), so one
  player binding the guitar binds it for everyone. A second player's
  Clone Hero found the guitar with no setup.
- **Quitting:** ❌ holding minus + plus doesn't quit. famidrive-quit only
  watches pads that have Select and Start buttons, and the Raphnet
  reports neither: its 16 buttons are numbered, not named. To fix:
  record which numbers minus and plus are, and give famidrive-quit a
  combo for this adapter.
- **Still to record:** which button is which, and calibration.

## Xbox 360 guitar

❔ Being tested in Clone Hero.

## Racing wheels

❔ No wheel tried yet. Games to try one with:
[DiRT Rally](COMPATIBILITY.md#dirt-rally) and
[Need for Speed Heat](COMPATIBILITY.md#need-for-speed-heat).

How a wheel is expected to work on a FamiDrive box, until one has:

- **Steering, pedals and buttons** reach games as a plain joystick on any
  wheel, with no driver needed. Racing games read wheels directly, which
  suits FamiDrive's default of Steam Input off. Under Proton, games see
  the wheel through Wine. Some games only accept wheels from their own
  list of known models.
- **Force feedback** needs a kernel driver for the wheel's maker:
  - **Logitech G29, G920, G923** and older Logitech wheels: in the
    kernel. The out-of-tree `new-lg4ff` driver adds more effects for
    the older ones.
  - **Thrustmaster** (T300RS, T248, TX and others): `hid-tmff2`, out of
    tree.
  - **Fanatec:** `hid-fanatecff`, out of tree.
  - **Direct-drive bases** that use the standard USB force-feedback
    protocol (Moza, Simucube, VRS, Cammus, ...): `hid-universal-pidff`,
    in the kernel since 6.15.

  nixpkgs packages the out-of-tree drivers, so FamiDrive can turn each
  one on for the box. That option doesn't exist yet (#58): it's worth
  adding once a wheel of that kind has been tried.
- **Rotation range, centering and other settings** are usually set with
  Oversteer, a desktop app. A TV box has no desktop, so FamiDrive would
  set them from Nix.
- **Emulators:** Dolphin can present a wheel to the GameCube as its
  steering wheel accessory, for the few games that support it. Wii
  racing games use the Wii Remote, in or out of a Wii Wheel shell.

## Steam's prompts

Steam's own dialogs over a launch (a game's EULA, a cloud save conflict,
a CD key) are made for a mouse. While one is up, the controller works as
one (`famidrive-padmouse`):

| Pad | Does |
|---|---|
| Left stick | moves the pointer |
| Right stick | scrolls |
| A | clicks |
| B | Esc |
| X / R1 | Tab (next button) |
| L1 | Shift+Tab (previous button) |
| Y | Space |
| D-pad | arrow keys |
| Start | Enter (not while Select is held: Select + Start still quits) |

It switches off once the prompt is answered, so the game gets the pad to
itself. Windows installers that run before a game (Rockstar's, the EA app)
are a different case: Proton's own helper already lets a controller move
between their buttons.

Tested on the first box: Ghost Recon Wildlands' EULA, accepted with an
8BitDo Ultimate 2 (left stick to the Accept button, then A). Steam then
went on to process the game's shaders.

## Typing on the TV

Sign-ins and search boxes are the hardest part of a box with no
keyboard. What works today:

- **On-screen keyboards:** Steam's (in Steam and in games started from
  Steam), Kodi's, and ES-DE's own.
- **A phone or another device:** most sign-ins on the box show a code to
  enter elsewhere instead of a password: Prism (Minecraft) and Jellyfin's
  Quick Connect do this. The phone apps for Steam and RomM handle a lot
  without the TV at all: installing and removing Steam games, and
  managing the library in RomM's web UI.
- **A keyboard:** any USB or Bluetooth keyboard works, including small
  ones that clip onto a controller.

## What to test

For each controller, try:

1. **Connect it.** Note the USB ID (`lsusb`), the kernel driver
   (`/sys/class/input/*/device/driver`), and the name SDL gives it.
2. **ES-DE menus,** and "Who's playing?".
3. **Holding Select + Start** in a game.
4. **One game per emulator:** RetroArch, Dolphin GameCube and Wii, Eden.
   Check that the face buttons match their labels.
5. **A Steam game,** with Steam Input off.
6. **Rumble.**
7. **Two of the same model at once.** Check that each player keeps the
   same pad.
8. **Sleep:** let it sleep mid-game, then wake it.
