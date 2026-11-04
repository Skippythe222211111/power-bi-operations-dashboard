"""Independent KPI check for the FHWA dashboard.

Recomputes the headline numbers straight from data/*.csv with the standard
library only, so the DAX measures can be compared against a second
implementation. Writes reports/kpi_check.md.

Usage: python scripts/verify_kpis.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "reports" / "kpi_check.md"

MONTHS_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def month_key(iso: str) -> tuple[int, int]:
    year, month, _ = iso.split("-")
    return int(year), int(month)


def shift(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def main() -> None:
    rows = list(csv.DictReader((DATA / "traffic_vmt_monthly.csv").open(encoding="utf-8")))
    by_month: dict[tuple[int, int], float] = defaultdict(float)
    by_state: dict[str, float] = defaultdict(float)
    by_region: dict[str, float] = defaultdict(float)
    for row in rows:
        key = month_key(row["month"])
        value = float(row["vmt_millions"])
        by_month[key] += value
        by_state[row["state"]] += value
        by_region[row["region"]] += value

    months = sorted(by_month)
    last = months[-1]
    window = {shift(last[0], last[1], -i) for i in range(12)}
    window_prev = {shift(last[0], last[1], -i) for i in range(12, 24)}

    total = sum(by_month.values())
    l12 = sum(by_month[m] for m in window if m in by_month)
    prev12 = sum(by_month[m] for m in window_prev if m in by_month)
    yoy = (l12 - prev12) / prev12 if prev12 else None

    top_states = sorted(by_state.items(), key=lambda kv: kv[1], reverse=True)[:5]
    regions = sorted(by_region.items(), key=lambda kv: kv[1], reverse=True)

    lines = [
        "# Независимая проверка KPI",
        "",
        "Пересчёт по `data/*.csv` стандартной библиотекой Python, без pandas и без DAX.",
        "",
        f"- Период: {months[0][0]}-{months[0][1]:02d} … {last[0]}-{last[1]:02d}",
        f"- Месяцев: {len(months)}, штатов: {len(by_state)}",
        f"- VMT за весь период: {total:,.1f} млн",
        f"- VMT за 12 мес. (окно {MONTHS_RU[shift(last[0], last[1], -11)[1]]} "
        f"{shift(last[0], last[1], -11)[0]} … {MONTHS_RU[last[1]]} {last[0]}): {l12:,.1f} млн",
        f"- VMT за предыдущие 12 мес.: {prev12:,.1f} млн",
        f"- Рост 12 мес. к предыдущим 12 мес.: {yoy * 100:+.1f}%",
        f"- Средний VMT в месяц: {total / len(months):,.1f} млн",
        "",
        "## Топ-5 штатов по VMT",
        "",
        "| Штат | VMT, млн | Доля |",
        "|---|---:|---:|",
    ]
    for state, value in top_states:
        lines.append(f"| {state} | {value:,.1f} | {value / total * 100:.1f}% |")

    lines += ["", "## Доли регионов FHWA", "", "| Регион | VMT, млн | Доля |", "|---|---:|---:|"]
    for region, value in regions:
        lines.append(f"| {region} | {value:,.1f} | {value / total * 100:.1f}% |")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"total={total:,.1f} l12={l12:,.1f} prev12={prev12:,.1f} yoy={yoy * 100:+.2f}%")
    print(f"written {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
