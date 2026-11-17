"""主流程：抓取 → 過濾 → 去重 → 分類 → 摘要 → 輸出網站資料及每日摘要。
用法：python -m pipeline.run            （正式抓取）
      python -m pipeline.run --fixture tests/fixtures/sample_feed.xml   （離線測試）"""
import argparse, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import fetch, classify as C, dedupe as D, summarize as S

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HKT = timezone(timedelta(hours=8))
KEEP_DAYS = 30


def load_json(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="用本地 RSS 檔測試，不連網")
    ap.add_argument("--no-ai", action="store_true")
    args = ap.parse_args()
    if args.no_ai:
        for k in ("OPENAI_API_KEY", "AZURE_OPENAI_KEY"):
            os.environ.pop(k, None)

    cfg = load_json(ROOT / "config/sources.json", {})
    rules = load_json(ROOT / "config/rules.json", {})
    now = datetime.now(timezone.utc)
    print(f"== 香港蟲害管理新聞情報中心：{now.astimezone(HKT):%Y-%m-%d %H:%M} HKT ==")

    # 1. 抓取
    if args.fixture:
        src = {"id": "fixture", "name": "測試資料", "tier": "media"}
        raw, errors = fetch.parse_feed(Path(args.fixture).read_bytes(), src), []
    else:
        raw, errors = fetch.fetch_all(cfg["sources"])
    print(f"1. 抓取：{len(raw)} 則")

    # 2. 時間 + 相關度過濾
    cutoff = now - timedelta(hours=cfg.get("lookback_hours", 30))
    kept = []
    for it in raw:
        if it["published"] and datetime.fromisoformat(it["published"]) < cutoff and not args.fixture:
            continue
        it["relevance"] = C.relevance(it, rules)
        if it["relevance"] >= rules["min_relevance_score"]:
            kept.append(it)
    print(f"2. 過濾後：{len(kept)} 則（剔除 {len(raw) - len(kept)} 則無關/過時）")

    # 3. 去重（與過去72小時事件合併）
    events = load_json(DATA / "events.json", [])
    events, added, merged = D.merge(kept, events, rules["dedupe_similarity"], rules["dedupe_window_hours"])
    print(f"3. 去重：新事件 {added} 個，合併重複報道 {merged} 則")

    # 4+5. 分類 + 摘要（只處理新增/有更新的事件）
    review_media = os.getenv("REVIEW_MEDIA", "false").lower() == "true"
    n_sum = 0
    for e in events:
        if not e.get("needs_resummary"):
            continue
        C.classify(e, rules)
        e.update(S.summarize(e))
        e.setdefault("status", "published" if (e["tier"] == "official" or not review_media) else "draft")
        e["updated"] = now.isoformat()
        e["needs_resummary"] = False
        n_sum += 1
    print(f"4-5. 分類及摘要：{n_sum} 個事件")

    # 6. 存檔：超過 30 日移入 archive
    keep_after = now - timedelta(days=KEEP_DAYS)
    active, old = [], []
    for e in events:
        (active if datetime.fromisoformat(e["first_seen"]) >= keep_after else old).append(e)
    if old:
        ap_ = DATA / "archive" / f"{now:%Y-%m}.json"
        save_json(ap_, load_json(ap_, []) + old)
    active.sort(key=lambda e: e["first_seen"], reverse=True)
    save_json(DATA / "events.json", active)

    # 網站讀取的公開檔（只含已發布）
    pub = [{k: e.get(k) for k in ("id", "title", "summary", "management_note", "categories", "priority",
                                  "priority_reason", "districts", "first_seen", "tier", "sources")}
           for e in active if e.get("status") == "published"]
    payload = {"generated": now.isoformat(), "count": len(pub), "items": pub}
    save_json(DATA / "news.json", payload)
    # news.js：讓 index.html 直接雙擊開啟（file://）都可讀取
    (DATA / "news.js").write_text("window.NEWS_DATA = " + json.dumps(payload, ensure_ascii=False) + ";",
                                  encoding="utf-8")
    write_digest(active, now)
    save_json(DATA / "last_run.json", {"time": now.isoformat(), "fetched": len(raw), "kept": len(kept),
                                       "new_events": added, "merged": merged, "errors": errors,
                                       "drafts_pending": sum(e.get("status") == "draft" for e in active)})
    print(f"6. 完成：已發布 {len(pub)}，待審批 {sum(e.get('status') == 'draft' for e in active)}，來源錯誤 {len(errors)}")


def write_digest(events, now):
    since = now - timedelta(hours=24)
    today = [e for e in events if datetime.fromisoformat(e["updated"]) >= since] if events else []
    order = {"高": 0, "中": 1, "低": 2}
    today.sort(key=lambda e: (order.get(e.get("priority"), 3), -len(e["sources"])))
    lines = [f"# 香港蟲害管理新聞每日摘要（{now.astimezone(HKT):%Y-%m-%d}）", "",
             f"過去24小時共 {len(today)} 個事件；高關注 {sum(e.get('priority') == '高' for e in today)} 個。", ""]
    for e in today:
        lines += [f"## 【{e.get('priority')}】{e['title']}",
                  f"- 類別：{'、'.join(e.get('categories', []))}；地區：{'、'.join(e.get('districts') or ['未註明'])}",
                  f"- 摘要：{e.get('summary', '')}",
                  f"- 管理提示：{e.get('management_note', '')}",
                  f"- 狀態：{'已發布' if e.get('status') == 'published' else '待審批'}",
                  "- 來源：" + "；".join(f"[{s['media']}]({s['url']})" for s in e["sources"]), ""]
    (DATA / "daily_digest.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
