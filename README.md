# 香港蟲害管理新聞情報中心

網站（`index.html`）＋每日自動更新流程（`pipeline/`），只用 Python 標準庫，免安裝套件。
每日香港時間 06:00、13:00、19:00 由 GitHub Actions 自動更新。

## 流程
抓取 → 媒體黑名單 → 相關度過濾 → 去重 → 分類 → 摘要 → 輸出 `data/news.json`

## 新聞來源（`config/sources.json`）
- 主題搜尋：鼠患、蚊患、其他害蟲、樹木蟲害、食環署、英文
- 指定媒體：星島日報、星島頭條、on.cc東網、東方日報、信報、香港經濟日報、am730、大公報、香港文匯報、香港電台、無綫新聞、有線新聞、商台新聞、Now新聞、明報、香港01
- 官方：政府新聞公報

## 分類規則（`config/rules.json`）
- 新聞必須屬於以下最少一類，否則不顯示（已取消「其他蟲害」）：
  鼠患、蚊患及病媒疾病、蟑螂及室內害蟲、白蟻及木材害蟲、樹木及戶外蟲害
- 「技術及藥劑」「政府政策及執法」只會加在已屬蟲害類別的新聞上
- 例外：含滅蟲產品／技術字眼（`pest_tech_keywords`，如殺蟲劑、捕鼠器、蚊怕水）的新聞會保留，歸入「技術及藥劑」
- 每次更新會用最新規則重新分類全部舊新聞

## 常用調整
| 想做 | 改邊度 |
|---|---|
| 唔要某個媒體 | `rules.json` → `blocked_media` 加名稱 |
| 只保留指定媒體 | `rules.json` → `only_allowed_media` 改 `true` |
| 加減蟲害字眼 | `rules.json` → `pest_categories` |
| 加減滅蟲產品字眼 | `rules.json` → `pest_tech_keywords` |
| 排除誤中字眼 | `rules.json` → `exclude_keywords` |
| 加減來源 | `sources.json` |

## 本機測試
```bash
python -m pytest tests
python -m pipeline.run --fixture tests/fixtures/sample_feed.xml --no-ai
```

## AI 摘要（可選）
GitHub → Settings → Secrets and variables → Actions，加入
`AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_KEY`、`AZURE_OPENAI_DEPLOYMENT`，或 `OPENAI_API_KEY`。
冇設定則用規則式摘要。

## 審批（可選）
`.github/workflows/daily.yml` 內 `REVIEW_MEDIA` 改 `"true"`，媒體報道會先入草稿：
```bash
python -m pipeline.review list
python -m pipeline.review approve <id>
```

## 合規
只顯示標題、自撰摘要、來源名稱及原文連結；不複製全文及圖片。
