# Online play, opt-in per box (roms.md "Online play").
# Flipping famidrive.online.enable fills in every emulator's netplay settings,
# pointed at your backends in endpoints.nix. Off by default,
# so a box only talks to these servers once it opts in.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption;
  cfg = config.famidrive;
  ep = cfg.endpoints;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  has = s: cfg.systems ? ${s};
in
{
  # Each player shows up in lobbies and rooms by their RomM username
  # (players.<name>.owner); the guest as "Guest".
  imports = [
    (lib.mkRemovedOptionModule [ "famidrive" "online" "nickname" ] "Each player's netplay name is their RomM username, famidrive.players.<name>.owner.")
  ];

  options.famidrive.online = {
    enable = mkEnableOption "online play for this box's emulators";
  };

  config = lib.mkIf (cfg.enable && cfg.online.enable) {
    # An RPCN account per player (the guest has none). Created by script
    # against the self-hosted RPCN (email validation off), not by hand.
    # Open question in roms.md.
    sops.secrets = lib.mkIf (has "ps3") (lib.mapAttrs' (name: p:
      lib.nameValuePair "rpcn-password-${name}" { owner = p.user; }
    ) (lib.filterAttrs (_: p: !p.isGuest) cfg.allPlayers));

    # Inbound for peer-to-peer play when this box hosts. Ports to verify
    # per emulator. Dolphin's traversal server usually makes this
    # unnecessary, RPCS3 P2P generally needs it.
    networking.firewall.allowedUDPPorts =
      lib.optionals (has "ps3") [ 3658 ]
      ++ lib.optionals (has "gc" || has "wii") [ 2626 ];

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveOnline = lib.hm.dag.entryAfter [ "famidriveEmulators" ] (lib.concatStrings [
        (lib.optionalString (has "gc" || has "wii") (seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/dolphin-emu/Dolphin.ini";
          keys.NetPlay = {
            TraversalChoice = "traversal";
            TraversalServer = ep.dolphinTraversal;
            TraversalPort = ep.dolphinTraversalPort;
            Nickname = famidrivePlayer.nickname;
          };
        }))

        (lib.optionalString (has "psx") (seedLib.lockKeys {
          format = "keyValue";
          target = "$HOME/.config/retroarch/retroarch.cfg";
          keys = {
            netplay_nickname = famidrivePlayer.nickname;
            netplay_use_mitm_server = "true";
            netplay_mitm_server = "custom";
            netplay_custom_mitm_server = ep.retroarchTunnel;
            netplay_public_announce = "false";
          };
        }))

        (lib.optionalString (has "ps3") ''
          ${seedLib.lockKeys {
            format = "yaml";
            target = "$HOME/.config/rpcs3/rpcn.yml";
            keys = {
              ".Host" = ep.rpcn;          # TODO: verify rpcn.yml key names
              ".NPID" = famidrivePlayer.nickname;
            };
          }}
          ${lib.optionalString (!famidrivePlayer.isGuest) ''
            # Password comes from sops at activation time, never from the Nix store.
            ${pkgs.yq-go}/bin/yq -i ".Password = \"$(cat ${config.sops.secrets."rpcn-password-${famidrivePlayer.name}".path})\"" "$HOME/.config/rpcs3/rpcn.yml"
          ''}
        '')

        # Revised 2026-10-05: Switch is Eden, which tunnels local wireless
        # through "rooms" (eden-room). This pre-fills Direct Connect; joining is
        # still one menu action in Eden. Qt settings need the matching
        # `\default=false` or Eden ignores the value. Keys seen in a real
        # Eden 0.2.1 qt-config.ini, under [UI].
        (lib.optionalString (has "switch") (seedLib.lockKeys {
          format = "ini";
          target = "$HOME/.config/eden/qt-config.ini";
          keys.UI = {
            "Multiplayer\\ip" = ep.edenRoomHost;
            "Multiplayer\\ip\\default" = "false";
            "Multiplayer\\port" = ep.edenRoomPort;
            "Multiplayer\\port\\default" = "false";
            "Multiplayer\\nickname" = famidrivePlayer.nickname;
            "Multiplayer\\nickname\\default" = "false";
          };
        }))

        # Xenia netplay: API address in the Netplay fork's config. TODO: format/keys,
        # and depends on the Xenia fork decision.
      ]);
    };
  };
}
