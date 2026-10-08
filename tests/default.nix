# What `nix flake check` runs, on every pull request (.github/workflows).
#
#   - unit tests for FamiDrive's own Python tools, with no server, Steam
#     or TV: each one against made-up files in a temp folder
#   - example boxes, evaluated (not built: a whole box is many GB), with
#     checks on what the module made of them
#   - every package in the flake, built
#
# What needs real hardware or a real RomM (the session on a TV, games,
# controllers, save sync against a server) is tested on a box after merging.
{ self, nixpkgs, pkgs, system }:

let
  inherit (nixpkgs) lib;

  unit = name: script: python: pkgs.runCommand "test-${name}" { nativeBuildInputs = [ python ]; } ''
    export HOME=$TMPDIR
    python3 ${./. + "/${name}_test.py"} ${script}
    touch $out
  '';

  # A box from a host module, the way lib.mkBox builds one, plus what
  # every NixOS host needs that a test has no real value for.
  box = host: lib.nixosSystem {
    inherit system;
    modules = [
      self.nixosModules.default
      {
        networking.hostName = "test";
        fileSystems."/" = { device = "/dev/disk/by-label/nixos"; fsType = "ext4"; };
        boot.loader.systemd-boot.enable = true;
        system.stateVersion = "26.05";
        # The secrets file only matters when the box is built and run.
        sops.defaultSopsFile = "/nonexistent/secrets.yaml";
        sops.validateSopsFiles = false;
      }
      host
    ];
  };

  # Evaluates the whole box (every module, option and assertion) without
  # building it, then checks what came out. A failing check names itself.
  expect = name: host: checks:
    let
      c = (box host).config;
      failed = lib.filter (x: !x.ok) (checks c);
    in
    pkgs.runCommand "box-${name}" { } (
      if failed != [ ] then
        throw "box ${name}: ${lib.concatMapStringsSep "; " (x: x.what) failed}"
      else ''
        echo ${builtins.unsafeDiscardStringContext c.system.build.toplevel.drvPath} > $out
      '');
  check = what: ok: { inherit what ok; };
  etcJson = c: name: builtins.fromJSON c.environment.etc.${name}.text;

  # USAGE.md, from every option a box can set (not internal or hidden
  # ones). A value that can't be shown without a real box (a default
  # computed from another option) comes out as null.
  usageDoc =
    let
      safe = v: let r = builtins.tryEval (builtins.deepSeq v v); in if r.success then r.value else null;
      all = lib.optionAttrSetToDocList (box { }).options;
      hidden = map (o: o.name) (lib.filter (o: o.visible == false || o.internal) all);
      options = lib.filter (o: lib.hasPrefix "famidrive." o.name && !lib.hasInfix "._module." o.name
          && !lib.any (h: o.name == h || lib.hasPrefix "${h}." o.name) hidden)
        all;
      json = builtins.unsafeDiscardStringContext (builtins.toJSON (map (o: {
        inherit (o) name type readOnly;
        description = safe (o.description or null);
        hasDefault = o ? default;
        default = safe (o.default or null);
        example = safe (o.example or null);
      }) options));
    in
    pkgs.runCommand "USAGE.md" { nativeBuildInputs = [ pkgs.python3 ]; } ''
      python3 ${./usage_doc.py} ${builtins.toFile "famidrive-options.json" json} > $out
    '';
  # A family: two players with RomM, a guest, every lane.
  familyHost = {
    famidrive = {
      enable = true;
      lanes = [ "roms" "steam" "heroic" "minecraft" ];
      players = {
        alice.romm.tokenFile = "/run/secrets/alice-token";
        bob.owner = "bobby";
      };
      primaryPlayer = "alice";
      guest.enable = true;
      switch.ryujinx.games = [ "01006A800016E000" ];
      endpoints.romm = "https://romm.example.org";
      endpoints.jellyfin = "https://jellyfin.example.org";
      media.jellyfin.enable = true;
      media.kodi = {
        enable = true;
        sources.Movies = { path = "/media/movies"; content = "movies"; };
        addons = p: [ p.a4ksubtitles ];
      };
      minecraft.instances."Test Server" = {
        minecraft = "26.2";
        players = [ "alice" ];
        servers = [ { name = "Test"; address = "mc.example.org"; } ];
      };
      yarg.enable = true;
      cloneHero = {
        enable = true;
        songs."AFI - Miss Murder" = "05185565cb931978c11de73d3048206e";
        audioOffset = 200;
      };
      valheim.mods."ValheimModding-Jotunn-2.30.2" = "sha256-iq6S2ivg62ggzUz1fi9sHWrQ1zjUkVlm58PXqU6amw8=";
    };
    nix.gc.options = "--delete-older-than 30d";   # a host's own choice wins
  };
in
{
  # Every system's launch shell on the family box, through ShellCheck as
  # famidrive-launch's build does (writeShellApplication), without
  # building the box's emulators. Found 2026-10-07: a Ryujinx hook that
  # evaluated fine failed the first box's build.
  box-family-launch =
    let
      systems = (box familyHost).config.famidrive.systems;
      script = builtins.unsafeDiscardStringContext (''
        #!/usr/bin/env bash
        set -euo pipefail
        ROM="$1"; system="$2"; sync=""
        case "$ROM" in
      '' + lib.concatStrings (lib.mapAttrsToList (name: s: ''
          ${name})
            ${s.before}
            bash -c ${lib.escapeShellArg s.command}
            ${s.after}
            ;;
      '') systems) + ''
        esac
      '');
    in
    pkgs.runCommand "test-box-family-launch" { nativeBuildInputs = [ pkgs.shellcheck ]; } ''
      shellcheck -e SC2016 ${builtins.toFile "famidrive-launch.sh" script}
      ${lib.concatStrings (lib.mapAttrsToList (name: s: ''
        shellcheck -s bash -e SC2016 ${builtins.toFile "command-${name}.sh" (builtins.unsafeDiscardStringContext s.command)}
      '') systems)}
      touch $out
    '';

  # USAGE.md is generated: this fails when it's out of date.
  usage-doc = pkgs.runCommand "test-usage-doc" { passthru.doc = usageDoc; } ''
    if ! diff -u ${../USAGE.md} ${usageDoc}; then
      echo "USAGE.md is out of date. Regenerate it:" >&2
      echo "  nix build .#checks.x86_64-linux.usage-doc.doc && cp result USAGE.md" >&2
      exit 1
    fi
    touch $out
  '';

  romm-agent = unit "romm_agent" ../pkgs/romm-agent/romm_agent.py
    (pkgs.python3.withPackages (ps: [ ps.requests ps.cryptography ]));
  valheim = unit "valheim" ../pkgs/famidrive-valheim/famidrive_valheim.py pkgs.python3;
  steam-config = unit "steam_config" ../pkgs/famidrive-steam-config/famidrive_steam_config.py pkgs.python3;
  clonehero = unit "clonehero" ../pkgs/famidrive-clonehero/famidrive_clonehero.py pkgs.python3;
  kodi = unit "kodi" ../pkgs/famidrive-kodi/famidrive_kodi.py pkgs.python3;
  prism = unit "prism" ../pkgs/famidrive-prism/famidrive_prism.py pkgs.python3;
  ryujinx = unit "ryujinx" ../pkgs/famidrive-ryujinx/famidrive_ryujinx.py pkgs.python3;
  hardware = unit "hardware" ../pkgs/famidrive-hardware/famidrive_hardware.py pkgs.python3;

  # An Nvidia box: the proprietary driver, set up for gamescope.
  box-nvidia = expect "nvidia" {
    famidrive = {
      enable = true;
      players.alice = { };
      romm.enable = false;
      gpu = "nvidia";
    };
  } (c: [
    (check "Nvidia's driver, open kernel module, with modesetting for gamescope"
      (lib.elem "nvidia" c.services.xserver.videoDrivers && c.hardware.nvidia.open
        && c.hardware.nvidia.modesetting.enable))
    (check "the long-term kernel, which Nvidia's driver keeps up with"
      (c.boot.kernelPackages.kernel.version == pkgs.linuxPackages.kernel.version))
    (check "the boot check knows the box is set up for Nvidia"
      (lib.hasInfix "check nvidia" c.systemd.services.famidrive-hardware-check.serviceConfig.ExecStart))
  ]);
  generators = unit "generators" ../pkgs/famidrive-generators/famidrive_generate.py pkgs.python3;
  picker = unit "picker" ../pkgs/famidrive-picker/famidrive_picker.py
    (pkgs.python3.withPackages (ps: [ ps.pygame-ce ]));

  toast = unit "toast" ../pkgs/famidrive-toast/famidrive_toast.py pkgs.python3;
  pads = unit "pads" ../pkgs/famidrive-pads/famidrive_pads.py pkgs.python3;
  cheevos = unit "cheevos" ../pkgs/famidrive-cheevos/famidrive_cheevos.py
    (pkgs.python3.withPackages (ps: [ ps.requests ]));

  # Overlays: the box's positions, a player's own, MangoHud for one player.
  box-overlays = expect "overlays" {
    famidrive = {
      enable = true;
      romm.enable = false;
      guest.enable = true;
      overlays.toasts.position = "top-left";
      players.alice.overlays = {
        toasts = { position = "bottom-right"; hide = [ "progress" ]; };
        performance = { enable = true; position = "top-right"; };
      };
      players.bob = { };
    };
  } (c: let r = c.famidrive.overlays.resolved; in [
    (check "a player's own toast position and hidden kinds, the box's for the rest"
      (r.alice.toasts == { position = "bottom-right"; hide = [ "progress" ]; }
        && r.bob.toasts.position == "top-left" && r.guest.toasts.position == "top-left"))
    (check "MangoHud only for the player who turned it on, where they put it"
      (r.alice.performance.enable && !r.bob.performance.enable
        && lib.hasInfix "position=top-right" c.home-manager.users.alice.xdg.configFile."MangoHud/MangoHud.conf".text
        && !(c.home-manager.users.bob.xdg.configFile ? "MangoHud/MangoHud.conf")))
    (check "the toast daemon starts with every session"
      (lib.hasInfix "famidrive-toast daemon" c.famidrive.sessionSetup
        && lib.any (p: lib.getName p == "famidrive-toast") c.environment.systemPackages))
  ]);

  # RetroAchievements for one player of two: their secret, their session
  # signing in, and the unlock watcher beside every RetroArch game.
  box-retroachievements = expect "retroachievements" {
    famidrive = {
      enable = true;
      romm.enable = false;
      guest.enable = true;
      lanes = [ "roms" "steam" "heroic" ];   # Steam and Heroic: systems with no emulator
      players.alice.retroAchievements = { username = "alice-ra"; hardcore = true; };
      players.bob = { };
    };
  } (c: [
    (check "a password secret for the player with an account, owned by them, and none for the others"
      (c.sops.secrets ? "retroachievements-alice" && c.sops.secrets."retroachievements-alice".owner == "alice"
        && !(c.sops.secrets ? "retroachievements-bob") && !(c.sops.secrets ? "retroachievements-guest")))
    (check "their session signs in, nobody else's"
      (lib.hasInfix "alice) " c.famidrive.sessionSetup && lib.hasInfix "famidrive-cheevos setup" c.famidrive.sessionSetup
        && !(lib.hasInfix "bob) " c.famidrive.sessionSetup)))
    (check "PCSX2 starts without its setup wizard, with two pads mapped"
      (let a = c.home-manager.users.alice.home.activation.famidriveEmulators.data; in
        lib.hasInfix "SetupWizardIncomplete" a && lib.hasInfix "SDL-0/FaceSouth" a && lib.hasInfix "SDL-1/+RightTrigger" a))
    (check "RetroArch, PCSX2 and RPCS3 show nothing of their own over a game"
      (let a = c.home-manager.users.alice.home.activation.famidriveEmulators.data; in
        lib.hasInfix "video_font_enable" a && lib.hasInfix "cheevos_visibility_summary" a
          && lib.hasInfix "OsdMessagesPos" a && lib.hasInfix ''.Miscellaneous["Show trophy popups"] = false'' a))
    (check "the pads connected at launch are bound in Dolphin (gamepad ports) and Eden"
      (lib.hasInfix "famidrive-pads dolphin" c.famidrive.systems.gc.before
        && lib.hasInfix "famidrive-pads eden" c.famidrive.systems.switch.before
        && lib.hasInfix "famidrive-pads cemu" c.famidrive.systems.wiiu.before
        && lib.hasInfix "libSDL3.so.0" c.famidrive.systems.gc.before))
    (check "Cemu starts without its getting-started wizard"
      (lib.hasInfix "Cemu/settings.xml" c.home-manager.users.alice.home.activation.famidriveEmulators.data))
    (check "Dolphin's own on-screen messages off, for every player (toasts instead)"
      (lib.all (u: lib.hasInfix "OnScreenDisplayMessages" c.home-manager.users.${u}.home.activation.famidriveEmulators.data) [ "alice" "bob" "guest" ]))
    (check "Heroic sends desktop notifications (not taken for Steam Deck Game Mode); GOG games have the Comet watcher"
      (lib.hasInfix "XDG_CURRENT_DESKTOP=FamiDrive" c.famidrive.systems.gog.command
        && lib.hasInfix "XDG_CURRENT_DESKTOP=FamiDrive" c.famidrive.systems.settings.command
        && lib.hasInfix "watch-comet" c.famidrive.systems.gog.before
        && !(lib.hasInfix "watch-comet" c.famidrive.systems.epic.before)))
    (check "RetroArch and Dolphin games have the unlock watcher; Eden's don't"
      (lib.hasInfix "famidrive-cheevos" c.famidrive.systems.psx.before
        && lib.hasInfix "--log-file" c.famidrive.systems.n64.command
        && lib.hasInfix "dolphin.log" c.famidrive.systems.gc.before
        && lib.hasInfix "dolphin.log" c.famidrive.systems.wii.before
        && !(lib.hasInfix "famidrive-cheevos" c.famidrive.systems.switch.before)))
  ]);

  # One person, ROMs only, no RomM: the smallest box.
  box-one-player = expect "one-player" {
    famidrive = {
      enable = true;
      players.alice = { };
      romm.enable = false;
      yarg.enable = true;
    };
  } (c: [
    (check "a boot screen in place of console text"
      (c.boot.plymouth.enable && c.boot.plymouth.theme == "bgrt" && c.boot.initrd.systemd.enable
        && lib.hasInfix "DeviceScale=4" c.boot.plymouth.extraConfig
        && lib.elem "quiet" c.boot.kernelParams && lib.elem "splash" c.boot.kernelParams))
    (check "AMD and Intel by default, Intel's video decoder included, newest kernel"
      (lib.any (p: lib.getName p == "intel-media-driver") c.hardware.graphics.extraPackages
        && c.services.xserver.videoDrivers != [ "nvidia" ]
        && c.boot.kernelPackages.kernel.version == pkgs.linuxPackages_latest.kernel.version))
    (check "YARG without Clone Hero still gets the box's songs"
      (c.systemd.services ? famidrive-clonehero-songs
        && !(lib.any (p: lib.getName p == "clonehero") c.environment.systemPackages)))
    (check "YARG reads the box's songs, then the player's own"
      (lib.hasInfix "/var/lib/famidrive/clonehero/songs"
        c.home-manager.users.alice.home.activation.famidriveYarg.data))
    (check "autologin as the only player" (c.services.greetd.settings.initial_session.user == "alice"))
    (check "no picker" (c.services.greetd.settings.default_session.user == "alice"))
    (check "ES-DE's Quit menu (power off, reboot) is on"
      (lib.hasInfix "ShowQuitMenu" c.home-manager.users.alice.home.activation.famidriveEsSettings.data))
    (check "alice is a player" (lib.elem "famidrive" c.users.users.alice.extraGroups))
    (check "ES-DE reads alice's own ROM folder"
      (lib.hasInfix "/home/alice/.local/share/famidrive/roms" c.home-manager.users.alice.home.activation.famidriveEsSettings.data))
    (check "no RomM agent configs" (!(c.environment.etc ? "famidrive/romm/library.json")))
    (check "old builds are cleaned up weekly, two weeks kept"
      (c.nix.gc.automatic && c.nix.gc.options == "--delete-older-than 14d"
        && c.boot.loader.systemd-boot.configurationLimit == 10))
  ]);

  box-family = expect "family" familyHost (c:
    let
      picker = c.services.greetd.settings.default_session;
      pam = c.security.pam.services.greetd.rules.auth;
      bob = etcJson c "famidrive/romm/bob.json";
      library = etcJson c "famidrive/romm/library.json";
    in [
      (check "starts on the picker as greeter" (picker.user == "greeter" && lib.hasInfix "famidrive-picker" picker.command))
      (check "no autologin" (!(c.services.greetd.settings ? initial_session)))
      (check "a switch restarts the session when it changed" c.systemd.services.greetd.restartIfChanged)
      (check "a host's own cleanup choice wins" (c.nix.gc.options == "--delete-older-than 30d"))
      (check "YARG is in Ports next to Clone Hero, scores saved under its RomM entry"
        (lib.hasInfix "yarg)" c.famidrive.systems.ports.command
          && lib.hasInfix "clonehero)" c.famidrive.systems.ports.command
          && (etcJson c "famidrive/romm/alice.json").apps ? yarg))
      (check "a Switch game listed for Ryujinx runs there, its save bridged through Eden's"
        (lib.hasInfix "FAMIDRIVE_RYUJINX" c.famidrive.systems.switch.command
          && lib.hasInfix "famidrive-ryujinx save-in" c.famidrive.systems.switch.before
          && lib.hasInfix "famidrive-ryujinx save-out" c.famidrive.systems.switch.after
          && (etcJson c "famidrive/romm/library.json").ryujinxGames == [ "01006A800016E000" ]))
    (check "Ryujinx gets 8 GiB on its command line (it ignores Config.json's with --no-gui)"
      (lib.hasInfix "--dram-size MemoryConfiguration8GiB" c.famidrive.systems.switch.command))
      (check "Clone Hero is in Ports, songs come down as the library"
        (c.famidrive.systems ? ports
          && c.systemd.services.famidrive-clonehero-songs.serviceConfig.User == "famidrive-library"))
      (check "a Minecraft instance only for the players it's declared for"
        (lib.hasInfix ''"instances":{"Test Server"'' c.home-manager.users.alice.home.activation.famidriveMinecraft.data
          && lib.hasInfix ''"instances":{}'' c.home-manager.users.bob.home.activation.famidriveMinecraft.data
          && lib.hasInfix ''"instances":{}'' c.home-manager.users.guest.home.activation.famidriveMinecraft.data))
      (check "RomM systems' art is the library's, PC lanes' stays the player's"
        (lib.hasInfix "/var/lib/famidrive/media/gc" c.home-manager.users.bob.home.activation.famidriveRoms.data
          && !(lib.hasInfix "/var/lib/famidrive/media/steam" c.home-manager.users.bob.home.activation.famidriveRoms.data)
          && library.platforms == null))
      (check "Dolphin loads the library's texture packs, for every player"
        (lib.elem "d /var/lib/famidrive/textures 0755 famidrive-library famidrive -" c.systemd.tmpfiles.rules
          && lib.hasInfix "HiresTextures" c.home-manager.users.guest.home.activation.famidriveEmulators.data))
      (check "PlayStation's BIOS under the names SwanStation looks for"
        (lib.hasInfix "scph5501.bin" c.famidrive.sessionSetup))
      (check "RetroArch saves straight in saves/, where save sync looks"
        (lib.hasInfix "sort_savefiles_enable" c.home-manager.users.bob.home.activation.famidriveEmulators.data
          && c.famidrive.systems.psx.saveSync))
      (check "one Ports system, for Minecraft and Clone Hero both"
        (!(c.famidrive.systems ? minecraft)
          && lib.sort lib.lessThan c.famidrive.systems.ports.extensions == [ ".port" ".prism" ]
          && lib.hasInfix "prismlauncher" c.famidrive.systems.ports.command
          && lib.hasInfix "clonehero" c.famidrive.systems.ports.command
          # Saving after a game is outside it, where a quit can't skip it.
          && lib.hasInfix "famidrive-clonehero played" c.famidrive.systems.ports.after
          && !(lib.hasInfix "played" c.famidrive.systems.ports.command)))
      (check "Clone Hero reads the box's songs and calibration"
        (lib.hasInfix "/var/lib/famidrive/clonehero/songs" c.home-manager.users.bob.home.activation.famidriveCloneHero.data
          && lib.hasInfix "200" c.home-manager.users.bob.home.activation.famidriveCloneHero.data))
      (check "Media has Kodi and Jellyfin, one entry each, for every player"
        (c.famidrive.systems.media.extensions == [ ".kodi" ".jellyfin" ]
          && lib.hasInfix "Kodi.kodi" c.home-manager.users.bob.home.activation.famidriveMedia.data
          && lib.hasInfix "Jellyfin.jellyfin" c.home-manager.users.guest.home.activation.famidriveMedia.data
          && lib.hasInfix "/media/movies" c.famidrive.systems.media.command))
      (check "Kodi has JellyCon on the box's Jellyfin, Up Next, and the box's own add-ons"
        (lib.hasInfix "plugin.video.jellycon" c.famidrive.systems.media.command
          && lib.hasInfix "https://jellyfin.example.org" c.famidrive.systems.media.command
          && !(lib.hasInfix "plugin.video.jellyfin" c.famidrive.systems.media.command)
          && lib.hasInfix "service.upnext" c.famidrive.systems.media.command
          && lib.hasInfix "service.subtitles.a4ksubtitles" c.famidrive.systems.media.command))
      (check "new players start at full volume"
        (c.services.pipewire.wireplumber.extraConfig.famidrive-volume."wireplumber.settings"."device.routes.default-sink-volume" == 1.0))
      (check "players log in without a password from greetd"
        (pam.famidrive-player.enable && pam.famidrive-player.control == "sufficient"
          && pam.famidrive-player.order < pam.unix.order))
      (check "an account per player and the guest"
        (lib.all (u: lib.elem "famidrive" c.users.users.${u}.extraGroups) [ "alice" "bob" "guest" ]))
      (check "the library has its own account" (c.users.users.famidrive-library.isSystemUser))
      (check "bob's token comes from sops; alice's is set by hand"
        (c.sops.secrets ? romm-token-bob && !(c.sops.secrets ? romm-token-alice) && !(c.sops.secrets ? romm-token-guest)))
      (check "the library pulls with the primary player's token"
        (c.systemd.services.romm-library-pull.serviceConfig.LoadCredential == "romm-token:/run/secrets/alice-token"
          && c.systemd.services.romm-library-pull.serviceConfig.User == "famidrive-library"))
      (check "library config holds no token" (library.tokenFile == null))
      (check "RomM keeps three versions of each save" (bob.saveHistory == 3))
      (check "the pull waits for the library disk and sets up its folders"
        (c.systemd.services.romm-library-pull.unitConfig.RequiresMountsFor == "/var/lib/famidrive"
          && lib.hasInfix "systemd-tmpfiles --create --prefix=/var/lib/famidrive"
            c.systemd.services.romm-library-pull.serviceConfig.ExecStartPre))
      (check "bob's agent config is his" (bob.owner == "bobby" && bob.gamelistDir == "/home/bob/ES-DE/gamelists"
        && bob.playerRoms == "/home/bob/.local/share/famidrive/roms"))
      (check "no agent config for the guest" (!(c.environment.etc ? "famidrive/romm/guest.json")))
      (check "save reconcile for each RomM player, not the guest"
        (c.systemd.timers ? romm-save-reconcile-alice && c.systemd.timers ? romm-save-reconcile-bob
          && !(c.systemd.timers ? romm-save-reconcile-guest)))
      (check "a Steam menu generator per player"
        (lib.all (p: c.systemd.services ? "famidrive-gen-steam-${p}") [ "alice" "bob" "guest" ]))
      (check "GOG, Epic and Amazon are each a system, launched through Heroic"
        (lib.all (s: c.famidrive.systems ? ${s} && lib.hasInfix "heroic://launch" c.famidrive.systems.${s}.command)
          [ "gog" "epic" "amazon" ]))
      (check "Heroic's menu entries follow its installed-games files, per player"
        (lib.hasInfix "legendaryConfig/legendary/installed.json"
          (toString c.systemd.paths.famidrive-gen-heroic-bob.pathConfig.PathChanged)))
      (check "Heroic is in Settings, for sign-in and installs"
        (lib.hasInfix "Heroic Games Launcher.setting" c.home-manager.users.alice.home.activation.famidriveSettings.data))
      (check "Steam's art and details after each Steam menu update, not before the session"
        (c.systemd.services.famidrive-gen-steam-alice.onSuccess == [ "famidrive-steam-media-alice.service" ]
          && !(lib.elem "display-manager.service" (c.systemd.services.famidrive-steam-media-alice.wantedBy or [ ]))))
      (check "the TV can power off and reboot without a password"
        (lib.hasInfix "org.freedesktop.login1.power-off" c.security.polkit.extraConfig
          && lib.hasInfix "isInGroup(\"famidrive\")" c.security.polkit.extraConfig))
      (check "the shared library is read-only to players"
        (lib.elem "d /var/lib/famidrive/roms 0755 famidrive-library famidrive -" c.systemd.tmpfiles.rules))
    ]);
}
