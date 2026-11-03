#!/usr/bin/env python3
r"""בדיקת ודאות: האם מספר קלפי מזהה מקום? מה ודאי ומה ספק בחיבור בין השנים?
לא משנה שום נתון. כותב קובץ לבדיקה ידנית (kalpiot_audit.xlsx בשולחן העבודה) וסיכום JSON.
שימוש: python -I -X utf8 scripts/audit_matching.py <summary.json>
"""
import json, os, re, sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
MUNI = r"C:\MUNI_RESULTS"
HAREDI = {"3780", "6100", "3797", "1309", "2610", "3000", "922", "1137", "3660"}


def J(*a):
    return json.load(open(os.path.join(*a), encoding="utf-8"))


def nn(s):
    s = str(s or "").replace("״", '"').replace("׳", "'").replace("-", " ")
    return re.sub(r"[\"'().,\s]", "", s)


def sim(a, b):
    return SequenceMatcher(None, nn(a), nn(b)).ratio()


def na(s):
    s = str(s or "").replace("״", '"').replace("׳", "'").replace("-", " ").replace(",", " ")
    s = re.sub(r"[\"'().]", "", s)
    s = re.sub(r"\b(רחוב|רח|שד|שדרות|דרך)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def split_addr(s):
    m = re.match(r"^(.*?)\s*(\d+\s*[א-ת]?)?$", na(s))
    return (m.group(1).strip(), (m.group(2) or "").replace(" ", "")) if m else (na(s), "")


def cmp_addr(a, b):
    """same = זהה | street_nonum = אותו רחוב ולאחת חסר מספר | street_diff = אותו רחוב, מספר אחר | diff = שונה | na = חסר"""
    if not na(a) or not na(b):
        return "na"
    if na(a) == na(b):
        return "same"
    sa, ha = split_addr(a); sb, hb = split_addr(b)
    if sa and sa == sb:
        return "street_nonum" if (not ha or not hb) else "street_diff"
    return "diff"


def cmp_name(a, b):
    if not nn(a) or not nn(b):
        return "na"
    if nn(a) == nn(b):
        return "same"
    return "similar" if sim(a, b) >= 0.75 else "diff"


base = lambda b: str(b).split(".")[0]
is_num = lambda b: bool(re.fullmatch(r"\d+(\.\d+)?", str(b))) and float(b) < 990


def pattern(boxes):
    return "split" if any("." in b for b in boxes) else "plain"


def main(out_json):
    idx = J(LIVE, "loc_index.json"); p26 = J(LIVE, "places26.json"); p25 = J(LIVE, "places25.json")
    st26 = J(LIVE, "stations26.json"); muni = J(MUNI, "muni_2024.json"); nbhd = J(LIVE, "place_nbhd.json")
    S = {}
    # --- 2026: קלפי → מקום → כתובת
    addr26, addr_src = {}, Counter()
    for code in p26:
        by = {nn(x["name"]): x for x in st26.get(code, {}).get("places", [])}
        addr26[code] = {nn(k): v for k, v in by.items()}
    def a26(code, place):
        x = addr26.get(code, {}).get(nn(place))
        return x["addr"] if x else None
    # 2022: קלפי → מקום
    b22 = {c: {("%g" % float(x["box"])): x["place"] for x in v.get("boxes", []) if is_num(x["box"])} for c, v in p25.items()}
    # 2024: קלפי → כתובת, מקום
    b24 = {c: {b: (s[1], s[2]) for b, s in v.get("stations", {}).items() if is_num(b)} for c, v in muni.items() if v.get("stations")}
    b26 = {c: {b: v["place"] for b, v in d.items() if is_num(b)} for c, d in p26.items()}

    # --- א. בדיקת המקור: האם רשימת הכתובות הרשמית מסכימה עם אתר התוצאות על שיוך קלפי למקום?
    ok = bad = 0; bad_ex = []
    for code, d in st26.items():
        if code not in b26:
            continue
        for pl in d["places"]:
            for b in pl["boxes"]:
                if b in b26[code]:
                    if nn(b26[code][b]) == nn(pl["name"]) or sim(b26[code][b], pl["name"]) >= 0.75:
                        ok += 1
                    else:
                        bad += 1
                        if len(bad_ex) < 12:
                            bad_ex.append([idx.get(code, {}).get("name"), b, b26[code][b], pl["name"]])
    S["source_check_box_to_place"] = {"agree": ok, "disagree": bad, "examples": bad_ex}

    # --- ב. 2024 מול 2026 לפי אותו מספר קלפי מדויק (שתיהן עם כתובת רשמית)
    def scope_key(code):
        return "haredi" if code in HAREDI else "other"
    t = {k: Counter() for k in ("haredi", "other")}
    per_city = defaultdict(Counter)
    ex_moved = []
    for code in b26:
        if code not in b24:
            continue
        for b, pl in b26[code].items():
            if b not in b24[code]:
                t[scope_key(code)]["no_such_box_in_2024"] += 1; continue
            ad24, pl24 = b24[code][b]; ad = a26(code, pl)
            ca, cn = cmp_addr(ad24, ad) if ad is not None else "na", cmp_name(pl24, pl)
            t[scope_key(code)][ca + "|" + cn] += 1
            per_city[code]["n"] += 1; per_city[code]["addr_" + ca] += 1
            if ca == "diff" and code in HAREDI and len(ex_moved) < 15:
                ex_moved.append([idx[code]["name"], b, pl24, ad24, pl, ad])
    S["box_24_26_exact"] = {k: dict(v) for k, v in t.items()}
    S["box_24_26_moved_examples"] = ex_moved

    # --- ג. לפי מספר בסיס ותתי מספרים
    def groups(d):
        g = defaultdict(list)
        for b in d:
            g[base(b)].append(b)
        return g
    t = {k: Counter() for k in ("haredi", "other")}
    within = {y: Counter() for y in ("2022", "2024", "2026")}
    for code in b26:
        if code not in b24:
            continue
        g26, g24 = groups(b26[code]), groups(b24[code])
        for bb, l26 in g26.items():
            ads26 = {na(a26(code, b26[code][x]) or "") for x in l26}
            if len(l26) > 1 or "." in l26[0]:
                within["2026"]["one_place" if len({nn(b26[code][x]) for x in l26}) == 1 else "many_places"] += 1
            if bb not in g24:
                continue
            l24 = g24[bb]; ads24 = {na(b24[code][x][0]) for x in l24}
            pat = pattern(l24) + ">" + pattern(l26)
            if len(ads26) == 1 and len(ads24) == 1:
                c = cmp_addr(next(iter(ads24)), next(iter(ads26)))
            else:
                c = "same" if ads24 & ads26 else "mixed"
            t[scope_key(code)][pat + "|" + c] += 1
    for code, d in b24.items():
        for bb, l in groups(d).items():
            if len(l) > 1 or "." in l[0]:
                within["2024"]["one_place" if len({na(d[x][0]) for x in l}) == 1 else "many_places"] += 1
    for code, d in b22.items():
        for bb, l in groups(d).items():
            if len(l) > 1 or "." in l[0]:
                within["2022"]["one_place" if len({nn(d[x]) for x in l}) == 1 else "many_places"] += 1
    S["box_24_26_base"] = {k: dict(v) for k, v in t.items()}
    S["subnumbers_within_year"] = {k: dict(v) for k, v in within.items()}

    # --- ד. 2022 מול 2026 ומול 2024 לפי מספר בסיס: שם, וכתובת דרך שם ברשימת 2024
    t = {k: Counter() for k in ("haredi", "other")}; t24 = {k: Counter() for k in ("haredi", "other")}
    for code in b26:
        if code not in b22:
            continue
        name2addr24 = {nn(pl): ad for ad, pl in b24.get(code, {}).values()}
        g22, g26 = groups(b22[code]), groups(b26[code])
        for bb, l26 in g26.items():
            if bb not in g22:
                t[scope_key(code)]["no_base_in_2022"] += 1; continue
            n22 = {b22[code][x] for x in g22[bb]}; n26 = {b26[code][x] for x in l26}
            best = max(n22 | {""}, key=lambda a: max(sim(a, z) for z in n26))
            z = max(n26, key=lambda q: sim(best, q))
            cn = cmp_name(best, z)
            ad22 = name2addr24.get(nn(best)); ad = a26(code, z)
            ca = cmp_addr(ad22, ad) if ad22 and ad else "na"
            t[scope_key(code)][cn + "|" + ca] += 1
        if code in b24:
            g24 = groups(b24[code])
            for bb, l24 in g24.items():
                if bb in g22:
                    n22 = {b22[code][x] for x in g22[bb]}; n24 = {b24[code][x][1] for x in l24}
                    t24[scope_key(code)][max((cmp_name(a, z) for a in n22 for z in n24), key=["diff", "similar", "same", "na"].index)] += 1
    S["box_22_26_base"] = {k: dict(v) for k, v in t.items()}
    S["box_22_24_base_name"] = {k: dict(v) for k, v in t24.items()}

    # --- ה. מספר ברזל (נשמר רק בתשע הערים)
    same = tot = 0
    for code in HAREDI:
        z25 = {("%g" % float(x["box"])): x.get("barzel") for x in p25.get(code, {}).get("boxes", []) if is_num(x["box"])}
        for b, v in p26.get(code, {}).items():
            if b in z25 and v.get("barzel") and z25[b]:
                tot += 1; same += str(v["barzel"]) == str(z25[b])
    S["barzel_same_between_years"] = {"compared": tot, "same": same}

    # --- מעבר כקבוצה: קלפיות של אותה כתובת ב-2024, לאן הגיעו ב-2026 לפי אותו מספר
    gm = {k: Counter() for k in ("haredi", "other")}
    for code in b26:
        if code not in b24:
            continue
        grp = defaultdict(list)
        for b, (ad, pl) in b24[code].items():
            grp[na(ad)].append(b)
        for ad, bl in grp.items():
            hit = [na(a26(code, b26[code][b]) or "") for b in bl if b in b26[code]]
            if len(hit) < 2:
                continue
            c = Counter(hit); top, n = c.most_common(1)[0]
            frac = n / len(hit)
            kind = "stayed" if cmp_addr(ad, top) in ("same", "street_nonum") and frac >= 0.8 else "moved_together" if frac >= 0.8 else "stayed_partly" if cmp_addr(ad, top) in ("same", "street_nonum") else "scattered"
            gm[scope_key(code)][kind] += 1
    S["address_groups_24_26"] = {k: dict(v) for k, v in gm.items()}
    # --- תתי מספרים בכל שנה
    sub = {}
    for y, src in (("2022", b22), ("2024", b24), ("2026", b26)):
        n = t_ = 0
        for d in src.values():
            for b in d:
                t_ += 1; n += "." in b
        sub[y] = {"boxes": t_, "with_subnumber": n}
    S["subnumber_share"] = sub
    # --- חיבור מוניציפלי לכנסת: מה לא לפי כתובת זהה
    join = J(LIVE, "muni2024.json"); mrows = []; mc = Counter(); mvot = Counter()
    HB = ("דגל התורה", "אגודת ישראל", "יהדות התורה (דגל+אגודה)", 'ש"ס', 'משותפת: יהדות התורה + ש"ס', "בני תורה (פלג)", "חרדי כללי")
    for code, j in join.items():
        hl = [l for l, v in j["lists"].items() if v["bloc"] in HB]
        st = muni.get(code, {}).get("stations", {})
        for pl, v in j["places"].items():
            ad26 = a26(code, pl)
            for b in v["boxes"]:
                s_ = st.get(b)
                c = cmp_addr(s_[1], ad26) if s_ and ad26 else "na"
                mc["boxes_" + c] += 1
                if c != "same":
                    rec = next((r for r in muni[code]["council"]["boxes"] if str(r[0]) in (b, b + ".0") or ("%g" % float(r[0]) == b if is_num(r[0]) else False)), None)
                    hv = sum(int((rec[6:] + [0] * 99)[muni[code]["council"]["cols"].index(l)] or 0) for l in hl) if rec else 0
                    mrows.append([code in HAREDI, j["name"], b, s_[1] if s_ else "", s_[2] if s_ else "", "שויך ברמת ספק", pl, ad26 or "", hv, "", ""])
        for u in j["unmatched"]:
            mc["unmatched"] += 1
            hv = sum(u["votes"].get(l, 0) for l in hl); mvot["unmatched_haredi"] += hv
            mrows.append([code in HAREDI, j["name"], u["box"], u["addr"], u["place"], "לא שויך", "", "", hv, "", ""])
    mrows.sort(key=lambda r: (not r[0], r[1], r[5], -r[8]))
    S["muni_join"] = {**dict(mc), **dict(mvot), "rows": len(mrows)}

    # --- ו. סיווג כל חיבור בין 2022 ל-2026
    rows, certain, tiers = [], [], Counter()
    votes = lambda bx, l: sum(b["votes"].get(l, 0) for b in bx)
    for code in sorted(b26, key=lambda c: (c not in HAREDI, -idx[c]["a26"]["e"])):
        f = os.path.join(LIVE, "loc", code + ".json")
        if not os.path.exists(f):
            continue
        city = J(f); cname = city["name"]
        name2addr24 = {nn(pl): ad for ad, pl in b24.get(code, {}).values()}
        pls26 = [p for p in city["places"] if p["name"]]
        addr_of26 = {p["name"]: a26(code, p["name"]) for p in pls26}
        def addr22(name):
            a = name2addr24.get(nn(name))
            if a:
                return a, "exact"
            if name2addr24:
                k = max(name2addr24, key=lambda z: SequenceMatcher(None, z, nn(name)).ratio())
                if SequenceMatcher(None, k, nn(name)).ratio() >= 0.75:
                    return name2addr24[k], "similar"
            return None, None
        def hints_for22(p):
            bases = {base(b["box"]) for b in p["boxes22"]}; h_b, h_a, h_n = [], [], []
            ad, how = addr22(p["name22"])
            for q in pls26:
                qb = {base(b["box"]) for b in q["boxes26"]}
                ov = len(bases & qb)
                if ov:
                    h_b.append((ov / len(bases), q["name"]))
                if ad and addr_of26.get(q["name"]) and cmp_addr(ad, addr_of26[q["name"]]) in ("same", "street_nonum"):
                    h_a.append(q["name"])
                s_ = sim(p["name22"], q["name"])
                if s_ >= 0.6:
                    h_n.append((s_, q["name"]))
            return ad, how, sorted(h_b, reverse=True)[:3], h_a[:3], sorted(h_n, reverse=True)[:3]
        for p in city["places"]:
            bx26, bx22 = p["boxes26"], p["boxes22"]
            common = {"code": code, "city": cname, "n26": p["name"] or "", "n22": p["name22"] or "", "ad26": addr_of26.get(p["name"]) or "", "boxes26": ", ".join(b["box"] for b in bx26), "boxes22": ", ".join(b["box"] for b in bx22),
                      "e26": sum(b["e"] for b in bx26), "g26": votes(bx26, "ג"), "s26": votes(bx26, "שס"), "g22": votes(bx22, "ג"), "s22": votes(bx22, "שס"), "haredi": code in HAREDI, "nb": nbhd.get(code, {}).get(p["name"], "")}
            if p["name"] and p["name22"]:
                ad, how = addr22(p["name22"]); cn = cmp_name(p["name22"], p["name"])
                ca = cmp_addr(ad, addr_of26[p["name"]]) if ad and addr_of26.get(p["name"]) else "na"
                b1, b2 = {base(b["box"]) for b in bx22}, {base(b["box"]) for b in bx26}
                ov = len(b1 & b2) / max(1, min(len(b1), len(b2)))
                pos = (cn in ("same", "similar")) + (ov >= 0.5) + (ca in ("same", "street_nonum"))
                reason = []
                if ca == "diff": reason.append("הכתובות שונות")
                if ca == "street_diff": reason.append("אותו רחוב, מספר בית אחר")
                if cn == "diff": reason.append("השמות שונים")
                if ov < 0.5: reason.append("מעט קלפיות חופפות (%d%%)" % round(100 * ov))
                if ca == "na": reason.append("אין כתובת להשוואה")
                good = pos >= 2 and ca not in ("diff", "street_diff")
                common.update(ad22=ad or "", name_sig=cn, addr_sig=ca, box_ov=round(ov, 2), reason=" · ".join(reason))
                if good:
                    tiers["pair_certain"] += 1; tiers["pair_certain_g26"] += common["g26"]; certain.append(common)
                else:
                    tiers["pair_doubt"] += 1; tiers["pair_doubt_g26"] += common["g26"]
                    rows.append({**common, "kind": "חיבור קיים בספק"})
            elif p["name22"] and not p["name"]:
                ad, how, hb, ha, hn = hints_for22(p)
                tiers["old_unmatched"] += 1; tiers["old_unmatched_g22"] += common["g22"]
                rows.append({**common, "kind": "מקום 2022 בלי חיבור", "ad22": ad or "", "reason": "לא נמצא מקום מקביל ב-2026", "hint_addr": " ; ".join(ha), "hint_box": " ; ".join("%s (%d%%)" % (n, round(100 * s_)) for s_, n in hb), "hint_name": " ; ".join("%s (%d%%)" % (n, round(100 * s_)) for s_, n in hn)})
            elif p["name"] and not p["name22"]:
                bases = {base(b["box"]) for b in bx26}; olds = [q for q in city["places"] if q["name22"]]
                hb, ha, hn = [], [], []
                for q in olds:
                    qb = {base(b["box"]) for b in q["boxes22"]}; ov = len(bases & qb)
                    if ov: hb.append((ov / len(bases), q["name22"]))
                    a2, _ = addr22(q["name22"])
                    if a2 and addr_of26.get(p["name"]) and cmp_addr(a2, addr_of26[p["name"]]) in ("same", "street_nonum"): ha.append(q["name22"])
                    s_ = sim(q["name22"], p["name"])
                    if s_ >= 0.6: hn.append((s_, q["name22"]))
                tiers["new_unmatched"] += 1; tiers["new_unmatched_g26"] += common["g26"]
                rows.append({**common, "kind": "מקום 2026 בלי חיבור", "ad22": "", "reason": "לא נמצא מקום מקביל ב-2022", "hint_addr": " ; ".join(ha[:3]), "hint_box": " ; ".join("%s (%d%%)" % (n, round(100 * s_)) for s_, n in sorted(hb, reverse=True)[:3]), "hint_name": " ; ".join("%s (%d%%)" % (n, round(100 * s_)) for s_, n in sorted(hn, reverse=True)[:3])})
            if p["name"] and not addr_of26.get(p["name"]):
                tiers["place26_no_exact_address"] += 1
    S["tiers"] = dict(tiers)

    # --- ז. עמודות לגיליון
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    HF, Y = PatternFill("solid", fgColor="E6EFEE"), PatternFill("solid", fgColor="FFF4CC")

    def sheet(title, head, data, widths, fill=()):
        ws = wb.create_sheet(title[:31]); ws.sheet_view.rightToLeft = True; ws.append(head)
        for c in ws[1]:
            c.font = Font(bold=True); c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical="top")
        for r in data:
            ws.append(r)
        for row in ws.iter_rows(min_row=2):
            for i in fill:
                row[i].fill = Y
        for i, w in enumerate(widths):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    order = {"חיבור קיים בספק": 0, "מקום 2022 בלי חיבור": 1, "מקום 2026 בלי חיבור": 2}
    rows.sort(key=lambda r: (not r["haredi"], r["city"], order[r["kind"]], -(r["g22"] + r["g26"])))
    head = ["עיר", "סוג הספק", "למה ספק", "שם 2022", "כתובת 2022 (דרך רשימת 2024)", "קלפיות 2022", "יהדות התורה 2022", 'ש"ס 2022', "שם 2026", "כתובת 2026 (רשמית)", "קלפיות 2026", "יהדות התורה 2026", 'ש"ס 2026', "שכונה", "רמז: אותה כתובת", "רמז: אותם מספרי קלפי", "רמז: שם דומה", "✔ אותו מקום כמו", "✔ כתובת נכונה", "הערות"]
    sheet("ספקות", head, [[r["city"], r["kind"], r.get("reason", ""), r["n22"], r.get("ad22", ""), r["boxes22"], r["g22"] if r["n22"] else "", r["s22"] if r["n22"] else "", r["n26"], r["ad26"], r["boxes26"], r["g26"] if r["n26"] else "", r["s26"] if r["n26"] else "", r["nb"], r.get("hint_addr", ""), r.get("hint_box", ""), r.get("hint_name", ""), "", "", ""] for r in rows],
          [14, 18, 30, 30, 22, 16, 9, 8, 30, 22, 16, 9, 8, 14, 28, 30, 30, 26, 22, 18], fill=(17, 18, 19))
    sheet("מוניציפלי - ספק", ["עיר", "קלפי 2024", "כתובת 2024", "מקום 2024", "מצב", "מקום כנסת ששויך", "כתובת כנסת", "קולות חרדיים 2024", "✔ שיוך נכון", "הערות"], [r[1:] for r in mrows], [14, 8, 24, 30, 14, 30, 24, 9, 26, 18], fill=(8, 9))
    bycity = defaultdict(Counter)
    for r in certain:
        bycity[r["city"]]["cert"] += 1; bycity[r["city"]]["cert_g"] += r["g26"]
    for r in rows:
        k = {"חיבור קיים בספק": "doubt", "מקום 2022 בלי חיבור": "old", "מקום 2026 בלי חיבור": "new"}[r["kind"]]
        bycity[r["city"]][k] += 1; bycity[r["city"]][k + "_g"] += r["g26"] if k != "old" else r["g22"]
    S["by_city_haredi"] = {idx[c]["name"]: dict(bycity[idx[c]["name"]]) for c in HAREDI}
    certain.sort(key=lambda r: (not r["haredi"], r["city"], -r["g26"]))
    sheet("ודאי - לבדיקה מדגמית", ["עיר", "שם 2022", "כתובת 2022 (דרך רשימת 2024)", "קלפיות 2022", "יהדות התורה 2022", "שם 2026", "כתובת 2026", "קלפיות 2026", "יהדות התורה 2026", "שם", "כתובת", "חפיפת קלפיות"],
          [[r["city"], r["n22"], r["ad22"], r["boxes22"], r["g22"], r["n26"], r["ad26"], r["boxes26"], r["g26"], r["name_sig"], r["addr_sig"], r["box_ov"]] for r in certain], [14, 30, 22, 16, 9, 30, 22, 16, 9, 8, 12, 9])
    cityrows = []
    for code, c in sorted(per_city.items(), key=lambda kv: (kv[0] not in HAREDI, -kv[1]["n"])):
        n = c["n"]; cityrows.append([idx[code]["name"], n, c["addr_same"], c["addr_street_nonum"], c["addr_street_diff"], c["addr_diff"], c["addr_na"], round(100 * (c["addr_same"] + c["addr_street_nonum"]) / n, 1) if n else ""])
    sheet("מספר קלפי לפי עיר", ["עיר", "קלפיות עם אותו מספר ב-2024 וב-2026", "אותה כתובת", "אותו רחוב, לאחת חסר מספר", "אותו רחוב, מספר אחר", "כתובת אחרת", "אין כתובת", "% באותה כתובת"], cityrows, [18, 12, 10, 12, 12, 10, 9, 10])
    out = os.path.join(os.path.expanduser("~"), "Desktop", "kalpiot_audit.xlsx")
    wb.save(out)
    S["written"] = out; S["doubts"] = dict(Counter(r["kind"] for r in rows)); S["doubts_haredi"] = dict(Counter(r["kind"] for r in rows if r["haredi"])); S["certain_pairs"] = len(certain)
    S["totals"] = {"haredi_cert": sum(1 for r in certain if r["haredi"])}
    json.dump(S, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
