"""Generate the Power BI Project (PBIP) definition for the FHWA VMT dashboard.

Deterministic: every run rewrites the .pbip project folders from the single
source of truth below, so the committed project can always be rebuilt.

Usage:  python scripts/generate_pbip.py
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "TrafficOperations.Report"
MODEL_DIR = ROOT / "TrafficOperations.SemanticModel"

RAW_BASE = (
    "https://raw.githubusercontent.com/Skippythe222211111/"
    "power-bi-operations-dashboard/main/data"
)

# The parameter is written into the model; DATA_BASE lets a local build point at
# the committed CSV folder instead of the public URL.
DATA_BASE = os.environ.get("DATA_BASE", RAW_BASE)

PAGE_W, PAGE_H = 1280, 720

SCHEMA_PBIP = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json"
SCHEMA_PLATFORM = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json"
SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json"
SCHEMA_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"


def tag() -> str:
    return str(uuid.uuid4())


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lit(value) -> dict:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, str):
        text = "'" + value.replace("'", "''") + "'"
    else:
        text = str(value)
    return {"expr": {"Literal": {"Value": text}}}


def col(table: str, column: str, active: bool = True) -> dict:
    projection = {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
        "queryRef": f"{table}.{column}",
        "nativeQueryRef": column,
    }
    if active:
        projection["active"] = True
    return projection


def measure(name: str, display: str | None = None, fmt: str | None = None) -> dict:
    projection = {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "VMT"}}, "Property": name}},
        "queryRef": f"VMT.{name}",
        "nativeQueryRef": display or name,
    }
    if fmt:
        projection["format"] = fmt
    return projection


def visual(
    name: str,
    visual_type: str,
    x: float,
    y: float,
    width: float,
    height: float,
    roles: dict[str, list[dict]],
    title: str,
    sort: dict | None = None,
    show_legend: bool | None = None,
    hide_total: bool = False,
) -> dict:
    query: dict = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
    if sort:
        query["sortDefinition"] = {"sort": [sort], "isDefaultSort": True}
    container = {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
        "visual": {
            "visualType": visual_type,
            "query": query,
            "drillFilterOtherVisuals": True,
            "visualContainerObjects": {
                "title": [
                    {
                        "properties": {
                            "show": lit(True),
                            "text": lit(title),
                            "fontSize": lit(12),
                            "bold": lit(True),
                            "alignment": lit("left"),
                        }
                    }
                ]
            },
        },
    }
    if show_legend is not None:
        container["visual"]["objects"] = {
            "legend": [{"properties": {"show": lit(show_legend), "position": lit("Top")}}]
        }
    if hide_total:
        container["visual"].setdefault("objects", {})["total"] = [
            {"properties": {"show": lit(False)}}
        ]
    return container


def page(name: str, display: str, visuals: list[dict]) -> dict:
    return {"name": name, "displayName": display, "visuals": visuals}


def sort_by(measure_name: str) -> dict:
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "VMT"}}, "Property": measure_name}},
        "direction": "Descending",
    }


def build_pages() -> list[dict]:
    month_axis = col("DimDate", "month_label", active=False)
    region_axis = col("DimState", "region")
    state_axis = col("DimState", "state")

    overview = page(
        "Overview",
        "1. Обзор",
        [
            visual("v01", "card", 16, 16, 300, 92,
                   {"Values": [measure("VMT L12M", "VMT за 12 мес., млн")]},
                   "VMT за последние 12 месяцев, млн"),
            visual("v02", "card", 328, 16, 300, 92,
                   {"Values": [measure("VMT YoY %", "YoY, %", "0.0%")]},
                   "12 мес. к предыдущим 12 мес."),
            visual("v03", "card", 640, 16, 300, 92,
                   {"Values": [measure("States Reporting", "Штатов в отчёте")]},
                   "Штатов в отчёте"),
            visual("v04", "card", 952, 16, 312, 92,
                   {"Values": [measure("Avg Monthly VMT", "Средний VMT в месяц, млн")]},
                   "Средний VMT в месяц, млн"),
            visual("v05", "lineChart", 16, 124, 620, 286,
                   {"Category": [month_axis], "Y": [measure("Total VMT", "VMT, млн")]},
                   "Национальный VMT по месяцам, млн"),
            visual("v06", "clusteredBarChart", 648, 124, 616, 286,
                   {"Category": [state_axis], "Y": [measure("Total VMT", "VMT, млн")]},
                   "Топ-10 штатов по VMT, млн", sort=sort_by("Total VMT"), show_legend=False),
            visual("v07", "donutChart", 16, 424, 420, 280,
                   {"Category": [region_axis], "Y": [measure("Total VMT", "VMT, млн")]},
                   "Доля регионов в VMT"),
            visual("v08", "tableEx", 448, 424, 816, 280,
                   {"Values": [col("DimDate", "month_label", active=False),
                               measure("Total VMT", "VMT, млн"),
                               measure("VMT LY", "VMT год назад, млн")]},
                   "Последние месяцы: VMT и год назад", hide_total=True),
        ],
    )

    trend = page(
        "Trend",
        "2. Динамика",
        [
            visual("v09", "columnChart", 16, 16, 1248, 336,
                   {"Category": [month_axis], "Y": [measure("Total VMT", "VMT, млн")],
                    "Legend": [col("DimState", "region", active=False)]},
                   "VMT по месяцам и регионам, млн"),
            visual("v10", "lineChart", 16, 364, 616, 340,
                   {"Category": [month_axis], "Y": [measure("VMT YoY Month %", "YoY, %", "0.0%")]},
                   "Рост к тому же месяцу прошлого года, %", show_legend=False),
            visual("v11", "lineChart", 648, 364, 616, 340,
                   {"Category": [month_axis], "Y": [measure("VMT L12M", "Скользящие 12 мес., млн")]},
                   "Скользящее окно 12 месяцев, млн", show_legend=False),
        ],
    )

    states = page(
        "States",
        "3. Штаты и регионы",
        [
            visual("v12", "slicer", 16, 16, 264, 688,
                   {"Values": [col("DimState", "region")]},
                   "Фильтр по региону"),
            visual("v13", "tableEx", 296, 16, 968, 396,
                   {"Values": [col("DimState", "state", active=False),
                               col("DimState", "region", active=False),
                               measure("Total VMT", "VMT, млн"),
                               measure("VMT YoY %", "YoY, %", "0.0%"),
                               measure("VMT Share", "Доля в VMT", "0.0%")]},
                   "Штаты: объём, динамика, доля"),
            visual("v14", "clusteredBarChart", 296, 424, 968, 280,
                   {"Category": [state_axis], "Y": [measure("VMT YoY %", "YoY, %", "0.0%")]},
                   "Рост год к году по штатам, %", sort=sort_by("VMT YoY %"), show_legend=False),
        ],
    )
    return [overview, trend, states]


def tmdl_column(name: str, data_type: str, source: str | None = None, fmt: str | None = None,
                summarize: str = "none", sort_by: str | None = None) -> str:
    lines = [f"\tcolumn {name}", f"\t\tdataType: {data_type}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines.append(f"\t\tlineageTag: {tag()}")
    lines.append(f"\t\tsummarizeBy: {summarize}")
    if sort_by:
        lines.append(f"\t\tsortByColumn: {sort_by}")
    if source:
        lines.append(f"\t\tsourceColumn: {source}")
    return "\n".join(lines)


MEASURES = [
    ("Total VMT", "SUM ( VMT[vmt_millions] )", "#,0.0"),
    ("VMT L12M",
     "CALCULATE ( [Total VMT], DATESINPERIOD ( DimDate[date], MAX ( VMT[month] ), -12, MONTH ) )",
     "#,0.0"),
    ("VMT Prev12M",
     "CALCULATE ( [Total VMT], DATESINPERIOD ( DimDate[date], MAX ( VMT[month] ), -24, MONTH ) ) - [VMT L12M]",
     "#,0.0"),
    ("VMT YoY %", "DIVIDE ( [VMT L12M] - [VMT Prev12M], [VMT Prev12M] )", "0.0%"),
    ("VMT YoY Month %", "DIVIDE ( [Total VMT] - [VMT LY], [VMT LY] )", "0.0%"),
    ("VMT LY", "CALCULATE ( [Total VMT], SAMEPERIODLASTYEAR ( DimDate[date] ) )", "#,0.0"),
    ("Avg Monthly VMT", "AVERAGEX ( VALUES ( DimDate[date] ), [Total VMT] )", "#,0.0"),
    ("States Reporting", "DISTINCTCOUNT ( VMT[state] )", "#,0"),
    ("VMT Seasonality", "DIVIDE ( [Total VMT], CALCULATE ( [Total VMT], ALL ( DimDate ) ) )", "0.0%"),
    ("VMT Share", "DIVIDE ( [Total VMT], CALCULATE ( [Total VMT], ALLSELECTED ( DimState ) ) )", "0.0%"),
    ("Monitoring Stations", "SUM ( VMT[stations] )", "#,0"),
]


def csv_partition(table_name: str, file_name: str, columns: int, transformations: str) -> str:
    return (
        f"\tpartition {table_name} = m\n\t\tmode: import\n\t\tsource =\n"
        "\t\t\t\tlet\n"
        '\t\t\t\t    Raw = if Text.StartsWith(DataBase, "http") then '
        f'Web.Contents(DataBase & "/{file_name}") else File.Contents(DataBase & "\\{file_name}"),\n'
        "\t\t\t\t    Source = Csv.Document(Raw,"
        f'[Delimiter=",", Columns={columns}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted,{{{transformations}}})\n"
        "\t\t\t\tin\n"
        "\t\t\t\t    Typed\n"
    )


def build_model() -> None:
    model_dir = MODEL_DIR / "definition"
    (model_dir / "tables").mkdir(parents=True, exist_ok=True)

    write_json(MODEL_DIR / ".platform", {
        "$schema": SCHEMA_PLATFORM,
        "metadata": {"type": "SemanticModel", "displayName": "TrafficOperations"},
        "config": {"version": "2.0", "logicalId": tag()},
    })
    write_json(MODEL_DIR / "definition.pbism", {"version": "4.1", "settings": {}})
    (model_dir / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1606\n", encoding="utf-8")

    (model_dir / "expressions.tmdl").write_text(
        "expression DataBase = \"" + DATA_BASE + "\" meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]\n"
        f"\tlineageTag: {tag()}\n\n"
        "\tannotation PBI_ResultType = Text\n",
        encoding="utf-8",
    )

    vmt_cols = "\n\n".join([
        tmdl_column("month", "dateTime", "month", "yyyy-mm"),
        tmdl_column("state", "string", "state"),
        tmdl_column("region", "string", "region"),
        tmdl_column("vmt_millions", "double", "vmt_millions", "#,0.0", "sum"),
        tmdl_column("stations", "int64", "stations", "#,0"),
    ])
    measures_block = "\n\n".join(
        f"\tmeasure '{name}' = {expr}\n\t\tformatString: {fmt}\n\t\tlineageTag: {tag()}\n"
        for name, expr, fmt in MEASURES
    )
    (model_dir / "tables" / "VMT.tmdl").write_text(
        "table VMT\n"
        f"\tlineageTag: {tag()}\n\n"
        f"{vmt_cols}\n\n"
        f"{measures_block}\n"
        + csv_partition(
            "VMT", "traffic_vmt_monthly.csv", 5,
            '{"month", type date}, {"state", type text}, {"region", type text}, '
            '{"vmt_millions", type number}, {"stations", Int64.Type}',
        )
        + "\n\tannotation PBI_NavigationStepName = Navigation\n\n"
        "\tannotation PBI_ResultType = Table\n",
        encoding="utf-8",
    )

    date_cols = "\n\n".join([
        tmdl_column("date", "dateTime", "date", "dd.mm.yyyy"),
        tmdl_column("year", "int64", "year", "0"),
        tmdl_column("month_number", "int64", "month_number", "0"),
        tmdl_column("month_name", "string", "month_name", sort_by="month_number"),
        tmdl_column("month_label", "string", "month_label", sort_by="date"),
        tmdl_column("quarter", "string", "quarter"),
    ])
    (model_dir / "tables" / "DimDate.tmdl").write_text(
        "table DimDate\n"
        f"\tlineageTag: {tag()}\n\n"
        f"{date_cols}\n\n"
        + csv_partition(
            "DimDate", "dim_date.csv", 6,
            '{"date", type date}, {"year", Int64.Type}, {"month_number", Int64.Type}, '
            '{"month_name", type text}, {"month_label", type text}, {"quarter", type text}',
        )
        + "\n\tannotation PBI_NavigationStepName = Navigation\n\n"
        "\tannotation PBI_ResultType = Table\n",
        encoding="utf-8",
    )

    state_cols = "\n\n".join([
        tmdl_column("state", "string", "state"),
        tmdl_column("region", "string", "region"),
    ])
    (model_dir / "tables" / "DimState.tmdl").write_text(
        "table DimState\n"
        f"\tlineageTag: {tag()}\n\n"
        f"{state_cols}\n\n"
        + csv_partition(
            "DimState", "dim_state.csv", 2,
            '{"state", type text}, {"region", type text}',
        )
        + "\n\tannotation PBI_NavigationStepName = Navigation\n\n"
        "\tannotation PBI_ResultType = Table\n",
        encoding="utf-8",
    )

    (model_dir / "relationships.tmdl").write_text(
        "relationship " + tag() + "\n"
        "\tfromColumn: VMT.month\n"
        "\ttoColumn: DimDate.date\n\n"
        "relationship " + tag() + "\n"
        "\tfromColumn: VMT.state\n"
        "\ttoColumn: DimState.state\n",
        encoding="utf-8",
    )

    (model_dir / "model.tmdl").write_text(
        "model Model\n"
        "\tculture: en-US\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n\n"
        'annotation PBI_QueryOrder = ["DataBase","VMT","DimDate","DimState"]\n\n'
        "annotation __PBI_TimeIntelligenceEnabled = 1\n\n"
        "annotation PBIDesktopVersion = 2.157.879.0\n\n"
        'annotation PBI_ProTooling = ["DevMode"]\n\n'
        "ref table VMT\n\n"
        "ref table DimDate\n\n"
        "ref table DimState\n",
        encoding="utf-8",
    )


def build_report(pages: list[dict]) -> None:
    definition = REPORT_DIR / "definition"
    write_json(REPORT_DIR / ".platform", {
        "$schema": SCHEMA_PLATFORM,
        "metadata": {"type": "Report", "displayName": "TrafficOperations"},
        "config": {"version": "2.0", "logicalId": tag()},
    })
    write_json(REPORT_DIR / "definition.pbir", {
        "$schema": SCHEMA_PBIR,
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../TrafficOperations.SemanticModel"}},
    })
    write_json(definition / "version.json", {"$schema": SCHEMA_VERSION, "version": "2.0.0"})
    write_json(definition / "report.json", {
        "$schema": SCHEMA_REPORT,
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.55", "type": "SharedResources"}},
        "layoutOptimization": "None",
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
        "slowDataSourceSettings": {
            "isCrossHighlightingDisabled": False,
            "isSlicerSelectionsButtonEnabled": False,
            "isFilterSelectionsButtonEnabled": False,
            "isFieldWellButtonEnabled": False,
            "isApplyAllButtonEnabled": False,
        },
    })
    write_json(definition / "pages" / "pages.json", {
        "$schema": SCHEMA_PAGES,
        "pageOrder": [p["name"] for p in pages],
        "activePageName": pages[0]["name"],
    })
    for pg in pages:
        page_dir = definition / "pages" / pg["name"]
        write_json(page_dir / "page.json", {
            "$schema": SCHEMA_PAGE,
            "name": pg["name"],
            "displayName": pg["displayName"],
            "displayOption": "FitToPage",
            "height": PAGE_H,
            "width": PAGE_W,
        })
        for vis in pg["visuals"]:
            write_json(page_dir / "visuals" / vis["name"] / "visual.json", vis)


def write_project_file() -> None:
    write_json(ROOT / "TrafficOperations.pbip", {
        "$schema": SCHEMA_PBIP,
        "version": "1.0",
        "artifacts": [{"report": {"path": "TrafficOperations.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })


def main() -> None:
    pages = build_pages()
    build_model()
    build_report(pages)
    write_project_file()
    visuals = sum(len(p["visuals"]) for p in pages)
    print(f"pages: {len(pages)}, visuals: {visuals}")


if __name__ == "__main__":
    main()
