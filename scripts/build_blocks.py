#!/usr/bin/env python3
"""בונה live/blocks.json (גושי שכונות למסך העיר) מתוך live/blocks_src.json.
blocks_src.json = השיוך הידני של כל מקום קלפי 2026 לגוש (ולשכונה), לפי עיר: {code: {"order": [...], "note": "", "places": {שם מקום: {"block", "nbhd"}}}}.
כל קבוצת מקומות בטבלת הבסיס (שורה מסוג place) משויכת לגוש של המקום הגדול בה (לפי בעלי זכות 2026).
להריץ אחרי build_base_table.py, כי הקבוצות יכולות להשתנות.
שימוש: python -I scripts/build_blocks.py
"""
import json, os, sys, collections

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))


def main():
    src = json.load(open(os.path.join(LIVE, "blocks_src.json"), encoding="utf-8"))
    base = json.load(open(os.path.join(LIVE, "base_table.json"), encoding="utf-8"))
    out = {}
    for code, s in src.items():
        loc = json.load(open(os.path.join(LIVE, "loc", code + ".json"), encoding="utf-8"))
        e = {p["name"]: sum(b["e"] for b in p["boxes26"]) for p in loc["places"] if p["name"]}
        pb = {n: v["block"] for n, v in s["places"].items()}
        rows = {}
        for r in base:
            if r["code"] != code or r["kind"] != "place" or not r["names26"]:
                continue
            best = max(((e.get(n, 0), pb[n]) for n in r["names26"] if n in pb), default=None)
            if best:
                rows["|".join(r["names26"])] = best[1]
        out[code] = {"order": s["order"], "rows": rows, "note": s.get("note", "")}
        print(code, len(rows), "groups", dict(collections.Counter(rows.values())))
    json.dump(out, open(os.path.join(LIVE, "blocks.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    sys.exit(main())
