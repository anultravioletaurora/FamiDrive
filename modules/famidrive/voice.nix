# Voice chat with friends from the couch (#168). Discord by default,
# official: an account only ever used that way stays on Discord's own
# terms, so this keeps working if they ever crack down on client mods.
# `client = "vesktop"` or `"equibop"` switches a player to Vencord's or
# Equicord's desktop client instead, which the future overlay and
# controller mute/deafen (#168) will need a plugin for. Either way it
# runs the whole session for players who turn it on, hidden until they
# go to Settings' "Discord Voice Chat" (settings.nix) to sign in, pick a
# channel, or check who's there; closing that puts ES-DE back without
# ending the call, the same way Big Picture does for Steam.
#
# The Vencord/Equicord plugin #168 describes (voice state out to a
# socket, mute/deafen back in) and the overlay that would read it aren't
# built yet; signing in, joining and muting all happen in the client's
# own window for now. Opt-in per player, not box-wide, either way.
#
# Two couch problems neither client fixes on its own:
#   - A desktop app's own minimize/maximize/close buttons and fonts are
#     sized for a monitor an arm's length away, not a TV across the
#     room. Vesktop and Equibop both have a `nativeTitleBar` setting
#     (off, drawing their own, by default on Vesktop; on already for
#     Equibop on Linux) that this locks on for both: gamescope draws no
#     frame of its own, so a native one is none at all. The official
#     app has no such setting (closed source); its buttons stay.
#   - Chromium's `--force-device-scale-factor` (`display.scale`,
#     session.nix, shared with the boot screen's own scale) scales the
#     whole UI up for a 4K TV, the same flag for all three clients since
#     they're all Electron.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };

  # Safe for the guest too, who never goes through famidrive.players and
  # so has no `voice` attribute at all (overlays.nix's `resolve` does the
  # same for `overlays`).
  voiceUsers = lib.filterAttrs (_: p: p.voice.discord.enable or false) cfg.allPlayers;
  clientPackages = { discord = pkgs.discord; vesktop = pkgs.vesktop; equibop = pkgs.equibop; };
  client = p: clientPackages.${p.voice.discord.client};
  clientBin = p: p.voice.discord.client;
  scaleFlag = " --force-device-scale-factor=${toString cfg.display.scale}";
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
          type = types.enum [ "discord" "vesktop" "equibop" ];
          default = "discord";
          description = ''
            `"discord"`, the official app, or a client mod's desktop
            app: `"vesktop"` (Vencord) or `"equibop"` (Equicord). The
            official app is the default so this keeps working on
            Discord's own terms; Vesktop and Equibop are there for a
            player who wants one, and are what the overlay this issue
            describes will need a plugin for once it's built.
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
          ${pkgs.gamescope-fg}/bin/gamescope-fg --voice-start ${client p}/bin/${clientBin p}${scaleFlag} &
          ;;
      '') voiceUsers)}
      esac
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }:
      lib.mkIf (famidrivePlayer.voice.discord.enable or false) {
        home.packages = [ (client famidrivePlayer) ];
        # Vesktop and Equibop draw their own minimize/maximize/close
        # buttons unless told to use a native frame instead; gamescope
        # draws no frame of its own, so that's none at all. The official
        # app has no such setting (closed source): its buttons stay.
        home.activation.famidriveVoice = lib.mkIf (famidrivePlayer.voice.discord.client != "discord")
          (lib.hm.dag.entryAfter [ "writeBoundary" ] (seedLib.lockKeys {
            format = "json";
            target = "$HOME/.config/${famidrivePlayer.voice.discord.client}/settings.json";
            keys.".nativeTitleBar" = true;
          }));
      };
  };
}
