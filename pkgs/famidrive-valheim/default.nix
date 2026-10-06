{ writers }:

writers.writePython3Bin "famidrive-valheim" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_valheim.py)
