# Trying a change on a real box

A box is its own private flake that imports this one through
`famidrive.lib.mkBox`. Its config sits in `/etc/nixos` and is owned by
root. This repo has no hosts.

## Build without switching

You can check that a branch builds for a real box without touching the
running system.

1. Copy the box's flake to a folder you own, such as `~/famidrive-host`.
2. rsync this repo next to it, such as `~/famidrive-repo`.
3. Build:

```sh
cd ~/famidrive-host
nix build --no-link --print-out-paths \
  .#nixosConfigurations.<host>.config.system.build.toplevel \
  --override-input famidrive path:$HOME/famidrive-repo
```

To see what would restart, diff the result against `/run/current-system`.

When the maintainer changes the real `/etc/nixos/configuration.nix`,
copy it into the test folder again so the two don't drift apart.

## Deploying, after a merge

The maintainer runs:

```sh
cd /etc/nixos && sudo nix flake update famidrive \
  && sudo nixos-rebuild switch --flake /etc/nixos#<host>
```

## What restarts the TV

`famidrive.session.restartOnSwitch` (default on) restarts greetd during
the switch whenever its unit changes. That ends whatever is on screen.
greetd's unit changes whenever anything in the session script's closure
changes.

To avoid that, the session calls FamiDrive's own tools by name, from
`environment.systemPackages`, not by store path. That covers
`romm-agent` and `famidrive-clonehero`. A fix to one of those tools then
doesn't restart the TV. Do the same for any new tool the session runs.
Changing the session itself (session.nix, the picker, gamescope-fg)
still restarts the TV. Warn the maintainer before they rebuild.

## Over SSH

- Use `ssh -o ConnectTimeout=10`. A bare SSH call can hang.
- Many Macs don't have `timeout`.
- Each player's user services:
  `sudo systemctl --user -M <user>@ status …`, or
  `sudo -u <user> XDG_RUNTIME_DIR=/run/user/<uid> systemctl --user …`.
- Library services are system units: `romm-library-pull`,
  `famidrive-clonehero-songs`.
- Each player's RomM agent state is in `~/.local/state/romm-agent/`:
  `saves.json`, `save-snapshot.json`, `device.json`.
- Run one sync by hand as the player: `romm-agent reconcile`. Or wait:
  each player has a `romm-save-reconcile-<user>` timer, every 15 minutes,
  and its log is that unit's journal.
- **There's no `python3` on a box's PATH.** Borrow a FamiDrive tool's
  Python environment, which has its libraries: famidrive-quit's has
  `evdev`, famidrive-toast's has `pygame` and `Xlib`. Find the path in
  `ps -eo args` (the first word of the tool's command line). The
  binary that `/proc/<pid>/exe` points at is a bare Python without them.
- **Don't trust SSH to stay up for big transfers.** On one network, a
  copy of a few MB kept dying partway, and then new connections were
  refused for minutes (ping still worked). Keep transfers small: crop or
  shrink on the box first, or `base64` a small file through a command.

## Seeing what's on the TV

- **A screenshot:** set `GAMESCOPECTRL_REQUEST_SCREENSHOT` on the root
  window of the session's X display (`DISPLAY=:0`) with `xprop`
  (`nix build nixpkgs#xorg.xprop`). gamescope writes `/tmp/gamescope.png`.
  It didn't show toasts that a capture card on the HDMI output did, so
  it can't prove an overlay isn't there.
- **The toast window's own pixels:** with famidrive-toast's Python, find
  the window named `famidrive-toast` under the root and `get_image` the
  corner the toasts use. All-zero alpha means nothing is drawn there.
- **Ask before putting anything on the screen** (a test toast, a game):
  someone may be playing.

## Reading a controller

- `/proc/bus/input/devices` gives the name, USB ID and key bitmap, and
  `/sys/class/input/event<N>/device/device/driver` the kernel driver.
- To see which codes the buttons send, read the device with `evdev`
  (famidrive-quit's Python) while the maintainer presses them. Read only:
  never grab a pad someone's using.
- ES-DE's log (`~/ES-DE/logs/es_log.txt`) lists each pad as SDL sees it,
  with its GUID, as it connects.
- The kernel log (`journalctl -k`) shows USB drops. A pad that drops
  off and comes back every few seconds, or logs `error -71`, is a bad
  pad, cable or port, not a FamiDrive bug. Try another port first.
- `bluetoothctl list` before pairing anything: small office PCs often
  have no Bluetooth at all.

## Importing saves from another console OS

Put the save files where the emulator keeps them, in the player's home,
as that player. The next reconcile finds and uploads each one that
belongs to a game in the box's library. That means a game listed in
`/var/lib/famidrive/index.json`, the library's index; a game that isn't
in it is skipped. Check the player's `saves.json` afterwards.

- **GameCube:** Dolphin's GCI folder,
  `~/.local/share/dolphin-emu/GC/<region>/Card A/`, where region is
  `USA`, `EUR` or `JAP` from the disc's header. Batocera keeps GameCube
  saves as `.gci` files too; they copy straight in. Done for one player
  on the second box 2026-10-08 (9 games).
- Check the folder is empty first, or move what's there aside: never
  overwrite a player's saves.

## Secrets

RomM tokens and other secrets are in `/run/secrets` (sops-nix). Read
them only on the box, for example:

```sh
T=$(cat /run/secrets/romm-token-<user>)
curl -H "Authorization: Bearer $T" …
```

Never copy a secret off the box or print it.

## Testing against RomM

Debug against the server's own `GET /api/openapi.json` and real
responses, not the docs. Several fields don't match what their names
suggest; see [gotchas.md](gotchas.md#romm).

To test the pull on a few games before the whole library, a host can set
`famidrive.romm.collection` to a small RomM collection.
