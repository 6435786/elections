#!/usr/bin/env python3
"""ניתוח לפי קלפיות: בונה live/boxes.json – לכל עיר, הקלפיות של 2026 ושל 2022 מקובצות לפי מקום הקלפי.

קלט:
  live/expb.csv      – תוצאות 2026 לפי קלפי (ועדת הבחירות)
  live/expb25.csv    – תוצאות 2022 לפי קלפי
  live/places26.json – {code: {box: {place, barzel}}}  שמות מקומות הקלפי 2026 (נמשכו מאתר הוועדה)
  live/places25.json – {code: {name, boxes:[{box, place, barzel}]}} שמות מקומות הקלפי 2022
  live/place_map.json (רשות) – {code: {"שם מקום 2026": "שם מקום 2022"}} התאמות ידניות

התאמה בין 2026 ל-2022 לפי שם המקום (מנורמל), לא לפי מספר קלפי.
"""
import csv, io, json, os, re, sys, difflib

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
CITIES = {"3780": "ביתר עילית", "6100": "בני ברק", "3797": "מודיעין עילית", "1309": "אלעד", "2610": "בית שמש", "3000": "ירושלים",
          "922": "רכסים", "1137": "קרית יערים", "3660": "עמנואל"}


def decode(raw):
    for enc in ("utf-8-sig", "cp1255"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def read_expb(path, codes):
    rows = list(csv.reader(io.StringIO(decode(open(path, "rb").read()))))
    h = [c.strip() for c in rows[0]]
    ix = {c: i for i, c in enumerate(h)}
    ic, ik, ie, iv, iinv, ivalid = ix["סמל ישוב"], ix["קלפי"], ix["בזב"], ix["מצביעים"], ix["פסולים"], ix["כשרים"]
    letters = [c for c in h[ivalid + 1:] if c]
    out = {}
    for r in rows[1:]:
        if len(r) <= ivalid or r[ic].strip() not in codes:
            continue
        try:
            box = float(r[ik])
        except ValueError:
            continue
        n = lambda i: int(float(r[i])) if r[i].strip() else 0
        votes = {}
        for l in letters:
            j = ix[l]
            if j < len(r) and r[j].strip() and r[j].strip() != "0":
                votes[l] = int(float(r[j]))
        key = ("%g" % box)
        out.setdefault(r[ic].strip(), {})[key] = {"box": key, "e": n(ie), "v": n(iv), "inv": n(iinv), "k": n(ivalid), "votes": votes}
    return out


STOP = {"בית", "ספר", "ביס", "ביהס", "בי", "ס", "ה", "ע", "ש", "עש", "החדש", "לשעבר", "בנות", "בנים", "ממד", "ממלכתי", "תורני",
        "יסודי", "תיכון", "חטב", "ילדים", "גן", "גני", "מרכז", "מתנס", "קהילתי", "מינהל", "מנהל", "סמינר", "תלמוד", "תורה", "תת",
        "שלוחת", "אגף", "כניסה", "ראשית", "רח", "רחוב"}


def norm(s):
    s = (s.replace('בי"ס', " ביס ").replace('ביה"ס', " ביהס ").replace("בית ספר", " ביס ").replace('מתנ"ס', " מתנס ")
         .replace('ת"ת', " תת ").replace('ממ"ד', " ממד ").replace('חט"ב', " חטב ").replace('ע"ש', " עש "))
    s = re.sub(r'[\s"\'״׳\-–,.()/:]+', " ", s)
    return s.strip().lower()


def tokens(s):
    t = [w for w in norm(s).split() if w not in STOP and len(w) > 1]
    return set(t) or set(norm(s).split())


def name_sim(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    return max(j, difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() if j > 0 else 0.0)


KEEP = ["מחל", "פה", "כן", "ט", "שס", "ג", "ל", "אמת", "מרצ", "ום", "ד", "עם", "ב", "דרך", "רק", "די", "ודם", "ך", "זך", "נר", "ני"]
NAFA_DIST = {11: "ירושלים", 21: "צפון", 22: "צפון", 23: "צפון", 24: "צפון", 25: "צפון", 29: "צפון", 31: "חיפה", 32: "חיפה",
             41: "מרכז", 42: "מרכז", 43: "מרכז", 44: "מרכז", 51: "תל אביב", 52: "תל אביב", 53: "תל אביב", 61: "דרום", 62: "דרום"}


def match_places(code, b26, b25, names26, names25, pmap):
    """מקבץ קלפיות לפי מקום ומתאים מקומות 2026 ל-2022 (ידני → שם זהה → דמיון שם + חפיפת מספרי קלפיות)."""
    places25 = {}
    for k, bx in b25.items():
        places25.setdefault(names25.get(k, "?"), []).append(bx)
    places = {}
    for k, bx in b26.items():
        places.setdefault(names26.get(k, "?"), []).append(bx)
    used, pre = set(), {}
    n25 = {norm(x): x for x in places25 if x != "?"}
    box25 = {x: {b["box"] for b in bx} for x, bx in places25.items()}
    for pname in places:
        m = pmap.get(pname) or (n25.get(norm(pname)) if pname != "?" else None)
        if m and m in places25 and m not in used:
            pre[pname] = (m, "manual" if pmap.get(pname) else "name"); used.add(m)
    cands = []
    for pname, boxes in places.items():
        if pname in pre or pname == "?":
            continue
        nums = {b["box"] for b in boxes}
        for x in places25:
            if x in used or x == "?":
                continue
            ns = name_sim(pname, x)
            ov = len(nums & box25[x]) / max(1, min(len(nums), len(box25[x])))
            score = ns + (0.6 if ov >= 0.5 else 0.3 if ov > 0 else 0.0)
            if ns >= 0.5 or (ov >= 0.5 and ns >= 0.2):
                cands.append((score, pname, x, "name" if ns >= 0.5 else "boxes"))
    for score, pname, x, how in sorted(cands, reverse=True):
        if pname in pre or x in used:
            continue
        pre[pname] = (x, how); used.add(x)
    # ביישוב בלי שמות מקומות: "?" מול "?" – מקום אחד שמכיל את כל הקלפיות
    if "?" in places and "?" in places25 and "?" not in used:
        pre["?"] = ("?", "all"); used.add("?")
    result = []
    for pname, boxes in sorted(places.items()):
        m, how = pre.get(pname, (None, None))
        result.append({"name": pname, "name22": m, "match": how,
                       "boxes26": sorted(boxes, key=lambda x: float(x["box"])),
                       "boxes22": sorted(places25.get(m, []), key=lambda x: float(x["box"])) if m else []})
    for pname, boxes in places25.items():
        if pname not in used:
            result.append({"name": None, "name22": pname, "match": None, "boxes26": [], "boxes22": sorted(boxes, key=lambda x: float(x["box"]))})
    return result


def slim(bx):
    return {"box": bx["box"], "e": bx["e"], "v": bx["v"], "k": bx["k"], "votes": {l: n for l, n in bx["votes"].items() if l in KEEP}}


def main():
    p = lambda f: os.path.join(LIVE, f)
    loc = json.load(open(p("localities.json"), encoding="utf-8")) if os.path.exists(p("localities.json")) else {}
    pl26 = json.load(open(p("places26.json"), encoding="utf-8")) if os.path.exists(p("places26.json")) else {}
    pl25 = json.load(open(p("places25.json"), encoding="utf-8")) if os.path.exists(p("places25.json")) else {}
    pmap = json.load(open(p("place_map.json"), encoding="utf-8")) if os.path.exists(p("place_map.json")) else {}
    # כל היישובים שמופיעים באחד הקבצים
    codes = set()
    for f in ("expb.csv", "expb25.csv"):
        rows = csv.reader(io.StringIO(decode(open(p(f), "rb").read())))
        h = [c.strip() for c in next(rows)]
        ic, iname = h.index("סמל ישוב"), h.index("שם ישוב")
        for r in rows:
            if len(r) > ic and r[ic].strip().isdigit():
                codes.add(r[ic].strip())
                loc.setdefault(r[ic].strip(), {"name": r[iname].strip(), "nafa": 0, "nafa_name": "", "district": "אחר", "moatza": ""})
    r26, r25 = read_expb(p("expb.csv"), codes), read_expb(p("expb25.csv"), codes)
    os.makedirs(p("loc"), exist_ok=True)
    index, out_all = {}, {"cities": {}}
    for code in sorted(codes, key=int):
        b26, b25 = r26.get(code, {}), r25.get(code, {})
        names26 = {k: v["place"] for k, v in pl26.get(code, {}).items()}
        names25 = {("%g" % float(x["box"])): x["place"] for x in pl25.get(code, {}).get("boxes", [])}
        places = match_places(code, b26, b25, names26, names25, pmap.get(code, {}))
        name = loc.get(code, {}).get("name") or code
        city = {"code": code, "name": name, "district": loc.get(code, {}).get("district", "אחר"), "nafa": loc.get(code, {}).get("nafa_name", ""),
                "n26": len(b26), "n22": len(b25), "named26": sum(1 for k in b26 if k in names26), "named22": sum(1 for k in b25 if k in names25),
                "places": [{**pl, "boxes26": [slim(b) for b in pl["boxes26"]], "boxes22": [slim(b) for b in pl["boxes22"]]} for pl in places]}
        json.dump(city, open(p("loc/%s.json" % code), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        agg = lambda bx: {"e": sum(b["e"] for b in bx), "v": sum(b["v"] for b in bx), "k": sum(b["k"] for b in bx),
                          "votes": {l: sum(b["votes"].get(l, 0) for b in bx) for l in KEEP if any(b["votes"].get(l) for b in bx)}}
        index[code] = {"name": name, "district": city["district"], "nafa": city["nafa"], "n26": len(b26), "n22": len(b25),
                       "hasPlaces": city["named26"] > 0, "a26": agg(b26.values()), "a22": agg(b25.values())}
        if code in CITIES:
            out_all["cities"][code] = city
    json.dump(index, open(p("loc_index.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(out_all, open(p("boxes.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("localities:", len(index), "| per-locality files in live/loc | index", os.path.getsize(p("loc_index.json")), "bytes")
    for code in CITIES:
        c = out_all["cities"].get(code)
        if c:
            m = sum(1 for x in c["places"] if x["name"] and x["name22"])
            print("  %s %s: %d boxes, %d places, matched %d" % (code, c["name"], c["n26"], sum(1 for x in c["places"] if x["name"]), m))


if __name__ == "__main__":
    sys.exit(main())
