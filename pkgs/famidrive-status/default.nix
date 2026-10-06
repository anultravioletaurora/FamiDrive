{ writers, python3Packages }:

writers.writePython3Bin "famidrive-status" {
  libraries = [ python3Packages.pygame-ce ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_status.py)
