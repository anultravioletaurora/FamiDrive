# SuperTux Party, a free party game in the style of Mario Party (Godot 3).
# Not in nixpkgs. Upstream's own Linux build of the last release, patched
# to run on NixOS: the binary and its game data (.pck files), kept
# together, since Godot looks for them next to itself.
{ lib, stdenv, fetchurl, unzip, autoPatchelfHook, makeWrapper
, libX11, libXcursor, libXinerama, libXrandr, libXrender, libXi, libGL
, alsa-lib, libpulseaudio, udev }:

stdenv.mkDerivation rec {
  pname = "supertuxparty";
  version = "0.9";

  src = fetchurl {
    url = "https://supertux.party/download/v${version}/linux.zip";
    hash = "sha256-hvAhUqgGIYHN1063XyGrE9F0hD/8WusLHMgJQ1AEfsk=";
  };

  nativeBuildInputs = [ unzip autoPatchelfHook makeWrapper ];
  buildInputs = [ libX11 libXcursor libXinerama libXrandr libXrender libXi libGL alsa-lib libpulseaudio ];

  unpackPhase = ''
    runHook preUnpack
    unzip -q $src -d source
    runHook postUnpack
  '';
  sourceRoot = "source";
  dontBuild = true;
  dontStrip = true;   # the .pck data is appended to nothing, but stripping Godot binaries is known to break them

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/supertuxparty $out/bin
    cp -r . $out/share/supertuxparty/
    chmod +x $out/share/supertuxparty/supertuxparty
    # Godot opens udev for controller hotplug at run time.
    makeWrapper $out/share/supertuxparty/supertuxparty $out/bin/supertuxparty \
      --prefix LD_LIBRARY_PATH : ${lib.makeLibraryPath [ udev ]}
    runHook postInstall
  '';

  meta = {
    description = "Free and open-source party game inspired by Mario Party";
    homepage = "https://supertux.party";
    license = lib.licenses.gpl3Plus;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "x86_64-linux" ];
    mainProgram = "supertuxparty";
  };
}
