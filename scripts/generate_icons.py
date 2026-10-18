"""生成 PWA 所需的 PNG 图标（开发期一次性脚本）。

运行：python scripts/generate_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def make_icon(size, path):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=int(size * 0.21),
        fill=(196, 102, 74, 255),
    )

    pad_x = int(size * 0.18)
    top = int(size * 0.22)
    bottom = int(size * 0.78)
    draw.rounded_rectangle(
        [pad_x, top, size - pad_x, bottom],
        radius=int(size * 0.085),
        fill=(250, 248, 245, 255),
    )

    width = max(2, int(size * 0.072))
    points = [
        (int(size * 0.34), int(size * 0.52)),
        (int(size * 0.45), int(size * 0.63)),
        (int(size * 0.68), int(size * 0.38)),
    ]
    draw.line(points, fill=(122, 155, 118, 255), width=width, joint="curve")

    image.save(path, "PNG")


if __name__ == "__main__":
    make_icon(192, STATIC_DIR / "icon-192.png")
    make_icon(512, STATIC_DIR / "icon-512.png")
    print("icons generated:", STATIC_DIR)
