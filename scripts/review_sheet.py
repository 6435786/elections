#!/usr/bin/env python3
"""קובץ בדיקה ידנית למקומות הקלפי: לכל עיר גיליון, שורה לכל מקום קלפי (2026 ו-2022),
מה הותאם אוטומטית ובאיזו ודאות, ועמודות ריקות למילוי: אישור/תיקון ההתאמה ל-2022, שכונה.
מיקום: כתובת רשמית מקובץ ועדת הבחירות (stations26.json, דרך import_stations.py); שכונה משוערת מ-OpenStreetMap.
שימוש: python scripts/review_sheet.py <output.xlsx>
"""
import json, os, sys

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
HEAD = ["עיר", "מקום הקלפי 2026", "קלפיות 2026", "בז\"ב 2026", "מקום 2022 שהותאם", "איך הותאם", "קלפיות 2022",
        "✔ ההתאמה ל-2022 נכונה? (כן / לא / שם המקום הנכון)",
        "כתובת רשמית (ועדת הבחירות)", "הערת ועדת הבחירות", "מקור המיקום", "שכונה משוערת (OSM)", "מפה",
        "✔ שכונה נכונה / תיקון", "הערות"]
HOW = {"name": "שם זהה", "boxes": "שם דומה + מספרי קלפיות", "manual": "ידני", "all": "כל הקלפיות", None: "לא הותאם"}
FILL = (7, 13, 14)  # עמודות למילוי (0-based)


def main(out):
    boxes = json.load(open(os.path.join(LIVE, "boxes.json"), encoding="utf-8"))
    geo = json.load(open(os.path.join(LIVE, "place_geo.json"), encoding="utf-8"))
    sheets = []
    for code, city in boxes["cities"].items():
        rows = []
        for pl in sorted(city["places"], key=lambda p: (p["name"] is None, p["name"] or p["name22"] or "")):
            name = pl["name"]
            g = geo.get(code, {}).get(name or pl["name22"], {})
            if g.get("cec_addr") is not None:
                addr, srcl = g["cec_addr"], "רשמי – ועדת הבחירות"
            elif g.get("x"):
                addr, srcl = (g.get("inst") or "") + ((" · " + g["addr"]) if g.get("addr") else ""), "משוער – מוסד ממשרד החינוך"
            elif name is None:
                addr, srcl = "", "לא פעיל ב-2026"
            else:
                addr, srcl = "", "לא נמצא"
            rows.append([city["name"], name or "(לא פעיל ב-2026)", ", ".join(b["box"] for b in pl["boxes26"]) or "", sum(b["e"] for b in pl["boxes26"]) or "",
                         pl["name22"] or ("" if name is None else "— חדש ב-2026"), HOW.get(pl["match"]), ", ".join(b["box"] for b in pl["boxes22"]) or "",
                         "", addr, g.get("cec_note") or "", srcl, g.get("nbhd") or "", g.get("map") or "", "", ""])
        sheets.append((city["name"], rows))
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook(); wb.remove(wb.active)
        for title, rows in sheets:
            ws = wb.create_sheet(title[:31]); ws.sheet_view.rightToLeft = True
            ws.append(HEAD)
            for c in ws[1]:
                c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="E6EFEE"); c.alignment = Alignment(wrap_text=True, vertical="top")
            for r in rows:
                ws.append(r)
                if r[12]:
                    c = ws.cell(row=ws.max_row, column=13); c.hyperlink = r[12]; c.value = "מפה"; c.font = Font(color="136F73", underline="single")
            fill_y = PatternFill("solid", fgColor="FFF4CC")
            for row in ws.iter_rows(min_row=2):
                for idx in FILL:
                    row[idx].fill = fill_y
                if str(row[10].value or "").startswith("רשמי"):
                    row[8].fill = PatternFill("solid", fgColor="DDEEDD")
            widths = [12, 34, 22, 9, 30, 20, 22, 30, 28, 24, 22, 20, 8, 24, 20]
            for i, w in enumerate(widths):
                ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
            ws.freeze_panes = "A2"
        wb.save(out)
    except ImportError:
        import csv
        out = os.path.splitext(out)[0] + ".csv"
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f); w.writerow(HEAD)
            for title, rows in sheets:
                for r in rows:
                    w.writerow(r)
    print("written", out, sum(len(r) for _, r in sheets), "rows")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Desktop", "kalpiot_review.xlsx")))
