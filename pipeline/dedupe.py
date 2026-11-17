"""步驟3：去重 — 相同網址或標題相似度高的報道合併為一個「事件」。"""
import hashlib, re
from datetime import datetime, timedelta, timezone

PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


def norm(title):
    t = re.sub(r"【[^】]*】|\[[^\]]*\]|（[^）]*）", "", title)
    return PUNCT.sub("", t.lower())


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def similarity(a, b):
    A, B = bigrams(norm(a)), bigrams(norm(b))
    return len(A & B) / max(1, min(len(A), len(B)))  # overlap coefficient


def event_id(title):
    return hashlib.sha1(norm(title).encode()).hexdigest()[:12]


def _dt(s):
    return datetime.fromisoformat(s) if s else datetime.now(timezone.utc)


def merge(new_items, existing_events, threshold=0.55, window_hours=72):
    """把新項目合併入現有事件；回傳 (全部事件, 新增事件數, 合併報道數)。"""
    events = list(existing_events)
    url_index = {s["url"]: e for e in events for s in e["sources"]}
    added = merged = 0
    for it in sorted(new_items, key=lambda x: x.get("published") or ""):
        if it["url"] in url_index:
            continue
        ref = _dt(it.get("published"))
        best, best_sim = None, 0.0
        for e in events:
            if abs((_dt(e["first_seen"]) - ref)) > timedelta(hours=window_hours):
                continue
            sim = similarity(it["title"], e["title"])
            if sim > best_sim:
                best, best_sim = e, sim
        src = {k: it[k] for k in ("title", "url", "media", "published", "tier")}
        if best and best_sim >= threshold:
            if not any(s["media"] == it["media"] and s["title"] == it["title"] for s in best["sources"]):
                best["sources"].append(src)
                merged += 1
            if it["tier"] == "official" and best.get("tier") != "official":
                best["tier"] = "official"
            best["needs_resummary"] = True
            url_index[it["url"]] = best
        else:
            e = {
                "id": event_id(it["title"]), "title": it["title"], "description": it.get("description", ""),
                "first_seen": it.get("published") or datetime.now(timezone.utc).isoformat(),
                "tier": it["tier"], "sources": [src], "needs_resummary": True,
                "relevance": it.get("relevance", 0),
            }
            events.append(e)
            url_index[it["url"]] = e
            added += 1
    return events, added, merged
