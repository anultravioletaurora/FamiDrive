# Controllers (controllers.md). The ways out of a game, what's plugged
# into each GameCube port and Wii Remote slot, and face-button layout.
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
  wii = cfg.controllers.wii;
  wiiSource = { none = 0; emulated = 1; real = 2; };
  anyReal = lib.elem "real" wii.remotes || wii.balanceBoard;
  byLabel = cfg.controllers.faceButtons == "labels";

  # Controllers FamiDrive knows by a short name: the name SDL (and so
  # Dolphin) gives them, and the GUID Eden stores in its bindings. Anything
  # not listed can still go on a GameCube port by its SDL name.
  knownPads = {
    # 2.4 GHz dongle (USB 2dc8:310b, the xpad driver). Bluetooth mode
    # reports a different name and is untested.
    "8bitdo-ultimate-2" = {
      sdlName = "8BitDo Ultimate 2 Wireless Controller";
    };
  };
  sdlName = p: knownPads.${p}.sdlName or p;


  # Dolphin's SIDevice numbers (SI_Device.h): 0 nothing, 6 standard
  # GameCube controller, 12 Wii U GameCube adapter.
  siDevice = p: if p == "none" then 0 else if p == "adapter" then 12 else 6;

  isPad = p: p != "none" && p != "adapter";

  # Dolphin tells identical controllers apart by a per-name index:
  # SDL/0/<name> is the first one connected, SDL/1/<name> the second.
  device = i: p:
    let
      name = sdlName p;
      before = lib.count (q: sdlName q == name) (lib.take i ports);
    in
    "SDL/${toString before}/${name}";

  # A modern pad on a GameCube port. Names are SDL's standard gamepad
  # layout, so this one mapping fits any pad SDL recognizes. SDL names
  # buttons by position on an Xbox-style pad (A bottom, B right, X left,
  # Y top). "positions" follows the GameCube's shape instead: B left,
  # X right. With "labels", famidrive-pads sets A, B, X and Y again for
  # each pad it puts on a "gamepad" port, by the labels on that pad: a
  # Nintendo-labelled one has B at the bottom.
  padMapping = {
    "Buttons/A" = "`Button S`";
    "Buttons/B" = if byLabel then "`Button E`" else "`Button W`";
    "Buttons/X" = if byLabel then "`Button W`" else "`Button E`";
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
  options.famidrive.controllers.instruments = mkOption {
    type = types.listOf (types.strMatching "[0-9a-fA-F]{4}:[0-9a-fA-F]{4}");
    default = [ "289b:0080" ];
    example = [ "289b:0080" "12ba:0100" ];
    description = ''
      USB ids (vendor:product) of instrument adapters: guitars and drums
      for rhythm games. Clone Hero and YARG see them; Steam games and
      SuperTux don't, since SDL takes any of them for a game controller,
      and one plugged in first became player 1. Found on the first box
      2026-10-09: Call of Duty: WWII read the guitar adapter instead of
      the 8BitDo. The default is raphnet's WUSBMote (Wii guitars and
      drums).
    '';
  };

  # The same list as SDL's SDL_GAMECONTROLLER_IGNORE_DEVICES wants it,
  # which Proton's Wine also reads, for its SDL and its evdev devices
  # alike (is_sdl_ignored_device, dlls/winebus.sys/bus_sdl.c).
  options.famidrive.controllers.sdlIgnoreDevices = mkOption {
    type = types.str;
    readOnly = true;
    internal = true;
    default = lib.concatMapStringsSep "," (id:
      let p = lib.splitString ":" (lib.toLower id); in "0x${lib.elemAt p 0}/0x${lib.elemAt p 1}"
    ) cfg.controllers.instruments;
  };

  options.famidrive.controllers.faceButtons = mkOption {
    type = types.enum [ "labels" "positions" ];
    default = "labels";
    description = ''
      How a modern pad's A/B/X/Y reach the GameCube and the Switch, whose
      layouts differ from an Xbox-style pad's.

      - `"labels"`: pressing the button printed A is A in the game, and so
        on. What you see is what you get, but B and X sit somewhere else
        than on the original console.
      - `"positions"`: buttons keep the original console's places. On the
        Switch, the bottom button is B and the right one A; on the
        GameCube and the N64, B is left (and the GameCube's X right),
        whatever the pad says.

      On the N64 (RetroArch's Mupen64Plus-Next), "labels" puts the N64's
      B on the pad's B and the C button that was there on X. Found on the
      first box 2026-10-06: Mario Party 3's dialog skipped ahead on X.

      In Eden this applies to the pads FamiDrive knows (see
      `gamecube.ports`) once Eden has set one up; other pads keep Eden's
      own mapping.
    '';
  };

  options.famidrive.controllers.wii = {
    remotes = mkOption {
      type = types.listOf (types.enum [ "real" "emulated" "none" ]);
      default = [ "emulated" ];
      example = [ "real" "real" "real" "real" ];
      description = ''
        What's in each Wii Remote slot in Dolphin, player 1 first. Slots
        left off the end are empty. Each entry is one of:

        - `"real"`: a first-party Wii Remote over Bluetooth. Dolphin keeps
          looking for remotes, so pressing 1 + 2 (or the red sync button)
          connects one at any time, also mid-game. Everything a remote
          has works, including its speaker, Nunchuk and Classic
          Controller.
        - `"emulated"`: Dolphin's emulated Wii Remote, played with a modern
          pad. Its bindings are still Dolphin's own, made in its controller
          screens; FamiDrive doesn't set them yet.
        - `"none"`: nothing in this slot.

        Rebuilt on every switch, like the GameCube ports.
      '';
    };

    balanceBoard = mkOption {
      type = types.bool;
      default = false;
      description = ''
        A real Wii Balance Board, connected like a real Wii Remote (the
        sync button under its battery cover).
      '';
    };

    speaker = mkOption {
      type = types.bool;
      default = true;
      description = "Play game sounds through real Wii Remotes' speakers.";
    };

    bluetoothPassthrough = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Hand a Bluetooth adapter to the emulated Wii entirely, as a real
        Wii's Bluetooth chip. The most faithful way to use real remotes
        (pairing is remembered, as on a Wii), but it needs an adapter
        Dolphin supports, and that adapter is then of no use to anything
        else on the box, so it should be a second one. Untested.
      '';
    };
  };

  options.famidrive.controllers.xboxWirelessAdapter = mkOption {
    type = types.bool;
    default = false;
    description = ''
      Turn on xone, the driver for Microsoft's Xbox Wireless Adapter (the
      USB dongle that connects Xbox One and Series controllers without
      Bluetooth). Only the dongle needs it: those controllers already work
      over Bluetooth (xpadneo) and over a USB cable (`xpad`).

      Off by default, because xone replaces the kernel's `xpad` driver
      with xpad-noone, a copy without Xbox One support, so that the two
      don't fight over wired Xbox One pads. xpad-noone still drives Xbox
      360 pads, and 8BitDo pads in XInput mode. xone also blocks
      `mt76x2u`, the driver for some MediaTek USB Wi-Fi adapters, since
      the dongle uses the same chip.
    '';
  };

  options.famidrive.controllers.gamecube.ports = mkOption {
    type = types.listOf types.str;
    default = [ "gamepad" ];
    example = [ "8bitdo-ultimate-2" "8bitdo-ultimate-2" "adapter" ];
    description = ''
      What's in each GameCube port in Dolphin, port 1 first. Ports left off
      the end are empty. Each entry is one of:

      - `"gamepad"`: whichever controller is connected when the game
        starts: the first `"gamepad"` port gets the first pad, and so on,
        modern pads before GameCube controllers on the official adapter.
        Any model works; nothing is tied to one pad.
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
    # The pads connected when a game starts, bound in Dolphin and Eden just
    # before it (pkgs/famidrive-pads), each read through that emulator's own
    # SDL. Both bind a pad by identity, so a binding made for one pad did
    # nothing for another. Found on the first box 2026-10-07: with the
    # 8BitDo flat, the Xbox controller worked in Steam and RetroArch but not
    # in Dolphin or Eden.
    famidrive.systems = lib.mkIf (lib.elem "roms" cfg.lanes) (
      let
        dolphin = lib.optionalString (lib.elem "gamepad" ports) ''
          ${pkgs.famidrive-pads}/bin/famidrive-pads dolphin ${q (builtins.toJSON {
            sdl = "${lib.getLib pkgs.sdl3}/lib/libSDL3.so.0";   # Dolphin's
            inherit ports;
            inherit (cfg.controllers) faceButtons;
            adapter = lib.elem "adapter" ports;
            config = "~/.config/dolphin-emu/GCPadNew.ini";
          })} || echo "famidrive-launch: couldn't bind the connected pads in Dolphin" >&2
        '';
      in {
        gc.before = dolphin;
        wii.before = dolphin;
        wiiu.before = ''
          ${pkgs.famidrive-pads}/bin/famidrive-pads cemu ${q (builtins.toJSON {
            sdl = "${lib.getLib pkgs.SDL2}/lib/libSDL2-2.0.so.0";   # Cemu's (sdl2-compat)
            inherit (cfg.controllers) faceButtons;
            config = "~/.config/Cemu/controllerProfiles/controller0.xml";
          })} || echo "famidrive-launch: couldn't bind the connected pad in Cemu" >&2
        '';
        switch.before = ''
          ${pkgs.famidrive-pads}/bin/famidrive-pads eden ${q (builtins.toJSON {
            sdl = "${lib.getLib pkgs.SDL2}/lib/libSDL2-2.0.so.0";   # Eden's (sdl2-compat)
            inherit (cfg.controllers) faceButtons;
            config = "~/.config/eden/qt-config.ini";
          })} || echo "famidrive-launch: couldn't bind the connected pads in Eden" >&2
        '';
      });

    assertions = [{
      assertion = lib.length ports <= 4;
      message = "famidrive.controllers.gamecube.ports: a GameCube has 4 ports.";
    } {
      assertion = lib.length wii.remotes <= 4;
      message = "famidrive.controllers.wii.remotes: a Wii has 4 Wii Remote slots.";
    }];

    # USB access to the GameCube adapter and to Bluetooth adapters for
    # passthrough (Dolphin's udev rules).
    services.udev.packages =
      lib.optional (lib.elem "adapter" ports || wii.bluetoothPassthrough) pkgs.dolphin-emu
      # Wii Remotes paired with the box over Bluetooth: the player at the
      # TV may open their hidraw devices, which Dolphin's real-remote mode
      # reads. Dolphin's own rules only cover remotes on USB (the
      # DolphinBar): a Bluetooth remote has no USB attributes. Found on the
      # first box 2026-10-08: hidraw was root-only, and Dolphin never took
      # the remote. 0306 is the Wii Remote, 0330 the Wii Remote Plus. In a
      # file of its own, numbered before systemd's 73-seat-late (as YARG's
      # instruments).
      ++ lib.optional anyReal (pkgs.writeTextDir "lib/udev/rules.d/70-famidrive-wii-remotes.rules" ''
        SUBSYSTEM=="hidraw", KERNELS=="0005:057E:0306.*", TAG+="uaccess"
        SUBSYSTEM=="hidraw", KERNELS=="0005:057E:0330.*", TAG+="uaccess"
      '');

    # The Xbox Wireless Adapter: nixpkgs' module brings the driver, the
    # dongle's firmware (unfree, allowed in default.nix) and xpad-noone.
    hardware.xone.enable = cfg.controllers.xboxWirelessAdapter;

    famidrive.playerHome = { lib, ... }: {
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

        # Wii Remote slots. Sources: 0 nothing, 1 emulated, 2 real.
        wiimote="$HOME/.config/dolphin-emu/WiimoteNew.ini"
        touch "$wiimote"
        ${lib.concatStrings (lib.genList (i: ''
          ${crudini} --set "$wiimote" Wiimote${toString (i + 1)} Source ${toString wiiSource.${lib.elemAt (wii.remotes ++ lib.replicate 4 "none") i}}
        '') 4)}
        ${crudini} --set "$wiimote" BalanceBoard Source ${if wii.balanceBoard then "2" else "0"}
        # Keep looking for real remotes, so one connects whenever 1 + 2 is
        # pressed, not only at game start.
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Core WiimoteContinuousScanning ${if anyReal then "True" else "False"}
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Core WiimoteEnableSpeaker ${if wii.speaker then "True" else "False"}
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" BluetoothPassthrough Enabled ${if wii.bluetoothPassthrough then "True" else "False"}


        # Quitting is famidrive-quit's job: no "are you sure?" box nobody
        # can reach with a controller.
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Interface ConfirmStop False
        # Read the controllers even if gamescope hasn't given Dolphin's
        # window keyboard focus. Only one game runs at a time.
        ${crudini} --set "$HOME/.config/dolphin-emu/Dolphin.ini" Input BackgroundInput True

        # N64 (RetroArch's Mupen64Plus-Next): a remap file for the core,
        # every port. Face buttons per faceButtons: btn_a is the pad's
        # right button, btn_y its left; RetroPad ids 1 is Y (the core's
        # N64 B), 8 is A (its C1). And both triggers are Z: the core puts
        # Z on LT only, and on RT a "C buttons mode" that does nothing by
        # itself (the right stick already gives the C buttons). Found on
        # the first box 2026-10-06 in Mario Party 3: RT did nothing.
        # 12 is L2, the core's Z.
        n64="$HOME/.config/retroarch/config/remaps/Mupen64Plus-Next"
        mkdir -p "$n64"
        touch "$n64/Mupen64Plus-Next.rmp"
        ${seedLib.lockKeys {
          format = "keyValue";
          target = "$HOME/.config/retroarch/config/remaps/Mupen64Plus-Next/Mupen64Plus-Next.rmp";
          keys = lib.listToAttrs (lib.concatMap (n: [
            (lib.nameValuePair "input_player${toString n}_btn_a" (if byLabel then 1 else 8))
            (lib.nameValuePair "input_player${toString n}_btn_y" (if byLabel then 8 else 1))
            (lib.nameValuePair "input_player${toString n}_btn_r2" 12)
          ]) [ 1 2 3 4 ]);
        }}

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
