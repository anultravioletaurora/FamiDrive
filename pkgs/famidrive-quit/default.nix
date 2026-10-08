{ lib, writers, python3Packages, sdl_gamecontrollerdb }:

writers.writePython3Bin "famidrive-quit" {
  libraries = [ python3Packages.evdev ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@gamecontrollerdb@" ] [ "${sdl_gamecontrollerdb}/share/gamecontrollerdb.txt" ]
  (builtins.readFile ./famidrive_quit.py))
