# The box's graphics card. A build can't look at the hardware it will
# run on, so the driver can't be picked by looking; but AMD and Intel
# cards both use Mesa, which every box has, so "auto" drives both and
# only Nvidia, whose driver is proprietary and built into the system, has
# to be chosen. famidrive-hardware lists a box's cards, and a check at
# boot says so in the journal when an Nvidia card has no driver.
#
# Hybrid graphics (most laptops with an Nvidia card): the Intel or AMD
# card has every output, the TV's HDMI too, and the Nvidia card only
# renders. A build can't tell the two apart either, so each session asks
# famidrive-hardware: gamescope and ES-DE go on the card the TV is on,
# and with "nvidia", each game renders on the Nvidia card, which powers
# off again in the menu (session.nix, gamescope-fg).
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
        20-series and GTX 16-series cards and newer), with kernel
        modesetting, which gamescope needs, its video decoder, and the
        long-term kernel, which Nvidia's driver keeps up with. On a
        laptop, where the TV is on the Intel or AMD card and the Nvidia
        card has no screen of its own (hybrid graphics), games render on
        the Nvidia card and the other one shows them (PRIME render
        offload), while ES-DE stays on the other card and the Nvidia one
        powers off; each session works that out from the hardware.
        Untested: results welcome in docs/COMPATIBILITY.md.
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
      # Hybrid graphics: the Nvidia card powers off while nothing renders
      # on it (the menu, session.nix). The same as NixOS's
      # hardware.nvidia.powerManagement.finegrained, which needs each
      # box's PCI bus IDs written down; this needs none. The driver's own
      # default only does this for Ampere cards and newer. Found on a
      # hybrid laptop 2026-10-16 (T600, Turing): "Runtime D3 status:
      # Disabled by default", and the card's power/control stuck "on".
      # A card that drives a screen, or a desktop's, just stays on.
      boot.extraModprobeConfig = ''
        options nvidia NVreg_DynamicPowerManagement=0x02
      '';
      services.udev.extraRules = ''
        ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="auto"
        ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="auto"
        ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="on"
        ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="on"
      '';
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
