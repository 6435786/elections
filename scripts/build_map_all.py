#!/usr/bin/env python3
r"""קובץ אחד למפה הארצית: live/map_all.json = {places:[{c,cn,n,n22,pt:[lat,lon,addr,nbhd],b26:[...],b22:[...]}], skipped:{...}}
ביישובים עם שמות מקומות קלפי: נקודה לכל מקום (מיקום רשמי, live/points.json).
ביישובים קטנים בלי שמות: נקודה אחת ליישוב, במרכז מקומות הקלפי הרשמיים שלו (live/stations26.json), עם כל הקלפיות.
מעטפות חיצוניות (9999) אינן על המפה. מקומות בלי מיקום נספרים ב-skipped."""
import json, os, sys

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))


def main():
    pts = json.load(open(os.path.join(LIVE, "points.json"), encoding="utf-8"))
    st = json.load(open(os.path.join(LIVE, "stations26.json"), encoding="utf-8"))
    idx = json.load(open(os.path.join(LIVE, "loc_index.json"), encoding="utf-8"))
    alias = {"1061": "נוף הגליל"}
    places = []
    s = {"localities_no_location": [], "places_no_location": 0, "boxes_no_location": 0, "e26_no_location": 0}
    n_place = n_loc = 0
    for code in idx:
        if code == "9999":
            continue
        city = json.load(open(os.path.join(LIVE, "loc", code + ".json"), encoding="utf-8"))
        cn = alias.get(code) or city["name"]
        if code in pts:
            for p in city["places"]:
                if not p["name"]:
                    continue
                pt = pts[code].get(p["name"])
                if not pt:
                    s["places_no_location"] += 1; s["boxes_no_location"] += len(p["boxes26"]); s["e26_no_location"] += sum(b["e"] for b in p["boxes26"])
                    continue
                places.append({"c": code, "cn": cn, "n": p["name"], "n22": p["name22"], "pt": pt, "b26": p["boxes26"], "b22": p["boxes22"]})
                n_place += 1
        else:
            b26 = [b for p in city["places"] for b in p["boxes26"]]
            b22 = [b for p in city["places"] for b in p["boxes22"]]
            if not b26:
                continue
            ll = [(x["lat"], x["lon"]) for x in st.get(code, {}).get("places", []) if x["lat"]]
            if not ll:
                s["localities_no_location"].append(cn); s["boxes_no_location"] += len(b26); s["e26_no_location"] += sum(b["e"] for b in b26)
                continue
            lat, lon = round(sum(x[0] for x in ll) / len(ll), 5), round(sum(x[1] for x in ll) / len(ll), 5)
            places.append({"c": code, "cn": cn, "n": cn, "n22": cn if b22 else None, "whole": True, "pt": [lat, lon, "", ""], "b26": b26, "b22": b22})
            n_loc += 1
    json.dump({"places": places, "skipped": s}, open(os.path.join(LIVE, "map_all.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    e_on = sum(b["e"] for p in places for b in p["b26"]); e_all = sum(v["a26"]["e"] for v in idx.values())
    print("points:", len(places), "| by place", n_place, "| whole locality", n_loc)
    print("eligible on map %d of %d (%.1f%%)" % (e_on, e_all, 100 * e_on / e_all))
    print("skipped:", {k: (v if not isinstance(v, list) else len(v)) for k, v in s.items()})
    print("bytes:", os.path.getsize(os.path.join(LIVE, "map_all.json")))


if __name__ == "__main__":
    sys.exit(main())
