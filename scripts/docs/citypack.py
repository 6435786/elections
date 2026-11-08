#!/usr/bin/env python3
"""נתונים למסמכי הערים: סיכום לפי עיר, אזור חרדי וגוש, והערכת לאן הלכו קולות ש"ס.
קלט: live/base_table.json, live/loc/<code>.json, live/blocks_src.json (השיוך הידני של מקומות קלפי לגושים).
פלט: packs.json בתיקייה שמקבלים כארגומנט (לא בתוך הפרויקט).
שימוש: python -I scripts/docs/citypack.py <תיקיית פלט>
"""
import json, os, sys, collections

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "live"))
SURE = {"ודאי", "כמעט ודאי"}
AR = ("עם", "ודם", "ד")
LISTS = [("utj", "יהדות התורה", ["ג"], ["ג"]), ("shas", "ש\"ס", ["שס"], ["שס"]),
         ("orzd", "עוצמה יהודית + הציונות הדתית", ["ב", "ט"], ["ט"]), ("otz", "עוצמה יהודית", ["ב"], None), ("rzd", "הציונות הדתית", ["ט"], None),
         ("likud", "הליכוד", ["מחל"], ["מחל"]), ("zach", "הציבור החרדי", ["זך"], None), ("ner", "צבע שחור", ["נר"], None), ("noam", "נעם", ["ני"], None)]
HAR26, HAR22 = ["ג", "שס", "נר", "זך"], ["ג", "שס"]
RIGHT26, RIGHT22 = ["ב", "ט", "מחל", "ני", "ך"], ["ט", "מחל", "ב"]


def summary(rows):
    A = {y: {"e": 0, "v": 0, "k": 0, "votes": collections.Counter()} for y in ("y22", "y26")}
    m = collections.Counter()
    for r in rows:
        for y in A:
            for k in ("e", "v", "k"):
                A[y][k] += r[y][k]
            A[y]["votes"].update(r[y]["votes"])
        if r.get("m"):
            m.update(r["m"]["b"])
    y2, y6 = A["y22"], A["y26"]
    s = lambda y, ls: sum(y["votes"].get(l, 0) for l in ls)
    out = {"e22": y2["e"], "e26": y6["e"], "v22": y2["v"], "v26": y6["v"], "k22": y2["k"], "k26": y6["k"], "n": len(rows), "m": dict(m), "lists": {}}
    named22 = named26 = 0
    for key, name, l6, l2 in LISTS:
        a6 = s(y6, l6); a2 = s(y2, l2) if l2 else None
        out["lists"][key] = {"name": name, "v22": a2, "v26": a6}
        if key not in ("otz", "rzd"):
            named26 += a6; named22 += (a2 or 0)
    out["lists"]["other"] = {"name": "כל השאר", "v22": y2["k"] - named22, "v26": y6["k"] - named26}
    out["lists"]["har"] = {"name": "כל הרשימות החרדיות", "v22": s(y2, HAR22), "v26": s(y6, HAR26)}
    out["lists"]["right"] = {"name": "הימין שאינו חרדי", "v22": s(y2, RIGHT22), "v26": s(y6, RIGHT26)}
    return out


def flow(rows):
    """צפוי מול בפועל: בכל מקום, הצבעת 2022 (כחלק מבעלי זכות הבחירה) כפול בעלי זכות 2026."""
    G = {"UTJ": (["ג"], ["ג"]), "Shas": (["שס"], ["שס"]), "Right": (RIGHT26, RIGHT22), "NewH": (["נר", "זך"], [])}
    S = collections.Counter(); bands = collections.defaultdict(collections.Counter); nb = collections.Counter()
    for r in rows:
        y2, y6 = r["y22"], r["y26"]; E2, E6 = y2["e"], y6["e"]
        if not E2 or not E6:
            continue
        d = {k: sum(y6["votes"].get(l, 0) for l in l6) - sum(y2["votes"].get(l, 0) for l in l2) / E2 * E6 for k, (l6, l2) in G.items()}
        o2 = y2["k"] - sum(y2["votes"].get(l, 0) for _, l2 in G.values() for l in l2)
        o6 = y6["k"] - sum(y6["votes"].get(l, 0) for l6, _ in G.values() for l in l6)
        d["Other"] = o6 - o2 / E2 * E6
        d["Abst"] = (E6 - y6["k"]) - (E2 - y2["k"]) / E2 * E6
        g = E6 / E2 - 1; band = "<10" if g < .1 else ("10-20" if g < .2 else ">=20")
        S.update(d); bands[band].update(d); nb[band] += 1
    return {"all": dict(S), "bands": {b: dict(v) for b, v in bands.items()}, "nbands": dict(nb)}


def main(outdir):
    D = json.load(open(os.path.join(LIVE, "base_table.json"), encoding="utf-8"))
    SRC = json.load(open(os.path.join(LIVE, "blocks_src.json"), encoding="utf-8"))
    sure = lambda L: [r for r in L if r["tier"] in SURE]
    is_har = lambda r: r["y22"]["k"] and sum(r["y22"]["votes"].get(l, 0) for l in HAR22) / r["y22"]["k"] > .5
    is_arab = lambda r: r["y26"]["k"] and sum(r["y26"]["votes"].get(l, 0) for l in AR) / r["y26"]["k"] >= .5
    packs = {}
    for code, src in SRC.items():
        loc = json.load(open(os.path.join(LIVE, "loc", code + ".json"), encoding="utf-8"))
        E = {p["name"]: sum(b["e"] for b in p["boxes26"]) for p in loc["places"] if p["name"]}
        pb = {n: v["block"] for n, v in src["places"].items()}; pnb = {n: v["nbhd"] for n, v in src["places"].items()}
        R = [r for r in D if r["code"] == code and r["kind"] == "place" and not is_arab(r)]
        blocks = collections.defaultdict(list); nbs = collections.defaultdict(set); rest = []
        for r in R:
            best = max(((E.get(n, 0), pb[n]) for n in r["names26"] if n in pb), default=None)
            if not best:
                rest.append(r); continue
            b = best[1]; blocks[b].append(r)
            for n in r["names26"]:
                if pb.get(n) == b and pnb.get(n):
                    nbs[b].add(pnb[n])
        area = [r for L in blocks.values() for r in L]; har = [r for r in R if is_har(r)]
        packs[code] = {"city": R[0]["city"] if R else code, "order": src["order"], "all": summary(R), "area": summary(area), "har": summary(har), "rest": summary(rest),
                       "flow_all": flow(R), "flow_sure": flow(sure(R)), "flow_har": flow(har), "flow_har_sure": flow(sure(har)),
                       "blocks": {b: {"sum": summary(L), "nbs": sorted(nbs[b])} for b, L in blocks.items()}}
        print(code, packs[code]["city"], len(R), "groups,", {b: len(L) for b, L in blocks.items()}, "outside blocks:", len(rest))
    os.makedirs(outdir, exist_ok=True)
    json.dump(packs, open(os.path.join(outdir, "packs.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1]))
