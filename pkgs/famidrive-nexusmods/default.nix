{ lib, writers, python3Packages, libarchive, unar, vulkan-tools, famidrive-toast }:

writers.writePython3Bin "famidrive-nexusmods" {
  libraries = [ python3Packages.requests python3Packages.xxhash python3Packages.pyyaml ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@bsdtar@" "@unar@" "@vulkaninfo@" "@toast@" ] [ "${libarchive}/bin/bsdtar" "${unar}/bin/unar" "${vulkan-tools}/bin/vulkaninfo" "${famidrive-toast}/bin/famidrive-toast" ]
  (builtins.readFile ./famidrive_nexusmods.py))
