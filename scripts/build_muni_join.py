#!/usr/bin/env python3
r"""מחבר את תוצאות הבחירות המוניציפליות 2024 (C:\MUNI_RESULTS\muni_2024.json, לפי קלפי + כתובת) למקומות הקלפי של הכנסת
(live/stations26.json כתובות רשמיות, live/loc/<code>.json מקומות) לפי כתובת, ואז לפי שם המקום.
פלט: live/muni2024.json = {code: {name, lists:{letter:{name, bloc}}, tot:{e,v,k,votes}, places:{knessetPlace:{boxes,e,v,k,votes}}, unmatched:[{box,addr,place,e,v,k,votes}]}}
רק ליישובים שיש להם קובץ מועצה 2024 וגם מקומות קלפי של הכנסת (עם שמות).
הסיווג לגושים: live/muni_blocs.json {code:{letter:bloc}} אם קיים (אחרי בדיקת המשתמש), אחרת מ-C:\MUNI_RESULTS\haredi_lists_2024.json.
"""
import json, os, re, sys
from difflib import SequenceMatcher

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
MUNI = r"C:\MUNI_RESULTS"


def norm_addr(s):
    s = (s or "").replace("״", '"').replace("׳", "'").replace("-", " ").replace(",", " ")
    s = re.sub(r"[\"'().]", "", s)
    s = re.sub(r"\b(רחוב|רח|שד|שדרות|דרך)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def street_only(s):
    return re.sub(r"\s*\d+[א-ת]?\s*$", "", norm_addr(s)).strip()


def norm_name(s):
    s = (s or "").replace("״", '"').replace("׳", "'").replace("-", " ")
    s = re.sub(r"[\"'().,]", "", s)
    return re.sub(r"\s+", "", s)


def main():
    muni = json.load(open(os.path.join(MUNI, "muni_2024.json"), encoding="utf-8"))
    st26 = json.load(open(os.path.join(LIVE, "stations26.json"), encoding="utf-8"))
    parties = json.load(open(os.path.join(MUNI, "parties_2024.json"), encoding="utf-8"))
    bl_path = os.path.join(LIVE, "muni_blocs.json")
    blocs = json.load(open(bl_path, encoding="utf-8")) if os.path.exists(bl_path) else {}
    auto = {}
    for city, letter, name, bloc, _, _ in json.load(open(os.path.join(MUNI, "haredi_lists_2024.json"), encoding="utf-8")):
        auto.setdefault(city, {})[letter] = bloc
    idx = json.load(open(os.path.join(LIVE, "loc_index.json"), encoding="utf-8"))
    out, report = {}, []
    for code, m in muni.items():
        c = m.get("council")
        f = os.path.join(LIVE, "loc", code + ".json")
        if not c or not os.path.exists(f) or code not in st26:
            continue
        city = json.load(open(f, encoding="utf-8"))
        kplaces = [p["name"] for p in city["places"] if p["name"]]
        if not kplaces:
            continue
        # כתובת/שם של כל מקום קלפי בכנסת
        by_addr, by_street, by_name = {}, {}, {}
        for s in st26[code]["places"]:
            by_addr.setdefault(norm_addr(s["addr"]), s["name"])
            by_street.setdefault(street_only(s["addr"]), []).append(s["name"])
            by_name[norm_name(s["name"])] = s["name"]
        kset = set(kplaces)
        # שמות ואותיות
        pname = m.get("muni") or m.get("name")
        plist = parties.get(pname) or next((v for k, v in parties.items() if norm_name(k) == norm_name(str(pname))), {"lists": []})
        lists = {}
        for l in plist["lists"]:
            if l["t"] in ("Reshumak", "Council", "Com") and l["l"]:
                # קובץ הסיווג המאושר קובע לבדו ("" = לא חרדי); בלעדיו, הסיווג האוטומטי
                bloc = blocs.get(code, {}).get(l["l"], "") if blocs else auto.get(pname, {}).get(l["l"], "")
                lists[l["l"]] = {"name": l["n"], "bloc": bloc}
        cols = c["cols"]
        for l in cols:  # אות שאין לה שם בנתוני הפורטל
            if l not in lists:
                lists[l] = {"name": "(שם הרשימה לא נמצא)", "bloc": {"שס": 'ש"ס', "דגל": "דגל התורה"}.get(l, "")}
        places, unmatched, tot = {}, [], {"e": 0, "v": 0, "k": 0, "votes": {}}
        special = {"boxes": [], "e": 0, "v": 0, "k": 0, "votes": {}}  # קלפיות מיוחדות (992): חיילים, בתי חולים וכו' – בלי כתובת
        n_addr = n_street = n_name = 0
        for row in c["boxes"]:
            try:
                bnum = float(row[0])
            except (TypeError, ValueError):
                continue
            if bnum == 993:  # שורת הסיכום הרשמית
                continue
            if bnum >= 990 and "%g" % bnum not in m.get("stations", {}):  # קלפיות מיוחדות, בלי כתובת
                special["boxes"].append("%g" % bnum)
                for dst in (special, tot):
                    dst["e"] += int(row[2] or 0); dst["v"] += int(row[3] or 0); dst["k"] += int(row[5] or 0)
                    for l, v in zip(cols, row[6:]):
                        if v:
                            dst["votes"][l] = dst["votes"].get(l, 0) + int(v)
                continue
            box = "%g" % bnum
            s = m.get("stations", {}).get(box)
            votes = {l: int(v or 0) for l, v in zip(cols, row[6:]) if v}
            rec = {"box": box, "addr": s[1] if s else "", "place": s[2] if s else "", "e": int(row[2] or 0), "v": int(row[3] or 0), "k": int(row[5] or 0), "votes": votes}
            tot["e"] += rec["e"]; tot["v"] += rec["v"]; tot["k"] += rec["k"]
            for l, v in votes.items():
                tot["votes"][l] = tot["votes"].get(l, 0) + v
            target, how = None, None
            if s:
                a = norm_addr(s[1])
                if a in by_addr and by_addr[a] in kset:
                    target, how = by_addr[a], "addr"
                if not target:
                    nm = norm_name(s[2])
                    if nm in by_name and by_name[nm] in kset:
                        target, how = by_name[nm], "name"
                if not target:
                    st = street_only(s[1])
                    cands = [x for x in by_street.get(st, []) if x in kset]
                    if len(cands) == 1:
                        target, how = cands[0], "street"
                    elif len(cands) > 1:  # אותו רחוב, כמה מקומות: לפי דמיון שם המקום
                        best = max(cands, key=lambda x: SequenceMatcher(None, norm_name(x), norm_name(s[2])).ratio())
                        if SequenceMatcher(None, norm_name(best), norm_name(s[2])).ratio() >= 0.5:
                            target, how = best, "street+name"
            if target:
                n_addr += how == "addr"; n_street += how in ("street", "street+name"); n_name += how == "name"
                pl = places.setdefault(target, {"boxes": [], "e": 0, "v": 0, "k": 0, "votes": {}})
                pl["boxes"].append(box); pl["e"] += rec["e"]; pl["v"] += rec["v"]; pl["k"] += rec["k"]
                for l, v in votes.items():
                    pl["votes"][l] = pl["votes"].get(l, 0) + v
            else:
                unmatched.append(rec)
        out[code] = {"name": m["name"], "lists": lists, "cols": cols, "tot": tot, "places": places, "unmatched": unmatched, "special": special}
        report.append((code, m["name"], sum(len(p["boxes"]) for p in places.values()), len(unmatched), n_addr, n_street, n_name, len(places), len(kplaces)))
    json.dump(out, open(os.path.join(LIVE, "muni2024.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("localities joined:", len(out))
    print("code | name | boxes matched | unmatched | by addr | by street | by name | knesset places hit / total")
    for r in sorted(report, key=lambda r: -(r[2] + r[3]))[:25]:
        print("  %s | %s | %d | %d | %d | %d | %d | %d/%d" % r)


if __name__ == "__main__":
    sys.exit(main())
