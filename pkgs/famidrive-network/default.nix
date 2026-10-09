{ writers, python3Packages }:

writers.writePython3Bin "famidrive-network" {
  libraries = [ python3Packages.dbus-next ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_network.py)
