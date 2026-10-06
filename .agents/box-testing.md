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
- Run one sync by hand as the player: `romm-agent reconcile`.

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
