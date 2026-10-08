{ writers }:

writers.writePython3Bin "famidrive-pads" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_pads.py)
