# The `famidrive` module: everything that makes a box a FamiDrive.
# Hosts only set options declared here; they never reach into submodules.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
in
{
  imports = [
    ./session.nix
    ./frontend.nix
    ./emulators.nix
    ./romm-agent.nix
    ./generators.nix
    ./pc-saves.nix
    ./online.nix
    ./media.nix
    ./endpoints.nix
    ./controllers.nix
  ];

  options.famidrive = {
    enable = mkEnableOption "FamiDrive";

    user = mkOption {
      type = types.str;
      default = "famidrive";
      description = ''
        Local Linux account the session runs as. Separate from `owner` on
        purpose: every box can use the same local user, but each belongs to
        a different person.
      '';
    };

    owner = mkOption {
      type = types.str;
      example = "alice";
      description = ''
        RomM user this box belongs to. Everything that touches save data
        follows from it: the RomM Client API Token is issued by this user,
        the box registers as one of this user's RomM devices, and PC save
        folders pair only with this user's. One owner, many boxes share
        saves; different owners never do (multi-box.md "Per-user saves").
      '';
    };

    lanes = mkOption {
      type = types.listOf (types.enum [ "roms" "steam" "gog" "minecraft" ]);
      default = [ "roms" ];
      description = ''
        Which launch lanes this box carries. An emulation-only box is
        `[ "roms" ]` and skips Steam/Proton/gogdl/Prism entirely.
      '';
    };

    romm = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = ''
          Pull the library, firmware and console saves from RomM. Off for a
          box whose ROMs are already on local disk (`localRoms`) while the
          RomM agent is unproven: saves then stay local, exactly like before
          FamiDrive. Also gates the per-box sops secret, so a box with this
          off needs no sops setup at all.
        '';
      };

      url = mkOption {
        type = types.str;
        default = config.famidrive.endpoints.romm;
        description = "RomM base URL. Reached over HTTPS through Traefik from anywhere.";
      };

      collection = mkOption {
        type = types.nullOr types.str;
        default = null;   # the whole library (every platform this box has a system for)
        example = "Living Room";
        description = ''
          RomM collection this box mirrors locally, or null for everything.
          What a box carries is managed in RomM's web UI, not here.
        '';
      };

      tokenFile = mkOption {
        type = types.path;
        default = config.sops.secrets."romm-token".path;
        description = "Client API Token (rmm_...) issued by `owner`, decrypted by sops-nix.";
      };

      firmwarePlatforms = mkOption {
        type = types.listOf types.str;
        default = lib.unique (lib.filter (s: s != null)
          (lib.mapAttrsToList (_: s: s.rommPlatform) config.famidrive.systems));
        defaultText = "every RomM platform this box has a system for";
        description = "RomM platform slugs whose firmware gets pulled. A platform with none in RomM costs one empty request.";
      };
    };

    # ROMs that already live on this box, outside dataDir: system -> folder.
    # Each becomes a symlink at dataDir/roms/<system>, so ES-DE and
    # famidrive-launch can't tell them from pulled ones. This is how a box that
    # predates FamiDrive keeps its library without downloading it again.
    localRoms = mkOption {
      type = types.attrsOf types.str;
      default = { };
      example = { gc = "/srv/roms/gamecube"; };
    };

    # Per-owner emulator profile IDs. Xenia's is derived from `owner`, never
    # set by hand: if each box invented its own, one owner's saves wouldn't
    # line up across their boxes (roms.md "Mapping saves to games").
    identity = {
      # Revised 2026-10-05: the Switch emulator is Eden, not Ryubing. Eden
      # keeps profiles in a binary profiles.dat, so the ID isn't derived and
      # seeded the way Ryubing's Profiles.json was going to be. It's the
      # profile Eden already uses on the owner's first box, set by hand,
      # and seeding it onto later boxes is an open question in roms.md.
      edenProfileId = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "Eden profile whose saves sync with RomM. Required before Switch save sync.";
      };
      xeniaXuid = mkOption {
        type = types.str;
        readOnly = true;
        # Offline profiles use the E0... range. VERIFY against the chosen Xenia fork.
        default = lib.toUpper ("E0" + builtins.substring 0 14 (builtins.hashString "sha256" "famidrive-xenia:${config.famidrive.owner}"));
      };
    };

    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/famidrive";
      description = "Local library root: pulled ROMs, firmware, generator placeholders.";
    };
  };

  config = lib.mkIf config.famidrive.enable {
    # Steam, the Xbox controller driver and others are unfree.
    nixpkgs.config.allowUnfree = true;

    # Newest stable kernel (Decided 2026-10-05): display and GPU support
    # moves fast (HDMI 2.1 for AMD landed in 7.2), and the kernel is cheap to
    # roll back from the boot menu. A host can still pin its own.
    boot.kernelPackages = lib.mkDefault pkgs.linuxPackages_latest;
    nix.settings.experimental-features = [ "nix-command" "flakes" ];

    users.users.${config.famidrive.user} = {
      isNormalUser = true;
      extraGroups = [ "input" "video" "audio" ];
    };

    # Per-box secrets. Each host points sops.defaultSopsFile at its own file.
    sops.secrets."romm-token" = lib.mkIf config.famidrive.romm.enable {
      owner = config.famidrive.user;
    };

    systemd.tmpfiles.rules = [
      "d ${config.famidrive.dataDir} 0755 ${config.famidrive.user} users -"
      "d ${config.famidrive.dataDir}/roms 0755 ${config.famidrive.user} users -"
      "d ${config.famidrive.dataDir}/firmware 0750 ${config.famidrive.user} users -"
    ] ++ lib.mapAttrsToList (system: dir:
      "L+ ${config.famidrive.dataDir}/roms/${system} - - - - ${dir}"
    ) config.famidrive.localRoms;

    home-manager.useGlobalPkgs = true;
    home-manager.users.${config.famidrive.user}.home.stateVersion = "26.05";

    # Remote management baseline (remote-management.md).
    services.openssh.enable = true;
  };
}
