"""famidrive-nexusmods: where a collection's files go, without Nexus Mods.

    python3 nexusmods_test.py path/to/famidrive_nexusmods.py

The cases are from Welcome to Night City (Cyberpunk 2077), revision 480,
checked against Vortex on the first box 2026-10-10: these rules put 265
of its 268 mods where Vortex did, and the other three Vortex left empty.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_nexusmods", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.BSDTAR = shutil.which("bsdtar") or "tar"   # macOS's tar is bsdtar

CET = "bin/x64/plugins/cyber_engine_tweaks/mods"

WTNC = b"""<?xml version="1.0"?>
<config>
  <moduleName>WTNC Config</moduleName>
  <installSteps order="Explicit">
    <installStep name="Your Choice Awaits">
      <optionalFileGroups order="Explicit">
        <group name="Choose Your Experience" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Welcome to Night City">
              <files><folder source="Welcome to Night City" destination="" priority="0" /></files>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
            <plugin name="Cyberpunk THING">
              <files><folder source="Cyberpunk THING" destination="" priority="0" /></files>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>"""
WTNC_FILES = [
    "WTNC Config/fomod/ModuleConfig.xml",
    "WTNC Config/Welcome to Night City/r6/tweaks/a.yaml",
    "WTNC Config/Cyberpunk THING/r6/tweaks/a.yaml",
    "WTNC Config/Cyberpunk THING/archive/pc/mod/thing.archive",
]


class Names(unittest.TestCase):
    def test_vortex_style_mod_names(self):
        self.assertEqual(m.mod_name("Sort Ripperdoc Inventory-17630-1-1-1754342283.zip", "x"), "Sort Ripperdoc Inventory")
        # A long version leaves the mod id on, as Vortex does.
        self.assertEqual(m.mod_name("reset attributes-9240-1-0-0-4-1728625012.zip", "x"), "reset attributes-9240")
        self.assertEqual(m.mod_name(None, "Fallback"), "Fallback")

    def test_folders_listed_without_a_slash_are_not_files(self):
        self.assertEqual(m.files_only(["archive", "archive/pc", "archive/pc/mod", "archive/pc/mod/a.archive", "readme/"]),
                         ["archive/pc/mod/a.archive"])
        self.assertEqual(m.files_only(["a\\b.reds"]), ["a/b.reds"])


class Cyberpunk(unittest.TestCase):
    def place(self, members, name="My Mod"):
        return sorted(m.cyberpunk_layout(members, name))

    def test_laid_out_from_the_game_folder_inside_a_folder(self):
        self.assertEqual(self.place(["Mod/archive/pc/mod/x.archive", "Mod/r6/scripts/X/x.reds", "Mod/readme.txt", "other.txt"]),
                         [("Mod/archive/pc/mod/x.archive", "archive/pc/mod/x.archive"),
                          ("Mod/r6/scripts/X/x.reds", "r6/scripts/X/x.reds"),
                          ("Mod/readme.txt", "readme.txt")])

    def test_scripts_straight_in_r6_scripts_get_a_folder(self):
        self.assertEqual(self.place(["r6/scripts/stealthrc.reds"], "StealthRC.zip"),
                         [("r6/scripts/stealthrc.reds", "r6/scripts/StealthRC.zip/stealthrc.reds")])

    def test_loose_files(self):
        self.assertEqual(self.place(["a.archive", "a.archive.xl", "t.yaml", "Plugin.dll", "readme.md", "x.reds"]),
                         [("Plugin.dll", "red4ext/plugins/Plugin/Plugin.dll"),
                          ("a.archive", "archive/pc/mod/a.archive"),
                          ("a.archive.xl", "archive/pc/mod/a.archive.xl"),
                          ("t.yaml", "r6/tweaks/t.yaml"),
                          ("x.reds", "r6/scripts/My Mod/x.reds")])

    def test_scripts_in_a_folder_keep_it(self):
        self.assertEqual(self.place(["Hub/a.reds", "Hub/sub/b.reds"]),
                         [("Hub/a.reds", "r6/scripts/Hub/a.reds"), ("Hub/sub/b.reds", "r6/scripts/Hub/sub/b.reds")])

    def test_cyber_engine_tweaks_and_redmod(self):
        self.assertEqual(self.place(["Tool/init.lua", "Tool/data/x.json"]),
                         [("Tool/data/x.json", f"{CET}/Tool/data/x.json"), ("Tool/init.lua", f"{CET}/Tool/init.lua")])
        self.assertEqual(self.place(["Big/info.json", "Big/archives/a.archive"]),
                         [("Big/archives/a.archive", "mods/Big/archives/a.archive"), ("Big/info.json", "mods/Big/info.json")])


class Fomod(unittest.TestCase):
    def test_the_installers_default(self):
        placed = m.fomod_layout(WTNC_FILES, WTNC_FILES[0], WTNC)
        self.assertEqual(placed, [("WTNC Config/Welcome to Night City/r6/tweaks/a.yaml", "r6/tweaks/a.yaml")])

    def test_the_players_pick(self):
        placed = m.fomod_layout(WTNC_FILES, WTNC_FILES[0], WTNC, {"Cyberpunk THING"})
        self.assertEqual(sorted(b for _, b in placed), ["archive/pc/mod/thing.archive", "r6/tweaks/a.yaml"])

    def test_the_curators_recorded_choices(self):
        choices = [{"name": "Your Choice Awaits", "groups": [{"name": "Choose Your Experience",
                                                             "choices": [{"name": " Cyberpunk THING", "idx": 1}]}]}]
        placed = m.fomod_layout(WTNC_FILES, WTNC_FILES[0], WTNC, choices)
        self.assertIn(("WTNC Config/Cyberpunk THING/archive/pc/mod/thing.archive", "archive/pc/mod/thing.archive"), placed)

    def test_flags_and_required_files(self):
        xml = b"""<config><requiredInstallFiles><file source="core.dll" destination="red4ext/plugins/C/core.dll"/></requiredInstallFiles>
          <installSteps><installStep name="S"><optionalFileGroups><group name="G" type="SelectExactlyOne"><plugins>
            <plugin name="Big"><conditionFlags><flag name="size">big</flag></conditionFlags></plugin>
          </plugins></group></optionalFileGroups></installStep></installSteps>
          <conditionalFileInstalls><patterns>
            <pattern><dependencies operator="And"><flagDependency flag="size" value="big"/></dependencies>
              <files><file source="big.archive" destination="archive/pc/mod/big.archive"/></files></pattern>
            <pattern><dependencies operator="And"><flagDependency flag="size" value="small"/></dependencies>
              <files><file source="small.archive" destination="archive/pc/mod/small.archive"/></files></pattern>
          </patterns></conditionalFileInstalls></config>"""
        files = ["fomod/ModuleConfig.xml", "core.dll", "big.archive", "small.archive"]
        self.assertEqual(sorted(b for _, b in m.fomod_layout(files, files[0], xml)),
                         ["archive/pc/mod/big.archive", "red4ext/plugins/C/core.dll"])


class Plan(unittest.TestCase):
    def test_exact_places_from_the_collection(self):
        mod = {"hashes": [{"path": "archive\\pc\\mod\\Gorilla Grapple.archive", "md5": "x"},
                          {"path": "r6\\scripts\\Gorilla_Grapple\\Gorilla_Grapple.reds", "md5": "y"}]}
        status, placed = m.place(mod, ["Gorilla Grapple.archive", "Gorilla_Grapple/Gorilla_Grapple.reds"])
        self.assertEqual(status, "exact")
        self.assertEqual(sorted(placed), [("Gorilla Grapple.archive", "archive/pc/mod/Gorilla Grapple.archive"),
                                          ("Gorilla_Grapple/Gorilla_Grapple.reds", "r6/scripts/Gorilla_Grapple/Gorilla_Grapple.reds")])

    def test_installer_read_from_the_archive(self):
        mod = {"domainName": "cyberpunk2077", "name": "WTNC Config"}
        status, placed = m.place(mod, WTNC_FILES, read=lambda member: WTNC, picks=["Cyberpunk THING"])
        self.assertEqual(status, "installer")
        self.assertEqual(len(placed), 2)

    def test_cyberpunk_fallback_as_is(self):
        status, placed = m.place({"domainName": "cyberpunk2077", "name": "Odd"}, ["Odd Folder/thing.bin", "readme.txt"])
        self.assertEqual(status, "fallback")
        self.assertEqual(sorted(placed), [("Odd Folder/thing.bin", "Odd Folder/thing.bin"), ("readme.txt", "readme.txt")])

    def test_a_game_without_rules(self):
        self.assertEqual(m.place({"domainName": "stardewvalley"}, ["Mod/manifest.json"]), ("unknown", []))

    def test_only_nexus_files_are_fetched(self):
        nexus, other = m.nexus_mods({"mods": [{"source": {"type": "nexus"}}, {"source": {"type": "browse"}}]})
        self.assertEqual((len(nexus), len(other)), (1, 1))

    def test_compare_with_vortex(self):
        plan = {"mods": [{"files": [{"from": "a", "to": "archive/pc/mod/A.archive"}, {"from": "b", "to": "r6/b.reds"}]}]}
        c = m.compare(plan, {"files": [{"relPath": "archive\\pc\\mod\\a.archive"}, {"relPath": "bin\\x.dll"}]})
        self.assertEqual((c["both"], c["onlyPlan"], c["onlyVortex"]), (1, ["r6/b.reds"], ["bin/x.dll"]))


class Order(unittest.TestCase):
    def test_phases_then_after_rules(self):
        mods = [{"name": "Config", "phase": 3, "source": {}}, {"name": "Base", "phase": 1, "source": {}},
                {"name": "Extended", "phase": 1, "source": {}}, {"name": "Early", "phase": 0, "source": {}}]
        rules = {"modRules": [{"type": "after", "source": {"logicalFileName": "Base"},
                               "reference": {"logicalFileName": "Extended"}}]}
        self.assertEqual([x["name"] for x in m.install_order(rules, mods)], ["Early", "Extended", "Base", "Config"])

    def test_collections_list_or_one(self):
        self.assertEqual(m.collections_of({"collection": {"slug": "a", "revision": 1}}), [{"slug": "a", "revision": 1}])
        self.assertEqual(len(m.collections_of({"collections": [{"slug": "a", "revision": 1}, {"slug": "b", "revision": 2}]})), 2)


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        m.STATE = self.base / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, name, files):
        p = self.base / name
        with zipfile.ZipFile(p, "w") as z:
            for k, v in files.items():
                z.writestr(k, v)
        return str(p)

    def test_read_only_folders_in_an_archive(self):
        src = self.base / "ro"
        (src / "Mod/r6/scripts").mkdir(parents=True)
        (src / "Mod/r6/scripts/a.reds").write_text("x")
        os.chmod(src / "Mod/r6/scripts", 0o555)
        os.chmod(src / "Mod/r6", 0o555)
        archive = self.base / "ro.tar"
        subprocess.run([m.BSDTAR, "-cf", str(archive), "-C", str(src), "Mod"], check=True)
        os.chmod(src / "Mod/r6", 0o755)
        os.chmod(src / "Mod/r6/scripts", 0o755)
        root = self.base / "game"
        root.mkdir()
        plan = {"mods": [{"name": "RO", "archive": str(archive), "files": [{"from": "Mod/r6/scripts/a.reds", "to": "r6/scripts/a.reds"}]}]}
        rec = m.install(plan, root, "1091500", {})
        self.assertTrue(rec["complete"])
        self.assertEqual((root / "r6/scripts/a.reds").read_text(), "x")

    def test_finds_the_game_in_any_library(self):
        steam, lib = self.base / "steam", self.base / "games"
        (steam / "steamapps").mkdir(parents=True)
        (lib / "steamapps").mkdir(parents=True)
        (steam / "steamapps/libraryfolders.vdf").write_text(f'"libraryfolders"\n{{\n "1"\n {{\n  "path" "{lib}"\n }}\n}}\n')
        (lib / "steamapps/appmanifest_1091500.acf").write_text('"AppState"\n{\n "StateFlags" "4"\n "installdir" "Cyberpunk 2077"\n}\n')
        (lib / "steamapps/appmanifest_22380.acf").write_text('"AppState"\n{\n "StateFlags" "1026"\n "installdir" "Fallout New Vegas"\n}\n')
        self.assertEqual(m.game_dir("1091500", steam), lib / "steamapps/common/Cyberpunk 2077")
        self.assertIsNone(m.game_dir("22380", steam))   # still updating
        self.assertIsNone(m.game_dir("400", steam))

    def test_follows_the_case_already_there(self):
        root = self.base / "game"
        (root / "r6/scripts").mkdir(parents=True)
        self.assertEqual(m.resolve(root, "R6/Scripts/a.reds"), root / "r6/scripts/a.reds")

    def test_install_then_uninstall(self):
        root = self.base / "game"
        (root / "r6/config").mkdir(parents=True)
        (root / "r6/config/options.json").write_text("the game's own")
        a = self.archive("a.zip", {"Mod/r6/scripts/a.reds": "first", "Mod/r6/config/options.json": "modded"})
        b = self.archive("b.zip", {"x.reds": "second"})
        plan = {"mods": [
            {"name": "A", "archive": a, "files": [{"from": "Mod/r6/scripts/a.reds", "to": "r6/scripts/A/a.reds"},
                                                  {"from": "Mod/r6/config/options.json", "to": "r6/config/options.json"}]},
            {"name": "B", "archive": b, "files": [{"from": "x.reds", "to": "R6/Scripts/A/a.reds"}]},
        ]}
        want = {"collections": [{"slug": "s", "revision": 1}], "choices": {}}
        rec = m.install(plan, root, "1091500", want)
        self.assertTrue(rec["complete"])
        self.assertEqual(m.resolve(root, "r6/scripts/A/a.reds").read_text(), "second")   # the later mod's, once
        self.assertEqual((root / "r6/config/options.json").read_text(), "modded")
        self.assertEqual(rec["replaced"], ["r6/config/options.json"])
        self.assertEqual(m.read_installed("1091500")["want"], want)
        m.uninstall(m.read_installed("1091500"))
        self.assertEqual((root / "r6/config/options.json").read_text(), "the game's own")
        self.assertEqual(sorted(p.name for p in (root / "r6").iterdir()), ["config"])   # emptied folders gone
        self.assertIsNone(m.read_installed("1091500"))

    def test_the_one_off_install_counts_as_installed(self):
        cache = self.base / "cache"
        (cache / "installed").mkdir(parents=True)
        (cache / "installed/1091500.json").write_text(json.dumps(
            {"collection": "iszwwe", "revision": 481, "backup": str(self.base / "bk"), "files": [], "replaced": []}))
        game = self.base / "steam/steamapps/common/Cyberpunk 2077"
        game.mkdir(parents=True)
        (self.base / "steam/steamapps/appmanifest_1091500.acf").write_text('"StateFlags" "4"\n"installdir" "Cyberpunk 2077"\n')
        real = m.game_dir
        m.game_dir = lambda appid, steam=None, heroic=None: real(appid, self.base / "steam")
        try:
            have = m.read_installed("1091500", cache)
        finally:
            m.game_dir = real
        self.assertEqual(have["want"], m.want_of({"collection": {"slug": "iszwwe", "revision": 481}}))
        self.assertEqual(have["root"], str(game))   # from Steam, for taking it out

    def test_a_game_taken_out_of_the_config_loses_its_mods(self):
        root = self.base / "game"
        root.mkdir()
        (root / "mod.archive").write_text("x")
        m.save_installed("1091500", {"appid": "1091500", "root": str(root), "want": {}, "files": ["mod.archive"],
                                     "replaced": [], "backup": str(self.base / "bk"), "complete": True})
        m.game_running = lambda appid, root=None: False
        self.assertEqual(m.cmd_sync({"cache": str(self.base / "cache"), "apiKeyFile": None, "games": {}}), 0)
        self.assertFalse((root / "mod.archive").exists())


def octodelta(commands):
    """An OctoDiff delta, as Wabbajack's patches are."""
    import struct
    out = b"OCTODELTA\x01" + bytes([4]) + b"SHA1" + struct.pack("<i", 20) + b"\0" * 20 + b">>>"
    for c in commands:
        if c[0] == "copy":
            out += b"\x60" + struct.pack("<qq", c[1], c[2])
        else:
            out += b"\x80" + struct.pack("<q", len(c[1])) + c[1]
    return out


class Wabbajack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        m.STATE = self.base / "state"
        self.cache = self.base / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def test_octodiff(self):
        base = b"Hello, Mojave!"
        self.assertEqual(m.octodiff(base, octodelta([("copy", 0, 7), ("data", b"Courier"), ("copy", 13, 1)])),
                         b"Hello, Courier!")

    def test_hash_like_wabbajack(self):
        f = self.base / "x"
        f.write_bytes(b"abc")
        self.assertEqual(m.wj_hash(f), m.wj_hash_bytes(b"abc"))
        self.assertEqual(len(m.base64.b64decode(m.wj_hash(f))), 8)

    def test_mo2_order_lowest_first(self):
        prof = self.base / "profiles/Default"
        prof.mkdir(parents=True)
        (prof / "modlist.txt").write_text("+Top\n-Off\n+Middle\n*DLC\n-Fixes_separator\n+Bottom\n")
        self.assertEqual(m.mo2_order(prof), ["Bottom", "Middle", "Top"])

    def build_list(self):
        """A tiny list: one download (with an archive inside it), an inline
        file, a patched file, MO2's own file (left out)."""
        dl = self.base / "dl"
        (dl / "inner").mkdir(parents=True)
        (dl / "inner/sky.dds").write_bytes(b"sky")
        inner = self.base / "Mojave Nights.fomod"
        subprocess.run([m.BSDTAR, "-c", "--format", "zip", "-f", str(inner), "-C", str(dl / "inner"), "sky.dds"], check=True)
        archive = self.base / "download.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("Mod/meshes/a.nif", b"mesh")
            z.writestr("Mod/a.ini", b"x=1\n")
            z.write(inner, "Mojave Nights.fomod")
        h = m.wj_hash(archive)
        patched = b"x=2\n"
        directives = [
            {"$type": "FromArchive", "ArchiveHashPath": [h, "Mod\\meshes\\a.nif"], "To": "mods\\A Mod\\meshes\\a.nif"},
            {"$type": "FromArchive", "ArchiveHashPath": [h, "Mojave Nights.fomod", "sky.dds"], "To": "mods\\A Mod\\textures\\sky.dds"},
            {"$type": "PatchedFromArchive", "ArchiveHashPath": [h, "Mod\\a.ini"], "PatchID": "p1",
             "Hash": m.wj_hash_bytes(patched), "To": "mods\\A Mod\\a.ini"},
            {"$type": "InlineFile", "SourceDataID": "i1", "To": "profiles\\Default\\modlist.txt"},
            {"$type": "InlineFile", "SourceDataID": "i2", "To": "ModOrganizer.ini"},
        ]
        modlist = {"Name": "Test List", "GameType": "FalloutNewVegas", "Directives": directives,
                   "Archives": [{"Hash": h, "Name": "download.zip", "Size": archive.stat().st_size,
                                 "State": {"$type": "NexusDownloader, Wabbajack.Lib", "GameName": "FalloutNewVegas",
                                           "ModID": 1, "FileID": 2}}]}
        wfile = m.wabbajack_file(self.cache, "list", 1)
        wfile.parent.mkdir(parents=True)
        with zipfile.ZipFile(wfile, "w") as z:
            z.writestr("modlist", json.dumps(modlist))
            z.writestr("i1", "+A Mod\n")
            z.writestr("i2", "[General]\n")
            z.writestr("p1", octodelta([("data", b"x=2\n")]))
        dest = m.wj_archive_file(self.cache, modlist["Archives"][0])
        dest.parent.mkdir(parents=True)
        shutil.copyfile(archive, dest)

    def test_build_and_plan(self):
        self.build_list()
        tree = m.build_wabbajack(self.cache, "list", 1)
        self.assertEqual((tree / "mods/A Mod/meshes/a.nif").read_bytes(), b"mesh")
        self.assertEqual((tree / "mods/A Mod/textures/sky.dds").read_bytes(), b"sky")   # from the archive inside
        self.assertEqual((tree / "mods/A Mod/a.ini").read_bytes(), b"x=2\n")             # patched
        self.assertFalse((tree / "ModOrganizer.ini").exists())                            # MO2's own: not needed
        mods = m.plan_wabbajack(self.cache, "list", 1)
        self.assertEqual([x["name"] for x in mods], ["A Mod"])
        self.assertEqual(sorted(f["to"] for f in mods[0]["files"]),
                         ["Data/a.ini", "Data/meshes/a.nif", "Data/textures/sky.dds"])

    def test_installs_from_the_built_folders_and_keeps_them(self):
        self.build_list()
        m.build_wabbajack(self.cache, "list", 1)
        root = self.base / "game"
        (root / "Data").mkdir(parents=True)
        plan = {"mods": m.plan_wabbajack(self.cache, "list", 1)}
        rec = m.install(plan, root, "22380", {})
        self.assertEqual((root / "Data/meshes/a.nif").read_bytes(), b"mesh")
        self.assertTrue((m.wj_tree(self.cache, "list", 1) / "mods/A Mod/meshes/a.nif").exists())   # linked, not moved
        self.assertEqual(len(rec["files"]), 3)


class Heroic(unittest.TestCase):
    def test_gog_game_and_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            heroic, game, prefix = Path(d) / "heroic", Path(d) / "Games/Fallout New Vegas", Path(d) / "Prefixes/FNV"
            (heroic / "gog_store").mkdir(parents=True)
            (heroic / "GamesConfig").mkdir()
            (prefix / "pfx/drive_c/users/steamuser").mkdir(parents=True)
            (heroic / "gog_store/installed.json").write_text(json.dumps(
                {"installed": [{"appName": "1454587428", "install_path": str(game), "platform": "windows"}]}))
            (heroic / "GamesConfig/1454587428.json").write_text(json.dumps({"1454587428": {"winePrefix": str(prefix)}}))
            self.assertEqual(m.game_dir("gog:1454587428", heroic=heroic), game)
            self.assertIsNone(m.game_dir("gog:1", heroic=heroic))
            self.assertEqual(m.prefix_of("gog:1454587428", game, heroic=heroic), prefix / "pfx")
            self.assertEqual(m.installed_file("gog:1454587428").name, "gog-1454587428.json")

    def test_steam_prefix_beside_its_library(self):
        root = Path("/lib/steamapps/common/Fallout New Vegas")
        self.assertEqual(m.prefix_of("22380", root), Path("/lib/steamapps/compatdata/22380"))


class NewVegas(unittest.TestCase):
    def test_ini_tweaks_merge(self):
        base = "[Archive]\nbInvalidateOlderFiles=0\nSArchiveList=a.bsa\n[Display]\niSize W=1280\n"
        out = m.ini_merge(base, "[Archive]\nbInvalidateOlderFiles=1\n[General]\nsLanguage=ENGLISH\n")
        self.assertIn("bInvalidateOlderFiles=1", out)
        self.assertNotIn("bInvalidateOlderFiles=0", out)
        self.assertIn("SArchiveList=a.bsa", out)
        self.assertIn("[General]\nsLanguage=ENGLISH", out)

    def test_empty_bsa(self):
        self.assertEqual(len(m.EMPTY_BSA), 36)
        self.assertEqual(m.EMPTY_BSA[:4], b"BSA\0")


if __name__ == "__main__":
    unittest.main()
