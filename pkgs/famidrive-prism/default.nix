{ writers }:

writers.writePython3Bin "famidrive-prism" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_prism.py)
