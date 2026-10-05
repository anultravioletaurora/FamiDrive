# A Settings system in ES-DE: one entry per feature this box has that's
# configured from its own screens, so the game lists hold only games.
# ES-DE's own settings menu can't take custom entries.
#
#   Steam Settings          Steam's Big Picture (Proton per game, launch
#                           options, Steam Input, downloads); steam lane
#   Jellyfin Media Player   the Jellyfin app, with its sign-in and its
#                           own settings menu; media.jellyfin.enable
{ config, lib, pkgs, ... }:

let
  cfg = config.famidrive;
  steam = lib.elem "steam" cfg.lanes;
  jellyfin = cfg.media.jellyfin.enable;
  dir = "${cfg.dataDir}/roms/settings";

  # Placeholder file name (what ES-DE shows) -> what it opens.
  entries =
    lib.optionalAttrs steam { "Steam Settings" = "steam"; }
    // lib.optionalAttrs jellyfin { "Jellyfin Media Player" = "jellyfin"; };

  # ES-DE sorts by name; Steam Settings goes first by its sort name. ES-DE
  # rewrites gamelists itself (play counts), so this is only a first copy.
  gamelist = pkgs.writeText "gamelist.xml" ''
    <?xml version="1.0"?>
    <gameList>
      <game>
        <path>./Steam Settings.setting</path>
        <name>Steam Settings</name>
        <sortname>0</sortname>
      </game>
    </gameList>
  '';
in
{
  config = lib.mkIf (cfg.enable && entries != { }) {
    famidrive.systems.settings = {
      fullname = "Settings";
      theme = "tools";   # Art Book Next's tools art
      extensions = [ ".setting" ];
      command = ''
        case "$(cat "$ROM")" in
          ${lib.optionalString steam ''steam) exec ${pkgs.gamescope-fg}/bin/gamescope-fg --steam bigpicture ;;''}
          ${lib.optionalString jellyfin ''jellyfin) ${cfg.systems.media.command} ;;''}
        esac
      '';
    };

    # tmpfiles rewrites the placeholders on every boot and switch. An entry
    # whose feature is turned off is removed with it.
    systemd.tmpfiles.rules = [
      "d ${dir} 0755 ${cfg.user} users -"
    ] ++ lib.mapAttrsToList (name: what:
      "f+ ${dir}/${lib.replaceStrings [ " " ] [ "\\x20" ] name}.setting 0644 ${cfg.user} users - ${what}"
    ) entries ++ map (name:
      "r ${dir}/${lib.replaceStrings [ " " ] [ "\\x20" ] name}.setting"
    ) (lib.filter (n: !(entries ? ${n})) [ "Steam Settings" "Jellyfin Media Player" ]);

    home-manager.users.${cfg.user} = { lib, ... }: {
      home.activation.famidriveSettingsGamelist = lib.mkIf steam (lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        g="$HOME/ES-DE/gamelists/settings/gamelist.xml"
        if [ ! -e "$g" ]; then
          mkdir -p "$(dirname "$g")"
          install -m 0644 ${gamelist} "$g"
        fi
      '');
    };
  };
}
