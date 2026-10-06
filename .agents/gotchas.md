# Gotchas

Things that cost a debugging session to find. If you add one, put it
next to the code it's about as a comment too.

## RomM

Found against RomM 5.3:

- **The ROM list omits nested files.** For a ROM with
  `has_nested_single_file`, `GET /roms` sends `files: []`. Fetch
  `GET /roms/{id}` to get the real file list.
- **File extensions:** use RomM's `fs_extension`, not the file name's
  suffix. "Super Smash Bros. Melee" has a dot in its name.
- **Multi-file ROMs** come as a folder. RomM offers an `.m3u` for them,
  but FamiDrive links to the folder's largest top-level file that has
  one of the system's extensions, and writes `noload.txt` inside the
  folder.
- **GameCube and Wii game IDs** come back as 4 hex-encoded characters.
  Decode them, then complete the ID from the disc itself with
  `dolphin-tool header` (`Game ID: GMPE01`). Reuse a stored ID only if
  it's complete.
- **Timestamps:** compare them as parsed datetimes (`same_time`). As
  strings, the timezone formats differ and every save looks like a
  conflict.
- **Save history:**
  - Uploads pass `autocleanup=true&autocleanup_limit=N`. RomM prunes per
    user, ROM and slot.
  - Conflict copies go to their own slot, once per version
    (`conflict_pushed`). Without that, the box uploaded a copy every 15
    minutes.
- **Renames:** a renamed ROM gets a new key in `saves.json`. `my_state`
  carries the old key's sync history over. Without it, the next push is
  a false conflict.
- **Tokens need write scopes** for save upload. A read-only token pulls
  fine and then fails on push.

## Eden (Switch)

- **`profiles.dat` layout:** a 0x10-byte header, then 8 users of 0xC8
  bytes each.
- **Save folders** are named after the user's 128-bit ID, as
  `{hi:016X}{lo:016X}`.
- **The active profile** is `current_user` in Eden's settings.
- **New profiles:** FamiDrive derives a new profile's ID from the RomM
  owner, so the same player gets the same ID on every box.
- **Save archives** store the profile folder as `@profile`, and the
  hashes are computed over the archived paths, not the local ones.

## ES-DE

- **ES-DE 3.5 runs from its AppImage, inside a bubblewrap sandbox with
  its own `/etc`.** Every game it launches inherits that `/etc`. Anything
  a launch reads from `/etc` has to be bound in through
  `extraBwrapArgs`, which is how `/etc/famidrive` gets there.
- **ES-DE 3.5 has no menu music.** FamiDrive plays it with mpv over an
  IPC socket, and gamescope-fg pauses it while a game has focus.
- **`ROMDirectory` is per player:** `~/.local/share/famidrive/roms`.
  - Shared systems in it are symlinks into `dataDir/roms`.
  - Per-player lanes (Steam, GOG, Minecraft, settings, media, ports) are
    real folders.
- **Quitting ES-DE ends the session.** `ShowQuitMenu` is on, and quitting
  runs `famidrive-end-session`, which takes you back to "Who's playing?".

## gamescope and the TV

- **Drawing with pygame under HDR:** gamescope's surface is 10 bits per
  channel, and anti-aliased text drawn straight onto it turns into
  blocks. Draw on a 32-bit surface and blit that to the screen.
- **gamescope-fg decides which window is the game.**
  - Steam runs install scripts (`SteamLaunch AppId=N Install=1`, such as
    the EA app) before the game. Their windows are tagged as the game by
    process ancestry, so they aren't hidden.
  - The game's own launcher is matched with `AppId=N( --|$)`.

## Steam

- **Steam Input is off per game**, written into `localconfig.vdf` at
  session start. That file has two `apps` blocks, and the right one is
  the top-level one.
- **A launch counts as started only when Steam's log says so**
  (`console_log.txt`). Install scripts run through the same launcher
  process first.

## Audio

- **Switching players left a dummy sink.** The previous player's
  WirePlumber kept the device, so with more than one player each session
  restarts WirePlumber at start.
- **New players get WirePlumber's default volume, which was quieter.**
  FamiDrive sets a new player's default sink volume to 1.0.

## Controllers

- **The 8BitDo 2.4 GHz dongle shows up as three devices:** a pad, a
  keyboard and a mouse. Anything that scans for pads has to skip the
  last two.
- **Dolphin tells identical pads apart by connection order**
  (`SDL/<n>/<name>`).
- **A bad USB hub looks like a bad controller.** The kernel logs
  "Cannot enable" for the port. Try another hub before debugging the
  device.

See [CONTROLLERS.md](../CONTROLLERS.md) for per-controller results.

## Nix and CI

- **writeShellApplication runs shellcheck.** A variable that's only used
  when an option is on breaks the build when it's off. Wrap it in
  `optionalString`.
- **Name clashes in checks:** a flake check can't share a name with a
  package, so packages are checked as `pkg-<name>`.
- **Defining one attribute twice:** set `systemd.services` and similar
  attributes once per module, or combine the pieces with `lib.mkMerge`.
