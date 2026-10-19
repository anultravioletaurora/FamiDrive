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
#
# Two shares every player can open, besides their home:
#   Library  the shared library (dataDir), read-only. Only the RomM pull
#            writes there.
#   Drop     a folder per console (Drop/gc, Drop/switch, by the library's
#            own folder names), writable by every player. What's copied in
#            is linked into the library's folder for that console, so ES-DE
#            lists it from the next session on. A game RomM later brings
#            under the same name takes its place; the copy stays in Drop.
#
# NFS (off by default) is for Linux computers. It has no sign-in, so it
# only offers the Library, read-only, to the networks a host lists.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkOption types;
  cfg = config.famidrive;
  withFile = lib.filterAttrs (_: p: p.smb.passwordFile != null) cfg.players;
  smbpasswd = "${config.services.samba.package}/bin/smbpasswd";

  # Consoles a game can be dropped in for: the ones the library pull
  # fills. A system from localRoms is a folder elsewhere on the box, not
  # the library's, so it has none.
  dropSystems = lib.filter (n: cfg.systems.${n}.rommPlatform != null && !(cfg.localRoms ? ${n}))
    (lib.attrNames cfg.systems);
  drop = "${cfg.dataDir}/drop";
  shares = cfg.smb.library.enable || cfg.smb.drop.enable;
  # The guest is in group famidrive too, for the library.
  guestOut = lib.optionalAttrs cfg.guest.enable { "invalid users" = cfg.allPlayers.guest.user; };
  ifs = cfg.smb.interfaces;
  everywhere = ifs == [ ];

  # Links each file or folder in Drop/<system> into the library's
  # <system> folder, unless the library has one by that name; links to
  # what's gone from Drop are removed. Runs as famidrive-library, which
  # owns the library.
  linkDrop = pkgs.writeShellScript "famidrive-drop" ''
    for sys in ${lib.concatStringsSep " " dropSystems}; do
      lib=${lib.escapeShellArg "${cfg.dataDir}/roms"}/$sys
      for link in "$lib"/*; do
        [ -L "$link" ] || continue
        case "$(readlink "$link")" in
          ${lib.escapeShellArg "${drop}/"}*) [ -e "$link" ] || rm -f "$link" ;;
        esac
      done
      for f in ${lib.escapeShellArg drop}/"$sys"/*; do
        [ -e "$f" ] || continue
        name=$(basename "$f")
        case "$name" in *.part|*.crdownload) continue ;; esac
        [ -e "$lib/$name" ] || [ -L "$lib/$name" ] && continue
        mkdir -p "$lib"
        ln -s "$f" "$lib/$name"
      done
    done
  '';
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
        on the box once). The guest can't sign in. The `Library` and
        `Drop` shares come with it. Off: no file sharing.
      '';
    };

    smb.library.enable = mkOption {
      type = types.bool;
      default = true;
      description = ''
        A `Library` share: the shared library (`dataDir`), read-only, for
        any player to copy games, art or firmware off. Systems from
        `localRoms` aren't in it: they're folders elsewhere on the box.
      '';
    };

    smb.drop.enable = mkOption {
      type = types.bool;
      default = true;
      description = ''
        A `Drop` share any player can copy games into, with a folder per
        console named as in the library (`gc`, `switch`, `psx` …). ES-DE
        lists what's copied in from the next session on, for every
        player. A game RomM brings later under the same name is used
        instead; the copy stays in `Drop`. Dropped games' saves stay on
        the box. Systems from `localRoms` have no folder: copy into
        their own folder instead.
      '';
    };

    smb.interfaces = mkOption {
      type = types.listOf types.str;
      default = [ ];
      example = [ "enp3s0" ];
      description = ''
        The network interfaces file sharing is reachable on: the home
        network's, never a VPN's or a public one's. Empty, every
        interface. Covers SMB, finding the box in Finder and Windows'
        Network, and NFS (`nfs.enable`).
      '';
    };

    nfs = {
      enable = mkOption {
        type = types.bool;
        default = false;
        description = ''
          The shared library (`dataDir`) over NFS (version 4), read-only,
          for Linux computers. NFS has no sign-in: anyone on
          `nfs.allowedNetworks` can read it, so only the library is
          offered, and firmware stays unreadable to them.
        '';
      };

      allowedNetworks = mkOption {
        type = types.listOf types.str;
        default = [ ];
        example = [ "192.168.1.0/24" ];
        description = "The networks (addresses or subnets) NFS serves. `nfs.enable` needs at least one.";
      };
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

  config = lib.mkIf cfg.enable (lib.mkMerge [ (lib.mkIf cfg.smb.enable {
    services.samba = {
      enable = true;
      openFirewall = everywhere;
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
        } // lib.optionalAttrs (!everywhere) {
          interfaces = lib.concatStringsSep " " ([ "lo" ] ++ ifs);
          "bind interfaces only" = "yes";
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
      } // lib.optionalAttrs cfg.smb.library.enable {
        Library = {
          path = cfg.dataDir;
          "read only" = "yes";
          "valid users" = "@famidrive";
        } // guestOut;
      } // lib.optionalAttrs cfg.smb.drop.enable {
        # Group famidrive, and writable by it, so every player can read
        # and replace what someone else dropped.
        Drop = {
          path = drop;
          "read only" = "no";
          "valid users" = "@famidrive";
        } // guestOut // {
          "force group" = "famidrive";
          "create mask" = "0664";
          "directory mask" = "2775";
        };
      };
    };

    # The library's disk can mount after smbd starts.
    systemd.services.samba-smbd.unitConfig.RequiresMountsFor = lib.mkIf shares [ cfg.dataDir ];

    # Finder's Network: the box's SMB, by Bonjour. Samba in nixpkgs is
    # built without Avahi, so it doesn't say so itself.
    services.avahi = {
      enable = true;
      openFirewall = everywhere;
      allowInterfaces = lib.mkIf (!everywhere) ifs;
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
      openFirewall = everywhere;
      extraOptions = [ "--shortlog" ] ++ lib.concatMap (i: [ "--interface" i ]) ifs;
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
  })

  (lib.mkIf (cfg.smb.enable && cfg.smb.drop.enable) {
    # setgid, so what's copied in stays group famidrive.
    systemd.tmpfiles.rules = [ "d ${drop} 2775 famidrive-library famidrive -" ]
      ++ map (n: "d ${drop}/${n} 2775 famidrive-library famidrive -") dropSystems;

    # On every change in a console's folder, and once at boot.
    systemd.paths.famidrive-drop = lib.mkIf (dropSystems != [ ]) {
      description = "FamiDrive: games copied into Drop";
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = map (n: "${drop}/${n}") dropSystems;
    };
    systemd.services.famidrive-drop = {
      description = "FamiDrive: link games copied into Drop into the library";
      wantedBy = [ "multi-user.target" ];
      unitConfig.RequiresMountsFor = [ cfg.dataDir ];
      serviceConfig = {
        Type = "oneshot";
        User = "famidrive-library";
        Group = "famidrive";
        ExecStartPre = "+${config.systemd.package}/bin/systemd-tmpfiles --create --prefix=${drop} --prefix=${cfg.dataDir}/roms";
        ExecStart = linkDrop;
      };
    };
  })

  (lib.mkIf cfg.nfs.enable {
    assertions = [{
      assertion = cfg.nfs.allowedNetworks != [ ];
      message = "famidrive.nfs.allowedNetworks: list the home network (say \"192.168.1.0/24\"); NFS has no sign-in.";
    }];
    services.nfs.server = {
      enable = true;
      # all_squash: whoever reads is nobody here, so the library's
      # firmware (group famidrive only) stays unreadable.
      exports = "${cfg.dataDir} ${lib.concatMapStringsSep " "
        (n: "${n}(ro,all_squash,no_subtree_check,crossmnt)") cfg.nfs.allowedNetworks}\n";
    };
    # Version 4 only: one port, no rpcbind or mountd to open.
    services.nfs.settings.nfsd = { vers3 = false; udp = false; };
    systemd.services.nfs-server.unitConfig.RequiresMountsFor = [ cfg.dataDir ];
    networking.firewall.allowedTCPPorts = lib.mkIf everywhere [ 2049 ];
  })

  (lib.mkIf (!everywhere && (cfg.smb.enable || cfg.nfs.enable)) {
    # SMB, wsdd (3702, 5357) and Bonjour (5353), and NFS, on these only.
    networking.firewall.interfaces = lib.genAttrs ifs (_: {
      allowedTCPPorts = lib.optionals cfg.smb.enable [ 445 5357 ] ++ lib.optional cfg.nfs.enable 2049;
      allowedUDPPorts = lib.optionals cfg.smb.enable [ 3702 5353 ];
    });
  })
  ]);
}
