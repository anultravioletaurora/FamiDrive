{ lib, writers, gst_all_1, pipewire, ffmpeg-headless }:

let
  # Every plugin the pipeline names: pipewiresrc (pipewire), the GL
  # elements, videoconvert and the rest (base), pulsesrc, mp4mux and
  # aacparse (good), h264parse and the va and nvcodec encoders (bad),
  # x264enc (ugly), avenc_aac (libav), and gst-vaapi. pw-dump finds
  # gamescope's stream and its size. ffmpeg takes each recording's still
  # for ES-DE.
  plugins = with gst_all_1; [
    gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
    gst-libav gst-vaapi pipewire
  ];
in
writers.writePython3Bin "famidrive-record" {
  flakeIgnore = [ "E501" ];   # line-length only
} (lib.replaceStrings [ "@gstLaunch@" "@gstInspect@" "@gstPlugins@" "@pwDump@" "@ffmpeg@" ] [
  "${gst_all_1.gstreamer.bin}/bin/gst-launch-1.0"
  "${gst_all_1.gstreamer.bin}/bin/gst-inspect-1.0"
  (lib.makeSearchPathOutput "lib" "lib/gstreamer-1.0" plugins)
  "${pipewire}/bin/pw-dump"
  "${ffmpeg-headless}/bin/ffmpeg"
] (builtins.readFile ./famidrive_record.py))
