"""Download FHWA Traffic Volume Trends workbooks and build tidy CSVs.

Usage: python build_tvt_data.py [--months 2024-01..2026-08]
"""
import csv
import datetime as dt
import io
import re
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
BASE = "https://www.fhwa.dot.gov/policyinformation/travel_monitoring/{code}tvt/{code}tvt.xlsx"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
REGIONS = {"Northeast", "South Atlantic", "North Central", "South Gulf", "West"}

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
DATA = ROOT / "data"


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_sheet(path, wanted):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for _, el in ET.iterparse(z.open("xl/sharedStrings.xml"), events=("end",)):
                if el.tag == NS + "si":
                    shared.append("".join(t.text or "" for t in el.iter(NS + "t")))
                    el.clear()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        relns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.get("Id"): r.get("Target") for r in rels}
        for sheet in wb.iter(NS + "sheet"):
            if sheet.get("name") != wanted:
                continue
            target = relmap[sheet.get(relns)].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            rows = []
            for _, el in ET.iterparse(z.open(target), events=("end",)):
                if el.tag != NS + "row":
                    continue
                vals = {}
                for c in el.findall(NS + "c"):
                    kind = c.get("t")
                    if kind == "inlineStr":
                        node = c.find(NS + "is")
                        text = "".join(t.text or "" for t in node.iter(NS + "t")) if node is not None else ""
                    else:
                        v = c.find(NS + "v")
                        text = None
                        if v is not None:
                            text = shared[int(v.text)] if kind == "s" else v.text
                    vals[col_index(c.get("r"))] = text
                rows.append([vals.get(i, "") for i in range(max(vals) + 1 if vals else 0)])
                el.clear()
            return rows
    raise ValueError(f"sheet {wanted} not found in {path}")


def num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_month(rows):
    """Return list of (state, region, stations, vmt_millions) from Table 5."""
    region = None
    out = []
    for row in rows:
        cell = (row[0] or "").strip() if row else ""
        if cell in REGIONS:
            region = cell
            continue
        if not cell or cell.lower().startswith(("subtotal", "totals", "note", "*", "table", "region and state")):
            continue
        if len(row) < 6:
            continue
        stations = num(row[3]) if len(row) > 3 else None
        vmt = num(row[4]) if len(row) > 4 else None
        if vmt is None or region is None:
            continue
        out.append((cell, region, int(stations) if stations else None, vmt))
    return out


def main():
    CACHE.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    start = dt.date(2024, 1, 1)
    end = dt.date(2026, 8, 1)
    fact = []
    cur = start
    while cur <= end:
        code = f"{cur.year % 100:02d}{MONTHS[cur.month - 1]}"
        path = CACHE / f"{code}.xlsx"
        if not path.exists():
            url = BASE.format(code=code)
            print("downloading", code, flush=True)
            with urllib.request.urlopen(url, timeout=120) as resp:
                path.write_bytes(resp.read())
        rows = read_sheet(path, "Page 6")
        states = parse_month(rows)
        print(code, "states:", len(states), flush=True)
        for state, region, stations, vmt in states:
            fact.append({
                "month": cur.isoformat(),
                "state": state,
                "region": region,
                "vmt_millions": round(vmt, 2),
                "stations": stations or "",
            })
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)

    with open(DATA / "traffic_vmt_monthly.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["month", "state", "region", "vmt_millions", "stations"])
        w.writeheader()
        w.writerows(fact)

    ru_month = ["янв", "фев", "мар", "апр", "май", "июн",
                "июл", "авг", "сен", "окт", "ноя", "дек"]
    day = dt.date(2023, 1, 1)
    calendar = []
    while day <= dt.date(2026, 8, 31):
        calendar.append({
            "date": day.isoformat(),
            "year": day.year,
            "month_number": day.month,
            "month_name": ru_month[day.month - 1],
            "month_label": f"{ru_month[day.month - 1]} {day.year % 100:02d}",
            "quarter": f"Q{(day.month - 1) // 3 + 1}",
        })
        day += dt.timedelta(days=1)
    with open(DATA / "dim_date.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "year", "month_number", "month_name", "month_label", "quarter"])
        w.writeheader()
        w.writerows(calendar)

    states = sorted({(r["state"], r["region"]) for r in fact})
    with open(DATA / "dim_state.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["state", "region"])
        w.writerows(states)

    print("rows:", len(fact), "states:", len(states))


if __name__ == "__main__":
    main()
