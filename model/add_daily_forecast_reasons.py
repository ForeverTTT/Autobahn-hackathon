from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data_autobahn"
KFZ_MODEL_PATH = ROOT / "models" / "kfz_h" / "multi.cbm"
DAILY_FORECAST_PATH = DATA_DIR / "forecast_2026_2029_daily.csv"

TRAIN_END = pd.Timestamp("2024-12-31 23:59:59")
PROFILE_KFZ_P90 = 0.90
PROFILE_V_P85 = 0.85

FILES = {
    "traffic": DATA_DIR / "合并表格，小时交通流量.csv",
    "temp": DATA_DIR / "合并表格，时间，气温，路温.csv",
    "holiday": DATA_DIR / "合并表格，holiday日级.csv",
    "weather": DATA_DIR / "合并表格，weather日级.csv",
    "construction": DATA_DIR / "合并表格，construction日级.csv",
    "events": DATA_DIR / "合并表格，special_events日级.csv",
}


def read_semicolon(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", skiprows=[1], dtype=str, keep_default_na=True)


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False).replace({"nan": np.nan, "": np.nan}),
        errors="coerce",
    )


def load_daily(path: Path, num_cols, cat_cols) -> pd.DataFrame:
    df = read_semicolon(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    for col in num_cols:
        if col in df.columns:
            df[col] = to_num(df[col]).fillna(0)
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    keep = ["date"] + [col for col in (num_cols + cat_cols) if col in df.columns]
    return df[keep].drop_duplicates("date")


def add_holiday_proximity(holiday: pd.DataFrame) -> pd.DataFrame:
    h = holiday.sort_values("date").copy().reset_index(drop=True)
    h["_next_start"] = h.loc[h["is_holiday_start"] == 1, "date"]
    h["_next_start"] = h["_next_start"].bfill()
    h["days_to_holiday_start"] = (h["_next_start"] - h["date"]).dt.days.clip(0, 30).fillna(30).astype(int)

    h["_last_end"] = h.loc[h["is_holiday_end"] == 1, "date"]
    h["_last_end"] = h["_last_end"].ffill()
    h["days_since_holiday_end"] = (h["date"] - h["_last_end"]).dt.days.clip(0, 30).fillna(30).astype(int)

    h["total_holiday_overlap"] = (h["school_holiday_count"] + h["public_holiday_count"]).clip(0, 6)
    weekday = h["date"].dt.weekday
    h["is_departure_wave_day"] = (
        (weekday == 5) & (h["days_to_holiday_start"] > 0) & (h["days_to_holiday_start"] <= 7)
    ).astype(int)
    h["is_return_wave_day"] = (
        (weekday == 6) & (h["days_since_holiday_end"] > 0) & (h["days_since_holiday_end"] <= 7)
    ).astype(int)
    return h.drop(columns=["_next_start", "_last_end"])


def load_feature_sources():
    traffic = read_semicolon(FILES["traffic"])
    for col in ["bab_km", "longitude", "latitude", "kfz_h", "sv_h", "v_kfz"]:
        traffic[col] = to_num(traffic[col])
    traffic["ts"] = pd.to_datetime(
        traffic["datum"] + " " + traffic["t_start"], format="%d.%m.%Y %H:%M:%S", errors="coerce"
    )
    traffic = traffic.dropna(subset=["ts"]).copy()
    traffic["date"] = traffic["ts"].dt.normalize()
    traffic["hour"] = traffic["ts"].dt.hour
    traffic["weekday"] = traffic["wochentag"].astype(int)
    traffic["site_id"] = traffic["road"] + "_" + traffic["direction"] + "_" + traffic["site_name"]
    traffic.loc[traffic["kfz_h"] < 0, "kfz_h"] = np.nan
    traffic.loc[traffic["sv_h"] < 0, "sv_h"] = np.nan
    traffic.loc[(traffic["kfz_h"].isna()) | (traffic["kfz_h"] <= 0), "v_kfz"] = np.nan
    traffic["lkw_ratio"] = np.where(traffic["kfz_h"] > 0, traffic["sv_h"] / traffic["kfz_h"], np.nan)

    temp_raw = read_semicolon(FILES["temp"])
    temp_raw["lt"] = to_num(temp_raw["lt"])
    temp_raw["fbt"] = to_num(temp_raw["fbt"])
    temp_raw["ts"] = pd.to_datetime(temp_raw["t_start"], errors="coerce")
    temp_raw = temp_raw.dropna(subset=["ts"]).copy()
    temp_raw["date"] = temp_raw["ts"].dt.normalize()
    temp_raw["hour"] = temp_raw["ts"].dt.hour
    temp_hourly = (
        temp_raw.groupby(["date", "hour"])
        .agg(lt_mean=("lt", "mean"), fbt_mean=("fbt", "mean"), fbt_min=("fbt", "min"))
        .reset_index()
    )
    temp_hourly["month"] = temp_hourly["date"].dt.month
    temp_climo = (
        temp_hourly.groupby(["month", "hour"])
        .agg(lt_mean_c=("lt_mean", "mean"), fbt_mean_c=("fbt_mean", "mean"), fbt_min_c=("fbt_min", "mean"))
        .reset_index()
    )

    holiday = load_daily(
        FILES["holiday"],
        [
            "is_school_holiday_DE_BY",
            "is_school_holiday_AT_SB",
            "is_school_holiday_AT_TI",
            "is_public_holiday_DE_BY",
            "is_public_holiday_AT_SB",
            "is_public_holiday_AT_TI",
            "school_holiday_count",
            "public_holiday_count",
            "is_holiday_start",
            "is_holiday_end",
            "in_traffic_window",
        ],
        ["window_direction", "window_risk_level", "a8_direction", "a93_direction"],
    )
    holiday = add_holiday_proximity(holiday)

    weather = read_semicolon(FILES["weather"])
    weather["date"] = pd.to_datetime(weather["date"], errors="coerce").dt.normalize()
    for col in [
        "precip_mm",
        "snowfall_mm",
        "low_vis_hours",
        "t_min_c",
        "t_max_c",
        "has_ice_risk",
        "precip_mm_mean",
        "low_vis_hours_mean",
        "ice_risk_prob",
        "t_min_c_mean",
        "t_max_c_mean",
    ]:
        if col in weather.columns:
            weather[col] = to_num(weather[col])
    weather["w_precip"] = weather["precip_mm"].fillna(weather.get("precip_mm_mean"))
    weather["w_snow"] = weather["snowfall_mm"].fillna(0)
    weather["w_lowvis"] = weather["low_vis_hours"].fillna(weather.get("low_vis_hours_mean"))
    weather["w_tmin"] = weather["t_min_c"].fillna(weather.get("t_min_c_mean"))
    weather["w_tmax"] = weather["t_max_c"].fillna(weather.get("t_max_c_mean"))
    weather["w_ice"] = weather["has_ice_risk"].fillna(weather.get("ice_risk_prob"))
    weather["weather_source"] = weather["weather_source"].fillna("climatology").astype(str)
    weather = weather[["date", "w_precip", "w_snow", "w_lowvis", "w_tmin", "w_tmax", "w_ice", "weather_source"]]

    construction = load_daily(
        FILES["construction"],
        [
            "has_a8_construction",
            "has_a93_construction",
            "a8_construction_count",
            "a93_construction_count",
            "has_2_plus_0",
            "two_plus_0_count",
            "max_closed_lanes",
            "sum_closed_lanes",
            "has_target_bbox_construction",
        ],
        [],
    )
    events = load_daily(
        FILES["events"],
        [
            "has_special_event",
            "active_event_count",
            "max_impact_level",
            "impact_score",
            "affects_a8_ost",
            "affects_a93_sued",
            "has_munich_event",
            "has_salzburg_event",
            "has_rosenheim_event",
            "has_kufstein_event",
            "has_confirmed_event",
            "has_estimated_event",
        ],
        [],
    )

    return traffic, temp_hourly, temp_climo, holiday, weather, construction, events


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date = df["date"]
    df["month"] = date.dt.month
    df["doy"] = date.dt.dayofyear
    df["week_of_year"] = date.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["weekday"] >= 6).astype(int)
    df["is_friday"] = (df["weekday"] == 5).astype(int)
    df["is_saturday"] = (df["weekday"] == 6).astype(int)
    df["is_sunday"] = (df["weekday"] == 7).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * (df["weekday"] - 1) / 7)
    df["dow_cos"] = np.cos(2 * np.pi * (df["weekday"] - 1) / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["doy_sin"] = np.sin(2 * np.pi * df["doy"] / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df["doy"] / 365.25)
    season_map = {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "autumn",
        10: "autumn",
        11: "autumn",
    }
    df["season"] = df["month"].map(season_map)
    return df


def make_merge_conditional(temp_hourly, temp_climo, holiday, weather, construction, events):
    def merge_conditional(df: pd.DataFrame) -> pd.DataFrame:
        df = df.merge(holiday, on="date", how="left")
        df = df.merge(weather, on="date", how="left")
        df = df.merge(construction, on="date", how="left")
        df = df.merge(events, on="date", how="left")
        df = df.merge(temp_hourly[["date", "hour", "lt_mean", "fbt_mean", "fbt_min"]], on=["date", "hour"], how="left")
        df = df.merge(temp_climo, on=["month", "hour"], how="left")
        df["lt_mean"] = df["lt_mean"].fillna(df["lt_mean_c"])
        df["fbt_mean"] = df["fbt_mean"].fillna(df["fbt_mean_c"])
        df["fbt_min"] = df["fbt_min"].fillna(df["fbt_min_c"])
        df = df.drop(columns=["lt_mean_c", "fbt_mean_c", "fbt_min_c"])
        for col in ["weather_source", "window_direction", "window_risk_level", "a8_direction", "a93_direction"]:
            if col in df.columns:
                df[col] = df[col].fillna("none").replace("", "none").astype(str)
        return df

    return merge_conditional


def derive_tagestyp(df: pd.DataFrame) -> pd.Series:
    weekday = df["weekday"].astype(int)
    public_holiday = pd.to_numeric(df.get("is_public_holiday_DE_BY", 0), errors="coerce").fillna(0)
    school_holiday = pd.to_numeric(df.get("is_school_holiday_DE_BY", 0), errors="coerce").fillna(0)
    return pd.Series(
        np.where((weekday == 7) | (public_holiday == 1), "s", np.where(school_holiday == 1, "u", "w")),
        index=df.index,
    )


def build_profiles(train_df: pd.DataFrame) -> dict:
    train = train_df[train_df["kfz_h"].notna()]
    return {
        "prof_kfz_shd": train.groupby(["site_id", "hour", "weekday"])["kfz_h"].median().rename("prof_kfz_shd"),
        "prof_kfz_sht": train.groupby(["site_id", "hour", "tagestyp"])["kfz_h"].median().rename("prof_kfz_sht"),
        "prof_kfz_shm": train.groupby(["site_id", "hour", "month"])["kfz_h"].median().rename("prof_kfz_shm"),
        "prof_kfz_p90": train.groupby(["site_id", "hour", "weekday"])["kfz_h"].quantile(PROFILE_KFZ_P90).rename("prof_kfz_p90"),
        "prof_lkw_shd": train[train["lkw_ratio"].notna()].groupby(["site_id", "hour", "weekday"])["lkw_ratio"].median().rename("prof_lkw_shd"),
        "prof_v_shd": train[train["v_kfz"].notna()].groupby(["site_id", "hour", "weekday"])["v_kfz"].median().rename("prof_v_shd"),
        "prof_v_p85": train[train["v_kfz"].notna()].groupby(["site_id", "hour"])["v_kfz"].quantile(PROFILE_V_P85).rename("prof_v_p85"),
        "prof_kfz_shs": train.groupby(["site_id", "hour", "season"])["kfz_h"].median().rename("prof_kfz_shs"),
        "prof_lkw_sht": train[train["lkw_ratio"].notna()].groupby(["site_id", "hour", "tagestyp"])["lkw_ratio"].median().rename("prof_lkw_sht"),
        "prof_v_sht": train[train["v_kfz"].notna()].groupby(["site_id", "hour", "tagestyp"])["v_kfz"].median().rename("prof_v_sht"),
    }


PROFILE_KEYS = {
    "prof_kfz_shd": ["site_id", "hour", "weekday"],
    "prof_kfz_sht": ["site_id", "hour", "tagestyp"],
    "prof_kfz_shm": ["site_id", "hour", "month"],
    "prof_kfz_p90": ["site_id", "hour", "weekday"],
    "prof_lkw_shd": ["site_id", "hour", "weekday"],
    "prof_v_shd": ["site_id", "hour", "weekday"],
    "prof_v_p85": ["site_id", "hour"],
    "prof_kfz_shs": ["site_id", "hour", "season"],
    "prof_lkw_sht": ["site_id", "hour", "tagestyp"],
    "prof_v_sht": ["site_id", "hour", "tagestyp"],
}


def apply_profiles(df: pd.DataFrame, profiles: dict) -> pd.DataFrame:
    df = df.copy()
    for name, keys in PROFILE_KEYS.items():
        df = df.merge(profiles[name], on=keys, how="left")
    for name in PROFILE_KEYS:
        if df[name].isna().any():
            df[name] = df[name].fillna(df[name].median())
    return df


CALENDAR = [
    "hour",
    "weekday",
    "month",
    "doy",
    "week_of_year",
    "is_weekend",
    "is_friday",
    "is_saturday",
    "is_sunday",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
    "doy_sin",
    "doy_cos",
]
STATIC_NUM = ["bab_km", "longitude", "latitude"]
STATIC_CAT = ["site_id", "road", "direction", "site_name", "tagestyp", "season"]
HOLIDAY = [
    "is_school_holiday_DE_BY",
    "is_school_holiday_AT_SB",
    "is_school_holiday_AT_TI",
    "is_public_holiday_DE_BY",
    "is_public_holiday_AT_SB",
    "is_public_holiday_AT_TI",
    "school_holiday_count",
    "public_holiday_count",
    "is_holiday_start",
    "is_holiday_end",
    "in_traffic_window",
    "days_to_holiday_start",
    "days_since_holiday_end",
    "total_holiday_overlap",
    "is_departure_wave_day",
    "is_return_wave_day",
]
HOLIDAY_CAT = ["window_direction", "window_risk_level", "a8_direction", "a93_direction"]
WEATHER = ["w_precip", "w_snow", "w_lowvis", "w_tmin", "w_tmax", "w_ice"]
WEATHER_CAT = ["weather_source"]
TEMP = ["lt_mean", "fbt_mean", "fbt_min"]
CONSTRUCTION = [
    "has_a8_construction",
    "has_a93_construction",
    "a8_construction_count",
    "a93_construction_count",
    "has_2_plus_0",
    "two_plus_0_count",
    "max_closed_lanes",
    "sum_closed_lanes",
    "has_target_bbox_construction",
]
EVENTS = [
    "has_special_event",
    "active_event_count",
    "max_impact_level",
    "impact_score",
    "affects_a8_ost",
    "affects_a93_sued",
    "has_munich_event",
    "has_salzburg_event",
    "has_rosenheim_event",
    "has_kufstein_event",
    "has_confirmed_event",
    "has_estimated_event",
]
PROF_KFZ = ["prof_kfz_shd", "prof_kfz_sht", "prof_kfz_shm", "prof_kfz_p90", "prof_kfz_shs"]
PROF_LKW = ["prof_lkw_shd", "prof_lkw_sht"]
PROF_V = ["prof_v_shd", "prof_v_p85", "prof_v_sht"]
COND = HOLIDAY + HOLIDAY_CAT + WEATHER + WEATHER_CAT + TEMP + CONSTRUCTION + EVENTS
CAT_FEATURES = STATIC_CAT + HOLIDAY_CAT + WEATHER_CAT
FEATURES_KFZ = CALENDAR + STATIC_NUM + STATIC_CAT + PROF_KFZ + COND

GROUPS = {
    "Historical Traffic Baseline": PROF_KFZ + PROF_LKW + PROF_V,
    "Date and Time Pattern": CALENDAR,
    "Holiday Effect": HOLIDAY + HOLIDAY_CAT,
    "Road Segment and Detector Attributes": STATIC_NUM + STATIC_CAT,
    "Weather and Temperature": WEATHER + WEATHER_CAT + TEMP,
    "Special Events": EVENTS,
    "Construction Impact": CONSTRUCTION,
}


def build_future_grid(dates, traffic, merge_conditional, profiles, hours=range(24)) -> pd.DataFrame:
    site_meta = (
        traffic.groupby("site_id")[["road", "direction", "site_name", "bab_km", "longitude", "latitude"]]
        .first()
        .reset_index()
    )
    dates = pd.to_datetime(list(dates)).normalize()
    grid = pd.MultiIndex.from_product(
        [site_meta["site_id"], dates, list(hours)], names=["site_id", "date", "hour"]
    ).to_frame(index=False)
    grid = grid.merge(site_meta, on="site_id", how="left")
    grid["weekday"] = grid["date"].dt.weekday + 1
    grid["ts"] = grid["date"] + pd.to_timedelta(grid["hour"], unit="h")
    grid["tagestyp"] = "w"
    grid = add_calendar(grid)
    grid = merge_conditional(grid)
    grid["tagestyp"] = derive_tagestyp(grid)
    grid = apply_profiles(grid, profiles)
    return grid


def month_chunks(start: pd.Timestamp, end: pd.Timestamp):
    for period in pd.period_range(start=start, end=end, freq="M"):
        chunk_start = max(start.normalize(), period.start_time.normalize())
        chunk_end = min(end.normalize(), period.end_time.normalize())
        yield pd.date_range(chunk_start, chunk_end, freq="D")


def format_reason(row: pd.Series) -> str:
    values = {label: row[label] for label in GROUPS}
    total = sum(values.values())
    if total <= 0:
        return ""
    parts = []
    for label, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
        pct = round(value / total * 100, 1)
        if pct != 0.0:
            parts.append(f"{label}: {pct:.1f}%")
    return "；".join(parts)


def main():
    print("Loading feature sources...", flush=True)
    traffic, temp_hourly, temp_climo, holiday, weather, construction, events = load_feature_sources()
    merge_conditional = make_merge_conditional(temp_hourly, temp_climo, holiday, weather, construction, events)

    print("Rebuilding notebook profiles...", flush=True)
    base = merge_conditional(add_calendar(traffic))
    train_df = base[base["ts"] <= TRAIN_END].copy()
    profiles = build_profiles(train_df)

    print("Loading kfz_h MultiQuantile model...", flush=True)
    model = CatBoostRegressor()
    model.load_model(str(KFZ_MODEL_PATH))

    daily = pd.read_csv(DAILY_FORECAST_PATH)
    if "原因" in daily.columns:
        daily = daily.drop(columns=["原因"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    start = daily["date"].min()
    end = daily["date"].max()

    feature_index = {feature: index for index, feature in enumerate(FEATURES_KFZ)}
    group_feature_indexes = {
        label: [feature_index[feature] for feature in features if feature in feature_index]
        for label, features in GROUPS.items()
    }
    cat_features = [col for col in CAT_FEATURES if col in FEATURES_KFZ]
    daily_keys = ["site_id", "road", "direction", "site_name", "date"]
    reason_parts = []

    chunks = list(month_chunks(start, end))
    for chunk_index, dates in enumerate(chunks, start=1):
        print(f"[{chunk_index:02d}/{len(chunks)}] SHAP {dates.min().date()} ~ {dates.max().date()}", flush=True)
        grid = build_future_grid(dates, traffic, merge_conditional, profiles)
        x = grid[FEATURES_KFZ].copy()
        for col in cat_features:
            x[col] = x[col].astype(str)
        pool = Pool(x, cat_features=cat_features)
        shap_raw = model.get_feature_importance(
            pool,
            type="ShapValues",
            shap_calc_type="Approximate",
            thread_count=-1,
            verbose=False,
        )
        shap = shap_raw[:, 1, :-1] if shap_raw.ndim == 3 else shap_raw[:, :-1]

        grouped = grid[daily_keys].copy()
        for label, indexes in group_feature_indexes.items():
            grouped[label] = np.abs(shap[:, indexes]).sum(axis=1) if indexes else 0.0
        grouped = grouped.groupby(daily_keys, as_index=False)[list(GROUPS)].sum()
        reason_parts.append(grouped)

    reason_df = pd.concat(reason_parts, ignore_index=True)
    reason_df["原因"] = reason_df.apply(format_reason, axis=1)

    enriched = daily.merge(reason_df[daily_keys + ["原因"]], on=daily_keys, how="left", validate="one_to_one")
    if enriched["原因"].isna().any():
        missing = enriched.loc[enriched["原因"].isna(), daily_keys].head(10)
        raise ValueError(f"Missing reasons for {enriched['原因'].isna().sum()} rows. Examples:\n{missing}")

    enriched["date"] = enriched["date"].dt.strftime("%Y-%m-%d")
    output_columns = [col for col in daily.columns if col != "原因"] + ["原因"]
    enriched = enriched[output_columns]
    enriched.to_csv(DAILY_FORECAST_PATH, index=False)

    print(f"Wrote {len(enriched):,} rows with 原因 -> {DAILY_FORECAST_PATH}", flush=True)
    print(enriched[["site_id", "date", "原因"]].head(5).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()