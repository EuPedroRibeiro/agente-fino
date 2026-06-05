from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = PROJECT_ROOT / "app" / "static" / "brand"
STATIC_DIR = PROJECT_ROOT / "app" / "static"


def crop_by_ratio(image: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = box
    return image.crop((round(left * width), round(top * height), round(right * width), round(bottom * height)))


def remove_edge_background(image: Image.Image, threshold: int = 245) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    def is_background(x: int, y: int) -> bool:
        r, g, b, _ = pixels[x, y]
        return r >= threshold and g >= threshold and b >= threshold

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or not (0 <= x < width and 0 <= y < height):
            continue
        visited.add((x, y))
        if not is_background(x, y):
            continue
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    return rgba


def fit_contain(image: Image.Image, size: tuple[int, int], background: tuple[int, int, int, int] = (255, 255, 255, 0)) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, background)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def make_og(full_logo: Image.Image, symbol: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (1200, 630), (251, 251, 251, 255))
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((725, 70, 1085, 430), fill=(229, 9, 20, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(42))
    canvas.alpha_composite(glow)

    full = fit_contain(full_logo, (900, 260))
    canvas.alpha_composite(full, ((1200 - full.width) // 2, 145))

    small = fit_contain(symbol, (138, 138))
    canvas.alpha_composite(small, (80, 430))
    draw = ImageDraw.Draw(canvas)
    draw.text((240, 466), "Pensa. Organiza. Resolve.", fill=(110, 110, 110, 255))
    return canvas.convert("RGB")


def save_png(image: Image.Image, path: Path, size: tuple[int, int] | None = None) -> None:
    output = fit_contain(image, size) if size else image
    output.save(path, "PNG", optimize=True)


def generate_assets(source: Path) -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGB")

    full_logo = remove_edge_background(crop_by_ratio(image, (0.105, 0.235, 0.955, 0.555)))
    symbol = remove_edge_background(crop_by_ratio(image, (0.105, 0.225, 0.365, 0.57)))
    reduced = remove_edge_background(crop_by_ratio(image, (0.405, 0.755, 0.562, 0.97)))
    mono = remove_edge_background(crop_by_ratio(image, (0.665, 0.765, 0.842, 0.975)))

    save_png(full_logo, BRAND_DIR / "agente-fino-logo-full.png", (980, 320))
    save_png(symbol, BRAND_DIR / "agente-fino-symbol.png", (512, 512))
    save_png(reduced, BRAND_DIR / "agente-fino-symbol-reduced.png", (512, 512))
    save_png(mono, BRAND_DIR / "agente-fino-symbol-mono.png", (512, 512))
    make_og(full_logo, symbol).save(BRAND_DIR / "agente-fino-og.png", "PNG", optimize=True)

    icon = fit_contain(reduced, (512, 512), (255, 255, 255, 0))
    fit_contain(reduced, (180, 180), (255, 255, 255, 0)).save(STATIC_DIR / "apple-touch-icon.png", "PNG", optimize=True)
    icon.save(
        STATIC_DIR / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Agente Fino brand assets from a source brand sheet.")
    parser.add_argument("source", type=Path, help="Path to the source PNG/JPG brand sheet.")
    args = parser.parse_args()
    generate_assets(args.source)


if __name__ == "__main__":
    main()
