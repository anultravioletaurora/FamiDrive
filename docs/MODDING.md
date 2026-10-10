# Modding

FamiDrive installs mods from three places, all of them declared once and
kept in place without anyone at the TV with a keyboard:

| Mods for | From | Chosen in | Account |
|---|---|---|---|
| Steam and GOG games (Cyberpunk 2077, Fallout: New Vegas) | [Nexus Mods](#nexus-mods) collections and Wabbajack lists | each player's config | the player's, premium |
| Valheim, Risk of Rain 2 and other BepInEx games on Steam | [Thunderstore](#thunderstore) | each player's config | none |
| GameCube, Wii and Switch games | [your RomM library](#emulators) | RomM | none |

Mods come from their authors' pages; FamiDrive downloads them the way
you would, with your own account where one is needed.

## Nexus Mods

A Nexus Mods **collection** is a curator's list of mods for a game: which
file of each, in what order, and how each installs. FamiDrive installs a
collection into a player's Steam copy of the game, the way Vortex does,
and keeps it there: change the config and rebuild, and the game's mods
follow.

### What you need

- **A premium Nexus Mods account.** Nexus Mods lets a program download
  files directly only for premium accounts. A free account has to click
  "Slow download" on the website for every file, and FamiDrive doesn't
  get around that.
- **Its personal API key** (nexusmods.com → your account → Site
  preferences → API Keys), in the box's `secrets.yaml` under the player:
  ```yaml
  alice:
    nexusmods: <the API key>
  ```
- **Adult content allowed** on the account, for collections Nexus Mods
  marks adult (many large ones are, for a few of their mods). A key
  without it can't see them.
- **The game installed** in the player's Steam library, or through
  Heroic for a GOG game, and run once.

### Setting it up

Each game gets one or more collections, by the id at the end of the
collection's address and a revision. A Steam game goes by its app id, a
GOG game (installed through Heroic) as `gog:<GOG id>`:

```nix
famidrive.players.alice.nexusmods.games."1091500" = {   # Cyberpunk 2077
  collections = [
    { slug = "rcuccp"; revision = 189; }   # NCR Core
    { slug = "srpv39"; revision = 129; }   # NCR - Extras
    { slug = "g0tcm4"; revision = 42; }    # High-Res Graphics Pack - MAXIMUM
  ];
  # Options to pick in mods whose installer (FOMOD) the collection
  # leaves to the player, by mod name.
  choices."WTNC Config" = [ "Cyberpunk THING" ];
};
```

- **The slug** is the last part of the collection's address:
  `nexusmods.com/games/cyberpunk2077/collections/iszwwe` is `iszwwe`.
- **The revision** is pinned, like a flake input. A curator publishes new
  revisions; FamiDrive uses one only once it's set here, so a working
  setup never changes under a player mid-playthrough.
- **Several collections** install in the order listed. Where two have the
  same file, the later one's wins. A big modpack and a separate texture
  pack is the usual pairing.
- **Choices** are for installers the collection didn't record a choice
  for. Without one, the installer's own default is used (its first
  option, where one must be picked).

### What a rebuild does

Each player has a service, `famidrive-nexusmods-<player>`, that a rebuild
starts whenever it changes that player's mods (and that runs at boot). It
doesn't hold up the rebuild: downloads happen in the background, with a
progress toast on the TV.

- **Mods added:** every file of every collection is downloaded into the
  player's cache (`~/.cache/famidrive/nexusmods`) and checked against the
  collection's checksum. Once all are there, they're installed in the
  game's folder.
- **Mods changed** (another collection, a new revision, other choices):
  the old install comes out, then the new one goes in. Files already
  downloaded are kept, so going back is quick.
- **Mods removed** (a game taken out, or all of a player's mods): that
  game's mods come out, and everything they had replaced is put back.
- **A rebuild while it's still downloading** stops that run, which
  cancels its downloads, and starts again with the new config.
- **The game running:** installing waits until it's closed.
- **The game not installed** (or Steam updating it): its mods wait, and
  go in on a later run.
- **Vortex managing the game** (its `vortex.deployment.json` in the
  game's folder): left alone, with a toast. See [Moving from Vortex](#moving-from-vortex).
- **A download failing** (a server down, a file pulled): tried again the
  next day.

### How mods are installed

- **In the collection's order:** by its install phases, then its "after"
  rules. Where two mods have the same file, the later one's wins.
- **Where each file goes:** from the collection itself where it says
  (mods the curator installed by hand list their exact files), from the
  mod's FOMOD installer (with the curator's recorded choices, or the
  player's), and otherwise by the game's own rules, written to match
  Vortex's extension for the game. Cyberpunk 2077 has rules: checked
  against Vortex on the first box, they put 265 of 268 mods of Welcome to
  Night City where Vortex did, and the other 3 Vortex had failed to install.
  A game without rules installs only its exact and FOMOD mods.
- **Folder names follow the case already in the game's folder,** since
  the game (under Proton) doesn't care about case and Linux does.
- **Anything already there** (one of the game's own files, a settings
  file a mod wrote while you played) is moved to a backup first,
  `~/.local/share/famidrive/nexusmods/backup/<app id>/`, and put back
  when the mods come out.
- **Every file installed is recorded,** in
  `~/.local/share/famidrive/nexusmods/installed/<app id>.json`, as it
  goes, so even an install cut short comes out cleanly.

Mods that aren't on Nexus Mods (a collection can point to a website)
can't be downloaded for you; they're listed in the service's log.

### Moving from Vortex

A game whose mods Vortex installed (directly, or through Lutris or Steam
Tinker Launch) is left alone until Vortex's install is out of its
folder. Vortex installs mods as hard links to its own staging folder, so
nothing is lost moving them aside. With the game and Vortex closed:

1. **Back up Vortex's files:** each file `vortex.deployment.json` lists,
   hard-linked into a backup folder (`cp -al`, no extra space), with
   `vortex.deployment.json` itself and every `*.vortex_backup` file.
2. **Remove them** from the game's folder.
3. **Put back what Vortex replaced:** each `<file>.vortex_backup` back
   to `<file>`, as Vortex does when it purges.
4. **Remove `vortex.deployment.json`,** so neither Vortex nor FamiDrive
   thinks Vortex's mods are still there.

The next run installs the collection. To go back to Vortex, remove
FamiDrive's mods (take the game out of the config and rebuild) and link
the backup back in.

### Checking on it

- **What it's doing:** `journalctl -u famidrive-nexusmods-<player>`.
- **Where each file would go,** without installing:
  `famidrive-nexusmods plan <spec>`, where `<spec>` is the JSON file in
  the service's command line. `--compare <game>/vortex.deployment.json`
  compares the plan with a Vortex install.
- **Taking a game's mods out by hand:**
  `famidrive-nexusmods uninstall <spec> <app id>`.

### Wabbajack lists

Some collections are Wabbajack lists (NakeyJakey's New Vegas is one):
instead of a list of mods to install, the list holds the steps that
build a finished Mod Organizer 2 setup, every file of it. FamiDrive
treats one like any other collection in the config:

```nix
famidrive.players.alice.nexusmods.games."gog:1454587428".collections = [
  { slug = "ezlocx"; revision = 1; }   # NakeyJakey's New Vegas
];
```

- **Downloading:** every file the list names, from Nexus Mods (and a
  few from their authors' own sites, such as GitHub releases), checked
  against the list's checksums.
- **Building:** each mod's folder, exactly as the list describes: files
  out of the downloads (also out of archives inside them), files the
  list carries itself, and the few it patches. Built once, in
  `~/.local/share/famidrive/nexusmods/wabbajack/<slug>-<revision>/`.
- **Installing:** the mods go into the game's own `Data` folder in the
  order the list's Mod Organizer profile gives them (a later mod wins a
  shared file), as hard links to the built folders, so they take no
  extra space. Mod Organizer itself isn't needed: the game starts from
  Steam, Heroic or ES-DE as it always does.
- **Steps FamiDrive doesn't do yet** (building BSA archives, converting
  textures) are named in the service's log, and that list isn't
  installed.

### Fallout: New Vegas

A New Vegas list expects more than its mods in place, and FamiDrive does
that too, recorded and backed up like everything else:

- **xNVSE**, the script extender (pinned in FamiDrive, from its GitHub
  releases), into the game's folder.
- **The 4GB patch**, by its author's own Python patcher (Nexus Mods,
  "FNV 4GB Patcher", downloaded with the player's key and run only if
  it's exactly the one FamiDrive knows). It lets the game use 4 GB of
  memory and load xNVSE itself.
- **The launcher out of the way:** Steam and GOG start New Vegas's
  settings launcher; the patched game takes its place, so a launch goes
  straight into the modded game.
- **The profile's INIs** (`Fallout.ini`, `FalloutPrefs.ini`,
  `FalloutCustom.ini`, with its INI tweaks) and **plugins**
  (`plugins.txt`) into the game's Windows prefix, where the game reads
  them, and the plugins' **load order**, which New Vegas takes from the
  plugin files' dates.
- **Archive invalidation:** the empty `Fallout - Invalidation.bsa` the
  profile's INI names, as Mod Organizer makes it.

Lists for New Vegas usually need **every DLC** (Dead Money, Honest
Hearts, Old World Blues, Lonesome Road, Gun Runners' Arsenal and the
Courier's Stash): the Ultimate Edition on GOG, or the base game plus
its DLC on Steam.

### Not done yet

- **Rules for other games** (Bethesda games' `Data` folder and plugin
  order, Baldur's Gate 3, Stardew Valley's SMAPI).
- **A Settings entry** to turn a game's mods off without a rebuild.
- **Game updates:** a collection is made for one version of the game.
  Steam updating the game past it can break mods until the curator
  publishes a new revision.

## Thunderstore

Thunderstore is where r2modman and Thunderstore Mod Manager get their
mods: BepInEx plugins for Unity games such as Valheim and Risk of Rain 2.
Each player declares their own, by Steam app id, with the same
Author-Name-Version ids a dedicated server's mod list or an r2modman
profile uses, so they can match a server's or their friends' pack:

```nix
famidrive.players.alice.thunderstore.games = {
  "892970".mods = {   # Valheim
    "ValheimModding-Jotunn-2.30.2" = "sha256-…";
    "RandyKnapp-EquipmentAndQuickSlots-3.1.3" = "sha256-…";
  };
  "632360".mods = {   # Risk of Rain 2
    "tristanmcpherson-R2API-5.0.5" = "sha256-…";
  };
};
```

- **Downloads:** each package is downloaded by Nix at build time, with
  its hash (leave it `""` and the build error gives the right one). No
  account is needed.
- **Dependencies** aren't added for you: list them too, as a server's
  list does. One that's missing is logged when the mods go in.
- **Where they go:** the rebuild puts BepInEx and the mods in the
  player's own Steam copy of the game, where r2modman would, and sets
  the game's launch options that load BepInEx for that player only. A
  player without mods plays the game unmodded.
- **Only what's listed:** plugins that aren't listed are moved to
  `BepInEx/plugins-off` (not deleted), so the game matches the pack
  exactly. `onlyListed = false` keeps plugins added by hand.
- **Taking a game out** clears its launch options, so it starts
  unmodded; its files stay in the game's folder.
- **Other games:** FamiDrive knows Valheim's and Risk of Rain 2's BepInEx
  pack and launch options. For another BepInEx game, set its
  `bepinex.package`, `bepinex.hash` and `launchOptions` too. A Windows
  game under Proton loads BepInEx with
  `WINEDLLOVERRIDES="winhttp=n,b" %command%`.

Valheim's mods were once one list for the whole box
(`famidrive.valheim.mods`); that option is gone, and the build says
where its mods go now.

## Emulators

Mods for emulated games live in your RomM library, beside the game:
zips in the game's `mod` folder in RomM. Each player's session links
them into their emulators, and a mod removed from RomM is removed there
too.

- **GameCube and Wii (Dolphin): HD texture packs.** A zip of Dolphin
  textures (`tex1_…` files, usually in one folder named for the game's
  ID) goes in as `Load/Textures/<game ID>`. Dolphin is set to load custom
  textures and preload them, so they don't stutter in.
- **Switch (Eden, and Ryujinx for the games listed in
  `switch.ryujinx.games`): mods.** A zip laid out like a Switch SD card
  (`atmosphere/contents/<title ID>/…`), or like a yuzu mod (`exefs/`,
  `romfs/` at the top), goes in under the game's title ID. Mods built on
  Skyline plugins (HewDraw Remix for Smash Ultimate) need Ryujinx.

Other emulators' mods and patches aren't handled yet.
