"""Merge observed daily weather and climatology into one daily CSV."""

from datetime import date, timedelta
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "external"
WEATHER_DAILY = EXTERNAL_DIR / "weather_daily.parquet"
WEATHER_CLIMATOLOGY = EXTERNAL_DIR / "weather_climatology.parquet"
OUTPUT = EXTERNAL_DIR / "合并表格，weather日级.csv"

DATE_START = date(2023, 1, 1)
DATE_END = date(2029, 12, 31)

HEADER_CN = [
    "日期",
    "星期(1=周一..7=周日)",
    "一年中的第几天",
    "是否有真实历史天气",
    "天气来源(observed/climatology)",
    "真实日降水量mm",
    "真实日降雪量mm",
    "真实低能见度小时数",
    "真实日最低气温C",
    "真实日最高气温C",
    "真实是否有结冰风险",
    "气候态平均降水量mm",
    "气候态90分位降水量mm",
    "气候态湿日概率",
    "气候态平均低能见度小时数",
    "气候态低能见度/雾概率",
    "气候态结冰风险概率",
    "气候态平均最低气温C",
    "气候态平均最高气温C",
    "气候态统计年份数",
]


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main() -> None:
    calendar = pl.DataFrame(
        {
            "date": [d for d in daterange(DATE_START, DATE_END)],
        }
    ).with_columns(
        [
            pl.col("date").dt.weekday().alias("weekday_iso"),
            pl.col("date").dt.ordinal_day().alias("doy"),
        ]
    )

    observed = (
        pl.read_parquet(WEATHER_DAILY)
        .with_columns(pl.col("date").cast(pl.Date))
        .select(
            [
                "date",
                "precip_mm",
                "snowfall_mm",
                "low_vis_hours",
                "t_min_c",
                "t_max_c",
                "has_ice_risk",
            ]
        )
    )

    climatology = pl.read_parquet(WEATHER_CLIMATOLOGY)

    merged = (
        calendar.join(observed, on="date", how="left")
        .join(climatology, on="doy", how="left")
        .with_columns(
            [
                pl.col("precip_mm").is_not_null().cast(pl.Int8).alias("has_observed_weather"),
                pl.when(pl.col("precip_mm").is_not_null())
                .then(pl.lit("observed"))
                .otherwise(pl.lit("climatology"))
                .alias("weather_source"),
                pl.col("has_ice_risk").cast(pl.Int8),
            ]
        )
        .select(
            [
                "date",
                "weekday_iso",
                "doy",
                "has_observed_weather",
                "weather_source",
                "precip_mm",
                "snowfall_mm",
                "low_vis_hours",
                "t_min_c",
                "t_max_c",
                "has_ice_risk",
                "precip_mm_mean",
                "precip_mm_p90",
                "precip_prob_wet",
                "low_vis_hours_mean",
                "low_vis_prob_foggy",
                "ice_risk_prob",
                "t_min_c_mean",
                "t_max_c_mean",
                "n_years",
            ]
        )
        .sort("date")
    )

    with open(OUTPUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(";".join(merged.columns) + "\n")
        fh.write(";".join(HEADER_CN) + "\n")
        for row in merged.iter_rows():
            values = ["" if value is None else str(value) for value in row]
            fh.write(";".join(values) + "\n")

    observed_days = merged.select(pl.col("has_observed_weather").sum()).item()
    print(f"Saved: {OUTPUT}")
    print(f"Total days: {merged.height:,}")
    print(f"Observed weather days: {observed_days:,}")
    print(f"Climatology-only days: {merged.height - observed_days:,}")
    print(f"Date range: {merged['date'].min()} -> {merged['date'].max()}")


if __name__ == "__main__":
    main()
