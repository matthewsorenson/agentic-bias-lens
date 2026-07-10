"""Burn an 'AI-GENERATED' banner into every surfaced image and strip metadata.

No generated image may circulate without a visible mark that it is synthetic.
finalize_image() is the single entry point adapters use so the guarantee cannot
be bypassed.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_BANNER = "AI-GENERATED IMAGE - RESEARCH OUTPUT"


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def strip_and_reencode(src: str | Path, dst: str | Path) -> Path:
    """Copy pixels into a fresh image so no EXIF/ICC/text metadata survives."""
    with Image.open(src) as im:
        im = im.convert("RGB")
        clean = Image.new("RGB", im.size)
        clean.putdata(list(im.getdata()))
    dst = Path(dst)
    clean.save(dst, format="PNG")
    return dst


def watermark(src: str | Path, dst: str | Path, text: str = DEFAULT_BANNER) -> Path:
    with Image.open(src) as im:
        im = im.convert("RGB").copy()
    w, h = im.size
    band_h = max(14, h // 10)
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, h - band_h, w, h], fill=(0, 0, 0))
    font = _load_font(max(8, band_h - 6))
    draw.text((4, h - band_h + 2), text, fill=(255, 255, 255), font=font)
    dst = Path(dst)
    im.save(dst, format="PNG")
    return dst


def finalize_image(src: str | Path, dst: str | Path, banner: str = DEFAULT_BANNER) -> Path:
    """Strip metadata then burn the banner. The only sanctioned way to surface an image."""
    dst = Path(dst)
    tmp = dst.with_name(dst.stem + ".tmp.png")
    strip_and_reencode(src, tmp)
    watermark(tmp, dst, banner)
    tmp.unlink(missing_ok=True)
    return dst
