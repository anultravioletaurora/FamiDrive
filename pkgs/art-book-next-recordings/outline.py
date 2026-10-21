"""The Recordings system's art for Art Book Next's outline schemes.

    python3 outline.py THEME/_inc/systems/artwork-outline/_default.png OUT.png

The outline schemes' art is a slanted band of the system's color with a
white doodle on it. The theme has none for recordings, and its fallback
is a blue band with a controller on it, the same as Controllers', so the
two looked alike (first box, 2026-10-16). This is that band in a light
red, with a record button (a ring around a dot) in place of the
controller, in the doodle's white and about where it sits.
"""

import sys

from PIL import Image, ImageDraw

RED = (224, 102, 102)
WHITE = (231, 232, 232)   # the doodles' white
SCALE = 4                 # drawn this much larger, then scaled down, for smooth edges


def main(src: str, out: str) -> None:
    im = Image.open(src).convert("RGBA")
    shape = im.getchannel("A")
    art = Image.new("RGBA", im.size, (*RED, 255))
    art.putalpha(shape)

    w, h = im.size
    k = SCALE
    mark = Image.new("L", (w * k, h * k), 0)
    d = ImageDraw.Draw(mark)
    cx, cy = 255 * k, 830 * k
    ring, dot, stroke = 82 * k, 44 * k, 9 * k
    d.ellipse((cx - ring, cy - ring, cx + ring, cy + ring), outline=255, width=stroke)
    d.ellipse((cx - dot, cy - dot, cx + dot, cy + dot), fill=255)
    mark = mark.resize((w, h), Image.Resampling.LANCZOS)

    # Only on the band, never past its edges.
    inside = shape.point(lambda a: 255 if a > 0 else 0)
    white = Image.new("RGBA", im.size, (*WHITE, 255))
    white.putalpha(Image.composite(mark, Image.new("L", im.size, 0), inside))
    art.alpha_composite(white)
    art.save(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
