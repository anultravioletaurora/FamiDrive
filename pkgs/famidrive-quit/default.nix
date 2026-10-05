{ writers, python3Packages }:

writers.writePython3Bin "famidrive-quit" {
  libraries = [ python3Packages.evdev ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_quit.py)
