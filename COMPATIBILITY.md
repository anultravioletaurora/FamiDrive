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

- [Test box](#test-box)
- **Games**
  - [Animal Crossing](#animal-crossing) (GameCube)
  - [Animal Crossing: New Horizons](#animal-crossing-new-horizons) (Switch)
  - [Call of Duty: Black Ops III](#call-of-duty-black-ops-iii) (PC)
  - [Cyberpunk 2077](#cyberpunk-2077) (PC)
  - [The Jackbox Party Pack 3](#the-jackbox-party-pack-3) (PC)
  - [The Jackbox Party Pack 6](#the-jackbox-party-pack-6) (PC)
  - [Left 4 Dead 2](#left-4-dead-2) (PC)
  - [Minecraft (vanilla 26.2, a private server)](#minecraft-vanilla-262-a-private-server) (PC)
  - [Rocket League](#rocket-league) (PC)
  - [Street Fighter 6](#street-fighter-6) (PC)
  - [Super Smash Bros. Melee](#super-smash-bros-melee) (GameCube)
  - [Super Smash Bros. Ultimate](#super-smash-bros-ultimate) (Switch)
  - [Valheim](#valheim) (PC)
  - [Wii Sports](#wii-sports) (Wii)
- [Known problems across games](#known-problems-across-games)

## Test box

Every result below comes from this box, unless a game says otherwise.

| | |
|---|---|
| CPU | AMD Ryzen 9 7900X |
| GPU | AMD Radeon RX 7900 XTX (24 GB) |
| Display | 4K TV, 120 Hz, HDR on (`display.hdr = true`, `display.refresh = 120`) |
| Controllers | 8BitDo Ultimate 2 (2.4 GHz dongle), Xbox Wireless Controller (Bluetooth), first-party Wii Remotes |
| FamiDrive | `f2b8769` and later, October 2026 |

## Games

### Animal Crossing

**GameCube, Dolphin: ✅ Works.** With custom textures. The save loads.
Select + Start quits, with a short flicker of Dolphin's window first.

### Animal Crossing: New Horizons

**Switch, Eden: ✅ Works.** Fullscreen with no menu or status bar
(`-f -g`). The save loads; it didn't from Steam's old launcher, likely a
different Eden profile.

### Call of Duty: Black Ops III

**Steam: ✅ Works.** Proton Experimental (Steam's choice), no launch
options.

- **Performance:** 170–185 fps at 4K with every graphics setting maxed.
- **Controllers:** the Xbox Wireless Controller's rumble works. The
  8BitDo's rumble isn't checked yet.
- **ES-DE:** TheGamesDB's scraper matched it to the 2010 *Call of Duty:
  Black Ops*, so it was listed under that name with that game's details.
  Fixed by re-scraping it in ES-DE. ScreenScraper matches more reliably.
- **Community clients:** not set up. Opt-in support is tracked in #2
  (a BOIII-style client) and #3 (Plutonium, for the older Treyarch
  games).

### Cyberpunk 2077

**Steam: ✅ Works.**

- **Runs on:** GE-Proton7-50, set in Steam.
- **Mods:** through Vortex: Cyber Engine Tweaks, RED4ext and archive
  mods all load.
- **Launch options:** `WINEDLLOVERRIDES="winmm,version=n,b" %command%`.
- **Launching:** works. Steam's window shows briefly, then a black screen
  for about 37 s while the game starts, then the game. It used to drop
  back to ES-DE with the game running behind it: Steam swaps the process
  it starts for another, three times in 40 s, and FamiDrive followed only
  the first. Fixed in `ac82a59`. The black wait is the planned status
  screen's job (see [Steam launches](#steam-launches)).
- **Performance:** frame rate not measured yet (see
  [Measuring performance](#measuring-performance)). One sample, place in
  the game unknown: GPU 50–70% busy at 1.5 GHz and 105 W, 9 GB of video
  memory, the game using about 7 CPU cores. That looks capped (menu,
  pause or a frame limit) or CPU-bound, not GPU-bound.

**GOG: ❔ Untested.** The planned home for it: DRM-free, with the
same REDmod support.

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

### Minecraft (vanilla 26.2, a private server)

**Prism Launcher: ✅ Works.** Declared in Nix (`minecraft.instances`) and
joins the server straight from launch.

- **Controller:** Controlify, added by FamiDrive. Works perfectly, with
  button prompts that match the pad.
- **Sign-in:** Prism asked to sign in again and showed a code to enter in
  a browser on another device. No keyboard or browser needed on the box.
- **Fullscreen:** opened in a window at first. FamiDrive now starts
  every Prism instance fullscreen; confirmed.

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

### Super Smash Bros. Melee

**GameCube, Dolphin: ✅ Works.** Face buttons by label
(`controllers.faceButtons`).

### Super Smash Bros. Ultimate

**Switch, Eden: ✅ Works.** Face buttons by label.

### Valheim

**Steam: ✅ Works.**

- **Runs on:** native, with mods through BepInEx.
- **Launch options:** `./start_game_bepinex.sh || %command%`.
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

There's no frame-rate counter yet. MangoHud is installed. Planned: a
performance overlay switched on from the controller, through gamescope's
`--mangoapp` (as on the Steam Deck), plus a log readable over SSH.
