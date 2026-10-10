# One place for every backend address. Set them once (in a host file, or a
# shared module of your own) and every feature that needs one reads it here.
#
# Deliberately no defaults: these are your servers, not this repo's. An
# option is only read when the feature using it is on, so a box with RomM,
# Jellyfin and online play all off evaluates without any of them set, and
# turning a feature on without its address fails loudly at build time
# instead of quietly pointing somewhere wrong.
{ lib, ... }:

let
  inherit (lib) mkOption types;
in
{
  options.famidrive.endpoints = {
    romm = mkOption {
      type = types.str;
      example = "https://romm.example.com";
      description = "RomM base URL, over HTTPS (behind a reverse proxy) so boxes off the LAN can reach it.";
    };

    jellyfin = mkOption {
      type = types.str;
      example = "https://jellyfin.example.com";
      description = "Jellyfin's public URL, the same from every box on or off the LAN.";
    };

    # Online-play backends (roms.md "Online play"), one service each.
    #
    # Exposure follows option A: HTTP/relay services go through the reverse
    # proxy, while traversal/signaling services get direct port-forwards
    # because they need real client source addresses.
    # The one default here: RPCN is RPCS3's own service, not a server of
    # yours, and its public server is where the other players are. A
    # self-hosted RPCN only has your own boxes on it.
    rpcn = mkOption {
      type = types.str;
      default = "np.rpcs3.net";
      example = "rpcn.example.com:31313";             # self-hosted, port-forwarded (P2P signaling)
      description = "RPCN server (PS3 online, RPCS3), host and optional port: RPCS3's public one unless set. A self-hosted one needs a port forward, since it signals peer-to-peer connections.";
    };
    edenRoomHost = mkOption {
      type = types.str;
      example = "eden.example.com";
      # Revised 2026-10-05: replaces Ryubing's LDN server.
      description = "Eden room server (Switch online), `eden-room`, which ships with nixpkgs' eden.";
    };
    edenRoomPort = mkOption {
      type = types.port;
      default = 24872;                                 # Eden's default room port; exposure (proxy vs. forward) unverified
      description = "The Eden room server's port.";
    };
    xeniaWebServices = mkOption {
      type = types.str;
      example = "https://xenia.example.com";           # reverse proxy (plain REST API)
      description = "Xenia web services (Xbox 360 online), a plain REST API behind the reverse proxy.";
    };
    retroarchTunnel = mkOption {
      type = types.str;
      example = "netplay.example.com:55435";           # reverse-proxy TCP/UDP entrypoint (pure relay)
      description = "RetroArch netplay relay (its MITM tunnel server), host and port.";
    };
    dolphinTraversal = mkOption {
      type = types.str;
      example = "traversal.example.com";               # port-forwarded (NAT traversal)
      description = "Dolphin's traversal server (GameCube and Wii netplay). Needs a port forward: it sees players' real addresses.";
    };
    dolphinTraversalPort = mkOption {
      type = types.port;
      default = 6262;
      description = "The Dolphin traversal server's port.";
    };
  };
}
