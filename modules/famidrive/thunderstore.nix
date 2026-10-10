# Thunderstore mods (BepInEx), per player, declared in Nix: the same
# Author-Name-Version ids a dedicated server's mod list (for example
# mbround18/valheim's MODS) or an r2modman profile uses, so a player can
# match a server's or their friends' pack. Each package is fetched by Nix
# with its hash, then put in the game's folder in the player's own Steam
# library at activation (pkgs/famidrive-thunderstore), with the launch
# options that load BepInEx set for that player only (docs/MODDING.md).
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  thunderstore = ident: hash:
    let
      parts = lib.splitString "-" ident;
      n = lib.length parts;
      author = lib.concatStringsSep "-" (lib.take (n - 2) parts);
      name = lib.elemAt parts (n - 2);
      version = lib.elemAt parts (n - 1);
    in
    pkgs.fetchurl {
      name = "${ident}.zip";
      url = "https://thunderstore.io/package/download/${author}/${name}/${version}/";
      inherit hash;
    };

  # What FamiDrive knows about each game: its BepInExPack and the launch
  # options that load it. Other games set both themselves.
  known = {
    # Valheim's Linux build, through BepInExPack's own start script.
    "892970" = {
      bepinex = {
        package = "denikson-BepInExPack_Valheim-5.4.2351";
        hash = "sha256-vOYxSXl2qTl3zrCOFmcS5sMdFSRJVvifF98JKpti4p8=";
      };
      launchOptions = "./start_game_bepinex.sh %command%";
    };
    # Risk of Rain 2, a Windows game under Proton: BepInEx loads through
    # the pack's winhttp.dll, which Wine only uses when told to.
    "632360" = {
      bepinex = {
        package = "bbepis-BepInExPack-5.4.2122";
        hash = "sha256-ipjDz6g8kg0hxEfgt2BsiiarIYw1xHg5Sh+wgO+9tSc=";
      };
      launchOptions = ''WINEDLLOVERRIDES="winhttp=n,b" %command%'';
    };
  };

  game = types.submodule ({ name, ... }: {
    options = {
      mods = mkOption {
        type = types.attrsOf types.str;
        default = { };
        example = {
          "ValheimModding-Jotunn-2.30.2" = "sha256-…";
          "RandyKnapp-EquipmentAndQuickSlots-3.1.3" = "sha256-…";
        };
        description = ''
          Thunderstore packages, by Author-Name-Version, each with the hash
          of its download (leave it "" and the build error gives the right
          one). Dependencies aren't added for you: list them too, as a
          server's list does (a missing one is logged).
        '';
      };
      onlyListed = mkOption {
        type = types.bool;
        default = true;
        description = ''
          Turn off plugins that aren't listed (they're moved to
          BepInEx/plugins-off, not deleted), so the game matches a
          server's pack exactly. Off: plugins added by hand stay on.
        '';
      };
      bepinex = {
        package = mkOption {
          type = types.nullOr types.str;
          default = known.${name}.bepinex.package or null;
          defaultText = lib.literalMD "the game's, for Valheim and Risk of Rain 2";
          example = "bbepis-BepInExPack-5.4.2122";
          description = "The game's BepInExPack on Thunderstore, by Author-Name-Version.";
        };
        hash = mkOption {
          type = types.str;
          default = known.${name}.bepinex.hash or "";
          defaultText = lib.literalMD "the game's, for Valheim and Risk of Rain 2";
          description = "Hash of that package's download.";
        };
      };
      launchOptions = mkOption {
        type = types.nullOr types.str;
        default = known.${name}.launchOptions or null;
        defaultText = lib.literalMD "the game's, for Valheim and Risk of Rain 2";
        example = ''WINEDLLOVERRIDES="winhttp=n,b" %command%'';
        description = ''
          The game's launch options in Steam that load BepInEx, for this
          player only: a Windows game under Proton needs the winhttp
          override above. Cleared again when the game is taken out.
        '';
      };
    };
  });

  players = lib.filterAttrs (_: p: !p.isGuest && (p.thunderstore.games or { }) != { }) cfg.allPlayers;

  spec = p: {
    games = lib.mapAttrs (_: g: {
      bepinex = {
        inherit (g.bepinex) package;
        zip = toString (thunderstore g.bepinex.package g.bepinex.hash);
      };
      mods = lib.mapAttrs (ident: hash: toString (thunderstore ident hash)) g.mods;
      inherit (g) onlyListed;
    }) p.thunderstore.games;
  };
in
{
  imports = [
    (lib.mkRemovedOptionModule [ "famidrive" "valheim" ] ''
      Valheim's mods are now each player's own:
      famidrive.players.<name>.thunderstore.games."892970".mods, with the
      same Author-Name-Version ids and hashes (docs/MODDING.md).
    '')
  ];

  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.thunderstore.games = mkOption {
        type = types.attrsOf game;
        default = { };
        example = lib.literalExpression ''
          {
            "892970".mods = {   # Valheim
              "ValheimModding-Jotunn-2.30.2" = "sha256-…";
            };
            "632360".mods = {   # Risk of Rain 2
              "tristanmcpherson-R2API-5.0.5" = "sha256-…";
            };
          }
        '';
        description = ''
          Thunderstore (BepInEx) mods for their Steam games, by app id.
          Valheim (892970) and Risk of Rain 2 (632360) need only `mods`;
          another game also needs its `bepinex` pack and `launchOptions`.
          Put in their own Steam library's copy of the game at each
          rebuild, with BepInEx turned on for them only. A game taken out
          keeps its files but starts unmodded (its launch options are
          cleared). See docs/MODDING.md.
        '';
      };
    });
  };

  config = lib.mkIf (cfg.enable && hasLane "steam" && players != { }) {
    assertions = lib.concatLists (lib.mapAttrsToList (name: p: lib.mapAttrsToList (appid: g: {
      assertion = g.bepinex.package != null && g.launchOptions != null;
      message = "famidrive.players.${name}.thunderstore.games.\"${appid}\": FamiDrive doesn't know this game; set its bepinex.package, bepinex.hash and launchOptions.";
    }) p.thunderstore.games) players);

    famidrive.steam.playerLaunchOptions = lib.mapAttrs' (_: p: lib.nameValuePair p.user
      (lib.mapAttrs (_: g: g.launchOptions) p.thunderstore.games)) players;

    famidrive.playerHome = { lib, famidrivePlayer, ... }:
      lib.mkIf (players ? ${famidrivePlayer.name}) {
        home.activation.famidriveThunderstore = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          ${pkgs.famidrive-thunderstore}/bin/famidrive-thunderstore ${lib.escapeShellArg (builtins.toJSON (spec famidrivePlayer))} || true
        '';
      };
  };
}
