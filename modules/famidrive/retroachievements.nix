# RetroAchievements, per player: each player's emulators signed in to
# their own account, set once in the host config instead of once per
# emulator on the TV (#14). Unlocks show as toasts (overlays.nix).
#
# Achievements never go through RomM. The emulators talk to
# RetroAchievements directly; RomM shows a player's progress beside their
# games by reading it from RetroAchievements, once their RetroAchievements
# username is linked in their RomM profile.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  has = s: cfg.systems ? ${s};

  withCheevos = lib.filterAttrs (_: p: !p.isGuest && (p.retroAchievements.username or null) != null) cfg.allPlayers;

  passwordFile = name: p:
    if p.retroAchievements.passwordFile != null then p.retroAchievements.passwordFile
    else config.sops.secrets."${name}/retroachievements".path;

  spec = name: p: pkgs.writeText "famidrive-cheevos-${name}.json" (builtins.toJSON {
    inherit (p.retroAchievements) username hardcore;
    passwordFile = toString (passwordFile name p);
    # Steam, Heroic and other launchers have no emulator.
    retroarch = lib.any (s: s.emulator != null && lib.hasPrefix "retroarch-" s.emulator) (lib.attrValues cfg.systems);
    dolphin = has "gc" || has "wii";
    pcsx2 = has "ps2";
  });
in
{
  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.retroAchievements = {
        username = mkOption {
          type = types.nullOr types.str;
          default = null;
          description = ''
            Their RetroAchievements username. Set, their RetroArch, Dolphin
            and PCSX2 are signed in at the start of each of their sessions,
            and unlocks show as toasts. Their password is a sops secret,
            `<name>/retroachievements`, unless `passwordFile` says otherwise.
          '';
        };
        passwordFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          defaultText = lib.literalMD "their sops secret, `<name>/retroachievements`";
          description = "A file with their RetroAchievements password, readable by their account.";
        };
        hardcore = mkOption {
          type = types.bool;
          default = false;
          description = ''
            Hardcore mode: unlocks count for more on RetroAchievements, and
            save states, rewind, slow motion and cheats are off.
          '';
        };
      };
    });
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.famidrive-cheevos ];

    sops.secrets = lib.mapAttrs' (name: p: lib.nameValuePair "${name}/retroachievements" { owner = p.user; })
      (lib.filterAttrs (_: p: p.retroAchievements.passwordFile == null) withCheevos);

    # Signed in before ES-DE, in the background: a slow or unreachable
    # RetroAchievements never holds up the menu. Emulators started before
    # it finishes keep the last session's token.
    famidrive.sessionSetup = lib.optionalString (withCheevos != { }) ''
      case "$(id -un)" in
      ${lib.concatStrings (lib.mapAttrsToList (name: p: ''
        ${p.user}) ${pkgs.famidrive-cheevos}/bin/famidrive-cheevos setup ${spec name p} \
             || echo "famidrive-session: RetroAchievements not signed in" >&2 & ;;
      '') withCheevos)}
      esac
    '';
  };
}
