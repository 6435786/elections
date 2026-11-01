#!/usr/bin/env python3
"""ממיר את מיקומי מקומות הקלפי (ITM) לקווי רוחב/אורך ומוסיף כתובת ושכונה משוערות (OpenStreetMap, Nominatim).
מעדכן את live/place_geo.json במקום: lat, lon, addr, nbhd, map. מכבד מגבלת קצב (בקשה בשנייה)."""
import json, math, os, sys, time, urllib.request, urllib.parse

LIVE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
UA = "ElectionsResearch/1.0 (6435786@gmail.com)"


def itm2wgs(E, N):
    a = 6378137.0; f = 1 / 298.257222101; e2 = 2 * f - f * f; k0 = 1.0000067
    lon0 = math.radians(35.2045169444); lat0 = math.radians(31.7343936111); FE = 219529.584; FN = 626907.39
    e4 = e2 * e2; e6 = e4 * e2

    def M(phi):
        return a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                    + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))
    Mval = M(lat0) + (N - FN) / k0
    mu = Mval / (a * (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2); T1 = math.tan(phi1) ** 2; C1 = (e2 / (1 - e2)) * math.cos(phi1) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5; D = (E - FE) / (N1 * k0); ep2 = e2 / (1 - e2)
    lat = phi1 - (N1 * math.tan(phi1) / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24
                                               + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D ** 6 / 720)
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D ** 5 / 120) / math.cos(phi1)
    return round(math.degrees(lat) + 0.00011, 6), round(math.degrees(lon) - 0.00022, 6)  # תיקון דאטום משוער


def reverse(lat, lon):
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "accept-language": "he", "zoom": 17})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/reverse?" + q, headers={"User-Agent": UA})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    a = d.get("address", {})
    street = " ".join(x for x in [a.get("road") or a.get("pedestrian") or a.get("footway") or "", a.get("house_number") or ""] if x).strip()
    nbhd = a.get("neighbourhood") or a.get("suburb") or a.get("quarter") or a.get("residential") or ""
    return street, nbhd, d.get("name") or ""


def main():
    p = os.path.join(LIVE, "place_geo.json")
    g = json.load(open(p, encoding="utf-8"))
    todo = [(code, name, v) for code, res in g.items() for name, v in res.items() if (v.get("x") or v.get("lat")) and not v.get("addr_done")]
    print("to geocode:", len(todo))
    for i, (code, name, v) in enumerate(todo):
        if v.get("src") == "cec" and v.get("lat"):
            lat, lon = v["lat"], v["lon"]  # מיקום רשמי של ועדת הבחירות
        else:
            lat, lon = itm2wgs(v["x"], v["y"])
        v["lat"], v["lon"] = lat, lon
        v["map"] = "https://www.google.com/maps?q=%s,%s" % (lat, lon)
        try:
            street, nbhd, pname = reverse(lat, lon)
            v["addr"], v["nbhd"], v["osm_name"] = street, nbhd, pname
        except Exception as e:
            v["addr"], v["nbhd"] = "", ""
            print("  reverse failed for", code, name, repr(e)[:80])
        v["addr_done"] = True
        if (i + 1) % 25 == 0:
            json.dump(g, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            print("  ", i + 1, "done")
        time.sleep(1.1)
    json.dump(g, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    n = sum(1 for res in g.values() for v in res.values() if v.get("addr"))
    print("done; with street:", n, "| with neighbourhood:", sum(1 for res in g.values() for v in res.values() if v.get("nbhd")))


if __name__ == "__main__":
    sys.exit(main())
