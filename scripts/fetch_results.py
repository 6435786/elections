#!/usr/bin/env python3
"""מוריד את קובץ התוצאות לפי יישובים של ועדת הבחירות המרכזית (expc.csv),
מסכם לרמה ארצית וכותב live/results.json. ספרייה סטנדרטית בלבד.

שימוש:  python3 scripts/fetch_results.py [--url URL] [--file PATH] [--out live/results.json]
"""
import argparse, csv, io, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

DEFAULT_URL = "https://media26.bechirot.gov.il/files/expc.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
META = ["סמל ועדה", "שם ישוב", "סמל ישוב", "בזב", "מצביעים", "פסולים", "כשרים"]
PLACES = {  # יישובים שמוצגים בנפרד בלוח החי ובדוח ביתר (השוואה לערים חרדיות)
    "3780": "ביתר עילית", "6100": "בני ברק", "1309": "אלעד", "3797": "מודיעין עילית", "2610": "בית שמש", "3000": "ירושלים",
}
IL = timezone(timedelta(hours=2))  # שעון חורף בישראל (27.10.2026)


def download(url, verbose=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        if verbose:
            print("GET %s -> %s %s, %d bytes, final url %s" % (url, r.status, r.headers.get("Content-Type"), len(body), r.geturl()))
            print("headers:", dict(r.headers))
        return body


def decode(raw):
    for enc in ("utf-8-sig", "cp1255"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def to_int(s):
    s = (s or "").strip().replace(",", "").replace("‬", "").replace("‫", "")
    try:
        return int(float(s)) if s else 0
    except ValueError:
        return 0


def summarize(text, source):
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise SystemExit("empty file")
    header = [h.strip().lstrip("﻿") for h in rows[0]]
    missing = [m for m in META if m not in header]
    if missing:
        raise SystemExit("missing column(s): %s ; header=%s" % (missing, header))
    idx = {h: i for i, h in enumerate(header)}
    letters = [h for h in header[len(META):] if h]
    totals = {k: 0 for k in ("בזב", "מצביעים", "פסולים", "כשרים")}
    votes = {l: 0 for l in letters}
    localities = 0
    places = {}
    for r in rows[1:]:
        if len(r) < len(META):
            continue
        localities += 1
        for k in totals:
            totals[k] += to_int(r[idx[k]])
        for l in letters:
            i = idx[l]
            if i < len(r):
                votes[l] += to_int(r[i])
        code = r[idx["סמל ישוב"]].strip()
        if code in PLACES:
            places[code] = {"name": PLACES[code], "eligible": to_int(r[idx["בזב"]]), "voters": to_int(r[idx["מצביעים"]]),
                            "invalid": to_int(r[idx["פסולים"]]), "valid": to_int(r[idx["כשרים"]]),
                            "votes": {l: to_int(r[idx[l]]) for l in letters if idx[l] < len(r) and to_int(r[idx[l]]) > 0}}
    now = datetime.now(IL)
    return {
        "updated": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("%H:%M"),
        "source": source,
        "status": "no_data" if localities == 0 else "partial",
        "localities": localities,
        "eligible": totals["בזב"],
        "voters": totals["מצביעים"],
        "invalid": totals["פסולים"],
        "valid": totals["כשרים"],
        "letters": letters,
        "votes": votes,
        "places": places,
    }


DAY_URL ="https://navonyaniv.github.io/election-il-2026/results.json"
GOVMAP_MANIFEST = "https://elections.govmap.gov.il/data/votes/elections.json"


def govmap_summary():
    """מקור שני: GovMap (אתר המיפוי הממשלתי) – municipal_data.json של הכנסת ה-26, אותו מבנה תוצאה כמו summarize()."""
    man = json.loads(download(GOVMAP_MANIFEST).decode("utf-8"))
    el = man.get("elections", {})
    e = el.get("26") or next((v for v in el.values() if v.get("isCurrent")), None)
    if not e:
        raise SystemExit("govmap: no current election in manifest")
    url = "https://elections.govmap.gov.il/data/votes/%s/municipal_data.json" % e.get("path", "latest")
    raw = download(url, verbose=True)
    if not raw.lstrip().startswith(b"{"):
        raise SystemExit("govmap: data file not published yet (%d bytes, not JSON)" % len(raw))
    g = json.loads(raw.decode("utf-8"))
    parties = g.get("parties") or []
    feats = g.get("features") or {}
    totals = {k: 0 for k in ("בזב", "מצביעים", "פסולים", "כשרים")}
    votes = {p: 0 for p in parties}
    localities = 0
    places = {}
    for code, f in feats.items():
        if not isinstance(f, dict):
            continue
        localities += 1
        for k in totals:
            totals[k] += to_int(str(f.get(k, 0)))
        for p in parties:
            votes[p] += to_int(str(f.get(p, 0)))
        if str(code) in PLACES:
            places[str(code)] = {"name": PLACES[str(code)], "eligible": to_int(str(f.get("בזב", 0))), "voters": to_int(str(f.get("מצביעים", 0))),
                                 "invalid": to_int(str(f.get("פסולים", 0))), "valid": to_int(str(f.get("כשרים", 0))),
                                 "votes": {p: to_int(str(f.get(p, 0))) for p in parties if to_int(str(f.get(p, 0))) > 0}}
    if not localities or not totals["כשרים"]:
        raise SystemExit("govmap: no counted localities yet")
    t = g.get("totals") or {}
    kal, kc = to_int(str(t.get("kalpi", 0))), to_int(str(t.get("kalpi_counted", 0)))
    now = datetime.now(IL)
    return {
        "updated": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("%H:%M"),
        "source": url,
        "status": "final" if (kal and kc >= kal) else "partial",
        "localities": localities,
        "eligible": totals["בזב"],
        "voters": totals["מצביעים"],
        "invalid": totals["פסולים"],
        "valid": totals["כשרים"],
        "letters": parties,
        "votes": votes,
        "kalpi": kal or None,
        "kalpi_counted": kc or None,
        "counted_pct": (round(kc / kal * 100, 1) if kal else None),
        "votes_counted": t.get("votes_counted"),
        "generated": g.get("generated"),
        "places": places,
    }


def bulletin_slot(label):
    """'12:49' -> '12:00' (הוועדה מפרסמת בשעות זוגיות); '13:14' -> '12:00'."""
    try:
        h, m = label.split(":")[:2]
        h = int(h)
        h -= h % 2
        return "%02d:00" % h
    except Exception:
        return None


def sector_estimates(day, sectors_path="live/sectors.json"):
    """אומדן אחוז הצבעה ביישובים ערביים/חרדיים ברובם: ממוצע משוקלל (בעלי זכות בחירה 2022) של נתוני היישובים בהזנה."""
    try:
        sectors = json.load(open(sectors_path, encoding="utf-8"))
    except Exception:
        return None
    towns = day.get("live_towns") or {}
    out = {}
    for name in ("arab", "haredi"):
        codes = sectors.get(name, {}).get("codes", {})
        E = W = 0
        cnt = 0
        for code, elig in codes.items():
            t = towns.get(code)
            if t and isinstance(t[0], (int, float)) and t[0] > 0:
                E += elig
                W += t[0] * elig
                cnt += 1
        if E:
            out[name] = round(W / E, 1)
            out[name + "_n"] = cnt
    return out or None


V26_URL = "https://votes26.com/api/v1/elections/26/turnout"


def update_turnout26(path):
    """אחוזי הצבעה מ-votes26.com: דיווחים רשמיים לפי שעה + אומדני מגזרים מקלפיות מדגם. נשמר כמו שהוא ב-live/turnout26.json."""
    raw = download(V26_URL + "?t=%d" % int(datetime.now().timestamp()))
    d = json.loads(raw.decode("utf-8"))
    if not isinstance(d.get("reports"), list):
        raise SystemExit("votes26: unexpected format")
    try:
        old = json.load(open(path, encoding="utf-8"))
        if old.get("updated_at_utc") == d.get("updated_at_utc") and len(old.get("reports", [])) == len(d["reports"]):
            print("votes26 turnout unchanged (%s, %d reports)" % (d.get("updated_at_utc"), len(d["reports"])))
            return
    except Exception:
        pass
    # שומרים רק את מה שהדף צריך (הקובץ המלא גדול)
    keep_n = ("now", "est", "prev", "lo", "hi", "reported", "stations", "coverage", "status", "eligible", "voters")
    slim = {"schema_version": d.get("schema_version"), "updated_at_utc": d.get("updated_at_utc"),
            "fetched": datetime.now(IL).isoformat(timespec="seconds"), "source": V26_URL, "reports": []}
    for r in d["reports"]:
        n = r.get("national") or {}
        slim["reports"].append({
            "at": r.get("at"), "hour": r.get("hour"),
            "national": {k: n.get(k) for k in keep_n if k in n},
            "sectors": [{k: s.get(k) for k in ("id", "now", "est", "prev", "eligible", "voters") if k in s} for s in (r.get("sectors") or [])],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=1)
    print("votes26 turnout written: %d reports, updated %s" % (len(d["reports"]), d.get("updated_at_utc")))


def nearest_slot(label):
    """'16:41' -> ('16:00', 41); '17:30' -> ('18:00', 30): השעה הזוגית הקרובה והמרחק בדקות."""
    try:
        h, m = [int(x) for x in label.split(":")[:2]]
    except Exception:
        return None, None
    minutes = h * 60 + m
    best = min((10, 12, 14, 16, 18, 20, 22), key=lambda H: abs(minutes - H * 60))
    return "%02d:00" % best, abs(minutes - best * 60)

# ---- קובצי "שיעור ההצבעה בכל קלפי" של ועדת הבחירות (gov.il), נאספים ב-9:00, 12:00, 16:00, 20:00 ----
GOV_XLSX = "https://www.gov.il/BlobFolder/generalpage/turnout_at_polling_stations/he/voter_turnout_%s.xlsx"
GOV_HOURS = ("09", "12", "16", "20")


def read_xlsx_rows(data):
    """קורא גיליון ראשון מקובץ xlsx (ספרייה סטנדרטית בלבד): רשימת מילונים {עמודה: ערך}."""
    import zipfile, re as _re
    from xml.etree import ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(data))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(ns + "si"):
            ss.append("".join(t.text or "" for t in si.iter(ns + "t")))
    sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    rows = []
    for r in ET.fromstring(z.read(sheet)).iter(ns + "row"):
        row = {}
        for c in r.findall(ns + "c"):
            col = _re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find(ns + "v")
            if v is None:
                isv = c.find(ns + "is")
                row[col] = "".join(t.text or "" for t in isv.iter(ns + "t")) if isv is not None else None
            else:
                row[col] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(row)
    return rows


def update_places_official(path):
    """מצרף ל-turnout.json את אחוז ההצבעה הרשמי של היישובים הנבחרים מקובצי הקלפיות (09/12/16/20)."""
    try:
        tj = json.load(open(path, encoding="utf-8"))
    except Exception:
        tj = {}
    done = tj.setdefault("official_files", {})
    pl = tj.setdefault("k26_places", {})
    off = tj.setdefault("k26_places_official", {})
    changed = False
    for hh in GOV_HOURS:
        if hh in done:
            continue
        try:
            data = download(GOV_XLSX % hh)
        except Exception as e:
            print("gov.il file %s not available yet (%s)" % (hh, getattr(e, "code", e)))
            continue
        if not data.startswith(b"PK"):
            print("gov.il file %s is not xlsx yet" % hh)
            continue
        rows = read_xlsx_rows(data)[1:]
        f = lambda x: float(x) if x not in (None, "") else 0.0
        for code, name in PLACES.items():
            b = [r for r in rows if (r.get("A") or "").strip() == code]
            if not b:
                continue
            e = sum(f(r.get("E")) for r in b)
            v = sum(f(r.get("F")) for r in b)
            times = sorted(f(r.get("H")) for r in b if r.get("H"))
            med = times[len(times) // 2] if times else 0
            label = "%02d:%02d" % (int(med * 24), int(round((med * 24 - int(med * 24)) * 60)))
            pct = round(v / e * 100, 1) if e else 0
            slot = "%s:00" % hh
            off.setdefault(slot, {})[code] = {"pct": pct, "voters": int(v), "eligible": int(e), "stations": len(b), "reported": label}
            # גם לטבלת השעות: השעה הזוגית הקרובה, עם מספרי המצביעים הרשמיים
            pslot, dist = nearest_slot(label)
            cur = pl.setdefault(pslot, {})
            old = cur.get(code)
            if old is None or nearest_slot(old[1])[1] is None or dist <= nearest_slot(old[1])[1]:
                cur[code] = [pct, label, int(v), int(e)]
            elif old and len(old) < 4 and old[0] == pct:  # אותו ערך מההזנה – מצרפים את מספרי המצביעים הרשמיים
                cur[code] = [old[0], old[1], int(v), int(e)]
            print("official %s %s: %s%% (%d/%d, %d stations, reported ~%s)" % (hh, name, pct, v, e, len(b), label))
        done[hh] = datetime.now(IL).isoformat(timespec="seconds")
        changed = True
    if changed:
        tj["updated"] = datetime.now(IL).isoformat(timespec="seconds")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(tj, fh, ensure_ascii=False, indent=1)


def update_turnout(path):
    """מוסיף ל-live/turnout.json את אחוז ההצבעה האחרון שפורסם (דרך הזנת election-il-2026)."""
    try:
        day = json.loads(download(DAY_URL + "?t=%d" % int(datetime.now().timestamp())).decode("utf-8"))
    except Exception as e:
        print("turnout feed unavailable:", e)
        return
    t = day.get("turnout") or {}
    pct, label = t.get("pct"), t.get("updated")
    slot = bulletin_slot(label or "")
    if not (isinstance(pct, (int, float)) and pct > 0 and slot):
        return
    try:
        tj = json.load(open(path, encoding="utf-8"))
    except Exception:
        tj = {"k26": {}}
    k26 = tj.setdefault("k26", {})
    sectors = sector_estimates(day)
    sec = tj.setdefault("k26_sectors", {})
    changed = False
    if k26.get(slot) != pct:
        k26[slot] = pct
        changed = True
    if sectors and sec.get(slot) != sectors:
        sec[slot] = sectors
        changed = True
    # יישובים נבחרים: הדיווח היישובי נרשם לשעה הזוגית הקרובה לשעה שלו (לא לשעת הדיווח הארצי),
    # ולכל שעה נשמר הדיווח הקרוב ביותר לשעה העגולה
    towns = day.get("live_towns") or {}
    pl = tj.setdefault("k26_places", {})
    for code in PLACES:
        t = towns.get(code)
        if t and isinstance(t[0], (int, float)) and t[0] > 0:
            tlabel = t[2] if len(t) > 2 else ""
            pslot, dist = nearest_slot(tlabel)
            if not pslot:
                continue
            cur = pl.setdefault(pslot, {})
            old = cur.get(code)
            if old != [t[0], tlabel]:
                if old is None or nearest_slot(old[1])[1] is None or dist <= nearest_slot(old[1])[1]:
                    cur[code] = [t[0], tlabel]
                    changed = True
    if not changed:
        print("turnout unchanged: %s %s%%" % (slot, pct))
        return
    tj["updated"] = datetime.now(IL).isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tj, f, ensure_ascii=False, indent=1)
    print("turnout written: %s %s%%" % (slot, pct))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--file", help="קובץ מקומי במקום הורדה")
    ap.add_argument("--out", default="live/results.json")
    ap.add_argument("--turnout", default="live/turnout.json")
    ap.add_argument("--no-turnout", action="store_true")
    a = ap.parse_args()
    if not a.no_turnout:
        try:
            update_turnout(a.turnout)
        except Exception as e:
            print("turnout update failed:", e)
        try:
            update_turnout26(os.path.join(os.path.dirname(a.turnout) or ".", "turnout26.json"))
        except Exception as e:
            print("votes26 turnout failed:", repr(e))
        try:
            update_places_official(a.turnout)
        except Exception as e:
            print("official station files failed:", repr(e))
    data = None
    try:  # מקור ראשון: קובץ ועדת הבחירות
        raw = open(a.file, "rb").read() if a.file else download(a.url, verbose=True)
        if not raw.strip():
            print("CEC file is empty (%d bytes)" % len(raw))
        else:
            d = summarize(decode(raw), a.file or a.url)
            if d["localities"] > 0:
                data = d
            else:
                print("CEC file has headers only")
    except SystemExit as e:
        print("CEC file not usable:", e)
    except Exception as e:
        print("CEC download failed:", repr(e))
    if data is None and not a.file:
        try:  # מקור שני: GovMap
            data = govmap_summary()
            print("using GovMap: %d localities, %s%% of ballot boxes counted" % (data["localities"], data.get("counted_pct")))
        except SystemExit as e:
            print("GovMap not usable:", e)
        except Exception as e:
            print("GovMap download failed:", repr(e))
    if data is None:
        print("no results from any source – nothing written")
        return 0
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    # לא לכתוב מחדש אם רק חותמת הזמן השתנתה
    if os.path.exists(a.out):
        try:
            old = json.load(open(a.out, encoding="utf-8"))
            same = all(old.get(k) == data[k] for k in ("localities", "eligible", "voters", "invalid", "valid", "votes"))
            if same:
                print("unchanged: %d localities, %d valid votes" % (data["localities"], data["valid"]))
                return 0
        except Exception:
            pass
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("written %s: %d localities, %d valid votes, %d letters" % (a.out, data["localities"], data["valid"], len(data["letters"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
