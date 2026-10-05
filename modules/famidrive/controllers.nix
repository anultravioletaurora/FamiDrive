# Controllers (controllers.md). The ways out of a game, and what's plugged
# into each GameCube port.
#
# Quitting: hold Select + Start on any pad (famidrive-quit, started by the
# session). RetroArch also has its own menu on L3 + R3 (click both sticks).
#
# GameCube ports are set here instead of in Dolphin's own screens, so a
# rebuilt or second box comes up with the same ports.
# Found on the first box 2026-10-05: an old Dolphin.ini had every port on "Wii U
# GameCube adapter", so Dolphin ignored the 8BitDo entirely. It had also
# filled port 1 with keyboard keys under the 8BitDo's name.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  ports = cfg.controllers.gamecube.ports;

  # Controllers FamiDrive knows by a short name, mapped to the name SDL
  # (and so Dolphin) gives them. Anything not listed can still be used by
  # passing its SDL name directly.
  knownPads = {
    # 2.4 GHz dongle (USB 2dc8:310b, the xpad driver). Bluetooth mode
    # reports a different name and is untested.
    "8bitdo-ultimate-2" = "8BitDo Ultimate 2 Wireless Controller";
  };

  # Dolphin's SIDevice numbers (SI_Device.h): 0 nothing, 6 standard
  # GameCube controller, 12 Wii U GameCube adapter.
  siDevice = p: if p == "none" then 0 else if p == "adapter" then 12 else 6;

  isPad = p: p != "none" && p != "adapter";

  # Dolphin tells identical controllers apart by a per-name index:
  # SDL/0/<name> is the first one connected, SDL/1/<name> the second.
  device = i: p:
    let
      name = knownPads.${p} or p;
      before = lib.count (q: (knownPads.${q} or q) == name) (lib.take i ports);
    in
    "SDL/${toString before}/${name}";

  # A modern pad on a GameCube port. Names are SDL's standard gamepad
  # layout, so this one mapping fits any pad SDL recognizes. Face buttons
  # follow the GameCube's shape: A at the bottom, B left, X right, Y top.
  padMapping = {
    "Buttons/A" = "`Button S`";
    "Buttons/B" = "`Button W`";
    "Buttons/X" = "`Button E`";
    "Buttons/Y" = "`Button N`";
    "Buttons/Z" = "`Shoulder R`";
    "Buttons/Start" = "`Start`";
    "Main Stick/Up" = "`Left Y+`";
    "Main Stick/Down" = "`Left Y-`";
    "Main Stick/Left" = "`Left X-`";
    "Main Stick/Right" = "`Left X+`";
    "C-Stick/Up" = "`Right Y+`";
    "C-Stick/Down" = "`Right Y-`";
    "C-Stick/Left" = "`Right X-`";
    "C-Stick/Right" = "`Right X+`";
    "Triggers/L" = "`Trigger L`";
    "Triggers/R" = "`Trigger R`";
    "Triggers/L-Analog" = "`Trigger L`";
    "Triggers/R-Analog" = "`Trigger R`";
    "D-Pad/Up" = "`Pad N`";
    "D-Pad/Down" = "`Pad S`";
    "D-Pad/Left" = "`Pad W`";
    "D-Pad/Right" = "`Pad E`";
    "Rumble/Motor" = "`Motor`";
  };

  seedLib = import ./lib/seed.nix { inherit lib pkgs; };
  crudini = "${pkgs.crudini}/bin/crudini";
  gcpad = ''"$HOME/.config/dolphin-emu/GCPadNew.ini"'';
  q = lib.escapeShellArg;
in
{
  options.famidrive.controllers.gamecube.ports = mkOption {
    type = types.listOf types.str;
    default = [ "gamepad" ];
    example = [ "8bitdo-ultimate-2" "8bitdo-ultimate-2" "adapter" ];
    description = ''
      What's in each GameCube port in Dolphin, port 1 first. Ports left off
      the end are empty. Each entry is one of:

      - `"gamepad"`: a modern controller, whichever one Dolphin picks.
      - a known controller's short name, such as `"8bitdo-ultimate-2"`. Name
        the same model twice for two of them; the first one connected is
        the lower port.
      - any other controller's SDL name, as Dolphin shows it.
      - `"adapter"`: a real GameCube controller on the official adapter
        (Wii U / Switch GameCube adapter).
      - `"none"`: nothing in this port.

      These ports are rebuilt on every switch. Changes made in Dolphin's own
      controller screens don't last, on purpose.
    '';
  };

  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = lib.length ports <= 4;
      message = "famidrive.controllers.gamecube.ports: a GameCube has 4 ports.";
    }];

    # USB access to the GameCube adapter (Dolphin's udev rule).
    services.udev.packages = lib.mkIf (lib.elem "adapter" ports) [ pkgs.dolphin-emu ];

    home-manager.users.${cfg.user} = { lib, ... }: {
      home.activation.famidriveControllers = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p "$HOME/.config/dolphin-emu"
        touch "$HOME/.config/dolphin-emu/Dolphin.ini" ${gcpad}
        ${lib.concatStrings (lib.genList (i:
          let p = lib.elemAt (ports ++ lib.replicate 4 "none") i; in ''
            ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Core SIDevice${toString i} ${toString (siDevice p)}
            # Rebuilt from scratch, so nothing left over from Dolphin's own guesses.
            ${crudini} --del ${gcpad} GCPad${toString (i + 1)}
          '' + lib.optionalString (isPad p) ''
            ${lib.optionalString (p != "gamepad") ''
              ${crudini} --set ${gcpad} GCPad${toString (i + 1)} Device ${q (device i p)}
            ''}
            ${lib.concatStrings (lib.mapAttrsToList (k: v: ''
              ${crudini} --set ${gcpad} GCPad${toString (i + 1)} ${q k} ${q v}
            '') padMapping)}
          '') 4)}

        # Quitting is famidrive-quit's job: no "are you sure?" box nobody
        # can reach with a controller.
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Interface ConfirmStop False
        # Read the controllers even if gamescope hasn't given Dolphin's
        # window keyboard focus. Only one game runs at a time.
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Input BackgroundInput True

        # RetroArch's own menu (save states, settings) on L3 + R3. Its combo
        # list has no Select + X, and anything with Select + Start would
        # collide with famidrive-quit. 2 = L3 + R3.
        ${seedLib.lockKeys {
          format = "keyValue";
          target = "$HOME/.config/retroarch/retroarch.cfg";
          keys.input_menu_toggle_gamepad_combo = 2;
        }}
      '';
    };
  };
}
