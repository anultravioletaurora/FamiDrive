{ lib, writers, python3Packages, libarchive, famidrive-toast }:

writers.writePython3Bin "famidrive-nexusmods" {
  libraries = [ python3Packages.requests ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@bsdtar@" "@toast@" ] [ "${libarchive}/bin/bsdtar" "${famidrive-toast}/bin/famidrive-toast" ]
  (builtins.readFile ./famidrive_nexusmods.py))
