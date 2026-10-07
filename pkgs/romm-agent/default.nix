# The agent shells out to a few tools for local game-ID derivation and
# firmware installs (roms.md "Mapping saves to games"), so they're baked
# into its PATH here, not left to whoever calls it (systemd or famidrive-launch).
{ writers, python3Packages, symlinkJoin, makeWrapper, lib, dolphin-emu, _7zz, rpcs3 }:

let
  agent = writers.writePython3Bin "romm-agent" {
    libraries = [ python3Packages.requests python3Packages.cryptography ];   # cryptography: Switch NCA headers
    flakeIgnore = [ "E501" "E127" "E128" "W503" "W504" ];   # line-length + continuation style only
  } (builtins.readFile ./romm_agent.py);
in
symlinkJoin {
  name = "romm-agent";
  paths = [ agent ];
  nativeBuildInputs = [ makeWrapper ];
  postBuild = ''
    wrapProgram $out/bin/romm-agent \
      --prefix PATH : ${lib.makeBinPath [
        dolphin-emu   # dolphin-tool: GC/Wii game IDs from any disc format (VERIFY it's in this output)
        _7zz          # 7zz: pull SYSTEM.CNF / PARAM.SFO out of PS2/PS3 ISOs
        rpcs3         # rpcs3 --installfw
      ]}
  '';
}
