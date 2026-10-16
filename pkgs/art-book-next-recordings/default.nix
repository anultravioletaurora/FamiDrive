# The Recordings system's look in Art Book Next (ES-DE edition), which
# has none: files laid out as in the theme, for frontend.nix to add to it
# (famidrive.esde.themeExtras).
#
#   - its logo, from the same author's Batocera edition (art-book-next-es),
#     which has a Recordings system
#   - the outline schemes' art: the theme's own default band in a light
#     red, with a record button on it (outline.py)
#   - the Original and Screenshots schemes' art: the Batocera edition's
#     photo
#   - its name and colors (_metadata-global), a light red like its art
#
# Like the theme itself, the Batocera edition states no license: its files
# are fetched from the author, never copied into this repo.
{ lib, runCommand, fetchurl, python3, theme }:

let
  rev = "9a50ef366e750aabfab29e6915a2867607212971";   # 2026-03-12
  file = path: hash: fetchurl {
    url = "https://raw.githubusercontent.com/anthonycaccese/art-book-next-es/${rev}/_inc/systems/${path}";
    inherit hash;
  };
  logo = file "logos/recordings.svg" "sha256-9NMbXWQkY4yYIqcRuNBHPm1yVXWfvoTOM4fUGj6THJo=";
  photo = file "artwork-default/recordings.png" "sha256-bf6DBRgDWdRTa59iTOAfksJbsTGeavhaXGghIlCHfn4=";

  metadata = builtins.toFile "recordings.xml" ''
    <theme>
        <variables>
            <systemName>Recordings</systemName>
            <systemDescription>Videos recorded on this box from the Guide menu: Start recording, then Stop recording when done. Each is named by when it started.</systemDescription>
            <systemManufacturer>FamiDrive</systemManufacturer>
            <systemReleaseYear />
            <systemReleaseDate />
            <systemReleaseDateFormated />
            <systemHardwareType>Folder</systemHardwareType>
            <systemCoverSize>1-1</systemCoverSize>
            <systemCoverSizeType>square</systemCoverSizeType>
            <systemColor>E06666</systemColor>
            <systemColorPalette1>E06666</systemColorPalette1>
            <systemColorPalette2>EA9999</systemColorPalette2>
            <systemColorPalette3>CC4125</systemColorPalette3>
            <systemColorPalette4>990000</systemColorPalette4>
            <systemCartSize>1-1</systemCartSize>
        </variables>
    </theme>
  '';
in
runCommand "art-book-next-recordings" {
  nativeBuildInputs = [ (python3.withPackages (ps: [ ps.pillow ])) ];
} ''
  s=$out/_inc/systems
  mkdir -p $s/logos $s/_metadata-global $s/artwork $s/artwork-screenshots $s/artwork-outline
  cp ${logo} $s/logos/recordings.svg
  cp ${photo} $s/artwork/recordings.png
  cp ${photo} $s/artwork-screenshots/recordings.png
  cp ${metadata} $s/_metadata-global/recordings.xml
  python3 ${./outline.py} ${theme}/_inc/systems/artwork-outline/_default.png $s/artwork-outline/recordings.png
''
