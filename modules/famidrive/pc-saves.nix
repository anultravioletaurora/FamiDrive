# PC/GOG saves: the one save path that doesn't go through RomM, because
# RomM can't model PC saves yet (pc-games.md open questions, "PC game save sync").
# Console saves never come through here; they use RomM's sync API only.
#
# Scoped to the box owner like everything else: folder IDs are prefixed with
# the owner, so two owners' boxes can never pair the same folder.
{ config, lib, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  pcLanes = lib.any (l: lib.elem l cfg.lanes) [ "steam" "gog" ];
in
{
  options.famidrive.pcSaves = {
    folders = mkOption {
      type = types.attrsOf types.str;
      default = { };
      example = { cyberpunk = "~/Games/gog/Cyberpunk 2077/saves"; };
      description = ''
        Per-game PC save dirs to sync, name -> path. No auto-discovery yet:
        PC games keep saves wherever they want (Proton prefix, Documents/, ...),
        so this is hand-listed for now.
      '';
    };
    peers = mkOption {
      type = types.attrsOf types.str;
      default = { };
      description = "Syncthing device IDs of the owner's other devices (server-side copy included).";
    };
  };

  config = lib.mkIf (cfg.enable && pcLanes && cfg.pcSaves.folders != { }) {
    services.syncthing = {
      enable = true;
      user = cfg.user;
      dataDir = "/home/${cfg.user}";
      overrideDevices = true;
      overrideFolders = true;
      settings = {
        devices = lib.mapAttrs (_: id: { inherit id; }) cfg.pcSaves.peers;
        folders = lib.mapAttrs' (name: path: lib.nameValuePair "${cfg.owner}-pc-${name}" {
          inherit path;
          devices = lib.attrNames cfg.pcSaves.peers;
          versioning = { type = "staggered"; params.maxAge = "2592000"; };   # 30 days
        }) cfg.pcSaves.folders;
      };
    };
  };
}
