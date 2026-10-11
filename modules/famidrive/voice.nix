# Voice chat with friends from the couch (#168). Discord only so far,
# through Vesktop (Vencord's client; nixpkgs builds it, and Vencord plays
# better with PipeWire and Wayland than Discord's own app), started
# hidden with the session for players who turn it on.
#
# This is only the first "to check first" from #168: the client running
# alongside a game without stealing gamescope's focus. The Vencord
# plugin the issue describes (voice state out to a socket, mute/deafen
# back in) and the overlay that would read it aren't built yet; until
# then, signing in, joining a channel and muting all happen in Vesktop's
# own window. Discord's terms forbid client mods, which is why this is
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
          Discord voice chat alongside a game, through Vesktop, started
          hidden with the session
        '';
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
          # --start-minimized is Discord's own flag, carried over by most
          # forks; VERIFY it keeps Vesktop's window off gamescope (no
          # window of its own should take focus, #168) and still lets a
          # player reach the QR sign-in the first time.
          ${pkgs.vesktop}/bin/vesktop --start-minimized &
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
