# Voice chat with friends from the couch (#168). Discord by default,
# official: an account only ever used that way stays on Discord's own
# terms, so this keeps working if they ever crack down on client mods.
# `client = "vesktop"` switches a player to Vencord's client instead,
# which the future overlay and controller mute/deafen (#168) will need a
# plugin for. Either way it runs the whole session for players who turn
# it on, hidden until they go to Settings' "Discord Voice Chat"
# (settings.nix) to sign in, pick a channel, or check who's there;
# closing that puts ES-DE back without ending the call, the same way Big
# Picture does for Steam.
#
# The Vencord plugin #168 describes (voice state out to a socket,
# mute/deafen back in) and the overlay that would read it aren't built
# yet; signing in, joining and muting all happen in the client's own
# window for now. Opt-in per player, not box-wide, either way.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;

  # Safe for the guest too, who never goes through famidrive.players and
  # so has no `voice` attribute at all (overlays.nix's `resolve` does the
  # same for `overlays`).
  voiceUsers = lib.filterAttrs (_: p: p.voice.discord.enable or false) cfg.allPlayers;
  client = p: if p.voice.discord.client == "vesktop" then pkgs.vesktop else pkgs.discord;
  clientBin = p: if p.voice.discord.client == "vesktop" then "vesktop" else "discord";
in
{
  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.voice.discord = {
        enable = mkEnableOption ''
          Discord voice chat alongside a game, running the whole
          session, hidden until Settings' "Discord Voice Chat" brings
          it up'';
        client = mkOption {
          type = types.enum [ "discord" "vesktop" ];
          default = "discord";
          description = ''
            `"discord"`, the official app, or `"vesktop"` (Vencord's
            client). The official app is the default so this keeps
            working on Discord's own terms; Vesktop is there for a
            player who wants it, and is what the overlay this issue
            describes will need once it's built.
          '';
        };
        mic = mkOption {
          type = types.nullOr types.str;
          default = null;
          example = "alsa_input.usb-Logitech_HD_Webcam_C920-02.analog-stereo";
          description = ''
            PipeWire source to use as their microphone in voice chat (its
            name, as `pactl list sources short` shows it), set as the
            default input for their session. Null leaves whatever
            PipeWire already picked.
          '';
        };
      };
    });
  };

  config = lib.mkIf (cfg.enable && voiceUsers != { }) {
    famidrive.sessionSetup = ''
      case "$(id -un)" in
      ${lib.concatStrings (lib.mapAttrsToList (user: p: ''
        ${user})
          ${lib.optionalString ((p.voice.discord.mic or null) != null) ''
            pactl set-default-source ${lib.escapeShellArg p.voice.discord.mic} \
              || echo "famidrive-session: couldn't set the voice microphone" >&2
          ''}
          # Hidden until Settings' "Discord Voice Chat" (settings.nix)
          # raises it; gamescope never shows an untagged, non-base window,
          # so no flag of the client's own is relied on for that.
          ${pkgs.gamescope-fg}/bin/gamescope-fg --voice-start ${client p}/bin/${clientBin p} &
          ;;
      '') voiceUsers)}
      esac
    '';

    famidrive.playerHome = { famidrivePlayer, ... }:
      lib.mkIf (famidrivePlayer.voice.discord.enable or false) {
        home.packages = [ (client famidrivePlayer) ];
      };
  };
}
