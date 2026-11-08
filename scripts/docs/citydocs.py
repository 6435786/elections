# -*- coding: utf-8 -*-
"""כלים למסמכי הערים (Word מימין לשמאל): טבלאות, פרק ש"ס, פרק דגל ואגודה ונספח גושים. הנתונים מ-packs.json (citypack.py)."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxlib
LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "live"))
P = {}
DATE = "8 בנובמבר 2026"
def load(outdir):
    P.update(json.load(open(os.path.join(outdir, "packs.json"), encoding="utf-8")))

f0 = lambda n: f"{round(n):,}"
def sg(n): return (f"{abs(round(n)):,}" + ("+" if n >= 0 else "−"))           # 1,234+ (מוצג ‎+1,234 בעברית)
def sp(x, d=1): t = f"{abs(x):.{d}f}"; return t if float(t) == 0 else t + ("+" if x >= 0 else "−")             # שינוי בנקודות / אחוזים
def spp(x, d=1): return f"{abs(x):.{d}f}%" + ("+" if x >= 0 else "−")         # אחוז עם סימן בסוף (מוצג ‎+12.2%)
def pct0(x): return f"{abs(x):.0f}%" + ("−" if x < 0 else "")                    # אחוז שלם, מינוס בסוף (מוצג ‎−40%)
def pc(a, b, d=1): return f"{100 * a / b:.{d}f}%" if b else "—"
def rel(a, b): return 100 * (a / b - 1) if b else 0

ORDER = ["utj", "shas", "orzd", "otz", "rzd", "likud", "zach", "ner", "noam", "other", "har", "right"]
def main_table(S):
    H = ["רשימה", "קולות 2022", "קולות 2026", "שינוי בקולות", "% מבעלי זכות הבחירה", "% מהקולות הכשרים"]
    rows = [H]
    for k in ORDER:
        L = S["lists"][k]; a2, a6 = L["v22"], L["v26"]
        name = {"otz": "— מתוכן עוצמה יהודית", "rzd": "— מתוכן הציונות הדתית", "har": "**כל הרשימות החרדיות", "right": "**הימין שאינו חרדי"}.get(k, L["name"])
        if k in ("otz", "rzd", "noam"):
            rows.append([name, "ברשימה המשותפת" if k == "noam" else "", f0(a6), "", pc(a6, S["e26"]), pc(a6, S["k26"])]); continue
        if a2 is None:
            rows.append([name, "לא רצה", f0(a6), "חדשה", pc(a6, S["e26"]), pc(a6, S["k26"])]); continue
        ch = f"{sg(a6 - a2)} ({spp(rel(a6, a2))})" if a2 >= 100 else sg(a6 - a2)
        de = 100 * (a6 / S["e26"] - a2 / S["e22"]); dk = 100 * (a6 / S["k26"] - a2 / S["k22"])
        rows.append([name, f0(a2), f0(a6), ch, f"{pc(a2, S['e22'])} ← {pc(a6, S['e26'])} ({sp(de)})", f"{pc(a2, S['k22'])} ← {pc(a6, S['k26'])} ({sp(dk)})"])
    return ("table", rows)

def headline(S):
    return (f"בעלי זכות בחירה: {f0(S['e22'])} ← {f0(S['e26'])} ({spp(rel(S['e26'], S['e22']))}) · קולות כשרים: {f0(S['k22'])} ← {f0(S['k26'])} · "
            f"אחוז הצבעה: {pc(S['v22'], S['e22'])} ← {pc(S['v26'], S['e26'])}")

def k(S, key, y="26"): return S["lists"][key]["v" + y]
def kp(S, key, y="26"): return 100 * (k(S, key, y) or 0) / S["k" + y]

def blocks_table(blocks, order):
    rows = [["גוש", "בעלי זכות בחירה", "יהדות התורה", "ש\"ס", "הימין שאינו חרדי", "חרדיות חדשות 2026"]]
    for b in order:
        S = blocks[b]["sum"]
        f = lambda key: f"{kp(S, key, '22'):.1f}% ← {kp(S, key):.1f}% ({sp(kp(S, key) - kp(S, key, '22'))})"
        rows.append([b, f"{f0(S['e22'])} ← {f0(S['e26'])} ({spp(rel(S['e26'], S['e22']))})", f("utj"), f("shas"), f("right"),
                     f"{100 * (k(S, 'ner') + k(S, 'zach')) / S['k26']:.1f}%"])
    return ("tablew", (rows, [2300, 1700, 1500, 1500, 1500, 1138]))

def flow_section(F, scope_note, extra_note="", title="לאן הלכו הקולות של ש\"ס: הערכה"):
    a = F["all"]; sh = -a["Shas"]
    pt = lambda x: pct0(100 * a[x] / sh)
    out = [("h2", title),
           ("pb", ("איך מעריכים.", " אין נתון על מי הצביע למי. לכן בכל מקום קלפי חושב מה היה קורה ב-2026 אילו כל בעלי זכות הבחירה, ותיקים וחדשים, היו מתנהגים כמו באותו מקום ב-2022, כולל מי שלא הצביע. ההפרש בין הצפוי לבפועל מראה מי הרוויח ומי הפסיד מעבר לגידול הטבעי. " + scope_note)),
           ("p", f"לפי החישוב, חסרים לש\"ס כ-{f0(sh)} קולות לעומת הצפוי. כך מתחלק הפער:"),
           ("table", [["לאן", "עודף מעבר לצפוי", f"חלק מהחוסר של ש\"ס ({f0(sh)})"],
                      ["יהדות התורה", sg(a["UTJ"]), pt("UTJ")], ["הימין שאינו חרדי", sg(a["Right"]), pt("Right")],
                      ["צבע שחור והציבור החרדי", sg(a["NewH"]), pt("NewH")], ["לא הצביעו או פסולים", sg(a["Abst"]), pt("Abst")],
                      ["כל השאר", sg(a["Other"]), pt("Other")]])]
    if a["Abst"] < 0:
        net = a["NewH"] + a["Abst"]
        out.append(("p", f"מספר שלא הצביעו ירד, כלומר אחוז ההצבעה עלה, ולכן הסכום עובר את 100%. סביר שחלק גדול מהמצביעים הנוספים הצביעו לצבע שחור, שמזוהה עם ציבור שלא נהג להצביע לכנסת. אם מקזזים את שני אלה זה בזה, נשארים {sg(net)} קולות ({pct0(100 * net / sh)}) לרשימות החרדיות החדשות ולהימנעות יחד."))
    out.append(("pb", ("הנחת עבודה.", " בבחירות האלו כמעט לא עברו מצביעים מיהדות התורה לש\"ס. החלוקה ביניהן היא בעיקר בין אשכנזים לספרדים, והסיבות לכעס הפעם (הגיוס, הישגים שלא הספיקו והציבור המודרני יותר) הופנו גם כלפי ש\"ס, ובמידה רבה יותר. לכן החוסר של ש\"ס הוא מצביעים שעזבו אותה או מצביעים חדשים שלא בחרו בה, ולא קיזוז נסתר.")))
    B = F["bands"]; nb = F["nbands"]
    lab = {"<10": "גידול מתחת ל-10%", "10-20": "גידול 10% עד 20%", ">=20": "גידול מעל 20%"}
    rows = [["מקומות לפי קצב הגידול", "חסר לש\"ס", "יהדות התורה", "הימין שאינו חרדי", "חרדיות חדשות", "לא הצביעו"]]
    for b in ("<10", "10-20", ">=20"):
        if b not in B: continue
        d = B[b]; s = -d["Shas"]
        if s <= 0: rows.append([f"{lab[b]} ({nb[b]} מקומות)", "אין חוסר", "", "", "", ""]); continue
        q = lambda x: pct0(100 * d[x] / s)
        rows.append([f"{lab[b]} ({nb[b]} מקומות)", f0(s), q("UTJ"), q("Right"), q("NewH"), q("Abst")])
    out += [("pb", ("לפי קצב הגידול של המקום.", " במקומות שכמעט לא גדלו יש מעט מצביעים חדשים, ולכן שם התמונה נקייה יותר.")), ("table", rows)]
    if extra_note: out.append(("p", extra_note))
    out.append(("note", "זו הערכה של מעברים נטו על סמך מקומות הקלפי, ולא ספירה של מצביעים. אם 100 עברו לכיוון אחד ו-50 בכיוון ההפוך, רואים רק 50."))
    return out

SOURCES = [("h2", "מקורות והערות"),
           ("li", "התוצאות לכנסת: קבצי התוצאות של ועדת הבחירות המרכזית לפי קלפי, לכנסת ה-25 (2022) ולכנסת ה-26 (2026). לא כולל מעטפות כפולות, שאינן משויכות לעיר."),
           ("li", "השוואה לפי מקומות קלפי: מקומות שהתפצלו או עברו בין הבחירות חוברו לקבוצה אחת. כל קבוצה שויכה לגוש של המקום הגדול בה."),
           ("li", "הגושים נקבעו ידנית לפי מיקום מקומות הקלפי."),
           ("li", "הימין שאינו חרדי: הליכוד, עוצמה יהודית, הציונות הדתית, נעם ועמך ישראל; ב-2022 הרשימה המשותפת של הציונות הדתית ועוצמה, הליכוד והבית היהודי. הרשימות החרדיות: יהדות התורה, ש\"ס, צבע שחור והציבור החרדי.")]

def block_details(blocks, order, title="נספח: כל גוש בפירוט"):
    out = [("h2", title)]
    for b in order:
        S = blocks[b]["sum"]; nbs = blocks[b].get("nbs") or []
        out.append(("h3", b))
        if nbs: out.append(("note", "שכונות: " + ", ".join(nbs)))
        out.append(("note", headline(S)))
        out.append(main_table(S))
    return out

def lists_sentences(S):
    """משפטים כלליים על המפלגות, מהנתונים."""
    u2, u6 = k(S, "utj", "22"), k(S, "utj"); s2, s6 = k(S, "shas", "22"), k(S, "shas"); g = rel(S["e26"], S["e22"])
    r2, r6 = k(S, "right", "22"), k(S, "right"); n6 = k(S, "ner"); z6 = k(S, "zach")
    return {
        "utj": f"יהדות התורה קיבלה {f0(u6)} קולות, לעומת {f0(u2)} ב-2022: {'עלייה' if u6 >= u2 else 'ירידה'} של {abs(rel(u6, u2)):.1f}%. בעלי זכות הבחירה גדלו באותה תקופה ב-{g:.1f}%. החלק שלה מהקולות הכשרים {'עלה' if kp(S,'utj')>=kp(S,'utj','22') else 'ירד'} מ-{kp(S,'utj','22'):.1f}% ל-{kp(S,'utj'):.1f}%.",
        "shas": f"ש\"ס {'ירדה' if s6 < s2 else 'עלתה'} מ-{f0(s2)} ל-{f0(s6)} קולות ({spp(rel(s6, s2))}). אילו שמרה על חלקה מבעלי זכות הבחירה, הייתה מגיעה לכ-{f0(s2 * S['e26'] / S['e22'])}. מהקולות הכשרים החלק שלה ירד מ-{kp(S,'shas','22'):.1f}% ל-{kp(S,'shas'):.1f}%.",
        "right": f"הימין שאינו חרדי קיבל {f0(r6)} קולות, לעומת {f0(r2)} ב-2022 ({spp(rel(r6, r2))}), {kp(S,'right'):.1f}% מהקולות הכשרים. עוצמה יהודית לבדה קיבלה {f0(k(S,'otz'))}, והציונות הדתית {f0(k(S,'rzd'))}; ב-2022 שתיהן יחד קיבלו {f0(k(S,'orzd','22'))}.",
        "new": f"שתי הרשימות החרדיות החדשות קיבלו יחד {f0(n6 + z6)} קולות, {100*(n6+z6)/S['k26']:.1f}% מהקולות הכשרים: צבע שחור {f0(n6)} והציבור החרדי {f0(z6)}.",
    }

THREE_WAYS = "כל שינוי מוצג בשלוש דרכים: השינוי במספר הקולות, השינוי באחוז מבעלי זכות הבחירה, והשינוי באחוז מהקולות הכשרים (כולל רשימות שלא עברו את אחוז החסימה). בסוגריים: השינוי בנקודות אחוז."
BLOCK_NOTE = ("note", "האחוזים מהקולות הכשרים. בסוגריים: השינוי בנקודות אחוז מ-2022.")

# ---------- דגל ואגודה ----------
_D = None
def _base():
    global _D
    if _D is None: _D = json.load(open(os.path.join(LIVE, "base_table.json"), encoding="utf-8"))
    return _D

def dagel_ladder(code):
    Q = []
    for r in _base():
        if r["code"] != code or r["kind"] != "place": continue
        m = r.get("m")
        if not m or not r["y22"]["k"] or not r["y26"]["k"]: continue
        b = m["b"]
        if b.get("utj", 0) or b.get("joint", 0): continue
        d, a = b.get("dagel", 0), b.get("aguda", 0)
        if d + a < 100 or (d + a) / max(1, m["k"]) < .5: continue
        Q.append((d / (d + a), r))
    out = []
    for t in (.6, .7, .8):
        res = []
        for side in ("d", "a"):
            L = [r for s, r in Q if (s >= t if side == "d" else s <= 1 - t)]
            if not L: res.append(None); continue
            k2 = sum(r["y22"]["k"] for r in L); k6 = sum(r["y26"]["k"] for r in L)
            u2 = sum(r["y22"]["votes"].get("ג", 0) for r in L); u6 = sum(r["y26"]["votes"].get("ג", 0) for r in L)
            res.append((len(L), 100 * u2 / k2, 100 * u6 / k6))
        out.append((t, res))
    return out, len(Q)

DG_METHOD = ("בבחירות לכנסת דגל התורה ואגודת ישראל רצות יחד, ולכן אי אפשר לספור את המצביעים של כל אחת. בבחירות לעירייה ב-2024 הן רצו בנפרד, "
             "ולפי זה אפשר לדעת באיזה מקום קלפי כל אחת חזקה. מעוז נקבע לפי החלק של דגל או של אגודה מתוך שתיהן יחד, ורק במקומות שבהם דגל ואגודה יחד קיבלו לפחות חצי מהקולות ב-2024. "
             "המדד: השינוי בחלק של יהדות התורה מהקולות הכשרים, מ-2022 ל-2026.")

def dagel_section(code, text):
    lad, n = dagel_ladder(code)
    out = [("h2", "דגל ואגודה"), ("p", DG_METHOD)]
    if not any(x for _, res in lad for x in res):
        return out + [("p", text)]
    rows = [["מעוז מ-", "מעוזי דגל", "מעוזי אגודה"]]
    for t, res in lad:
        f = lambda x: "אין מקומות" if not x else f"{x[0]} מקומות: {x[1]:.1f}% ← {x[2]:.1f}% ({sp(x[2] - x[1])})"
        rows.append([f"{int(t * 100)}%", f(res[0]), f(res[1])])
    out += [("table", rows), ("p", text),
            ("note", "מספר המקומות בכל שורה קטן, ולכן ההבדלים הם אינדיקציה ולא הוכחה. השורות התחתונות כוללות רק את המקומות ה\"טהורים\" יותר.")]
    return out
