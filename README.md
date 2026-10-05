# FamiDrive

**A 10,000-in-1 Declarative System**

FamiDrive is a free, TV-first game console you build out of NixOS. It boots
straight into [ES-DE](https://es-de.org), runs inside
[gamescope](https://github.com/ValveSoftware/gamescope), and puts every
console emulator, your Steam and GOG games, Minecraft and Jellyfin behind
one controller-driven menu. Nothing about the box is set up by hand: the
emulators, their settings, the menu and where every game comes from are
all one Nix flake. Your ROMs, firmware and saves live in your own
[RomM](https://github.com/rommapp/romm) server, so any number of boxes,
including ones outside your house, are just more clients of the same
library.

It exists because a console where Steam is the whole interface makes
everything that isn't a Steam game a guest: emulators get imported as
Steam shortcuts, saves outside Steam Cloud need their own backup scheme,
and Steam Input sits in front of every controller whether a game wants it
or not. FamiDrive keeps the good part, a box that boots into a console UI
and never needs a desktop, and makes Steam just one entry on the menu.

> **Status: early.** Nothing here has run on real hardware yet. The flake
> has never been evaluated; it's a careful sketch written from the design
> notes, and the first box (`atlantis`) is about to be its first test. See
> [Status](#status) for what's real and what's a placeholder.


## What's in the box

| Lane | How it plays | Where the games come from |
|---|---|---|
| Game Boy / Color / Advance | RetroArch + mGBA | RomM |
| SNES | RetroArch + Snes9x | RomM |
| Nintendo 64 / 64DD | RetroArch + Mupen64Plus-Next | RomM |
| DS / DSi | RetroArch + melonDS DS | RomM |
| 3DS / New 3DS | Azahar | RomM |
| GameCube / Wii | Dolphin | RomM, or a local folder |
| Wii U | Cemu | RomM |
| Switch | Eden | RomM, or a local folder |
| Genesis / Master System / Game Gear | RetroArch + Genesis Plus GX | RomM |
| Saturn | RetroArch + Beetle Saturn | RomM |
| Dreamcast | RetroArch + Flycast | RomM |
| PlayStation | RetroArch + SwanStation | RomM |
| PlayStation 2 | PCSX2 | RomM |
| PlayStation 3 | RPCS3 | RomM |
| PSP | PPSSPP | RomM |
| Xbox 360 | Xenia (fork still undecided) | RomM |
| Atari 2600 / 5200 / 7800 / Jaguar | RetroArch (Stella, Atari800, ProSystem, Virtual Jaguar) | RomM |
| Steam | Steam, started hidden | Your Steam library |
| GOG | `gogdl` (not packaged yet) | Your GOG library |
| Minecraft | Prism Launcher | Your Prism instances |
| Media | [Jellyfin MPV Shim](https://github.com/jellyfin/jellyfin-mpv-shim) 3.1 | Your Jellyfin server |

RetroArch runs everything it does well, so those systems share one
controller setup and one save folder. The rest get the standalone emulator
that's best for them. Platforms RomM can hold but FamiDrive leaves out:
Windows/PC and classic Mac/Apple II (computers, not consoles), iOS, Xbox
Series and Switch 2 (no emulator on Linux), and the original Xbox (later).
Save sync is on for every system whose save files are mapped so far (all
the cartridge systems, PlayStation 1–3, GameCube, Wii, Switch); the others
keep their saves locally until theirs are.

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
- **Every box belongs to one person.** `famidrive.owner` scopes the RomM
  token, the saves and the emulator profiles, so two people's boxes never
  share saves by accident.
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
flake.nix                    inputs, overlay, one nixosConfiguration per box
modules/famidrive/
  default.nix                the options a host sets: owner, user, lanes, romm.*, localRoms, dataDir
  endpoints.nix              every server address in one place, with no defaults
  session.nix                greetd autologin into gamescope running ES-DE
  emulators.nix              famidrive.systems: the one table of systems, emulators and save layouts
  frontend.nix               es_systems.xml generated from famidrive.systems; couch-launch
  romm-agent.nix             library + firmware pull, save reconcile timer
  generators.nix             Steam / GOG / Prism menu entries, regenerated when installs change
  pc-saves.nix               Syncthing for PC saves, the one thing RomM can't hold yet
  online.nix                 famidrive.online.enable fills in each emulator's netplay settings
  media.nix                  famidrive.media.jellyfin.enable: a "Media" entry for Jellyfin
  lib/seed.nix               seed / lockKeys helpers for configs the app also writes
pkgs/
  es-de/                     ES-DE 3.5.0 AppImage (ES-DE left nixpkgs on 2025-10-23)
  gamescope-fg/              sets STEAM_GAME on the game's window so gamescope focuses it
  romm-agent/                Python: pull, firmware, save-pull/push, reconcile
  couch-generators/          Python: install manifests -> ES-DE menu entries
  gogdl-cli/ tcli/           headless GOG and Thunderstore CLIs (unfinished)
  xenia-netplay/             placeholder until the Xenia fork is picked
hosts/
  atlantis/                  the first box: an existing NixOS TV box moving over
  remote-box/                template for a box outside the household (not built)
```

Code comments refer to design notes by file name (`roms.md`,
`controllers.md`, `spec.md` and so on). Those notes are a separate
planning doc for now and will move into this repo.

## Status

**Real:**

- ES-DE 3.5.0 and Jellyfin MPV Shim 3.1.0 are pinned with real hashes.
- Eden is the Switch emulator; the config keys it uses were read off a
  real Eden 0.2.1 install.
- `atlantis` is the real host config, carried over from its previous setup.

**Still a sketch:**

- The flake has never been evaluated.
- The RomM agent uses the endpoints in RomM 5.3.1's own `openapi.json`, but
  has never run against a real server. Field values it hasn't seen yet
  (cover paths, multi-file downloads) are marked `VERIFY`.
- RomM's save sync is being redesigned ("Save Sync v2", a draft as of
  2026-09-23). The agent's save half will need rewriting when it lands;
  the library and firmware half shouldn't.
- Launch flags for the standalone emulators added later (Azahar, PPSSPP,
  Cemu) and the RetroArch core file names are unverified.
- The GOG lane's packages have placeholder hashes.
- Online play needs servers that don't exist yet.
- The "home" button (back to the menu, or straight into Jellyfin, from
  inside a game) has no design yet.

**Not in scope yet:** original Xbox, HDMI-CEC power-on (sketched behind
`famidrive.cec.enable`, off), and waking the box with a controller.

## Moving an existing NixOS box over

This is the path `atlantis` takes: an existing NixOS gaming box whose ROM
drive is wiped and refilled from RomM, with old saves imported into RomM
along the way.

1. **Back up saves** off the box: Dolphin's `GC/` and `Wii/`, Eden's
   `nand/user/save`, Prism's instances, Steam's `userdata`, and `/etc/nixos`.
   Note the current generation number; it's the way back.
2. **Write the host file.** Keep `system.stateVersion` at the original
   install's value. Set `famidrive.user` to the existing account, so the
   Steam library and emulator data carry over. Carry over anything else
   the old config did that isn't about Steam (Sunshine, Avahi, Bluetooth,
   GPU tools). Fill in `owner` and `endpoints.romm`.
3. **Give the box its RomM token:** make an age key on the box
   (`/var/lib/sops-nix/key.txt`), add it to `.sops.yaml`, create a Client
   API Token in RomM with the scopes in `secrets/README.md`, and put it in
   `secrets/<host>.yaml` with `sops`.
4. **Prepare the library disk:** wipe it and `mkfs.ext4 -L famidrive`. The
   host mounts it by that label at `/var/lib/famidrive`.
5. **Build on the box itself:**
   `nixos-rebuild build --flake .#atlantis --extra-experimental-features 'nix-command flakes'`.
   Flakes only see files git tracks, so `git add` first. Nothing on the box
   changes yet. Fix things until it builds.
6. **Try it without committing:** `sudo nixos-rebuild test --flake .#atlantis`,
   over SSH. That switches the running system but not the boot default,
   so if anything goes wrong, a reboot brings back the old system.
7. **Pull a little first:** run `romm-agent pull` with `romm.collection` set
   to a small test collection, and check the games show up in ES-DE. Then
   set it back to `null` and let the full pull run (the timer does it every
   30 minutes; it resumes where it stopped).
8. **Bring old saves in:** copy them back into each emulator's save folder,
   sort out any duplicate Eden profiles first (keep the one Eden uses, and
   set `identity.edenProfileId` to it), then run `romm-agent reconcile`.
   Every save RomM doesn't have goes up, under your user.
9. **Check:** a GameCube game, a Switch game and a Steam game each launch,
   take focus, and quit back to ES-DE; the controller works throughout; a
   new save shows up in RomM after quitting; Media → Jellyfin plays
   something.
10. **Commit to it:** `sudo nixos-rebuild boot --flake .#atlantis` and reboot.
    Don't garbage-collect for a while: the old system's generation in the
    boot menu is the safety net.

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
  PPSSPP, Cemu, melonDS), Prism Launcher, Jellyfin and Jellyfin MPV Shim, mpv,
  home-manager, sops-nix and deploy-rs.

## License

GPL-3.0. See [LICENSE](LICENSE).
