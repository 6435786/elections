#!/usr/bin/env python3
r"""חיבור מקומות קלפי 2022↔2026 בערים שאינן חרדיות, לפי כלל המשתמש (3.11.2026):
מקבלים חיבור אם יש שם דומה/זהה, או כתובת זהה (2022: דרך השם ברשימת 2024), או כתובת חלקית + חפיפת מספרי קלפי.
מספר קלפי לבדו אינו מספיק. כמה מקומות של 2022 יכולים להתחבר למקום אחד של 2026.
הערים החרדיות (HAREDI) לא נוגעים. מריצים אחרי build_boxes.py; סה"כ היישוב לא משתנה (נבדק כאן).
שימוש: python -I -X utf8 scripts/rematch_other_cities.py [--dry]
"""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_matching import nn, sim, cmp_addr, base, HAREDI, LIVE, MUNI, J, is_num


def main():
    dry = "--dry" in sys.argv
    idx = J(LIVE, "loc_index.json"); st26 = J(LIVE, "stations26.json"); muni = J(MUNI, "muni_2024.json")
    c = Counter(); changed = {}
    for code, x in idx.items():
        f = os.path.join(LIVE, "loc", code + ".json")
        if code in HAREDI or code == "9999" or not x.get("hasPlaces") or not os.path.exists(f):
            continue
        city = J(f)
        if not any(p["name22"] and p["name22"] != "?" for p in city["places"]):
            continue
        a26 = {nn(s["name"]): s["addr"] for s in st26.get(code, {}).get("places", [])}
        n2a = {nn(s[2]): s[1] for b, s in muni.get(code, {}).get("stations", {}).items() if is_num(b)}

        def addr22(name):
            k = nn(name)
            if k in n2a:
                return n2a[k]
            best = max(n2a, key=lambda z: sim(z, k), default=None)
            return n2a[best] if best and sim(best, k) >= 0.75 else None

        def signals(old, new):
            s_ = sim(old["name22"], new["name"])
            ad, an = addr22(old["name22"]), a26.get(nn(new["name"]))
            ca = cmp_addr(ad, an) if ad and an else "na"
            b1, b2 = {base(b["box"]) for b in old["boxes22"]}, {base(b["box"]) for b in new["boxes26"]}
            ov = len(b1 & b2) / max(1, min(len(b1), len(b2)))
            return s_, ca, ov

        def accepted(s_, ca, ov):
            if s_ >= 0.75:
                return "name"
            if ca == "same":
                return "address"
            if ca == "street_nonum" and ov >= 0.5:
                return "address_partial+boxes"
            return None

        # שלב 1: חיבורים קיימים שלא עומדים בכלל מתפרקים
        places, freed = [], []
        for p in city["places"]:
            if p["name"] and p["name22"] and p["name22"] != "?" and not p.get("how"):
                s_, ca, ov = signals(p, p)
                how = accepted(s_, ca, ov)
                if how:
                    p["how"] = how; c["kept_" + how] += 1
                else:
                    c["unlinked"] += 1
                    freed.append({"name": None, "name22": p["name22"], "match": None, "boxes26": [], "boxes22": p["boxes22"]})
                    p["name22"], p["match"], p["boxes22"] = None, None, []
            places.append(p)
        places += freed
        # שלב 2: מקומות 2022 בלי חיבור מחפשים מקום 2026 (גם אם כבר מחובר)
        news = [p for p in places if p["name"]]
        rest = []
        for o in [p for p in places if not p["name"]]:
            scored = []
            for n in news:
                s_, ca, ov = signals(o, n)
                how = accepted(s_, ca, ov)
                if how:
                    scored.append(((how == "name") * s_ * 2 + (ca == "same") * 1.5 + ov * 0.5, how, n))
            if scored:
                _, how, n = max(scored, key=lambda t: t[0])
                n["names22"] = (n.get("names22") or ([n["name22"]] if n["name22"] else [])) + [o["name22"]]
                n["name22"] = " + ".join(n["names22"]); n["boxes22"] = n["boxes22"] + o["boxes22"]; n["how"] = n.get("how") or how; n["match"] = "rematch"
                c["linked_" + how] += 1; c["linked_g22"] += sum(b["votes"].get("ג", 0) for b in o["boxes22"])
            else:
                rest.append(o); c["still_old"] += 1; c["still_old_g22"] += sum(b["votes"].get("ג", 0) for b in o["boxes22"])
        final = news + rest
        for n in news:
            if not n["name22"]:
                c["still_new"] += 1; c["still_new_g26"] += sum(b["votes"].get("ג", 0) for b in n["boxes26"])
        # בדיקת שלמות: סה"כ היישוב לא השתנה
        tot = lambda ps, y: (sum(len(p[y]) for p in ps), sum(b["e"] for p in ps for b in p[y]), sum(b["k"] for p in ps for b in p[y]), sum(b["votes"].get("ג", 0) for p in ps for b in p[y]))
        orig = J(f)["places"]
        assert tot(final, "boxes26") == tot(orig, "boxes26") and tot(final, "boxes22") == tot(orig, "boxes22"), code
        city["places"] = final; changed[code] = city; c["cities"] += 1
    print(json.dumps(c, ensure_ascii=False))
    if not dry:
        for code, city in changed.items():
            json.dump(city, open(os.path.join(LIVE, "loc", code + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("written", len(changed), "locality files")


if __name__ == "__main__":
    sys.exit(main())
