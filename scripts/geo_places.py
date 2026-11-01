#!/usr/bin/env python3
"""מיקום מקומות הקלפי: מצליב את שם מקום הקלפי (מאתר הוועדה) מול מוסדות החינוך של משרד החינוך (live/mosdot.json, קואורדינטות ITM)
ומפיק live/place_geo.json: {code: {"שם מקום": {"x":..,"y":..,"inst":"שם המוסד","score":0.9}}}.
התאמות ידניות: live/place_geo_manual.json {code: {"שם מקום": {"x":..,"y":..} או {"inst":"שם מוסד"}}}.
"""
import json, os, re, sys, difflib

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
STOP = {"בית", "ספר", "ביס", "ביהס", "בי", "ס", "ה", "ע", "ש", "עש", "החדש", "לשעבר", "בנות", "בנים", "ממד", "ממלכתי", "תורני",
        "יסודי", "תיכון", "חטב", "ילדים", "גן", "גני", "מרכז", "מתנס", "קהילתי", "מינהל", "מנהל", "סמינר", "תלמוד", "תורה", "תת",
        "שלוחת", "אגף", "כניסה", "ראשית", "רח", "רחוב", "של", "על", "שם", "חדש", "ישן", "מתחם", "אשכול", "מעון", "מעונות", "כללי"}


def norm(s):
    s = (s.replace('בי"ס', " ביס ").replace('ביה"ס', " ביהס ").replace("בית ספר", " ביס ").replace('מתנ"ס', " מתנס ")
         .replace('ת"ת', " תת ").replace('ממ"ד', " ממד ").replace('חט"ב', " חטב ").replace('ע"ש', " עש ").replace('חב"ד', " חבד "))
    s = re.sub(r'[\s"\'״׳\-–,.()/:]+', " ", s)
    return s.strip().lower()


def tokens(s):
    t = [w for w in norm(s).split() if w not in STOP and len(w) > 1]
    return set(t)


def sim(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    seq = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    return max(j, seq * 0.9)


def main():
    p = lambda f: os.path.join(LIVE, f)
    boxes = json.load(open(p("boxes.json"), encoding="utf-8"))
    mosdot = json.load(open(p("mosdot.json"), encoding="utf-8"))
    manual = json.load(open(p("place_geo_manual.json"), encoding="utf-8")) if os.path.exists(p("place_geo_manual.json")) else {}
    out = {}
    for code, city in boxes["cities"].items():
        inst = [m for m in mosdot.get(code, []) if m.get("x") and m.get("y")]
        res = {}
        names = [pl["name"] for pl in city["places"] if pl["name"]] + [pl["name22"] for pl in city["places"] if not pl["name"]]
        found = 0
        for name in names:
            mm = manual.get(code, {}).get(name)
            if mm and "x" in mm:
                res[name] = {"x": mm["x"], "y": mm["y"], "inst": mm.get("inst", "ידני"), "score": 1.0, "how": "manual"}
                found += 1
                continue
            cands = sorted(((sim(name, m["name"]), m) for m in inst), key=lambda t: -t[0])
            if mm and "inst" in mm:
                cands = [(1.0, m) for m in inst if m["name"] == mm["inst"]] + cands
            if cands and cands[0][0] >= 0.65:
                sc, m = cands[0]
                res[name] = {"x": m["x"], "y": m["y"], "inst": m["name"], "score": round(sc, 2), "how": "mosdot"}
                found += 1
            else:
                res[name] = {"x": None, "y": None, "inst": (cands[0][1]["name"] if cands else None), "score": round(cands[0][0], 2) if cands else 0, "how": None}
        out[code] = res
        print("%s %s: %d/%d places located" % (code, city["name"], found, len(names)))
    json.dump(out, open(p("place_geo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    sys.exit(main())
