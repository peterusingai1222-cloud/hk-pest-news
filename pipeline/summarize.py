"""步驟5：中文摘要。
設定 AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY + AZURE_OPENAI_DEPLOYMENT，或 OPENAI_API_KEY 即用 AI；
否則用規則式摘要（不會捏造內容）。"""
import json, os, urllib.request

PROMPT = """你是香港物業管理公司的蟲害管理情報編輯。只可根據以下提供的標題及描述，
以繁體中文寫一段 50-100 字客觀摘要，不可加入資料沒有提及的數字、原因或結論。
再寫一句「管理提示」（30字內），說明物業/商場營運團隊可留意甚麼；如資料不足，寫「資料不足，請參閱原文」。
只輸出 JSON：{"summary": "...", "management_note": "..."}

報道：
"""


def _call_ai(text):
    if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_KEY"):
        url = (f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/deployments/"
               f"{os.environ['AZURE_OPENAI_DEPLOYMENT']}/chat/completions?api-version=2024-06-01")
        headers = {"api-key": os.environ["AZURE_OPENAI_KEY"], "Content-Type": "application/json"}
        body = {}
    elif os.getenv("OPENAI_API_KEY"):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"}
        body = {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")}
    else:
        return None
    body.update({"messages": [{"role": "user", "content": PROMPT + text}], "temperature": 0.1,
                 "response_format": {"type": "json_object"}})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        content = json.loads(r.read())["choices"][0]["message"]["content"]
    return json.loads(content)


def _rule_based(event):
    desc = event.get("description", "").strip()
    base = desc if len(desc) > 15 else event["title"]
    if len(base) > 110:
        base = base[:108] + "…"
    n = len(event["sources"])
    return {"summary": base + (f"（共 {n} 個來源報道）" if n > 1 else ""),
            "management_note": "資料不足，請參閱原文"}


def summarize(event, log=print):
    text = f"標題：{event['title']}\n描述：{event.get('description', '')}\n" + \
           "\n".join(f"其他來源標題：{s['title']}（{s['media']}）" for s in event["sources"][1:6])
    try:
        res = _call_ai(text)
        if res and res.get("summary"):
            res["summary_method"] = "ai"
            return res
    except Exception as e:
        log(f"  [AI摘要失敗，改用規則式] {event['title'][:30]}: {e}")
    res = _rule_based(event)
    res["summary_method"] = "rule"
    return res
