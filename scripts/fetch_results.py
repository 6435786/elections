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
IL = timezone(timedelta(hours=2))  # שעון חורף בישראל (27.10.2026)


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


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
    }


DAY_URL = "https://navonyaniv.github.io/election-il-2026/results.json"


def bulletin_slot(label):
    """'12:49' -> '12:00' (הוועדה מפרסמת בשעות זוגיות); '13:14' -> '12:00'."""
    try:
        h, m = label.split(":")[:2]
        h = int(h)
        h -= h % 2
        return "%02d:00" % h
    except Exception:
        return None


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
    if k26.get(slot) == pct:
        print("turnout unchanged: %s %s%%" % (slot, pct))
        return
    k26[slot] = pct
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
        update_turnout(a.turnout)
    raw = open(a.file, "rb").read() if a.file else download(a.url)
    data = summarize(decode(raw), a.file or a.url)
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
