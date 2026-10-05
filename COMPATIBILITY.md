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
  - [Cyberpunk 2077](#cyberpunk-2077) (PC)
  - [The Jackbox Party Pack 3](#the-jackbox-party-pack-3) (PC)
  - [The Jackbox Party Pack 6](#the-jackbox-party-pack-6) (PC)
  - [Left 4 Dead 2](#left-4-dead-2) (PC)
  - [Rocket League](#rocket-league) (PC)
  - [Street Fighter 6](#street-fighter-6) (PC)
  - [Super Smash Bros. Melee](#super-smash-bros-melee) (GameCube)
  - [Super Smash Bros. Ultimate](#super-smash-bros-ultimate) (Switch)
  - [Valheim](#valheim) (PC)
- [Known problems across games](#known-problems-across-games)

## Test box

Every result below comes from this box, unless a game says otherwise.

| | |
|---|---|
| CPU | AMD Ryzen 9 7900X |
| GPU | AMD Radeon RX 7900 XTX (24 GB) |
| Display | 4K TV, 120 Hz, HDR on (`display.hdr = true`, `display.refresh = 120`) |
| Controller | 8BitDo Ultimate 2, 2.4 GHz dongle |
| FamiDrive | `f2b8769` and later, October 2026 |

## Games

### Animal Crossing

**GameCube, Dolphin: ✅ Works.** With custom textures. The save loads.
Select + Start quits, with a short flicker of Dolphin's window first.

### Animal Crossing: New Horizons

**Switch, Eden: ✅ Works.** Fullscreen with no menu or status bar
(`-f -g`). The save loads; it didn't from Steam's old launcher, likely a
different Eden profile.

### Cyberpunk 2077

**Steam: 🟡 Playable.**

- **Runs on:** GE-Proton7-50, set in Steam.
- **Mods:** through Vortex: Cyber Engine Tweaks, RED4ext and archive
  mods all load.
- **Launch options:** `WINEDLLOVERRIDES="winmm,version=n,b" %command%`.
- **Launching:** about 37 s pass between Steam starting it and its first
  window. Until `f2b8769`, a closing launcher window could crash
  FamiDrive's launcher, and ES-DE came back over the loading game. That's
  fixed but not yet retested. Picking it again in ES-DE now brings back
  the running game instead of starting another.
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

**Steam: 🟡 Playable.** Native (Source engine). Workshop content loads.
Some on-screen controller prompts show "NOT BOUND" instead of a button.
Probably the game showing Steam Input's action names when it can't match
a binding to them. Not looked at yet.

### Rocket League

**Steam: 🟡 Playable.**

- **Runs on:** Proton Experimental, pinned with `steam.compatTools`.
  Steam still picks the dead native Linux build and swaps the install to
  it (a 40 GB re-download to undo).
- **Launching:** a Steam prompt to use Big Picture with a controller,
  then "processing Vulkan shaders", both visible. Then it launches.
- **Controller: the 8BitDo isn't seen in-game.** Select + Start still
  quits. Steam Input is forced on for this game
  (`UseSteamControllerConfig = 2`), a per-game override from before
  FamiDrive. FamiDrive's design is to not use Steam Input at all (see
  [Controllers in Steam games](#controllers-in-steam-games)).

### Street Fighter 6

**Steam: ✅ Works.** Proton (Steam's default).

- **Controllers:** two players at once (the 8BitDo and an Xbox Wireless
  Controller) mapped straight away with no setup. Steam Input was on and
  gave the game two virtual pads.
- **Launching:** a long wait with Steam's own window on screen. That's
  Steam processing shaders: about 2 minutes on the first launch. The
  game takes 106 GB on disk.
- **First test:** it was started by mistake while Cyberpunk was
  loading, and both ran at once. That launcher bug is fixed in `f2b8769`.

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

## Known problems across games

### Steam launches

ES-DE only knows "a game is running" or "it isn't". Steam has many states
in between, and today most of them look like a black screen:

- **Updating:** a game that needs an update first. Small updates are
  waited for. Big ones look like a black screen for up to five minutes.
- **Processing shaders:** Steam's own window, shown since `f2b8769`.
- **Waiting for an answer:** a first-launch prompt such as "which
  version?", a EULA or the controller prompt. Shown since `f2b8769`, but
  these are desktop-style Steam windows, not made for a controller.
- **Started, no window yet:** Cyberpunk takes about 37 s, a black screen
  meanwhile.

Planned: a FamiDrive status screen in ES-DE's look ("Updating Rocket
League: 18 of 40 GB", "Processing shaders", "Starting Cyberpunk 2077…")
from the moment a game is chosen until its window appears. Steam's
launch steps are in `~/.local/share/Steam/logs/console_log.txt`
(`GameAction [AppID …] : LaunchApp changed task to …`).

### Controllers in Steam games

Steam Input sits between the pad and a game: it hides the real pad and
shows the game a virtual "Microsoft X-Box 360 pad" instead.

- **Street Fighter 6:** worked through it, two players with no setup.
- **Rocket League:** saw nothing. It's the one game with Steam Input
  forced on by a per-game setting from before FamiDrive
  (`UseSteamControllerConfig = 2` in Steam's `localconfig.vdf`).
- **Left 4 Dead 2:** "NOT BOUND" prompts, possibly Steam Input related.

So Steam Input isn't broken across the board, and turning it off
everywhere isn't decided. Next test: turn it off for Rocket League (Steam
Settings → the game → Properties → Controller). The original plan was to
leave Steam Input out and let each game read the pad itself. That's still
the fallback if more games behave like Rocket League.

### Measuring performance

There's no frame-rate counter yet. MangoHud is installed. Planned: a
performance overlay switched on from the controller, through gamescope's
`--mangoapp` (as on the Steam Deck), plus a log readable over SSH.
