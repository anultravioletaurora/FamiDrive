{ writers, python3Packages }:

writers.writePython3Bin "famidrive-cheevos" {
  libraries = [ python3Packages.requests ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_cheevos.py)
