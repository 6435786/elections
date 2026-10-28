#!/usr/bin/env python3
"""תחזית ברמת קלפי: אילו קלפיות עוד לא נספרו, ומה הן הצביעו ב-2022.

מקורות:
  - קלפיות 2026 שנספרו:  https://media26.bechirot.gov.il/files/expb.csv  (ועדת הבחירות, מתעדכן)
  - רשימת כל קלפיות 2026 עם בז"ב: voter_turnout_20.xlsx של הוועדה (gov.il), מטמון ב-live/stations26.json
  - קלפיות 2022:         https://media25.bechirot.gov.il/files/expb.csv  (מטמון ב-live/expb25.csv)

פלט: live/remaining.json – לכל יישוב עם קלפיות שטרם נספרו: כמה קלפיות, כמה בז"ב, אומדן מצביעים,
ו"פרופיל 2022" של הקלפיות החסרות (קולות לפי אותיות 2022: אותה קלפי ב-2022 אם קיימת ודומה, אחרת ממוצע היישוב).
הדף status.html משתמש בפרופיל הזה במקום בממוצע היישובי כשהוא קיים ועדכני.
"""
import csv, io, json, os, re, sys, zipfile, urllib.request
from datetime import datetime, timezone, timedelta

IL = timezone(timedelta(hours=2))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
EXPB26 = "https://media26.bechirot.gov.il/files/expb.csv"
EXPB25 = "https://media25.bechirot.gov.il/files/expb.csv"
STATIONS_XLSX = "https://www.gov.il/BlobFolder/generalpage/turnout_at_polling_stations/he/voter_turnout_20.xlsx"
KEEP = ["מחל", "פה", "כן", "ט", "שס", "ג", "ל", "אמת", "מרצ", "ום", "ד", "עם", "ב"]  # אותיות 2022 שמהן נגזרות רשימות 2026
TOL = 0.35  # הפרש בז"ב מותר כדי להחשיב קלפי 2022 כ"אותה קלפי"


def download(url, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        lm = r.headers.get("Last-Modified")
    if dest:
        with open(dest, "wb") as f:
            f.write(body)
        if lm:
            try:
                from email.utils import parsedate_to_datetime
                ts = parsedate_to_datetime(lm).timestamp()
                os.utime(dest, (ts, ts))
            except Exception:
                pass
    return body


def decode(raw):
    for enc in ("utf-8-sig", "cp1255"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def read_expb(path):
    rows = list(csv.reader(io.StringIO(decode(open(path, "rb").read()))))
    h = [c.strip() for c in rows[0]]
    ix = {c: i for i, c in enumerate(h)}
    ic, ik, ie, iv, ivalid = ix["סמל ישוב"], ix["קלפי"], ix["בזב"], ix["מצביעים"], ix["כשרים"]
    letters = [c for c in h[ivalid + 1:] if c]
    out = {}
    for r in rows[1:]:
        if len(r) <= ivalid or not r[ic].strip():
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
        out.setdefault(r[ic].strip(), {})[box] = {"e": n(ie), "v": n(iv), "k": n(ivalid), "votes": votes}
    return out


def read_stations(xlsx_path):
    z = zipfile.ZipFile(xlsx_path)
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    ss = []
    try:
        sx = z.read("xl/sharedStrings.xml").decode("utf-8")
        ss = [re.sub(r"<[^>]+>", "", x) for x in re.findall(r"<si>.*?</si>", sx, re.S)]
    except KeyError:
        pass
    st = {}
    for row in re.findall(r"<row [^>]*>(.*?)</row>", xml, re.S)[1:]:
        cells = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<v>(.*?)</v>)?', row):
            col, attrs, v = m.group(1), m.group(2), m.group(3)
            if v is None:
                continue
            cells[col] = ss[int(v)] if 't="s"' in attrs else v
        code, box, e = cells.get("A", "").strip(), cells.get("C", "").strip(), cells.get("E", "0")
        if not code or not box:
            continue
        try:
            st.setdefault(code, {})[float(box)] = int(float(e))
        except ValueError:
            continue
    return st


def main():
    live = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live")
    live = os.path.normpath(live)
    p26, p25, pst, out = (os.path.join(live, x) for x in ("expb.csv", "expb25.csv", "stations26.json", "remaining.json"))
    # 1) קלפיות 2026 שנספרו (תמיד מורידים מחדש)
    try:
        download(EXPB26, p26)
    except Exception as e:
        print("expb 2026 download failed:", repr(e))
    if not os.path.exists(p26) or os.path.getsize(p26) < 1000:
        print("no 2026 box file – nothing written")
        return 0
    counted = read_expb(p26)
    asof = datetime.fromtimestamp(os.path.getmtime(p26), IL)
    # 2) רשימת כל הקלפיות (מטמון)
    if not os.path.exists(pst):
        xl = os.path.join(live, "stations26.xlsx")
        download(STATIONS_XLSX, xl)
        st = read_stations(xl)
        json.dump({c: {str(b): e for b, e in bx.items()} for c, bx in st.items()}, open(pst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        os.remove(xl)
    stations = {c: {float(b): e for b, e in bx.items()} for c, bx in json.load(open(pst, encoding="utf-8")).items()}
    # 3) קלפיות 2022 (מטמון)
    if not os.path.exists(p25) or os.path.getsize(p25) < 1000:
        download(EXPB25, p25)
    prev = read_expb(p25)
    # סיכומי יישוב 2022 (לממוצע כשאין קלפי תואמת)
    town22 = {}
    for code, bx in prev.items():
        t = {"e": 0, "v": 0, "k": 0, "votes": {}}
        for b in bx.values():
            t["e"] += b["e"]; t["v"] += b["v"]; t["k"] += b["k"]
            for l, n in b["votes"].items():
                t["votes"][l] = t["votes"].get(l, 0) + n
        town22[code] = t
    # 4) לכל יישוב: הקלפיות שחסרות
    towns, tot_boxes, tot_counted, tot_matched, tot_unmatched, tot_voters = {}, 0, 0, 0, 0, 0.0
    for code, bx in stations.items():
        if not code.isdigit() or int(code) >= 99999:  # שורת סיכום בקובץ של gov.il
            continue
        have = counted.get(code, {})
        tot_boxes += len(bx); tot_counted += len([b for b in bx if b in have])
        missing = [b for b in bx if b not in have]
        if not missing:
            continue
        ce = sum(have[b]["e"] for b in have); cv = sum(have[b]["v"] for b in have); ck = sum(have[b]["k"] for b in have)
        t22 = town22.get(code)
        if ce and cv:
            turnout = cv / ce
        elif t22 and t22["e"]:
            turnout = min(0.97, t22["v"] / t22["e"] * 1.10)  # אין עדיין קלפיות ביישוב: 2022 מוגדל
        else:
            turnout = 0.72
        valid_ratio = (ck / cv) if cv else 0.99
        prof, matched, unmatched, elig_un = {}, 0, 0, 0
        for b in missing:
            e26 = bx[b]; elig_un += e26
            pb = prev.get(code, {}).get(b)
            if pb and pb["e"] and abs(pb["e"] - e26) / max(pb["e"], e26) <= TOL and pb["k"]:
                matched += 1
                for l, n in pb["votes"].items():
                    if l in KEEP:
                        prof[l] = prof.get(l, 0) + n
            else:
                unmatched += 1
                if t22 and t22["e"]:
                    f = e26 / t22["e"]
                    for l, n in t22["votes"].items():
                        if l in KEEP:
                            prof[l] = prof.get(l, 0) + n * f
        voters_est = elig_un * turnout
        towns[code] = {"bt": len(bx), "bc": len(bx) - len(missing), "elig_un": elig_un, "voters_est": round(voters_est),
                       "valid_est": round(voters_est * valid_ratio), "matched": matched, "unmatched": unmatched,
                       "profile": {l: round(n) for l, n in prof.items() if n >= 0.5}}
        tot_matched += matched; tot_unmatched += unmatched; tot_voters += voters_est
    res = {"updated": datetime.now(IL).isoformat(timespec="seconds"), "asof": asof.isoformat(timespec="seconds"), "asof_label": asof.strftime("%H:%M"),
           "boxes_total": tot_boxes, "boxes_counted": tot_counted, "boxes_matched": tot_matched, "boxes_unmatched": tot_unmatched,
           "voters_est": round(tot_voters), "towns": towns}
    old = None
    if os.path.exists(out):
        try:
            old = json.load(open(out, encoding="utf-8"))
        except Exception:
            old = None
    if old and old.get("boxes_counted") == tot_counted and old.get("boxes_total") == tot_boxes and old.get("asof") == res["asof"] and old.get("voters_est") == res["voters_est"]:
        print("remaining unchanged: %d/%d boxes counted" % (tot_counted, tot_boxes))
        return 0
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("remaining written: %d/%d boxes counted, %d missing (%d matched to 2022, %d by town average), ~%d voters, as of %s"
          % (tot_counted, tot_boxes, tot_matched + tot_unmatched, tot_matched, tot_unmatched, tot_voters, res["asof_label"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
