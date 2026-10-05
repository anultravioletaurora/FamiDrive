# Xbox 360. Which Xenia fork to use is still open in roms.md (Canary vs
# Edge), and online play only exists on AdrianCassar's Netplay fork of
# Canary. Its Linux build state is unverified. Until that's settled this
# is a stub that evaluates fine and fails loudly at launch time. The
# community flake kuhree/flake-emulators is the other candidate source.
{ writeShellScriptBin }:

writeShellScriptBin "xenia_canary" ''
  echo "xenia: fork + Linux build not decided yet (roms.md open questions)" >&2
  exit 1
''
