"""步驟2+4：相關度過濾、分類、管理關注度、地區識別。"""


def _hits(text, words):
    t = text.lower()
    return [w for w in words if w.lower() in t]


def relevance(item, rules):
    title, desc = item["title"], item.get("description", "")
    if _hits(title + " " + desc, rules["exclude_keywords"]):
        return 0
    score = 3 * len(_hits(title, rules["core_keywords"])) + len(_hits(desc, rules["core_keywords"]))
    if _hits(title + desc, rules["districts"]) or "香港" in title + desc or "Hong Kong" in title + desc:
        score += 2
    if item.get("tier") == "official":
        score += 1
    return score


def classify(item, rules):
    text = item["title"] + " " + item.get("description", "")
    cats = []
    for cat, words in rules["categories"].items():
        n = len(_hits(text, words))
        if n:
            cats.append((n, cat))
    cats.sort(reverse=True)
    item["categories"] = [c for _, c in cats] or ["其他蟲害"]
    item["districts"] = _hits(text, rules["districts"])
    high = _hits(text, rules["high_priority_keywords"])
    med = _hits(text, rules["medium_priority_keywords"])
    if high:
        item["priority"], item["priority_reason"] = "高", "、".join(high[:3])
    elif med:
        item["priority"], item["priority_reason"] = "中", "、".join(med[:3])
    else:
        item["priority"], item["priority_reason"] = "低", "一般資訊"
    return item
