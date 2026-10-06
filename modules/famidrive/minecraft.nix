# Minecraft instances declared in Nix (pc-games.md). Prism Launcher still
# runs them and owns everything else about them (worlds, settings, mods
# added by hand); this sets up what a box should come with: the Minecraft
# and Fabric versions, the mods, Java, and the servers to show or join.
#
# The Microsoft account isn't here: Prism's sign-in is a one-time step on
# each box, and its tokens aren't something to put in a Nix store.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  hasLane = l: lib.elem l cfg.lanes;

  # Controller support: Controlify and what it needs, per Minecraft
  # version. Pinned here, so a version not listed needs its mods given by
  # hand (`mods`) until it's added.
  modrinth = name: url: sha512: pkgs.fetchurl { inherit name url sha512; };
  controllerMods = {
    "26.2" = [
      (modrinth "controlify-3.5.3+mc26.2-universal.jar"
        "https://cdn.modrinth.com/data/DOUdJVEm/versions/VDw4mGkG/controlify-3.5.3%2Bmc26.2-universal.jar"
        "fa590eeebeb7ce4be828456dd796dd786919b7a8c664a4e509fc1c4a82414a349c598a5c968e4b4974abcdb3db1d32d03a7f38a532d924308a5b382bdf28437a")
      (modrinth "fabric-api-0.161.0+26.2.jar"
        "https://cdn.modrinth.com/data/P7dR8mSH/versions/ewUK83HI/fabric-api-0.161.0%2B26.2.jar"
        "2502fa5ade78e9a120b3747bc1a9a2167d6671743bea45bf115d3174c94121aeda87c549446d1a604a9c11fb828de17a551e3514ce42f3e93069dd14bdaee55b")
      (modrinth "yet_another_config_lib_v3-3.9.7+26.2-fabric.jar"
        "https://cdn.modrinth.com/data/1eAoo2KR/versions/DoR7RYgi/yet_another_config_lib_v3-3.9.7%2B26.2-fabric.jar"
        "f36d91a9506ad9addbaaeecaea01d2b0cb5b060f52486b17688746cb597f0f3b23a80f8441f7a73a9cb8cde85af8809fe54825984b56345325359d505a80e7f2")
    ];
  };

  instance = types.submodule ({ name, config, ... }: {
    options = {
      minecraft = mkOption {
        type = types.str;
        example = "26.2";
        description = "Minecraft version.";
      };

      fabricLoader = mkOption {
        type = types.nullOr types.str;
        default = if config.controller then "0.19.5" else null;
        defaultText = ''"0.19.5" when `controller` is on, else null'';
        description = "Fabric Loader version, or null for vanilla Minecraft (no mods).";
      };

      controller = mkOption {
        type = types.bool;
        default = true;
        description = ''
          Play with a controller: adds Controlify (and Fabric API and
          YACL, which it needs). Needs Fabric, and a Minecraft version
          FamiDrive has these pinned for.
        '';
      };

      mods = mkOption {
        type = types.listOf types.path;
        default = [ ];
        example = lib.literalExpression ''[ (pkgs.fetchurl { name = "sodium.jar"; url = "…"; sha512 = "…"; }) ]'';
        description = "More mod jars. Mods added by hand in Prism stay as well.";
      };

      servers = mkOption {
        type = types.listOf (types.submodule {
          options = {
            name = mkOption { type = types.str; };
            address = mkOption { type = types.str; example = "mc.example.org"; };
          };
        });
        default = [ ];
        description = "Servers in the multiplayer list. Servers added in-game stay.";
      };

      join = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "mc.example.org";
        description = ''
          A server to join straight from launch, skipping the title screen:
          picking the instance in ES-DE drops you into that server.
        '';
      };

      java = mkOption {
        type = types.package;
        default = pkgs.jdk25;
        defaultText = "pkgs.jdk25";
        description = "Java to run it with. Minecraft 26 needs 25; older versions want older ones (1.20.5 to 1.21: jdk21).";
      };

      memory = mkOption {
        type = types.nullOr types.ints.positive;
        default = null;
        example = 6144;
        description = "Most memory Minecraft may use, in MiB. null: Prism's setting.";
      };
    };
  });

  spec = {
    root = "~/.local/share/PrismLauncher";
    launcher = {
      # Prism's window closes once the game is up, and Prism quits when the
      # game does, so ES-DE comes back when Minecraft is closed.
      CloseAfterLaunch = "true";
      QuitAfterGameStop = "true";
      # Each instance sets its own Java; no first-run Java wizard.
      IgnoreJavaWizard = "true";
    };
    instances = lib.mapAttrs (_: i: {
      inherit (i) minecraft fabricLoader servers join memory;
      java = "${i.java}/bin/java";
      mods = map toString (lib.optionals i.controller controllerMods.${i.minecraft} ++ i.mods);
    }) cfg.minecraft.instances;
  };
in
{
  options.famidrive.minecraft.instances = mkOption {
    type = types.attrsOf instance;
    default = { };
    example = lib.literalExpression ''
      {
        "Friends Server" = {
          minecraft = "26.2";
          servers = [ { name = "Friends"; address = "mc.example.org"; } ];
          join = "mc.example.org";
        };
      }
    '';
    description = ''
      Prism Launcher instances this box comes with, by the name ES-DE shows.
      Instances not listed here are left alone.
    '';
  };

  config = lib.mkIf (cfg.enable && hasLane "minecraft" && cfg.minecraft.instances != { }) {
    assertions = lib.concatLists (lib.mapAttrsToList (name: i: [
      {
        assertion = !i.controller || i.fabricLoader != null;
        message = "famidrive.minecraft.instances.\"${name}\": controller support needs Fabric (fabricLoader).";
      }
      {
        assertion = !i.controller || controllerMods ? ${i.minecraft};
        message = ''
          famidrive.minecraft.instances."${name}": FamiDrive has no controller mods pinned for
          Minecraft ${i.minecraft} (it has: ${lib.concatStringsSep ", " (lib.attrNames controllerMods)}).
          Set controller = false and add Controlify for that version to `mods` yourself.
        '';
      }
    ]) cfg.minecraft.instances);

    famidrive.playerHome = { lib, ... }: {
      home.activation.famidriveMinecraft = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${pkgs.famidrive-prism}/bin/famidrive-prism ${lib.escapeShellArg (builtins.toJSON spec)}
      '';
    };
  };
}
