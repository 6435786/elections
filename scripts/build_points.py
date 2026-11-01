#!/usr/bin/env python3
"""נקודות מפה לכל מקום קלפי: מצמיד את שמות מקומות הקלפי (live/loc/<code>.json, מאתר התוצאות) למקומות בקובץ הרשמי
live/stations26.json (כתובת + lat/lon), לפי שם מנורמל ואחרת לפי דמיון שם + חפיפת מספרי קלפיות.
כותב live/points.json: {code: {place: [lat, lon, addr]}} ומדפיס כיסוי."""
import json, os, re, sys
from difflib import SequenceMatcher

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))


def norm(s):
    s = (s or "").replace("״", '"').replace("׳", "'").replace("-", " ")
    s = re.sub(r"[\"'().,]", "", s)
    return re.sub(r"\s+", "", s).strip()


def main():
    st = json.load(open(os.path.join(LIVE, "stations26.json"), encoding="utf-8"))
    geo = json.load(open(os.path.join(LIVE, "place_geo.json"), encoding="utf-8"))
    nbp = os.path.join(LIVE, "place_nbhd.json")
    nb = json.load(open(nbp, encoding="utf-8")) if os.path.exists(nbp) else {}  # שכונות אחרי בדיקת המשתמש
    out, tot, hit, boxes_tot, boxes_hit = {}, 0, 0, 0, 0
    for code, s in st.items():
        f = os.path.join(LIVE, "loc", code + ".json")
        if not os.path.exists(f):
            continue
        city = json.load(open(f, encoding="utf-8"))
        bykey = {norm(x["name"]): x for x in s["places"] if x["lat"]}
        used, res = set(), {}
        for pl in city["places"]:
            if not pl["name"]:
                continue
            tot += 1; boxes_tot += len(pl["boxes26"])
            nums = {b["box"] for b in pl["boxes26"]}
            m = bykey.get(norm(pl["name"]))
            if m is None:
                best = (0, None)
                for c in s["places"]:
                    if not c["lat"] or id(c) in used:
                        continue
                    ov = len(nums & set(c["boxes"]))
                    sc = SequenceMatcher(None, norm(pl["name"]), norm(c["name"])).ratio() + (0.5 if ov else 0)
                    if sc > best[0]:
                        best = (sc, c)
                if best[1] and best[0] >= 0.85:
                    m = best[1]
            if m is None:
                continue
            used.add(id(m)); hit += 1; boxes_hit += len(pl["boxes26"])
            g = geo.get(code, {}).get(pl["name"], {})
            res[pl["name"]] = [m["lat"], m["lon"], m["addr"], nb.get(code, {}).get(pl["name"]) or g.get("nbhd") or ""]
        if res:
            out[code] = res
    json.dump(out, open(os.path.join(LIVE, "points.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("points.json: localities %d | places %d/%d located (%.0f%%) | boxes %d/%d (%.0f%%)" % (len(out), hit, tot, 100 * hit / max(1, tot), boxes_hit, boxes_tot, 100 * boxes_hit / max(1, boxes_tot)))


if __name__ == "__main__":
    sys.exit(main())
