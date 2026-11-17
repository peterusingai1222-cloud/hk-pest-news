"""步驟2+4：相關度過濾、分類、管理關注度、地區識別。
規則：新聞必須屬於最少一個「蟲害類別」或含滅蟲產品／技術字眼，否則剔除；
「技術及藥劑」「政府政策及執法」只會加喺已屬蟲害類別嘅新聞上。"""


def _hits(text, words):
    t = text.lower()
    return [w for w in words if w.lower() in t]


def pest_hits(text, rules):
    return {cat: n for cat, words in rules["pest_categories"].items() if (n := len(_hits(text, words)))}


def tech_hits(text, rules):
    return _hits(text, rules.get("pest_tech_keywords", []))


def relevance(item, rules):
    title, desc = item["title"], item.get("description", "")
    text = title + " " + desc
    if _hits(text, rules["exclude_keywords"]) or not (pest_hits(text, rules) or tech_hits(text, rules)):
        return 0
    score = 3 * len(_hits(title, rules["core_keywords"])) + len(_hits(desc, rules["core_keywords"]))
    if _hits(text, rules["districts"]) or "香港" in text or "Hong Kong" in text:
        score += 2
    if item.get("tier") == "official":
        score += 1
    return score


def classify(item, rules):
    text = item["title"] + " " + item.get("description", "")
    pests = pest_hits(text, rules)
    if _hits(text, rules["exclude_keywords"]):
        pests = {}
    cats = [c for c, _ in sorted(pests.items(), key=lambda x: -x[1])]
    if not cats and tech_hits(text, rules) and not _hits(text, rules["exclude_keywords"]):
        cats = ["技術及藥劑"]  # 滅蟲產品／技術新聞，冇提害蟲名稱都保留
    if cats:  # 只有蟲害相關新聞先可以加技術／政府標籤
        cats += [c for c, words in rules["context_categories"].items() if _hits(text, words)]
    item["categories"] = list(dict.fromkeys(cats))            # 空 list = 非蟲害，會被剔除
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
