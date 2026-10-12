# A boot screen instead of the kernel's and systemd's console text, from
# just after the boot menu (where a generation is still picked) until the
# TV's session takes over. Plymouth draws it; a FamiDrive boot animation
# later is just a Plymouth theme (frames or a script).
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  splash = cfg.boot.splash;
  # Plymouth only has pre-rendered images for whole numbers 1-4; round
  # and clamp famidrive.display.scale (a Chromium scale factor too) into that.
  plymouthScale = lib.max 1 (lib.min 4 (builtins.floor (cfg.display.scale * 1.0 + 0.5)));
in
{
  imports = [
    (lib.mkRemovedOptionModule [ "famidrive" "boot" "splash" "scale" ] "Shared with the Electron UI scale now: famidrive.display.scale.")
  ];

  options.famidrive.boot.splash = {
    enable = mkEnableOption "a boot screen (Plymouth) in place of console text while the box starts" // {
      default = true;
    };

    theme = mkOption {
      type = types.str;
      default = "bgrt";
      example = "spinner";
      description = ''
        The Plymouth theme. `"bgrt"` (the default) shows the computer's
        own logo with a spinner, when its firmware provides a logo (not
        every PC's does; the spinner alone shows otherwise). `"spinner"`
        is the same without the logo. A theme from another package needs it in
        `themePackages` too.
      '';
    };

    earlyGraphics = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Load the graphics driver in the initrd (by `famidrive.gpu`: AMD,
        Intel, or both for `"auto"`), so the boot screen is drawn at the
        TV's own resolution from the start. Without it, the boot screen
        starts on the firmware's low-resolution framebuffer, scaled up
        by `famidrive.display.scale`, until the driver loads from the
        system disk. Found on both test boxes 2026-10-10: a blocky
        spinner for the first 13 seconds. Costs a larger initrd (the
        driver and its firmware).
      '';
    };

    themePackages = mkOption {
      type = types.listOf types.package;
      default = [ ];
      example = lib.literalExpression ''[ (pkgs.adi1090x-plymouth-themes.override { selected_themes = [ "rings" ]; }) ]'';
      description = "Packages with more Plymouth themes, for `theme`.";
    };
  };

  config = lib.mkIf (cfg.enable && splash.enable) {
    boot.plymouth = {
      enable = true;
      inherit (splash) theme themePackages;
      extraConfig = "DeviceScale=${toString plymouthScale}";
    };
    # Plymouth from the start of boot, in the initrd, not halfway
    # through; a host with an initrd of its own can still say otherwise.
    boot.initrd.systemd.enable = lib.mkDefault true;
    # The graphics driver there too, so that start is at the TV's
    # resolution (earlyGraphics). Nvidia's driver isn't loaded early here.
    boot.initrd.kernelModules = lib.mkIf splash.earlyGraphics (
      lib.optionals (lib.elem cfg.gpu [ "auto" "amd" ]) [ "amdgpu" ]
      ++ lib.optionals (lib.elem cfg.gpu [ "auto" "intel" ]) [ "i915" ]);
    hardware.amdgpu.initrd.enable = lib.mkIf (splash.earlyGraphics && lib.elem cfg.gpu [ "auto" "amd" ]) true;
    # No text over the splash: the kernel's messages, systemd's status
    # lines and udev's. A failed boot still shows them, and Esc on the
    # splash shows them too.
    boot.kernelParams = [ "quiet" "splash" "udev.log_priority=3" "rd.udev.log_level=3" "systemd.show_status=auto" ];
    boot.consoleLogLevel = lib.mkDefault 3;
    boot.initrd.verbose = false;
  };
}
