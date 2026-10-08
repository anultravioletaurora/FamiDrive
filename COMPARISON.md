# FamiDrive and the alternatives

There are a lot of good ways to put a gaming PC under a TV, and
FamiDrive is the youngest of them. This page is here so you can pick the
right one before you commit to it. If you spot something wrong or out of
date about another project, please open an issue: they all move fast.

## At a glance

| | FamiDrive | Jovian-NixOS | Bazzite | ChimeraOS | Batocera | Windows + Playnite |
|---|---|---|---|---|---|---|
| **Base** | NixOS | NixOS | Fedora Atomic | Arch, as a read-only image | Its own Linux, as a read-only image | Windows |
| **Boots into** | ES-DE | Steam's gaming mode | Steam's gaming mode | Steam's gaming mode | EmulationStation | The Windows desktop, then Playnite (it can start in fullscreen at login) |
| **The menu is built around** | Every system at once: emulators, Steam, other stores, apps | Steam | Steam | Steam | Emulators | Every store and emulator, as one library |
| **Emulators out of the box** | ✅ Installed and set up from the flake | ❌ Bring your own, added as Steam shortcuts | Partly: installers like EmuDeck or RetroDECK are a click away | Partly: its web app adds ROMs as Steam shortcuts | ✅ Emulation is its whole job | Partly: Playnite finds and launches emulators you install |
| **Steam** | One entry in the menu, launched from ES-DE | ✅ Is the UI | ✅ Is the UI | ✅ Is the UI | Add-on (Flatpak) | ✅ Native |
| **GOG, Epic, Amazon** | Through Heroic, in the same menu | Through Heroic, as Steam shortcuts | Through Heroic or Lutris, as Steam shortcuts | Through its web app or Heroic, as Steam shortcuts | Limited | ✅ Native clients, in one library |
| **RomM as the library** | ✅ Games, firmware, art and details pulled per platform | ❌ | ❌ | ❌ | ❌ | A community plugin |
| **Saves across boxes** | ✅ Through RomM, with conflict copies and history | Steam Cloud only | Steam Cloud, or set up your own | Steam Cloud, or set up your own | Set up your own | Steam Cloud, or set up your own |
| **Several players** | ✅ "Who's playing?": each player has their own saves, Steam, RomM account and RetroAchievements | One Steam account at a time | One Steam account at a time | One Steam account at a time | One profile | One Windows user at a time |
| **The whole box as code** | ✅ One flake: copy it to another box and get the same console | ✅ The NixOS parts, not what you set up in Steam | ❌ | ❌ | ❌ | ❌ |
| **Updates and rollback** | Each rebuild is a boot entry; a config that doesn't evaluate never gets switched to | Same as FamiDrive | Image updates, with the previous image to boot back into | Image updates, with the previous image to boot back into | Image updates | System Restore, sometimes |
| **Changing anything** | Anything: edit the flake, or override any part of it in your own config | Anything, the NixOS way | Within the image: Flatpaks, Distrobox, Homebrew; changing the image itself is discouraged | Within the image: Flatpaks; the system itself is read-only | Its config files and scripts; system changes don't survive updates | Anything Windows allows |
| **Desktop mode** | ❌ (Steam's Big Picture is under Settings) | ✅ Switch to a desktop and back | ✅ Switch to a desktop and back | ✅ A desktop session is available | ❌ | It *is* a desktop |
| **PC games that need anti-cheat** | Only the ones that allow Proton | Only the ones that allow Proton | Only the ones that allow Proton | Only the ones that allow Proton | Only the ones that allow Proton | ✅ Nearly all |
| **Cost** | Free | Free | Free | Free | Free | A Windows license |
| **Maturity** | Early: running on its first boxes | Mature | Mature, big community | Mature | Mature, big community | Mature |

## Why NixOS

FamiDrive's main bet is the base it's built on:

- **Reproducible.** The emulators, their settings, the menu, the players
  and where each game comes from are all in one flake. Put that flake on
  another box and you get the same console, as far as its hardware
  allows. Nothing on the box is set up by clicking through a UI that
  you'd have to repeat.
- **Hard to break.** A config with a mistake in it usually doesn't
  build, so you never get switched to it. If a rebuild that did build
  turns out to be wrong on the TV, the previous one is still in the boot
  menu, or one `nixos-rebuild switch --rollback` away.
- **Yours to change.** Every part of FamiDrive is a NixOS module you can
  override from your own config, and anything in nixpkgs is one line
  away. You don't have to stay within what an image allows or what's
  available as a Flatpak.

Jovian-NixOS shares the first two: it's NixOS too. The difference is
what the TV shows. Jovian-NixOS gives you Steam's gaming mode, which is
the best way to play a Steam library. FamiDrive gives you ES-DE, with
Steam as one system among the rest.

## Why not Steam as the menu

Steam's gaming mode is excellent at Steam games, and every other game is
a guest in it. Emulated games are Steam shortcuts that some tool has to
create and keep in sync. Saves that aren't in Steam Cloud need a backup
scheme of their own. Steam Input sits in front of every controller,
whether the game wants it or not. Plugins (Decky, for example) can make
it slower.

ES-DE is lighter. On the first box, its menus are quicker than Steam's,
and quitting a game gets you back to the menu sooner.

## When to pick something else

- **Your library is mostly Steam games:** Steam's gaming mode is the
  better menu for it. Pick Bazzite, ChimeraOS, or Jovian-NixOS if you
  want NixOS.
- **You want a desktop on the same box:** Bazzite, ChimeraOS and
  Jovian-NixOS all switch between gaming mode and a desktop. FamiDrive
  doesn't have a desktop mode.
- **You play online games with kernel anti-cheat:** only Windows runs
  most of those.
- **You want emulation and nothing else, with no config files:**
  Batocera runs from a USB stick and works out of the box.
- **You don't want to learn Nix:** you'll need a little of it to set up
  FamiDrive, and more to change it.

## Others worth a look

- **SteamOS:** Valve's own, and what Bazzite, ChimeraOS and Jovian-NixOS
  recreate. It ships on Valve's hardware. Installing it on other PCs
  depends on what Valve supports at the time.
- **RetroBat:** Batocera's idea on Windows: EmulationStation over
  RetroArch and standalone emulators.
- **LaunchBox and Big Box:** a Windows frontend, like Playnite. Big Box,
  its TV mode, needs a paid license.
- **EmuDeck and RetroDECK:** set up emulators and Steam shortcuts on
  SteamOS-style systems such as Bazzite and ChimeraOS. They aren't a
  whole OS.
- **Lakka:** a small Linux that boots straight into RetroArch.
