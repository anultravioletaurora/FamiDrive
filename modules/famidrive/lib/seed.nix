# Helpers for configs the app also writes (tv-interface.md "ES-DE config management").
#
# A home-manager symlink into the read-only Nix store breaks any app that
# rewrites its own config (ES-DE, Dolphin, RetroArch, Eden...). Instead:
#   seed     - copy a starting file in only if none exists yet
#   lockKeys - force a small set of keys on every activation and leave
#              everything else to the app
#
# Both return shell snippets meant for home.activation.
{ lib, pkgs }:

let
  q = lib.escapeShellArg;
  # File paths are double-quoted, not escaped, so "$HOME/..." still expands.
  dq = s: ''"${s}"'';

  setters = {
    # [Section] key = value, used by Dolphin's INIs
    ini = file: keys: lib.concatStrings (lib.mapAttrsToList (section: kv:
      lib.concatStrings (lib.mapAttrsToList (k: v: ''
        ${pkgs.crudini}/bin/crudini --set ${dq file} ${q section} ${q k} ${q (toString v)}
      '') kv)) keys);

    # key = "value", one per line, used by retroarch.cfg
    keyValue = file: keys: lib.concatStrings (lib.mapAttrsToList (k: v: ''
      if grep -q '^${k} = ' ${dq file}; then
        sed -i 's|^${k} = .*|${k} = "${toString v}"|' ${dq file}
      else
        echo '${k} = "${toString v}"' >> ${dq file}
      fi
    '') keys);

    # ES-DE's es_settings.xml is a flat list of <type name="X" value="Y" />
    # lines with no single root element, so xmlstarlet can't parse it as a
    # document. Line-level edits instead. keys = { Name = { type = "string"; value = ...; }; }
    esSettings = file: keys: lib.concatStrings (lib.mapAttrsToList (k: v: ''
      if grep -q 'name="${k}"' ${dq file}; then
        sed -i 's|<[a-z]* name="${k}" value="[^"]*" />|<${v.type} name="${k}" value="${toString v.value}" />|' ${dq file}
      else
        echo '<${v.type} name="${k}" value="${toString v.value}" />' >> ${dq file}
      fi
    '') keys);

    # RPCS3's YAML configs (config.yml, rpcn.yml). keys = { ".Path.To.Key" = value; }
    yaml = file: keys: lib.concatStrings (lib.mapAttrsToList (path: v: ''
      ${pkgs.yq-go}/bin/yq -i '${path} = ${builtins.toJSON v}' ${dq file}
    '') keys);

    # JSON configs (Jellyfin MPV Shim's conf.json). keys = { ".path.to.key" = value; }
    json = file: keys: lib.concatStrings (lib.mapAttrsToList (path: v: ''
      [ -s ${dq file} ] || echo '{}' > ${dq file}
      tmp=$(mktemp)
      ${pkgs.jq}/bin/jq '${path} = ${builtins.toJSON v}' ${dq file} > "$tmp" && mv "$tmp" ${dq file}
    '') keys);
  };
in
{
  seed = { target, source }: ''
    if [ ! -e ${dq target} ]; then
      mkdir -p "$(dirname ${dq target})"
      install -m 0644 ${source} ${dq target}
    fi
  '';

  # Creates an empty file if needed, so locked keys still apply on first boot
  # before the app has ever written its own config.
  lockKeys = { format, target, keys }: ''
    mkdir -p "$(dirname ${dq target})"
    touch ${dq target}
    ${setters.${format} target keys}
  '';
}
