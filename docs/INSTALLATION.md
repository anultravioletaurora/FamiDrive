# Installation

A FamiDrive box is a private flake with two files of its own,
`flake.nix` and `configuration.nix`, plus the
`hardware-configuration.nix` NixOS made. It usually lives in
`/etc/nixos`. There are two ways to get there:

- [Fresh NixOS install](#fresh-nixos-install): a PC with no operating
  system yet, or one running something FamiDrive will replace
- [Existing NixOS install](#existing-nixos-install): a NixOS box you
  already have, moved over to FamiDrive

Both use the same [Secrets](#secrets) and
[RomM entries to add by hand](#romm-entries-to-add-by-hand), and
[Updating](#updating) works the same way after. Every option, with what
it does and its default, is in [USAGE.md](USAGE.md).

`lib.mkBox` builds on FamiDrive's own pinned nixpkgs, so every box built
from the same FamiDrive revision runs the same emulator builds, which
netplay needs.

## Fresh NixOS install

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
   to the USB stick with [Fedora Media Writer](https://flathub.org/apps/org.fedoraproject.MediaWriter)
   or [balenaEtcher](https://etcher.balena.io), or from a terminal on
   Linux or macOS with `dd`, where `/dev/sdX` is the USB stick (this
   erases it):

   ```sh
   sudo dd if=nixos-graphical-*-x86_64-linux.iso of=/dev/sdX bs=4M status=progress conv=fsync
   ```
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
   connect (the installer turns on NetworkManager):

   ```sh
   nmcli device wifi connect "<network>" password "<password>"
   ```

   To SSH in from another computer, find the box's address:

   ```sh
   ip a
   ```
5. **Make `/etc/nixos` a FamiDrive box.** The installer left
   `configuration.nix` and `hardware-configuration.nix` there. Add a
   `flake.nix` beside them, with `nixosConfigurations.tv` named after the
   computer name:

   ```nix
   # flake.nix
   {
     inputs.famidrive.url = "github:anultravioletaurora/FamiDrive";

     outputs = { famidrive, ... }: {
       nixosConfigurations.tv = famidrive.lib.mkBox ./configuration.nix;
     };
   }
   ```

   In `configuration.nix`, keep everything the installer wrote,
   especially `system.stateVersion`, the boot loader, networking, time
   zone and the user account, and add a `famidrive` block:

   ```nix
   famidrive = {
     enable = true;
     players.alice = { };          # the account the installer made
     lanes = [ "roms" "steam" ];
     romm.enable = false;          # or true, with the steps below
     localRoms.gc = "/srv/roms/gamecube";   # games already on the box, by system
   };
   ```

   Every option is in [USAGE.md](USAGE.md), and
   [Players](../README.md#players) covers more than one player and the
   guest.
   - **Without a RomM server:** keep `romm.enable = false`. No secrets
     are needed. Games come from folders on the box (`localRoms`);
     plugging in a drive and having it just work is
     [#99](https://github.com/anultravioletaurora/FamiDrive/issues/99).
   - **With RomM:** set `romm.enable = true` and `endpoints.romm`, and
     give the box its age key and each player's token. Make the key:

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

     Then open `secrets.yaml` with sops, which finds `.sops.yaml` from
     the folder you're in:

     ```sh
     cd /etc/nixos && sudo env SOPS_AGE_KEY_FILE=/var/lib/sops-nix/key.txt nix --extra-experimental-features 'nix-command flakes' run nixpkgs#sops -- secrets.yaml
     ```

     and add alice's token, as in [Secrets](#secrets):

     ```yaml
     alice:
       romm: rmm_…
     ```

     Last, point `configuration.nix` at it:

     ```nix
     sops.defaultSopsFile = ./secrets.yaml;
     sops.age.keyFile = "/var/lib/sops-nix/key.txt";
     ```
   - **A second disk for the library:** format it, where `/dev/<disk>` is
     that disk (this erases it):

     ```sh
     sudo mkfs.ext4 -L famidrive /dev/<disk>
     ```

     and mount it at `/var/lib/famidrive` in `configuration.nix`:

     ```nix
     fileSystems."/var/lib/famidrive" = {
       device = "/dev/disk/by-label/famidrive";
       options = [ "nofail" ];
     };
     ```
6. **Build and switch.** If `/etc/nixos` is a git repository, add new
   files first, because flakes only see what git tracks:

   ```sh
   cd /etc/nixos && sudo git add -A
   ```

   Then build:

   ```sh
   sudo nixos-rebuild switch --flake /etc/nixos#tv --extra-experimental-features 'nix-command flakes'
   ```

   The first build downloads several gigabytes (Steam, the emulators,
   ES-DE). FamiDrive turns flakes on, so later rebuilds don't need the
   last flag.
7. **Reboot.** After the boot screen, the TV shows ES-DE, or "Who's
   playing?" with more than one player.

   ```sh
   sudo reboot
   ```
8. **First run, on the TV:**
   - **Controllers:** 2.4 GHz dongles and wired pads work as they are.
     For a Bluetooth pad, put it in pairing mode and launch Controllers
     → Pair a Controller (always the first entry): the first pad found
     is paired, and toasts say how it went. Controllers → Forget
     <controller> unpairs one.
     [CONTROLLERS.md](CONTROLLERS.md) has each pad's notes.
   - **Wi-Fi:** Settings lists the networks in range as "Wi-Fi:
     <network>". An open one joins when launched. For one with a
     password, press Select on it, choose "Edit this game's metadata",
     type the password as its **Sort name** with ES-DE's on-screen
     keyboard, Save, then launch it. The password is wiped from ES-DE's
     list after joining, and the box remembers the network.
     Settings → Ethernet shows the wired port: cable, address, speed and
     hardware address. The lists are as they were when ES-DE started.
   - **Steam:** sign in under Steam → Steam Settings, the first entry
     in the Steam system.
   - **The other PC stores**, if `lanes` has `"stores"`: Epic under
     Epic Games Store → Heroic Games Launcher; GOG, Amazon, Battle.net,
     EA, Ubisoft and Humble Bundle under Lutris → Lutris. Each launcher
     is the first entry in its system, after any favorites
     (`famidrive.stores` says which launcher has each).
     For Battle.net, launch Lutris → Install Battle.net, and close
     Battle.net's sign-in window when the installer gets there; sign
     in the first time you start Battle.net. Then install games from
     Battle.net itself: each one it installs is in the Lutris system
     the next time ES-DE starts.
   - **Jellyfin:** sign in once in Media.
   - **RomM:** with a token, the library pull starts by itself (every
     30 minutes). To start it now, over SSH:

     ```sh
     sudo systemctl start romm-library-pull
     ```

     Then add the [RomM entries](#romm-entries-to-add-by-hand) for the
     apps you turned on.

## Existing NixOS install

This is the path the first box takes: an existing NixOS gaming box whose
ROM drive is wiped and refilled from RomM, with old saves imported into
RomM along the way.

1. **Back up saves** off the box: Dolphin's `GC/` and `Wii/`, Eden's
   `nand/user/save`, Prism's instances, Steam's `userdata`, and
   `/etc/nixos`. For `/etc/nixos`, for example:

   ```sh
   sudo tar czf ~/etc-nixos-backup.tar.gz /etc/nixos
   ```

   Then note the current generation number; it's the way back:

   ```sh
   nixos-rebuild list-generations
   ```
2. **Write the host files.** Add a `flake.nix` to `/etc/nixos`, with
   `nixosConfigurations.tv` named after the box:

   ```nix
   # flake.nix
   {
     inputs.famidrive.url = "github:anultravioletaurora/FamiDrive";

     outputs = { famidrive, ... }: {
       nixosConfigurations.tv = famidrive.lib.mkBox ./configuration.nix;
     };
   }
   ```

   Then add FamiDrive to `configuration.nix`. A whole one looks like
   this:

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

     sops.defaultSopsFile = ./secrets.yaml;   # the RomM token, step 3
     sops.age.keyFile = "/var/lib/sops-nix/key.txt";
   }
   ```

   Keep `system.stateVersion` at the original install's value. Make the
   existing account a player (`famidrive.players.<account> = { };`), so
   the Steam library and emulator data carry over. Carry over anything
   else the old config did that isn't about Steam (Sunshine, Avahi,
   Bluetooth, GPU tools). Fill in `endpoints.romm`, and set `owner` on
   the player if their RomM username isn't the account's name (see
   [Players](../README.md#players)). Every option is in
   [USAGE.md](USAGE.md).
3. **Give the box its RomM token.** Make an age key on the box:

   ```sh
   sudo mkdir -p /var/lib/sops-nix
   sudo nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#age -c age-keygen -o /var/lib/sops-nix/key.txt
   ```

   Add the public key it prints (`age1…`) to `/etc/nixos/.sops.yaml`:

   ```yaml
   creation_rules:
     - path_regex: secrets\.yaml$
       age: age1…
   ```

   Create a Client API Token in RomM with the scopes under
   [Secrets](#secrets), and put it in the host's `secrets.yaml` with sops:

   ```sh
   cd /etc/nixos && sudo env SOPS_AGE_KEY_FILE=/var/lib/sops-nix/key.txt nix --extra-experimental-features 'nix-command flakes' run nixpkgs#sops -- secrets.yaml
   ```
4. **Prepare the library disk.** Wipe it and format it, where
   `/dev/<disk>` is that disk:

   ```sh
   sudo mkfs.ext4 -L famidrive /dev/<disk>
   ```

   The host mounts it by that label at `/var/lib/famidrive`:

   ```nix
   fileSystems."/var/lib/famidrive" = {
     device = "/dev/disk/by-label/famidrive";
     options = [ "nofail" ];
   };
   ```
5. **Build on the box itself.** If the host flake is a git repo, flakes
   only see files git tracks, so add them first:

   ```sh
   cd /etc/nixos && sudo git add -A
   ```

   Then build:

   ```sh
   nixos-rebuild build --flake /etc/nixos#tv --extra-experimental-features 'nix-command flakes'
   ```

   Nothing on the box changes yet. Fix things until it builds.
6. **Try it without committing,** over SSH:

   ```sh
   sudo nixos-rebuild test --flake /etc/nixos#tv
   ```

   That switches the running system but not the boot default, so if
   anything goes wrong, a reboot brings back the old system. The TV's
   session restarts by itself when the switch changed it
   ([`famidrive.session.restartOnSwitch`](USAGE.md#famidrivesessionrestartonswitch)).
   If a library folder is missing:

   ```sh
   sudo systemd-tmpfiles --create
   ```
7. **Pull a little first.** Set `romm.collection` to a small test
   collection:

   ```nix
   famidrive.romm.collection = "<test collection>";
   ```

   Switch to it with `nixos-rebuild test` as in step 6, then pull:

   ```sh
   sudo systemctl start romm-library-pull
   ```

   Check the games show up in ES-DE. Then set `romm.collection` back to
   `null` and let the full pull run (the timer does it every 30 minutes;
   it resumes where it stopped).
8. **Bring old saves in.** Copy them back into each emulator's save
   folder ([Bringing saves from another setup](../README.md#bringing-saves-from-another-setup)
   lists them). Sort out any duplicate Eden profiles first: FamiDrive
   syncs the one Eden runs games as; set the player's
   [`edenProfileId`](USAGE.md#famidriveplayersnameedenprofileid) only if
   that isn't the one with the real saves. Then reconcile as that
   player, here `alice`:

   ```sh
   sudo systemctl start romm-save-reconcile-alice
   ```

   Every save RomM doesn't have goes up, under their RomM user.
9. **Check:** a GameCube game, a Switch game and a Steam game each launch,
   take focus, and quit back to ES-DE; the controller works throughout; a
   new save shows up in RomM after quitting; Media → Jellyfin plays
   something. Add the [RomM entries](#romm-entries-to-add-by-hand) for
   the apps you turned on.
10. **Commit to it,** and reboot:

    ```sh
    sudo nixos-rebuild boot --flake /etc/nixos#tv
    sudo reboot
    ```

    Don't garbage-collect for a while: the old system's generation in the
    boot menu is the safety net.

## Secrets

Server addresses aren't secret and go in `configuration.nix`. Logins for
Jellyfin, Steam and the PC stores (in Heroic and Lutris) happen once in
each app, on the TV. The only secrets are in the host's `secrets.yaml`,
encrypted with [sops](https://github.com/getsops/sops) to the box's
[age](https://github.com/FiloSottile/age) key plus yours, and read on the
box by [sops-nix](https://github.com/Mic92/sops-nix). Each player's are
together under their name:

```yaml
alice:
  romm: rmm_…
  retroachievements: …
bob:
  romm: rmm_…
```

- `romm`: one per player, a RomM Client API Token (`rmm_…`)
  issued by that player's RomM user. The primary player's
  ([`famidrive.primaryPlayer`](USAGE.md#famidriveprimaryplayer)) also
  pulls the shared library. Scopes the agent uses: `roms.read`,
  `platforms.read`, `firmware.read`, `collections.read`, `assets.read`,
  `assets.write`, `devices.read`, `devices.write`. Add `roms.write` to
  let a box write game IDs it worked out back to RomM (optional; skipped
  quietly without it).
- `retroachievements`: the player's RetroAchievements password, for
  players with `retroAchievements.username` set.
- `rpcn`: their RPCN account's password, for PS3 online
  (`famidrive.online.ps3.enable`, [PS3.md](Online-Play/PS3.md)).
- `nexusmods`: their Nexus Mods personal API key, for players with
  `nexusmods.games` set. Downloading needs a premium Nexus Mods account
  ([MODDING.md](MODDING.md)).
- `smb`: their password for file sharing, for players whose
  `smb.passwordFile` points at it ([File sharing](#file-sharing)).

Before 2026-10-10 these were top-level keys (`romm-token-alice`,
`retroachievements-alice`, `rpcn-password-alice`). Move each under its
player, with the new name, before rebuilding with a newer FamiDrive.

A box with `famidrive.romm.enable = false` needs no secrets and no sops
setup at all.

## File sharing

Each player's home folder is on the network over SMB, unless the box
sets `famidrive.smb.enable = false`. It's how to change the menu's music
(`ES-DE/music`, played from the player's next session on) or copy
recordings off (`Recordings`) from another computer. On a Mac the box
is under Network in Finder's sidebar, by its hostname; on Windows it's
under Network.

Sign in as the player's Linux account. Samba can't check a Linux
password, so each player needs an SMB password as well. Set it once on
the box:

```sh
sudo smbpasswd -a alice
```

Or keep it with the player's secrets, as `smb` under their name, and
point their `smb.passwordFile` at it; it's set at each boot:

```nix
sops.secrets."alice/smb" = { };
famidrive.players.alice.smb.passwordFile = config.sops.secrets."alice/smb".path;
```

The guest can't sign in.

## RomM entries to add by hand

RomM keeps saves only for games in its library, and some apps on the box
aren't ROMs. To sync their saves, add one entry for each in RomM's web
UI, once for the whole RomM server, with "Add Physical Game" (no file
needed) and exactly this name. Any platform works; the box doesn't
download physical entries, so an app's entry can sit with the console it
belongs to:

| Turned on with | RomM entry | What syncs |
|---|---|---|
| `cloneHero.enable` | `Clone Hero` (`cloneHero.romm.entry`) | each player's scores and profiles |
| `yarg.enable` | `YARG` (`yarg.romm.entry`) | each player's scores and profiles |
| `miis.wii.enable` | `Mii Channel` (`miis.wii.romm.entry`), on the Wii platform | each player's Wii Miis |

Without its entry, an app still works, and its saves stay on the box.

## Updating

Updating later is the same for every box:

```sh
cd /etc/nixos && sudo nix flake update famidrive && sudo nixos-rebuild switch --flake /etc/nixos#tv
```

If an update misbehaves, pick the previous generation in the boot menu.
