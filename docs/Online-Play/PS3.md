# PS3 online

PS3 games play online through **RPCN**, RPCS3's own stand-in for the
PlayStation Network. RPCS3 can't sign in to PSN, and a PSN account isn't
used anywhere: each player has an RPCN account instead, free, made once.
Other RPCS3 players are on RPCN's public server (`np.rpcs3.net`, run by
the RPCS3 project), so that's where FamiDrive points by default.

FamiDrive is for games you own. It provides no games, keys or firmware.

## How it works

With `famidrive.online.ps3.enable` on, each player's RPCS3 (not the
guest's) is set up at every rebuild and boot:

- **Signed in to RPCN:** `~/.config/rpcs3/rpcn.yml` gets the server
  (`famidrive.endpoints.rpcn`), their RPCN username
  (`players.<name>.rpcn.username`, their RomM username unless set) and
  their password. The password comes from their sops secret
  `<name>/rpcn` when the box starts, never through the Nix store, and is
  written the way RPCS3 keeps it: RPCS3 never stores the password you
  type, only a key derived from it (PBKDF2 over SHA3-256, as its own
  settings window does).
- **Online in RPCS3's settings:** `config.yml`'s `Net` section says
  `Internet enabled: Connected` and `PSN status: RPCN`, with UPnP on.
- **Peer-to-peer:** many PS3 games connect players to each other
  directly once RPCN has matched them. FamiDrive opens UDP 3658 (RPCS3's
  default) in the box's firewall, and UPnP asks the router to forward it.
  On a router without UPnP, forward UDP 3658 to the box by hand.
- **The guest** has no RPCN account and stays offline.

`famidrive.online.enable` turns this on too, along with every other
system's online play. `online.ps3.enable` alone turns on only PS3's,
which needs no servers of your own.

## Setting it up

1. **Make an RPCN account,** once per player, in RPCS3 on any computer
   (a desktop, a laptop, a Steam Deck; RPCS3's settings window isn't
   reachable on the TV yet): open RPCS3's RPCN settings (Configuration →
   RPCN) and create an account. Pick a username (3 to 16 letters, digits,
   `-` or `_`), a password, and an email address. RPCN emails a token
   that validates the account: enter it when RPCS3 asks. After that, the
   account works on any box with just the username and password.
2. **Put the password in the box's secrets,** under the player:
   ```yaml
   alice:
     romm: rmm_…
     rpcn: the-rpcn-password
   ```
3. **Turn it on,** and add PS3 to the platforms the box pulls from RomM:
   ```nix
   famidrive.online.ps3.enable = true;
   famidrive.romm.platforms = [ /* … */ "ps3" ];
   # Only if the RPCN username isn't their RomM username:
   famidrive.players.alice.rpcn.username = "alice-ps3";
   ```
4. **Rebuild,** then start a PS3 game. RPCS3 signs in to RPCN as the game
   starts; the game's own online menu does the rest.

A self-hosted RPCN server (github.com/RipleyTom/rpcn) works the same way
with `famidrive.endpoints.rpcn = "rpcn.example.com:31313"`, but only
your own boxes are on it.

## Games: disc images and their keys

RPCS3 plays a disc image (`.iso`) straight from RomM, like any other
system. A Redump image of a PS3 disc is **encrypted**, and needs that
disc's key to play: a `.dkey` file (the key as 32 hex characters) or a
`.key` file (16 bytes), made from your own disc when you dumped it.

- **Upload the key to RomM as PS3 firmware** (the PS3 platform's
  firmware, not the game). romm-agent puts every `.dkey` and `.key` it
  finds there into RPCS3's key folder (`~/.config/rpcs3/data/redump/`),
  and RPCS3 (since April 2026) tries each one on an encrypted image until
  one fits. The game itself stays one `.iso` in RomM, so ES-DE lists it
  like any other.
- **A decrypted image** (from a PS3, or decrypted with PS3Dec) needs no
  key.

## Firmware

RPCS3 needs the PS3's system software (`PS3UPDAT.PUP`, from Sony's
website) installed once. RPCS3 only installs it through its own window,
which FamiDrive can't drive on the TV yet
([#48](https://github.com/anultravioletaurora/FamiDrive/issues/48)): install
it once from RPCS3 itself (File → Install Firmware), on the box with a
keyboard and mouse.

## Game updates

Many PS3 games only go online with their latest update installed, as on
a real PS3. An update is a `.pkg` file that RPCS3 installs from its own
window (File → Install Packages), which, like the firmware, needs a
keyboard and mouse on the box for now.

## First test: Call of Duty: World at War

On the first box, from a disc image of a copy we own, with its key.
Record here what happened:

- [ ] The image plays, with the key from RomM's PS3 firmware.
- [ ] RPCS3 signs in to RPCN as the game starts (RPCS3's log:
      `rpcn` lines; no RPCN pop-up, since FamiDrive turns RPCS3's own
      pop-ups off).
- [ ] The game's online menu: does it ask for an update first?
- [ ] Finding a match, or hosting one, with another RPCS3 player.
- [ ] Voice chat and the friends list, if the game uses them.
