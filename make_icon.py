"""產生 Pathshot 專屬 icon。

設計：藍色圓角方形底 + 白色相機圖示 + 路徑箭頭（截圖 + 路徑）。
"""
from PIL import Image, ImageDraw


def make_icon(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 背景：圓角方形（深藍漸層感，用純色）
    margin = size // 16
    d.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 8,
        fill=(37, 99, 235, 255),  # 鮮明藍
    )

    # 相機機身
    body_w, body_h = size * 0.6, size * 0.42
    bx0 = (size - body_w) / 2
    by0 = size * 0.32
    d.rounded_rectangle(
        [bx0, by0, bx0 + body_w, by0 + body_h],
        radius=size // 16,
        fill=(255, 255, 255, 255),
    )

    # 相機頂部突起
    top_w, top_h = size * 0.22, size * 0.08
    tx0 = (size - top_w) / 2
    d.rounded_rectangle(
        [tx0, by0 - top_h, tx0 + top_w, by0],
        radius=size // 40,
        fill=(255, 255, 255, 255),
    )

    # 鏡頭外圈
    lens_r = size * 0.13
    cx, cy = size / 2, by0 + body_h / 2
    d.ellipse([cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r], fill=(37, 99, 235, 255))

    # 鏡頭內圈
    lens_r2 = size * 0.07
    d.ellipse([cx - lens_r2, cy - lens_r2, cx + lens_r2, cy + lens_r2], fill=(255, 255, 255, 255))

    # 路徑箭頭（從相機右下延伸，象徵「複製路徑」）
    arrow_color = (255, 255, 255, 255)
    ax0, ay0 = size * 0.62, size * 0.72
    ax1, ay1 = size * 0.85, size * 0.88
    d.line([ax0, ay0, ax1, ay1], fill=arrow_color, width=size // 24)
    # 箭頭頭
    ah = size // 18
    d.polygon(
        [
            (ax1, ay1),
            (ax1 - ah, ay1 - ah // 2),
            (ax1 - ah // 2, ay1 - ah),
        ],
        fill=arrow_color,
    )

    return img


if __name__ == "__main__":
    icon = make_icon(256)
    icon.save("pathshot_icon.png")
    icon.save("pathshot_icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("已產生 pathshot_icon.png / pathshot_icon.ico")
