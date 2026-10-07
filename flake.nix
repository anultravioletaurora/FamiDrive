{
  description = "FamiDrive: a 10,000-in-1 Declarative System";

  inputs = {
    # The base system tracks the latest NixOS release: kernel, mesa, systemd,
    # Steam, greetd, gamescope only change when the flake moves to the next
    # release. Releases are supported for about seven months, so this line
    # moves twice a year (26.05 is supported until 2026-12-31; next is 26.11).
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # Emulators move faster than releases do, so the few that need to stay
    # current come from unstable through the overlay below. Nothing else does.
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";   # must match nixpkgs
      inputs.nixpkgs.follows = "nixpkgs";
    };

    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # The gamescope session is built from plain nixpkgs (base-os.md).
  };

  outputs = { self, nixpkgs, nixpkgs-unstable, home-manager, sops-nix, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ self.overlays.default ];
      };
    in
    {
      # Packages nixpkgs doesn't carry (or doesn't carry the variant we need),
      # plus this project's own scripts.
      overlays.default = final: prev:
      let
        unstable = import nixpkgs-unstable {
          inherit (final.stdenv.hostPlatform) system;
          config.allowUnfree = true;
        };
      in
      {
        # From unstable, on purpose. Each of these is a lot newer there than
        # in the release (as of 2026-10-05: eden 0.2.1 vs 0.1.1, rpcs3 Aug vs
        # Apr snapshot, jellyfin-mpv-shim 3.0 vs 2.9). They still use the
        # release's mesa through /run/opengl-driver, so if a Vulkan emulator
        # misbehaves, a mesa mismatch is the first thing to suspect.
        # Dolphin and PCSX2 stay on the release: same versions in both, and
        # Dolphin's maintainers backport to stable for netplay compatibility.
        eden = unstable.eden;
        rpcs3 = unstable.rpcs3;

        es-de = final.callPackage ./pkgs/es-de { };
        tcli = final.callPackage ./pkgs/tcli { };
        xenia-netplay = final.callPackage ./pkgs/xenia-netplay { };
        gamescope-fg = final.callPackage ./pkgs/gamescope-fg { };
        romm-agent = final.callPackage ./pkgs/romm-agent { };
        famidrive-generators = final.callPackage ./pkgs/famidrive-generators { };
        famidrive-quit = final.callPackage ./pkgs/famidrive-quit { };
        famidrive-steam-config = final.callPackage ./pkgs/famidrive-steam-config { };
        famidrive-prism = final.callPackage ./pkgs/famidrive-prism { };
        famidrive-valheim = final.callPackage ./pkgs/famidrive-valheim { };
        famidrive-status = final.callPackage ./pkgs/famidrive-status { };
        famidrive-picker = final.callPackage ./pkgs/famidrive-picker { };
        famidrive-end-session = final.callPackage ./pkgs/famidrive-end-session { };
        famidrive-clonehero = final.callPackage ./pkgs/famidrive-clonehero { };
        famidrive-kodi = final.callPackage ./pkgs/famidrive-kodi { };
        famidrive-ryujinx = final.callPackage ./pkgs/famidrive-ryujinx { };
        famidrive-hardware = final.callPackage ./pkgs/famidrive-hardware { };
        famidrive-toast = final.callPackage ./pkgs/famidrive-toast { };

        # libmpv with SDL2 gamepad input compiled in. nixpkgs builds mpv
        # with sdl2Support = false, and without it the shim's gamepad
        # setting silently does nothing (media.md "On the box").
        mpv-gamepad = unstable.mpv-unwrapped.override { sdl2Support = true; };

        # Jellyfin MPV Shim 3.1.0, built on unstable (the release has 2.9,
        # from before v3's library browser and controller support; unstable
        # has 3.0.0; 3.1.0 adds the fontconfig fix NixOS needs), with its
        # Python mpv binding pointed at mpv-gamepad. On Linux the shim plays
        # through libmpv in-process.
        jellyfin-mpv-shim =
          let
            python = unstable.python3.override {
              self = python;
              packageOverrides = pyFinal: pyPrev: {
                mpv = pyPrev.mpv.override { mpv = final.mpv-gamepad; };
              };
            };
          in
          (unstable.jellyfin-mpv-shim.override { python3Packages = python.pkgs; })
          .overridePythonAttrs (old: rec {
            version = "3.1.0";
            src = unstable.fetchPypi {
              pname = "jellyfin_mpv_shim";
              inherit version;
              hash = "sha256-ad6ZokTy8vxAVrgopK+DK9WQqOlEKssigA++68vuid4=";
            };
            # 3.1.0 made notify_updates a tri-state, so nixpkgs'
            # `notify_updates: bool = True` substitution no longer matches
            # and --replace-fail would break the build. check_updates is
            # still a plain bool. Keep the pyproject renames.
            #
            # The sign-in form starts with an empty Server URL. FamiDrive
            # fills it from FAMIDRIVE_JELLYFIN_SERVER (media.nix), so a new box
            # only needs "Use Quick Connect" and a code. Both places the form
            # is reset: app.py (first run) and auth.py (every Add Server).
            postPatch = ''
              substituteInPlace jellyfin_mpv_shim/mpvtk_browser/app.py jellyfin_mpv_shim/mpvtk_browser/auth.py \
                --replace-fail 'self._login = {"server": "",' \
                  'self._login = {"server": __import__("os").environ.get("FAMIDRIVE_JELLYFIN_SERVER", ""),'
              substituteInPlace jellyfin_mpv_shim/conf.py \
                --replace-fail "check_updates: bool = True" "check_updates: bool = False"
              substituteInPlace pyproject.toml \
                --replace-fail "python-mpv" "mpv" \
                --replace-fail "mpv-jsonipc" "python_mpv_jsonipc"
            '';
          });
      };

      packages.${system} = {
        inherit (pkgs) es-de tcli xenia-netplay gamescope-fg romm-agent famidrive-generators famidrive-quit famidrive-steam-config famidrive-prism famidrive-status famidrive-valheim famidrive-picker famidrive-end-session famidrive-clonehero famidrive-kodi famidrive-ryujinx famidrive-hardware famidrive-toast
          mpv-gamepad jellyfin-mpv-shim;
      };

      # `nix flake check`: unit tests, example boxes, and every package
      # built (tests/default.nix). Run on each pull request.
      # tcli is a placeholder (no source yet) until Valheim's mod profiles
      # need it, so it's left out.
      checks.${system} = import ./tests { inherit self nixpkgs pkgs system; }
        // nixpkgs.lib.mapAttrs' (name: p: nixpkgs.lib.nameValuePair "pkg-${name}" p)
          (removeAttrs self.packages.${system} [ "tcli" ]);

      # What a box imports. Brings everything the famidrive module needs
      # (the overlay, home-manager, sops-nix), so a host only adds its own
      # file. Hosts live in their own private flake, not in this repo:
      # they hold the box's hardware, server addresses and secrets.
      nixosModules.default = {
        imports = [
          home-manager.nixosModules.home-manager
          sops-nix.nixosModules.sops
          self.nixosModules.famidrive
        ];
        nixpkgs.overlays = [ self.overlays.default ];
      };

      # Just the module, for a host that brings its own home-manager and sops-nix.
      nixosModules.famidrive = import ./modules/famidrive;

      # A whole box from one host module, on this flake's own nixpkgs, so every
      # box built from the same revision gets the same emulator builds.
      # That's a hard requirement for lockstep netplay (roms.md "Online
      # play"), not just tidiness.
      #
      #   nixosConfigurations.tv = famidrive.lib.mkBox ./configuration.nix;
      lib.mkBox = hostModule: nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ self.nixosModules.default hostModule ];
      };
    };
}
