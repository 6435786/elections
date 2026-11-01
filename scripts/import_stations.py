#!/usr/bin/env python3
"""מייבא את קובץ מקומות הקלפי הרשמי (ועדת הבחירות, "קובץ ריכוזים סופי", כפי שפורסם ב-findmykalpi.com/data/stations.json):
שם מקום, כתובת ונקודת מפה לכל מקום קלפי בארץ.
כותב live/stations26.json (לכל היישובים) ומעדכן את live/place_geo.json לערים החרדיות: כתובת רשמית + מיקום רשמי (src="cec").
שימוש: python -I scripts/import_stations.py <stations.json>
"""
import json, os, re, sys
from difflib import SequenceMatcher

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))


def norm(s):
    s = (s or "").replace("״", '"').replace("׳", "'").replace("-", " ")
    s = re.sub(r"[\"'().,]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    return norm(s).replace(" ", "")


def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def main(src):
    S = json.load(open(src, encoding="utf-8"))
    idx = json.load(open(os.path.join(LIVE, "loc_index.json"), encoding="utf-8"))
    name2code = {}
    for c, v in idx.items():
        name2code.setdefault(key(v["name"]), c)
    # שמות שונים בקובץ הוועדה לעומת קובץ התוצאות
    for alias, code in {"נוף הגליל": "1061", "כוכב יאיר-צור יגאל": "1224", "כרם ביבנה (ישיבה)": "1094", "סואעד (חמירה)": "942"}.items():
        name2code.setdefault(key(alias), code)
    out, unmatched = {}, []
    for li, lname in enumerate(S["L"]):
        code = name2code.get(key(lname))
        if not code:
            unmatched.append(lname)
            continue
        out[code] = {"name": lname, "places": []}
    for p in S["P"]:
        lat, lon, li, pname, addr, n, acc, spc, boxes, note = p[:10]
        code = name2code.get(key(S["L"][li]))
        if not code:
            continue
        bx = [("%g" % float(b.rstrip("*"))) for b in boxes.split(",") if b.strip()]
        out[code]["places"].append({"name": pname, "addr": addr, "lat": lat or None, "lon": lon or None, "n": n, "boxes": bx, "note": note})
    json.dump(out, open(os.path.join(LIVE, "stations26.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("stations26.json: localities", len(out), "| places", sum(len(v["places"]) for v in out.values()), "| unmatched locality names", len(unmatched))

    # ערים חרדיות: הצמדת מקום קלפי → מקום רשמי (שם זהה, אחרת חפיפת מספרי קלפיות + דמיון שם)
    boxes = json.load(open(os.path.join(LIVE, "boxes.json"), encoding="utf-8"))
    gp = os.path.join(LIVE, "place_geo.json")
    geo = json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) else {}
    for code, city in boxes["cities"].items():
        st = out.get(code, {}).get("places", [])
        bykey = {key(s["name"]): s for s in st}
        used, hits, total = set(), 0, 0
        for pl in city["places"]:
            if not pl["name"]:
                continue
            total += 1
            nums = {b["box"] for b in pl["boxes26"]}
            s = bykey.get(key(pl["name"]))
            how = "name"
            if s is None:
                best = (0, None)
                for c in st:
                    if id(c) in used:
                        continue
                    ov = len(nums & set(c["boxes"]))
                    sc = sim(pl["name"], c["name"]) + (0.5 if ov else 0)
                    if ov and sc > best[0]:
                        best = (sc, c)
                if best[1] and best[0] >= 0.8:
                    s, how = best[1], "boxes"
            if s is None:
                continue
            used.add(id(s)); hits += 1
            v = geo.setdefault(code, {}).setdefault(pl["name"], {})
            v.update({"cec_name": s["name"], "cec_addr": s["addr"], "cec_how": how, "cec_note": s["note"]})
            if s["lat"]:
                v.update({"lat": s["lat"], "lon": s["lon"], "src": "cec", "map": "https://www.google.com/maps?q=%s,%s" % (s["lat"], s["lon"]), "addr_done": False})
        print("  %s %s: %d/%d places got official address" % (code, city["name"], hits, total))
    json.dump(geo, open(gp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    if unmatched:
        print("unmatched locality names (first 20):", unmatched[:20])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
