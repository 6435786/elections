#!/usr/bin/env python3
r"""קולט את סיווג הרשימות המוניציפליות מקובץ הבדיקה (haredi_lists_2024.xlsx, גיליונות 1 ו-2) וכותב live/muni_blocs.json:
{code: {letter: bloc}}. סיווג ידני גובר על האוטומטי; "לא חרדי" נשמר כ-"" כדי לבטל סיווג אוטומטי.
שורה בלי סיווג ידני מקבלת את הסיווג האוטומטי, אלא אם הוא "?" (לא הוכרע).
שימוש: python -I -X utf8 scripts/ingest_blocs.py [--report-only] [xlsx]
"""
import json, os, re, sys
from collections import Counter
import openpyxl

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
MUNI = r"C:\MUNI_RESULTS"
VALID = {"דגל התורה", "אגודת ישראל", "יהדות התורה (דגל+אגודה)", 'ש"ס', 'משותפת: יהדות התורה + ש"ס', "בני תורה (פלג)", "חרדי כללי", "לא חרדי"}


def norm(s):
    return re.sub(r"[\s\-\"'״׳]", "", str(s or ""))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    report_only = "--report-only" in sys.argv
    path = args[0] if args else os.path.join(os.path.expanduser("~"), "Desktop", "haredi_lists_2024.xlsx")
    muni = json.load(open(os.path.join(MUNI, "muni_2024.json"), encoding="utf-8"))
    name2code = {}
    for code, m in muni.items():
        for n in (m.get("muni"), m.get("name")):
            if n:
                name2code[norm(n)] = code
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    manual, auto, invalid, conflicts, no_code = {}, {}, [], [], set()
    for title, i_letter, i_auto, i_fix in (("רשימות חרדיות", 1, 3, 6), ("ערים חרדיות - כל הרשימות", 2, 4, 6)):
        rows = wb[title].iter_rows(values_only=True)
        next(rows)
        for r in rows:
            if not r or not r[0] or not r[i_letter]:
                continue
            city, letter = str(r[0]).strip(), str(r[i_letter]).strip()
            code = name2code.get(norm(city))
            if not code:
                no_code.add(city)
                continue
            a = str(r[i_auto] or "").strip()
            if a and not a.startswith("?"):
                auto.setdefault(code, {})[letter] = a
            fix = str(r[i_fix] or "").strip() if len(r) > i_fix else ""
            if not fix:
                continue
            if fix not in VALID:
                invalid.append((title, city, letter, fix))
                continue
            prev = manual.setdefault(code, {}).get(letter)
            if prev and prev != fix:
                conflicts.append((city, letter, prev, fix))
            manual[code][letter] = fix
    out = {}
    for code in set(auto) | set(manual):
        d = dict(auto.get(code, {}))
        d.update(manual.get(code, {}))
        out[code] = {l: ("" if b == "לא חרדי" else b) for l, b in d.items()}
    print("manual choices:", sum(len(v) for v in manual.values()), "| by value:", dict(Counter(b for v in manual.values() for b in v.values())))
    print("final classified lists:", sum(1 for v in out.values() for b in v.values() if b), "| authorities:", len(out))
    print("invalid values:", invalid[:20])
    print("conflicts between sheets:", conflicts[:20])
    print("cities without a 2024 council file:", sorted(no_code))
    if not report_only:
        json.dump(out, open(os.path.join(LIVE, "muni_blocs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written live/muni_blocs.json")


if __name__ == "__main__":
    sys.exit(main())
