"""Brings FamiDrive's own pins up to their latest upstream versions.

    python3 scripts/update-pins.py [SUMMARY_FILE]

Run from the repository's root, with Nix (for the hashes) and network.
The weekly Update workflow (.github/workflows/update.yml) runs it after
`nix flake update`; it works the same by hand. Each pin is checked
against where it comes from, and only changed when there's something
newer:

- ES-DE's AppImage (GitLab releases)                 pkgs/es-de
- xNVSE (GitHub releases)                            modules/famidrive/nexusmods.nix
- Art Book Next (its GitHub main branch)             modules/famidrive/frontend.nix
- SuperTux Advance and Brux (their default branches,
  moved together: they're developed together)        pkgs/supertux-advance
- SuperTux Party (GitLab releases)                   pkgs/supertuxparty
- Valheim's and Risk of Rain 2's BepInExPacks
  (Thunderstore)                                     modules/famidrive/thunderstore.nix

What nix-update does, for pins it can't reach: most of these are option
defaults or module values rather than packages, or come from sites it
doesn't know. Hashes come from Nix itself (nix store prefetch-file, nix
flake prefetch). Each update is one line in SUMMARY_FILE (Markdown), for
the pull request. A pin whose upstream can't be read is left alone and
reported, so one site being down never stops the rest.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
summary: list[str] = []


# What each upstream's API answers, the parts read here.
class GitLabLink(TypedDict):
    name: str
    url: str


class GitLabAssets(TypedDict):
    links: list[GitLabLink]


class GitLabRelease(TypedDict):
    tag_name: str
    released_at: str
    assets: GitLabAssets


class GitHubAsset(TypedDict):
    name: str
    browser_download_url: str


class GitHubRelease(TypedDict):
    tag_name: str
    assets: list[GitHubAsset]


class GitHubRepo(TypedDict):
    default_branch: str


class GitHubCommitter(TypedDict):
    date: str


class GitHubCommitInfo(TypedDict):
    committer: GitHubCommitter


class GitHubCommit(TypedDict):
    sha: str
    commit: GitHubCommitInfo


class ThunderstoreVersion(TypedDict):
    version_number: str


class ThunderstorePackage(TypedDict):
    latest: ThunderstoreVersion


class NixPrefetch(TypedDict):
    hash: str


def get(url: str) -> bytes:
    headers = {"User-Agent": "FamiDrive-updates"}
    if "api.github.com" in url and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        body: bytes = r.read()
        return body


def gitlab_latest(project: str) -> GitLabRelease:
    """A GitLab project's newest release (project: "group%2Fname")."""
    releases: list[GitLabRelease] = json.loads(get(f"https://gitlab.com/api/v4/projects/{project}/releases?per_page=1"))
    return releases[0]


def github_latest(owner: str, repo: str) -> GitHubRelease:
    release: GitHubRelease = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest"))
    return release


def thunderstore_latest(author: str, name: str) -> str:
    """A Thunderstore package's newest version number."""
    package: ThunderstorePackage = json.loads(
        get(f"https://thunderstore.io/api/experimental/package/{author}/{name}/"))
    return package["latest"]["version_number"]


def nix_hash(*args: str) -> str:
    out = subprocess.run(["nix", "--extra-experimental-features", "nix-command flakes", *args, "--json"],
                         check=True, capture_output=True, text=True).stdout
    prefetched: NixPrefetch = json.loads(out)
    return prefetched["hash"]


def url_hash(url: str) -> str:
    return nix_hash("store", "prefetch-file", url)


def tree_hash(flakeref: str) -> str:
    """The hash fetchFromGitHub has for a commit (its unpacked tree)."""
    return nix_hash("flake", "prefetch", flakeref)


def head(owner: str, repo: str) -> tuple[str, str]:
    """(commit, its date) at the tip of a GitHub repo's default branch."""
    info: GitHubRepo = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}"))
    c: GitHubCommit = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}/commits/{info['default_branch']}"))
    return c["sha"], c["commit"]["committer"]["date"][:10]


def edit(path: str, changes: list[tuple[str, str]]) -> None:
    """Replace each (old, new) in a file, exactly once each."""
    p = ROOT / path
    text = p.read_text()
    for old, new in changes:
        if text.count(old) != 1:
            raise RuntimeError(f"{path}: expected one {old!r}")
        text = text.replace(old, new)
    p.write_text(text)


def one(pattern: str, path: str) -> re.Match[str]:
    m = re.search(pattern, (ROOT / path).read_text())
    if not m:
        raise RuntimeError(f"{path}: no match for {pattern}")
    return m


# ---------------------------------------------------------------- the pins

def es_de() -> None:
    path = "pkgs/es-de/default.nix"
    m = one(r'version = "([^"]+)";', path)
    release = gitlab_latest("es-de%2Femulationstation-de")
    new = release["tag_name"].lstrip("v")
    if new == m.group(1):
        return
    link = next(a["url"] for a in release["assets"]["links"] if a["name"] == "ES-DE_x64.AppImage")
    old_url = one(r'url = "(https://gitlab\.com/[^"]+)";', path).group(1)
    old_hash = one(r'hash = "(sha256-[^"]+)";', path).group(1)
    old_comment = one(r"# ES_DE_x64\.AppImage from the v[^\n]+", path).group(0)
    edit(path, [(f'version = "{m.group(1)}";', f'version = "{new}";'),
                (old_url, link),
                (old_hash, url_hash(link)),
                (old_comment, f"# ES_DE_x64.AppImage from the v{new} release ({release['released_at'][:10]}).")])
    summary.append(f"- **ES-DE** {m.group(1)} → {new}")


def xnvse() -> None:
    path = "modules/famidrive/nexusmods.nix"
    m = one(r'url = "https://github\.com/xNVSE/NVSE/releases/download/([^/]+)/([^"]+)";\s*hash = "([^"]+)";', path)
    release = github_latest("xNVSE", "NVSE")
    if release["tag_name"] == m.group(1):
        return
    asset = next(a for a in release["assets"] if re.fullmatch(r"nvse_[\d_]+\.7z", a["name"]))
    url = asset["browser_download_url"]
    edit(path, [(f"https://github.com/xNVSE/NVSE/releases/download/{m.group(1)}/{m.group(2)}", url),
                (m.group(3), url_hash(url))])
    summary.append(f"- **xNVSE** {m.group(1)} → {release['tag_name']}")


def art_book() -> None:
    path = "modules/famidrive/frontend.nix"
    m = one(r'rev = "([0-9a-f]{40})";   # (\S+)\n\s*hash = "([^"]+)";', path)
    rev, date = head("anthonycaccese", "art-book-next-es-de")
    if rev == m.group(1):
        return
    edit(path, [(f'rev = "{m.group(1)}";   # {m.group(2)}', f'rev = "{rev}";   # {date}'),
                (m.group(3), tree_hash(f"github:anthonycaccese/art-book-next-es-de/{rev}"))])
    summary.append(f"- **Art Book Next** {m.group(1)[:7]} → {rev[:7]} ({date})")


def supertux_advance() -> None:
    path = "pkgs/supertux-advance/default.nix"
    for repo, submodules in (("brux-gdk", True), ("supertux-advance", False)):
        text = (ROOT / path).read_text()
        block = re.search(rf'version = "(0-unstable-[\d-]+)";\s*\n\s*src = fetchFromGitHub \{{\s*owner = "KelvinShadewing";\s*'
                          rf'repo = "{repo}";\s*rev = "([0-9a-f]+)";(.*?)hash = "([^"]+)";', text, re.S)
        if not block:
            raise RuntimeError(f"{path}: no pin for {repo}")
        rev, date = head("KelvinShadewing", repo)
        if rev == block.group(2):
            continue
        ref = (f"git+https://github.com/KelvinShadewing/{repo}?rev={rev}&submodules=1" if submodules
               else f"github:KelvinShadewing/{repo}/{rev}")
        new = block.group(0).replace(block.group(1), f"0-unstable-{date}").replace(block.group(2), rev) \
                            .replace(block.group(4), tree_hash(ref))
        edit(path, [(block.group(0), new)])
        summary.append(f"- **{'Brux' if repo == 'brux-gdk' else 'SuperTux Advance'}** {block.group(2)[:7]} → {rev[:7]} ({date})")


def supertux_party() -> None:
    path = "pkgs/supertuxparty/default.nix"
    m = one(r'version = "([^"]+)";', path)
    new = gitlab_latest("SuperTuxParty%2FSuperTuxParty")["tag_name"].lstrip("v")
    if new == m.group(1):
        return
    old_hash = one(r'hash = "(sha256-[^"]+)";', path).group(1)
    edit(path, [(f'version = "{m.group(1)}";', f'version = "{new}";'),
                (old_hash, url_hash(f"https://supertux.party/download/v{new}/linux.zip"))])
    summary.append(f"- **SuperTux Party** {m.group(1)} → {new}")


def bepinex() -> None:
    path = "modules/famidrive/thunderstore.nix"
    for m in re.finditer(r'package = "(([\w]+)-([\w]+))-([\d.]+)";\s*hash = "([^"]+)";', (ROOT / path).read_text()):
        full, author, name, version, old_hash = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        new = thunderstore_latest(author, name)
        if new == version:
            continue
        url = f"https://thunderstore.io/package/download/{author}/{name}/{new}/"
        edit(path, [(f'package = "{full}-{version}";', f'package = "{full}-{new}";'),
                    (old_hash, url_hash(url))])
        summary.append(f"- **{full}** {version} → {new}")


def main() -> None:
    failed: list[str] = []
    updates: tuple[Callable[[], None], ...] = (es_de, xnvse, art_book, supertux_advance, supertux_party, bepinex)
    for update in updates:
        try:
            update()
        except Exception as e:   # one upstream down shouldn't stop the others
            failed.append(f"- {update.__name__}: couldn't check ({e})")
            print(f"update-pins: {update.__name__}: {e}", file=sys.stderr)
    lines = summary + (["", "Not checked this time:", *failed] if failed else [])
    print("\n".join(lines) or "update-pins: everything is current")
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text("\n".join(lines) + "\n" if lines else "")


if __name__ == "__main__":
    main()
