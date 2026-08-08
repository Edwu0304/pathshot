# Pathshot

**Pathshot** — 區域截圖工具，截圖後**自動複製檔案路徑到剪貼簿**，專為 CLI agent / AI 工作流設計。

## 為什麼做這個？

CLI agent（如 Command Code、Claude Code）看不到螢幕截圖，但能讀圖檔。
Pathshot 解決這個痛點：框選 → 存 PNG → **路徑自動進剪貼簿** → 貼路徑給 agent 即可讓它讀圖。

## 功能特色

- 🖱️ **拖曳框選**：全螢幕選取任意區域（幾乎透明遮罩，底下畫面清晰）
- 📏 **即時尺寸**：框選時顯示「寬 × 高」
- 👁️ **預覽確認**：放開後顯示截圖預覽，可確認 / 重截 / 取消
- 🖍️ **註記工具**：原子筆、螢光筆、直線、方框，支援多種顏色組合
- 🔍 **縮放控制**：預設 140% 縮放，支援 100%~200% 無縫縮放
- 📋 **自動複製路徑**：儲存後完整檔案路徑自動進剪貼簿
- 🖼️ **選填圖片複製**：勾選「同時複製圖片內容」可額外將圖片拷貼到剪貼簿
- 🗂️ **自訂輸出目錄**：UI 可瀏覽/編輯輸出目錄
- 💾 **記住上次路徑**：重開後自動載入上次選的輸出目錄
- 🎨 **深色粗框**：框選範圍清楚易辨識

## 環境需求

- Python 3.7+
- Windows / macOS / Linux（tkinter 內建）

## 安裝與執行

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行
python screenshot.py
```

## 使用

1. 啟動 → UI 視窗顯示（含「📸 截圖」按鈕）
2. 點「📸 截圖」→ 出現幾乎透明的全螢幕遮罩
3. **拖曳滑鼠**框選要截圖的區域（顯示即時尺寸）
4. 放開 → **預覽視窗**顯示結果
5. 使用註記工具在圖片上標註 (原子筆、螢光筆、直線、方框)
6. 點「✓ 確認儲存」→ 存 PNG + **選擇複製內容到剪貼簿**
   - 或「↻ 重截」重新框選、「✕ 取消」放棄
   - 右側可以選擇複製「路徑」或「圖片」

UI 常駐，可隨時再截。

### 輸出目錄

- 預設：專案下 `Source\`
- UI 可點「瀏覽…」切換目錄，或直接編輯路徑欄
- 選擇會記住（存 `screenshot_config.json`），重開自動載入

### 貼給 CLI agent 使用

截圖後直接貼剪貼簿路徑給 agent：

```
幫我看這個截圖: C:\path\to\Source\20260808_140130.png
```

支援讀圖的 agent 會直接解析圖片內容。

## 建置執行檔（可選）

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name pathshot screenshot.py
# 產出 dist\pathshot.exe
```

## 專案結構

```
pathshot/
├── screenshot.py   # 主程式
├── make_icon.py    # icon 產生器
├── requirements.txt
├── LICENSE         # MIT
└── README.md
```

## License

[MIT](LICENSE)
