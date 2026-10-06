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
    (check "no Switch Player without a second player"
      (!(lib.hasInfix "Switch Player" c.home-manager.users.alice.home.activation.famidriveSettings.data or "")))
    (check "alice is a player" (lib.elem "famidrive" c.users.users.alice.extraGroups))
    (check "ES-DE reads alice's own ROM folder"
      (lib.hasInfix "/home/alice/.local/share/famidrive/roms" c.home-manager.users.alice.home.activation.famidriveEsSettings.data))
    (check "no RomM agent configs" (!(c.environment.etc ? "famidrive/romm/library.json")))
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
      minecraft.instances."Test Server" = {
        minecraft = "26.2";
        servers = [ { name = "Test"; address = "mc.example.org"; } ];
      };
      valheim.mods."ValheimModding-Jotunn-2.30.2" = "sha256-iq6S2ivg62ggzUz1fi9sHWrQ1zjUkVlm58PXqU6amw8=";
    };
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
      (check "bob's agent config is his" (bob.owner == "bobby" && bob.gamelistDir == "/home/bob/ES-DE/gamelists"
        && bob.playerRoms == "/home/bob/.local/share/famidrive/roms"))
      (check "no agent config for the guest" (!(c.environment.etc ? "famidrive/romm/guest.json")))
      (check "save reconcile for each RomM player, not the guest"
        (c.systemd.timers ? romm-save-reconcile-alice && c.systemd.timers ? romm-save-reconcile-bob
          && !(c.systemd.timers ? romm-save-reconcile-guest)))
      (check "a Steam menu generator per player"
        (lib.all (p: c.systemd.services ? "famidrive-gen-steam-${p}") [ "alice" "bob" "guest" ]))
      (check "Switch Player in Settings"
        (lib.hasInfix "Switch Player" c.home-manager.users.bob.home.activation.famidriveSettings.data))
      (check "the shared library is read-only to players"
        (lib.elem "d /var/lib/famidrive/roms 0755 famidrive-library famidrive -" c.systemd.tmpfiles.rules))
    ]);
}
