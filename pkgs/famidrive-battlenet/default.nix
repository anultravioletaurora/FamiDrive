{ lib, writers, python3Packages, util-linux }:

writers.writePython3Bin "famidrive-battlenet" {
  libraries = [ python3Packages.pyyaml ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@nsenter@" ] [ "${util-linux}/bin/nsenter" ]
  (builtins.readFile ./famidrive_battlenet.py))
