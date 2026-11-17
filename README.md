# 香港蟲害管理新聞情報中心

網站（`index.html`）＋每日自動更新流程（`pipeline/`），只用 Python 標準庫，免安裝套件。

## 網站上線（GitHub Pages，免費）
1. 建立 GitHub repository，上載本資料夾全部內容（包括 `.github`、`.nojekyll`）。
2. Settings → Pages → Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾 `/ (root)`，按 Save。
3. Actions → 「每日蟲害新聞更新」→ **Run workflow**，等約1-2分鐘。
4. 開啟 `https://<你的帳戶>.github.io/<repository名稱>/` 即可見到新聞。
5. 之後每日 06:00、13:00、19:00（香港時間）自動更新，網站自動跟住更新。

> 注意：GitHub Pages 免費版需要 Public repository；如要內部私用，可改放公司 SharePoint／Azure Static Web Apps，或 GitHub 付費方案。
> 本機預覽：直接雙擊 `index.html`（讀取 `data/news.js`）。

## 網站功能
搜尋、管理關注度（高/中/低）、蟲害類別、日期、地區、媒體、官方/媒體篩選；排序；同一事件合併多個媒體來源；管理提示；趨勢統計（類別、地區、媒體、每日事件數）。

---
# 每日自動流程

只用 Python 標準庫，無需安裝套件。

## 流程
| 步驟 | 檔案 | 作用 |
|---|---|---|
| 1 抓取 | `pipeline/fetch.py` | 讀取 `config/sources.json` 內的 RSS 及 Google News 搜尋 RSS |
| 2 過濾 | `pipeline/classify.py` | 只保留30小時內；關鍵字評分 ≥3；剔除「滑鼠、股市」等誤中 |
| 3 去重 | `pipeline/dedupe.py` | 同網址或標題相似度 ≥0.55（72小時內）合併為同一事件，保留全部來源 |
| 4 分類 | `pipeline/classify.py` | 7個蟲害類別、18區/常見地區、管理關注度（高/中/低）|
| 5 摘要 | `pipeline/summarize.py` | 有 AI 金鑰用 AI（只根據報道內容）；否則規則式摘要 |
| 6 輸出 | `pipeline/run.py` | `data/news.json`（網站讀取）、`data/daily_digest.md`、`data/last_run.json` |

## 本機測試
```bash
python -m pipeline.run --fixture tests/fixtures/sample_feed.xml --no-ai   # 離線測試
python -m pipeline.run                                                    # 正式抓取
python -m pytest tests
```

## 審批（可選）
預設全部自動發布。如想媒體報道先入草稿，將 workflow 內 `REVIEW_MEDIA` 改為 `"true"`，再用：
```bash
python -m pipeline.review list
python -m pipeline.review approve <id> <id>
python -m pipeline.review reject <id>
python -m pipeline.review approve-all
```

## AI 摘要設定（可選）
1. 建立 **Private** GitHub repository，上載本資料夾全部內容。
2. Settings → Secrets → Actions，加入（二選一，可略過則用規則式摘要）：
   - `AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_KEY`、`AZURE_OPENAI_DEPLOYMENT`；或 `OPENAI_API_KEY`
3. Actions → 「每日蟲害新聞更新」→ Run workflow 先手動試一次。
4. 之後每日 06:00、13:00、19:00（香港時間）自動執行並提交 `data/`。
5. 網站前台讀取 `data/news.json` 即可顯示。

## 調整
- 加減來源：`config/sources.json`（`enabled:false` 的來源須先確認網址有效）
- 關鍵字、類別、排除字、關注度：`config/rules.json`
- 過濾太鬆 → 提高 `min_relevance_score`；重複太多 → 降低 `dedupe_similarity`

## 合規提醒
只儲存標題、自撰摘要、來源名稱及原文連結；不複製全文及圖片。正式對外公開前，建議檢視各來源使用條款。
