#!/usr/bin/env python3
"""בונה live/sectors.json: סיווג יישובים לערביים/חרדיים ברובם לפי תוצאות 2022 (expc.csv של הכנסת ה-25),
עם בעלי זכות הבחירה של כל יישוב (משקל) ואחוז ההצבעה הסופי של כל מגזר ב-2022.

שימוש: python3 scripts/build_sectors.py path/to/expc25.csv
"""
import csv, io, json, sys

ARAB = ("עם", "ום", "ד")   # רע"ם, חד"ש-תע"ל, בל"ד
HAREDI = ("ג", "שס")       # יהדות התורה, ש"ס


def main(path, out="live/sectors.json"):
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1255")
    rows = list(csv.reader(io.StringIO(text)))
    h = [c.strip() for c in rows[0]]
    ix = {c: i for i, c in enumerate(h)}
    n = lambda r, c: int(r[ix[c]]) if c in ix and r[ix[c]].strip().isdigit() else 0
    sect = {"arab": {}, "haredi": {}}
    tot = {"arab": [0, 0], "haredi": [0, 0]}
    for r in rows[1:]:
        if len(r) < 8:
            continue
        valid = n(r, "כשרים")
        if not valid:
            continue
        code = r[ix["סמל ישוב"]].strip()
        a = sum(n(r, c) for c in ARAB) / valid
        hh = sum(n(r, c) for c in HAREDI) / valid
        s = "arab" if a >= 0.5 else ("haredi" if hh >= 0.5 else None)
        if not s:
            continue
        e, v = n(r, "בזב"), n(r, "מצביעים")
        sect[s][code] = e
        tot[s][0] += e
        tot[s][1] += v
    data = {
        "note": "סיווג לפי תוצאות 2022: יישוב שבו רע\"ם+חד\"ש-תע\"ל+בל\"ד קיבלו רוב = ערבי; ש\"ס+יהדות התורה רוב = חרדי. משקל = בעלי זכות בחירה 2022.",
        "arab": {"codes": sect["arab"], "eligible2022": tot["arab"][0], "turnout2022": round(tot["arab"][1] / tot["arab"][0] * 100, 1)},
        "haredi": {"codes": sect["haredi"], "eligible2022": tot["haredi"][0], "turnout2022": round(tot["haredi"][1] / tot["haredi"][0] * 100, 1)},
    }
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("arab %d localities, haredi %d localities -> %s" % (len(sect["arab"]), len(sect["haredi"]), out))


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3]))
