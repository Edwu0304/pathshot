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
import sys
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
            font=("Microsoft YaHei UI", 16),
        )

        # 尺寸標籤（拖曳時顯示寬×高，黑底白字）
        self.size_text = self.canvas.create_text(
            12, 60, text="", anchor="w", fill="white", font=("Microsoft YaHei UI", 14)
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
    """截圖預覽視窗：Canvas 顯示 + 註記工具（原子筆/螢光筆/直線/方框）。"""

    TOOL_PEN = "pen"
    TOOL_HIGHLIGHT = "highlight"
    TOOL_LINE = "line"
    TOOL_RECT = "rect"

    PEN_COLORS = ["#ff0000", "#0000ff", "#000000", "#ffff00", "#ffffff"]  # 紅/藍/黑/黃/白
    HL_COLORS = ["#ffff00", "#00ff00"]  # 黃/綠

    def __init__(self, master: tk.Tk, image, region: tuple[int, int, int, int]) -> None:
        self.master = master
        self.image = image
        self.region = region
        self.choice: str | None = None  # "save" / "retake" / "cancel"
        self.zoom = 1.4  # 縮放係數（1.0 = 原始適配）

        self._build_window()

        self.win.grab_set()

    def _build_window(self) -> None:
        """建立預覽視窗（依目前 zoom 重建）。"""
        self.win = tk.Toplevel(self.master)
        self.win.title("截圖預覽")
        self.win.attributes("-topmost", True)

        # 縮放顯示（zoom 倍率，限制最大 1000x650 * zoom）
        img_w, img_h = self.image.size
        base_scale = min(1.0, 1000 / img_w, 650 / img_h)
        self.scale = base_scale * self.zoom
        self.disp_w = max(1, int(img_w * self.scale))
        self.disp_h = max(1, int(img_h * self.scale))

        from PIL import ImageTk

        self.photo = ImageTk.PhotoImage(self.image.resize((self.disp_w, self.disp_h)))

        # 工具狀態
        self.tool = self.TOOL_PEN
        self.pen_color = self.PEN_COLORS[0]
        self.hl_color = self.HL_COLORS[0]
        self.draw_items: list[int] = []  # 目前一筆註記的 item
        self.all_annotations: list[tuple[list[int], list[tuple]]] = []  # (item_ids, ann_data) 供合成與復原
        self.start_x = 0
        self.start_y = 0

        # 工具列
        self._build_toolbar()

        # Canvas 疊圖
        self.canvas = tk.Canvas(self.win, width=self.disp_w, height=self.disp_h, highlightthickness=0)
        self.canvas.pack(padx=8, pady=(8, 0))
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        # 綁定繪圖事件
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # 尺寸資訊
        info = tk.Label(self.win, text=f"{img_w} × {img_h} 像素", font=("Microsoft YaHei UI", int(10 * self.zoom)))
        info.pack(pady=(4, 0))

        # 操作列 — 左邊主要動作，右邊剪貼簿說明
        bfont = ("Microsoft YaHei UI", int(13 * self.zoom))
        fs_small = ("Microsoft YaHei UI", int(10 * self.zoom))

        action_row = tk.Frame(self.win)
        action_row.pack(pady=14, padx=8, fill="x")

        # --- 主要動作 (左側) ---
        btn_group = tk.LabelFrame(action_row, text="操作", font=("Microsoft YaHei UI", int(11 * self.zoom)), padx=12, pady=8)
        btn_group.pack(side="left")

        save_btn = tk.Button(
            btn_group, text="✓ 確認儲存",
            font=(bfont[0], bfont[1], "bold"),
            command=self._save, padx=16, pady=5,
            bg="#2563eb", fg="white",
            activebackground="#1d4ed8", activeforeground="white",
        )
        save_btn.pack(side="left", padx=8)

        retake_btn = tk.Button(
            btn_group, text="↻ 重截", font=bfont,
            command=self._retake, padx=16, pady=5,
            activebackground="#e0e0e0",
        )
        retake_btn.pack(side="left", padx=8)

        cancel_btn = tk.Button(
            btn_group, text="✕ 取消", font=bfont,
            command=self._cancel, padx=16, pady=5,
            activebackground="#fee2e2", activeforeground="#991b1b",
        )
        cancel_btn.pack(side="left", padx=8)

        # --- 剪貼簿選項 (右側) ---
        clipboard_frame = tk.Frame(action_row)
        clipboard_frame.pack(side="right", fill="x", expand=True)

        tk.Label(
            clipboard_frame,
            text="儲存後複製到剪貼簿：",
            font=fs_small, fg="#475569",
        ).pack(anchor="e")

        # 二選一：路徑 / 圖片
        self.clipboard_mode = tk.StringVar(value="path")
        mode_frame = tk.Frame(clipboard_frame)
        mode_frame.pack(anchor="e", pady=(2, 0))
        tk.Radiobutton(
            mode_frame, text="📄 路徑", variable=self.clipboard_mode, value="path",
            font=fs_small, activebackground="#f1f5f9",
        ).pack(side="left", padx=4)
        tk.Radiobutton(
            mode_frame, text="🖼️ 圖片", variable=self.clipboard_mode, value="image",
            font=fs_small, activebackground="#f1f5f9",
        ).pack(side="left", padx=4)

        # 置中
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"+{x}+{y}")

    def _rebuild(self) -> None:
        """依目前 zoom 重建預覽視窗。"""
        # 若已有視窗，先銷毀
        if hasattr(self, "win") and self.win.winfo_exists():
            self.win.destroy()
        self._build_window()

    def _zoom_in(self) -> None:
        if self.zoom < 2.0:
            self.zoom = round(min(2.0, self.zoom + 0.25), 2)
            self._rebuild()

    def _zoom_out(self) -> None:
        if self.zoom > 1.0:
            self.zoom = round(max(1.0, self.zoom - 0.25), 2)
            self._rebuild()

    def _build_toolbar(self) -> None:
        """建立工具列：工具選擇、顏色選擇、註記動作、縮放控制。"""
        bar = tk.Frame(self.win, relief="sunken", bd=1)
        bar.pack(pady=(6, 6), padx=8, fill="x")

        fs = int(11 * self.zoom)
        fs_btn = ("Microsoft YaHei UI", fs)

        # --- 工具群組 (button-group style) ---
        tools_frame = tk.LabelFrame(bar, text="工具", font=fs_btn, padx=6, pady=4)
        tools_frame.pack(side="left", padx=(4, 2))

        self.tool_var = tk.StringVar(value=self.tool)
        self.tool_buttons: dict[str, tk.Radiobutton] = {}
        tools = [
            ("✏️ 原子筆", self.TOOL_PEN),
            ("🖍️ 螢光筆", self.TOOL_HIGHLIGHT),
            ("📏 直線", self.TOOL_LINE),
            ("▭ 方框", self.TOOL_RECT),
        ]
        for text, tool in tools:
            btn = tk.Radiobutton(
                tools_frame, text=text, value=tool, variable=self.tool_var,
                command=self._on_tool_change,
                font=fs_btn,
                indicatoron=False,
                relief="raised", bd=2,
                padx=10, pady=3,
            )
            btn.pack(side="left", padx=2, pady=1)
            self.tool_buttons[tool] = btn
        self._update_tool_buttons()

        # --- 顏色群組 ---
        color_frame = tk.LabelFrame(bar, text="顏色", font=fs_btn, padx=6, pady=4)
        color_frame.pack(side="left", padx=(2, 2))

        self.color_buttons: dict[str, tk.Button] = {}
        for color in self.PEN_COLORS:
            btn = tk.Button(
                color_frame, bg=color, fg=color,
                width=3, height=1,
                command=lambda c=color: self._set_pen_color(c),
                relief="raised", bd=2,
                highlightthickness=1, highlightbackground="#888888",
            )
            btn.pack(side="left", padx=2, pady=1)
            self.color_buttons[color] = btn
        self._update_color_buttons()

        # --- 註記動作 ---
        actions_frame = tk.LabelFrame(bar, text="註記", font=fs_btn, padx=6, pady=4)
        actions_frame.pack(side="left", padx=(2, 2))

        tk.Button(actions_frame, text="↩️ 復原", font=fs_btn,
                  command=self._undo, padx=8, pady=2,
                  activebackground="#e0e0e0").pack(side="left", padx=2)
        tk.Button(actions_frame, text="🧹 清除", font=fs_btn,
                  command=self._clear, padx=8, pady=2,
                  activebackground="#e0e0e0").pack(side="left", padx=2)

        # --- 縮放控制 (靠右) ---
        zoom_frame = tk.LabelFrame(bar, text="縮放", font=fs_btn, padx=6, pady=4)
        zoom_frame.pack(side="right", padx=(2, 4))

        tk.Button(zoom_frame, text="🔍 −", font=("Microsoft YaHei UI", int(13 * self.zoom)),
                  command=self._zoom_out, padx=10, pady=2,
                  activebackground="#e0e0e0").pack(side="left", padx=2)
        self.zoom_label = tk.Label(zoom_frame, text=f"{int(self.zoom * 100)}%",
                                   font=fs_btn)
        self.zoom_label.pack(side="left", padx=4)
        tk.Button(zoom_frame, text="🔍 +", font=("Microsoft YaHei UI", int(13 * self.zoom)),
                  command=self._zoom_in, padx=10, pady=2,
                  activebackground="#e0e0e0").pack(side="left", padx=2)

    def _update_tool_buttons(self) -> None:
        """更新工具按鈕的選中狀態顯示。"""
        fs = int(11 * self.zoom)
        for tool, btn in self.tool_buttons.items():
            if tool == self.tool:
                btn.configure(relief="sunken", font=("Microsoft YaHei UI", fs, "bold"))
            else:
                btn.configure(relief="raised", font=("Microsoft YaHei UI", fs))

    def _update_color_buttons(self) -> None:
        """更新顏色按鈕的選中狀態顯示。"""
        for color, btn in self.color_buttons.items():
            if color == self.pen_color:
                btn.configure(bd=3, relief="sunken", highlightthickness=2, highlightbackground="#0066cc")
            else:
                btn.configure(bd=2, relief="raised", highlightthickness=1, highlightbackground="#888888")

    def _on_tool_change(self) -> None:
        self.tool = self.tool_var.get()
        self._update_tool_buttons()

    def _set_pen_color(self, color: str) -> None:
        self.pen_color = color
        self._update_color_buttons()

    def _on_press(self, event) -> None:
        self.start_x = event.x
        self.start_y = event.y
        self.draw_items = []
        if self.tool in (self.TOOL_PEN, self.TOOL_HIGHLIGHT):
            color = self.pen_color if self.tool == self.TOOL_PEN else self.hl_color
            width = 2 if self.tool == self.TOOL_PEN else 12
            # 螢光筆半透明（stipple 點狀）
            item = self.canvas.create_line(
                event.x, event.y, event.x + 1, event.y + 1,
                fill=color, width=width,
                stipple="gray50" if self.tool == self.TOOL_HIGHLIGHT else "",
                capstyle="round", smooth=True,
            )
            self.draw_items.append(item)

    def _on_drag(self, event) -> None:
        if self.tool in (self.TOOL_PEN, self.TOOL_HIGHLIGHT):
            if self.draw_items:
                self.canvas.coords(self.draw_items[0], *self._append_point(event))
        elif self.tool == self.TOOL_LINE:
            self._draw_preview_line(event)
        elif self.tool == self.TOOL_RECT:
            self._draw_preview_rect(event)

    def _append_point(self, event) -> list:
        coords = list(self.canvas.coords(self.draw_items[0]))
        coords.extend([event.x, event.y])
        return coords

    def _draw_preview_line(self, event) -> None:
        if not self.draw_items:
            item = self.canvas.create_line(
                self.start_x, self.start_y, event.x, event.y,
                fill=self.pen_color, width=2,
            )
            self.draw_items.append(item)
        else:
            self.canvas.coords(self.draw_items[0], self.start_x, self.start_y, event.x, event.y)

    def _draw_preview_rect(self, event) -> None:
        if not self.draw_items:
            item = self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline=self.pen_color, width=2,
            )
            self.draw_items.append(item)
        else:
            self.canvas.coords(self.draw_items[0], self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event) -> None:
        # 記錄註記資料：(canvas item ids, 合成用資料) — 在視窗銷毀前抓取，避免 destroy 後不能讀取 canvas
        ann_data = []
        for item in self.draw_items:
            item_type = self.canvas.type(item)
            coords = tuple(self.canvas.coords(item))
            fill = self.canvas.itemcget(item, "fill")
            width = int(float(self.canvas.itemcget(item, "width") or 1))
            ann_data.append((item_type, coords, fill, width))
        self.all_annotations.append((list(self.draw_items), ann_data))

    def _undo(self) -> None:
        """復原最後一筆註記。"""
        if self.all_annotations:
            item_ids, _ = self.all_annotations.pop()
            for item in item_ids:
                self.canvas.delete(item)

    def _clear(self) -> None:
        """清除全部註記。"""
        for item_ids, _ in self.all_annotations:
            for item in item_ids:
                self.canvas.delete(item)
        self.all_annotations.clear()

    def _annotated_image(self):
        """將註記資料合成到 PIL 圖片（不需存取已銷毀的 canvas）。"""
        from PIL import Image, ImageDraw

        img = self.image.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        def to_img(c: float) -> int:
            return int(c / self.scale)

        for _, ann_data in self.all_annotations:
            for item_type, coords, fill, width in ann_data:
                if item_type == "line":
                    # 原子筆/螢光筆：連線段
                    points = [(to_img(x), to_img(y)) for x, y in zip(coords[::2], coords[1::2])]
                    if len(points) >= 2:
                        # 螢光筆（寬線）用半透明
                        alpha = 128 if width > 5 else 255
                        color = fill + hex(alpha)[2:].zfill(2) if fill.startswith("#") else fill
                        d.line(points, fill=color, width=max(1, int(width / self.scale)), joint="curve")
                elif item_type == "rectangle":
                    x1, y1, x2, y2 = coords
                    d.rectangle(
                        [to_img(x1), to_img(y1), to_img(x2), to_img(y2)],
                        outline=fill, width=max(1, int(width / self.scale)),
                    )

        return Image.alpha_composite(img, overlay).convert("RGB")

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

        # 設定視窗/工作列 icon（PyInstaller 打包後用 _MEIPASS 找 icon）
        self._set_window_icon(root)

        # 狀態標籤
        self.status_var = tk.StringVar(value="就緒")
        status = tk.Label(root, textvariable=self.status_var, font=("Microsoft YaHei UI", 14))
        status.pack(pady=(16, 8))

        # 截圖按鈕
        btn = tk.Button(
            root,
            text="📸 截圖",
            font=("Microsoft YaHei UI", 22),
            width=12,
            height=3,
            command=self.start_capture,
        )
        btn.pack(pady=12)

        # 輸出目錄欄位 + 瀏覽按鈕
        dir_frame = tk.Frame(root)
        dir_frame.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(dir_frame, text="輸出目錄:", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.dir_var = tk.StringVar(value=str(self.out_dir))
        dir_entry = tk.Entry(dir_frame, textvariable=self.dir_var, font=("Microsoft YaHei UI", 9), width=28)
        dir_entry.pack(side="left", padx=6, fill="x", expand=True)
        tk.Button(dir_frame, text="瀏覽…", font=("Microsoft YaHei UI", 10), command=self._browse_dir).pack(side="left")

        # 最近截圖路徑顯示
        self.path_var = tk.StringVar(value="")
        path_label = tk.Label(root, textvariable=self.path_var, font=("Microsoft YaHei UI", 9), fg="gray", wraplength=380)
        path_label.pack(pady=(6, 12))

        # 設定視窗尺寸並置中
        root.update_idletasks()
        w, h = 460, 250
        root.geometry(f"{w}x{h}")
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 3
        root.geometry(f"+{x}+{y}")

    def _set_window_icon(self, root: tk.Tk) -> None:
        """設定視窗/工作列 icon。"""
        try:
            # PyInstaller 打包時 icon 複製到 _MEIPASS；一般執行時在專案目錄
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
            icon_path = base / "pathshot_icon.ico"
            if icon_path.exists():
                root.iconbitmap(str(icon_path))
        except (tk.TclError, OSError):
            pass  # icon 設定失敗不影響功能

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
            # 儲存含註記的圖片
            annotated = preview._annotated_image()
            annotated.save(out_path, "PNG")

            import pyperclip
            from PIL import ImageTk

            path_text = str(out_path)
            mode = getattr(preview, "clipboard_mode", None)
            clipboard_mode = mode.get() if mode else "path"

            self.root.clipboard_clear()
            if clipboard_mode == "image":
                try:
                    photo = ImageTk.PhotoImage(annotated)
                    self._clipboard_photo = photo  # 保持參考避免被 GC
                    self.root.clipboard_append(photo, type="image")
                    self.status_var.set("已儲存，圖片已複製到剪貼簿")
                except tk.TclError:
                    # fallback: 複製路徑
                    self.root.clipboard_append(path_text)
                    self.status_var.set("已儲存，路徑已複製 (圖片複製失敗)")
            else:
                # clipboard_mode == "path"
                self.root.clipboard_append(path_text)
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
