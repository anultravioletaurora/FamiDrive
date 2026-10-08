# SuperTux Advance, a 2D platformer in the style of the SuperTux games,
# made for the Brux game engine by the same author. Neither is in
# nixpkgs, and the game's releases only ship a Windows build, so both are
# built here from source, at matching commits (they're developed
# together): Brux with Meson, then the game's scripts and art beside it.
{ lib, stdenv, fetchFromGitHub, meson, ninja, cmake, pkg-config, makeWrapper
, SDL2, SDL2_image, SDL2_net, SDL2_mixer, SDL2_gfx, curl, physfs, libgit2 }:

let
  brux = stdenv.mkDerivation (finalAttrs: {
    pname = "brux-gdk";
    version = "0-unstable-2026-08-19";

    src = fetchFromGitHub {
      owner = "KelvinShadewing";
      repo = "brux-gdk";
      rev = "d8e73aa44d39029421738a1606ac78c79b98d2c1";
      fetchSubmodules = true;   # simplesquirrel (and Squirrel inside it)
      hash = "sha256-/7EZ8DLpwEEqx7Nxu/Td35fBYqH42rYtGz4PH/aeaRE=";
    };
    sourceRoot = "${finalAttrs.src.name}/rte";

    nativeBuildInputs = [ meson ninja cmake pkg-config ];
    dontUseCmakeConfigure = true;   # Meson drives CMake for the subprojects
    buildInputs = [ SDL2 SDL2_image SDL2_net SDL2_mixer SDL2_gfx curl physfs libgit2 ];

    installPhase = ''
      runHook preInstall
      install -Dm755 brux $out/bin/brux
      runHook postInstall
    '';

    meta = {
      description = "Brux, a 2D game engine scripted in Squirrel";
      homepage = "https://github.com/KelvinShadewing/brux-gdk";
      license = lib.licenses.agpl3Only;
      platforms = lib.platforms.linux;
      mainProgram = "brux";
    };
  });
in
stdenv.mkDerivation {
  pname = "supertux-advance";
  version = "0-unstable-2026-08-09";

  src = fetchFromGitHub {
    owner = "KelvinShadewing";
    repo = "supertux-advance";
    rev = "cb51c39235b5bd99ad899ba9e14592292f517c75";
    hash = "sha256-+YCjcA0leL27uqoBg7OU30ZFVajQSrQroGFe08V9ihU=";
  };

  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/supertux-advance
    cp -r . $out/share/supertux-advance/
    # Brux runs a game from its folder. The game writes its config and
    # saves to the player's own folder (PhysFS's pref dir,
    # ~/.local/share/sta/supertux-advance), not next to itself.
    makeWrapper ${lib.getExe brux} $out/bin/supertux-advance \
      --chdir $out/share/supertux-advance --add-flags game.brx
    runHook postInstall
  '';

  passthru = { inherit brux; };

  meta = {
    description = "2D platformer in the style of SuperTux, on the Brux engine";
    homepage = "https://github.com/KelvinShadewing/supertux-advance";
    license = lib.licenses.agpl3Only;
    platforms = lib.platforms.linux;
    mainProgram = "supertux-advance";
  };
}
