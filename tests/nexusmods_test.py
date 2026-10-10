"""famidrive-nexusmods: where a collection's files go, without Nexus Mods.

    python3 nexusmods_test.py path/to/famidrive_nexusmods.py

The cases are from Welcome to Night City (Cyberpunk 2077), revision 480,
checked against Vortex on the first box 2026-10-10: these rules put 265
of its 268 mods where Vortex did, and the other three Vortex left empty.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_nexusmods", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

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

    def test_a_game_without_rules(self):
        self.assertEqual(m.place({"domainName": "stardewvalley"}, ["Mod/manifest.json"]), ("unknown", []))

    def test_only_nexus_files_are_fetched(self):
        nexus, other = m.nexus_mods({"mods": [{"source": {"type": "nexus"}}, {"source": {"type": "browse"}}]})
        self.assertEqual((len(nexus), len(other)), (1, 1))

    def test_compare_with_vortex(self):
        plan = {"mods": [{"files": [{"from": "a", "to": "archive/pc/mod/A.archive"}, {"from": "b", "to": "r6/b.reds"}]}]}
        c = m.compare(plan, {"files": [{"relPath": "archive\\pc\\mod\\a.archive"}, {"relPath": "bin\\x.dll"}]})
        self.assertEqual((c["both"], c["onlyPlan"], c["onlyVortex"]), (1, ["r6/b.reds"], ["bin/x.dll"]))


if __name__ == "__main__":
    unittest.main()
