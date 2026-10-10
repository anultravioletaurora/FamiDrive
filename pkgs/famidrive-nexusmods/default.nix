{ lib, writers, python3Packages, libarchive, unar, famidrive-toast }:

writers.writePython3Bin "famidrive-nexusmods" {
  libraries = [ python3Packages.requests python3Packages.xxhash ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@bsdtar@" "@unar@" "@toast@" ] [ "${libarchive}/bin/bsdtar" "${unar}/bin/unar" "${famidrive-toast}/bin/famidrive-toast" ]
  (builtins.readFile ./famidrive_nexusmods.py))
