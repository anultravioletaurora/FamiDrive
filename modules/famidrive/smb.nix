# File sharing (SMB): each player's home folder on the network, so they
# can change what's in it from another computer's file browser: the
# menu's music (~/ES-DE/music), or recordings to copy off (~/Recordings).
# The box shows up by its hostname under Network in Finder (Bonjour,
# through Avahi) and in Windows' Network (wsdd).
#
# Samba can't check a Linux password: SMB sign-in needs a hash of its
# own (the NT hash), and the Linux one can't be turned into it. So each
# player has an SMB password too, from `smb.passwordFile` or set once on
# the box with `sudo smbpasswd -a <user>`. The guest gets none: the
# guest's files are anyone's who plays, not someone's to sign in as.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  withFile = lib.filterAttrs (_: p: p.smb.passwordFile != null) cfg.players;
  smbpasswd = "${config.services.samba.package}/bin/smbpasswd";
in
{
  options.famidrive = {
    smb.enable = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Each player's home folder on the network over SMB, to change
        the files in it from another computer: the menu's music in
        `ES-DE/music` (played from the next session on), or recordings
        in `Recordings`. The box shows up by its hostname under Network
        in a Mac's Finder and in Windows' Network. A player signs in as
        their Linux account, with their SMB password
        (`players.<name>.smb.passwordFile`, or `sudo smbpasswd -a <user>`
        on the box once). The guest can't sign in. Off: no file sharing.
      '';
    };

    players = mkOption {
      type = types.attrsOf (types.submodule {
        options.smb.passwordFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          example = "/run/secrets/alice/smb";
          description = ''
            A file with their SMB password, readable by root, set as
            their password at each boot. Unset, they set one once on the
            box with `sudo smbpasswd -a <user>`. Samba keeps its own
            passwords: it can't check their Linux one.
          '';
        };
      });
    };
  };

  config = lib.mkIf (cfg.enable && cfg.smb.enable) {
    services.samba = {
      enable = true;
      openFirewall = true;
      # NetBIOS names are for old Windows; wsdd and Bonjour find the box.
      nmbd.enable = false;
      settings = {
        global = {
          "server string" = "FamiDrive";
          "server role" = "standalone server";
          "map to guest" = "never";
          "disable netbios" = "yes";
          "smb ports" = "445";
          "server min protocol" = "SMB2_10";
          "load printers" = "no";
          "printcap name" = "/dev/null";
          "disable spoolss" = "yes";
          # Apple's SMB extensions, so Finder is quick and keeps a file's
          # metadata in extended attributes, not "._" files next to it:
          # a "._song.mp3" in ES-DE/music is a file the music would try
          # to play. Leftover ones are hidden from the box (veto).
          "vfs objects" = "catia fruit streams_xattr";
          "fruit:metadata" = "stream";
          "fruit:posix_rename" = "yes";
          "fruit:wipe_intentionally_left_blank_rfork" = "yes";
          "fruit:delete_empty_adfiles" = "yes";
          "veto files" = "/.DS_Store/";
          "delete veto files" = "yes";
        };
        # Each player's home, as a share named after their account; only
        # they can open it.
        homes = {
          browseable = "no";
          "read only" = "no";
          "valid users" = "%S";
          "create mask" = "0644";
          "directory mask" = "0755";
        };
      };
    };

    # Finder's Network: the box's SMB, by Bonjour. Samba in nixpkgs is
    # built without Avahi, so it doesn't say so itself.
    services.avahi = {
      enable = true;
      openFirewall = true;
      nssmdns4 = lib.mkDefault true;
      publish = {
        enable = true;
        userServices = true;
      };
      extraServiceFiles.smb = ''
        <?xml version="1.0" standalone='no'?>
        <!DOCTYPE service-group SYSTEM "avahi-service.dtd">
        <service-group>
          <name replace-wildcards="yes">%h</name>
          <service>
            <type>_smb._tcp</type>
            <port>445</port>
          </service>
        </service-group>
      '';
    };

    # Windows' Network.
    services.samba-wsdd = {
      enable = true;
      openFirewall = true;
    };

    # passwordFile, as their SMB password. smbpasswd -a adds them, or
    # changes it for one already there.
    systemd.services.famidrive-smb-passwords = lib.mkIf (withFile != { }) {
      description = "FamiDrive: players' SMB passwords";
      wantedBy = [ "multi-user.target" ];
      after = [ "samba-smbd.service" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = lib.concatStrings (lib.mapAttrsToList (_: p: ''
        if ! { pw=$(cat ${lib.escapeShellArg (toString p.smb.passwordFile)}) \
            && printf '%s\n%s\n' "$pw" "$pw" | ${smbpasswd} -s -a ${lib.escapeShellArg p.user} > /dev/null; }; then
          echo "famidrive-smb-passwords: couldn't set ${p.user}'s" >&2
        fi
      '') withFile);
    };
  };
}
