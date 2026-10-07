{ writers }:

writers.writePython3Bin "famidrive-hardware" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_hardware.py)
