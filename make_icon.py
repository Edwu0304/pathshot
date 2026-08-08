"""產生多尺寸 ICO：手動組 ICONDIR + PNG 影像（最可靠，不依賴 Pillow 的 ICO 儲存）。"""
import struct
import io
from PIL import Image

SIZES = [16, 24, 32, 48, 64, 128, 256]


def make_frames():
    base = Image.open("pathshot_icon.png").convert("RGBA")
    frames = []
    for s in SIZES:
        img = base.resize((s, s), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        frames.append(buf.getvalue())
    return frames


def write_ico(path: str, frames: list[bytes]):
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = b""
    datas = b""
    for i, s in enumerate(SIZES):
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        entries += struct.pack(
            "<BBBBHHII", w, h, 0, 0, 1, 32, len(frames[i]), offset
        )
        datas += frames[i]
        offset += len(frames[i])
    with open(path, "wb") as f:
        f.write(header + entries + datas)


if __name__ == "__main__":
    frames = make_frames()
    write_ico("pathshot_icon.ico", frames)
    import os
    print(f"已產生多尺寸 ICO: {os.path.getsize('pathshot_icon.ico')} bytes, 尺寸: {SIZES}")
