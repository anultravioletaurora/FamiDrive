# Notes for coding agents

FamiDrive is a NixOS flake that turns a PC into a TV game console:
greetd → "Who's playing?" → gamescope → ES-DE, with emulators, Steam,
GOG, Minecraft and Clone Hero behind it, and RomM as the library and
save server. Read [README.md](README.md) first. Its Layout section maps
every module and package.

More detail, by topic:

- [.agents/box-testing.md](.agents/box-testing.md): building and trying
  a change on a real box, and what makes the TV restart
- [.agents/gotchas.md](.agents/gotchas.md): things that cost a debugging
  session to find, by area (RomM, ES-DE, gamescope, Steam, audio, CI)

## The boxes

Two real boxes run FamiDrive so far. In docs, comments and commits they
are only ever "the first box" and "the second box":

- **The first box:** a big AMD gaming PC (Ryzen 9 7900X, Radeon RX 7900
  XTX) on a 4K120 HDR TV. An existing NixOS box moved over (the README's
  "Moving an existing NixOS box over"). Several players and a guest.
  Most results in the docs come from it.
- **The second box:** a small Intel office PC (Dell OptiPlex 3070 Micro,
  i5-9500T, UHD 630 graphics, 16 GB) on a TV at 1080p, wired Ethernet,
  no Bluetooth. A fresh install straight from the README, with one
  player and no guest, so it boots past "Who's playing?" into ES-DE. It's
  the check that the README's install steps work as written and that a
  low-end Intel box is enough for the older consoles.

Results from either go in the docs with the box named that way and a
date.

## Where it's going

Today a box is NixOS installed by hand, plus a private host flake that
someone writes. The goal is to take away everything before FamiDrive
takes over. FamiDrive's job ends once the box is built and set up.

- **An installer, so FamiDrive works like a distro**
  ([#156](https://github.com/anultravioletaurora/FamiDrive/issues/156)).
  A blank PC boots the image, installs, and finishes a first-boot setup
  with only a controller: players, network, pairing controllers, RomM,
  which systems to show. The steps, in order:
  1. A binary cache that CI pushes to. GitHub can't host one, and
     unfree builds stay out of it.
  2. The answers a host gives live in a `famidrive.json` that
     `lib.mkBox` reads, and there's a host-flake template.
  3. An installer ISO with the system pre-built in its store, plus
     disko and nixos-facter.
  4. A controller-driven installer and first-boot setup.
  5. Settings and automatic updates from the couch.
- **Other distros**
  ([#157](https://github.com/anultravioletaurora/FamiDrive/issues/157)).
  Split the modules into a per-player home-manager module and host
  modules (system-manager), so a box on Fedora with Nix gets the same
  apps and per-player setup. Greetd, the picker, players as accounts
  and boot-menu rollback stay NixOS-only. A Docker image was considered
  and set aside: FamiDrive's core is the display, the input devices and
  the kernel, which a container shares with the host.

What this means for changes now:
- **Keep per-player config separate from host config.** Per-player
  config goes in `famidrive.playerHome`.
- **Prefer options that are plain data** (strings, lists, attrsets of
  them), so a setup screen could write them to JSON later.
- **Don't make a player hand-edit Nix** for something a setup screen
  could ask.

## Rules

- **Nothing private in this repo.** That means no server addresses, RomM
  or Jellyfin URLs, account names, hostnames, or people's names. Those
  live in each box's own private host flake. In docs and comments, boxes
  are "the first box" and "the second box" ([The boxes](#the-boxes)).
  `endpoints.nix` has options with no defaults for every server.
- **Don't name other NixOS console or handheld projects** anywhere except
  the README's Special Thanks and [COMPARISON.md](docs/COMPARISON.md).
- **No AI attribution.** Leave out Co-Authored-By lines for an assistant
  and "Generated with …" footers. This applies to commits, pull requests
  and issues, and it overrides any tool default.
- **People are they/them**, including made-up names in tests and docs.
- **Name things the way ES-DE shows them.** Anything a player reads (a
  toast, a menu entry, a message) calls a game or app by the name it has
  in ES-DE: "Mii Channel", "Clone Hero", "Mii Maker". Never an internal
  key (`app:wii-miis`) or a description ("Wii Miis").
- Before committing, grep the staged diff for the maintainer's private
  names (hosts, domains, people). Keep that list in your own notes, not
  here.
- **Games are the user's own.** FamiDrive is for games people legally
  own and backups they made themselves. It ships no games, BIOS, keys or
  firmware, and the docs never link to where to get them.
- **Secrets stay on the box:** RomM tokens, RetroAchievements logins,
  console keys. Read them there when a test needs them; never copy them
  off, print them, or paste them into an issue.
- **Ask before:**
  - putting anything new on a box's TV (test toasts, launching a game)
    while someone may be using it
  - deleting anything of a player's (saves, games, settings), and back
    it up first when editing their files
  - accepting a EULA or terms of service for someone. FamiDrive helps a
    player answer the prompt with the controller
    (famidrive-padmouse); it never answers for them.

## Workflow

1. Make a branch per change, then open a pull request with `gh`.
2. The **Check** workflow runs `nix flake check`
   ([tests/default.nix](tests/default.nix)). It takes about 25–30 minutes
   on GitHub's runners, so run it locally first when you can. On a Mac
   without Nix, run the Python unit tests directly
   (`python3 tests/<name>_test.py pkgs/<name>/<file>.py`) and let CI do
   the rest. A box can build checks too (see
   [box-testing.md](.agents/box-testing.md)).
3. Pull requests that build on each other are merged in order, each
   rebased onto main after the one before it lands.
4. Squash-merge and delete the branch.
5. Then the maintainer tests on a real box, and against RomM for anything
   that touches it.
6. Write the results down: games go in [COMPATIBILITY.md](docs/COMPATIBILITY.md),
   controllers go in [CONTROLLERS.md](docs/CONTROLLERS.md). Keep the old notes
   when a status changes.

Doc-only updates (results, these notes, the files in `docs/`) go
straight to main.

## Docs

- [README.md](README.md) is the front page: what FamiDrive is, its
  status, installing, and a **Docs** list linking every page in `docs/`.
- `docs/` holds the rest, all Markdown, so it can become a GitHub Pages
  site later: [COMPARISON.md](docs/COMPARISON.md),
  [USAGE.md](docs/USAGE.md) (generated, never edited by hand except to
  mirror an option's description exactly), [COMPATIBILITY.md](docs/COMPATIBILITY.md)
  and [CONTROLLERS.md](docs/CONTROLLERS.md). A new page goes in `docs/`
  and gets a line in the README's Docs list. Links between pages in
  `docs/` are relative; links to code use `../`.
- **Recording a result:** a dated bullet that says which box, what was
  tried and what happened, with ✅ 🟡 ❌ ❔ as each page defines them.
  Keep the old bullets when a status changes.
- **A new controller** gets three things in CONTROLLERS.md: a row in "At
  a glance", a line in Contents, and a section. Record its USB ID and
  kernel driver (`/proc/bus/input/devices`, and
  `/sys/class/input/event<N>/device/device/driver`), and the name SDL
  gives it (ES-DE's log has it). A pad on `hid-generic` has numbered
  buttons whatever their names say, so note that.
- **The README's Status section** says what's real. Update it when a
  box proves something new, or when something listed there breaks.

The maintainer runs the `sudo` rebuilds on the box themselves. Hand them
the exact commands.

## Writing code here

- **Comments say why**, and where a fact came from. A finding from real
  hardware gets dated: `Found on the first box 2026-10-06: …`. Comments
  also point to design notes by file name (`roms.md`, `controllers.md`).
  Those notes aren't in the repo yet.
- **Options:**
  - A host sets everything under `famidrive.*`, and every option gets a
    description.
  - [USAGE.md](docs/USAGE.md) is generated from the options and CI fails
    when it's out of date. After adding or changing an option, rebuild
    it on an x86_64-linux machine:
    `nix build .#checks.x86_64-linux.usage-doc.doc && cp result docs/USAGE.md`.
    A new top-level option group needs a section in `tests/usage_doc.py`,
    or it lands under "Everything else".
  - A default a host may want to change is `lib.mkDefault`.
  - An app whose saves sync under a RomM entry made by hand
    (`famidrive.romm.apps`, like Clone Hero and YARG) gets a row in the
    README's "RomM entries to add by hand" table.
  - A renamed or removed option gets `mkRemovedOptionModule` or
    `mkRenamedOptionModule` with a message that says what to use instead.
- **Players:**
  - `famidrive.allPlayers` (internal) is every player, plus the guest when
    it's on, with `home`, `roms`, `tokenFile` and `isGuest` filled in.
  - Per-player home-manager config goes in `famidrive.playerHome`, which
    receives `famidrivePlayer`.
  - Shell that has to run at each session start goes in
    `famidrive.sessionSetup`.
- **Configs that the app also writes** (Dolphin.ini, ES-DE settings,
  Clone Hero's settings.ini): use `lib/seed.nix`. `seed` writes a file
  only if it's missing. `lockKeys` resets just the keys FamiDrive owns
  and leaves everything else to the app.
- **Shared library disk:**
  - `dataDir` belongs to the `famidrive-library` user and the `famidrive`
    group.
  - Services that write to it need `RequiresMountsFor = dataDir`, plus an
    ExecStartPre of `+systemd-tmpfiles --create --prefix=…`. The disk can
    mount after tmpfiles has already run.
- **Python tools** live in `pkgs/<name>/` and each one has a
  `tests/<name>_test.py`. Unit tests run against made-up files in a temp
  directory, with no network. Use an environment variable to point a
  URL at a local file, as `FAMIDRIVE_ENCORE` does.
- **New tests:**
  - Register a unit test in `tests/default.nix`.
  - For a module change, add a check to an example box (`box-one-player`,
    `box-family`).
  - Packages are checked as `pkg-<name>`. `tcli` doesn't build yet and
    is left out.
