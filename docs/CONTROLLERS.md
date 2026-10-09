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
| [8BitDo Ultimate 2C](#8bitdo-ultimate-2c) | 2.4 GHz dongle / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [8BitDo Pro 2 and Pro 3](#8bitdo-pro-2-and-pro-3) | Bluetooth / 2.4 GHz dongle (Pro 3) | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [8BitDo Arcade Stick](#8bitdo-arcade-stick) | 2.4 GHz dongle / Bluetooth / USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [8BitDo Ultimate (first model)](#8bitdo-ultimate-first-model) | USB / 2.4 GHz dongle / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [ATK AXE Pro](#atk-axe-pro) | 2.4 GHz dongle / Bluetooth / USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Logitech gamepads](#logitech-gamepads) | USB (F310) / 2.4 GHz dongle (F710) | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Xbox Wireless Controller](#xbox-wireless-controller) | Bluetooth | ✅ | ❔ | ❔ | ❔ | ❔ | ✅ | ❔ | ❔ |
| [Xbox 360 controller, wired](#xbox-360-controller-wired) | USB | ✅ | ❔ | ✅ | ❔ | ❔ | ❔ | ❔ | ✅ |
| [Xbox One controller, wired](#xbox-one-controller-wired) | USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Original Xbox controller (Duke)](#original-xbox-controller-duke) | Xbox-to-USB cable | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [DualShock 4](#dualshock-4) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Razer Raiju Tournament Edition](#razer-raiju) | USB / Bluetooth | ✅ | ❔ | ✅ | ❔ | ❔ | ❔ | ❔ | ✅ |
| [PS3 Sixaxis / DualShock 3](#ps3-sixaxis--dualshock-3) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [PS2 controllers on a USB adapter](#ps2-controllers-on-a-usb-adapter) | USB adapter | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [DualSense](#dualsense) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Switch Pro Controller](#switch-pro-controller) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Joy-Cons](#joy-cons) | Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Switch 2 GameCube controller](#switch-2-gamecube-controller) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [PowerA GameCube-style controller for Switch](#powera-gamecube-style-controller-for-switch) | USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Wii U Pro Controller](#wii-u-pro-controller) | Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Wii Classic Controller Pro](#wii-classic-controller-pro) | Through a Wii Remote | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Wii U GamePad](#wii-u-gamepad) | Chocolate USB adapter | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Google Stadia controller](#google-stadia-controller) | USB / Bluetooth | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Steam Controller (2015)](#steam-controller-2015) | USB dongle / USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Steam Controller (2026)](#steam-controller-2026) | Wireless puck / USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Steam Deck](#steam-deck) | Steam Remote Play, over the network | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [USB NES and SNES pads](#usb-nes-and-snes-pads) | USB | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [SNES controller with a mod kit](#snes-controller-with-a-mod-kit) | Depends on the kit | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [NES and SNES Classic controllers](#nes-and-snes-classic-controllers) | USB adapter / through a Wii Remote | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [Meta Quest Touch Plus controllers](#meta-quest-touch-plus-controllers) | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| [NES Zapper](#nes-zapper) | — | ❌ | ❌ | — | — | — | — | — | — |
| [Wii Remote](#wii-remote) | Bluetooth, through Dolphin | — | — | — | ✅ | — | — | ❔ | ❔ |
| [Wii MotionPlus](#wii-motionplus) | Through a Wii Remote | — | — | — | ❔ | — | — | — | — |
| [Wii Balance Board](#wii-balance-board) | Bluetooth, through Dolphin | — | — | — | ❔ | — | — | — | — |
| [GameCube controller on the official adapter](#gamecube-controllers-on-the-official-adapter) | USB adapter | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ | ❔ |
| [DK Bongos](#dk-bongos) | Official GameCube adapter | — | — | ❌ not yet (#131) | — | — | — | — | ❌ no Select |
| [Wii guitar on a Raphnet adapter](#wii-guitar-on-a-raphnet-adapter) | USB adapter | ✅ | — | — | — | — | — | — | ❔ |
| [Xbox 360 guitar](#xbox-360-guitar) | ❔ | ❔ | — | — | — | — | — | — | ❔ |

Clone Hero results for the guitars are in their own entries below.

## Contents

- [8BitDo Ultimate 2 (2.4 GHz)](#8bitdo-ultimate-2-24-ghz)
- [8BitDo Ultimate 2 (Bluetooth)](#8bitdo-ultimate-2-bluetooth)
- [8BitDo Ultimate 2C](#8bitdo-ultimate-2c)
- [8BitDo Pro 2 and Pro 3](#8bitdo-pro-2-and-pro-3)
- [8BitDo Arcade Stick](#8bitdo-arcade-stick)
- [8BitDo Ultimate (first model)](#8bitdo-ultimate-first-model)
- [ATK AXE Pro](#atk-axe-pro)
- [Logitech gamepads](#logitech-gamepads)
- [Xbox Wireless Controller](#xbox-wireless-controller)
- [Xbox 360 controller, wired](#xbox-360-controller-wired)
- [Xbox One controller, wired](#xbox-one-controller-wired)
- [Original Xbox controller (Duke)](#original-xbox-controller-duke)
- [DualShock 4](#dualshock-4)
- [Razer Raiju](#razer-raiju)
- [PS3 Sixaxis / DualShock 3](#ps3-sixaxis--dualshock-3)
- [PS2 controllers on a USB adapter](#ps2-controllers-on-a-usb-adapter)
- [DualSense](#dualsense)
- [Switch Pro Controller](#switch-pro-controller)
- [Joy-Cons](#joy-cons)
- [Switch 2 GameCube controller](#switch-2-gamecube-controller)
- [PowerA GameCube-style controller for Switch](#powera-gamecube-style-controller-for-switch)
- [Wii U Pro Controller](#wii-u-pro-controller)
- [Wii Classic Controller Pro](#wii-classic-controller-pro)
- [Wii U GamePad](#wii-u-gamepad)
- [Google Stadia controller](#google-stadia-controller)
- [Steam Controller (2015)](#steam-controller-2015)
- [Steam Controller (2026)](#steam-controller-2026)
- [Steam Deck](#steam-deck)
- [USB NES and SNES pads](#usb-nes-and-snes-pads)
- [SNES controller with a mod kit](#snes-controller-with-a-mod-kit)
- [NES and SNES Classic controllers](#nes-and-snes-classic-controllers)
- [Meta Quest Touch Plus controllers](#meta-quest-touch-plus-controllers)
- [NES Zapper](#nes-zapper)
- [Wii Remote](#wii-remote)
- [Wii MotionPlus](#wii-motionplus)
- [Wii Balance Board](#wii-balance-board)
- [GameCube controllers on the official adapter](#gamecube-controllers-on-the-official-adapter)
- [DK Bongos](#dk-bongos)
- [Wii guitar on a Raphnet adapter](#wii-guitar-on-a-raphnet-adapter)
- [Xbox 360 guitar](#xbox-360-guitar)
- [Fight sticks](#fight-sticks)
- [Racing wheels](#racing-wheels)
- [Pen tablets](#pen-tablets)
- [Flight sticks and throttles](#flight-sticks-and-throttles)
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

## 8BitDo Ultimate 2C

❔ Untested, in either version (2.4 GHz or Bluetooth). The 2.4 GHz
dongle is expected to work like the
[Ultimate 2's](#8bitdo-ultimate-2-24-ghz), under `xpad`, but it has its
own USB ID and name, so FamiDrive's known-pad entry for the Ultimate 2
doesn't cover it. Record the USB ID and the name SDL gives it.

## 8BitDo Pro 2 and Pro 3

❔ Untested. The Pro 2 is Bluetooth only; the Pro 3 adds a 2.4 GHz
dongle. Both have a mode switch on the back: X (XInput) is the one to
try first. The Switch mode presents a Switch Pro Controller instead,
whose button layout is swapped from the labels on an Xbox-style pad.

## 8BitDo Ultimate (first model)

❔ Untested. The Ultimate from before the Ultimate 2 came in three
versions: wired, 2.4 GHz (with a charging dock), and Bluetooth (which
also has a 2.4 GHz dongle). Over the dongle or a cable it's expected to
run under `xpad` like the [Ultimate 2](#8bitdo-ultimate-2-24-ghz), but
with its own USB ID and name. Record both, and which version it is.

## 8BitDo Arcade Stick

❔ Untested. 8BitDo's fight stick, over its 2.4 GHz dongle, Bluetooth or a
USB cable. Its mode switch picks X (XInput), D (DirectInput) or Switch.
In X mode it's expected to run under `xpad` like the
[Ultimate 2](#8bitdo-ultimate-2-24-ghz), with its own USB ID and name.
See [Fight sticks](#fight-sticks) for what to check on any stick.

## ATK AXE Pro

❔ Untested. ATK's wireless pad, over its 2.4 GHz dongle, Bluetooth or a
USB-C cable, with Hall-effect sticks and a gyro. It's sold for PC and the
Switch, so like most such pads it's expected to have a PC (XInput) mode
that runs under `xpad`, and a Switch mode that looks like a Switch Pro
Controller (`hid-nintendo`, gyro included, but Nintendo's button
layout). Record which mode it's in, the USB ID and the name SDL gives
it. Its gyro would matter for motion controls in Switch games
([#133](https://github.com/anultravioletaurora/FamiDrive/issues/133)).

## Logitech gamepads

❔ Untested. Logitech's current pads are the F310 (USB) and the F710
(2.4 GHz dongle). Each has an X/D switch: X (XInput) runs under `xpad`
like an Xbox 360 pad, and is the one to use. D (DirectInput) is a
generic HID pad with numbered buttons.

## Xbox Wireless Controller

Over Bluetooth. The Xbox Series X|S controller and the later Xbox One
controllers (the ones with Bluetooth) are both this pad as far as Linux
is concerned. They report the same name, and both run under xpadneo.
Which of the two the result below was from isn't recorded.

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

- **Older Xbox One controllers** (the first models, without the
  plastic around the Xbox button joined to the face) have no Bluetooth.
  They work over USB as an [Xbox One controller,
  wired](#xbox-one-controller-wired), or wirelessly through Microsoft's
  Xbox Wireless Adapter. The adapter needs the out-of-tree `xone`
  driver: turn it on with
  [`famidrive.controllers.xboxWirelessAdapter`](USAGE.md#famidrivecontrollersxboxwirelessadapter).
  Untested.

## Xbox 360 controller, wired

The kernel's `xpad` driver handles it (`045e:028e`, "Microsoft X-Box
360 pad"), and almost every PC game and emulator expects its layout.
Kodi's map for the 8BitDo Ultimate 2 is this pad's layout.

- **2026-10-08, a generic third-party pad on the second box:** ✅ The
  toasts came up, it drove ES-DE, played a whole Grand Prix in
  [Mario Kart: Double Dash!!](COMPATIBILITY.md#mario-kart-double-dash) in Dolphin, and
  Select + Start quit the game. No setup.

## Xbox One controller, wired

❔ Untested. Licensed wired pads use the Xbox One protocol, which
`xpad` also handles. Check its USB ID and the name SDL gives it, since
third-party pads each have their own.

- **2026-10-08, Afterglow Prismatic (PDP, `0e6f:0139`):** ❔ `xpad`
  took it and ES-DE added it, but it didn't respond, and it kept
  dropping off USB and coming back every few seconds (`error -71`).
  This pad had been unreliable before, so it's probably the pad, not
  FamiDrive. Needs another Xbox One pad to settle it.

## Original Xbox controller (Duke)

❔ Untested. The original Xbox's port is USB with a different plug, so
the pad needs an Xbox-to-USB cable or adapter, not a driver. The
kernel's `xpad` driver knows the Duke and the later Controller S. Its
face buttons and black and white buttons are pressure-sensitive; games
see them as plain buttons. Record the name SDL gives it, and whether
the black and white buttons come through.

## DualShock 4

❔ Untested. The kernel driver is `hid-playstation` on recent kernels.
SDL knows the pad. Things to note:

- the touchpad, which can show up as a mouse
- the light bar
- whether FamiDrive's controller tools need to skip its motion-sensor
  device

## Razer Raiju

The Raiju Tournament Edition, Razer's PS4-style pad, over a USB
cable. It also has Bluetooth, untested.

- **2026-10-08, ES-DE:** ✅ On the second box, FamiDrive's toast
  announced it when it was plugged in, and it drove ES-DE's menus.
- **USB ID** `1532:1007`. The kernel names it "Razer Razer Raiju
  Tournament Edition Wired".
- **2026-10-08, Dolphin (GameCube):** ✅ It played Mario Party 4
  Deluxe, then stopped responding in the middle of the game, until it
  was unplugged and plugged back in. Not yet known why.
- **Select + Start:** ❌ at first. The kernel has no driver of its own
  for it (it's `hid-generic`), so its buttons get names in order, and
  "Select" and "Start" were the stick clicks. famidrive-quit now finds
  Share and Options through SDL's controller database.
- **2026-10-09, Select + Start:** ✅ Share + Options closed the Mii
  Channel on the second box.
- **Still to record:** the name SDL gives it, and how it does in other
  emulators and Steam games. The other Raijus (the original, Ultimate and Mobile)
  are untested.

## PS3 Sixaxis / DualShock 3

❔ Untested. The driver is `hid-sony`.

- **USB:** expected to work once plugged in.
- **Bluetooth:** pairing is unusual. Plug it in by USB once with
  Bluetooth on, then accept it in `bluetoothctl` (BlueZ's `sixaxis`
  plugin handles the rest). Unplug it and press the PS button.
- **To note:** its motion sensors show up as a separate input device,
  like the DualShock 4's.

## PS2 controllers on a USB adapter

❔ Untested. A PS2 pad needs a PS2-to-USB adapter, and the adapter
decides how it works:

- **Cheap two-port adapters** often show up as one device with two
  pads in it, with numbered buttons and the D-pad as an axis. Some only
  report the sticks while the pad's Analog light is on.
- **Raphnet's adapters** present each pad cleanly and keep the
  pressure-sensitive buttons for PCSX2.
- **Quitting:** with numbered buttons, famidrive-quit may not see
  Select and Start, as with the [USB NES and SNES
  pads](#usb-nes-and-snes-pads).

Record the adapter's USB ID, and whether both ports show up.

## DualSense

❔ Untested. Same notes as the DualShock 4, plus the adaptive triggers
and haptics, which need USB or game support over Bluetooth.

## Switch Pro Controller

❔ Untested. The driver is `hid-nintendo`, over USB or Bluetooth.

- **Face buttons:** Nintendo's A and B are where an Xbox pad has B and
  A. Check that each emulator and Steam game goes by label
  (`controllers.faceButtons`).
- **Joy-Cons:** see [Joy-Cons](#joy-cons).

## Joy-Cons

❔ Untested, and they need Bluetooth (the second box has none). The plan
for them is [#133](https://github.com/anultravioletaurora/FamiDrive/issues/133).

- **In Switch games:** Eden has its own Joy-Con driver, on by default,
  that talks to them directly: each Joy-Con is its own controller, with
  motion, HD rumble and amiibo (NFC). That's what Super Mario Party (one
  sideways Joy-Con each) and motion games like Super Mario Odyssey want.
- **Everywhere else** (ES-DE, RetroArch, Dolphin, Steam, Select +
  Start): the kernel's `hid-nintendo` sees each Joy-Con as its own
  device. `joycond` would make L + R across two Joy-Cons one controller,
  and SL + SR on one a sideways pad. FamiDrive doesn't turn joycond on
  yet.
- **BetterJoy** is for Windows only, and not needed here: on Linux the
  kernel driver, joycond, SDL, Steam Input and Eden's driver cover what
  it does.
- **An ordinary pad in a Joy-Con game:** Eden makes it a sideways
  Joy-Con with the controls turned 90°. See
  [Super Mario Party](COMPATIBILITY.md#super-mario-party).

## Switch 2 GameCube controller

❔ Untested. The Nintendo Switch Online GameCube controller for the
Switch 2. Linux support for Switch 2 controllers is new: SDL 3 talks to
them over USB, and kernel and Bluetooth support was still in progress as of
2026-10. Try USB first, and record the kernel version.

## PowerA GameCube-style controller for Switch

❔ Untested. A wired pad shaped like a GameCube controller that speaks
the Switch's wired-pad protocol, so it's expected to show up as a
generic Switch controller rather than a GameCube one. Check whether
Dolphin can use it as a GameCube pad, and how its triggers read (they're
digital on most of these).

## Wii U Pro Controller

❔ Untested. The driver is `hid-wiimote`, over Bluetooth. Pair it like
any other Bluetooth pad (press the sync button underneath).

## Wii Classic Controller Pro

❔ Untested. It plugs into a Wii Remote, so it connects however the
remote does:

- **In Dolphin (Wii):** the remote connects to Dolphin directly, and
  the Classic Controller Pro is the game's extension. Check games that
  use it (Mario Kart Wii, Smash Bros. Brawl).
- **Everywhere else:** paired with the box itself, `hid-wiimote` shows
  the extension as its own pad. Then it could be a general controller,
  but a remote can't be paired with the box and with Dolphin at once.

## Wii U GamePad

❔ Not possible yet: it needs Chocolate, a USB adapter that hasn't
shipped. Support for it is planned in
[#127](https://github.com/anultravioletaurora/FamiDrive/issues/127),
Cemu's second screen included.

## Google Stadia controller

❔ Untested. Over USB it's a standard HID gamepad that SDL knows. For
Bluetooth, it needs the Bluetooth mode Google released before Stadia
shut down; once switched over, it pairs like any other pad.

## Steam Controller (2015)

❔ Untested. The USB dongle (or a cable) and the kernel's `hid-steam`
driver.

- Without Steam running, the pad starts out as a mouse and keyboard
  ("lizard mode"). `hid-steam` also offers it as a gamepad.
- Steam turns the gamepad into whatever its Steam Input config says.
  With Steam Input off (FamiDrive's default), how it behaves in Steam
  games needs checking.
- Its trackpads have no stick equivalent outside Steam.

## Steam Controller (2026)

❔ Untested. Valve's new controller and its wireless puck. Linux support
outside Steam is new. Check what the kernel and SDL see with Steam
closed, and with Steam running.

## Steam Deck

❔ Untested. A Deck isn't a controller over USB or Bluetooth, but it
can be one over the network:

- **Steam Remote Play** from the Deck to the box streams a Steam game
  to the Deck, and the Deck's controls reach the game on the box.
- **Remote Play Together** lets the Deck join a game running on the box
  as another player, if the game supports it.

Both need Steam running on the box, and neither reaches ES-DE or the
emulators. Check what the box's Steam allows over its network.

## USB NES and SNES pads

❔ Untested. Generic USB pads in the shape of an NES or SNES controller.

- They're plain HID gamepads with numbered buttons, so names vary and the
  D-pad is often an axis.
- RetroArch has autoconfigs for many common ones, by USB ID.
- **Quitting:** their buttons are numbered, not named, so famidrive-quit
  looks them up in SDL's community controller database to find Select
  and Start. A pad that isn't in it can't quit with Select + Start yet:
  record which numbers they are.

## SNES controller with a mod kit

❔ Untested. An original SNES pad rebuilt with a mod kit inside. It
behaves like whatever the kit presents: 8BitDo's Bluetooth kit looks
like an 8BitDo pad (with its own mode switch), and USB kits are usually
plain HID pads like the [USB NES and SNES pads](#usb-nes-and-snes-pads).
Record which kit it is and the name SDL gives it.

## NES and SNES Classic controllers

❔ Untested. The NES Classic and SNES Classic pads have the Wii's
extension plug, so they need one of:

- **A USB adapter** (Mayflash, Raphnet, 8BitDo's Retro Receiver for the
  Classics, and others). Each presents them differently: record which
  adapter, and its USB ID.
- **A Wii Remote:** in Dolphin they act as a Classic Controller. Paired
  with the box, `hid-wiimote` may show them as their own pad. See the
  [Wii Classic Controller Pro](#wii-classic-controller-pro).

The NES pad has only A, B, Select and Start, so it's a pad for NES
games. ES-DE's menus need more buttons than it has.

## Meta Quest Touch Plus controllers

❌ Not usable. They connect only to their Quest headset, not to a PC
on their own. They'd work along with the headset, once FamiDrive
supports VR ([#128](https://github.com/anultravioletaurora/FamiDrive/issues/128)).

## NES Zapper

❌ Doesn't work, and can't without changes. The Zapper senses the light
of a CRT's picture as it's drawn, which an LCD or OLED TV doesn't
produce, and it has no USB. The usual ways to play light-gun games on a
modern TV are a Wii Remote (Dolphin, and RetroArch through
`hid-wiimote`), an IR light gun such as the Sinden or a GUN4IR build,
or a Zapper rebuilt with one of those kits. None have been tried on
FamiDrive yet.

## Wii Remote

✅ Real Wii Remotes, connected to Dolphin over Bluetooth by pressing
1 + 2.

- Wii Sports bowling worked with two remotes as two players
  (`controllers.wii.remotes = [ "real" … ]`).
- **Paired with the box, the way to use them:** pair each remote with the
  box's own Bluetooth once (`bluetoothctl`: `scan on`, press the red
  sync button inside the battery cover, then `pair`, `trust` and
  `connect` with its address). It shows up as `Nintendo RVL-CNT-01`
  (`-TR` for a Wii Remote Plus). From then on, any button turns it on
  and reconnects it, as on a Wii. FamiDrive lets the player at the TV
  open it, so Dolphin takes it as a real remote about 6 seconds after a
  game starts (it buzzes when that happens). A controller-friendly
  pairing screen is planned (#144).
- **2026-10-08, the Mii Channel on the first box:** ✅ with a remote
  paired that way, pointer and all. Without the box's permission rule,
  Dolphin couldn't open the remote and never took it. Dolphin's own
  rules only cover remotes on USB.
- **2026-10-09, after the rebuild with that rule (#146):** ✅ the Mii
  Channel again, with nothing done by hand: press a button, start the
  channel, and the remote works in it.
- **Still to check:** the remote's speaker (`controllers.wii.speaker`),
  rumble, Bluetooth passthrough with a second, Wii-compatible adapter
  (`controllers.wii.bluetoothPassthrough`), and whether ES-DE's menus
  can use the remote.

## Wii MotionPlus

❔ Untested. The MotionPlus adds a gyroscope to a Wii Remote, plugged in
or built into a Wii Remote Plus. With a real remote connected to
Dolphin, games that need it (Wii Sports Resort, Skyward Sword) should
see it. Check that it's detected, and whether it needs recalibrating.

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

## DK Bongos

❌ Not set up yet: FamiDrive can't tell Dolphin about them
([#131](https://github.com/anultravioletaurora/FamiDrive/issues/131)).
No one has tried a set on a FamiDrive box.

The GameCube's bongo controller, for Donkey Konga 1, 2 and 3 and
Donkey Kong Jungle Beat. How it's meant to work:

- **Connection:** the bongos plug into a GameCube port, so they need
  the [official adapter](#gamecube-controllers-on-the-official-adapter)
  (or one that copies it) in Wii U mode, and a port set to `"adapter"`.
- **Dolphin** has to be told the port has bongos, not a controller: the
  "DK Bongos" checkbox in its adapter settings (`SimulateKonga<port>`
  under `[Core]` in Dolphin.ini). FamiDrive resets Dolphin's port
  settings on every switch, so turning it on in Dolphin doesn't last.
  #131 adds a `"bongos"` port value that sets it.
- **Without real bongos:** Dolphin can also emulate them from an
  ordinary pad (its "DK Bongos" device). FamiDrive doesn't offer that
  yet either.
- **Quitting:** the bongos have Start but no Select, so Select + Start
  can't quit from them. Keep a pad connected to quit.
- **Donkey Kong Jungle Beat on Wii** (New Play Control!) uses the Wii
  Remote and Nunchuk instead, not the bongos.

To check, once someone has a set: both games see them, the clap sensor
works through the adapter, and which port each player's bongos land on.

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

## Fight sticks

❔ None tried yet. Most sticks are made for one console and act like
that console's pad on a PC:

- **Xbox sticks** (and sticks in an XInput mode) run under `xpad`, like
  an Xbox pad.
- **PlayStation sticks** (Hori, Victrix, Qanba and others) usually show
  up as a PlayStation pad, or as a generic HID pad whose buttons come
  out numbered (like the [Razer Raiju](#razer-raiju)).
- **Switch sticks** run under `hid-nintendo`, or as a generic HID pad.

To check with each one:

- **The stick's mode switch** (often labeled DP / LS / RS): whether the
  lever is the d-pad or the left stick. ES-DE's menus and most fighting
  games want the d-pad. Some emulated games want the stick.
- **Select + Start** to quit: many sticks hide Select (View, Share or
  "Back") on the top or side of the case, and some have a lock switch
  that turns those buttons off during tournaments. Check that the lock
  is off, and that famidrive-quit sees both buttons.
- **Button layout:** the eight buttons on the face map to the pad's
  A/B/X/Y and shoulder buttons. Check that each game's default layout
  makes sense, especially in emulators, where the console's own layout
  may differ from the stick's labels.
- **Leverless sticks** (all buttons, like a Hit Box) send the
  direction buttons as a d-pad. Check how each game resolves left and
  right held at once (SOCD).
- **Games to try:** [Street Fighter 6](COMPATIBILITY.md#street-fighter-6)
  on Steam, arcade fighting games in FinalBurn Neo (the Arcade
  system), and console fighting games in the other emulators.

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
- **Shifters, pedals and handbrakes:** a Logitech shifter and pedals
  plug into the wheel and come through as part of it. A handbrake (and
  pedals on their own cable) is usually a separate USB device, which
  only games that take input from several devices at once can use:
  most sims do, many arcade racers don't. Logitech's shifter is
  H-pattern, and each gear is a button.
- **Fanatec ClubSport** (wheel bases, pedals, shifter, handbrake):
  ❔ untested.
  - The wheel base's force feedback needs `hid-fanatecff`, which covers
    the ClubSport V2 and V2.5 bases as well as Fanatec's direct-drive
    ones.
  - ClubSport pedals plugged into the base come through as part of the
    wheel. Plugged in by their own USB cable, they're a separate device.
  - The ClubSport shifter and handbrake plug into the base too, or into
    USB with an adapter, and then they're separate devices, as above.
  - Fanatec's wheel rims are read through the base.
  - Record each device's USB ID and what the game sees.
- **Rotation range, centering and other settings** are usually set with
  Oversteer, a desktop app. A TV box has no desktop, so FamiDrive would
  set them from Nix.
- **Emulators:** Dolphin can present a wheel to the GameCube as its
  steering wheel accessory, for the few games that support it. Wii
  racing games use the Wii Remote, in or out of a Wii Wheel shell.

## Flight sticks and throttles

❔ None tried yet. Thrustmaster's sticks and throttles (the T.16000M,
TWCS, T.Flight HOTAS and others), Speedlink's joysticks and most
others are plain USB joysticks, with no driver
needed. They're for PC flight and space games on Steam, which read them
directly, and through Proton they reach games through Wine.

To check with one:

- **Several devices at once:** a stick and a throttle (or two sticks)
  are separate devices. Check that the game sees each, and keeps its
  bindings when they're plugged in a different order.
- **ES-DE and FamiDrive's tools** should leave them alone. A stick
  isn't a gamepad (it has a trigger, not A and B), so it shouldn't move
  ES-DE's menus or count as a player.
- **Force feedback** on the sticks that have it (none of the above do)
  would need checking, like a [wheel's](#racing-wheels).

## Pen tablets

❔ None tried yet. For [osu!](USAGE.md#famidriveosuenable), which plays
best with a pen tablet.

- **How they work here:** osu! has OpenTabletDriver built in, and reads
  the tablet itself. FamiDrive installs OpenTabletDriver's udev rules so
  the player at the TV can open it, and not OpenTabletDriver's own
  background service, which would fight osu! for the tablet.
- **Wacom:** the kernel's `wacom` driver also makes the tablet a pointer
  everywhere else, and OpenTabletDriver supports Wacom's tablets. The
  usual osu! choices are the Intuos S (CTL-4100) and the older One by
  Wacom (CTL-472).
- **Others:** XP-Pen and Huion tablets are cheaper and also supported by
  OpenTabletDriver; check its list of supported tablets for the exact
  model.
- **To check:** that osu! finds the tablet in its settings, area mapping,
  and that the kernel's pointer and osu!'s reading don't both move the
  cursor.

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
