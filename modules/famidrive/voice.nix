# Voice chat with friends from the couch (#168). Discord only so far,
# through Vesktop (Vencord's client; nixpkgs builds it, and Vencord plays
# better with PipeWire and Wayland than Discord's own app), running the
# whole session for players who turn it on, hidden until they go to
# Settings' "Discord Voice Chat" (settings.nix) to sign in, pick a
# channel, or check who's there; closing that puts ES-DE back without
# ending the call, the same way Big Picture does for Steam.
#
# The Vencord plugin #168 describes (voice state out to a socket,
# mute/deafen back in) and the overlay that would read it aren't built
# yet; signing in, joining and muting all happen in Vesktop's own window
# for now. Discord's terms forbid client mods, which is why this is
# opt-in per player, not box-wide.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;

  # Safe for the guest too, who never goes through famidrive.players and
  # so has no `voice` attribute at all (overlays.nix's `resolve` does the
  # same for `overlays`).
  voiceUsers = lib.filterAttrs (_: p: p.voice.discord.enable or false) cfg.allPlayers;
in
{
  options.famidrive.players = mkOption {
    type = types.attrsOf (types.submodule {
      options.voice.discord = {
        enable = mkEnableOption ''
          Discord voice chat alongside a game, through Vesktop, running
          the whole session, hidden until Settings' "Discord Voice Chat"
          brings it up'';
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
          # so no flag of Vesktop's own is relied on for that.
          ${pkgs.gamescope-fg}/bin/gamescope-fg --voice-start ${pkgs.vesktop}/bin/vesktop &
          ;;
      '') voiceUsers)}
      esac
    '';

    famidrive.playerHome = { famidrivePlayer, ... }:
      lib.mkIf (famidrivePlayer.voice.discord.enable or false) {
        home.packages = [ pkgs.vesktop ];
      };
  };
}
