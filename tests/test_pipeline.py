import json, subprocess, sys, shutil
from pathlib import Path
from pipeline import dedupe, classify
ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "config/rules.json").read_text(encoding="utf-8"))

def test_similarity():
    assert dedupe.similarity("食環署深水埗展開滅鼠行動 巡查食肆後巷", "食環署深水埗展開滅鼠行動　巡查食肆後巷") > 0.9
    assert dedupe.similarity("沙田屋苑住戶投訴木蝨", "衞生防護中心呼籲市民防蚊") < 0.3

def test_exclude():
    assert classify.relevance({"title": "新款無線滑鼠評測", "description": ""}, RULES) == 0

def test_priority():
    e = classify.classify({"title": "食肆後巷鼠患 食環署檢控", "description": ""}, RULES)
    assert e["priority"] == "高" and e["categories"][0] in ("鼠患", "政府政策及執法")
