# FamiDrive

**A 10,000-in-1 Declarative System**

FamiDrive is a free, TV-first game console you build out of NixOS. It boots
straight into [ES-DE](https://es-de.org), runs inside
[gamescope](https://github.com/ValveSoftware/gamescope), and puts every
console emulator, your Steam, GOG, Epic and Amazon games, Minecraft and
Jellyfin behind one controller-driven menu. Nothing about the box is set up by hand: the
emulators, their settings, the menu and where every game comes from are
all one Nix flake. Your ROMs, firmware and saves can live in your own
[RomM](https://github.com/rommapp/romm) server, so any number of boxes,
including ones outside your house, are just more clients of the same
library, and RomM's web UI is where you manage it. RomM is optional: a
box can also play ROM folders already on its own disks.

It exists because a console where Steam is the whole interface makes
everything that isn't a Steam game a guest: emulators get imported as
Steam shortcuts, saves outside Steam Cloud need their own backup scheme,
and Steam Input sits in front of every controller whether a game wants it
or not. FamiDrive keeps the good part, a box that boots into a console UI
and never needs a desktop, and makes Steam just one entry on the menu.

> **Status: early.** FamiDrive runs on its first box: it boots into ES-DE
> at 4K120 with HDR, and GameCube and Switch games launch, take focus and
> quit back to the menu from the controller. Steam games launch, with rough
> edges. RomM sync works for GameCube, Wii, Switch and Clone Hero; most of
> the other emulators haven't been tried yet. See
> [Status](#status) for what's real and what's a placeholder, and
> [COMPATIBILITY.md](COMPATIBILITY.md) for game-by-game results.

FamiDrive is for games you legally own, and for backups you made yourself
of games you own. See [Your games](#your-games).


## What's in the box

| System | Plays with | nixpkgs | Save sync | Where the games come from |
|---|---|---|---|---|
| Game Boy / Color / Advance | [RetroArch](https://www.retroarch.com) + [mGBA](https://mgba.io) | [`libretro.mgba`](https://search.nixos.org/packages?channel=26.05&show=libretro.mgba) | ✅ | RomM |
| SNES | [RetroArch](https://www.retroarch.com) + [Snes9x](https://www.snes9x.com) | [`libretro.snes9x`](https://search.nixos.org/packages?channel=26.05&show=libretro.snes9x) | ✅ | RomM |
| Nintendo 64 | [RetroArch](https://www.retroarch.com) + [Mupen64Plus-Next](https://github.com/libretro/mupen64plus-libretro-nx) | [`libretro.mupen64plus`](https://search.nixos.org/packages?channel=26.05&show=libretro.mupen64plus) | ✅ | RomM |
| Nintendo 64DD | [RetroArch](https://www.retroarch.com) + [Mupen64Plus-Next](https://github.com/libretro/mupen64plus-libretro-nx) | [`libretro.mupen64plus`](https://search.nixos.org/packages?channel=26.05&show=libretro.mupen64plus) | — | RomM |
| DS / DSi | [RetroArch](https://www.retroarch.com) + [melonDS DS](https://github.com/JesseTG/melonds-ds) | [`libretro.melondsds`](https://search.nixos.org/packages?channel=26.05&show=libretro.melondsds) | — | RomM |
| 3DS / New 3DS | [Azahar](https://azahar-emu.org) | [`azahar`](https://search.nixos.org/packages?channel=26.05&show=azahar) | — | RomM |
| GameCube / Wii | [Dolphin](https://dolphin-emu.org) | [`dolphin-emu`](https://search.nixos.org/packages?channel=26.05&show=dolphin-emu) | ✅ | RomM |
| Wii U | [Cemu](https://cemu.info) | [`cemu`](https://search.nixos.org/packages?channel=26.05&show=cemu) | — | RomM |
| Switch | [Eden](https://eden-emu.dev), or [Ryubing](https://ryujinx.app) (Ryujinx) for the games listed in `switch.ryujinx.games` | [`eden`](https://search.nixos.org/packages?channel=unstable&show=eden), [`ryubing`](https://search.nixos.org/packages?channel=26.05&show=ryubing) | ✅ | RomM, with each game's update and DLC |
| Genesis / Master System / Game Gear | [RetroArch](https://www.retroarch.com) + [Genesis Plus GX](https://github.com/libretro/Genesis-Plus-GX) | [`libretro.genesis-plus-gx`](https://search.nixos.org/packages?channel=26.05&show=libretro.genesis-plus-gx) | ✅ | RomM |
| Saturn | [RetroArch](https://www.retroarch.com) + [Beetle Saturn](https://github.com/libretro/beetle-saturn-libretro) | [`libretro.beetle-saturn`](https://search.nixos.org/packages?channel=26.05&show=libretro.beetle-saturn) | — | RomM |
| Dreamcast | [RetroArch](https://www.retroarch.com) + [Flycast](https://github.com/flyinghead/flycast) | [`libretro.flycast`](https://search.nixos.org/packages?channel=26.05&show=libretro.flycast) | — | RomM |
| PlayStation | [RetroArch](https://www.retroarch.com) + [SwanStation](https://github.com/libretro/swanstation) | [`libretro.swanstation`](https://search.nixos.org/packages?channel=26.05&show=libretro.swanstation) | ✅ | RomM |
| PlayStation 2 | [PCSX2](https://pcsx2.net) | [`pcsx2`](https://search.nixos.org/packages?channel=26.05&show=pcsx2) | ✅ | RomM |
| PlayStation 3 | [RPCS3](https://rpcs3.net) | [`rpcs3`](https://search.nixos.org/packages?channel=unstable&show=rpcs3) | ✅ | RomM |
| PSP | [PPSSPP](https://www.ppsspp.org) | [`ppsspp-sdl`](https://search.nixos.org/packages?channel=26.05&show=ppsspp-sdl) | — | RomM |
| Xbox 360 | [Xenia](https://xenia.jp) (fork still undecided) | FamiDrive's own ([`pkgs/xenia-netplay`](pkgs/xenia-netplay)) | ✅ | RomM |
| Atari 2600 / 5200 / 7800 / Jaguar | [RetroArch](https://www.retroarch.com) + [Stella](https://stella-emu.github.io), [Atari800](https://github.com/libretro/libretro-atari800), [ProSystem](https://github.com/libretro/prosystem-libretro), [Virtual Jaguar](https://github.com/libretro/virtualjaguar-libretro) | [`libretro.stella`](https://search.nixos.org/packages?channel=26.05&show=libretro.stella), [`libretro.atari800`](https://search.nixos.org/packages?channel=26.05&show=libretro.atari800), [`libretro.prosystem`](https://search.nixos.org/packages?channel=26.05&show=libretro.prosystem), [`libretro.virtualjaguar`](https://search.nixos.org/packages?channel=26.05&show=libretro.virtualjaguar) | — | RomM |
| Steam | [Steam](https://store.steampowered.com), started hidden, with [Proton-GE](https://github.com/GloriousEggroll/proton-ge-custom) available | [`steam`](https://search.nixos.org/packages?channel=26.05&show=steam), [`proton-ge-bin`](https://search.nixos.org/packages?channel=26.05&show=proton-ge-bin) | Steam Cloud | Your Steam library |
| GOG, Epic Games Store, Amazon Games | [Heroic Games Launcher](https://heroicgameslauncher.com), each store its own system | [`heroic`](https://search.nixos.org/packages?channel=26.05&show=heroic) | Each store's cloud saves | Your libraries in each store |
| Minecraft | [Prism Launcher](https://prismlauncher.org) | [`prismlauncher`](https://search.nixos.org/packages?channel=26.05&show=prismlauncher) | — | Your Prism instances, and ones declared in Nix |
| Clone Hero, YARG | [Clone Hero](https://clonehero.net) and [YARG](https://yarg.in), in the Ports system | [`clonehero`](https://search.nixos.org/packages?channel=26.05&show=clonehero), [`yarg`](https://search.nixos.org/packages?channel=26.05&show=yarg) | ✅ (scores and profiles) | Songs declared in Nix, downloaded once for the box |
| Media | [Kodi](https://kodi.tv) 21 with [JellyCon](https://github.com/jellyfin/jellycon), or [Jellyfin MPV Shim](https://github.com/jellyfin/jellyfin-mpv-shim) 3.1 | [`kodi`](https://search.nixos.org/packages?channel=26.05&show=kodi), [`jellyfin-mpv-shim`](https://search.nixos.org/packages?channel=unstable&show=jellyfin-mpv-shim) | — | Your Jellyfin server, and media folders on the box (an external drive) |

RetroArch runs everything it does well, so those systems share one
controller setup and one save folder. The rest get the standalone emulator
that's best for them. Platforms RomM can hold but FamiDrive leaves out:
Windows/PC and classic Mac/Apple II (computers, not consoles), iOS, Xbox
Series and Switch 2 (no emulator on Linux), and the original Xbox (later).
Save sync is on for every system whose save files are mapped so far
(✅ above, through RomM); the others (—) keep their saves on the box until theirs are.
Every console system can also play from a folder already on the box
instead of RomM (`localRoms`). The menu itself is
[ES-DE](https://es-de.org), packaged in FamiDrive
([`pkgs/es-de`](pkgs/es-de)), in a [gamescope](https://github.com/ValveSoftware/gamescope)
session ([`gamescope`](https://search.nixos.org/packages?channel=26.05&show=gamescope)).

A few ideas run through all of it:

- **Every launch goes through one wrapper**, `famidrive-launch`. It pulls the
  game's newest save from RomM, starts the game with gamescope's focus set
  so the game actually comes to the front, and pushes the save back when
  you quit.
- **Who writes a config file decides how Nix manages it.** Files only Nix
  writes (like ES-DE's `es_systems.xml`) are symlinked from the store.
  Files the app also rewrites from its own settings menu (ES-DE's
  `es_settings.xml`, Dolphin's INIs, Eden's `qt-config.ini`, the shim's
  `conf.json`) are seeded once, with only the few keys FamiDrive depends on
  forced back on every rebuild. Everything else you change from the TV
  survives.
- **Firmware and keys never enter the Nix store**, which anyone on the box
  can read. They come from RomM.
- **Everyone in the house gets their own profile.** Each player in
  `famidrive.players` is their own Linux account and their own RomM user:
  their own Steam login, saves, favorites and RomM token, so two people's
  saves never mix. The ROMs, firmware and controller setup are the box's
  and shared. With more than one player, the box starts on a "Who's
  playing?" screen, and quitting ES-DE goes back to it. An
  optional Guest plays everything with saves kept on the box only.
- **The base is the latest NixOS release; only the emulators chase
  unstable.** The kernel, graphics stack, Steam and the session come from
  `nixos-26.05`, so the parts that would leave you without a working TV
  only change when you choose to move releases. The few emulators that
  improve month to month (Eden, RPCS3) and the Jellyfin client come from
  `nixos-unstable` through the overlay. Releases are supported for about
  seven months, so the flake moves to the next one twice a year: 26.05 is
  supported until 2026-12-31, and 26.11 is next.
- **Flakes are on.** Upstream Nix still labels them experimental, but
  they've been dependable since 2021 and the whole ecosystem builds on
  them. The module turns them on; a box only needs
  `--extra-experimental-features 'nix-command flakes'` for its very first build.
- **Online play is a per-box option**, `famidrive.online.enable`, which
  points each emulator's netplay settings at servers you run.

## Layout

```
flake.nix                    inputs, overlay, nixosModules.default, lib.mkBox
modules/famidrive/
  default.nix                the options a host sets: players, guest, lanes, romm.*, localRoms, dataDir
  endpoints.nix              every server address in one place, with no defaults
  session.nix                greetd: "Who's playing?" (or autologin), then gamescope running ES-DE
  emulators.nix              famidrive.systems: the one table of systems, emulators and save layouts
  frontend.nix               es_systems.xml generated from famidrive.systems; famidrive-launch
  romm-agent.nix             library + firmware pull, save reconcile timer
  generators.nix             Steam / Heroic / Prism menu entries, regenerated when installs change
  pc-saves.nix               Syncthing for PC saves, the one thing RomM can't hold yet
  online.nix                 famidrive.online.enable fills in each emulator's netplay settings
  media.nix                  famidrive.media.kodi / .jellyfin: "Media" entries for Kodi and Jellyfin
  controllers.nix            GameCube ports per box, the quit combo, RetroArch's menu combo
  lib/seed.nix               seed / lockKeys helpers for configs the app also writes
pkgs/
  es-de/                     ES-DE 3.5.0 AppImage (ES-DE left nixpkgs on 2025-10-23)
  gamescope-fg/              sets STEAM_GAME on the game's window so gamescope focuses it
  famidrive-quit/            hold Select + Start on any controller to quit the game
  famidrive-picker/          "Who's playing?", greetd's greeter on a box with more than one player
  romm-agent/                Python: pull, firmware, save-pull/push, reconcile
  famidrive-generators/      Python: install manifests -> ES-DE menu entries
  tcli/                      Thunderstore's CLI (unfinished)
  xenia-netplay/             placeholder until the Xenia fork is picked
```

There are no hosts in this repo. Each box is its own small private flake
that imports this one (see [Using it](#using-it)), because a host holds
things that don't belong in public: its hardware, its server addresses and
its secrets.

Code comments refer to design notes by file name (`roms.md`,
`controllers.md`, `spec.md` and so on). Those notes are a separate
planning doc for now and will move into this repo.

## Status

**Real:**

- ES-DE 3.5.0 and Jellyfin MPV Shim 3.1.0 are pinned with real hashes.
- Eden is the Switch emulator; the config keys it uses were read off a
  real Eden 0.2.1 install.
- On the first box: the gamescope session, 4K120 HDR over HDMI 2.1,
  the Art Book Next theme, GameCube (Dolphin) and Switch (Eden) games
  taking focus, the 8BitDo Ultimate 2 over 2.4 GHz, and quitting with
  Select + Start.
- "Who's playing?" with two players and a guest, each with their own
  saves, Steam and RomM account, and powering off from the controller.
- The RomM agent against RomM 5.3 on the first box: the library pull
  (single files, folders and nested files), firmware, and save sync both
  ways for GameCube, Wii, Switch and Clone Hero, with conflict copies
  and a short save history. Each
  game's details and box art come from RomM, with each player's
  favorites and play counts kept. A box can mirror some platforms only
  (`romm.platforms`). Dolphin HD texture packs kept in RomM (a zip in the
  game's `mod/` folder) are unpacked once and loaded for every player.
  Switch games come with their newest update and every DLC from RomM,
  one copy for the whole box that Eden reads in place, and a game's
  console-side (device) save syncs along with the player's. Save sync
  also works for PlayStation and N64 (RetroArch), and Switch mods kept
  in RomM (`mod/`) are linked into each player's emulator.
- Ryujinx for the Switch games that need it (`switch.ryujinx.games`):
  Smash Ultimate with HewDraw Remix gets there with its update, DLC and
  the player's save bridged from Eden's. Its menus work on the first
  box, but matches crash on Ryujinx 1.3.3 (see
  [COMPATIBILITY.md](COMPATIBILITY.md#super-smash-bros-ultimate)).
- The Steam lane, with Proton pins and Steam Input set from Nix, Steam's
  Big Picture as a Settings entry, a status screen while Steam
  updates, processes shaders or starts a game, and each game's art and
  details from Steam itself. GOG, Epic and Amazon through Heroic
  (`lanes` has `"heroic"`). Results per game are in
  [COMPATIBILITY.md](COMPATIBILITY.md).
- Toasts over whatever's on the TV, in the player's theme, with an icon
  each: a save going up to RomM, or not. Toasts show bottom right by
  default, and MangoHud's performance overlay, off by default, middle
  left; each player can move either (`famidrive.overlays`). Apps' own
  desktop notifications show as toasts too, Heroic's included (installs,
  downloads), and so do GOG achievements, through Comet.
- RetroAchievements per player (`players.<name>.retroAchievements`):
  RetroArch, Dolphin and PCSX2 signed in to the player's own account at
  the start of their session, from a password in their sops secret.
  Unlocks in RetroArch and Dolphin show as toasts, with the
  achievement's description and points; Dolphin's own on-screen messages
  are off. RomM shows each player's progress itself once their
  RetroAchievements username is linked in their RomM profile; the box
  sends RomM nothing about achievements.
- Clone Hero in a Ports system (`famidrive.cloneHero`): songs for the
  whole box, listed by their Chorus Encore md5 and downloaded to the
  library disk, a profile for every player plus guests, and the TV's
  calibration set once for everyone. Each player's scores and profiles
  sync with RomM, under a "Clone Hero" entry added there by hand (see
  [RomM entries to add by hand](#using-it)).
- YARG in Ports too (`famidrive.yarg`), playing the same songs as Clone
  Hero, with scores and profiles under a "YARG" entry in RomM.
- Menu music: each player's `~/ES-DE/music`, shuffled behind ES-DE and
  paused while a game is open (ES-DE has no music of its own).
- Wii games with real Wii Remotes and the Balance Board, and Minecraft
  instances declared in Nix (per player), with controller play through
  Controlify.
- Kodi in Media (`famidrive.media.kodi`), with JellyCon (Jellyfin, live TV
  included, the server filled in from `endpoints.jellyfin`), Up Next, the
  box's own media folders, HDR, and the house controllers mapped.
- A boot screen (Plymouth) in place of console text, and graphics card
  setup (`famidrive.gpu`; see below).

**Still a sketch:**

- The RomM agent's save sync for systems other than GameCube, Wii and
  Switch hasn't run against a real server yet. Field values it hasn't
  seen are marked `VERIFY`.
- PS3 firmware isn't installed automatically: RPCS3 only installs it
  through its own window (#48).
- RomM's save sync is being redesigned ("Save Sync v2", a draft as of
  2026-09-23). The agent's save half will need rewriting when it lands;
  the library and firmware half shouldn't.
- Launch flags for the standalone emulators added later (Azahar, PPSSPP,
  Cemu) and the RetroArch core file names are unverified.
- The Heroic lane (GOG, Epic, Amazon) hasn't run against a signed-in
  Heroic yet. The installed-games files it reads were taken from
  Heroic's source and are marked `VERIFY`.
- Online play needs servers that don't exist yet.
- The "home" button (back to the menu, or straight into Jellyfin, from
  inside a game) has no design yet.

**Graphics cards:** AMD is tested (the first box's Radeon RX 7900 XTX).
Intel Arc should just work, the same as AMD. Nvidia is supported
(`famidrive.gpu = "nvidia"`) but untested, and testers are wanted (#77).
[COMPATIBILITY.md](COMPATIBILITY.md#graphics-cards) has the details.

**Not in scope yet:** original Xbox, HDMI-CEC power-on (sketched behind
`famidrive.cec.enable`, off), and waking the box with a controller.

## Using it

A box is a private flake with two files of its own, `flake.nix` and
`configuration.nix`, plus the `hardware-configuration.nix` NixOS made.
It usually lives in `/etc/nixos`.

```nix
# flake.nix
{
  inputs.famidrive.url = "github:anultravioletaurora/FamiDrive";

  outputs = { famidrive, ... }: {
    nixosConfigurations.tv = famidrive.lib.mkBox ./configuration.nix;
  };
}
```

```nix
# configuration.nix
{
  imports = [ ./hardware-configuration.nix ];

  networking.hostName = "tv";
  boot.loader.systemd-boot.enable = true;
  system.stateVersion = "26.05";

  famidrive = {
    enable = true;
    players.alice = { };                   # a Linux account and RomM user, both "alice"
    lanes = [ "roms" "steam" ];
    endpoints.romm = "https://romm.example.org";
    endpoints.jellyfin = "https://jellyfin.example.org";
    media.jellyfin.enable = true;
    controllers.gamecube.ports = [ "gamepad" ];
  };

  sops.defaultSopsFile = ./secrets.yaml;   # the RomM token, below
  sops.age.keyFile = "/var/lib/sops-nix/key.txt";
}
```

`lib.mkBox` builds on this flake's own pinned nixpkgs, so every box built
from the same FamiDrive revision runs the same emulator builds, which
netplay needs. Build with
`sudo nixos-rebuild switch --flake /etc/nixos#tv`, and pick up a newer
FamiDrive with `nix flake update famidrive` first. Every option, with
what it does and its default, is in [USAGE.md](USAGE.md).

**Secrets.** Server addresses aren't secret and go in `configuration.nix`.
Logins for Jellyfin, Steam and Heroic's stores (GOG, Epic, Amazon) happen once in each app, on the TV. The
only secrets are in the host's `secrets.yaml`, encrypted with
[sops](https://github.com/getsops/sops) to the box's age key plus yours:

- `romm-token-<player>`: one per player, a RomM Client API Token (`rmm_…`)
  issued by that player's RomM user. The primary player's
  (`famidrive.primaryPlayer`) also pulls the shared library. Scopes the agent uses: `roms.read`, `platforms.read`,
  `firmware.read`, `collections.read`, `assets.read`, `assets.write`,
  `devices.read`, `devices.write`. Add `roms.write` to let a box write game
  IDs it worked out back to RomM (optional; skipped quietly without it).
- `rpcn-password-<player>`: only for PS3 with `famidrive.online.enable`.

A box with `famidrive.romm.enable = false` needs no secrets and no sops
setup at all.

**RomM entries to add by hand.** RomM keeps saves only for games in its
library, and some apps on the box aren't ROMs. To sync their saves, add
one entry for each in RomM's web UI, once for the whole RomM server.
Upload any small file to any platform this box doesn't pull, such as
Windows, and give the entry exactly this name:

| Turned on with | RomM entry | What syncs |
|---|---|---|
| `cloneHero.enable` | `Clone Hero` (`cloneHero.romm.entry`) | each player's scores and profiles |
| `yarg.enable` | `YARG` (`yarg.romm.entry`) | each player's scores and profiles |

Without its entry, an app still works, and its saves stay on the box.

## Players

```nix
famidrive = {
  players = {
    alice = { };                       # Linux account and RomM user "alice"
    sam.owner = "sammy";               # account "sam", RomM user "sammy"
  };
  primaryPlayer = "alice";             # whose token pulls the shared library
  guest.enable = true;                 # optional
};
```

- **What's shared:** ROMs, cover art and firmware live in `dataDir`,
  readable by every player (group `famidrive`) and written only by the
  library pull. ROM folders from `localRoms` need the same: readable by
  group `famidrive` or by everyone.
- **What's each player's own:** everything in their home. Saves, emulator
  settings, ES-DE's favorites and play counts, Steam, Prism, the Jellyfin
  login. Each player's saves go to RomM under their own RomM user, with
  their own token.
- **Steam:** each player signs in to their own account once, in Settings →
  Steam Settings. Games installed in one player's home show up only in
  their menu, so a game both play is downloaded twice. Steam Family lets
  a family share one copy of each *purchase* (each account still keeps
  its own download).
- **GOG, Epic and Amazon:** each player signs in to their own stores once,
  in Settings → Heroic Games Launcher, and installs games there. Each
  store's games show up in its own system in the menu.
- **The guest:** no RomM, so their saves stay on this box. They can sign
  in to their own Steam or play without it.
- **Switching and turning off:** ES-DE's Quit menu (Start → Quit) has
  Quit ES-DE, which closes Steam and ends the session so "Who's playing?"
  comes back, plus Reboot and Power Off. "Who's playing?" has Power Off
  too, below the players. Who played last starts out selected.

## Installing from scratch

For a PC with no operating system yet, or one running something else
(Windows, SteamOS, another Linux) that FamiDrive will replace. Installing
**erases the disk you install to**, so copy off anything you want to keep
first. Keeping another system beside FamiDrive (dual boot) works with
NixOS, but isn't covered here.

**You'll need:**
- a 64-bit PC (x86_64) with an AMD or Intel graphics card. Nvidia should
  work, but it's untested ([#77](https://github.com/anultravioletaurora/FamiDrive/issues/77)).
- a USB stick of 4 GB or more
- a keyboard for the install (only for the install: the box is played
  with controllers after)
- an internet connection, wired if you can
- optionally, a second disk for the game library, and another computer to
  SSH in from, which makes editing the config much easier

1. **Download NixOS 26.05:** the graphical installer ISO from
   [nixos.org/download](https://nixos.org/download/#nixos-iso). Write it
   to the USB stick with [Fedora Media Writer](https://flathub.org/apps/org.fedoraproject.MediaWriter),
   [balenaEtcher](https://etcher.balena.io) or `dd`.
2. **Set up the PC's firmware** (its BIOS or UEFI settings, usually Del
   or F2 at power-on). Boot in **UEFI mode**, and turn **Secure Boot off**:
   the NixOS installer isn't signed for it. Then boot from the USB stick
   (often F12 or F8 for a boot menu).
3. **Install NixOS.** The installer opens on its own. Choices that matter
   for FamiDrive:
   - **Location and language:** your real ones. FamiDrive's time zone,
     and later its language ([#100](https://github.com/anultravioletaurora/FamiDrive/issues/100)),
     come from them.
   - **Desktop:** **No desktop.** FamiDrive brings its own TV session.
   - **Unfree software:** allow it. Steam and some drivers need it.
   - **Users:** create the first player's account, with the name you'll
     use for them in FamiDrive (`alice` below), and a password. The TV
     never asks for it, but SSH and `sudo` do.
   - **Computer name:** what the box is called on your network, and the
     name its config is built under (`tv` below).
   - **Partitions:** erase the disk. Leave encryption off: a box that asks
     for a password at every boot has no keyboard to type it on.

   Reboot when it's done, and take the USB stick out.
4. **Log in** on the text console as the account you made. On Wi-Fi,
   connect with `nmcli device wifi connect "<network>" password "<password>"`
   (the installer turns on NetworkManager). `ip a` shows the box's
   address, for SSH from another computer.
5. **Make `/etc/nixos` a FamiDrive box.** The installer left
   `configuration.nix` and `hardware-configuration.nix` there. Add a
   `flake.nix` beside them, as in [Using it](#using-it), with
   `nixosConfigurations.tv` named after the computer name. In
   `configuration.nix`, keep everything the installer wrote, especially
   `system.stateVersion`, the boot loader, networking, time zone and the
   user account, and add a `famidrive` block:

   ```nix
   famidrive = {
     enable = true;
     players.alice = { };          # the account the installer made
     lanes = [ "roms" "steam" ];
     romm.enable = false;          # or true, with the steps below
     localRoms.gc = "/srv/roms/gamecube";   # games already on the box, by system
   };
   ```

   Every option is in [USAGE.md](USAGE.md).
   - **Without a RomM server:** keep `romm.enable = false`. No secrets
     are needed. Games come from folders on the box (`localRoms`);
     plugging in a drive and having it just work is
     [#99](https://github.com/anultravioletaurora/FamiDrive/issues/99).
   - **With RomM:** set `endpoints.romm`, and give the box its age key
     and each player's token:
     ```sh
     sudo mkdir -p /var/lib/sops-nix
     sudo nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#age -c age-keygen -o /var/lib/sops-nix/key.txt
     ```
     The command prints the box's public key (`age1…`). Put it in
     `/etc/nixos/.sops.yaml` (with yours, if you'll edit secrets from
     another computer):
     ```yaml
     creation_rules:
       - path_regex: secrets\.yaml$
         age: age1…
     ```
     Then add `romm-token-alice: rmm_…` to `secrets.yaml` with
     `cd /etc/nixos && sudo env SOPS_AGE_KEY_FILE=/var/lib/sops-nix/key.txt nix --extra-experimental-features 'nix-command flakes' run nixpkgs#sops -- secrets.yaml`
     (sops finds `.sops.yaml` from the folder you're in),
     and the two `sops.` lines from [Using it](#using-it) to
     `configuration.nix`. [Secrets](#using-it) lists the token's scopes.
   - **A second disk for the library:** `sudo mkfs.ext4 -L famidrive /dev/<disk>`,
     and mount it at `/var/lib/famidrive` in `configuration.nix`:
     ```nix
     fileSystems."/var/lib/famidrive" = {
       device = "/dev/disk/by-label/famidrive";
       options = [ "nofail" ];
     };
     ```
6. **Build and switch:**
   ```sh
   sudo nixos-rebuild switch --flake /etc/nixos#tv --extra-experimental-features 'nix-command flakes'
   ```
   The first build downloads several gigabytes (Steam, the emulators,
   ES-DE). FamiDrive turns flakes on, so later rebuilds don't need the
   last flag. If `/etc/nixos` is a git repository, `git add` new files
   first: flakes only see what git tracks.
7. **Reboot.** After the boot screen, the TV shows ES-DE, or "Who's
   playing?" with more than one player.
8. **First run, on the TV:**
   - **Controllers:** 2.4 GHz dongles and wired pads work as they are.
     Pair Bluetooth pads once with `bluetoothctl` over SSH
     (`scan on`, then `pair`, `trust` and `connect` with the pad's
     address). [CONTROLLERS.md](CONTROLLERS.md) has each pad's notes.
   - **Steam:** sign in under Settings → Steam Settings.
   - **GOG, Epic, Amazon:** sign in under Settings → Heroic Games
     Launcher, if `lanes` has `"heroic"`.
   - **Jellyfin:** sign in once in Media.
   - **RomM:** with a token, the library pull starts by itself (every
     30 minutes). `sudo systemctl start romm-library-pull` starts it now.

Updating later is the same everywhere:
`cd /etc/nixos && sudo nix flake update famidrive && sudo nixos-rebuild switch --flake /etc/nixos#tv`.
If an update misbehaves, pick the previous generation in the boot menu.

## Moving an existing NixOS box over

This is the path the first box takes: an existing NixOS gaming box whose
ROM drive is wiped and refilled from RomM, with old saves imported into
RomM along the way.

1. **Back up saves** off the box: Dolphin's `GC/` and `Wii/`, Eden's
   `nand/user/save`, Prism's instances, Steam's `userdata`, and `/etc/nixos`.
   Note the current generation number; it's the way back.
2. **Write the host file.** Keep `system.stateVersion` at the original
   install's value. Make the existing account a player
   (`famidrive.players.<account> = { };`), so the
   Steam library and emulator data carry over. Carry over anything else
   the old config did that isn't about Steam (Sunshine, Avahi, Bluetooth,
   GPU tools). Fill in `endpoints.romm`, and set `owner` on the player if
   their RomM username isn't the account's name.
3. **Give the box its RomM token:** make an age key on the box
   (`/var/lib/sops-nix/key.txt`), add it to `.sops.yaml`, create a Client
   API Token in RomM with the scopes under [Secrets](#using-it), and put
   it in the host's `secrets.yaml` with `sops`.
4. **Prepare the library disk:** wipe it and `mkfs.ext4 -L famidrive`. The
   host mounts it by that label at `/var/lib/famidrive`.
5. **Build on the box itself:**
   `nixos-rebuild build --flake /etc/nixos#tv --extra-experimental-features 'nix-command flakes'`.
   If the host flake is a git repo, flakes only see files git tracks, so
   `git add` first. Nothing on the box changes yet. Fix things until it
   builds.
6. **Try it without committing:** `sudo nixos-rebuild test --flake /etc/nixos#tv`,
   over SSH. That switches the running system but not the boot default,
   so if anything goes wrong, a reboot brings back the old system. The
   TV's session restarts by itself when the switch changed it
   (`famidrive.session.restartOnSwitch`); run
   `sudo systemd-tmpfiles --create` if a library folder is missing.
7. **Pull a little first:** run `sudo systemctl start romm-library-pull` with `romm.collection` set
   to a small test collection, and check the games show up in ES-DE. Then
   set it back to `null` and let the full pull run (the timer does it every
   30 minutes; it resumes where it stopped).
8. **Bring old saves in:** copy them back into each emulator's save folder,
   sort out any duplicate Eden profiles first (FamiDrive syncs the one
   Eden runs games as; set the player's `edenProfileId` only if that isn't
   the one with the real saves), then run `romm-agent reconcile` as that
   player. Every save RomM doesn't have goes up, under their RomM user.
9. **Check:** a GameCube game, a Switch game and a Steam game each launch,
   take focus, and quit back to ES-DE; the controller works throughout; a
   new save shows up in RomM after quitting; Media → Jellyfin plays
   something.
10. **Commit to it:** `sudo nixos-rebuild boot --flake /etc/nixos#tv` and reboot.
    Don't garbage-collect for a while: the old system's generation in the
    boot menu is the safety net.

## Making changes

Changes go in through pull requests. Each one runs `nix flake check` on
GitHub ([.github/workflows/check.yml](.github/workflows/check.yml)), which
covers what can be tested without a TV or a server ([tests/](tests)):

- unit tests for FamiDrive's own tools (the RomM agent, the Valheim mod
  installer, the Steam settings writer, "Who's playing?"), against
  made-up files
- example boxes (one player; a family with RomM and a guest), evaluated
  with checks on what the module made of them
- every package in the flake, built

Run the same locally with `nix flake check`. After merging, a change gets
tried on a real box (and against RomM, for anything that touches it),
and the results go in [COMPATIBILITY.md](COMPATIBILITY.md) (games) and
[CONTROLLERS.md](CONTROLLERS.md) (controllers). Notes for coding agents
are in [AGENTS.md](AGENTS.md).

## Special Thanks

- **[Jovian-NixOS](https://github.com/Jovian-Experiments/Jovian-NixOS)
  contributors**, who inspired me to build this and to not be afraid of Nix.
- **[Art Book Next](https://github.com/anthonycaccese/art-book-next-es-de)
  contributors**, for making FamiDrive look amazing.
- **[RomM](https://github.com/rommapp/romm) contributors**, for the
  inspiration to rework my gaming setup entirely.
- **Everyone else whose open source work this is built on**: NixOS and
  nixpkgs, ES-DE, gamescope, Steam's Linux team, the emulator projects
  (Dolphin, Eden, RetroArch and its cores, PCSX2, RPCS3, Xenia, Azahar,
  PPSSPP, Cemu, melonDS), Prism Launcher, Kodi, Jellyfin and Jellyfin MPV Shim, mpv,
  home-manager and sops-nix.

## Your games

FamiDrive is for games you legally own, and for legal backups you've made
yourself of games you own. That's how it's used on the boxes it was built
for, and it's the expectation for everyone else who uses it.

FamiDrive provides no games, licenses, keys, BIOS files or firmware.
Everything it plays is sourced by you: from your own RomM server, your own
disks, or your own store accounts (Steam, GOG, Epic, Amazon). It's your
responsibility to source your games' licenses, keys and files ethically
and legally.

## License

GPL-3.0. See [LICENSE](LICENSE).
