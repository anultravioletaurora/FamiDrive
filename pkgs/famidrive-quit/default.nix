{ lib, writers, python3Packages, sdl_gamecontrollerdb, famidrive-bluetooth }:

writers.writePython3Bin "famidrive-quit" {
  libraries = [ python3Packages.evdev ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@gamecontrollerdb@" "@famidrivebluetooth@" ]
  [ "${sdl_gamecontrollerdb}/share/gamecontrollerdb.txt" "${famidrive-bluetooth}/bin/famidrive-bluetooth" ]
  (builtins.readFile ./famidrive_quit.py))
