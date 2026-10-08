# Usage

Every option a box's `configuration.nix` can set, under `famidrive.`. For
setting up a box, start with [Using it](../README.md#using-it) in the README.

Options without a default have to be set when the feature that uses them
is on; every other option is optional.

<!-- Generated from the option declarations by tests/usage_doc.py. CI
     fails when this file is out of date. To change it, change the
     option's description, then regenerate on an x86_64-linux machine:
     nix build .#checks.x86_64-linux.usage-doc.doc && cp result docs/USAGE.md -->

## Contents

- [The box](#the-box)
- [Players](#players)
- [Servers](#servers)
- [RomM](#romm)
- [Hardware](#hardware)
- [TV and session](#tv-and-session)
- [Menu](#menu)
- [Switch](#switch)
- [Controllers](#controllers)
- [Steam](#steam)
- [Media](#media)
- [Clone Hero](#clone-hero)
- [YARG](#yarg)
- [osu!](#osu)
- [SuperTuxKart](#supertuxkart)
- [Minecraft](#minecraft)
- [Valheim](#valheim)
- [PC saves](#pc-saves)
- [Online play](#online-play)
- [Systems](#systems)
- [Everything else](#everything-else)

## The box

What the box is: on or off, which kinds of games it carries, and where its shared library lives.

### `famidrive.dataDir`

The shared library: pulled ROMs, firmware, cover art. Every player reads it; only the library pull writes it.

- **Type:** absolute path
- **Default:** `"/var/lib/famidrive"`

### `famidrive.enable`

Whether to enable FamiDrive.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.lanes`

Which launch lanes this box carries:

- `"roms"`: the consoles, through their emulators.
- `"steam"`: each player's Steam library.
- `"heroic"`: each player's GOG, Epic Games Store and Amazon
  Games libraries, through Heroic Games Launcher. Each store is
  its own system in the menu.
- `"minecraft"`: Prism Launcher's instances, in Ports.

An emulation-only box is `[ "roms" ]` and skips Steam, Proton,
Heroic and Prism entirely.

- **Type:** list of (one of "roms", "steam", "heroic", "gog", "minecraft")
- **Default:** 

  ```nix
  [
    "roms"
  ]
  ```

### `famidrive.localRoms`

ROM folders already on this box, by system. Every player has to be
able to read them: group `famidrive` (every player is in it) with
read access all the way down, or readable by everyone.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    gc = "/srv/roms/gamecube";
  }
  ```

## Players

Who plays. Each player is a Linux account and a RomM user of their own.

### `famidrive.guest.enable`

Whether to enable a Guest player on the "Who's playing?" screen, for anyone without
their own: every game on the box, their own saves kept on this box
only (no RomM), and Steam if they sign in to theirs.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.players`

Who plays on this box. Each player is their own Linux account and
their own RomM user, so each has their own Steam login, saves,
RetroAchievements and ES-DE favorites, while the ROMs, firmware and
controller setup are the box's and shared. With more than one
player (the guest counts), the box starts on a "Who's playing?"
screen, and quitting ES-DE goes back to it.

- **Type:** attribute set of (submodule)
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    alice = { };                              # Linux account and RomM user "alice"
    sam = { displayName = "Sammy"; };
  }
  ```

### `famidrive.players.<name>.displayName`

What the "Who's playing?" screen calls them.

- **Type:** string
- **Default:** the name, capitalized

### `famidrive.players.<name>.edenProfileId`

The Eden profile whose saves sync with RomM, by its save folder's
name. Usually left unset: FamiDrive uses the one Eden runs games
as. For an Eden with old saves spread over several profiles, to
say which one is real.

- **Type:** null or string
- **Default:** `null`
- **Example:** `"63CA1C4C81D775E24288780D17344942"`

### `famidrive.players.<name>.overlays.performance.enable`

MangoHud's performance overlay (frame rate, frame times, CPU and
GPU load and temperatures) over every game and the menu, through
gamescope's `--mangoapp`. Takes effect at the player's next
session.

- **Type:** null or boolean
- **Default:** the box's (`famidrive.overlays`)

### `famidrive.players.<name>.overlays.performance.position`

Where the performance overlay shows up.

- **Type:** null or one of "top-left", "top-center", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-center", "bottom-right"
- **Default:** the box's (`famidrive.overlays`)

### `famidrive.players.<name>.overlays.toasts.hide`

Kinds of toast not to show: `"notice"` (a save uploaded and the
like), `"alert"` (something went wrong), `"progress"` (downloads
and other background work), `"achievement"` (RetroAchievements
unlocks). Toasts are always on; this is how to quiet some.

- **Type:** null or (list of (one of "notice", "alert", "progress", "achievement"))
- **Default:** the box's (`famidrive.overlays`)

### `famidrive.players.<name>.overlays.toasts.position`

Where toasts show up.

- **Type:** null or one of "top-left", "top-center", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-center", "bottom-right"
- **Default:** the box's (`famidrive.overlays`)

### `famidrive.players.<name>.owner`

Their RomM username. Their token is issued by this user, the box
registers as one of this user's RomM devices, and their saves go
up under it. One owner across several boxes shares saves;
different owners never do (multi-box.md "Per-user saves").

- **Type:** string
- **Default:** `"‹name›"`

### `famidrive.players.<name>.retroAchievements.hardcore`

Hardcore mode: unlocks count for more on RetroAchievements, and
save states, rewind, slow motion and cheats are off.

- **Type:** boolean
- **Default:** `false`

### `famidrive.players.<name>.retroAchievements.passwordFile`

A file with their RetroAchievements password, readable by their account.

- **Type:** null or absolute path
- **Default:** their sops secret, `retroachievements-<name>`

### `famidrive.players.<name>.retroAchievements.username`

Their RetroAchievements username. Set, their RetroArch, Dolphin
and PCSX2 are signed in at the start of each of their sessions,
and unlocks show as toasts. Their password is a sops secret,
`retroachievements-<name>`, unless `passwordFile` says otherwise.

- **Type:** null or string
- **Default:** `null`

### `famidrive.players.<name>.romm.tokenFile`

Their RomM Client API Token (rmm_...), decrypted by sops-nix.

- **Type:** null or absolute path
- **Default:** their sops secret, `romm-token-<name>`

### `famidrive.players.<name>.user`

Their Linux account. Made if it doesn't exist yet.

- **Type:** string
- **Default:** `"‹name›"`

### `famidrive.primaryPlayer`

The box's main player. Their RomM token is the one the shared
library and firmware are pulled with, and it's whose PC saves sync
(`pcSaves`). Needed once there's more than one player.

- **Type:** null or string
- **Default:** the only player, when there's one
- **Example:** `"alice"`

## Servers

Your servers' addresses. None has a default: they're yours, not FamiDrive's. Each is only read when the feature that uses it is on, so a box that doesn't use one doesn't set it.

### `famidrive.endpoints.dolphinTraversal`

Dolphin's traversal server (GameCube and Wii netplay). Needs a port forward: it sees players' real addresses.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"traversal.example.com"`

### `famidrive.endpoints.dolphinTraversalPort`

The Dolphin traversal server's port.

- **Type:** 16 bit unsigned integer; between 0 and 65535 (both inclusive)
- **Default:** `6262`

### `famidrive.endpoints.edenRoomHost`

Eden room server (Switch online), `eden-room`, which ships with nixpkgs' eden.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"eden.example.com"`

### `famidrive.endpoints.edenRoomPort`

The Eden room server's port.

- **Type:** 16 bit unsigned integer; between 0 and 65535 (both inclusive)
- **Default:** `24872`

### `famidrive.endpoints.jellyfin`

Jellyfin's public URL, the same from every box on or off the LAN.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"https://jellyfin.example.com"`

### `famidrive.endpoints.retroarchTunnel`

RetroArch netplay relay (its MITM tunnel server), host and port.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"netplay.example.com:55435"`

### `famidrive.endpoints.romm`

RomM base URL, over HTTPS (behind a reverse proxy) so boxes off the LAN can reach it.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"https://romm.example.com"`

### `famidrive.endpoints.rpcn`

RPCN server (PS3 online, RPCS3), host and port. Needs a port forward: it signals peer-to-peer connections.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"rpcn.example.com:31313"`

### `famidrive.endpoints.xeniaWebServices`

Xenia web services (Xbox 360 online), a plain REST API behind the reverse proxy.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"https://xenia.example.com"`

## RomM

The game library, firmware and console saves, from your own [RomM](https://github.com/rommapp/romm). Optional: a box can also run from ROM folders already on it (`localRoms`).

### `famidrive.romm.collection`

RomM collection this box mirrors locally, or null for everything.
What a box carries is managed in RomM's web UI, not here.

- **Type:** null or string
- **Default:** `null`
- **Example:** `"Living Room"`

### `famidrive.romm.enable`

Pull the library, firmware and console saves from RomM. Off for a
box whose ROMs are already on local disk (`localRoms`) while the
RomM agent is unproven: saves then stay local, exactly like before
FamiDrive. Also gates the per-box sops secret, so a box with this
off needs no sops setup at all.

- **Type:** boolean
- **Default:** `true`

### `famidrive.romm.firmwarePlatforms`

RomM platform slugs whose firmware gets pulled. A platform with none in RomM costs one empty request.

- **Type:** list of string
- **Default:** every RomM platform this box has a system for

### `famidrive.romm.platforms`

RomM platforms (their slugs, as in RomM's URLs) this box mirrors,
or null for every platform it has a system for. Works with
`collection`: both set, a box gets that collection's games on
these platforms.

- **Type:** null or (list of string)
- **Default:** `null`
- **Example:** 

  ```nix
  [
    "ngc"
    "wii"
  ]
  ```

### `famidrive.romm.saveHistory`

Versions of each game's save RomM keeps for a player: every push
adds one, and RomM deletes the oldest beyond this. Only FamiDrive's
own save slots; saves uploaded to RomM by hand are left alone.

- **Type:** integer between 1 and 100 (both inclusive)
- **Default:** `3`

### `famidrive.romm.url`

The RomM server this box uses. Set `endpoints.romm` instead; this is for a box that uses a different RomM than the rest.

- **Type:** string
- **Default:** `config.famidrive.endpoints.romm`

## Hardware

The box's graphics card. AMD is tested, Intel should just work, Nvidia is untested.

### `famidrive.gpu`

The box's graphics card, for its drivers. `famidrive-hardware` on
the box lists its cards and the setting to use.

- `"auto"` (the default): AMD and Intel cards, both through Mesa,
  plus Intel's video decoder for Kodi. Nothing to choose for either.
- `"amd"`, `"intel"`: the same as `"auto"`, said outright.
  AMD is what FamiDrive is tested on; Intel should just work.
- `"nvidia"`: Nvidia's own driver (its open kernel module, for RTX
  20-series cards and newer), with kernel modesetting, which
  gamescope needs, its video decoder, and the long-term kernel,
  which Nvidia's driver keeps up with. Untested: results welcome
  in docs/COMPATIBILITY.md.

- **Type:** one of "auto", "amd", "intel", "nvidia"
- **Default:** `"auto"`

## TV and session

The picture, and what happens to the TV on a rebuild.

### `famidrive.boot.splash.enable`

Whether to enable a boot screen (Plymouth) in place of console text while the box starts.

- **Type:** boolean
- **Default:** `true`
- **Example:** `true`

### `famidrive.boot.splash.scale`

How large Plymouth draws the boot screen. It can't tell how far
away a TV is, so on a 4K TV it draws everything tiny at 1. The
default, 4, is for a 4K TV; use 2 on a 1080p one.

Until the graphics driver loads, a few seconds in, the screen is
the firmware's, usually a lower resolution, so the spinner is
larger then and shrinks when the driver takes over. Found on the
first box 2026-10-07: at 2 the spinner looked right on the
firmware's screen and tiny at 4K.

- **Type:** integer between 1 and 4 (both inclusive)
- **Default:** `4`

### `famidrive.boot.splash.theme`

The Plymouth theme. `"bgrt"` (the default) shows the computer's
own logo with a spinner, when its firmware provides a logo (not
every PC's does; the spinner alone shows otherwise). `"spinner"`
is the same without the logo. A theme from another package needs it in
`themePackages` too.

- **Type:** string
- **Default:** `"bgrt"`
- **Example:** `"spinner"`

### `famidrive.boot.splash.themePackages`

Packages with more Plymouth themes, for `theme`.

- **Type:** list of package
- **Default:** `[ ]`
- **Example:** `[ (pkgs.adi1090x-plymouth-themes.override { selected_themes = [ "rings" ]; }) ]`

### `famidrive.cec.enable`

Whether to enable HDMI-CEC TV power-on. Deferred to project phase 2 (spec.md); off by
default and untested. AMD discrete GPUs don't expose CEC on Linux, so
on those it also needs a USB-CEC adapter (tv-interface.md).

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.display.hdr`

Whether this box's TV does HDR. On: gamescope outputs HDR and Proton
games are told they may use it. Off (the default): plain SDR, nothing
to go wrong on a TV that doesn't support it.

- **Type:** boolean
- **Default:** `false`

### `famidrive.display.refresh`

Refresh rate gamescope asks the TV for. null = the TV's preferred mode.

- **Type:** null or (positive integer, meaning >0)
- **Default:** `null`
- **Example:** `120`

### `famidrive.display.vrr`

Variable refresh rate (FreeSync / HDMI VRR): the TV follows the
game's frame rate. Smoother when a game dips below the refresh rate,
but many TVs pulse in brightness when the frame rate is low or
uneven. Found on the first box 2026-10-05: Jackbox Party Pack 6
pulsed on the TV with it on. Off by default, like `hdr`: turn it on
for a TV that handles it well.

- **Type:** boolean
- **Default:** `false`

### `famidrive.session.restartOnSwitch`

Restart the TV's session on `nixos-rebuild switch` when the switch
changed it, so the new one is what's on screen. Whatever is running
on the TV closes (back to "Who's playing?" or the menu). Off: the
new session starts at the next reboot or
`systemctl restart display-manager`, as on plain NixOS.

- **Type:** boolean
- **Default:** `true`

## Menu

ES-DE, the menu everything launches from.

### `famidrive.esde.musicVolume`

Volume of the menu's music, 0 to 100. ES-DE has no music of its own:
FamiDrive plays each player's `~/ES-DE/music` (MP3, OGG, FLAC, ...)
shuffled behind the menu, paused while a game or app is open.
Players without music files get none.

- **Type:** integer between 0 and 100 (both inclusive)
- **Default:** `50`

### `famidrive.esde.nowPlaying`

Whether the menu's music shows a toast as each song starts: its
title and artist (from the file's tags; the file name when it has
none).

- **Type:** boolean
- **Default:** `true`

### `famidrive.esde.skipFolders`

Folders, at any depth under a system's ROMs, that ES-DE shouldn't
list: a game's DLC, updates and the like, which the emulator installs
or applies, not something to launch. Matched by name, ignoring case.
Each one gets an empty `noload.txt`, ES-DE's own "skip this folder"
marker, at boot and on every switch.

- **Type:** list of string
- **Default:** 

  ```nix
  [
    "dlc"
    "update"
    "updates"
    "patch"
    "patches"
    "mod"
    "mods"
    "manual"
    "manuals"
  ]
  ```

### `famidrive.esde.theme`

ES-DE theme, symlinked in and selected. null = ES-DE's bundled default.

- **Type:** null or (submodule)
- **Default:** [Art Book Next](https://github.com/anthonycaccese/art-book-next-es-de), pinned
- **Example:** `{ name = "my-theme"; src = ./themes/my-theme; }`

### `famidrive.esde.theme.name`

Folder name under ES-DE/themes/, which is also ES-DE's Theme setting.

- **Type:** string
- **Default:** none; required when used

### `famidrive.esde.theme.src`

The theme's files.

- **Type:** absolute path
- **Default:** none; required when used

## Switch

Switch games that run in Ryujinx instead of Eden.

### `famidrive.switch.ryujinx.games`

Switch games to run in Ryujinx instead of Eden, by title ID. For
games, or mods, that only work there: HewDraw Remix for Smash
Ultimate (`01006A800016E000`) needs Skyline plugins, which Eden
can't run. Each player's save for the game is the same one Eden
would use, so switching a game between the two keeps it.

- **Type:** list of string matching the pattern 0100[0-9A-Fa-f]{12}
- **Default:** `[ ]`
- **Example:** 

  ```nix
  [
    "01006A800016E000"
  ]
  ```

### `famidrive.switch.ryujinx.memory`

The memory Ryujinx gives the Switch it emulates. A real Switch has
4 GiB; modded games need more. Found on the first box 2026-10-07:
Smash Ultimate with HewDraw Remix and all its DLC ran out at 4 GiB
(`MapPhysicalMemory() = LimitReached` in Ryujinx's log) and crashed
on the character select screen. HDR's own guides ask for 8 GiB.

Passed as `--dram-size`: started with `--no-gui`, Ryujinx takes
its settings from the command line, not from Config.json.

- **Type:** one of "4GiB", "6GiB", "8GiB", "12GiB"
- **Default:** `"8GiB"`

### `famidrive.switch.ryujinx.package`

The Ryujinx to run them with: nixpkgs' Ryubing, or a canary build.

- **Type:** package
- **Default:** `pkgs.ryubing`

## Controllers

How controllers reach the emulators. Per-controller results are in [CONTROLLERS.md](CONTROLLERS.md).

### `famidrive.controllers.faceButtons`

How a modern pad's A/B/X/Y reach the GameCube and the Switch, whose
layouts differ from an Xbox-style pad's.

- `"labels"`: pressing the button printed A is A in the game, and so
  on. What you see is what you get, but B and X sit somewhere else
  than on the original console.
- `"positions"`: buttons keep the original console's places. On the
  Switch, the bottom button is B and the right one A; on the
  GameCube and the N64, B is left (and the GameCube's X right),
  whatever the pad says.

On the N64 (RetroArch's Mupen64Plus-Next), "labels" puts the N64's
B on the pad's B and the C button that was there on X. Found on the
first box 2026-10-06: Mario Party 3's dialog skipped ahead on X.

In Eden this applies to the pads FamiDrive knows (see
`gamecube.ports`) once Eden has set one up; other pads keep Eden's
own mapping.

- **Type:** one of "labels", "positions"
- **Default:** `"labels"`

### `famidrive.controllers.gamecube.ports`

What's in each GameCube port in Dolphin, port 1 first. Ports left off
the end are empty. Each entry is one of:

- `"gamepad"`: whichever controller is connected when the game
  starts: the first `"gamepad"` port gets the first pad, and so on,
  modern pads before GameCube controllers on the official adapter.
  Any model works; nothing is tied to one pad.
- a known controller's short name, such as `"8bitdo-ultimate-2"`. Name
  the same model twice for two of them; the first one connected is
  the lower port.
- any other controller's SDL name, as Dolphin shows it.
- `"adapter"`: a real GameCube controller on the official adapter
  (Wii U / Switch GameCube adapter).
- `"none"`: nothing in this port.

These ports are rebuilt on every switch. Changes made in Dolphin's own
controller screens don't last, on purpose.

- **Type:** list of string
- **Default:** 

  ```nix
  [
    "gamepad"
  ]
  ```
- **Example:** 

  ```nix
  [
    "8bitdo-ultimate-2"
    "8bitdo-ultimate-2"
    "adapter"
  ]
  ```

### `famidrive.controllers.wii.balanceBoard`

A real Wii Balance Board, connected like a real Wii Remote (the
sync button under its battery cover).

- **Type:** boolean
- **Default:** `false`

### `famidrive.controllers.wii.bluetoothPassthrough`

Hand a Bluetooth adapter to the emulated Wii entirely, as a real
Wii's Bluetooth chip. The most faithful way to use real remotes
(pairing is remembered, as on a Wii), but it needs an adapter
Dolphin supports, and that adapter is then of no use to anything
else on the box, so it should be a second one. Untested.

- **Type:** boolean
- **Default:** `false`

### `famidrive.controllers.wii.remotes`

What's in each Wii Remote slot in Dolphin, player 1 first. Slots
left off the end are empty. Each entry is one of:

- `"real"`: a first-party Wii Remote over Bluetooth. Dolphin keeps
  looking for remotes, so pressing 1 + 2 (or the red sync button)
  connects one at any time, also mid-game. Everything a remote
  has works, including its speaker, Nunchuk and Classic
  Controller.
- `"emulated"`: Dolphin's emulated Wii Remote, played with a modern
  pad. Its bindings are still Dolphin's own, made in its controller
  screens; FamiDrive doesn't set them yet.
- `"none"`: nothing in this slot.

Rebuilt on every switch, like the GameCube ports.

- **Type:** list of (one of "real", "emulated", "none")
- **Default:** 

  ```nix
  [
    "emulated"
  ]
  ```
- **Example:** 

  ```nix
  [
    "real"
    "real"
    "real"
    "real"
  ]
  ```

### `famidrive.controllers.wii.speaker`

Play game sounds through real Wii Remotes' speakers.

- **Type:** boolean
- **Default:** `true`

### `famidrive.controllers.xboxWirelessAdapter`

Turn on xone, the driver for Microsoft's Xbox Wireless Adapter (the
USB dongle that connects Xbox One and Series controllers without
Bluetooth). Only the dongle needs it: those controllers already work
over Bluetooth (xpadneo) and over a USB cable (`xpad`).

Off by default, because xone replaces the kernel's `xpad` driver
with xpad-noone, a copy without Xbox One support, so that the two
don't fight over wired Xbox One pads. xpad-noone still drives Xbox
360 pads, and 8BitDo pads in XInput mode. xone also blocks
`mt76x2u`, the driver for some MediaTek USB Wi-Fi adapters, since
the dongle uses the same chip.

- **Type:** boolean
- **Default:** `false`

## Steam

The Steam lane (`lanes` has `"steam"`).

### `famidrive.steam.compatTools`

Per-game Proton pins, by game name (as Steam and ES-DE show it) or
Steam app id: what Steam's "Force the use of a specific Steam Play
compatibility tool" sets. Tool names are Steam's internal ones
(`proton_experimental`, `proton_10`, `proton_hotfix`, or a custom
tool's folder name such as `GE-Proton`). Mostly for games whose
native Linux build Steam still prefers but which no longer works,
like Rocket League.

This is for settling on a choice. To try versions out without a
rebuild, use Steam Settings in ES-DE's Steam system (Big Picture →
the game → Properties → Compatibility). Pinned games are set back to
their pin at the start of each session, before Steam starts; other
games keep whatever Steam was told. Names of games that aren't
installed yet are skipped until they are.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    "1091500" = "GE-Proton";
    "Rocket League" = "proton_experimental";
  }
  ```

### `famidrive.steam.launchOptions`

Games' launch options, by name (as Steam and ES-DE show it) or app
id. Set at the start of each session; a game not listed keeps what
was set in Steam.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    "Cyberpunk 2077" = "WINEDLLOVERRIDES=\"winmm,version=n,b\" %command%";
  }
  ```

### `famidrive.steam.steamInput`

Whether Steam Input stands between controllers and Steam games.
Off (the default): FamiDrive sets "Disable Steam Input" on every
installed game at the start of each session, so each game reads the
pad itself, the same as every emulator does. Games installed during
a session get it from the next one. On: Steam's own per-game
choices are left alone.

- **Type:** boolean
- **Default:** `false`

### `famidrive.steam.steamInputGames`

Games that keep Steam Input while `steamInput` is off, by name (as
Steam and ES-DE show it) or app id. For games whose own controller
support is missing or worse, such as Valve's older games, which
expect Steam Input.

- **Type:** list of string
- **Default:** `[ ]`
- **Example:** 

  ```nix
  [
    "Left 4 Dead 2"
  ]
  ```

## Media

Video apps in ES-DE's Media system.

### `famidrive.media.jellyfin.enable`

Whether to enable Jellyfin MPV Shim as a Media entry in ES-DE.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.media.jellyfin.server`

Public Jellyfin hostname, the same from every box on or off the LAN.
Pre-filled into the shim's sign-in form (a small patch in the flake
overlay), so first launch is just "Use Quick Connect" and a code. The
shim keeps its own login token afterwards; nothing secret is here.

- **Type:** null or string
- **Default:** `null`

### `famidrive.media.kodi.addons`

More Kodi add-ons from nixpkgs' kodiPackages, for every player.
JellyCon (Jellyfin), controller support, inputstream.adaptive
and Up Next are always there.

- **Type:** function that evaluates to a(n) list of package
- **Default:** `p: [ ]`
- **Example:** `p: [ p.a4ksubtitles p.sendtokodi p.pvr-hdhomerun ]`

### `famidrive.media.kodi.enable`

Whether to enable Kodi as a Media entry in ES-DE, with Jellyfin through JellyCon
(movies, shows, music and live TV), already pointed at
`endpoints.jellyfin` when that's set.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.media.kodi.sources`

This box's own media folders, in every player's Kodi library:
named sources, set to their content with Kodi's TMDB scrapers,
and scanned each time Kodi starts, so new files turn up on their
own. A folder that isn't there (an unplugged drive) is skipped.

Mount the drive in the host's config, readable by every player,
and with `nofail` so the box still boots without it:

    fileSystems."/media" = {
      device = "/dev/disk/by-label/media";
      options = [ "nofail" "x-systemd.automount" ];
    };

(exFAT and NTFS drives also need `uid`/`gid`/`umask` options,
since they have no Linux permissions of their own.)

- **Type:** attribute set of (submodule)
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    Movies = {
      content = "movies";
      path = "/media/movies";
    };
    "TV Shows" = {
      content = "tvshows";
      path = "/media/tv";
    };
  }
  ```

### `famidrive.media.kodi.sources.<name>.content`

What the folder holds, so Kodi knows how to scan it (its "Set content").

- **Type:** one of "movies", "tvshows"
- **Default:** none; required when used

### `famidrive.media.kodi.sources.<name>.path`

A folder on this box, usually on an external drive the host mounts.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"/media/movies"`

## Clone Hero

Clone Hero, in the Ports system.

### `famidrive.cloneHero.audioOffset`

Clone Hero's audio calibration in milliseconds, the same for every
player: it belongs to the TV and speakers, not the person. null
leaves each player's own (Settings → Calibration).

- **Type:** null or signed integer
- **Default:** `null`
- **Example:** `200`

### `famidrive.cloneHero.enable`

Whether to enable Clone Hero, in ES-DE's Ports system.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.cloneHero.guestProfiles`

Clone Hero profiles named "Guest 1", "Guest 2", ... next to one for
each player, so friends can jump in on another instrument with a
profile of their own.

- **Type:** integer between 0 and 8 (both inclusive)
- **Default:** `3`

### `famidrive.cloneHero.onlyListed`

Remove charts from the managed library that are no longer listed.
Songs added by hand go in `clonehero/local` on the library disk
(dataDir), which is never touched.

- **Type:** boolean
- **Default:** `true`

### `famidrive.cloneHero.romm.entry`

The RomM entry each player's Clone Hero scores and profiles are
saved under, by name. RomM keeps saves only for games in its
library, so add one by hand (any platform this box doesn't pull,
and any small file). null keeps scores on this box only.

- **Type:** null or string
- **Default:** `"Clone Hero"`

### `famidrive.cloneHero.sharedBindings`

Controller bindings are the box's: when anyone binds a guitar (or
rebinds one) and exits Clone Hero, every player gets the same
bindings the next time it starts. They're kept on the library disk
(clonehero/bindings). false leaves each player's own.

- **Type:** boolean
- **Default:** `true`

### `famidrive.cloneHero.songs`

Charts for every player on this box, in Clone Hero and in YARG
(`famidrive.yarg`), by name (the file's name) and
Chorus Encore md5 (enchor.us: a chart's download is
files.enchor.us/<md5>.sng). Downloaded to the library disk at boot
and whenever this list changes. A changed md5 downloads again.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    "AFI - Miss Murder" = "05185565cb931978c11de73d3048206e";
  }
  ```

### `famidrive.cloneHero.videoOffset`

Clone Hero's video calibration in milliseconds, the same for every player. null leaves each player's own.

- **Type:** null or signed integer
- **Default:** `null`

## YARG

YARG (Yet Another Rhythm Game), in the Ports system, playing the same songs as Clone Hero.

### `famidrive.yarg.enable`

Whether to enable YARG (Yet Another Rhythm Game), in ES-DE's Ports system: guitar,
bass, drums, keys and vocals, with the box's Clone Hero songs
(`cloneHero.songs`).

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

### `famidrive.yarg.romm.entry`

The RomM entry each player's YARG scores and profiles are saved
under, by name. RomM keeps saves only for games in its library, so
add one by hand (any platform this box doesn't pull, and any small
file), as for Clone Hero. null keeps scores on this box only.

- **Type:** null or string
- **Default:** `"YARG"`

## osu!

osu! (lazer), in the Ports system.

### `famidrive.osu.enable`

Whether to enable osu! (lazer), in ES-DE's Ports system, played with a mouse, a pen
tablet or a touchscreen, and a keyboard. Pen tablets work through
osu!'s built-in OpenTabletDriver.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

## SuperTuxKart

SuperTuxKart, in the Ports system.

### `famidrive.superTuxKart.enable`

Whether to enable SuperTuxKart, in ES-DE's Ports system.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

## Minecraft

Minecraft through Prism Launcher, in the Ports system (`lanes` has `"minecraft"`).

### `famidrive.minecraft.instances`

Prism Launcher instances this box comes with, by the name ES-DE shows.
Instances not listed here are left alone.

- **Type:** attribute set of (submodule)
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    "Friends Server" = {
      minecraft = "26.2";
      servers = [ { name = "Friends"; address = "mc.example.org"; } ];
      join = "mc.example.org";
    };
  }
  ```

### `famidrive.minecraft.instances.<name>.controller`

Play with a controller: adds Controlify (and Fabric API and
YACL, which it needs). Needs Fabric, and a Minecraft version
FamiDrive has these pinned for.

- **Type:** boolean
- **Default:** `true`

### `famidrive.minecraft.instances.<name>.fabricLoader`

Fabric Loader version, or null for vanilla Minecraft (no mods).

- **Type:** null or string
- **Default:** `"0.19.5"` when `controller` is on, else `null`

### `famidrive.minecraft.instances.<name>.java`

Java to run it with. Minecraft 26 needs 25; older versions want older ones (1.20.5 to 1.21: jdk21).

- **Type:** package
- **Default:** `pkgs.jdk25`

### `famidrive.minecraft.instances.<name>.join`

A server to join straight from launch, skipping the title screen:
picking the instance in ES-DE drops you into that server.

- **Type:** null or string
- **Default:** `null`
- **Example:** `"mc.example.org"`

### `famidrive.minecraft.instances.<name>.memory`

Most memory Minecraft may use, in MiB. null: Prism's setting.

- **Type:** null or (positive integer, meaning >0)
- **Default:** `null`
- **Example:** `6144`

### `famidrive.minecraft.instances.<name>.minecraft`

Minecraft version.

- **Type:** string
- **Default:** none; required when used
- **Example:** `"26.2"`

### `famidrive.minecraft.instances.<name>.mods`

More mod jars. Mods added by hand in Prism stay as well.

- **Type:** list of absolute path
- **Default:** `[ ]`
- **Example:** `[ (pkgs.fetchurl { name = "sodium.jar"; url = "…"; sha512 = "…"; }) ]`

### `famidrive.minecraft.instances.<name>.players`

The players (`famidrive.players`) who get this instance. Each
plays with their own Microsoft account, signed in once in their
own Prism. A player no longer listed loses the instance from
their Ports; it's moved aside, worlds and all, not deleted.

- **Type:** list of string
- **Default:** every player (not the guest)
- **Example:** 

  ```nix
  [
    "alice"
  ]
  ```

### `famidrive.minecraft.instances.<name>.servers`

Servers in the multiplayer list. Servers added in-game stay.

- **Type:** list of (submodule)
- **Default:** `[ ]`

### `famidrive.minecraft.instances.<name>.servers.*.address`

- **Type:** string
- **Default:** none; required when used
- **Example:** `"mc.example.org"`

### `famidrive.minecraft.instances.<name>.servers.*.name`

- **Type:** string
- **Default:** none; required when used

## Valheim

Valheim mods, for playing on a modded server.

### `famidrive.valheim.bepinex.hash`

Hash of that version's download.

- **Type:** string
- **Default:** `"sha256-vOYxSXl2qTl3zrCOFmcS5sMdFSRJVvifF98JKpti4p8="`

### `famidrive.valheim.bepinex.version`

denikson's BepInExPack_Valheim version.

- **Type:** string
- **Default:** `"5.4.2351"`

### `famidrive.valheim.mods`

Thunderstore packages to play Valheim with, by Author-Name-Version,
each with the hash of its download (leave it "" and the build
error gives the right one). Dependencies aren't added for you: list
them too, as a server's list does. Setting any turns on BepInEx and
Valheim's launch option for it.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    "RandyKnapp-EquipmentAndQuickSlots-3.1.3" = "sha256-…";
    "ValheimModding-Jotunn-2.30.2" = "sha256-…";
  }
  ```

### `famidrive.valheim.onlyListed`

Turn off plugins that aren't listed (they're moved to
BepInEx/plugins-off, not deleted), so the game matches a server's
pack exactly. Off: plugins added by hand stay on.

- **Type:** boolean
- **Default:** `true`

## PC saves

Syncing PC games' saves that Steam Cloud doesn't.

### `famidrive.pcSaves.folders`

Per-game PC save dirs to sync, name -> path. No auto-discovery yet:
PC games keep saves wherever they want (Proton prefix, Documents/, ...),
so this is hand-listed for now.

- **Type:** attribute set of string
- **Default:** `{ }`
- **Example:** 

  ```nix
  {
    cyberpunk = "~/Games/gog/Cyberpunk 2077/saves";
  }
  ```

### `famidrive.pcSaves.peers`

Syncthing device IDs of the owner's other devices (server-side copy included).

- **Type:** attribute set of string
- **Default:** `{ }`

## Online play

Emulator netplay, through the servers in Servers.

### `famidrive.online.enable`

Whether to enable online play for this box's emulators.

- **Type:** boolean
- **Default:** `false`
- **Example:** `true`

## Systems

The systems in ES-DE's menu. FamiDrive fills these in for every console it supports; most boxes never set them.

### `famidrive.systems`

The systems in ES-DE's menu, by ES-DE's folder name for them. Every
console FamiDrive supports is already here (with the `roms` lane);
set one's fields to change it, or add a system of your own.

- **Type:** attribute set of (submodule)
- **Default:** `{ }`

### `famidrive.systems.<name>.after`

Shell run just after the command, outside it. Quitting (Select +
Start) ends the command's whole process group, so anything that
must still happen after a quit (pushing a save) goes here, never
in the command.

- **Type:** strings concatenated with "\n"
- **Default:** `""`

### `famidrive.systems.<name>.before`

Shell run just before the command, outside it.

- **Type:** strings concatenated with "\n"
- **Default:** `""`

### `famidrive.systems.<name>.command`

The emulator's command line. `$ROM` is replaced with the game's path.

- **Type:** string
- **Default:** none; required when used

### `famidrive.systems.<name>.contentCategories`

RomM file categories (its subfolders) pulled along with the game
into its folder, such as a Switch game's `update` and `dlc`.

- **Type:** list of string
- **Default:** `[ ]`

### `famidrive.systems.<name>.emulator`

The emulator's name, sent to RomM with each save so its web UI shows what made it.

- **Type:** null or string
- **Default:** `null`

### `famidrive.systems.<name>.extensions`

File extensions ES-DE lists as games for this system, with the dot.

- **Type:** list of string
- **Default:** `[ ]`

### `famidrive.systems.<name>.firmwareDir`

The folder under the library's `firmware/` this system's firmware
goes to. null: the RomM platform. RetroArch systems share
`retroarch`.

- **Type:** null or string
- **Default:** `null`

### `famidrive.systems.<name>.fullname`

The system's name in ES-DE's menu.

- **Type:** string
- **Default:** none; required when used

### `famidrive.systems.<name>.platform`

ES-DE's platform for it, which picks its scraper.

- **Type:** string
- **Default:** `"pc"`

### `famidrive.systems.<name>.rommPlatform`

The RomM platform (its slug) this system's games come from. null: not from RomM.

- **Type:** null or string
- **Default:** `null`

### `famidrive.systems.<name>.saveLayout`

Where the emulator keeps saves and how a game maps to its save,
for the RomM agent: `{ kind; root; }`, with a kind the agent
knows (`dolphin-gci-folder`, `eden-title-id`, `retroarch-srm`, ...).

- **Type:** null or (attribute set)
- **Default:** `null`

### `famidrive.systems.<name>.saveSync`

Pull each game's save from RomM before it starts and push it back after.

- **Type:** boolean
- **Default:** `false`

### `famidrive.systems.<name>.sortName`

Where it sits in ES-DE's system list, which is otherwise by full name. Never shown. null: the full name.

- **Type:** null or string
- **Default:** `null`

### `famidrive.systems.<name>.theme`

The ES-DE theme folder for its logo and art. null: the platform's.

- **Type:** null or string
- **Default:** `null`

## Everything else

### `famidrive.overlays.performance.enable`

MangoHud's performance overlay (frame rate, frame times, CPU and
GPU load and temperatures) over every game and the menu, through
gamescope's `--mangoapp`. Takes effect at the player's next
session.

- **Type:** boolean
- **Default:** `false`

### `famidrive.overlays.performance.position`

Where the performance overlay shows up.

- **Type:** one of "top-left", "top-center", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-center", "bottom-right"
- **Default:** `"middle-left"`

### `famidrive.overlays.toasts.hide`

Kinds of toast not to show: `"notice"` (a save uploaded and the
like), `"alert"` (something went wrong), `"progress"` (downloads
and other background work), `"achievement"` (RetroAchievements
unlocks). Toasts are always on; this is how to quiet some.

- **Type:** list of (one of "notice", "alert", "progress", "achievement")
- **Default:** `[ ]`

### `famidrive.overlays.toasts.position`

Where toasts show up.

- **Type:** one of "top-left", "top-center", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-center", "bottom-right"
- **Default:** `"bottom-right"`
