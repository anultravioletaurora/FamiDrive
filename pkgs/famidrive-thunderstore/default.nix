{ writers }:

writers.writePython3Bin "famidrive-thunderstore" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_thunderstore.py)
