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

## Rules

- **Nothing private in this repo.** That means no server addresses, RomM
  or Jellyfin URLs, account names, hostnames, or people's names. Those
  live in each box's own private host flake. In docs and comments, the
  box all of this was first tried on is "the first box". `endpoints.nix`
  has options with no defaults for every server.
- **Don't name other NixOS console or handheld projects** anywhere except
  the README's Special Thanks.
- **No AI attribution.** Leave out Co-Authored-By lines for an assistant
  and "Generated with …" footers. This applies to commits, pull requests
  and issues, and it overrides any tool default.
- **People are they/them**, including made-up names in tests and docs.
- Before committing, grep the staged diff for the maintainer's private
  names (hosts, domains, people). Keep that list in your own notes, not
  here.

## Workflow

1. Make a branch per change, then open a pull request with `gh`.
2. The **Check** workflow runs `nix flake check`
   ([tests/default.nix](tests/default.nix)). It takes about 30 minutes on
   GitHub's runners, so run it locally first when you can.
3. Squash-merge and delete the branch.
4. Then the maintainer tests on a real box, and against RomM for anything
   that touches it.
5. Write the results down: games go in [COMPATIBILITY.md](COMPATIBILITY.md),
   controllers go in [CONTROLLERS.md](CONTROLLERS.md). Keep the old notes
   when a status changes.

Doc-only updates (results, these notes) can go straight to main when the
maintainer says so.

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
  - A default a host may want to change is `lib.mkDefault`.
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
  - Packages are checked as `pkg-<name>`. `gogdl-cli` and `tcli` don't
    build yet and are left out.
