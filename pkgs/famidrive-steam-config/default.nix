{ writers }:

writers.writePython3Bin "famidrive-steam-config" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_steam_config.py)
