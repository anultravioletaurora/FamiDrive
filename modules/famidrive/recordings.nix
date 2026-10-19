# Screen recordings: "Start recording" in the Guide menu (famidrive-toast)
# counts down from 3 and records the TV, game and sound, into the
# player's ~/Recordings (pkgs/famidrive-record), and "Stop recording" in
# the same place ends it. A Recordings system in ES-DE lists them, and
# plays one in mpv.
#
# Art Book Next (ES-DE edition) has no art for recordings, and its
# fallback is Controllers' too, so the two looked alike (first box,
# 2026-10-16): FamiDrive adds a logo, light red art and colors to it
# (pkgs/art-book-next-recordings).
#
# Each recording also gets a still and its own video as its art in ES-DE
# (famidrive-record media), and the folder is in the player's Kodi too,
# under Videos > Files (famidrive.media.kodi.homeFolders).
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
in
{
  options.famidrive.recordings = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = ''
      Screen recording from the Guide menu: "Start recording" counts
      down from 3, then records what's on the TV, with its sound, until
      "Stop recording". Each recording goes in the player's own
      `~/Recordings` as an MP4 named by when it started, and the
      Recordings system in ES-DE lists them to watch. Off: no menu entry
      and no Recordings system; recordings already made stay in
      `~/Recordings`.
    '';
  };

  config = lib.mkIf (cfg.enable && cfg.recordings) {
    # By name from PATH (the Guide menu and the session's end run it), so
    # a fix to it doesn't restart the TV (box-testing.md).
    environment.systemPackages = [ pkgs.famidrive-record ];

    # Art for recordings made before this, or while ES-DE wasn't looking,
    # and none left for ones the player deleted. In the background: it
    # only reads a frame from each new recording, but the TV shouldn't
    # wait on it.
    famidrive.sessionSetup = ''
      famidrive-record media || echo "famidrive-session: couldn't update the recordings' art" >&2 &
    '';

    famidrive.media.kodi.homeFolders.Recordings = { path = "Recordings"; type = "videos"; };

    # Only for Art Book Next: another theme has its own art, or its own
    # fallback.
    famidrive.esde.themeExtras = lib.mkIf (cfg.esde.theme != null && cfg.esde.theme.name == "art-book-next-es-de")
      [ (pkgs.callPackage ../../pkgs/art-book-next-recordings { theme = cfg.esde.theme.src; }) ];

    famidrive.systems.recordings = {
      fullname = "Recordings";
      theme = "recordings";
      sortName = "zzzx";   # with Controllers and Settings, after every game system
      extensions = [ ".mp4" ];
      # mpv-gamepad: mpv with SDL's gamepad input, as the Jellyfin shim
      # uses (flake.nix), so A pauses and the d-pad seeks. Select + Start
      # leaves it, as it does a game. Decoded on the GPU (mpv's default is
      # the CPU): playback was choppy on the first box 2026-10-16, and a 4K
      # video decoded on the CPU is one likely cause.
      command = ''${pkgs.mpv-gamepad}/bin/mpv --fs --hwdec=auto-safe --input-gamepad=yes --keep-open=no "$ROM"'';
    };

    # The Recordings system is a link to ~/Recordings, so it's the folder
    # a player copies their videos from. After famidriveRoms, which
    # clears every link that isn't a shared system's.
    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveRecordings = lib.hm.dag.entryAfter [ "famidriveRoms" ] ''
        mkdir -p "$HOME/Recordings"
        link=${lib.escapeShellArg "${famidrivePlayer.roms}/recordings"}
        if [ -e "$link" ] && [ ! -L "$link" ]; then
          echo "famidrive: $link is a folder, not a link to ~/Recordings; left as it is" >&2
        else
          ln -sfn "$HOME/Recordings" "$link"
        fi
      '';
    };
  };
}
