# Nexus Mods, per player: the collections (modpacks) they want for their
# Steam games, downloaded in the background with their own API key and
# installed in the game's folder. A rebuild that changes a player's mods
# starts their service again: a run still downloading is stopped (so its
# downloads are cancelled), and the new one installs what's listed now and
# takes out what isn't (docs/MODDING.md).
#
# Downloading straight from a program needs a premium Nexus Mods account;
# a free one has to click "Slow download" on the website for each file,
# and FamiDrive doesn't work around that.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;

  # Every player has the service, mods or not: one whose mods were all
  # taken out of the config needs it to take them out of the game.
  players = lib.filterAttrs (_: p: !p.isGuest) cfg.allPlayers;
  withMods = lib.filterAttrs (_: p: (p.nexusmods.games or { }) != { }) players;

  keyFile = name: p:
    if p.nexusmods.apiKeyFile != null then p.nexusmods.apiKeyFile
    else config.sops.secrets."${name}/nexusmods".path;

  # What some games need beyond their mods, pinned here.
  extras = {
    # xNVSE, New Vegas's script extender, which Wabbajack lists for it
    # expect in the game's folder.
    xnvse = pkgs.fetchurl {
      url = "https://github.com/xNVSE/NVSE/releases/download/6.4.9/nvse_6_4_9.7z";
      hash = "sha256-gfsGOPh7LIIicON88soRjTniQl8TAo+Rc7Fyxf2y64g=";
    };
  };

  spec = name: p: pkgs.writeText "famidrive-nexusmods-${name}.json" (builtins.toJSON {
    apiKeyFile = if withMods ? ${name} then toString (keyFile name p) else null;
    cache = "~/.cache/famidrive/nexusmods";
    extras = lib.mapAttrs (_: toString) extras;
    games = lib.mapAttrs (_: g: {
      collections = lib.optional (g.collection != null) g.collection ++ g.collections;
      inherit (g) choices;
    }) (p.nexusmods.games or { });
  });

  collectionType = types.submodule {
    options = {
      slug = mkOption {
        type = types.str;
        example = "iszwwe";
        description = "The collection's id, the last part of its address on nexusmods.com.";
      };
      revision = mkOption {
        type = types.ints.positive;
        example = 481;
        description = ''
          Which revision of it. Pinned, like a flake input: a curator's
          new revision is only used once it's set here, so a working
          setup doesn't change under a player.
        '';
      };
      skip = mkOption {
        type = types.listOf types.ints.positive;
        default = [ ];
        example = [ 512 711 ];
        description = ''
          Mods of the collection to leave out, by their Nexus Mods mod id
          (the number in the mod's address, nexusmods.com/<game>/mods/<id>).
          They're neither downloaded nor installed; the rest of the
          collection goes in as its curator made it.
        '';
      };
    };
  };

  game = types.submodule {
    options = {
      collections = mkOption {
        type = types.listOf collectionType;
        default = [ ];
        example = lib.literalExpression ''
          [
            { slug = "rcuccp"; revision = 189; }   # NCR Core
            { slug = "srpv39"; revision = 129; }   # NCR - Extras
            { slug = "g0tcm4"; revision = 42; }    # High-Res Graphics Pack - MAXIMUM
          ]
        '';
        description = ''
          The collections (modpacks) for this game, installed in this
          order: where two have the same file, the later one's wins.
        '';
      };
      collection = mkOption {
        type = types.nullOr collectionType;
        default = null;
        description = "One collection for this game, put before `collections`.";
      };
      choices = mkOption {
        type = types.attrsOf (types.listOf types.str);
        default = { };
        example = { "WTNC Config" = [ "Cyberpunk THING" ]; };
        description = ''
          Options to pick in mods with an installer (FOMOD) that the
          collection leaves to the player, by mod name: the names of the
          options, as the installer shows them. Unset, each installer's
          own default (its first option, when one must be picked).
        '';
      };
    };
  };
in
{
  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.nexusmods = {
        apiKeyFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          defaultText = lib.literalMD "their sops secret, `<name>/nexusmods`";
          description = ''
            Their Nexus Mods personal API key (nexusmods.com, Site
            preferences, API Keys), for an account with premium.
          '';
        };
        games = mkOption {
          type = types.attrsOf game;
          default = { };
          example = lib.literalExpression ''
            {
              "1091500".collections = [ { slug = "rcuccp"; revision = 189; } ];      # Cyberpunk 2077 on Steam
              "gog:1454587428".collections = [ { slug = "ezlocx"; revision = 1; } ];  # New Vegas on GOG, a Wabbajack list
            }
          '';
          description = ''
            Nexus Mods collections for their games: a Steam game by its app
            id, a GOG game (installed through Heroic) as `gog:<GOG id>`. A
            collection can be a Wabbajack list (New Vegas's NakeyJakey's,
            for one), built and installed the same way.
            Downloaded in the background into their cache
            (~/.cache/famidrive/nexusmods), each file checked against the
            collection's checksum, then installed in the game's folder,
            with every file recorded and anything it replaced backed up.
            A rebuild that changes this starts over: a game taken out gets
            its mods removed, and one with other collections, revisions or
            choices gets the old install taken out and the new one put
            in. See docs/MODDING.md.
          '';
        };
      };
    });
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = lib.mkIf (withMods != { }) [ pkgs.famidrive-nexusmods ];

    sops.secrets = lib.mapAttrs' (name: p: lib.nameValuePair "${name}/nexusmods" { owner = p.user; })
      (lib.filterAttrs (_: p: p.nexusmods.apiKeyFile == null) withMods);

    # Started at boot, and again by any rebuild that changes the player's
    # mods (restartTriggers): systemd stops a run still going first, which
    # cancels its downloads. Type exec, so a rebuild doesn't wait for a
    # 26 GB download to finish.
    systemd.services = lib.mapAttrs' (name: p: lib.nameValuePair "famidrive-nexusmods-${name}" {
      description = "${p.displayName}'s Nexus Mods";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];
      restartTriggers = [ (spec name p) ];
      serviceConfig = {
        Type = "exec";
        User = p.user;
        Nice = 10;
        IOSchedulingClass = "idle";   # a big collection shouldn't stutter a game
        ExecStart = "${pkgs.famidrive-nexusmods}/bin/famidrive-nexusmods sync ${spec name p}";
      };
    }) players;
    # Again daily, for downloads that failed (a server down, a file pulled).
    systemd.timers = lib.mapAttrs' (name: _: lib.nameValuePair "famidrive-nexusmods-${name}" {
      wantedBy = [ "timers.target" ];
      timerConfig.OnUnitInactiveSec = "1d";
    }) withMods;
  };
}
