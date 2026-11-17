"""主流程：抓取 → 媒體過濾 → 相關度過濾 → 去重 → 分類 → 摘要 → 輸出網站資料及每日摘要。
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


def make_media_filter(rules):
    blocked = [b.lower() for b in rules.get("blocked_media", [])]
    allowed = [a.lower() for a in rules.get("allowed_media", [])]
    only = rules.get("only_allowed_media", False)

    def ok(media):
        m = (media or "").lower()
        if any(b in m for b in blocked):
            return False
        return any(a in m for a in allowed) if only else True
    return ok


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
    media_ok = make_media_filter(rules)
    now = datetime.now(timezone.utc)
    print(f"== 香港蟲害管理新聞情報中心：{now.astimezone(HKT):%Y-%m-%d %H:%M} HKT ==")

    # 1. 抓取
    if args.fixture:
        src = {"id": "fixture", "name": "測試資料", "tier": "media"}
        raw, errors = fetch.parse_feed(Path(args.fixture).read_bytes(), src), []
    else:
        raw, errors = fetch.fetch_all(cfg["sources"])
    print(f"1. 抓取：{len(raw)} 則")

    # 1b. 媒體黑名單／白名單
    before = len(raw)
    raw = [it for it in raw if media_ok(it["media"])]
    print(f"1b. 媒體過濾：剔除 {before - len(raw)} 則黑名單／非指定媒體")

    # 2. 時間 + 相關度過濾
    cutoff = now - timedelta(hours=cfg.get("lookback_hours", 30))
    kept = []
    for it in raw:
        if it["published"] and datetime.fromisoformat(it["published"]) < cutoff and not args.fixture:
            continue
        it["relevance"] = C.relevance(it, rules)
        if it["relevance"] >= rules["min_relevance_score"]:
            kept.append(it)
    print(f"2. 過濾後：{len(kept)} 則（剔除 {len(raw) - len(kept)} 則無關／過時）")

    # 3. 去重（與過去72小時事件合併）；同時清走舊資料中已列入黑名單的來源
    events = load_json(DATA / "events.json", [])
    for e in events:
        e["sources"] = [x for x in e["sources"] if media_ok(x["media"])]
    events = [e for e in events if e["sources"]]
    events, added, merged = D.merge(kept, events, rules["dedupe_similarity"], rules["dedupe_window_hours"])
    print(f"3. 去重：新事件 {added} 個，合併重複報道 {merged} 則")

    # 4+5. 分類 + 摘要（只處理新增／有更新的事件）
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

    # 4b. 每次重新分類全部事件（規則改咗會即時套用到舊新聞）；非蟲害新聞剔除
    removed = 0
    for e in events:
        C.classify(e, rules)
        if not e["categories"]:
            if e.get("status") != "excluded":
                removed += 1
            e["status"] = "excluded"
        elif e.get("status") == "excluded":
            e["status"] = "published"
    print(f"4b. 剔除非蟲害新聞：{removed} 個")

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

    pub = [{k: e.get(k) for k in ("id", "title", "summary", "management_note", "categories", "priority",
                                  "priority_reason", "districts", "first_seen", "tier", "sources")}
           for e in active if e.get("status") == "published"]
    payload = {"generated": now.isoformat(), "count": len(pub), "items": pub}
    save_json(DATA / "news.json", payload)
    (DATA / "news.js").write_text("window.NEWS_DATA = " + json.dumps(payload, ensure_ascii=False) + ";",
                                  encoding="utf-8")
    write_digest(active, now)
    save_json(DATA / "last_run.json", {"time": now.isoformat(), "fetched": len(raw), "kept": len(kept),
                                       "new_events": added, "merged": merged, "errors": errors,
                                       "drafts_pending": sum(e.get("status") == "draft" for e in active)})
    print(f"6. 完成：已發布 {len(pub)}，待審批 {sum(e.get('status') == 'draft' for e in active)}，來源錯誤 {len(errors)}")


def write_digest(events, now):
    since = now - timedelta(hours=24)
    today = [e for e in events if e.get("status") != "excluded" and e.get("updated")
             and datetime.fromisoformat(e["updated"]) >= since]
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
