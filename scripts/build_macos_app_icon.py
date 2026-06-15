from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "packaging" / "pyinstaller"
DEFAULT_SOURCE = DEFAULT_OUTPUT_DIR / "lattice-icon-source.png"
ICONSET_SIZES = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]


def _clamp(value: float) -> int:
    return max(0, min(255, round(value)))


def _estimate_background(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    samples = [
        rgb.getpixel((8, 8)),
        rgb.getpixel((width - 9, 8)),
        rgb.getpixel((8, height - 9)),
        rgb.getpixel((width - 9, height - 9)),
    ]
    return tuple(round(sum(pixel[channel] for pixel in samples) / len(samples)) for channel in range(3))


def _remove_light_gallery_background(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    bg = _estimate_background(rgb)
    out = Image.new("RGBA", rgb.size)
    pixels: list[tuple[int, int, int, int]] = []

    source_pixels = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
    for r, g, b in source_pixels:
        distance = max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2]))
        alpha = _clamp((distance - 8) * 7)
        if r > 170 and g > 170 and b > 170:
            alpha = 0
        if alpha == 0:
            pixels.append((0, 0, 0, 0))
            continue
        if alpha < 255:
            a = alpha / 255
            r = _clamp((r - bg[0] * (1 - a)) / a)
            g = _clamp((g - bg[1] * (1 - a)) / a)
            b = _clamp((b - bg[2] * (1 - a)) / a)
        pixels.append((r, g, b, alpha))

    out.putdata(pixels)
    return out


def build_icon_png(source_path: Path = DEFAULT_SOURCE, size: int = 1024) -> Image.Image:
    if not source_path.exists():
        raise FileNotFoundError(f"Missing icon source image: {source_path}")
    source = Image.open(source_path)
    icon = _remove_light_gallery_background(source)
    return icon.resize((size, size), Image.Resampling.LANCZOS)


def build_icon(output_dir: Path = DEFAULT_OUTPUT_DIR, source_path: Path = DEFAULT_SOURCE) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_png = output_dir / "lattice-icon.png"
    icns_path = output_dir / "lattice.icns"
    iconset_dir = output_dir / "lattice.iconset"

    source = build_icon_png(source_path)
    source.save(source_png)

    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir()
    for size, filename in ICONSET_SIZES:
        resized = source.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / filename)

    subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)], check=True)
    shutil.rmtree(iconset_dir)
    return source_png, icns_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the macOS app icon assets for Lattice.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for PNG and ICNS outputs.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Generated source image to convert into app icons.")
    args = parser.parse_args()
    source_png, icns_path = build_icon(Path(args.output_dir), Path(args.source))
    print(f"source_png={source_png}")
    print(f"icns={icns_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
