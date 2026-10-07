# The box's graphics card. A build can't look at the hardware it will
# run on, so the driver can't be picked by looking; but AMD and Intel
# cards both use Mesa, which every box has, so "auto" drives both and
# only Nvidia, whose driver is proprietary and built into the system, has
# to be chosen. famidrive-hardware lists a box's cards, and a check at
# boot says so in the journal when an Nvidia card has no driver.
#
# Tested: AMD (the first box, Radeon RX 7900 XTX). Intel should just
# work (Mesa, the same as AMD). Nvidia is untested: help wanted.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  amdOrIntel = lib.elem cfg.gpu [ "auto" "amd" "intel" ];
in
{
  options.famidrive.gpu = mkOption {
    type = types.enum [ "auto" "amd" "intel" "nvidia" ];
    default = "auto";
    description = ''
      The box's graphics card, for its drivers. `famidrive-hardware` on
      the box lists its cards and the setting to use.

      - `"auto"` (the default): AMD and Intel cards, both through Mesa,
        plus Intel's video decoder for Kodi. Nothing to choose for either.
      - `"amd"`, `"intel"`: the same as `"auto"`, said outright.
        AMD is what FamiDrive is tested on; Intel should just work.
      - `"nvidia"`: Nvidia's own driver (its open kernel module, for RTX
        20-series cards and newer), with kernel modesetting, which
        gamescope needs, its video decoder, and the long-term kernel,
        which Nvidia's driver keeps up with. Untested: results welcome
        in COMPATIBILITY.md.
    '';
  };

  config = lib.mkIf cfg.enable (lib.mkMerge [
    (lib.mkIf amdOrIntel {
      # Intel's VA-API decoder (Kodi's hardware video decoding on Intel;
      # AMD's is in Mesa). Only loaded on an Intel card.
      hardware.graphics.extraPackages = [ pkgs.intel-media-driver pkgs.vpl-gpu-rt ];
    })

    (lib.mkIf (cfg.gpu == "nvidia") {
      services.xserver.videoDrivers = [ "nvidia" ];
      hardware.nvidia = {
        open = true;
        modesetting.enable = true;
        package = config.boot.kernelPackages.nvidiaPackages.stable;
      };
      hardware.graphics.extraPackages = [ pkgs.nvidia-vaapi-driver ];
      environment.sessionVariables.LIBVA_DRIVER_NAME = "nvidia";
      # The long-term kernel, not the newest (default.nix): Nvidia's
      # driver can lag a brand-new kernel. A host can still pin its own.
      boot.kernelPackages = lib.mkOverride 999 pkgs.linuxPackages;
    })

    {
      environment.systemPackages = [ pkgs.famidrive-hardware ];
      # Says in the journal when the card and famidrive.gpu don't match
      # (an Nvidia card without its driver), with the line to set.
      systemd.services.famidrive-hardware-check = {
        description = "Check famidrive.gpu against the box's graphics cards";
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.famidrive-hardware}/bin/famidrive-hardware check ${cfg.gpu}";
        };
      };
    }
  ]);
}
