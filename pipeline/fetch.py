"""步驟1：抓取 RSS / Google News 搜尋 RSS（只用標準庫）。"""
import html, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = "HKPestIntelBot/1.0 (+internal monitoring)"


def google_news_url(query, lang="zh"):
    q = urllib.parse.quote(query)
    if lang == "en":
        return f"https://news.google.com/rss/search?q={q}&hl=en-HK&gl=HK&ceid=HK:en"
    return f"https://news.google.com/rss/search?q={q}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"


def source_url(src):
    if src["type"] == "google_news":
        return google_news_url(src["query"], src.get("lang", "zh"))
    return src["url"]


def download(url, retries=2, timeout=20):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise last


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse_feed(xml_bytes, src):
    root = ET.fromstring(xml_bytes)
    items = []
    atom = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall(".//item") or root.findall(f".//{atom}entry")
    for n in nodes:
        def g(tag):
            el = n.find(tag)
            if el is None:
                el = n.find(atom + tag)
            return el
        title = strip_html(g("title").text if g("title") is not None else "")
        link_el = g("link")
        link = ""
        if link_el is not None:
            link = (link_el.text or link_el.get("href") or "").strip()
        desc_el = g("description") if g("description") is not None else g("summary")
        desc = strip_html(desc_el.text if desc_el is not None else "")
        date_el = g("pubDate") if g("pubDate") is not None else g("updated")
        published = parse_date(date_el.text if date_el is not None else None)
        # Google News：<source> 為實際媒體名稱；標題尾 " - 媒體" 要拆走
        media = src["name"]
        s_el = n.find("source")
        if s_el is not None and s_el.text:
            media = s_el.text.strip()
            suffix = " - " + media
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
            if desc.startswith(title):
                desc = desc[len(title):].strip(" -")
            if desc.endswith(media):
                desc = desc[: -len(media)].strip(" -")
        if not title or not link:
            continue
        items.append({
            "title": title, "url": link, "description": desc,
            "published": published.isoformat() if published else None,
            "media": media, "source_id": src["id"], "tier": src.get("tier", "media"),
        })
    return items


def fetch_all(sources, log=print):
    out, errors = [], []
    for src in sources:
        if not src.get("enabled", True):
            continue
        try:
            items = parse_feed(download(source_url(src)), src)
            log(f"  [OK] {src['name']}: {len(items)} 則")
            out.extend(items)
        except Exception as e:
            log(f"  [失敗] {src['name']}: {e}")
            errors.append({"source": src["id"], "error": str(e)})
        time.sleep(1)  # 禮貌間隔
    return out, errors
