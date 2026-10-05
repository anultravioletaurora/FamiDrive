# Compatibility

What's been tried on a FamiDrive box, what happened, and what's being done
about it. Games are in alphabetical order. Add a line whenever you test
something, and keep the old notes when a status changes: knowing what broke
before is half the point.

**Status:**

- ✅ **Works**: plays start to finish with a controller, nothing to fix.
- 🟡 **Playable**: plays, with a problem noted.
- ❌ **Broken**: doesn't start, or isn't playable.
- ❔ **Untested**: listed because it's been asked about.

## Test box

The box every result below comes from, unless a row says otherwise.

| | |
|---|---|
| CPU | AMD Ryzen 9 7900X |
| GPU | AMD Radeon RX 7900 XTX (24 GB) |
| Display | 4K TV, 120 Hz, HDR on (`display.hdr = true`, `display.refresh = 120`) |
| Controller | 8BitDo Ultimate 2, 2.4 GHz dongle |
| FamiDrive | the uncommitted work after `08fb472`, October 2026 |

## Games

| Game | System | Status | Runs on | Notes |
|---|---|---|---|---|
| Animal Crossing | GameCube | ✅ | Dolphin | Custom textures. The save loads. Select + Start quits, with a short flicker of Dolphin's window first. |
| Animal Crossing: New Horizons | Switch | ✅ | Eden | Fullscreen with no menu or status bar since `-f -g`. The save loads. |
| Cyberpunk 2077 | Steam | 🟡 | GE-Proton7-50 (pinned in Steam), mods through Vortex | Mods load (Cyber Engine Tweaks, RED4ext, archive mods). Its launch option is `WINEDLLOVERRIDES="winmm,version=n,b" %command%`. About 37 s pass between Steam starting it and its first window, and ES-DE shows meanwhile, so it looks like it failed (see [Steam launches](#steam-launches)). Frame rate not measured yet (see [Measuring performance](#measuring-performance)). |
| The Jackbox Party Pack 3 | Steam | ❌ | native (Steam Linux Runtime) | First launch: Steam stopped the launch for a 14 MB update (`AppError_19`). FamiDrive now waits for the update and asks again. Then it launched with heavy graphical glitches and artifacts. |
| The Jackbox Party Pack 6 | Steam | ❌ | native (Steam Linux Runtime) | First run: brightness pulsing, from variable refresh on the TV; VRR is now off by default (`display.vrr`). Second run: graphical glitches, then a green screen, then the whole box reset itself. Nothing in the logs, so the cause is unknown. Don't test it without being ready for a reboot. |
| Rocket League | Steam | 🟡 | Proton Experimental (`steam.compatTools`) | Steam still picks the dead native Linux build and swaps the install to it, so it's pinned to Proton. Launches after a Steam prompt to use a controller and a "processing Vulkan shaders" step. **The 8BitDo isn't seen in-game**; Select + Start still quits. |
| Street Fighter 6 | Steam | ❔ | Proton (Steam's default) | Launched, but was started by mistake while Cyberpunk was loading and both ran at once. Not looked at yet. |
| Super Smash Bros. Melee | GameCube | ✅ | Dolphin | Face buttons by label (`controllers.faceButtons`). |
| Super Smash Bros. Ultimate | Switch | ✅ | Eden | Face buttons by label. |
| Valheim | Steam | ✅ | native, mods through BepInEx | Launch option `./start_game_bepinex.sh \|\| %command%`. Runs on Vulkan, which the game picks on its own. |

## Known problems across games

### Steam launches

ES-DE only knows "a game is running" or "it isn't". Steam has many states
in between, and today most of them look like a black screen or like ES-DE
came back:

- **Updating:** a game that needs an update first. Small updates are now
  waited for. Big ones still look like a black screen for up to five
  minutes.
- **Processing shaders:** Steam shows its own window for this. It's
  visible since Steam's windows are allowed above ES-DE while a launch is
  pending.
- **Waiting for an answer:** a first-launch prompt such as "which
  version?", a EULA, or the controller prompt. Visible for the same reason.
  These are desktop-style Steam windows, not made for a controller.
- **Started, but no window yet:** Cyberpunk takes about 37 s. ES-DE shows
  and accepts input meanwhile, so a second game can be started on top of
  the first. That's how Cyberpunk and Street Fighter 6 ended up running
  at once.

Planned: a FamiDrive status screen in ES-DE's look ("Updating Rocket
League: 18 of 40 GB", "Processing shaders", "Starting Cyberpunk 2077…")
that stays up from the moment a game is chosen until its window appears,
and that never hands control back to ES-DE while Steam still has the game.
Steam's launch steps are in `~/.local/share/Steam/logs/console_log.txt`
(`GameAction [AppID …] : LaunchApp changed task to …`).

### Controllers in Proton games

Steam Input sits between the pad and Proton games: it hides the 8BitDo and
shows the game a virtual "Microsoft X-Box 360 pad" instead. In Rocket
League the game saw neither. Not looked at yet.

### Measuring performance

There's no frame-rate counter yet. MangoHud is installed. Planned: a
performance overlay that can be switched on from the controller, through
gamescope's `--mangoapp` (as on the Steam Deck), plus a log that can be
read over SSH.
