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
- **RomM hashes what's inside an archive,** not the archive (a zipped
  ROM then matches its known checksums). Zips are checked by size.
- **RomM has no hashes for Switch files,** and its file names carry no
  title IDs. Switch content is fetched file by file (`file_ids`) and
  checked by size.
- **A folder with extras:** RomM serves the whole folder as one zip
  unless asked for one file (`/roms/{id}/content/<file>?file_ids=<id>`).
- **RomM's file categories are its subfolder names:** `game`, `update`,
  `dlc`, `mod`, `hack`, `manual`, and so on. FamiDrive uses `update` and
  `dlc` (Switch, `contentCategories`), `mod` zips with Dolphin textures
  (texture packs), and leaves `hack` to #44.
- **RomM's `path_cover_large` can 404** (a cover it has no file for).
  Its `url_cover` is the fallback.
- **Pulls hash once:** `hashes.json` keeps each file's sha1 by size and
  mtime. Without it, every pull re-read the whole library.
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
- **Device saves:** some games keep their save on the console, not in a
  profile (Animal Crossing's island, part of Mario Kart 8's), under the
  all-zero user. They sync as they are.
- **Updates and DLC:** Eden loads them from a deep-scanned game folder
  (`ext_content_from_game_dirs`), so nothing is installed per player
  (`romm-agent eden-gamedir`).
- **Title IDs:** from a ticket's name in the NSP, else from the NCA
  headers, decrypted with the player's `header_key`. Read the file's
  contents, not its extension: one "NSP" was an XCI.
- **Learn-by-diff on Eden** must look two levels down: the top level is a
  whole profile, every game's saves.
- **Migrating saves:** "newest wins" is wrong when the game has just
  created a fresh, empty save. Check the contents (Tomodachi Life's
  played save had photos and creations; Smash's Mii numbers show how far
  it was played).
- **Save archives** store the profile folder as `@profile`, and the
  hashes are computed over the archived paths, not the local ones.
- **Eden can't run Skyline plugins** (like yuzu). A Skyline mod (HewDraw
  Remix) crashes the game about 4 s in, so those mods are left out of
  Eden and their games go to Ryujinx (`switch.ryujinx.games`).
- **Eden keeps installed firmware as one folder per NCA**
  (`registered/<id>.nca/00`, `01`, ...), not as files.

## Ryujinx (Ryubing 1.3.3)

- **`--no-gui` skips Ryujinx's game list scan,** and the scan is what
  finds updates and DLC. FamiDrive writes `games/<title id>/updates.json`
  (`selected`, `paths`) and `dlc.json` (each NSP with its content NCAs
  by `/name.nca` and decimal title ID) itself, before each launch.
- **Controller IDs:** `<n>-<SDL GUID as a .NET Guid>`, with the first 4
  digits (SDL's name checksum) replaced by `0000`, as 1.3.3's
  `SDL2GamepadDriver.GenerateGamepadId` does. Older Ryujinx code didn't
  zero them.
- **Ryujinx loads its own bundled libSDL2**
  (`lib/ryubing/runtimes/linux-x64/native/`), not the system's
  sdl2-compat. Enumerate pads through that one: the system's sees them
  differently, and inside the TV session it found none. The bundled one
  doesn't see the official GameCube adapter.
- **Save folders** are numbered (`bis/user/save/<n>/0`, committed copy);
  each one's `ExtraData0` starts with the title ID, little-endian.
  FamiDrive bridges a game's save through Eden's folder before and after
  each launch, so RomM syncs from one place.
- **Its log is the debugger:** `~/.config/Ryujinx/Logs/`. A guest crash
  shows as `InvalidAccessHandler` with a register dump; `Hid Remap: No
  matching controllers found` means the input IDs are wrong;
  `Using Firmware Version:` with nothing after it means no firmware.
- **Skyline logs over TCP** on `127.0.0.1:6969` (Ryujinx uses the host's
  network). Connect as soon as it opens (about 3 s in) to see which
  plugins loaded. HDR 0.49.11's ARCropolis needs Smash 13.0.4 exactly
  ("cannot currently run on a Smash version other than 13.0.4").

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
- **ES-DE reads launch commands once, at start.** After a switch that
  changes `es_systems.xml` but not the session, the running ES-DE still
  launches through the old famidrive-launch (#82). When testing a
  rebuild, Quit ES-DE and pick the player again.

## gamescope and the TV

- **Drawing with pygame under HDR:** gamescope's surface is 10 bits per
  channel, and anti-aliased text drawn straight onto it turns into
  blocks. Draw on a 32-bit surface and blit that to the screen.
- **gamescope-fg decides which window is the game.**
  - Steam runs install scripts (`SteamLaunch AppId=N Install=1`, such as
    the EA app) before the game. Their windows are tagged as the game by
    process ancestry, so they aren't hidden.
  - The game's own launcher is matched with `AppId=N( --|$)`.

- **Overlays over games are gamescope's external overlay:** a
  full-screen 32-bit window with `GAMESCOPE_EXTERNAL_OVERLAY` set, the
  way mangoapp does it. gamescope draws it over the focused app without
  focusing it. famidrive-toast writes premultiplied BGRA into it with
  `put_image`, in chunks under the X server's request limit.
- **Checking how a toast looks without the TV:** run the daemon under
  `xvfb-run` with `FAMIDRIVE_TOAST_SNAPSHOT=<dir>`; each toast is saved
  there as a PNG with its transparency. Screenshots of the X window lose
  the alpha.

## Steam

- **Steam Input is off per game**, written into `localconfig.vdf` at
  session start. That file has two `apps` blocks, and the right one is
  the top-level one.
- **A launch counts as started only when Steam's log says so**
  (`console_log.txt`). Install scripts run through the same launcher
  process first.
- **The app manifest's `BytesDownloaded` isn't live.** It can sit at 0
  for a whole download. Measure `steamapps/downloading/<appid>` against
  `BytesToStage` instead, and use `content_log.txt` for the real speed.
- **A full disk pauses Steam's queue for good.** Downloads that hit
  "Disk write failure" are marked paused (`StateFlags` 1538) and only
  resume when someone resumes them (the phone app's download queue).
- **Stopping and starting Steam by hand:** stop it by its exact process
  (`ps -C steam`), and start it again as the session does
  (`steam -silent`) with the session's environment (copy it from the
  ES-DE wrapper's `/proc/<pid>/environ`), or games launched later miss
  gamescope's variables.
- **GTA V on Steam is two apps:** Legacy (271590) and Enhanced (3240220),
  each with its own install folder.

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

## Clone Hero

- **Clone Hero 1.1 keeps its data in two places.** Scores
  (`scoredata.bin`, `scoresext.bin`), the song cache and Unity's `prefs`
  are in `~/.config/unity3d/srylain Inc_/Clone Hero/`. Profiles and
  settings are in `~/.clonehero/`.
- **`prefs` holds three kinds of data:**
  - the guitar bindings and calibration (Rewired's keys)
  - the window settings
  - a Unity login token

  Never sync the whole file.
- **RomM keeps saves only for entries in its library.** Clone Hero's
  saves live under an entry added by hand, which the agent finds by name
  (`famidrive.romm.apps`).

## Kodi

- **Kodi never sets `_NET_WM_PID`.** gamescope-fg finds its window's
  process through the X server (XRes, `xrestop`).
- **The joystick add-on has no maps for xpad or xpadneo pads** under
  their own names. FamiDrive seeds maps (the Xbox 360 pad's layout).
- **HDR works under gamescope.**

## Other emulators

- **RPCS3 installs firmware only through its window,** which waits for a
  click before and after (#48). Never run `--installfw` unattended.
- **RetroArch sorts saves into a folder per core by default**
  (`sort_savefiles_enable`). FamiDrive turns that off so `<game>.srm`
  sits in `saves/`, where the agent looks.
- **RetroArch names a save after the path it was given.** ES-DE hands
  over a link for folder games, and a `.cue` looks for its `.bin` beside
  that path, so RetroArch gets the real path (`readlink -f`).
- **SwanStation looks for its BIOS by one name per region**
  (`scph5501.bin` US, `scph5502.bin` Europe, `scph5500.bin` Japan).
  FamiDrive links whatever the library has under those names.
- **A dangling link in RetroArch's system folder** (`Mupen64plus`
  pointing into the library after a firmware pull removed it) stopped
  the N64 core writing its game database, so Mario Party 3 got the wrong
  save type and wouldn't start. Stale firmware links are removed at
  session start.

## Heroic, JellyCon

- **Heroic's installed games** are in `gog_store/installed.json`,
  `legendaryConfig/legendary/installed.json` and
  `nile_config/nile/installed.json` under `~/.config/heroic`; titles are
  in `store_cache/<store>_library.json`. `heroic --no-gui
  "heroic://launch?appName=…&runner=…"` exits when the game does.
- **JellyCon's server** is `server_address` in its settings.xml.
  Add-ons from outside Kodi's repository ask to be enabled once on
  Kodi's first start.

## The box

- **A full system disk:** Steam's download queue filled the first box's
  root disk twice (#90). Watch `df` before blaming anything else: a full
  disk showed up as an empty save (which went to RomM, now refused,
  #85), a black Heroic window and a paused Steam queue.
- **`pgrep -f` from SSH matches its own command line** when the pattern
  is in it. Killing by such a pattern killed the SSH session. Use
  `ps -C <name>` or a PID you've checked.
- **Two agent runs at once:** reconcile, save-pull and save-push take a
  lock per player. Don't run two by hand in parallel to test.

## Nix and CI

- **writeShellApplication runs shellcheck.** A variable that's only used
  when an option is on breaks the build when it's off. Wrap it in
  `optionalString`.
- **The Python tools' packages run flake8** (`writePython3Bin`), and their
  unit tests don't. A lambda assigned to a name (E731) passed every test
  and still failed CI. Build `.#checks.<system>.pkg-<name>` as well as the
  tool's test before pushing.
- **Name clashes in checks:** a flake check can't share a name with a
  package, so packages are checked as `pkg-<name>`.
- **Defining one attribute twice:** set `systemd.services` and similar
  attributes once per module, or combine the pieces with `lib.mkMerge`.
  `//` is shallow: `{ services.a = …; } // { services.b = …; }` drops `a`.
- **Example boxes are only evaluated,** so shell that fails ShellCheck
  only at build time used to pass CI. `box-family-launch` runs ShellCheck
  over every system's hooks and command. A `case` on a constant word is
  SC2194.
- **USAGE.md is generated:** regenerate it after any option change, and
  after rebasing a PR over another that changed options (merges can
  leave it stale). Write the build output to a temp file and check it's
  non-empty before copying, or a failed build empties USAGE.md.
- **Testing a branch on the box** without merging:
  `nixos-rebuild switch --flake /etc/nixos#<host> --override-input
  famidrive github:<owner>/FamiDrive/<branch>`. Then Quit ES-DE (#82).
