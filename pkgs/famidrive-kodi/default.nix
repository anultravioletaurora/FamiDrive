{ writers }:

writers.writePython3Bin "famidrive-kodi" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_kodi.py)
