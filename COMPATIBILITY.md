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
  - [Assassin's Creed Valhalla](#assassins-creed-valhalla) (PC)
  - [Back 4 Blood](#back-4-blood) (PC)
  - [Call of Duty: Black Ops III](#call-of-duty-black-ops-iii) (PC)
  - [Call of Duty: Infinite Warfare](#call-of-duty-infinite-warfare) (PC)
  - [Call of Duty: Modern Warfare Remastered](#call-of-duty-modern-warfare-remastered) (PC)
  - [Call of Duty: WWII](#call-of-duty-wwii) (PC)
  - [Cyberpunk 2077](#cyberpunk-2077) (PC)
  - [DiRT Rally](#dirt-rally) (PC)
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
  - [Left 4 Dead 2](#left-4-dead-2) (PC)
  - [Mario Kart: Double Dash!!](#mario-kart-double-dash) (GameCube)
  - [Mario Kart 8 Deluxe](#mario-kart-8-deluxe) (Switch)
  - [Mario Party 3](#mario-party-3) (N64)
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
  - [Super Smash Bros. Brawl](#super-smash-bros-brawl) (Wii)
  - [Super Smash Bros. Melee](#super-smash-bros-melee) (GameCube)
  - [Super Smash Bros. Ultimate](#super-smash-bros-ultimate) (Switch)
  - [Team Fortress 2](#team-fortress-2) (PC)
  - [Titanfall 2](#titanfall-2) (PC)
  - [Tomodachi Life: Living the Dream](#tomodachi-life-living-the-dream) (Switch)
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
| Controllers | 8BitDo Ultimate 2 (2.4 GHz dongle), Xbox Wireless Controller (Bluetooth), first-party Wii Remotes ([CONTROLLERS.md](CONTROLLERS.md)) |
| FamiDrive | `f2b8769` and later, October 2026 |

## Games

### Animal Crossing

**GameCube, Dolphin: ✅ Works.** With custom textures. The save loads.
Select + Start quits, with a short flicker of Dolphin's window first.

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

**Steam: ❔ Untested.**

- **Modes:** like [WWII](#call-of-duty-wwii), the campaign and Zombies
  run from one program, and multiplayer from another, so expect Steam's
  chooser first.
- **To check:** multiplayer under Proton, controllers and rumble in each
  mode.

### Call of Duty: Modern Warfare Remastered

**Steam: ❔ Untested.** The 2016 remaster, which came with Infinite
Warfare's Legacy Edition.

- **To check:**
  - the campaign, start to finish with a controller
  - multiplayer: whether matchmaking still finds players, and whether
    it lets a Proton player in
  - rumble and aim assist

### Call of Duty: WWII

**Steam: ❔ Untested.**

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
- **Mods:** through Vortex: Cyber Engine Tweaks, RED4ext and archive
  mods all load. Declaring them in Nix is tracked in #6.
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

### DiRT Rally

**Steam: ❔ Untested.** Which one (DiRT Rally or DiRT Rally 2.0) still to
be noted when it's tried.

- **Racing wheels:** the reason to test it. Both games support wheels
  with force feedback. How wheels work on a FamiDrive box is in
  [CONTROLLERS.md](CONTROLLERS.md#racing-wheels).
- **To check:** a controller first (triggers for throttle and brake,
  rumble), then a wheel if one is around.

### Fallout: New Vegas

**Steam: ✅ Works.** Proton Experimental (Steam's choice), unmodded.

- **Mods:** not set up. NakeyJakey's New Vegas (a Wabbajack list of
  about 335 mods) is the one wanted; tracked in #5.

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

**Steam: ❔ Untested.**

- **Ubisoft Connect** starts first and wants a sign-in, like the EA app
  for EA's games. Expect the same first-launch hurdles: its installer and
  sign-in window, probably wanting a mouse or keyboard
  ([Star Wars Jedi: Survivor](#star-wars-jedi-survivor)).
- **Multiplayer** (co-op, Ghost War) uses BattlEye. Check whether it
  works under Proton.
- **To check:** controllers and rumble, and whether Ubisoft Connect
  closes when the game does, so that quitting returns to ES-DE.

### Grand Theft Auto V

**Steam: ❔ Untested.** Story mode and GTA Online are different stories
here.

- **Story mode** should run under Proton. The Steam copy starts the
  Rockstar Games Launcher first, which asks for a Rockstar sign-in;
  check that with a controller, and that the launcher's windows count
  as the game's (`gamescope-fg`).
- **GTA Online:** expect ❌. Rockstar turned on BattlEye in September
  2024 and blocked Linux and Steam Deck players from GTA Online, and
  that's still the case as far as we know. Try it once and record what
  happens.
- **Enhanced and Legacy:** Steam has had two versions since 2025. Note
  which one is tested.

### Halo: The Master Chief Collection

**Steam: ❔ Untested.**

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

### Mario Kart 8 Deluxe

**Switch, Eden 0.2.1: 🟡 Graphics glitches.** 2026-10-06, with update
3.0.5 and the Booster Course Pass from RomM, played on a save carried
over from Ryujinx with everything unlocked.

- **Glitches:** during a cup, lots of stray textures (spiky polygons)
  cover the track. Menus are fine.
- **To try:** Eden's GPU accuracy (Normal and High), its asynchronous
  shader option, and Vulkan against OpenGL.

### Mario Party 3

**N64, RetroArch (Mupen64Plus-Next): ✅ Works.** The 8BitDo was picked up
right away.

- **Buttons:** with the core's own layout, the 8BitDo's X was the N64's B
  (where B sits on an N64 pad), so X sped through dialog, and the right
  trigger did nothing (the core puts Z on the left trigger only).
  FamiDrive now maps N64 buttons by label (`controllers.faceButtons`), the
  same as GameCube and Switch, and makes both triggers Z. Not yet tried
  that way.

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

**Steam: ❔ Untested.**

- **What to watch for:** the Steam copy goes through the EA app, which
  installs and asks for an EA sign-in inside Proton on first launch, as
  with [Titanfall 2](#titanfall-2).
- **Racing wheels:** worth a try once the controller works; see
  [CONTROLLERS.md](CONTROLLERS.md#racing-wheels).
- **To check:** controllers and rumble, online (crews and races with
  friends), and the EA app staying out of the way after sign-in.

### Overwatch

**Steam: ❔ Untested.** The Steam copy needs a Battle.net account linked
on first launch, but not the Battle.net app.

- **Other launchers:** Battle.net's own copy runs through the Battle.net
  app. FamiDrive has no Battle.net lane, so only the Steam copy plays for
  now. A Battle.net lane is worth an issue if this goes well. One account
  can play through either.
- **To check:**
  - the Battle.net account link with a controller
  - matchmaking under Proton
  - controllers and rumble (Overwatch has full console-style controller
    support)
  - the shader compile on first start

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

- **Mods:** Thunderstore, through BepInEx, the same as Valheim. FamiDrive
  already declares Valheim's mods in Nix (`famidrive.valheim.mods`); the
  same could work here. Worth an issue once the plain game is tested.
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

**Steam: ❔ Untested.** Expect the same EA hurdle as
[Jedi: Survivor](#star-wars-jedi-survivor): Steam's copy runs the EA app
first, which installs and asks for a sign-in. FamiDrive shows its windows
now, but they want a mouse or keyboard.

- **To check:** whether the EA app gets out of the way after the first
  sign-in, controllers and rumble, and quitting back to ES-DE with the EA
  app still running behind.

### Star Wars Jedi: Survivor

**Steam: ⚠️ In progress.** Installed remotely through Steam while the box
was in use; ES-DE listed it after the next session start.

- **First launch:** Steam runs the game's install script first, which
  installs the EA app. Its installer waits on a "Let's go" button, but its
  window wasn't shown, so the status screen sat on "Asking Steam" and
  ES-DE came back after three minutes. FamiDrive now shows an install
  script's windows on top ("Setting up the game") and waits for them.
  The EA app's installer and sign-in want a mouse or keyboard.

### Stardew Valley

**Steam: ❔ Untested.** Native Linux build.

- **Couch co-op:** up to four players on one screen (split-screen),
  which makes it a good fit for a TV box.
- **Mods:** SMAPI, the community's mod loader, also native. Declaring
  SMAPI and mods in Nix, like Valheim's, is worth an issue once the
  plain game is tested.
- **To check:** controllers (one per player in split-screen), rumble,
  and online co-op with friends.

### Super Smash Bros. Brawl

**Wii, Dolphin: ✅ Works.** Played with the 8BitDo as a GameCube
controller (Brawl takes them; `controllers.gamecube.ports`). Rumble
works.

### Super Smash Bros. Melee

**GameCube, Dolphin: ✅ Works.** Face buttons by label
(`controllers.faceButtons`). The 8BitDo's rumble works.

### Super Smash Bros. Ultimate

**Switch, Eden: ✅ Works.** Face buttons by label.

- **HewDraw Remix:** a Switch mod kept in RomM (the game's `mod/`
  folder), unpacked once and linked into every player's Eden (#53).
  Opting in per player is #4.
  - 2026-10-06: the zip in RomM was 303 MB, against 1.34 GB for the
    official `switch-package.zip` from HDR's releases. Its `hdr` and
    `hdr-assets` folders were empty, so only HDR's stages would load.
    Use the official zip as it comes.
  - First try with the official zip, on Eden 0.2.1 with RomM's updates
    (13.0.1 and 13.0.2) and every DLC: ❔ result to come.

### Team Fortress 2

**Steam: ❔ Untested.** Native Linux build (Source engine, 64-bit since
2024). There's no Proton pin unless the native build misbehaves.

- **Controllers:** like [Left 4 Dead 2](#left-4-dead-2), a Source game
  whose controller support leans on Steam Input. It probably needs
  `steam.steamInputGames`. Check with Steam Input off first.
- **To check:** VAC-secured servers, rumble, and the on-screen button
  prompts.

### Titanfall 2

**Steam: ❔ Untested.** First try on 2026-10-06: a fresh install and first
launch with no changes for this game, then controllers and rumble.

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
- **Mods:** declared with `famidrive.valheim.mods` (Thunderstore ids
  and hashes), which installs BepInEx, the mods, and the launch option
  `./start_game_bepinex.sh %command%`. Tested on a copy of the first
  box's install; not yet played that way.
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
