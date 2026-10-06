# Valheim's BepInEx mods declared in Nix, from Thunderstore (pc-games.md).
# The same Author-Name-Version ids a dedicated server's mod list uses (for
# example mbround18/valheim's MODS), so a box can match a server's pack.
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

  spec = {
    bepinex = {
      inherit (cfg.valheim.bepinex) version;
      zip = toString (thunderstore "denikson-BepInExPack_Valheim-${cfg.valheim.bepinex.version}" cfg.valheim.bepinex.hash);
    };
    mods = lib.mapAttrs (ident: hash: toString (thunderstore ident hash)) cfg.valheim.mods;
    inherit (cfg.valheim) onlyListed;
  };
in
{
  options.famidrive.valheim = {
    mods = mkOption {
      type = types.attrsOf types.str;
      default = { };
      example = {
        "ValheimModding-Jotunn-2.30.2" = "sha256-…";
        "RandyKnapp-EquipmentAndQuickSlots-3.1.3" = "sha256-…";
      };
      description = ''
        Thunderstore packages to play Valheim with, by Author-Name-Version,
        each with the hash of its download (leave it "" and the build
        error gives the right one). Dependencies aren't added for you: list
        them too, as a server's list does. Setting any turns on BepInEx and
        Valheim's launch option for it.
      '';
    };

    onlyListed = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Turn off plugins that aren't listed (they're moved to
        BepInEx/plugins-off, not deleted), so the game matches a server's
        pack exactly. Off: plugins added by hand stay on.
      '';
    };

    bepinex = {
      version = mkOption {
        type = types.str;
        default = "5.4.2351";
        description = "denikson's BepInExPack_Valheim version.";
      };
      hash = mkOption {
        type = types.str;
        default = "sha256-vOYxSXl2qTl3zrCOFmcS5sMdFSRJVvifF98JKpti4p8=";
        description = "Hash of that version's download.";
      };
    };
  };

  config = lib.mkIf (cfg.enable && hasLane "steam" && cfg.valheim.mods != { }) {
    # BepInExPack's own launcher for the Linux build.
    famidrive.steam.launchOptions."892970" = lib.mkDefault "./start_game_bepinex.sh %command%";

    home-manager.users.${cfg.user} = { lib, ... }: {
      home.activation.famidriveValheim = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${pkgs.famidrive-valheim}/bin/famidrive-valheim ${lib.escapeShellArg (builtins.toJSON spec)} || true
      '';
    };
  };
}
