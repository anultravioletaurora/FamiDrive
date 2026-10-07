{ writers }:

(writers.writePython3Bin "famidrive-ryujinx" {
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_ryujinx.py)).overrideAttrs (old: {
  # Ryubing 1.3.3's own Config.json as it first writes it (version 70),
  # with no controllers or game folders: what a player's Ryujinx starts
  # from, before FamiDrive's keys go on top. Newer Ryubing migrates it.
  passthru = (old.passthru or { }) // { defaultConfig = ./default-config.json; };
})
