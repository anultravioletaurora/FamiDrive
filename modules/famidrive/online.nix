# Online play, opt-in per box (roms.md "Online play").
# Flipping famidrive.online.enable fills in every emulator's netplay settings,
# pointed at your backends in endpoints.nix. Off by default,
# so a box only talks to these servers once it opts in.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkOption types;
  cfg = config.famidrive;
  ep = cfg.endpoints;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  has = s: cfg.systems ? ${s};

  # PS3 online (docs/Online-Play/PS3.md): on with online.enable, or alone.
  ps3Online = cfg.enable && has "ps3" && cfg.online.ps3.enable;
  rpcnPlayers = lib.filterAttrs (_: p: !p.isGuest) cfg.allPlayers;

  # RPCS3 keeps an RPCN password as this, never as typed: PBKDF2 over
  # SHA3-256, 200000 rounds, its fixed salt, upper-case hex
  # (derive_password, rpcs3qt/rpcn_settings_dialog.cpp, read 2026-10-10).
  derive = pkgs.writers.writePython3 "famidrive-rpcn-password" { } ''
    import hashlib
    import sys
    salt = b"No matter where you go, everybody's connected."
    password = sys.stdin.read().rstrip("\n").encode()
    print(hashlib.pbkdf2_hmac("sha3_256", password, salt, 200000).hex().upper())
  '';
in
{
  # Each player shows up in lobbies and rooms by their RomM username
  # (players.<name>.owner); the guest as "Guest".
  imports = [
    (lib.mkRemovedOptionModule [ "famidrive" "online" "nickname" ] "Each player's netplay name is their RomM username, famidrive.players.<name>.owner.")
  ];

  options.famidrive.online = {
    enable = mkEnableOption "online play for this box's emulators";
    ps3.enable = mkOption {
      type = types.bool;
      default = cfg.online.enable;
      defaultText = lib.literalExpression "config.famidrive.online.enable";
      description = ''
        PS3 online through RPCN, RPCS3's stand-in for the PlayStation
        Network, on its own: each player signed in to their RPCN account
        (their sops secret `<name>/rpcn`) on the server in
        `endpoints.rpcn`. See docs/Online-Play/PS3.md.
      '';
    };
  };

  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule ({ config, ... }: {
      options.rpcn.username = mkOption {
        type = types.str;
        default = config.owner;
        defaultText = lib.literalExpression "owner";
        example = "alice-ps3";
        description = ''
          Their RPCN username: what other players see in lobbies, 3 to 16
          letters, digits, - or _. Their RomM username unless it's set;
          an account made in RPCS3 under another name goes here.
        '';
      };
    }));
  };

  config = lib.mkMerge [ (lib.mkIf ps3Online {
    # An RPCN account per player (the guest has none), made once by the
    # player (docs/Online-Play/PS3.md); its password in their secrets.
    sops.secrets = lib.mapAttrs' (name: p: lib.nameValuePair "${name}/rpcn" { owner = p.user; }) rpcnPlayers;

    # RPCN signals peer-to-peer play to this port (RPCS3's default, 3658);
    # UPnP opens it on the router too, where the router allows that.
    networking.firewall.allowedUDPPorts = [ 3658 ];

    famidrive.playerHome = { lib, famidrivePlayer, ... }: lib.mkIf (!famidrivePlayer.isGuest) {
      home.activation.famidriveRpcn = lib.hm.dag.entryAfter [ "famidriveEmulators" ] ''
        ${seedLib.lockKeys {
          format = "yaml";
          target = "$HOME/.config/rpcs3/config.yml";
          # Key names and values read from RPCS3's source (system_config.h,
          # system_config_types.cpp) 2026-10-10.
          keys = {
            ".Net[\"Internet enabled\"]" = "Connected";
            ".Net[\"PSN status\"]" = "RPCN";
            ".Net[\"UPNP Enabled\"]" = true;
          };
        }}
        ${seedLib.lockKeys {
          format = "yaml";
          target = "$HOME/.config/rpcs3/rpcn.yml";
          # rpcn_config.h, read 2026-10-10.
          keys = {
            ".Version" = 2;
            ".Host" = ep.rpcn;
            ".NPID" = cfg.players.${famidrivePlayer.name}.rpcn.username;
          };
        }}
        # The password from sops at activation, never in the Nix store; RPCS3
        # takes it only in its derived form.
        rpcn_secret=${config.sops.secrets."${famidrivePlayer.name}/rpcn".path}
        if [ -r "$rpcn_secret" ]; then
          RPCN_PASSWORD=$(${derive} < "$rpcn_secret") \
            ${pkgs.yq-go}/bin/yq -i '.Password = strenv(RPCN_PASSWORD)' "$HOME/.config/rpcs3/rpcn.yml"
        fi
      '';
    };
  }) (lib.mkIf (cfg.enable && cfg.online.enable) {
    # Inbound for peer-to-peer play when this box hosts. Dolphin's
    # traversal server usually makes this unnecessary.
    networking.firewall.allowedUDPPorts = lib.optionals (has "gc" || has "wii") [ 2626 ];

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
  })];
}
