{ writers }:

writers.writePython3Bin "famidrive-clonehero" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_clonehero.py)
