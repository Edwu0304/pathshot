"""分類：supported（正式支援）。

UI 版區域截圖工具。

- 常駐 UI 視窗，含「截圖」按鈕
- 點按鈕 → 隱藏 UI → 拖曳框選區域 → 存 PNG → 自動複製檔案路徑 → 回到 UI
- 依賴：mss, Pillow, pyperclip（tkinter 內建）
"""

from __future__ import annotations

import argparse
import datetime
import json
import tkinter as tk
from pathlib import Path

DEFAULT_OUT_DIR = Path(r"D:\repo\Others\screenshot\Source")
CONFIG_PATH = Path(__file__).parent / "screenshot_config.json"


def load_config() -> dict:
    """讀取設定檔（記住上次輸出目錄）。"""
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_config(config: dict) -> None:
    """儲存設定檔。"""
    try:
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


class RegionSelector:
    """全螢幕 overlay，讓使用者拖曳框選區域。"""

    def __init__(self, master: tk.Tk) -> None:
        self.root = tk.Toplevel(master)
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="crosshair")
        # 幾乎透明遮罩：底下畫面清楚可見，但仍接收拖曳事件
        self.root.attributes("-alpha", 0.05)

        self.canvas = tk.Canvas(self.root, cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.start_x = 0
        self.start_y = 0
        self.rect = None
        self.region: tuple[int, int, int, int] | None = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self._cancel())

        # 提示文字（黑底白字，幾乎透明遮罩下仍可讀）
        self.canvas.create_rectangle(0, 8, 320, 52, fill="black", outline="")
        self.canvas.create_text(
            12,
            30,
            text="拖曳選取區域（Esc 取消）",
            anchor="w",
            fill="white",
            font=("Arial", 16),
        )

        # 尺寸標籤（拖曳時顯示寬×高，黑底白字）
        self.size_text = self.canvas.create_text(
            12, 60, text="", anchor="w", fill="white", font=("Arial", 14)
        )
        self.size_bg = None

    def _update_size_label(self) -> None:
        if self.rect is None:
            return
        coords = self.canvas.coords(self.rect)
        if len(coords) < 4:
            return
        x1, y1, x2, y2 = coords
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        label = f"{w} × {h}"
        if self.size_bg is None:
            self.size_bg = self.canvas.create_rectangle(0, 52, 260, 82, fill="black", outline="")
            self.canvas.tag_raise(self.size_bg)
        self.canvas.itemconfigure(self.size_text, text=label)
        self.canvas.tag_raise(self.size_text)

    def _on_press(self, event) -> None:
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#1a1a4a",  # 深藍黑，明顯易辨識
            width=5,  # 粗線
            fill="#1a1a4a",  # 半透明填色（配合遮罩 alpha 呈現淡色）
        )

    def _on_drag(self, event) -> None:
        if self.rect is not None:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x_root, event.y_root)
            self._update_size_label()

    def _on_release(self, event) -> None:
        left = min(self.start_x, event.x_root)
        top = min(self.start_y, event.y_root)
        right = max(self.start_x, event.x_root)
        bottom = max(self.start_y, event.y_root)
        width = right - left
        height = bottom - top
        if width > 0 and height > 0:
            self.region = (left, top, width, height)
        self.root.destroy()

    def _cancel(self) -> None:
        self.region = None
        self.root.destroy()

    def run(self) -> tuple[int, int, int, int] | None:
        self.root.wait_window()
        return self.region


def capture_region_image(region: tuple[int, int, int, int]):
    """用 mss 擷取指定區域，回傳 PIL Image（不存檔）。"""
    import mss
    from PIL import Image

    left, top, width, height = region
    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


class PreviewWindow:
    """截圖預覽視窗：顯示截圖，提供「確認儲存」與「重截」按鈕。"""

    def __init__(self, master: tk.Tk, image, region: tuple[int, int, int, int]) -> None:
        self.master = master
        self.image = image
        self.region = region
        self.choice: str | None = None  # "save" / "retake"

        self.win = tk.Toplevel(master)
        self.win.title("截圖預覽")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)

        # 縮放顯示（限制最大 900x600）
        max_w, max_h = 900, 600
        img_w, img_h = image.size
        scale = min(1.0, max_w / img_w, max_h / img_h)
        display_size = (int(img_w * scale), int(img_h * scale))

        from PIL import ImageTk

        self.photo = ImageTk.PhotoImage(image.resize(display_size))
        img_label = tk.Label(self.win, image=self.photo)
        img_label.pack(padx=8, pady=8)

        # 尺寸資訊
        info = tk.Label(self.win, text=f"{img_w} × {img_h} 像素", font=("Arial", 10))
        info.pack()

        # 按鈕列
        btn_frame = tk.Frame(self.win)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="✓ 確認儲存", font=("Arial", 12), command=self._save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="↻ 重截", font=("Arial", 12), command=self._retake).pack(side="left", padx=6)
        tk.Button(btn_frame, text="✕ 取消", font=("Arial", 12), command=self._cancel).pack(side="left", padx=6)

        # 置中
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"+{x}+{y}")

        self.win.grab_set()  # 強制焦點

    def _save(self) -> None:
        self.choice = "save"
        self.win.destroy()

    def _retake(self) -> None:
        self.choice = "retake"
        self.win.destroy()

    def _cancel(self) -> None:
        self.choice = "cancel"
        self.win.destroy()

    def run(self) -> str | None:
        self.win.wait_window()
        return self.choice


def timestamp_name() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class ScreenshotApp:
    """主 UI 視窗。"""

    def __init__(self, root: tk.Tk, out_dir: Path) -> None:
        self.root = root

        # 載入上次記住的輸出目錄
        config = load_config()
        saved = str(config.get("output_dir", "") or "").strip()
        self.out_dir = Path(saved) if saved else out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

        root.title("截圖工具")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        # 狀態標籤
        self.status_var = tk.StringVar(value="就緒")
        status = tk.Label(root, textvariable=self.status_var, font=("Arial", 14))
        status.pack(pady=(16, 8))

        # 截圖按鈕
        btn = tk.Button(
            root,
            text="📸 截圖",
            font=("Arial", 22),
            width=12,
            height=3,
            command=self.start_capture,
        )
        btn.pack(pady=12)

        # 輸出目錄欄位 + 瀏覽按鈕
        dir_frame = tk.Frame(root)
        dir_frame.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(dir_frame, text="輸出目錄:", font=("Arial", 10)).pack(side="left")
        self.dir_var = tk.StringVar(value=str(self.out_dir))
        dir_entry = tk.Entry(dir_frame, textvariable=self.dir_var, font=("Arial", 9), width=28)
        dir_entry.pack(side="left", padx=6, fill="x", expand=True)
        tk.Button(dir_frame, text="瀏覽…", font=("Arial", 10), command=self._browse_dir).pack(side="left")

        # 最近截圖路徑顯示
        self.path_var = tk.StringVar(value="")
        path_label = tk.Label(root, textvariable=self.path_var, font=("Arial", 9), fg="gray", wraplength=380)
        path_label.pack(pady=(6, 12))

        # 設定視窗尺寸並置中
        root.update_idletasks()
        w, h = 460, 250
        root.geometry(f"{w}x{h}")
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 3
        root.geometry(f"+{x}+{y}")

    def _browse_dir(self) -> None:
        """開啟目錄選擇對話框，並記住選的路徑。"""
        from tkinter import filedialog

        initial = str(self.dir_var.get()).strip() or str(self.out_dir)
        chosen = filedialog.askdirectory(initialdir=initial, title="選擇截圖輸出目錄")
        if chosen:
            self.out_dir = Path(chosen)
            self.out_dir.mkdir(parents=True, exist_ok=True)
            self.dir_var.set(str(self.out_dir))
            save_config({"output_dir": str(self.out_dir)})

    def start_capture(self) -> None:
        while True:
            # 隱藏主視窗，避免擋住框選與被截進畫面
            self.root.withdraw()
            self.root.update()

            selector = RegionSelector(self.root)
            region = selector.run()

            if region is None:
                self.root.deiconify()
                self.root.lift()
                self.status_var.set("已取消")
                return

            # 先截圖（UI 保持隱藏，不會被截進畫面）
            image = capture_region_image(region)

            # 截圖完成後才恢復主視窗
            self.root.deiconify()
            self.root.lift()

            preview = PreviewWindow(self.root, image, region)
            choice = preview.run()

            if choice == "retake":
                continue  # 重截（下一輪會再次隱藏 UI）
            if choice == "cancel":
                self.status_var.set("已取消")
                return

            # choice == "save"
            # 同步目前 UI 欄位顯示的輸出目錄（支援手動編輯）
            current_dir = str(self.dir_var.get()).strip()
            if current_dir:
                self.out_dir = Path(current_dir)
                self.out_dir.mkdir(parents=True, exist_ok=True)
                save_config({"output_dir": str(self.out_dir)})

            out_path = self.out_dir / f"{timestamp_name()}.png"
            image.save(out_path, "PNG")

            import pyperclip

            path_text = str(out_path)
            pyperclip.copy(path_text)

            self.status_var.set("已儲存，路徑已複製")
            self.path_var.set(path_text)
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="UI 版區域截圖工具")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="輸出目錄")
    args = parser.parse_args()

    root = tk.Tk()
    ScreenshotApp(root, Path(args.out))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
