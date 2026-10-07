{ writers, python3Packages }:

writers.writePython3Bin "famidrive-toast" {
  libraries = [ python3Packages.pygame-ce python3Packages.xlib python3Packages.jeepney ];
  flakeIgnore = [ "E501" ];   # line-length only
} (builtins.readFile ./famidrive_toast.py)
