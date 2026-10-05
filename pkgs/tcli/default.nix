# Thunderstore's official CLI, used for Valheim/BepInEx mod profiles
# headlessly (remote-management.md). It's a .NET app; not in nixpkgs.
{ lib, buildDotnetModule, fetchFromGitHub, dotnetCorePackages }:

buildDotnetModule {
  pname = "tcli";
  version = "TODO";

  src = fetchFromGitHub {
    owner = "thunderstore-io";
    repo = "thunderstore-cli";
    rev = "TODO";
    hash = lib.fakeHash;
  };

  projectFile = "ThunderstoreCLI/ThunderstoreCLI.csproj";   # TODO: verify
  nugetDeps = ./deps.json;                                  # generate with fetch-deps
  dotnet-sdk = dotnetCorePackages.sdk_8_0;                  # TODO: match upstream target
  executables = [ "tcli" ];

  meta = {
    description = "Thunderstore command-line tool";
    homepage = "https://github.com/thunderstore-io/thunderstore-cli";
    mainProgram = "tcli";
  };
}
