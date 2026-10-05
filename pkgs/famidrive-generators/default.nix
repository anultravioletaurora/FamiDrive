{ writers }:

writers.writePython3Bin "famidrive-generate" {
  flakeIgnore = [ "E501" "E127" "E128" "W503" "W504" ];   # line-length + continuation style only
} (builtins.readFile ./famidrive_generate.py)
