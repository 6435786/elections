#!/usr/bin/env python3
r"""קובץ ספקות לערים החרדיות: הצעות חיבור לאישור (כן/לא), חיבורים קיימים בספק, מקומות בלי הצעה, וקלפיות מוניציפליות בספק.
לא משנה נתונים. פלט: kalpiot_haredi_doubts.xlsx בשולחן העבודה."""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_matching import nn, sim, cmp_addr, cmp_name, base, HAREDI, LIVE, MUNI, J, is_num
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

idx = J(LIVE, "loc_index.json"); st26 = J(LIVE, "stations26.json"); muni = J(MUNI, "muni_2024.json"); nbh = J(LIVE, "place_nbhd.json"); join = J(LIVE, "muni2024.json")
g = lambda bx: sum(b["votes"].get("ג", 0) for b in bx)
sh = lambda bx: sum(b["votes"].get("שס", 0) for b in bx)
bl = lambda bx: ", ".join(b["box"] for b in bx)
rows, cnt = [], Counter()
for code in sorted(HAREDI, key=lambda c: -idx[c]["a26"]["e"]):
    city = J(LIVE, "loc", code + ".json"); cn = city["name"]
    a26 = {nn(s["name"]): s["addr"] for s in st26.get(code, {}).get("places", [])}
    n2a = {nn(s[2]): s[1] for b, s in muni.get(code, {}).get("stations", {}).items() if is_num(b)}

    def addr22(name):
        k = nn(name)
        if k in n2a:
            return n2a[k]
        best = max(n2a, key=lambda z: sim(z, k), default=None)
        return n2a[best] if best and sim(best, k) >= 0.75 else ""

    def sig(o, n):
        ad, an = addr22(o["name22"]), a26.get(nn(n["name"]), "")
        ca = cmp_addr(ad, an) if ad and an else "na"
        b1, b2 = {base(b["box"]) for b in o["boxes22"]}, {base(b["box"]) for b in n["boxes26"]}
        return sim(o["name22"], n["name"]), ca, len(b1 & b2) / max(1, min(len(b1), len(b2)))

    def why(s_, ca, ov):
        t = []
        if ca == "same": t.append("אותה כתובת")
        elif ca == "street_nonum": t.append("אותו רחוב, לאחת חסר מספר בית")
        elif ca == "street_diff": t.append("אותו רחוב, מספר בית אחר")
        elif ca == "diff": t.append("כתובת אחרת")
        if s_ >= 0.75: t.append("שם דומה (%d%%)" % round(100 * s_))
        if ov > 0: t.append("%d%% מהמספרים חופפים" % round(100 * ov))
        return " · ".join(t) or "אין סימן"

    def strength(s_, ca, ov):
        if ca in ("diff", "street_diff") and s_ >= 0.75: return "סתירה: שם דומה אבל כתובת אחרת"
        if (ca == "same" and (s_ >= 0.75 or ov >= 0.5)) or (s_ >= 0.75 and ov >= 0.5): return "חזק: שני סימנים"
        if ca == "street_nonum" and ov >= 0.5: return "בינוני: אותו רחוב ואותם מספרים"
        if ca == "same" or s_ >= 0.75: return "בינוני: סימן אחד (כתובת או שם)"
        if ov >= 0.5 and ca not in ("diff",): return "חלש: מספרי קלפי בלבד, נכון בערך בחצי מהמקרים"
        if ov >= 0.5: return "חלש מאוד: אותם מספרים אבל כתובת אחרת, אולי מעבר קבוצה"
        return "חלש"
    news = [p for p in city["places"] if p["name"]]; olds = [p for p in city["places"] if not p["name"]]
    base_row = lambda p22, p26: [cn, p22["name22"] if p22 else "", addr22(p22["name22"]) if p22 else "", bl(p22["boxes22"]) if p22 else "", g(p22["boxes22"]) if p22 else "", sh(p22["boxes22"]) if p22 else "", p26["name"] if p26 else "", a26.get(nn(p26["name"]), "") if p26 else "", bl(p26["boxes26"]) if p26 else "", g(p26["boxes26"]) if p26 else "", sh(p26["boxes26"]) if p26 else "", nbh.get(code, {}).get(p26["name"], "") if p26 else ""]
    used = set()
    for o in sorted(olds, key=lambda p: -g(p["boxes22"])):
        cands = []
        for n in news:
            s_, ca, ov = sig(o, n)
            score = (ca == "same") * 3 + (ca == "street_nonum") * 1.5 + (s_ >= 0.75) * 2 + (ov >= 0.5) * 1 + (0 < ov < 0.5) * 0.3 - (ca == "diff") * 0.5
            cands.append((score, s_, ca, ov, n))
        cands.sort(key=lambda t: (-t[0], -t[3]))
        if cands and cands[0][0] >= 0.3:
            _, s_, ca, ov, n = cands[0]
            used.add(n["name"])
            paired = "· המקום של 2026 כבר מחובר ל: " + n["name22"] if n["name22"] else ""
            alt = " ; ".join("%s (%s)" % (t[4]["name"], why(t[1], t[2], t[3])) for t in cands[1:3] if t[0] >= 0.3)
            rows.append(("1 הצעת חיבור", base_row(o, n), strength(s_, ca, ov), (why(s_, ca, ov) + " " + paired).strip(), alt)); cnt["suggest"] += 1
        else:
            rows.append(("3 מקום 2022 בלי הצעה", base_row(o, None), "", "לא נמצא סימן למקום מקביל", "")); cnt["old_none"] += 1
    for p in news:
        if p["name22"]:
            s_, ca, ov = sig(p, p)
            pos = (s_ >= 0.75) + (ov >= 0.5) + (ca in ("same", "street_nonum"))
            if pos < 2 or ca in ("diff", "street_diff"):
                rows.append(("2 חיבור קיים בספק", base_row(p, p), strength(s_, ca, ov), why(s_, ca, ov), "")); cnt["pair"] += 1
        elif p["name"] not in used:
            bases = {base(b["box"]) for b in p["boxes26"]}; h = []
            for q in city["places"]:
                if q["name22"]:
                    ov = len(bases & {base(b["box"]) for b in q["boxes22"]}) / max(1, len(bases))
                    s_ = sim(q["name22"], p["name"])
                    if ov > 0 or s_ >= 0.6:
                        h.append((ov + s_, "%s (%d%% מספרים, %d%% שם)" % (q["name22"], round(100 * ov), round(100 * s_))))
            rows.append(("4 מקום 2026 בלי הצעה", base_row(None, p), "", "אולי מקום חדש באמת", " ; ".join(x[1] for x in sorted(h, reverse=True)[:3]))); cnt["new_none"] += 1
rows.sort(key=lambda r: (r[1][0], r[0], -((r[1][4] or 0) + (r[1][9] or 0))))
wb = openpyxl.Workbook(); wb.remove(wb.active)
HF, Y = PatternFill("solid", fgColor="E6EFEE"), PatternFill("solid", fgColor="FFF4CC")
ws = wb.create_sheet("ספקות"); ws.sheet_view.rightToLeft = True
ws.append(["עיר", "סוג", "חוזק ההצעה", "על מה זה מבוסס", "שם 2022", "כתובת 2022 (דרך 2024)", "קלפיות 2022", "יהדות התורה 2022", 'ש"ס 2022', "שם 2026", "כתובת 2026", "קלפיות 2026", "יהדות התורה 2026", 'ש"ס 2026', "שכונה", "אפשרויות נוספות", "✔ נכון?", "✔ אם לא: השם הנכון מהשנה השנייה", "✔ הערות"])
for c in ws[1]:
    c.font = Font(bold=True); c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical="top")
for kind, b, st, wh, alt in rows:
    ws.append([b[0], kind[2:], st, wh, *b[1:], alt, "", "", ""])
dv = DataValidation(type="list", formula1='"כן,לא,לא יודע"', allow_blank=True); ws.add_data_validation(dv); dv.add("Q2:Q%d" % max(2, ws.max_row))
for row in ws.iter_rows(min_row=2):
    for i in (16, 17, 18):
        row[i].fill = Y
for i, w in enumerate([12, 17, 22, 28, 28, 20, 14, 8, 7, 28, 20, 14, 8, 7, 13, 30, 9, 26, 18]):
    ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
ws.freeze_panes = "B2"; ws.auto_filter.ref = ws.dimensions
# מוניציפלי בערים החרדיות
HB = ("דגל התורה", "אגודת ישראל", "יהדות התורה (דגל+אגודה)", 'ש"ס', 'משותפת: יהדות התורה + ש"ס', "בני תורה (פלג)", "חרדי כללי")
mr = []
for code in HAREDI:
    j = join.get(code)
    if not j:
        continue
    a26 = {nn(s["name"]): s["addr"] for s in st26.get(code, {}).get("places", [])}; st = muni[code]["stations"]; hl = [l for l, v in j["lists"].items() if v["bloc"] in HB]; cols = muni[code]["council"]["cols"]
    recs = {("%g" % float(r[0])): r for r in muni[code]["council"]["boxes"] if is_num(r[0])}
    for pl, v in j["places"].items():
        for b in v["boxes"]:
            s_ = st.get(b); c = cmp_addr(s_[1], a26.get(nn(pl))) if s_ and a26.get(nn(pl)) else "na"
            if c != "same":
                r = recs.get(b); hv = sum(int((list(r[6:]) + [0] * 99)[cols.index(l)] or 0) for l in hl) if r else 0
                mr.append([j["name"], b, s_[1] if s_ else "", s_[2] if s_ else "", "שויך לפי " + {"street_nonum": "אותו רחוב, לאחת חסר מספר", "street_diff": "אותו רחוב, מספר אחר", "diff": "שם דומה, כתובת אחרת", "na": "שם"}[c], pl, a26.get(nn(pl), ""), hv, "", "", ""])
    for u in j["unmatched"]:
        mr.append([j["name"], u["box"], u["addr"], u["place"], "לא שויך", "", "", sum(u["votes"].get(l, 0) for l in hl), "", "", ""])
mr.sort(key=lambda r: (r[0], r[4], -r[7]))
ws2 = wb.create_sheet("מוניציפלי"); ws2.sheet_view.rightToLeft = True
ws2.append(["עיר", "קלפי 2024", "כתובת 2024", "מקום 2024", "מצב", "מקום בכנסת ששויך", "כתובת בכנסת", "קולות חרדיים 2024", "✔ נכון?", "✔ אם לא: המקום הנכון ב-2026", "✔ הערות"])
for c in ws2[1]:
    c.font = Font(bold=True); c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical="top")
for r in mr:
    ws2.append(r)
dv2 = DataValidation(type="list", formula1='"כן,לא,לא יודע"', allow_blank=True); ws2.add_data_validation(dv2); dv2.add("I2:I%d" % max(2, ws2.max_row))
for row in ws2.iter_rows(min_row=2):
    for i in (8, 9, 10):
        row[i].fill = Y
for i, w in enumerate([12, 8, 22, 28, 24, 28, 22, 9, 9, 26, 18]):
    ws2.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
ws2.freeze_panes = "B2"; ws2.auto_filter.ref = ws2.dimensions
out = os.path.join(os.path.expanduser("~"), "Desktop", "kalpiot_haredi_doubts.xlsx")
wb.save(out)
strengths = Counter(r[2] for r in rows if r[0].startswith("1"))
print(json.dumps({"rows": len(rows), "kinds": dict(cnt), "strength": dict(strengths), "by_city": dict(Counter(r[1][0] for r in rows)), "muni_rows": len(mr), "muni_by_city": dict(Counter(r[0] for r in mr)), "muni_status": dict(Counter(r[4] for r in mr)), "muni_unmatched_votes": sum(r[7] for r in mr if r[4] == "לא שויך")}, ensure_ascii=False, indent=0))
