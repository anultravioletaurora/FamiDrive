# Nexus Mods, per player: the collections (modpacks) they want for their
# Steam games, downloaded in the background with their own API key, and a
# plan of where every file goes. Installing from the plan comes next; for
# now nothing in a game's folder is touched.
#
# Downloading straight from a program needs a premium Nexus Mods account;
# a free one has to click "Slow download" on the website for each file,
# and FamiDrive doesn't work around that.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;

  withMods = lib.filterAttrs (_: p: !p.isGuest && (p.nexusmods.games or { }) != { }) cfg.allPlayers;

  keyFile = name: p:
    if p.nexusmods.apiKeyFile != null then p.nexusmods.apiKeyFile
    else config.sops.secrets."${name}/nexusmods".path;

  spec = name: p: pkgs.writeText "famidrive-nexusmods-${name}.json" (builtins.toJSON {
    apiKeyFile = toString (keyFile name p);
    cache = "~/.cache/famidrive/nexusmods";
    games = lib.mapAttrs (_: g: { inherit (g) collection choices; }) p.nexusmods.games;
  });

  game = types.submodule {
    options = {
      collection = mkOption {
        type = types.submodule {
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
          };
        };
        description = "The collection (modpack) for this game.";
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
            { "1091500".collection = { slug = "iszwwe"; revision = 481; }; }   # Cyberpunk 2077
          '';
          description = ''
            Collections to download for their Steam games, by Steam app
            id. Downloaded in the background into their cache
            (~/.cache/famidrive/nexusmods), each file checked against the
            collection's checksum, with a plan of where each file goes in
            the game's folder. Nothing is installed in the game yet.
          '';
        };
      };
    });
  };

  config = lib.mkIf (cfg.enable && withMods != { }) {
    environment.systemPackages = [ pkgs.famidrive-nexusmods ];

    sops.secrets = lib.mapAttrs' (name: p: lib.nameValuePair "${name}/nexusmods" { owner = p.user; })
      (lib.filterAttrs (_: p: p.nexusmods.apiKeyFile == null) withMods);

    systemd.services = lib.mapAttrs' (name: p: lib.nameValuePair "famidrive-nexusmods-${name}" {
      description = "Download ${p.displayName}'s Nexus Mods collections";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = {
        Type = "oneshot";
        User = p.user;
        Nice = 10;
        IOSchedulingClass = "idle";   # a big collection shouldn't stutter a game
        ExecStart = [
          "${pkgs.famidrive-nexusmods}/bin/famidrive-nexusmods fetch ${spec name p}"
          "${pkgs.famidrive-nexusmods}/bin/famidrive-nexusmods plan ${spec name p}"
        ];
      };
    }) withMods;
    systemd.timers = lib.mapAttrs' (name: _: lib.nameValuePair "famidrive-nexusmods-${name}" {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5min";
        OnUnitActiveSec = "1d";
      };
    }) withMods;
  };
}
