import json
from pathlib import Path
from pipeline import dedupe, classify
from pipeline.run import make_media_filter

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "config/rules.json").read_text(encoding="utf-8"))


def cats(t):
    return classify.classify({"title": t, "description": ""}, RULES)["categories"]


def test_similarity():
    assert dedupe.similarity("食環署深水埗展開滅鼠行動 巡查食肆後巷", "食環署深水埗展開滅鼠行動　巡查食肆後巷") > 0.9
    assert dedupe.similarity("沙田屋苑住戶投訴木蝨", "衞生防護中心呼籲市民防蚊") < 0.3


def test_non_pest_removed():
    for t in ["政府公布財政預算案", "立法會討論AI發展", "米老鼠樂園新設施", "新款噴霧髮膠評測", "菜心驗出農藥殘留"]:
        assert cats(t) == [], t
        assert classify.relevance({"title": t}, RULES) == 0, t


def test_pest_with_context():
    assert cats("食環署展開滅鼠行動 檢控食肆") == ["鼠患", "政府政策及執法"]
    assert cats("AI 監察鼠患 試驗計劃") == ["鼠患", "技術及藥劑"]


def test_pest_product_kept():
    assert cats("新款殺蟲劑噴霧評測") == ["技術及藥劑"]
    assert cats("消委會測試蚊怕水") == ["技術及藥劑"]


def test_no_other_category():
    assert "其他蟲害" not in cats("沙田屋苑木蝨")


def test_media_filter():
    ok = make_media_filter(RULES)
    assert not ok("openPR.com") and not ok("UHK 港生活")
    assert ok("明報新聞網") and ok("星島頭條")
