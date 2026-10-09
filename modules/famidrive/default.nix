# The `famidrive` module: everything that makes a box a FamiDrive.
# Hosts only set options declared here; they never reach into submodules.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.famidrive;

  playerModule = { name, config, ... }: {
    options = {
      user = mkOption {
        type = types.str;
        default = name;
        description = "Their Linux account. Made if it doesn't exist yet.";
      };
      displayName = mkOption {
        type = types.str;
        default = lib.toUpper (lib.substring 0 1 name) + lib.substring 1 (-1) name;
        defaultText = lib.literalMD "the name, capitalized";
        description = "What the \"Who's playing?\" screen calls them.";
      };
      owner = mkOption {
        type = types.str;
        default = name;
        description = ''
          Their RomM username. Their token is issued by this user, the box
          registers as one of this user's RomM devices, and their saves go
          up under it. One owner across several boxes shares saves;
          different owners never do (multi-box.md "Per-user saves").
        '';
      };
      romm.tokenFile = mkOption {
        type = types.nullOr types.path;
        default = null;
        defaultText = lib.literalMD "their sops secret, `romm-token-<name>`";
        description = "Their RomM Client API Token (rmm_...), decrypted by sops-nix.";
      };
      # Revised 2026-10-06: no longer needed by hand. A player's new Eden
      # gets a profile from the RomM agent before its first start, with an
      # ID derived from `owner`; an Eden that already has one is read
      # (profiles.dat, and the user Eden runs games as). Saves go to RomM
      # without the ID and unpack under each box's own, so the same player
      # can have different IDs on different boxes.
      edenProfileId = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "63CA1C4C81D775E24288780D17344942";
        description = ''
          The Eden profile whose saves sync with RomM, by its save folder's
          name. Usually left unset: FamiDrive uses the one Eden runs games
          as. For an Eden with old saves spread over several profiles, to
          say which one is real.
        '';
      };
      # Xenia's is derived from `owner`, never set by hand: if each box
      # invented its own, one owner's saves wouldn't line up across their
      # boxes (roms.md "Mapping saves to games").
      xeniaXuid = mkOption {
        type = types.str;
        readOnly = true;
        internal = true;
        # Offline profiles use the E0... range. VERIFY against the chosen Xenia fork.
        default = lib.toUpper ("E0" + builtins.substring 0 14 (builtins.hashString "sha256" "famidrive-xenia:${config.owner}"));
      };
    };
  };

  # What the rest of the module reads for each player. `roms` is their
  # own view of the library: the shared systems linked in from dataDir,
  # next to their own Steam, Minecraft and Settings entries.
  withPaths = p: p // rec {
    home = "/home/${p.user}";
    roms = "${home}/.local/share/famidrive/roms";
    nickname = p.owner;
  };

  players = lib.mapAttrs (name: p: withPaths (p // {
    name = name;
    isGuest = false;
    tokenFile =
      if p.romm.tokenFile != null then p.romm.tokenFile
      else if cfg.romm.enable then config.sops.secrets."romm-token-${name}".path
      else null;
  })) cfg.players;

  guest = withPaths {
    name = "guest";
    user = "guest";
    displayName = "Guest";
    owner = "guest";
    tokenFile = null;   # no RomM: the guest's saves stay on this box
    edenProfileId = null;
    xeniaXuid = "E000000000000000";
    isGuest = true;
  } // { nickname = "Guest"; };
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
    ./minecraft.nix
    ./valheim.nix
    ./clonehero.nix
    ./yarg.nix
    ./osu.nix
    ./tux.nix
    ./spacecadet.nix
    ./miis.nix
    ./ryujinx.nix
    ./gpu.nix
    ./boot.nix
    ./overlays.nix
    ./retroachievements.nix
    ./settings.nix
    (lib.mkRemovedOptionModule [ "famidrive" "user" ] "Each player is listed in famidrive.players instead: famidrive.players.<name>.user is their Linux account.")
    (lib.mkRemovedOptionModule [ "famidrive" "owner" ] "Each player is listed in famidrive.players instead: famidrive.players.<name>.owner is their RomM username.")
    (lib.mkRemovedOptionModule [ "famidrive" "romm" "tokenFile" ] "Each player has their own: famidrive.players.<name>.romm.tokenFile.")
    (lib.mkRemovedOptionModule [ "famidrive" "identity" "edenProfileId" ] "Each player has their own: famidrive.players.<name>.edenProfileId.")
  ];

  options.famidrive = {
    enable = mkEnableOption "FamiDrive";

    players = mkOption {
      type = types.attrsOf (types.submodule playerModule);
      default = { };
      example = lib.literalExpression ''
        {
          alice = { };                              # Linux account and RomM user "alice"
          sam = { displayName = "Sammy"; };
        }
      '';
      description = ''
        Who plays on this box. Each player is their own Linux account and
        their own RomM user, so each has their own Steam login, saves,
        RetroAchievements and ES-DE favorites, while the ROMs, firmware and
        controller setup are the box's and shared. With more than one
        player (the guest counts), the box starts on a "Who's playing?"
        screen, and quitting ES-DE goes back to it.
      '';
    };

    primaryPlayer = mkOption {
      type = types.nullOr types.str;
      default = if lib.length (lib.attrNames config.famidrive.players) == 1
        then lib.head (lib.attrNames config.famidrive.players) else null;
      defaultText = lib.literalMD "the only player, when there's one";
      example = "alice";
      description = ''
        The box's main player. Their RomM token is the one the shared
        library and firmware are pulled with, and it's whose PC saves sync
        (`pcSaves`). Needed once there's more than one player.
      '';
    };

    guest.enable = mkEnableOption ''
      a Guest player on the "Who's playing?" screen, for anyone without
      their own: every game on the box, their own saves kept on this box
      only (no RomM), and Steam if they sign in to theirs'';

    lanes = mkOption {
      # "gog" stays in the enum only so the assertion below can say what
      # replaced it; the lane itself was never finished.
      type = types.listOf (types.enum [ "roms" "steam" "heroic" "gog" "minecraft" ]);
      default = [ "roms" ];
      description = ''
        Which launch lanes this box carries:

        - `"roms"`: the consoles, through their emulators.
        - `"steam"`: each player's Steam library.
        - `"heroic"`: each player's GOG, Epic Games Store and Amazon
          Games libraries, through Heroic Games Launcher. Each store is
          its own system in the menu.
        - `"minecraft"`: Prism Launcher's instances, in Ports.

        An emulation-only box is `[ "roms" ]` and skips Steam, Proton,
        Heroic and Prism entirely.
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
        defaultText = lib.literalExpression "config.famidrive.endpoints.romm";
        description = "The RomM server this box uses. Set `endpoints.romm` instead; this is for a box that uses a different RomM than the rest.";
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

      platforms = mkOption {
        type = types.nullOr (types.listOf types.str);
        default = null;
        example = [ "ngc" "wii" ];
        description = ''
          RomM platforms (their slugs, as in RomM's URLs) this box mirrors,
          or null for every platform it has a system for. Works with
          `collection`: both set, a box gets that collection's games on
          these platforms.
        '';
      };

      saveHistory = mkOption {
        type = types.ints.between 1 100;
        default = 3;
        description = ''
          Versions of each game's save RomM keeps for a player: every push
          adds one, and RomM deletes the oldest beyond this. Only FamiDrive's
          own save slots; saves uploaded to RomM by hand are left alone.
        '';
      };

      apps = mkOption {
        type = types.attrsOf (types.attrsOf types.anything);
        default = { };
        internal = true;
        description = ''
          Apps that aren't ROMs but keep saves in RomM, under an entry added
          to RomM by hand (Clone Hero's scores): name -> { title, rom,
          emulator, saveLayout }, where title is the name ES-DE shows it by,
          which toasts use too. Set by the app's module.
        '';
      };

      firmwarePlatforms = mkOption {
        type = types.listOf types.str;
        default = lib.unique (lib.filter (s: s != null)
          (lib.mapAttrsToList (_: s: s.rommPlatform) config.famidrive.systems));
        defaultText = lib.literalMD "every RomM platform this box has a system for";
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
      description = ''
        ROM folders already on this box, by system. Every player has to be
        able to read them: group `famidrive` (every player is in it) with
        read access all the way down, or readable by everyone.
      '';
    };

    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/famidrive";
      description = "The shared library: pulled ROMs, firmware, cover art. Every player reads it; only the library pull writes it.";
    };

    # Every player, the guest included, as the rest of the module sees them.
    allPlayers = mkOption {
      type = types.attrsOf types.attrs;
      internal = true;
      readOnly = true;
    };

    # Home-manager config every player gets (emulator settings, ES-DE,
    # controllers, ...). Modules add to it instead of naming a user; each
    # player's is given `famidrivePlayer`, that player's entry in allPlayers.
    playerHome = mkOption {
      type = types.deferredModule;
      internal = true;
      default = { };
    };
  };

  config = lib.mkIf cfg.enable {
    # Steam, the Xbox controller driver and others are unfree.
    nixpkgs.config.allowUnfree = true;

    # Newest stable kernel (Decided 2026-10-05): display and GPU support
    # moves fast (HDMI 2.1 for AMD landed in 7.2), and the kernel is cheap to
    # roll back from the boot menu. A host can still pin its own.
    boot.kernelPackages = lib.mkDefault pkgs.linuxPackages_latest;
    nix.settings.experimental-features = [ "nix-command" "flakes" ];

    # Housekeeping, so the system disk doesn't fill up with old builds.
    # Defaults: a host sets any of these to change them. Found on the first
    # box 2026-10-06: the system disk reached 99% with every generation
    # since the move kept.
    nix.gc = {
      automatic = lib.mkDefault true;
      dates = lib.mkDefault "weekly";
      # Two weeks of generations to roll back to, and nothing older.
      options = lib.mkDefault "--delete-older-than 14d";
      persistent = lib.mkDefault true;   # catch up after the box was off
    };
    # Identical files in the store stored once.
    nix.optimise.automatic = lib.mkDefault true;
    # The boot menu's list of generations, whichever loader the host uses.
    boot.loader.systemd-boot.configurationLimit = lib.mkDefault 10;
    boot.loader.grub.configurationLimit = lib.mkDefault 10;

    famidrive.allPlayers = players // lib.optionalAttrs cfg.guest.enable { guest = guest; };

    assertions = [{
      assertion = cfg.players != { };
      message = "famidrive.players: list at least one player (the box's main user).";
    } {
      assertion = cfg.primaryPlayer == null || cfg.players ? ${toString cfg.primaryPlayer};
      message = "famidrive.primaryPlayer: \"${toString cfg.primaryPlayer}\" isn't in famidrive.players.";
    } {
      assertion = !(cfg.guest.enable && cfg.players ? guest);
      message = "famidrive.players.guest: that name is the guest's (famidrive.guest.enable); pick another.";
    } {
      assertion = !(cfg.romm.enable && lib.elem "roms" cfg.lanes) || cfg.primaryPlayer != null;
      message = "famidrive.primaryPlayer: with more than one player, say whose RomM token pulls the library.";
    } {
      assertion = !(lib.elem "gog" cfg.lanes);
      message = "famidrive.lanes: \"gog\" is now \"heroic\", which brings GOG, the Epic Games Store and Amazon Games through Heroic Games Launcher.";
    }];

    # One Linux account per player. Group famidrive can read the shared
    # library; nobody but the library pull can change it.
    users.groups.famidrive = { };
    users.users = lib.mapAttrs' (_: p: lib.nameValuePair p.user {
      isNormalUser = true;
      extraGroups = [ "input" "video" "audio" "famidrive" ];
    }) cfg.allPlayers // {
      # Owns the shared library: the RomM pull runs as it, with the primary
      # player's token handed over by systemd (romm-agent.nix).
      famidrive-library = {
        isSystemUser = true;
        group = "famidrive";
        home = cfg.dataDir;
      };
    };

    # Per-player secrets. Each host points sops.defaultSopsFile at its own file.
    sops.secrets = lib.mkIf cfg.romm.enable (lib.mapAttrs' (name: p:
      lib.nameValuePair "romm-token-${name}" { owner = p.user; }
    ) (lib.filterAttrs (_: p: p.romm.tokenFile == null) cfg.players));

    # The shared library. Players read it (group famidrive); saves never
    # live here, they're in each player's home.
    systemd.tmpfiles.rules = [
      "d ${cfg.dataDir} 0755 famidrive-library famidrive -"
      "d ${cfg.dataDir}/roms 0755 famidrive-library famidrive -"
      "d ${cfg.dataDir}/firmware 0750 famidrive-library famidrive -"
      "d ${cfg.dataDir}/media 0755 famidrive-library famidrive -"
      "d ${cfg.dataDir}/textures 0755 famidrive-library famidrive -"
      "d ${cfg.dataDir}/mods 0755 famidrive-library famidrive -"
    ] ++ lib.mapAttrsToList (system: dir:
      "L+ ${cfg.dataDir}/roms/${system} - - - - ${dir}"
    ) cfg.localRoms;

    home-manager.useGlobalPkgs = true;
    home-manager.users = lib.mapAttrs' (_: p: lib.nameValuePair p.user {
      imports = [ cfg.playerHome ];
      _module.args.famidrivePlayer = p;
      home.stateVersion = "26.05";
    }) cfg.allPlayers;

    # Remote management baseline (remote-management.md).
    services.openssh.enable = true;
  };
}
