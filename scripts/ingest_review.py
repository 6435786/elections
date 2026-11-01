#!/usr/bin/env python3
"""קולט את קובץ הבדיקה הידנית (kalpiot_review.xlsx, מולא על ידי המשתמש) וכותב:
  live/place_nbhd.json  {code: {place2026: neighbourhood}}  – שכונה לכל מקום קלפי: תיקון המשתמש אם מולא, אחרת הניחוש (OSM)
  live/place_map.json   {code: {place2026: place2022}}      – תיקוני התאמה ל-2022 שהמשתמש מילא (שם מקום) ; "לא" = לבטל התאמה
שימוש: python -I scripts/ingest_review.py <kalpiot_review.xlsx>
"""
import json, os, re, sys

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))


def main(path):
    import openpyxl
    boxes = json.load(open(os.path.join(LIVE, "boxes.json"), encoding="utf-8"))
    name2code = {c["name"]: code for code, c in boxes["cities"].items()}
    wb = openpyxl.load_workbook(path, read_only=True)
    nbhd, pmap, unmatch, stats = {}, {}, {}, []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        head = [str(h or "").strip() for h in next(rows)]
        col = lambda prefix: next((i for i, h in enumerate(head) if h.startswith(prefix)), None)
        i_city, i_place, i_fix22, i_osm, i_fixn, i_note = col("עיר"), col("מקום הקלפי 2026"), col("✔ ההתאמה"), col("שכונה משוערת"), col("✔ שכונה"), col("הערות")
        n_fix, n_osm, n_fix22 = 0, 0, 0
        code = None
        for r in rows:
            if not r or not r[i_place]:
                continue
            city, place = str(r[i_city]).strip(), str(r[i_place]).strip()
            code = code or name2code.get(city)
            if not code or place.startswith("("):
                continue
            clean = lambda x: re.sub(r"\s*['\u05f3]\s*$", "", str(x or "").strip()).strip()  # מאחד "ב" ו"ב'"
            fix = clean(r[i_fixn]) if i_fixn is not None else ""
            osm = clean(r[i_osm]) if i_osm is not None else ""
            if fix:
                nbhd.setdefault(code, {})[place] = fix; n_fix += 1
            elif osm:
                nbhd.setdefault(code, {})[place] = osm; n_osm += 1
            f22 = str(r[i_fix22] or "").strip() if i_fix22 is not None else ""
            if f22 and f22 not in ("כן", "v", "V", "✔"):
                if f22 == "לא":
                    unmatch.setdefault(code, []).append(place)
                else:
                    pmap.setdefault(code, {})[place] = f22
                n_fix22 += 1
        stats.append((ws.title, n_fix, n_osm, n_fix22))
    json.dump(nbhd, open(os.path.join(LIVE, "place_nbhd.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pm_path = os.path.join(LIVE, "place_map.json")
    old = json.load(open(pm_path, encoding="utf-8")) if os.path.exists(pm_path) else {}
    for code, m in pmap.items():
        old.setdefault(code, {}).update(m)
    for code, lst in unmatch.items():
        old.setdefault(code, {}).update({p: None for p in lst})
    json.dump(old, open(pm_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t, a, b, c in stats:
        print("%s: שכונה מהמשתמש %d, מהניחוש %d, תיקוני 2022 %d" % (t, a, b, c))
    print("place_nbhd.json:", sum(len(v) for v in nbhd.values()), "places |", "place_map.json entries:", sum(len(v) for v in old.values()))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Desktop", "kalpiot_review.xlsx")))
