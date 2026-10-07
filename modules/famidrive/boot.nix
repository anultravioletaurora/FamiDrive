# A boot screen instead of the kernel's and systemd's console text, from
# just after the boot menu (where a generation is still picked) until the
# TV's session takes over. Plymouth draws it; a FamiDrive boot animation
# later is just a Plymouth theme (frames or a script).
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;
  splash = cfg.boot.splash;
in
{
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
        own logo, from its firmware, with a spinner; `"spinner"` is the
        same without the logo. A theme from another package needs it in
        `themePackages` too.
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
    };
    # Plymouth from the start of boot, in the initrd, not halfway
    # through; a host with an initrd of its own can still say otherwise.
    boot.initrd.systemd.enable = lib.mkDefault true;
    # No text over the splash: the kernel's messages, systemd's status
    # lines and udev's. A failed boot still shows them, and Esc on the
    # splash shows them too.
    boot.kernelParams = [ "quiet" "splash" "udev.log_priority=3" "rd.udev.log_level=3" "systemd.show_status=auto" ];
    boot.consoleLogLevel = lib.mkDefault 3;
    boot.initrd.verbose = false;
  };
}
