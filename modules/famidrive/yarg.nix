# YARG (Yet Another Rhythm Game), in ES-DE's Desktop system, next to Clone
# Hero. It reads the same chart formats, so it plays the box's Clone Hero
# library (clonehero.nix): the same songs for every player, listed once
# in `cloneHero.songs`, whether or not Clone Hero itself is on. Profiles,
# scores and settings are each player's; scores and profiles sync with
# RomM like a console game's save.
#
# YARG 0.14 (nixpkgs) keeps everything in
# ~/.config/unity3d/YARC/YARG/release/: settings.json, profiles/
# (profiles.json, bindings.json), scores/ (scores.db, replays/). Seen on
# the first box 2026-10-07, running it once in a scratch home. A
# settings.json holding only SongFolders loads, and YARG scans them.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  y = cfg.yarg;
  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  songs = "${cfg.dataDir}/clonehero";
  data = ".config/unity3d/YARC/YARG/release";

  sync = cfg.romm.enable && y.romm.entry != null;

  # Scores and profiles: what a player would miss on another box.
  # Bindings stay on this box (they belong to its instruments), and so do
  # replays, which grow with every song played.
  saveLayout = {
    kind = "files";
    root = "~";
    paths = [
      "${data}/scores/scores.db"
      "${data}/profiles/profiles.json"
    ];
  };
in
{
  options.famidrive.yarg = {
    enable = mkEnableOption ''
      YARG (Yet Another Rhythm Game), in ES-DE's Desktop system: guitar,
      bass, drums, keys and vocals, with the box's Clone Hero songs
      (`cloneHero.songs`)'';

    romm.entry = mkOption {
      type = types.nullOr types.str;
      default = "YARG";
      description = ''
        The RomM entry each player's YARG scores and profiles are saved
        under, by name. RomM keeps saves only for games in its library, so
        add one by hand, with "Add Physical Game" (no file needed), as for
        Clone Hero. null keeps scores on this box only.
      '';
    };
  };

  config = lib.mkIf (cfg.enable && y.enable) {

    # YARG reads guitars and drums through hidraw (its HIDrogen backend),
    # which is root-only by default; Clone Hero reads the joystick
    # interface, which players can. Found on the first box 2026-10-07: a
    # Wii Les Paul on a Raphnet adapter worked in Clone Hero, and YARG
    # logged "HIDrogen ... Error getting descriptor (EACCES)". The player
    # at the TV (uaccess) gets the hidraw devices of rhythm-game hardware
    # only, by vendor, not every hidraw device (keyboards are hidraw too).
    # In a rules file of its own, numbered before systemd's 73-seat-late,
    # which turns the uaccess tag into access: extraRules (99-local) would
    # come too late.
    services.udev.packages = [ (pkgs.writeTextDir "lib/udev/rules.d/70-famidrive-instruments.rules" (lib.concatMapStrings (v: ''
      KERNEL=="hidraw*", ATTRS{idVendor}=="${v}", TAG+="uaccess"
    '') [
      "289b"   # raphnet technologies (Wii, GameCube and other instrument adapters)
      "1209"   # pid.codes: Santroller and other open-hardware instruments
      "1430"   # RedOctane (Guitar Hero, its dongles and PC guitars)
      "12ba"   # Sony Computer Entertainment America (PS3 Guitar Hero and Rock Band)
      "0e6f"   # PDP (Rock Band 4, Riffmaster)
      "0738"   # Mad Catz (Rock Band)
      "1bad"   # Harmonix (Rock Band)
      "3651"   # CRKD (Nitro guitars)
    ])) ];
    environment.systemPackages = [ pkgs.yarg ];

    # Another kind of Desktop entry, like Clone Hero's: a .port file whose
    # content says which. The commands add to Clone Hero's (types.lines),
    # each case only acting on its own entry.
    famidrive.desktop.".port" = {
      before = lib.optionalString sync ''
        if [ "$(cat "$ROM")" = yarg ]; then
          [ -z "$sync" ] || romm-agent save-pull yarg app:yarg \
            || echo "famidrive-launch: YARG scores not pulled" >&2
        fi
      '';
      command = ''
        case "$(cat "$ROM")" in
          yarg) ${pkgs.yarg}/bin/yarg ;;
        esac
      '';
      after = lib.optionalString sync ''
        if [ "$(cat "$ROM")" = yarg ]; then
          [ -z "$sync" ] || romm-agent save-push yarg app:yarg \
            || echo "famidrive-launch: YARG scores not pushed, reconcile will retry" >&2
        fi
      '';
    };

    famidrive.romm.apps = lib.mkIf sync {
      yarg = { title = "YARG"; rom = y.romm.entry; emulator = "yarg"; inherit saveLayout; };
    };

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveYarg = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/desktop"}
        printf yarg > ${lib.escapeShellArg "${famidrivePlayer.roms}/desktop/YARG.port"}
        rm -f ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/YARG.port"}   # in Ports until 2026-10-10
        mkdir -p "$HOME/YARG Songs"
        ${seedLib.lockKeys {
          format = "json";
          target = "$HOME/${data}/settings.json";
          # The box's songs, then hand-added ones, then the player's own.
          keys.".SongFolders" = [
            "${songs}/songs"
            "${songs}/local"
            "${famidrivePlayer.home}/YARG Songs"
          ];
        }}
      '';
    };
  };
}
