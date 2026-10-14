# What FamiDrive knows about Steam games' launch options, by app id, so a
# host doesn't have to find them out again. Each game:
#   name     as Steam and ES-DE show it; a host's own launch options under
#            this name replace FamiDrive's, the same as under the app id
#   args     after %command%, for every player (skipping a launcher that
#            needs a mouse click)
#   modded   before %command%, for players who mod it (Nexus Mods
#            collections, nexusmods.nix, or Thunderstore, thunderstore.nix):
#            what loads the mods, such as a DLL override under Proton or
#            the mod loader's own start script
#   offline  true for a single-player game with nothing online to drop:
#            the Guide menu freezes it (an online one keeps running)
# Thunderstore's BepInExPacks stay in thunderstore.nix.
{ lib }:

let
  games = {
    "1091500" = {
      name = "Cyberpunk 2077";
      # REDlauncher's window draws nothing under gamescope (a transparent
      # background, all black on the TV) and waits for Play to be clicked.
      # Found on the first box 2026-10-12: the game hadn't started since
      # 2026-10-10, stuck there; --launcher-skip starts the game itself.
      args = "--launcher-skip";
      # Cyber Engine Tweaks and RED4ext load through these (MODDING.md).
      modded = ''WINEDLLOVERRIDES="winmm,version=n,b"'';
      offline = true;
    };
    "1172380" = {
      name = "STAR WARS Jedi: Fallen Order™";
      # Single-player only. Found on the first box 2026-10-14: the Guide
      # menu let it run on underneath ("The game keeps running").
      offline = true;
    };
    "892970" = {
      name = "Valheim";
      # Its Linux build, through BepInExPack's own start script.
      modded = "./start_game_bepinex.sh";
    };
    "632360" = {
      name = "Risk of Rain 2";
      # A Windows game under Proton: BepInEx loads through the pack's
      # winhttp.dll, which Wine only uses when told to.
      modded = ''WINEDLLOVERRIDES="winhttp=n,b"'';
    };
  };

  build = env: args: lib.concatStringsSep " "
    (lib.filter (s: s != "") [ env "%command%" args ]);
in
{
  inherit games;

  # Launch options for every player: games that need some unmodded.
  plain = lib.mapAttrs (_: g: build "" g.args)
    (lib.filterAttrs (_: g: (g.args or "") != "") games);

  # A game's launch options when a player mods it, or null when FamiDrive
  # knows nothing to add for mods.
  modded = appid:
    let g = games.${appid} or { }; in
    if (g.modded or "") == "" then null else build g.modded (g.args or "");

  # Games with nothing online, by app id: the Guide menu freezes them.
  offline = lib.attrNames (lib.filterAttrs (_: g: g.offline or false) games);

  # Whether a host's launch options (by app id or name) already cover it.
  setIn = attrs: appid:
    attrs ? ${appid} || (games ? ${appid} && attrs ? ${games.${appid}.name});
}
