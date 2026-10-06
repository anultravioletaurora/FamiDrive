# ES-DE was removed from nixpkgs on 2025-10-23 (FreeImage vulnerabilities).
# Open question in tv-interface.md: wrap upstream's AppImage (below, quickest) or
# build from source against a permitted-insecure freeimage.
{ lib, appimageTools, fetchurl }:

appimageTools.wrapType2 rec {
  pname = "es-de";
  version = "3.5.0";

  # The AppImage runs in a bubblewrap sandbox with an /etc of its own, and
  # every game ES-DE starts inherits it. Found on the first box
  # 2026-10-06: /etc/famidrive (each player's RomM agent config) wasn't
  # there, so famidrive-launch quietly skipped save sync.
  extraBwrapArgs = [ "--ro-bind-try /etc/famidrive /etc/famidrive" ];

  src = fetchurl {
    # ES_DE_x64.AppImage from the v3.5.0 release (2026-09-30).
    url = "https://gitlab.com/es-de/emulationstation-de/-/package_files/357718352/download";
    name = "ES-DE_x64-${version}.AppImage";
    hash = "sha256-q8KZmhI4X4V3W9P5hvqJHHa2nfN5H3wS5MeDzzw2MPU=";
  };

  meta = {
    description = "EmulationStation Desktop Edition";
    homepage = "https://es-de.org";
    license = lib.licenses.mit;
    mainProgram = "es-de";
    platforms = [ "x86_64-linux" ];
  };
}
