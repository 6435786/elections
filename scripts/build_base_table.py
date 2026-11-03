#!/usr/bin/env python3
r"""טבלת בסיס אחת: שורה לכל אשכול (מקומות קלפי מחוברים), עם כנסת 2026, כנסת 2022 ומוניציפלי 2024, ורמת ודאות לכל חיבור.
רמות: ודאי = שתי הוכחות בלי סתירה | כמעט ודאי = שם או כתובת, או כמה מספרי קלפי משותפים | השערה = מספר יחיד או רמז חלש | ללא שיוך.
לא משנה קובץ קיים. כותב live/base_table.json, טבלה לשולחן העבודה, ובודק שכל הסה"כ נשמרים מול הנתונים הרשמיים.
שימוש: python -I -X utf8 scripts/build_base_table.py <summary.json>
"""
import json, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_matching import nn, sim, cmp_addr, base, HAREDI, LIVE, MUNI, J, is_num

CERT, NEAR, GUESS, NONE = "ודאי", "כמעט ודאי", "השערה", "ללא שיוך"
RANK = {CERT: 3, NEAR: 2, GUESS: 1, NONE: 0}
BLOCS = {"דגל התורה": "dagel", "אגודת ישראל": "aguda", "יהדות התורה (דגל+אגודה)": "utj", 'ש"ס': "shas", 'משותפת: יהדות התורה + ש"ס': "joint", "בני תורה (פלג)": "peleg", "חרדי כללי": "other"}
KEEP = ["ג", "שס", "זך", "נר", "מחל", "ב", "ט", "ך", "דרך", "רק", "אמת", "ל", "די", "עם", "ודם", "פה", "כן", "מרצ", "ום", "ד", "ני"]
ALIAS = {"1061": "נוף הגליל"}


def sumbox(boxes):
    r = {"n": len(boxes), "e": 0, "v": 0, "k": 0, "votes": Counter()}
    for b in boxes:
        r["e"] += b["e"]; r["v"] += b["v"]; r["k"] += b["k"]
        r["votes"].update(b["votes"])
    return r


def worst(tiers):
    return min(tiers, key=lambda t: RANK[t])


def main(summary_path):
    idx = J(LIVE, "loc_index.json"); p26 = J(LIVE, "places26.json"); st26 = J(LIVE, "stations26.json"); pts = J(LIVE, "points.json"); nb = J(LIVE, "place_nbhd.json")
    join = J(LIVE, "muni2024.json"); blocs = J(LIVE, "muni_blocs.json"); muni = J(MUNI, "muni_2024.json")
    rows = []
    for code, x in idx.items():
        city = J(LIVE, "loc", code + ".json"); name = ALIAS.get(code) or city["name"]
        head = {"code": code, "city": name, "district": x["district"], "nafa": x["nafa"], "haredi": code in HAREDI}
        if code == "9999" or code not in p26:
            ll = [(s["lat"], s["lon"]) for s in st26.get(code, {}).get("places", []) if s["lat"]]
            b26 = [b for p in city["places"] for b in p["boxes26"]]; b22 = [b for p in city["places"] for b in p["boxes22"]]
            rows.append({**head, "kind": "external" if code == "9999" else "whole", "names26": [name], "names22": [name] if b22 else [], "addr": "", "nbhd": "", "lat": round(sum(a for a, _ in ll) / len(ll), 5) if ll else None, "lon": round(sum(b for _, b in ll) / len(ll), 5) if ll else None,
                         "tier": CERT if b26 and b22 else NONE, "why": "מעטפות חיצוניות" if code == "9999" else "יישוב שלם", "y26": sumbox(b26), "y22": sumbox(b22), "boxes26": [b["box"] for b in b26], "boxes22": [b["box"] for b in b22]})
            continue
        a26 = {nn(s["name"]): s["addr"] for s in st26.get(code, {}).get("places", [])}
        n2a = {nn(s[2]): s[1] for b, s in muni.get(code, {}).get("stations", {}).items() if is_num(b)}

        def addr22(n):
            k = nn(n)
            if k in n2a:
                return n2a[k]
            best = max(n2a, key=lambda z: sim(z, k), default=None)
            return n2a[best] if best and sim(best, k) >= 0.75 else None
        pl = city["places"]; parent = list(range(len(pl)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i

        def bases(p, y):
            return {base(b["box"]) for b in p[y]}

        def sig(name22, boxes22_bases, q):
            s_ = sim(name22, q["name"]); ad, an = addr22(name22), a26.get(nn(q["name"]))
            ca = cmp_addr(ad, an) if ad and an else "na"
            b2 = bases(q, "boxes26"); common = len(boxes22_bases & b2); ov = common / max(1, min(len(boxes22_bases), len(b2)))
            return s_, ca, ov, common

        def tier_of(s_, ca, ov, common):
            name_ok, addr_ok = s_ >= 0.75, ca == "same"; part = ca == "street_nonum"; num_ok = ov >= 0.5; conflict = ca in ("diff", "street_diff")
            if name_ok + num_ok + (addr_ok or part) >= 2 and not conflict:
                return CERT, "שתי הוכחות"
            if name_ok and conflict:
                return NEAR, "אותו שם, כתובת אחרת: כנראה עבר בניין"
            if name_ok:
                return NEAR, "שם בלבד"
            if addr_ok:
                return NEAR, "כתובת בלבד"
            if num_ok and common >= 2:
                return NEAR, "כמה מספרי קלפי משותפים" + (", כתובת אחרת: כנראה עברו בניין" if conflict else "")
            if common:
                return GUESS, "מספר קלפי בלבד"
            return GUESS, "רמז חלש בלבד"
        edges = defaultdict(list); member = {}
        for i, p in enumerate(pl):
            if p["name"] and p["name22"]:
                if p.get("names22"):
                    edges[i].append((NEAR, "כמה מקומות 2022 התחברו לפי " + {"name": "שם", "address": "כתובת"}.get(p.get("how"), "כתובת חלקית ומספרים")))
                else:
                    edges[i].append(tier_of(*sig(p["name22"], bases(p, "boxes22"), p)))
                member[i] = edges[i][-1][0]
        named = [i for i, p in enumerate(pl) if p["name"]]
        for i, o in enumerate(pl):
            if o["name"]:
                continue
            bo = bases(o, "boxes22"); best = None
            for j in named:
                s_, ca, ov, c = sig(o["name22"], bo, pl[j])
                score = (ca == "same") * 3 + (ca == "street_nonum") * 1.5 + (s_ >= 0.75) * 2 + ov + c * 0.01 - (ca == "diff") * 0.5
                if (c or s_ >= 0.6 or ca in ("same", "street_nonum")) and (not best or score > best[0]):
                    best = (score, j, s_, ca, ov, c)
            if best:
                _, j, s_, ca, ov, c = best
                parent[find(i)] = find(j); edges[find(j)].append(tier_of(s_, ca, ov, c)); member[i] = edges[find(j)][-1][0]; member.setdefault(j, member[i])  # מקום 2026 שהתחבר דרך מקום 2022 מקבל את אותה רמה
        linked = {find(i) for i, p in enumerate(pl) if not p["name"]}
        for j in named:
            p = pl[j]
            if p["name22"] or sum(1 for i in range(len(pl)) if find(i) == find(j)) > 1:
                continue
            b2 = bases(p, "boxes26"); best = None
            for i, q in enumerate(pl):
                if i == j or not q["name22"]:
                    continue
                bq = bases(q, "boxes22"); c = len(b2 & bq); ov = c / max(1, min(len(b2), len(bq))); s_ = sim(q["name22"].split(" + ")[0], p["name"])
                if (c or s_ >= 0.6) and (not best or ov + s_ > best[0]):
                    best = (ov + s_, i, s_, ov, c)
            if best:
                _, i, s_, ov, c = best
                t = tier_of(s_, "na", ov, c)
                parent[find(j)] = find(i); edges[find(i)].append(t); member[j] = t[0]
        comps = defaultdict(list)
        for i in range(len(pl)):
            comps[find(i)].append(i)
        # תגים מחושבים אחרי האיחודים
        all_edges = defaultdict(list)
        for k, v in edges.items():
            all_edges[find(k)].extend(v)
        place2comp = {}
        for root, ids in comps.items():
            ps = [pl[i] for i in ids]; b26 = [b for p in ps for b in p["boxes26"]]; b22 = [b for p in ps for b in p["boxes22"]]
            names26 = [p["name"] for p in ps if p["name"]]; names22 = []
            for p in ps:
                if p["name22"]:
                    names22 += p.get("names22") or [p["name22"]]
            es = all_edges.get(root, [])
            if es and b26 and b22:
                t = worst([e[0] for e in es]); why = next(e[1] for e in es if e[0] == t)
            else:
                t, why = NONE, "בלי מקביל ב-2022" if b26 else "בלי מקביל ב-2026"
            P = [pts.get(code, {}).get(n) for n in names26]; P = [z for z in P if z]
            row = {**head, "kind": "place", "names26": names26, "names22": names22, "addr": " ; ".join(sorted({a26.get(nn(n), "") for n in names26} - {""})), "nbhd": " ; ".join(sorted({nb.get(code, {}).get(n, "") for n in names26} - {""})),
                   "lat": round(sum(z[0] for z in P) / len(P), 5) if P else None, "lon": round(sum(z[1] for z in P) / len(P), 5) if P else None, "tier": t, "why": why, "y26": sumbox(b26), "y22": sumbox(b22), "boxes26": [b["box"] for b in b26], "boxes22": [b["box"] for b in b22], "n_places": len(ps)}
            sp = defaultdict(lambda: Counter())
            for i in ids:
                mt = member.get(i, NONE); q = pl[i]
                sp[mt]["k"] += sum(b["k"] for b in q["boxes26"]) + sum(b["k"] for b in q["boxes22"])
                sp[mt]["g26"] += sum(b["votes"].get("ג", 0) for b in q["boxes26"]); sp[mt]["g22"] += sum(b["votes"].get("ג", 0) for b in q["boxes22"])
                sp[mt]["s26"] += sum(b["votes"].get("שס", 0) for b in q["boxes26"]); sp[mt]["s22"] += sum(b["votes"].get("שס", 0) for b in q["boxes22"])
            row["split"] = {k: dict(v) for k, v in sp.items()}
            tk = sum(v["k"] for v in sp.values()); row["cert_share"] = round(100 * sp[CERT]["k"] / tk) if tk else None
            rows.append(row)
            for n in names26:
                place2comp[n] = row
    # --- מוניציפלי 2024
    def empty_m():
        return {"n": 0, "e": 0, "v": 0, "k": 0, "b": Counter(), "boxes": [], "places": set(), "by": defaultdict(Counter)}

    def add_m(row, e, v, k, votes, lists, boxes, place, tier):
        m = row.setdefault("m", empty_m())
        m["n"] += len(boxes); m["e"] += e; m["v"] += v; m["k"] += k; m["boxes"] += boxes
        if place:
            m["places"].add(place)
        for l, n in votes.items():
            bl = BLOCS.get((lists.get(l) or {}).get("bloc") or "")
            if bl:
                m["b"][bl] += n; m["by"][tier]["h"] += n
        m["by"][tier]["boxes"] += len(boxes); m["by"][tier]["k"] += k
        row["m_tier"] = worst([row.get("m_tier", CERT), tier])
    by_code = defaultdict(dict)
    for r in rows:
        if r["kind"] == "place":
            for n in r["names26"]:
                by_code[r["code"]][n] = r
    for code, j in join.items():
        st = muni[code]["stations"]; a26 = {nn(s["name"]): s["addr"] for s in st26.get(code, {}).get("places", [])}; lists = j["lists"]; head = {"code": code, "city": ALIAS.get(code) or j["name"], "district": idx.get(code, {}).get("district", ""), "nafa": idx.get(code, {}).get("nafa", ""), "haredi": code in HAREDI}
        if code not in by_code:
            continue
        recs = {("%g" % float(r[0])): r for r in muni[code]["council"]["boxes"] if str(r[0]).replace(".", "").isdigit() and float(r[0]) != 993}
        cols = muni[code]["council"]["cols"]
        for pl, v in j["places"].items():
            row = by_code[code].get(pl)
            for b in v["boxes"]:
                s = st.get(b); r = recs.get(b)
                c = cmp_addr(s[1], a26.get(nn(pl))) if s and a26.get(nn(pl)) else "na"
                nm = cmp_addr and sim(s[2], pl) >= 0.75 if s else False
                t = CERT if c == "same" else NEAR if (c == "street_nonum" or nm) else GUESS
                votes = {l: int(n or 0) for l, n in zip(cols, r[6:])} if r else {}
                add_m(row, int(r[2] or 0) if r else 0, int(r[3] or 0) if r else 0, int(r[5] or 0) if r else 0, votes, lists, [b], s[2] if s else "", t)
        num2place = defaultdict(list)
        for n, row in by_code[code].items():
            for b in row["boxes26"]:
                num2place[base(b)].append(row)
        extra = {"n": 0, "e": 0, "v": 0, "k": 0, "votes": Counter(), "boxes": [], "places": set()}
        for u in j["unmatched"]:
            cand = num2place.get(base(u["box"]))
            if cand:
                add_m(cand[0], u["e"], u["v"], u["k"], u["votes"], lists, [u["box"]], u["place"], GUESS)
            else:
                extra["n"] += 1; extra["e"] += u["e"]; extra["v"] += u["v"]; extra["k"] += u["k"]; extra["votes"].update(u["votes"]); extra["boxes"].append(u["box"]); extra["places"].add(u["place"])
        for kind, src, title, tt in (("muni_unlinked", extra, "קלפיות 2024 בלי מקביל ב-2026", NONE), ("muni_special", {**j.get("special", {}), "places": set()} if j.get("special", {}).get("v") else None, "קלפיות מיוחדות 2024", NONE)):
            if src and src.get("v"):
                row = {**head, "kind": kind, "names26": [title], "names22": [], "addr": "", "nbhd": "", "lat": None, "lon": None, "tier": NONE, "why": title, "y26": sumbox([]), "y22": sumbox([]), "boxes26": [], "boxes22": []}
                add_m(row, src["e"], src["v"], src["k"], src["votes"], lists, list(src["boxes"]), "", tt)
                row["m"]["places"] |= set(src.get("places", set()))
                rows.append(row)
    # מוניציפלי ביישובים שלמים (בלי חיבור לפי מקום)
    for r in rows:
        if r["kind"] != "whole":
            continue
        code = r["code"]; mm = muni.get(code)
        if not mm or not mm.get("council"):
            continue
        cols = mm["council"]["cols"]; lists = {l: {"bloc": b} for l, b in blocs.get(code, {}).items()}
        for row in mm["council"]["boxes"]:
            if not str(row[0]).replace(".", "").isdigit() or float(row[0]) == 993:
                continue
            add_m(r, int(row[2] or 0), int(row[3] or 0), int(row[5] or 0), {l: int(n or 0) for l, n in zip(cols, row[6:])}, lists, ["%g" % float(row[0])], "", CERT)
    # --- בדיקות שלמות
    chk = Counter(); diffs = []
    per = defaultdict(lambda: Counter())
    for r in rows:
        for y in ("y26", "y22"):
            per[r["code"]][y + "_e"] += r[y]["e"]; per[r["code"]][y + "_k"] += r[y]["k"]; per[r["code"]][y + "_g"] += r[y]["votes"].get("ג", 0); per[r["code"]][y + "_s"] += r[y]["votes"].get("שס", 0)
        if r.get("m"):
            per[r["code"]]["m_k"] += r["m"]["k"]; per[r["code"]]["m_v"] += r["m"]["v"]
    for code, x in idx.items():
        p = per[code]; ok = all(p[y + "_e"] == x[a]["e"] and p[y + "_k"] == x[a]["k"] and p[y + "_g"] == x[a]["votes"].get("ג", 0) and p[y + "_s"] == x[a]["votes"].get("שס", 0) for y, a in (("y26", "a26"), ("y22", "a22")))
        chk["loc_ok" if ok else "loc_bad"] += 1
        if not ok: diffs.append(("knesset", x["name"]))
        mm = muni.get(code)
        if mm and mm.get("council") and p["m_k"]:
            off = next((r for r in mm["council"]["boxes"] if str(r[0]).replace(".", "").isdigit() and float(r[0]) == 993), None)
            if off:
                if int(off[5] or 0) == p["m_k"] and int(off[3] or 0) == p["m_v"]:
                    chk["muni_ok"] += 1
                else:
                    chk["muni_bad"] += 1; diffs.append(("muni", x["name"], int(off[5] or 0), p["m_k"]))
    # --- פלט JSON (קטן: בלי רשימות מפורטות מיותרות)
    for r in rows:
        for y in ("y26", "y22"):
            r[y]["votes"] = {l: n for l, n in r[y]["votes"].items() if n}
        if r.get("m"):
            r["m"]["b"] = dict(r["m"]["b"]); r["m"]["places"] = sorted(r["m"]["places"]); r["m"]["by"] = {k: dict(v) for k, v in r["m"]["by"].items()}
    json.dump(rows, open(os.path.join(LIVE, "base_table.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # --- טבלה
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "טבלת בסיס"; ws.sheet_view.rightToLeft = True
    H = ["עיר", "מחוז", "עיר חרדית", "סוג שורה", "מקומות 2026", "מקומות 2022", "כתובת", "שכונה", "ודאות 2022-2026 (הנמוכה באשכול)", "% מהקולות בחיבור ודאי", "למה", "ודאות 2024-2026", "קלפיות 2026", "בז\"ב 2026", "מצביעים 2026", "כשרים 2026", "יהדות התורה 2026", 'ש"ס 2026', "הציבור החרדי 2026", "צבע שחור 2026", "הליכוד 2026", "עוצמה + ציונות 2026", "קלפיות 2022", "בז\"ב 2022", "מצביעים 2022", "כשרים 2022", "יהדות התורה 2022", 'ש"ס 2022', "הליכוד 2022", "ט 2022", "קלפיות 2024", "בז\"ב 2024", "מצביעים 2024", "כשרים 2024", "דגל 2024", "אגודה 2024", "יהדות התורה משותפת 2024", 'ש"ס 2024', 'משותפת כולל ש"ס 2024', "בני תורה 2024", "חרדי כללי 2024", "מקומות 2024", "lat", "lon"]
    ws.append(H)
    for c in ws[1]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="E6EFEE"); c.alignment = Alignment(wrap_text=True, vertical="top")
    KIND = {"place": "אשכול", "whole": "יישוב שלם", "external": "מעטפות חיצוניות", "muni_unlinked": "2024 בלי מקביל", "muni_special": "מיוחדות 2024"}
    rows.sort(key=lambda r: (not r["haredi"], r["city"], r["kind"] != "place", -r["y26"]["e"]))
    for r in rows:
        y6, y2, m = r["y26"], r["y22"], r.get("m"); v6, v2 = y6["votes"], y2["votes"]; b = m["b"] if m else {}
        ws.append([r["city"], r["district"], "כן" if r["haredi"] else "", KIND[r["kind"]], " ; ".join(r["names26"]), " ; ".join(r["names22"]), r["addr"], r["nbhd"], r["tier"], r.get("cert_share", 100 if r["tier"] == CERT else ""), r["why"], r.get("m_tier", ""), y6["n"], y6["e"], y6["v"], y6["k"], v6.get("ג", 0), v6.get("שס", 0), v6.get("זך", 0), v6.get("נר", 0), v6.get("מחל", 0), v6.get("ב", 0) + v6.get("ט", 0), y2["n"], y2["e"], y2["v"], y2["k"], v2.get("ג", 0), v2.get("שס", 0), v2.get("מחל", 0), v2.get("ט", 0),
                   m["n"] if m else "", m["e"] if m else "", m["v"] if m else "", m["k"] if m else "", b.get("dagel", 0) if m else "", b.get("aguda", 0) if m else "", b.get("utj", 0) if m else "", b.get("shas", 0) if m else "", b.get("joint", 0) if m else "", b.get("peleg", 0) if m else "", b.get("other", 0) if m else "", " ; ".join(m["places"]) if m else "", r["lat"], r["lon"]])
    for i, w in enumerate([13, 9, 6, 11, 30, 30, 22, 14, 10, 8, 22, 10] + [8] * 30):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
    ws.freeze_panes = "B2"; ws.auto_filter.ref = ws.dimensions
    sm = wb.create_sheet("סיכום ודאות"); sm.sheet_view.rightToLeft = True
    sm.append(["קבוצה", "רמת ודאות", "יהדות התורה 2026", "% ", 'ש"ס 2026', "% ", "יהדות התורה 2022", "% "])
    summ = {}; m_sum = {}
    for label, f in (("ערים חרדיות", lambda r: r["haredi"]), ("שאר הארץ", lambda r: not r["haredi"])):
        agg = defaultdict(Counter)
        for r in rows:
            if not f(r) or r["kind"] in ("muni_unlinked", "muni_special"):
                continue
            if r["kind"] == "place":
                for t, v in r["split"].items():
                    agg[t].update(v)
            else:
                t = r["tier"]; agg[t]["g26"] += r["y26"]["votes"].get("ג", 0); agg[t]["g22"] += r["y22"]["votes"].get("ג", 0); agg[t]["s26"] += r["y26"]["votes"].get("שס", 0); agg[t]["s22"] += r["y22"]["votes"].get("שס", 0)
        tg = sum(v["g26"] for v in agg.values()) or 1; ts = sum(v["s26"] for v in agg.values()) or 1; t2 = sum(v["g22"] for v in agg.values()) or 1; summ[label] = {}
        for t in (CERT, NEAR, GUESS, NONE):
            a = agg[t]; sm.append([label, t, a["g26"], round(100 * a["g26"] / tg, 1), a["s26"], round(100 * a["s26"] / ts, 1), a["g22"], round(100 * a["g22"] / t2, 1)])
            summ[label][t] = {"g26": a["g26"], "pct26": round(100 * a["g26"] / tg, 1), "g22": a["g22"], "pct22": round(100 * a["g22"] / t2, 1)}
        ma = defaultdict(Counter)
        for r in rows:
            if f(r) and r.get("m"):
                for t, v in r["m"]["by"].items():
                    ma[t].update(v)
        m_sum[label] = {t: dict(v) for t, v in ma.items()}
        for t in (CERT, NEAR, GUESS, NONE):
            sm.append([label + " · מוניציפלי 2024 (קולות חרדיים)", t, ma[t]["h"], "", "", "", "", ""])
    for c in sm[1]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="E6EFEE"); c.alignment = Alignment(wrap_text=True)
    for i, w in enumerate([24, 14, 8, 12, 12, 10, 12, 12]):
        sm.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
    df = wb.create_sheet("הגדרות"); df.sheet_view.rightToLeft = True; df.column_dimensions["A"].width = 18; df.column_dimensions["B"].width = 110
    for a, b in [("אשכול", "מקומות קלפי מחוברים זה לזה בין השנים. הקולות של כל שנה מסוכמים לשורה אחת, כך שפיצול קלפיות לא נראה כעלייה או ירידה."), (CERT, "לפחות שתי הוכחות מתוך שם, כתובת ומספרי קלפי, בלי סתירה בכתובת. ל-2022 אין כתובת ישירה, רק דרך השם ברשימת 2024."), (NEAR, "הוכחה אחת של שם או כתובת, או שם זהה בכתובת אחרת, או לפחות שני מספרי קלפי משותפים. כולל קבוצות שעברו בניין."), (GUESS, "מספר קלפי יחיד, או רמז חלש בלבד. אומת סטטיסטית בערים החרדיות, אבל לא שורה-שורה."), (NONE, "אין מקביל בשנה השנייה. הקולות נשמרים בשורה ונספרים בסה\"כ."), ("סה\"כ", "סכום כל השורות בעיר שווה לנתון הרשמי של העיר בכל שנה."), ("יישוב שלם", "יישובים קטנים בלי שמות מקומות: שורה אחת ליישוב, ודאי."), ("שכונה", "בתשע הערים החרדיות בלבד, לפי המפה והתיקונים שלך. אלעד בלי שכונות.")]:
        df.append([a, b])
    out = os.path.join(os.path.expanduser("~"), "Desktop", "kalpiot_base_table.xlsx")
    wb.save(out)
    sizes = Counter(r.get("n_places", 1) for r in rows if r["kind"] == "place")
    big = sorted([(r.get("n_places", 1), r["city"], len(r["boxes26"]), len(r["boxes22"])) for r in rows if r["kind"] == "place"], reverse=True)[:8]
    S = {"rows": len(rows), "kinds": dict(Counter(r["kind"] for r in rows)), "tiers": summ, "muni": m_sum, "check": dict(chk), "diffs": diffs[:15], "cluster_sizes": {str(k): sizes[k] for k in sorted(sizes)[:12]}, "largest": big, "national": {"g26": sum(r["y26"]["votes"].get("ג", 0) for r in rows), "g22": sum(r["y22"]["votes"].get("ג", 0) for r in rows), "s26": sum(r["y26"]["votes"].get("שס", 0) for r in rows), "k26": sum(r["y26"]["k"] for r in rows)}, "bytes": os.path.getsize(os.path.join(LIVE, "base_table.json")), "xlsx_bytes": os.path.getsize(out), "muni_rows": sum(1 for r in rows if r.get("m"))}
    json.dump(S, open(summary_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
