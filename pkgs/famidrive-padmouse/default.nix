{ writers, python3Packages }:

writers.writePython3Bin "famidrive-padmouse" {
  libraries = [ python3Packages.evdev ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_padmouse.py)
