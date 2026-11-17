"""審批工具：python -m pipeline.review list | approve <id...> | reject <id...> | approve-all"""
import sys
from .run import DATA, load_json, save_json


def main():
    events = load_json(DATA / "events.json", [])
    cmd, ids = (sys.argv[1] if len(sys.argv) > 1 else "list"), set(sys.argv[2:])
    if cmd == "list":
        for e in events:
            if e.get("status") == "draft":
                print(f"{e['id']}  【{e.get('priority')}】{e['title']}  ({len(e['sources'])}來源)")
        return
    for e in events:
        if cmd == "approve-all" and e.get("status") == "draft" or e["id"] in ids:
            e["status"] = "rejected" if cmd == "reject" else "published"
    save_json(DATA / "events.json", events)
    print("已更新；下次執行 run 時會重新生成 news.json")


if __name__ == "__main__":
    main()
