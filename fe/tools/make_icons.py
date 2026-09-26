#!/usr/bin/env python3
"""Regenerate fe/images/ icon set from a single source logo.

Authoring-time tool only — NOT part of the FE runtime and NOT run by CI, so the
"FE is zero-dep" rule (see root CLAUDE.md) is unaffected: nothing the browser
loads depends on this, and no workflow installs Pillow. Run it by hand after
replacing the source logo, then commit the regenerated PNGs.

    pip install Pillow
    python fe/tools/make_icons.py [path/to/new-logo.png]

Default source is logo.png at the REPO ROOT — that is the drop point for a new
brand mark, kept at full export resolution and never written to by this script.
Everything under fe/images/ is derived output and is overwritten on each run, so
never point the source at one of those files. The source is
cropped to its own alpha bounding box and re-padded to a centred square before
downscaling, so an off-centre or unevenly padded export still renders centred at
16px — the raw 1254x1254 export this was built from had its art sitting at
(82,53)-(1234,1212), which reads visibly off-centre once shrunk to a favicon.
"""
import sys
from pathlib import Path

from PIL import Image

FE = Path(__file__).resolve().parent.parent
ROOT = FE.parent
IMAGES = FE / "images"

# name -> edge length in px. Every consumer of these is listed in
# .claude/rules/DESIGN.md §13.11.
SIZES = {
    "favicon-16x16.png": 16,
    "favicon-32x32.png": 32,
    "icon-80.png": 80,          # kept for a future 80px slot; no consumer since
                                # the Excel add-in was removed 2026-09-25
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,        # PWA manifest + site header brand mark
    "icon-512.png": 512,        # PWA manifest, JSON-LD logo, msapplication tile
}

# Breathing room around the art inside the square canvas, as a fraction of the
# longest edge. Favicons look cramped flush to the edge; 4% is enough without
# shrinking the mark noticeably.
MARGIN = 0.04

# Social-card background — the site's own surface colour (--ivory in fe/style.css),
# so the card reads as part of the site rather than a cut-out on white.
OG_BACKGROUND = (250, 249, 245, 255)


def square_canvas(src: Image.Image) -> Image.Image:
    src = src.convert("RGBA")
    box = src.split()[3].getbbox() or src.getbbox()
    art = src.crop(box)
    edge = int(max(art.size) * (1 + 2 * MARGIN))
    canvas = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    canvas.paste(art, ((edge - art.width) // 2, (edge - art.height) // 2))
    return canvas


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logo.png"
    if not source.exists():
        sys.exit(f"source logo not found: {source}")

    IMAGES.mkdir(parents=True, exist_ok=True)
    master = square_canvas(Image.open(source))
    print(f"source {source} -> squared {master.size}")

    for name, edge in sorted(SIZES.items(), key=lambda kv: kv[1]):
        out = IMAGES / name
        master.resize((edge, edge), Image.LANCZOS).save(out, optimize=True)
        print(f"  {name:<22} {edge:>4}px  {out.stat().st_size:>7,} bytes")

    # Social card. NOT a square copy of the logo: _layout_head.html declares
    # og:image:width=1200 / og:image:height=630, and a square image under a 1.91:1
    # declaration gets letterboxed or centre-cropped by every scraper. Compose the
    # mark on the site's own surface colour at exactly the declared size instead.
    #
    # Named og-card.png, not logo.png, on purpose: .gitignore carries a bare
    # `logo.png` rule ("stray assets — keep OUT of this PUBLIC repo") which matches
    # at ANY depth, so an fe/images/logo.png would never be committed and would
    # 404 in production, where deploy.yml git-resets the box to the committed tree.
    card = Image.new("RGBA", (1200, 630), OG_BACKGROUND)
    mark = master.resize((int(630 * 0.62),) * 2, Image.LANCZOS)
    card.alpha_composite(mark, ((1200 - mark.width) // 2, (630 - mark.height) // 2))
    out = IMAGES / "og-card.png"
    card.convert("RGB").save(out, optimize=True)
    print(f"  {'og-card.png':<22} 1200x630  {out.stat().st_size:>7,} bytes")


if __name__ == "__main__":
    main()
