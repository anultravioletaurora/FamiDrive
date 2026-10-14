{ writers }:

writers.writePython3Bin "famidrive-steam-offline" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_steam_offline.py)
