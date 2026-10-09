{ writers, python3Packages }:

writers.writePython3Bin "famidrive-bluetooth" {
  libraries = [ python3Packages.dbus-next ];
  flakeIgnore = [ "E501" "F722" "F821" ];   # line length; dbus-next's D-Bus type strings in annotations
} (builtins.readFile ./famidrive_bluetooth.py)
