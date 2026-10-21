{ lib, writers, python3Packages, poppler-utils }:

writers.writePython3Bin "famidrive-toast" {
  libraries = [ python3Packages.pygame-ce python3Packages.xlib python3Packages.jeepney ];
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@pdftoppm@" "@pdfinfo@" ]
  [ "${poppler-utils}/bin/pdftoppm" "${poppler-utils}/bin/pdfinfo" ]
  (builtins.readFile ./famidrive_toast.py))
