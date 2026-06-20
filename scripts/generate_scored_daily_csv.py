"""
生成带拥堵评分的日级 CSV 文件
读取 forecast_2026_daily.csv，计算每天的 congestion_score 和 level
"""
import pandas as pd
import numpy as np
from pathlib import Path

# 路径
DATA_DIR = Path(__file__).parent.parent / "data_autobahn"
FORECAST_FILE = DATA_DIR / "forecast_2026_daily.csv"
HOLIDAY_FILE = DATA_DIR / "合并表格，holiday日级.csv"
WEATHER_FILE = DATA_DIR / "合并表格，weather日级.csv"
EVENT_FILE = DATA_DIR / "合并表格，special_events日级.csv"
CONSTRUCTION_FILE = DATA_DIR / "合并表格，construction日级.csv"
OUTPUT_FILE = DATA_DIR / "scored_traffic_2026_2029_daily.csv"


def load_external_factors():
    """加载外部因素数据"""
    print("Loading external factors...")

    # 假期数据
    holiday_df = pd.read_csv(HOLIDAY_FILE, sep=';', dtype=str)
    holiday_df = holiday_df.iloc[1:]  # 跳过中文表头
    holiday_df['date'] = pd.to_datetime(holiday_df['date'])
    holiday_df['is_weekend'] = holiday_df['is_weekend'].astype(int)
    holiday_df['is_public_holiday'] = holiday_df['is_public_holiday_DE_BY'].fillna('0').astype(int)
    holiday_df['is_school_holiday'] = holiday_df['is_school_holiday_DE_BY'].fillna('0').astype(int)
    holiday_df['is_holiday_start'] = holiday_df['is_holiday_start'].fillna('0').astype(int)
    holiday_df['is_holiday_end'] = holiday_df['is_holiday_end'].fillna('0').astype(int)

    # 天气数据
    weather_df = pd.read_csv(WEATHER_FILE, sep=';', dtype=str)
    weather_df = weather_df.iloc[1:]
    weather_df['date'] = pd.to_datetime(weather_df['date'])
    weather_df['precip_mm'] = pd.to_numeric(weather_df['precip_mm_mean'], errors='coerce').fillna(0)
    weather_df['low_vis_hours'] = pd.to_numeric(weather_df['low_vis_hours_mean'], errors='coerce').fillna(0)
    weather_df['ice_risk_prob'] = pd.to_numeric(weather_df['ice_risk_prob'], errors='coerce').fillna(0)

    # 特殊活动数据
    event_df = pd.read_csv(EVENT_FILE, sep=';', dtype=str)
    event_df = event_df.iloc[1:]
    event_df['date'] = pd.to_datetime(event_df['date'])
    event_df['has_special_event'] = event_df['has_special_event'].fillna('0').astype(int)
    event_df['impact_score'] = pd.to_numeric(event_df['impact_score'], errors='coerce').fillna(0)

    # 施工数据
    construction_df = pd.read_csv(CONSTRUCTION_FILE, sep=';', dtype=str)
    construction_df = construction_df.iloc[1:]
    construction_df['date'] = pd.to_datetime(construction_df['date'])
    construction_df['has_construction'] = construction_df['has_construction'].fillna('0').astype(int)
    construction_df['has_a8_construction'] = construction_df['has_a8_construction'].fillna('0').astype(int)
    construction_df['has_a93_construction'] = construction_df['has_a93_construction'].fillna('0').astype(int)

    return holiday_df, weather_df, event_df, construction_df


def calculate_daily_congestion_score(row, holiday_lookup, weather_lookup, event_lookup, construction_lookup):
    """计算日级拥堵分数"""

    # 日级交通数据 (需要换算成小时平均)
    daily_kfz = float(row['kfz_h_p50'])
    daily_sv = float(row['sv_h_pred'])
    v_kfz = float(row['v_kfz_pred'])
    date = row['date']
    road = row['road']

    # 换算为小时平均 (假设主要交通集中在 16 小时内)
    hourly_kfz = daily_kfz / 16
    hourly_sv = daily_sv / 16

    # 道路参数
    capacity = 4000
    free_flow_speed = 130

    # === 1. 流量因子 (25%) ===
    volume_ratio = hourly_kfz / capacity
    traffic_score = min(100, volume_ratio * 100)

    # === 2. 速度因子 (30%) ===
    speed_ratio = v_kfz / free_flow_speed
    speed_score = max(0, (1 - speed_ratio) * 100)

    # === 3. 容量因子 (25%) ===
    capacity_score = 0
    if daily_kfz > 0:
        heavy_ratio = daily_sv / daily_kfz
        capacity_score = heavy_ratio * 50
    capacity_score = min(100, capacity_score)

    # === 4. 外部因子 (20%) ===
    external_score = 0

    # 获取外部因素
    holiday_info = holiday_lookup.get(date, {})
    weather_info = weather_lookup.get(date, {})
    event_info = event_lookup.get(date, {})
    construction_info = construction_lookup.get(date, {})

    # 周末
    is_weekend = holiday_info.get('is_weekend', 0)
    if is_weekend:
        external_score += 10

    # 假期
    is_holiday = holiday_info.get('is_public_holiday', 0)
    is_school_holiday = holiday_info.get('is_school_holiday', 0)
    is_holiday_start = holiday_info.get('is_holiday_start', 0)
    is_holiday_end = holiday_info.get('is_holiday_end', 0)

    if is_holiday:
        external_score += 25
    if is_school_holiday:
        external_score += 15
    if is_holiday_start:
        external_score += 10
    if is_holiday_end:
        external_score += 10

    # 天气
    precip = weather_info.get('precip_mm', 0)
    low_vis = weather_info.get('low_vis_hours', 0)
    ice_risk = weather_info.get('ice_risk_prob', 0)

    weather_impact = 0
    if precip > 10:
        weather_impact += 0.3
    elif precip > 5:
        weather_impact += 0.2
    elif precip > 1:
        weather_impact += 0.1

    if low_vis > 4:
        weather_impact += 0.2
    elif low_vis > 2:
        weather_impact += 0.1

    if ice_risk > 0.5:
        weather_impact += 0.3
    elif ice_risk > 0.2:
        weather_impact += 0.1

    external_score += weather_impact * 30

    # 特殊活动
    has_event = event_info.get('has_special_event', 0)
    event_impact = event_info.get('impact_score', 0)
    if has_event:
        external_score += event_impact * 10

    # 施工
    has_construction = construction_info.get('has_construction', 0)
    if road == 'A8' and construction_info.get('has_a8_construction', 0):
        external_score += 15
    elif road == 'A93' and construction_info.get('has_a93_construction', 0):
        external_score += 15

    external_score = min(100, external_score)

    # === 加权总分 ===
    total_score = (
        0.25 * traffic_score +
        0.30 * speed_score +
        0.25 * capacity_score +
        0.20 * external_score
    )

    # === 等级 ===
    if total_score < 20:
        level = "smooth"
    elif total_score < 40:
        level = "light"
    elif total_score < 60:
        level = "moderate"
    elif total_score < 80:
        level = "heavy"
    else:
        level = "critical"

    return round(total_score, 1), level, is_weekend, is_holiday, is_school_holiday, weather_impact > 0, has_event, has_construction


def main():
    print("=" * 60)
    print("生成带拥堵评分的日级 CSV 文件")
    print("=" * 60)

    # 加载外部因素
    holiday_df, weather_df, event_df, construction_df = load_external_factors()

    # 构建查找表
    print("Building lookup tables...")
    holiday_lookup = {}
    for _, row in holiday_df.iterrows():
        date = row['date']
        holiday_lookup[date] = {
            'is_weekend': row['is_weekend'],
            'is_public_holiday': row['is_public_holiday'],
            'is_school_holiday': row['is_school_holiday'],
            'is_holiday_start': row['is_holiday_start'],
            'is_holiday_end': row['is_holiday_end'],
        }

    weather_lookup = {}
    for _, row in weather_df.iterrows():
        date = row['date']
        weather_lookup[date] = {
            'precip_mm': row['precip_mm'],
            'low_vis_hours': row['low_vis_hours'],
            'ice_risk_prob': row['ice_risk_prob'],
        }

    event_lookup = {}
    for _, row in event_df.iterrows():
        date = row['date']
        event_lookup[date] = {
            'has_special_event': row['has_special_event'],
            'impact_score': row['impact_score'],
        }

    construction_lookup = {}
    for _, row in construction_df.iterrows():
        date = row['date']
        construction_lookup[date] = {
            'has_construction': row['has_construction'],
            'has_a8_construction': row['has_a8_construction'],
            'has_a93_construction': row['has_a93_construction'],
        }

    # 加载预测数据
    print(f"Loading forecast data from {FORECAST_FILE}...")
    forecast_df = pd.read_csv(FORECAST_FILE)
    forecast_df['date'] = pd.to_datetime(forecast_df['date'])
    print(f"  Total rows: {len(forecast_df):,}")

    # 计算评分
    print("Calculating congestion scores...")
    results = []
    total = len(forecast_df)

    for i, (idx, row) in enumerate(forecast_df.iterrows()):
        if i % 5000 == 0:
            print(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%)")

        score, level, is_weekend, is_holiday, is_school_holiday, has_weather, has_event, has_construction = \
            calculate_daily_congestion_score(row, holiday_lookup, weather_lookup, event_lookup, construction_lookup)

        results.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'site_id': row['site_id'],
            'road': row['road'],
            'direction': row['direction'],
            'site_name': row['site_name'],
            'kfz_h_p10': round(float(row['kfz_h_p10']), 1),
            'kfz_h_p50': round(float(row['kfz_h_p50']), 1),
            'kfz_h_p90': round(float(row['kfz_h_p90']), 1),
            'sv_h_pred': round(float(row['sv_h_pred']), 1),
            'v_kfz_pred': round(float(row['v_kfz_pred']), 1),
            'congestion_score': score,
            'congestion_level': level,
            'is_weekend': int(is_weekend),
            'is_holiday': int(is_holiday),
            'is_school_holiday': int(is_school_holiday),
            'has_weather_impact': int(has_weather),
            'has_event': int(has_event),
            'has_construction': int(has_construction),
            'reasons': row.get('原因', ''),
        })

    # 保存结果
    print(f"\nSaving to {OUTPUT_FILE}...")
    result_df = pd.DataFrame(results)
    result_df.to_csv(OUTPUT_FILE, index=False)

    # 统计信息
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)
    print(f"总行数: {len(result_df):,}")
    print(f"\n拥堵等级分布:")
    print(result_df['congestion_level'].value_counts().sort_index())
    print(f"\n平均拥堵分数: {result_df['congestion_score'].mean():.1f}")
    print(f"最大拥堵分数: {result_df['congestion_score'].max():.1f}")
    print(f"最小拥堵分数: {result_df['congestion_score'].min():.1f}")

    print(f"\n✅ 完成! 输出文件: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
