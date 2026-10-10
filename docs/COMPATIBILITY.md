# Compatibility

What's been tried on a FamiDrive box, what happened, and what's being done
about it. Add to a game whenever you test it, and keep the old notes when
its status changes: knowing what broke before is half the point.

Each game lists every way it's been run. For a PC game that's each store
or launcher it came through (Steam, GOG, …), since the same game can
behave differently in each. For a console game it's the emulator.

**Status:**

- ✅ **Works**: plays start to finish with a controller, nothing to fix.
- 🟡 **Playable**: plays, with a problem noted.
- ❌ **Broken**: doesn't start, or isn't playable.
- ❔ **Untested**: listed because it's been asked about.

## Contents

- [Test boxes](#test-boxes)
- [Graphics cards](#graphics-cards)
- **Games**
  - [Animal Crossing](#animal-crossing) (GameCube)
  - [Animal Crossing: New Horizons](#animal-crossing-new-horizons) (Switch)
  - [Assassin's Creed Valhalla](#assassins-creed-valhalla) (PC)
  - [Back 4 Blood](#back-4-blood) (PC)
  - [Call of Duty: Black Ops III](#call-of-duty-black-ops-iii) (PC)
  - [Call of Duty: Infinite Warfare](#call-of-duty-infinite-warfare) (PC)
  - [Call of Duty: Modern Warfare Remastered](#call-of-duty-modern-warfare-remastered) (PC)
  - [Call of Duty: WWII](#call-of-duty-wwii) (PC)
  - [Cyberpunk 2077](#cyberpunk-2077) (PC)
  - [DiRT Rally](#dirt-rally) (PC)
  - [DOOM](#doom) (PC)
  - [Fallout: New Vegas](#fallout-new-vegas) (PC)
  - [Gears 5](#gears-5) (PC)
  - [Tom Clancy's Ghost Recon Wildlands](#tom-clancys-ghost-recon-wildlands) (PC)
  - [Grand Theft Auto V](#grand-theft-auto-v) (PC)
  - [Halo: The Master Chief Collection](#halo-the-master-chief-collection) (PC)
  - [Hell Let Loose](#hell-let-loose) (PC)
  - [Helldivers 2](#helldivers-2) (PC)
  - [Hollow Knight](#hollow-knight) (PC)
  - [The Jackbox Party Pack 3](#the-jackbox-party-pack-3) (PC)
  - [The Jackbox Party Pack 6](#the-jackbox-party-pack-6) (PC)
  - [The Legend of Zelda: Breath of the Wild](#the-legend-of-zelda-breath-of-the-wild) (Switch)
  - [The Legend of Zelda: Four Swords Adventures](#the-legend-of-zelda-four-swords-adventures) (GameCube)
  - [Left 4 Dead 2](#left-4-dead-2) (PC)
  - [Mario Kart: Double Dash!!](#mario-kart-double-dash) (GameCube)
  - [Mario Kart 8 Deluxe](#mario-kart-8-deluxe) (Switch)
  - [Mario Party 3](#mario-party-3) (N64)
  - [Mario Party 4 Deluxe](#mario-party-4-deluxe) (GameCube)
  - [Minecraft (vanilla 26.2, a private server)](#minecraft-vanilla-262-a-private-server) (PC)
  - [Need for Speed Heat](#need-for-speed-heat) (PC)
  - [Overwatch](#overwatch) (PC)
  - [Palworld](#palworld) (PC)
  - [Peak](#peak) (PC)
  - [Risk of Rain 2](#risk-of-rain-2) (PC)
  - [Rocket League](#rocket-league) (PC)
  - [Street Fighter 6](#street-fighter-6) (PC)
  - [Star Citizen](#star-citizen) (PC)
  - [Star Wars Jedi: Fallen Order](#star-wars-jedi-fallen-order) (PC)
  - [Star Wars Jedi: Survivor](#star-wars-jedi-survivor) (PC)
  - [Stardew Valley](#stardew-valley) (PC)
  - [Super Mario Odyssey](#super-mario-odyssey) (Switch)
  - [Super Mario Party](#super-mario-party) (Switch)
  - [Super Smash Bros. Brawl](#super-smash-bros-brawl) (Wii)
  - [Super Smash Bros. Melee](#super-smash-bros-melee) (GameCube)
  - [Super Smash Bros. Ultimate](#super-smash-bros-ultimate) (Switch)
  - [Team Fortress 2](#team-fortress-2) (PC)
  - [Titanfall 2](#titanfall-2) (PC)
  - [Tomodachi Life: Living the Dream](#tomodachi-life-living-the-dream) (Switch)
  - [Valheim](#valheim) (PC)
  - [Wii Sports](#wii-sports) (Wii)
- [Known problems across games](#known-problems-across-games)

## Test boxes

Every result below comes from the first box, unless a game says
otherwise.

**The first box:**

| | |
|---|---|
| CPU | AMD Ryzen 9 7900X |
| GPU | AMD Radeon RX 7900 XTX (24 GB) |
| Display | 4K TV, 120 Hz, HDR on (`display.hdr = true`, `display.refresh = 120`) |
| Controllers | 8BitDo Ultimate 2 (2.4 GHz dongle), Xbox Wireless Controller (Bluetooth), DualSense (Bluetooth), a PowerA GameCube-style pad for Switch (USB), first-party Wii Remotes, a Wii guitar on a Raphnet adapter ([CONTROLLERS.md](CONTROLLERS.md)) |
| FamiDrive | `f2b8769` and later, October 2026 |

**The second box:** a small office PC, installed fresh from the README.

| | |
|---|---|
| Model | Dell OptiPlex 3070 Micro |
| CPU | Intel Core i5-9500T (6 cores) |
| GPU | Intel UHD Graphics 630 (integrated) |
| Memory | 16 GB |
| Display | TV over HDMI, 1080p |
| Controllers | Razer Raiju Tournament Edition (USB), a generic wired Xbox 360 pad ([CONTROLLERS.md](CONTROLLERS.md)). No Bluetooth. |
| FamiDrive | main as of 2026-10-08 |

## Graphics cards

Which cards FamiDrive has run on, set with `famidrive.gpu`. On a box,
`famidrive-hardware` lists its cards and the setting to use. AMD and
Intel need nothing chosen (`"auto"`): both use Mesa. Nvidia's driver is
proprietary and has to be set (`"nvidia"`), and a check at boot says so
in the journal when an Nvidia card has no driver.

| Vendor | Driver | Status |
|---|---|---|
| AMD | Mesa (RADV), `amdgpu` | ✅ **Tested.** Radeon RX 7900 XTX on the [first box](#test-boxes): 4K120, HDR, VRR, Steam, every emulator so far. |
| Intel integrated | Mesa (ANV, iris), `i915` | ✅ **Tested** for GameCube. UHD Graphics 630 on the [second box](#test-boxes), at 1080p: ES-DE, and GameCube games played start to finish. Newer consoles and PC games untried; expect it to be too slow for Switch and most Steam games. |
| Intel Arc | Mesa (ANV), `i915` or `xe`, plus Intel's video decoder | ❔ **Untested, should just work.** The same Mesa path as AMD. Some DirectX 12 games run slower on Arc under Proton than on AMD. |
| Nvidia | Nvidia's driver (open kernel module), modesetting, the long-term kernel | ❔ **Untested. Help wanted:** #77 lists what to try. Gamescope, HDR and VRR on Nvidia are the least certain parts. |

## Games

### Animal Crossing

**GameCube, Dolphin: ✅ Works.** With custom textures. The save loads.
Select + Start quits, with a short flicker of Dolphin's window first.

- **The island (Kapp'n's boat):** ❌ not yet. It needs a Game Boy
  Advance linked to the GameCube, which Dolphin can emulate but FamiDrive
  doesn't set up
  ([#132](https://github.com/anultravioletaurora/FamiDrive/issues/132)).

### Animal Crossing: New Horizons

**Switch, Eden: ✅ Works.** Fullscreen with no menu or status bar
(`-f -g`). The save loads; it didn't from Steam's old launcher, likely a
different Eden profile.

### Assassin's Creed Valhalla

**Steam: ❔ Untested.**

- **What to watch for:** the Steam copy starts Ubisoft Connect first,
  which asks for a Ubisoft sign-in inside Proton. Check that sign-in
  with a controller, and that Ubisoft Connect's windows count as the
  game's (`gamescope-fg`), as the EA app's did for Star Wars Jedi:
  Survivor.
- **Other ways people own it:** Ubisoft Connect itself, and Ubisoft+.
  FamiDrive has no Ubisoft Connect lane, so only the Steam copy plays
  for now.
- **To check:** controllers and rumble, HDR, and the shader compile on
  first start.

### Back 4 Blood

**Steam: ✅ Works.** Proton Experimental (Steam's choice), no launch
options.

- **Graphics:** turn the game's own HDR setting off. With it on, colors
  were oversaturated: the sun blinding, shadows too dark to see into.
- **Controllers:** the 8BitDo plays well, rumble included, with Steam
  Input off.

### Call of Duty: Black Ops III

**Steam: ✅ Works.** Proton Experimental (Steam's choice), no launch
options.

- **Performance:** 170–185 fps at 4K with every graphics setting maxed.
- **Controllers:** the Xbox Wireless Controller's rumble works. The
  8BitDo's wasn't checked here; it works in other Steam games
  ([Back 4 Blood](#back-4-blood)).
- **ES-DE:** TheGamesDB's scraper matched it to the 2010 *Call of Duty:
  Black Ops*, so it was listed under that name with that game's details.
  Fixed by re-scraping it in ES-DE. ScreenScraper matches more reliably.
- **Community clients:** not set up. Opt-in support is tracked in #2
  (a BOIII-style client) and #3 (Plutonium, for the older Treyarch
  games).

### Call of Duty: Infinite Warfare

**Steam: ✅ Works.** Proton (Steam's choice), no launch options.

- **2026-10-07:** launched without trouble, Steam's one-time setup
  included. On first start the game asked whether to start in Safe Mode
  and said it had found new hardware; the controller moved between
  the dialogs' buttons fine (No to Safe Mode, Yes to reconfigure). Its
  shaders then compile in the game, once.
- **Modes:** like [WWII](#call-of-duty-wwii), the campaign and Zombies
  run from one program, and multiplayer from another, so expect Steam's
  chooser first.
- **To check:** the campaign past the shaders, multiplayer under Proton,
  rumble in each mode.

### Call of Duty: Modern Warfare Remastered

**Steam: ❔ Untested.** The 2016 remaster, which came with Infinite
Warfare's Legacy Edition.

- **To check:**
  - the campaign, start to finish with a controller
  - multiplayer: whether matchmaking still finds players, and whether
    it lets a Proton player in
  - rumble and aim assist

### Call of Duty: WWII

**Steam: ❔ Untested past its first launch.**

- **2026-10-09, controllers:** the game took the Raphnet adapter (a Wii
  guitar's, for Clone Hero and YARG) as the first controller, so the
  8BitDo didn't drive it. FamiDrive now hides instrument adapters from
  Steam and its games (`controllers.instruments`, #160), while Clone
  Hero and YARG still see them. Not yet tried again.

- **Modes:** the campaign and Nazi Zombies run from one program, and
  multiplayer from another. Steam asks which one to start, so expect
  Steam's own chooser on screen first. FamiDrive shows Steam's prompts
  on top ([Steam launches](#steam-launches)). Check whether the choice can be
  answered with a controller, and whether ES-DE should get one entry
  per mode instead.
- **To check:** multiplayer under Proton (matchmaking and anti-cheat),
  controllers and rumble in each mode.

### Cyberpunk 2077

**Steam: ✅ Works.**

- **Runs on:** GE-Proton7-50, set in Steam.
- **Mods:** ✅ from Nexus Mods collections, installed by FamiDrive
  ([MODDING.md](MODDING.md)). 2026-10-10, on the first box: first
  Welcome to Night City 2.31a (revision 481) in place of Vortex's install,
  then NCR Core 2.31a + NCR – Extras + High-Res Graphics Pack – MAXIMUM
  (5,575 files, 23 GB of archives): "looks preem". redscript compiled
  every script, RED4ext and Cyber Engine Tweaks loaded with no errors.
  The Proton launch option below is still needed.
- **Launch options:** `WINEDLLOVERRIDES="winmm,version=n,b" %command%`,
  set in Steam (or `steam.launchOptions`). Cyber Engine Tweaks and
  RED4ext load through them.
- **Launching:** works. Steam's window shows briefly, then a black screen
  for about 37 s while the game starts, then the game. It used to drop
  back to ES-DE with the game running behind it: Steam swaps the process
  it starts for another, three times in 40 s, and FamiDrive followed only
  the first. Fixed in `ac82a59`. The status screen now covers the wait
  with "Starting" (see [Steam launches](#steam-launches)).
- **Performance:** 2026-10-10, the game's own benchmark on the first
  box, with NCR and the High-Res Graphics Pack – MAXIMUM installed, at
  4K on the TV with every graphics setting at its highest (a custom
  preset) and FSR frame generation on:

  | FSR | Average | Minimum | Maximum |
  |---|---|---|---|
  | Auto | **170 fps** | 142.6 | 203.8 |
  | Quality | **121 fps** | 97.2 | 153.0 |

  Earlier, one unmodded sample with the place in the game unknown: GPU
  50–70% busy at 1.5 GHz and 105 W, 9 GB of video memory, about 7 CPU
  cores busy.

**GOG: ❔ Untested.** The planned home for it: DRM-free, with the
same REDmod support.

### DiRT Rally

**Steam: ❔ Untested.** Which one (DiRT Rally or DiRT Rally 2.0) still to
be noted when it's tried.

- **Racing wheels:** the reason to test it. Both games support wheels
  with force feedback. How wheels work on a FamiDrive box is in
  [CONTROLLERS.md](CONTROLLERS.md#racing-wheels).
- **To check:** a controller first (triggers for throttle and brake,
  rumble), then a wheel if one is around.

### DOOM

The 2016 one.

**Steam: ✅ Works** with an 8BitDo Ultimate 2, with Steam Input on for
it (`famidrive.steam.steamInputGames`).

- **Controllers:** it listens only to the first pad it finds. With
  Steam Input off (FamiDrive's default), the first pad was a Raphnet
  adapter (a guitar's, for YARG) and the 8BitDo did nothing in its menus.
  With Steam Input on, Steam hands it the pads in Steam's own order.
  Instrument adapters are now hidden from Steam games (#160), so it may
  play with Steam Input off too; not yet tried.
- **First launch:** it needed an update, then its install script ran.
  FamiDrive used to ask Steam to launch it again before the script had
  run, and the launch sat on "updating" for hours. Fixed in #118.

### Fallout: New Vegas

**Steam: ✅ Works.** Proton Experimental (Steam's choice), unmodded. The
copy on the first box is the base game only, without the DLC.

**GOG, through Heroic, with NakeyJakey's New Vegas: 🟡 Plays.**
2026-10-10, on the first box: the Ultimate Edition (GOG id
`1454587428`, version 1.4.0.525) with every DLC and the list's 336
mods, on Proton Experimental, reached the main menu and character
creation. The controller worked right away.

- **Typing:** naming the character needed a keyboard and mouse. The PC
  game has no on-screen keyboard; typing from the couch is #119 and #73.
- **How it got there**, after the black screen below:
  - **Restart loop:** the game started, closed, and started again every
    few seconds. Two causes. GE-Proton7-50, Heroic's choice, lacks
    `MSVCP140_ATOMIC_WAIT.dll`, which the list's JohnnyGuitar NVSE needs;
    Proton Experimental has it (Heroic now gets FamiDrive's GE-Proton
    as its default). And the list's `FalloutPrefs.ini` has no `[Display]`,
    so New Vegas found no record of the graphics card
    (`uVideoDeviceIdentifierPart1`–`4`), ran its launcher to detect it,
    and exited; with the launcher swapped for the game, that repeated.
    Bethesda's launcher, run once, wrote all zeros (DXVK's identifier).
    FamiDrive now writes a full `FalloutPrefs.ini` itself.
  - **umu's runtime:** Proton Experimental needs Valve's `steamrt4`, and
    umu's download of it failed its checksum twice; Valve's file was
    fine when fetched by hand.
  - **Registry:** GOG's `Installed Path` value was missing from the
    prefix; FamiDrive sets it now.

- **First launch:** a black screen. Heroic first downloaded GOG's
  runtimes (.NET 4, DirectX, Visual C++) and installed them into a new
  prefix, with no window, for about a minute. Then Bethesda's launcher
  opened, but stayed invisible: Heroic runs the game in Steam's
  pressure-vessel container, which starts a session of its own, and
  FamiDrive only showed windows from the launch's session. FamiDrive now
  shows windows from anything the launch started, and Heroic launches get
  the status screen ("Setting up the game", with the runtimes' download
  as a bar, then "Starting").
- **In the menu:** it showed up in a GOG system of its own, with the
  theme's fallback art (Art Book Next has none for GOG), named
  "Fallout_ New Vegas Ultimate Edition" (a file name can't have a ":"),
  with no details. Heroic's games are now Desktop entries, named and
  described from Heroic's store cache, with its cover and background.

- **Mods:** NakeyJakey's New Vegas, a Wabbajack list of 336 mods, as a
  Nexus Mods collection (`ezlocx`) through FamiDrive (#166,
  [MODDING.md](MODDING.md)). It needs every DLC, so the GOG copy. On
  2026-10-10 its download (26 GB), build (45 GB) and install (58,770
  files, with the 4 GB patch and xNVSE) took 21 minutes on the first
  box, all from a rebuild (#5).

### Gears 5

**Steam: 🟡 Plays.** 2026-10-06: it runs, and controllers work well.
Multiplayer, split-screen, rumble and HDR are still to check.

- **Accounts:** it wants a Microsoft account (Xbox) sign-in for the
  campaign's online parts and for multiplayer. Expect that sign-in on
  first launch, and check whether it can be done with a controller.
- **To check:** whether multiplayer and its anti-cheat run under Proton,
  split-screen co-op, controllers and rumble (it's an Xbox game, so pads
  should be first-class), and HDR.

### Tom Clancy's Ghost Recon Wildlands

**Steam: ✅ Works.** 2026-10-09: played with a DualSense over
Bluetooth, once signed in to Ubisoft Connect.

- **EULA:** Steam shows the game's EULA before the first launch. Accepted
  with the controller as a mouse
  ([Steam's prompts](CONTROLLERS.md#steams-prompts)). Steam then
  processed its Vulkan shaders.
- **Ubisoft Connect** starts first and wants an email and password
  ("Remember me" keeps the sign-in, in this game's Proton prefix only).
  That needs a keyboard for now; an on-screen keyboard is #119.
- **Multiplayer** (co-op, Ghost War) uses BattlEye. Check whether it
  works under Proton.
- **Rumble:** ✅ on a DualSense.
- **Quitting** returns to ES-DE: Ubisoft Connect closes with the game.

### Grand Theft Auto V

**Steam: ❔ Untested.** Story mode and GTA Online are different stories
here.

- **Story mode** should run under Proton. The Steam copy starts the
  Rockstar Games Launcher first, which asks for a Rockstar sign-in;
  check that with a controller, and that the launcher's windows count
  as the game's (`gamescope-fg`).
- **2026-10-07, Enhanced (3240220), first launch:**
  - **Steam's EULA:** Steam showed Rockstar's EULA in a Steam dialog,
    which took only a mouse. FamiDrive now makes the controller work as
    a mouse while Steam waits on a prompt (#117).
  - **Rockstar Games Launcher:** its installer, from the game's install
    script, could be worked with the controller (Proton's own helper
    moves between a Windows dialog's buttons).
  - **To check:** the game itself, the Rockstar sign-in, and controllers
    in game.
- **GTA Online:** expect ❌. Rockstar turned on BattlEye in September
  2024 and blocked Linux and Steam Deck players from GTA Online, and
  that's still the case as far as we know. Try it once and record what
  happens.
- **Enhanced and Legacy:** Steam has had two versions since 2025. Note
  which one is tested.

### Halo: The Master Chief Collection

**Steam: ❔ Untested.**

- **2026-10-07, stopped at sign-in:** the first launch finished its update
  (the status screen's progress was right, after #59), then opened
  Microsoft's sign-in page. A controller could move between its fields,
  but the email field needs a keyboard. Typing from the couch is #73.

- **Anti-cheat:** Steam offers two ways to start it: with Easy
  Anti-Cheat (matchmaking) or with it off (campaigns, custom games,
  mods). That's another Steam chooser on screen before the game. Check
  that both work under Proton, and that matchmaking works with EAC on.
- **To check:** controllers and rumble, split-screen (MCC has it in some
  games, depending on the game and mode), and playing online with a
  Microsoft account sign-in.

### Hell Let Loose

**Steam: ❔ Untested.**

- **Anti-cheat:** it uses Easy Anti-Cheat, and whether the developers
  have turned on EAC's Proton support decides whether it plays at all.
  Check that first.
- **Controllers:** it's built around mouse and keyboard on PC, so check
  how far a controller gets, with Steam Input off and on.

### Helldivers 2

**Steam: ✅ Works.** Proton Experimental (Steam's choice), no launch
options.

- **Launching:** the status screen shows Steam processing its Vulkan
  shaders, with progress, then the game.
- **Controllers:** picked up right away, with Steam Input off. Online
  play works.

### Hollow Knight

**Steam: ✅ Works.** Proton 11.0 (Steam's choice), no launch options.

- **Launching:** FamiDrive's status screen shows, then the game.
- **Controllers:** work as configured, with Steam Input off.

### The Jackbox Party Pack 3

**Steam: ❌ Broken.** Native (Steam Linux Runtime).

- **First launch:** Steam stopped the launch for a 14 MB update
  (`AppError_19`). FamiDrive now waits for the update and asks again.
- **Next launch:** it started, with heavy graphical glitches and
  artifacts.

### The Jackbox Party Pack 6

**Steam: ❌ Broken.** Native (Steam Linux Runtime).

- **First run:** brightness pulsing, from the TV's variable refresh.
  VRR is now off by default (`display.vrr`).
- **Second run:** graphical glitches, then a green screen, then the
  whole box reset itself. Nothing was logged; the cause is unknown.

Don't test it without being ready for a reboot.

### The Legend of Zelda: Breath of the Wild

**Switch, Eden: ✅ Works.** The first save went into Eden's profile, the
same one Animal Crossing: New Horizons and Smash Ultimate use. The
8BitDo's rumble works.

### The Legend of Zelda: Four Swords Adventures

**GameCube, Dolphin: ❔ Untested.** Single player (Hyrulean Adventure)
should play with any pad. Multiplayer needs a Game Boy Advance per
player, linked to the GameCube: Dolphin can emulate them, and FamiDrive
setting them up, with phones as the GBAs, is
[#132](https://github.com/anultravioletaurora/FamiDrive/issues/132).

### Left 4 Dead 2

**Steam: ✅ Works, with Steam Input.** Native (Source engine). Workshop
content loads.

- **Steam Input on, kept on with `steam.steamInputGames`:** menus,
  starting a campaign and shooting all work, and the on-screen prompts
  show the right buttons. Before, with Steam Input on but Steam not
  running the show, prompts for some buttons (D-pad left, D-pad up) read
  "NOT BOUND".
- **Steam Input off:** worse. Controller support had to be turned on in
  the game's options by hand, and even then shooting didn't work.

### Mario Kart: Double Dash!!

**GameCube, Dolphin: ✅ Works.** The 8BitDo's rumble works.

- **2026-10-08, the second box (Intel UHD 630):** ✅ A whole Grand Prix
  with a generic wired Xbox 360 pad, then Select + Start back to ES-DE.

### Mario Kart 8 Deluxe

**Switch, Eden 0.2.1: 🟡 Graphics glitches.** 2026-10-06, with update
3.0.5 and the Booster Course Pass from RomM, played on a save carried
over from Ryujinx with everything unlocked.

- **Glitches:** during a cup, lots of stray textures (spiky polygons)
  cover the track. Menus are fine.
- **Graphics API:** Eden runs on Vulkan (its default).
- **To try:** Eden's GPU accuracy (Normal and High), its asynchronous
  shader option, and OpenGL instead of Vulkan.

### Mario Party 3

**N64, RetroArch (Mupen64Plus-Next): ✅ Works.** The 8BitDo was picked up
right away.

- **Buttons:** with the core's own layout, the 8BitDo's X was the N64's B
  (where B sits on an N64 pad), so X sped through dialog, and the right
  trigger did nothing (the core puts Z on the left trigger only).
  FamiDrive now maps N64 buttons by label (`controllers.faceButtons`), the
  same as GameCube and Switch, and makes both triggers Z. Not yet tried
  that way.

### Mario Party 4 Deluxe

**GameCube, Dolphin: ✅ Works.** A fan-made update of Mario Party 4.
Its ID is `GMPDX2`, but its saves are in Dolphin's `GC/USA`, since that's
what its disc header says.

- **2026-10-08, the second box (Intel UHD 630):** ✅ A save brought over
  from Batocera loaded, with a party in progress on Koopa's Seaside
  Soiree, played with a Razer Raiju. The Raiju stopped responding partway
  through ([CONTROLLERS.md](CONTROLLERS.md#razer-raiju)).

### Minecraft (vanilla 26.2, a private server)

**Prism Launcher: ✅ Works.** Declared in Nix (`minecraft.instances`) and
joins the server straight from launch.

- **Controller:** Controlify, added by FamiDrive. Works perfectly, with
  button prompts that match the pad.
- **Sign-in:** Prism asked to sign in again and showed a code to enter in
  a browser on another device. No keyboard or browser needed on the box.
- **Fullscreen:** opened in a window at first. FamiDrive now starts
  every Prism instance fullscreen; confirmed.

### Need for Speed Heat

**Steam: ✅ Works.** Proton (Steam's choice), no launch options.

- **2026-10-07:** launched without trouble.
  - **First launch:** a one-time setup installs the EA app, and its
    installer could be worked with the controller. Steam then processed
    the game's Vulkan shaders, with the status screen's progress bar
    up, before the game started.
  - **Sign-in:** the player's EA account was already signed in from an
    earlier session ([Titanfall 2](#titanfall-2) as well), so the EA
    app stayed out of the way. A player signing in for the first time
    needs to type in the EA app inside Proton: the on-screen keyboard
    is #73.
  - **Controller:** the 8BitDo Ultimate 2 (2.4 GHz), with Steam Input
    off (FamiDrive's default): the right button glyphs in the game, and
    rumble that works well.
- **Racing wheels:** worth a try once the controller works; see
  [CONTROLLERS.md](CONTROLLERS.md#racing-wheels).
- **To check:** controllers and rumble, online (crews and races with
  friends), and the EA app staying out of the way after sign-in.

### Overwatch

**Steam: ✅ Works.** The Steam copy needs a Battle.net account linked
on first launch, but not the Battle.net app.

- **2026-10-07:** opened without trouble. The 8BitDo Ultimate 2 (2.4 GHz)
  was detected right away, with the right button glyphs in the game's
  UI. The 83 GB download beforehand is what showed that the status
  screen's progress bar was stuck at 0% (fixed in #59).

- **Other launchers:** Battle.net's own copy runs through the Battle.net
  app. FamiDrive has no Battle.net lane yet (#57), so only the Steam copy
  plays for now. One account can play through either.
- **Still to check:** matchmaking, rumble, and a second controller.

### Palworld

**Steam: ❔ Untested.**

- **To check:**
  - controllers and rumble
  - co-op with friends and joining dedicated servers
  - performance with a big base

### Peak

**Steam: ❔ Untested.** Co-op climbing, for up to four players online.

- **To check:** controllers and rumble, joining friends through Steam,
  and voice chat (proximity voice) through the TV's audio and a mic, if
  there is one.

### Risk of Rain 2

**Steam: ❔ Untested.** Windows only, so it runs under Proton.

- **Mods:** Thunderstore, through BepInEx, declared per player with
  `famidrive.players.<name>.thunderstore.games."632360".mods`
  ([MODDING.md](MODDING.md#thunderstore)), which installs BepInEx, the
  mods, and the launch options `WINEDLLOVERRIDES="winhttp=n,b" %command%`
  for that player. Not yet run on a box.
- **To check:** controllers and rumble, online co-op through Steam, and
  modded play with friends who use r2modman.

### Rocket League

**Steam: ✅ Works, with Steam Input off.**

- **Runs on:** Proton Experimental, pinned with `steam.compatTools`.
  Steam still picks the dead native Linux build and swaps the install to
  it (a 40 GB re-download to undo).
- **Launching:** a Steam prompt to use Big Picture with a controller,
  then "processing Vulkan shaders", both visible. Then it launches.
- **Controllers:** with Steam Input on, the 8BitDo wasn't seen at all.
  With it off, every pad works, and split-screen with two works.
- **Player order:** the Xbox controller became player 1, though the
  8BitDo was connected first. Not looked at yet.
- **"Overlay Disabled":** the game warns at start that the platform
  overlay is off. Dismiss it and play. Steam's overlay doesn't come up
  over games in FamiDrive's session yet, so buying in-game items, which
  Steam confirms in its overlay, won't work (2026-10-09).

### Street Fighter 6

**Steam: ✅ Works.** Proton (Steam's default).

- **Controllers:** two players at once (the 8BitDo and an Xbox Wireless
  Controller), each pad seen on its own, with Steam Input on and with it
  off.
- **Launching:** a long wait with Steam's own window on screen. That's
  Steam processing shaders, about 2 minutes on the first launch. The
  game takes 106 GB on disk.

**Other stores:** none known. Street Fighter 6 on PC is sold as Steam
keys only, including on Humble; there's no GOG or DRM-free version.

### Star Citizen

**RSI Launcher: ❔ Untested.** Not on Steam: it's played through Roberts
Space Industries' own launcher, which FamiDrive has no lane for yet.
Tracked with the other launchers in #57.

- **What it needs on Linux:** the community's Linux Users Group keeps
  it running under Wine (their LUG Helper sets it up). It wants a lot of
  memory (16 GB plus swap at the least) and a raised `vm.max_map_count`.
  Easy Anti-Cheat allows Linux for it.
- **Controllers:** it's built for keyboard and mouse or flight sticks. A
  gamepad works but isn't comfortable, so this is a test of how far a
  controller-only box goes.

### Star Wars Jedi: Fallen Order

**Steam: ✅ Works.** 2026-10-10, on the first box: plays really well.

- **EA app:** Steam's copy runs the EA app first, which wants a sign-in
  (a mouse or keyboard for now, #119). The account was already signed in
  from [Jedi: Survivor](#star-wars-jedi-survivor), so it went straight
  through.
- **Steam's controller prompt** came up first (a suggestion to use a
  controller with the game). It was dismissed, and turned off for every
  game, with the controller as a mouse ([Steam's prompts](CONTROLLERS.md#steams-prompts)).
- **To check:** rumble, and quitting back to ES-DE with the EA app still
  running behind.
- **Mods:** Nexus Mods collections, installed by FamiDrive
  ([MODDING.md](MODDING.md)): each mod is a `.pak` file, put in
  `SwGame/Content/Paks`. 2026-10-10: "Better Jedi Fallen Order" (`d3rtf0`,
  revision 2) planned on the first box without its two adult character
  mods (`skip`): 14 files, each where its author says. Not yet played
  modded.

### Star Wars Jedi: Survivor

**Steam: ❔ Untested past its first launch.** Installed remotely through
Steam while the box was in use; ES-DE listed it after the next session
start.

- **First launch:** Steam runs the game's install script first, which
  installs the EA app. Its installer waits on a "Let's go" button, but its
  window wasn't shown, so the status screen sat on "Asking Steam" and
  ES-DE came back after three minutes. FamiDrive now shows an install
  script's windows on top ("Setting up the game") and waits for them.
  The EA app's installer and sign-in want a mouse or keyboard.
- **2026-10-10:** the EA app installer's "Let's go" button couldn't be
  reached with the pad's buttons. With the controller as a mouse it
  went through, but the pointer was tiny at 4K; it's now scaled to the
  screen (`display.cursorScale`, #172). Steam then processed its
  shaders.
- **To check:** playing it, rumble, and quitting back to ES-DE.

### Stardew Valley

**Steam: ❔ Untested.** Native Linux build.

- **Couch co-op:** up to four players on one screen (split-screen),
  which makes it a good fit for a TV box.
- **Mods:** SMAPI, the community's mod loader, also native. Declaring
  SMAPI and mods in Nix, like Valheim's, is worth an issue once the
  plain game is tested.
- **To check:** controllers (one per player in split-screen), rumble,
  and online co-op with friends.

### Super Mario Odyssey

**Switch, Eden: ❔ Untested.** It uses motion controls (shaking to throw
Cappy, and more), which FamiDrive doesn't bind yet
([#133](https://github.com/anultravioletaurora/FamiDrive/issues/133)).
Every move also works with buttons, so it should play without them.

### Super Mario Party

**Switch, Eden: 🟡 Playable, barely.** Each player is meant to hold one
Joy-Con sideways.

- **2026-10, the first box, an 8BitDo Ultimate 2:** the controls came
  up rotated, and the menus were hard to get around. FamiDrive makes
  every player a Pro Controller, and Eden switches a player to a single
  Joy-Con when a game won't take that, so the pad drives a sideways
  Joy-Con as if it were upright. The fix, binding a normal pad as a
  sideways Joy-Con for games like this, is
  [#133](https://github.com/anultravioletaurora/FamiDrive/issues/133).

### Super Smash Bros. Brawl

**Wii, Dolphin: ✅ Works.** Played with the 8BitDo as a GameCube
controller (Brawl takes them; `controllers.gamecube.ports`). Rumble
works.

### Super Smash Bros. Melee

**GameCube, Dolphin: ✅ Works.** Face buttons by label
(`controllers.faceButtons`). The 8BitDo's rumble works.

- **More pads (2026-10-09 and 10):** a DualSense, paired from the couch,
  went straight into a match. The PowerA GameCube-style pad was
  excellent, and its − + quit shortcut worked
  ([CONTROLLERS.md](CONTROLLERS.md#powera-gamecube-style-controller-for-switch)).

- **RetroAchievements:** ✅ achievements unlock, with their toasts
  (2026-10-08). It needs a copy that matches one of RetroAchievements'
  hashes for the game: the first copy on the box didn't ("Unsupported
  Game Version"), and a fresh copy from RomM did.

### Super Smash Bros. Ultimate

**Switch, Eden: ✅ Works.** Face buttons by label.

**Switch, Ryujinx (Ryubing 1.3.3), with HewDraw Remix 0.49.11: ❌ Broken
in matches** (2026-10-07). HDR's menus work: it loads with the player's
save from Eden (Ness already unlocked), on update 13.0.4, with all 99 DLC
(`switch.ryujinx.games`, #88), and character select works with 8 GiB
(#102). Every match then crashes as the stage loads, whoever is picked
(Samus against Kirby on Battlefield, too). This was marked ✅ earlier the
same day from the menus alone. Only the 8BitDo reaches Ryujinx; the
GameCube adapter doesn't show up through its SDL.

- **HewDraw Remix:** a Switch mod kept in RomM (the game's `mod/`
  folder), unpacked once and linked into every player's Eden (#53).
  Opting in per player is #4.
  - 2026-10-06: the zip in RomM was 303 MB, against 1.34 GB for the
    official `switch-package.zip` from HDR's releases. Its `hdr` and
    `hdr-assets` folders were empty, so only HDR's stages would load.
    Use the official zip as it comes.
  - 2026-10-07, Eden 0.2.1: crashes about 4 s in. Eden, like yuzu, can't
    run Skyline plugins, which HDR is built on. FamiDrive now leaves
    Skyline mods out of Eden (#71) and runs Smash in Ryujinx instead
    (`switch.ryujinx.games`, #72).
  - 2026-10-07, Ryubing 1.3.3: Skyline and all six HDR plugins load, and
    HDR's launcher steps aside on an emulator, as it should. Then
    ARCropolis shows an error and the game crashes about 10 s in.
    ARCropolis in HDR 0.49.11 says "cannot currently run on a Smash
    version other than 13.0.4", and RomM had 13.0.1 and 13.0.2. **Needs
    Smash's 13.0.4 update in RomM** (`update/`); FamiDrive picks the
    newest. Along the way: Ryujinx needed the update chosen for it, all
    of Eden's firmware, and controllers named its way (#80).
  - 2026-10-07, with all 99 DLC: the game crashed on the character
    select screen, every time, after `MapPhysicalMemory() =
    LimitReached`. Ryujinx gave it a stock Switch's 4 GiB; started with
    `--no-gui`, Ryujinx ignores Config.json's `dram_size`. FamiDrive now
    passes `--dram-size` (`switch.ryujinx.memory`, 8 GiB, #102), and
    character select works. The DLC files themselves were fine: every
    NCA matched its hash.
  - 2026-10-07, in a match: an invalid memory access in the game's
    `WorkModule::get_param_float`, called through code that isn't the
    game's (HDR's plugins, which Skyline loads). Every run also logs
    `ControlCodeMemory() = InvalidEnumValue` about 4 s in: Ryujinx 1.3.3
    refuses a kind of code-memory call HDR's Smashline plugin makes to
    set up its fighter scripts, which only run once a match starts.
    **Likely needs a newer Ryujinx** (Ryubing's canary builds, through
    `switch.ryujinx.package`). Their site, git.ryujinx.app, was down,
    so that's untried.

### Team Fortress 2

**Steam: ❔ Untested.** Native Linux build (Source engine, 64-bit since
2024). There's no Proton pin unless the native build misbehaves.

- **Controllers:** like [Left 4 Dead 2](#left-4-dead-2), a Source game
  whose controller support leans on Steam Input. It probably needs
  `steam.steamInputGames`. Check with Steam Input off first.
- **To check:** VAC-secured servers, rumble, and the on-screen button
  prompts.

### Titanfall 2

**Steam: ✅ Works.** Proton (Steam's choice), no launch options.

- **2026-10-07:** launched and played.
  - **Dialog on launch:** one dialog to confirm with OK, which the
    controller could tab to and press.
  - **Shaders:** Steam processed them first, with the status screen's
    progress bar up.
  - **EA app:** already signed in, from an earlier session. It showed a
    pop-up with the profile and stayed out of the way.
  - **Controller:** the Xbox Wireless Controller (Bluetooth, xpadneo)
    worked as expected, with every button and the game's UI showing
    Xbox glyphs.
  - **To check:** rumble, and the 8BitDo.

- **2026-10-06, stopped during an update:** launching it started a Steam
  update, which FamiDrive's status screen showed with its progress bar.
  After about 80 minutes it had reached 6.1 GB, although Steam reported
  around 500 Mbps. That speed would have finished in a few minutes, so
  either the reported speed or the update itself was off. Not yet looked
  into: try again, and check Steam's `content_log.txt` for the update's
  real speed and any stalls.
- **Probably explained (2026-10-06):** the status screen's progress
  came from the app manifest's `BytesDownloaded`, which Steam doesn't
  keep current during a download. Overwatch showed the same thing: 0% on
  the TV, 28% in Steam's phone app. The 6.1 GB was likely a stale
  counter, not the real progress. The screen now measures the download
  folder itself (#59).

- **What to watch for:** Steam's copy still needs an EA account. On the
  first launch the EA app installs and asks for a sign-in inside
  Proton. Its install-script windows count as the game's
  (`gamescope-fg`), as they did for Star Wars Jedi: Survivor.
- **Other ways people own it:**
  - The EA app (once Origin).
  - EA Play, which is included in PC Game Pass Ultimate and also runs
    through the EA app.

  FamiDrive has no EA app lane, so those copies can't be played yet.
  EA Play bought through Steam plays as a Steam game.
- **Northstar** (community servers and mods) is #31.

### Tomodachi Life: Living the Dream

**Switch, Eden 0.2.1: ❌ Crashes on a played save.** 2026-10-06, with
update 1.0.3 from RomM.

- **A new save** (one the game created in Eden): it starts.
- **A played save** (one made in Ryujinx with update 1.0.2, with Miis,
  photos and food creations): Eden crashes about 3.5 seconds after
  booting, right after the game opens its save. The log just stops, with
  no error.
- **The save itself looks fine,** and it's kept in RomM.
- **To try:** a newer Eden; the game at 1.0.2, the version the save was
  made with.

### Valheim

**Steam: ✅ Works.**

- **Runs on:** native, with mods through BepInEx.
- **Mods:** declared per player with
  `famidrive.players.<name>.thunderstore.games."892970".mods`
  (Thunderstore ids and hashes, [MODDING.md](MODDING.md#thunderstore)),
  which installs BepInEx, the mods, and the launch options
  `./start_game_bepinex.sh %command%` for that player. Tested on a copy
  of the first box's install; not yet played that way.
- **Graphics:** runs on Vulkan, which the game picks on its own.

### Wii Sports

**Wii, Dolphin: ✅ Works.** Custom textures. Two real Wii Remotes,
connected with 1 + 2, as two players in bowling
(`controllers.wii.remotes = [ "real" … ]`).

## Known problems across games

### Steam launches

ES-DE only knows "a game is running" or "it isn't". Steam has many states
in between. FamiDrive's status screen (`famidrive-status`) covers them:
from the moment a Steam game is picked until its own window is up, it
shows the game's scraped art in the theme's fonts, with what Steam is
doing. The states come from Steam's launch log
(`~/.local/share/Steam/logs/console_log.txt`, `GameAction [AppID …] :
LaunchApp changed task to …`):

| Steam is… | Shown |
|---|---|
| asking for the game | "Asking Steam" |
| downloading an update | "Updating", with a progress bar, speed and time left |
| processing Vulkan shaders | "Processing Vulkan shaders", with a progress bar from Steam's `shader_log.txt` and why it happens. Took up to 5 min 41 s (Left 4 Dead 2). |
| waiting on a prompt (version picker, EULA, controller prompt) | Steam's own window, on top, to answer |
| starting the game, no window yet | "Starting" (Cyberpunk: about 37 s) |
| failing | "Steam couldn't start the game", for five seconds, then ES-DE |

A game counts as started only once Steam's log says so: Steam runs a
game's install script through the same launcher process first, and
taking that for the game sent Rocket League back to ES-DE while Steam
processed its shaders behind it. FamiDrive waits as long as Steam is still working, and only gives up after
two minutes with no progress at all. When Steam fails a launch because the
game needs an update (`AppError_19`), it waits for the update and asks
again. Select + Start gives up at any time. Steam's "Allow background
processing" (Settings → Downloads → Shader Pre-Caching) should mean fewer
shader waits at launch.

### Controllers in Steam games

Steam Input sits between the pad and a game: it hides the real pad and
shows the game a virtual "Microsoft X-Box 360 pad" instead.

**Steam Input is off for every game by default** (`steam.steamInput =
false`): each game reads the pad itself, the same as every emulator does.
FamiDrive sets "Disable Steam Input" on each installed game at the start
of each session. Games that do better with it are listed in
`steam.steamInputGames`.

| Game | Steam Input on | Steam Input off |
|---|---|---|
| Left 4 Dead 2 | works, right prompts: **kept on** | no shooting |
| Rocket League | no pad at all | works, split-screen too |
| Street Fighter 6 | works, two players | works, two players |

### Measuring performance

MangoHud's performance overlay draws over every game and the menu,
through gamescope's `--mangoapp` (as on the Steam Deck). Each player
turns it on in the config (`players.<name>.overlays.performance`, or
`overlays.performance` for the whole box) and picks what it shows (frame
rate, frame time, CPU and GPU load and temperatures, memory and graphics
memory), where, and whether as a column or one row (#165). It takes
effect at their next session.

- **Not yet:** switching it on or off from the controller, and a log of
  it readable over SSH.
- **Games' own benchmarks** are the other measure: see
  [Cyberpunk 2077](#cyberpunk-2077).
