# Free games starring Tux, in ES-DE's Ports system, each turned on by
# itself. All three are made for controllers and need nothing else:
#
# - SuperTuxKart: kart racing. Its menus, multiplayer setup (each player
#   presses a button on their own pad) and on-screen keyboard all work
#   from a pad.
# - SuperTux: a 2D platformer.
# - SuperTux Party: a party game of boards and minigames, up to four
#   players, like Mario Party. Not in nixpkgs: pkgs/supertuxparty.
# - SuperTux Advance: a newer 2D platformer in the SuperTux style, on
#   its author's Brux engine. Not in nixpkgs: pkgs/supertux-advance.
# - Extreme Tux Racer: sledding Tux downhill, collecting herring.
# - Tux Paint: a drawing program for children. It plays best with a
#   mouse or a touchscreen; it can also move its pointer with a pad.
#
# Their settings and progress are in each player's home and don't sync
# with RomM yet.
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;

  # SDL leaves out an instrument adapter (raphnet's WUSBMote, for Wii
  # guitars), which it otherwise counts as a game controller. Found on the
  # first box 2026-10-09: SuperTux gave player 1 the first controller,
  # which was the guitar adapter, and the 8BitDo did nothing.
  ignoreInstruments = "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x289b/0x0080";

  # Each game: its option, its Ports entry's name, the word in its .port
  # file, what runs it, and anything set for it first.
  games = {
    superTuxKart = { title = "SuperTuxKart"; word = "supertuxkart"; package = pkgs.supertuxkart; };
    superTux = { title = "SuperTux"; word = "supertux"; package = pkgs.supertux; env = ignoreInstruments; };
    # Godot 3.2's own controller list is from 2021: the pads plugged in are
    # looked up in SDL's community database, which Godot reads from
    # SDL_GAMECONTROLLERCONFIG (famidrive-pads sdl-mappings).
    superTuxParty = {
      title = "SuperTux Party"; word = "supertuxparty"; package = pkgs.supertuxparty;
      env = ''SDL_GAMECONTROLLERCONFIG="$(${pkgs.famidrive-pads}/bin/famidrive-pads sdl-mappings ${pkgs.sdl_gamecontrollerdb}/share/gamecontrollerdb.txt)"'';
    };
    superTuxAdvance = { title = "SuperTux Advance"; word = "supertuxadvance"; package = pkgs.supertux-advance; };
    extremeTuxRacer = { title = "Extreme Tux Racer"; word = "extremetuxracer"; package = pkgs.extremetuxracer; };
    tuxPaint = { title = "Tux Paint"; word = "tuxpaint"; package = pkgs.tuxpaint; };
  };
  on = lib.filterAttrs (name: _: cfg.${name}.enable) games;
in
{
  options.famidrive = lib.mapAttrs (_: g: {
    enable = lib.mkEnableOption "${g.title}, in ES-DE's Ports system";
  }) games;

  config = lib.mkIf (cfg.enable && on != { }) {
    environment.systemPackages = lib.mapAttrsToList (_: g: g.package) on;

    # Another kind of Ports entry, like Clone Hero's: a .port file whose
    # content says which.
    famidrive.ports.".port".command = ''
      case "$(cat "$ROM")" in
      ${lib.concatStrings (lib.mapAttrsToList (_: g: ''
        ${g.word}) ${g.env or ""} ${lib.getExe g.package} ;;
      '') on)}
      esac
    '';

    famidrive.playerHome = { lib, famidrivePlayer, ... }: {
      home.activation.famidriveTux = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p ${lib.escapeShellArg "${famidrivePlayer.roms}/ports"}
        ${lib.concatStrings (lib.mapAttrsToList (_: g: ''
          printf ${g.word} > ${lib.escapeShellArg "${famidrivePlayer.roms}/ports/${g.title}.port"}
        '') on)}
      '';
    };
  };
}
