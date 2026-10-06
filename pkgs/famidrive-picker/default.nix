{ writers, python3Packages }:

writers.writePython3Bin "famidrive-picker" {
  libraries = [ python3Packages.pygame-ce ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_picker.py)
