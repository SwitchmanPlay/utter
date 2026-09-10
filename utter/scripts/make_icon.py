"""Regenerate assets/icon.png + icon.ico from scratch with Pillow (no external assets)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"


def render(size: int) -> Image.Image:
    s = size * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = s * 0.22
    # background rounded square, indigo
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=r, fill=(124, 140, 255, 255))
    # sound-wave bars (the "utterance")
    bars = [0.30, 0.55, 0.85, 0.55, 0.30]
    n = len(bars)
    gap = s * 0.055
    bw = s * 0.09
    total = n * bw + (n - 1) * gap
    x = (s - total) / 2
    cy = s / 2
    for h in bars:
        bh = s * 0.62 * h
        d.rounded_rectangle((x, cy - bh / 2, x + bw, cy + bh / 2), radius=bw / 2, fill=(13, 15, 22, 255))
        x += bw + gap
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {sz: render(sz) for sz in sizes}
    imgs[256].save(OUT / "icon.png")
    imgs[256].save(OUT / "icon.ico", sizes=[(sz, sz) for sz in sizes], append_images=[imgs[sz] for sz in sizes[:-1]])
    print("wrote", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()
