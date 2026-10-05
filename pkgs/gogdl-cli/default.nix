# Headless GOG client (pc-games.md). Not in nixpkgs.
{ lib, rustPlatform, fetchFromGitHub, pkg-config, openssl }:

rustPlatform.buildRustPackage {
  pname = "gogdl-cli";
  version = "unstable-TODO";

  src = fetchFromGitHub {
    owner = "fernandonr189";
    repo = "gogdl-cli";
    rev = "TODO";
    hash = lib.fakeHash;
  };

  cargoHash = lib.fakeHash;

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ openssl ];

  meta = {
    description = "Headless GOG downloader/launcher";
    homepage = "https://github.com/fernandonr189/gogdl-cli";
    mainProgram = "gogdl-cli";
  };
}
