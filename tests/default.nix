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
in
{
  romm-agent = unit "romm_agent" ../pkgs/romm-agent/romm_agent.py
    (pkgs.python3.withPackages (ps: [ ps.requests ]));
  valheim = unit "valheim" ../pkgs/famidrive-valheim/famidrive_valheim.py pkgs.python3;
  steam-config = unit "steam_config" ../pkgs/famidrive-steam-config/famidrive_steam_config.py pkgs.python3;
  clonehero = unit "clonehero" ../pkgs/famidrive-clonehero/famidrive_clonehero.py pkgs.python3;
  kodi = unit "kodi" ../pkgs/famidrive-kodi/famidrive_kodi.py pkgs.python3;
  prism = unit "prism" ../pkgs/famidrive-prism/famidrive_prism.py pkgs.python3;
  picker = unit "picker" ../pkgs/famidrive-picker/famidrive_picker.py
    (pkgs.python3.withPackages (ps: [ ps.pygame-ce ]));

  # One person, ROMs only, no RomM: the smallest box.
  box-one-player = expect "one-player" {
    famidrive = {
      enable = true;
      players.alice = { };
      romm.enable = false;
    };
  } (c: [
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

  # A family: two players with RomM, a guest, every lane.
  box-family = expect "family" {
    famidrive = {
      enable = true;
      lanes = [ "roms" "steam" "minecraft" ];
      players = {
        alice.romm.tokenFile = "/run/secrets/alice-token";
        bob.owner = "bobby";
      };
      primaryPlayer = "alice";
      guest.enable = true;
      endpoints.romm = "https://romm.example.org";
      endpoints.jellyfin = "https://jellyfin.example.org";
      media.jellyfin.enable = true;
      media.kodi = {
        enable = true;
        sources.Movies = { path = "/media/movies"; content = "movies"; };
        addons = p: [ p.upnext ];
      };
      minecraft.instances."Test Server" = {
        minecraft = "26.2";
        players = [ "alice" ];
        servers = [ { name = "Test"; address = "mc.example.org"; } ];
      };
      cloneHero = {
        enable = true;
        songs."AFI - Miss Murder" = "05185565cb931978c11de73d3048206e";
        audioOffset = 200;
      };
      valheim.mods."ValheimModding-Jotunn-2.30.2" = "sha256-iq6S2ivg62ggzUz1fi9sHWrQ1zjUkVlm58PXqU6amw8=";
    };
    nix.gc.options = "--delete-older-than 30d";   # a host's own choice wins
  } (c:
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
      (check "Clone Hero is in Ports, songs come down as the library"
        (c.famidrive.systems ? ports
          && c.systemd.services.famidrive-clonehero-songs.serviceConfig.User == "famidrive-library"))
      (check "a Minecraft instance only for the players it's declared for"
        (lib.hasInfix "Test Server" c.home-manager.users.alice.home.activation.famidriveMinecraft.data
          && !(lib.hasInfix "Test Server" c.home-manager.users.bob.home.activation.famidriveMinecraft.data)
          && !(lib.hasInfix "Test Server" c.home-manager.users.guest.home.activation.famidriveMinecraft.data)))
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
      (check "the TV can power off and reboot without a password"
        (lib.hasInfix "org.freedesktop.login1.power-off" c.security.polkit.extraConfig
          && lib.hasInfix "isInGroup(\"famidrive\")" c.security.polkit.extraConfig))
      (check "the shared library is read-only to players"
        (lib.elem "d /var/lib/famidrive/roms 0755 famidrive-library famidrive -" c.systemd.tmpfiles.rules))
    ]);
}
