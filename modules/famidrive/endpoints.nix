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
    rpcn = mkOption {
      type = types.str;
      example = "rpcn.example.com:31313";             # port-forwarded (P2P signaling)
    };
    edenRoomHost = mkOption {
      type = types.str;
      example = "eden.example.com";
      description = "Eden room server (`eden-room`, ships in nixpkgs' eden). Revised 2026-10-05: replaces Ryubing's LDN server.";
    };
    edenRoomPort = mkOption {
      type = types.port;
      default = 24872;                                 # Eden's default room port; exposure (proxy vs. forward) unverified
    };
    xeniaWebServices = mkOption {
      type = types.str;
      example = "https://xenia.example.com";           # reverse proxy (plain REST API)
    };
    retroarchTunnel = mkOption {
      type = types.str;
      example = "netplay.example.com:55435";           # reverse-proxy TCP/UDP entrypoint (pure relay)
    };
    dolphinTraversal = mkOption {
      type = types.str;
      example = "traversal.example.com";               # port-forwarded (NAT traversal)
    };
    dolphinTraversalPort = mkOption {
      type = types.port;
      default = 6262;
    };
  };
}
