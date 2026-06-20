"""
Data Loader for Agent System
加载预测数据和外部因素数据

数据格式说明：
1. data_autobahn/forecast_2026_2029.csv - 模型预测结果（2026-2029）
2. data_autobahn/合并表格，holiday日级.csv - 假期数据
3. data_autobahn/合并表格，weather日级.csv - 天气数据
4. data_autobahn/合并表格，special_events日级.csv - 活动数据
5. data_autobahn/合并表格，construction日级.csv - 施工数据
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ============ 数据路径配置 ============

# 项目根目录
PROJECT_ROOT = Path(__file__).parents[2]

# 数据目录
DATA_DIR = PROJECT_ROOT / "data_autobahn"
DEFAULT_PREDICTIONS_FILE = DATA_DIR / "forecast_2026_2029.csv"


def read_data_autobahn_csv(path: Path, **kwargs) -> "pd.DataFrame":
    """Read data_autobahn CSV files, skipping the Chinese description row."""
    sep = kwargs.pop("sep", ";")
    skiprows = kwargs.pop("skiprows", [1])
    return pd.read_csv(path, sep=sep, skiprows=skiprows, **kwargs)


def is_missing(value: Any) -> bool:
    return value is None or (HAS_PANDAS and pd.isna(value))


def safe_number(value: Any, default: float = 0.0) -> float:
    if is_missing(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    return int(safe_number(value, default))


def safe_text(value: Any, default: str = "") -> str:
    if is_missing(value):
        return default
    return str(value)


# ============ 预测数据格式定义 ============

"""
forecast_2026_2029.csv 格式：

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 YYYY-MM-DD |
| hour | int | 小时 0-23 |
| site_id | string | 站点ID，如 A8_Mch_MQB25 |
| road | string | 高速公路 A8/A93 |
| direction | string | 方向 Mch/Sbg/Ro/Kff |
| kfz_h_p10 | float | 流量预测 P10 |
| kfz_h_p50 | float | 流量预测 P50 (中位数) |
| kfz_h_p90 | float | 流量预测 P90 |
| sv_h_p50 | float | 大车流量预测 |
| v_kfz_p50 | float | 平均车速预测 |
| tagestyp | string | 日类型 w/s/u |
| is_holiday | bool | 是否假期 |
| is_school_holiday | bool | 是否学校假期 |

示例:
date,hour,site_id,road,direction,kfz_h_p10,kfz_h_p50,kfz_h_p90,sv_h_p50,v_kfz_p50,tagestyp,is_holiday,is_school_holiday
2026-01-01,0,A8_Mch_MQB25,A8,Mch,180,240,320,20,135.5,s,true,false
2026-01-01,1,A8_Mch_MQB25,A8,Mch,150,200,270,15,138.0,s,true,false
...
"""


@dataclass
class PredictionRecord:
    """单条预测记录"""
    date: str
    hour: int
    site_id: str
    road: str
    direction: str
    kfz_h_p10: float
    kfz_h_p50: float
    kfz_h_p90: float
    sv_h_p50: float
    v_kfz_p50: float
    tagestyp: str = "w"
    is_holiday: bool = False
    is_school_holiday: bool = False


class PredictionDataLoader:
    """
    预测数据加载器（渐进式加载）
    按需从预测文件中查询数据，不一次性加载全部数据到内存
    """

    def __init__(self, predictions_path: str = None):
        """
        初始化

        Args:
            predictions_path: 预测文件路径 (.csv)
        """
        self.predictions_path = predictions_path or str(DEFAULT_PREDICTIONS_FILE)
        self._file_path: Optional[Path] = None
        self._file_format: Optional[str] = None
        self._initialized = False

        # 缓存：只缓存最近查询的日期数据
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_max_days = 7  # 最多缓存7天的数据
        self._cache_order: List[str] = []  # LRU 顺序

    def _init_file(self) -> bool:
        """初始化文件路径（不加载数据）"""
        if self._initialized:
            return self._file_path is not None

        if not HAS_PANDAS:
            print("Warning: pandas not installed")
            return False

        path = Path(self.predictions_path)

        if not path.exists():
            print(f"Warning: Predictions file not found: {path}")
            self._initialized = True
            return False

        self._file_path = path
        self._file_format = path.suffix
        self._initialized = True
        return True

    def _load_date(self, date: str) -> Optional[pd.DataFrame]:
        """
        渐进式加载：只加载指定日期的数据

        Args:
            date: 日期 YYYY-MM-DD

        Returns:
            该日期的 DataFrame，如果无数据返回 None
        """
        # 检查缓存
        if date in self._cache:
            # 更新 LRU 顺序
            self._cache_order.remove(date)
            self._cache_order.append(date)
            return self._cache[date]

        if not self._init_file():
            return None

        try:
            if self._file_format == ".csv":
                # CSV 需要分块读取过滤
                chunks = []
                for chunk in pd.read_csv(self._file_path, chunksize=10000):
                    chunk["date"] = chunk["date"].astype(str)
                    filtered = chunk[chunk["date"] == date]
                    if len(filtered) > 0:
                        chunks.append(filtered)

                if chunks:
                    df = pd.concat(chunks, ignore_index=True)
                else:
                    df = pd.DataFrame()
            else:
                return None

            df = self._normalize_prediction_columns(df)

            # 添加到缓存
            self._cache[date] = df
            self._cache_order.append(date)

            # LRU 清理：超过最大缓存天数时删除最旧的
            while len(self._cache_order) > self._cache_max_days:
                oldest = self._cache_order.pop(0)
                del self._cache[oldest]

            return df

        except Exception as e:
            print(f"Error loading predictions for {date}: {e}")
            return None

    def _normalize_prediction_columns(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Normalize forecast CSV columns to the legacy agent schema."""
        if df is None or len(df) == 0:
            return df

        df = df.copy()

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # Current forecast CSV uses *_pred names; older agent code expects *_p50.
        aliases = {
            "sv_h_pred": "sv_h_p50",
            "v_kfz_pred": "v_kfz_p50",
        }
        for source, target in aliases.items():
            if source in df.columns and target not in df.columns:
                df[target] = df[source]

        # Optional model-training flags are not part of the final forecast CSV.
        defaults = {
            "tagestyp": "w",
            "is_holiday": False,
            "is_school_holiday": False,
        }
        for column, value in defaults.items():
            if column not in df.columns:
                df[column] = value

        return df

    def query(
        self,
        date: str,
        site_id: str = None,
        road: str = None,
        direction: str = None,
        hours: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        查询预测数据（渐进式加载）

        Args:
            date: 日期 YYYY-MM-DD
            site_id: 站点ID（可选）
            road: 高速公路（可选）
            direction: 方向（可选）
            hours: 小时列表（可选）

        Returns:
            预测记录列表
        """
        # 只加载指定日期的数据
        df = self._load_date(date)

        if df is None or len(df) == 0:
            return []

        # 过滤条件
        mask = pd.Series([True] * len(df))

        if site_id:
            mask &= df["site_id"] == site_id
        if road:
            mask &= df["road"] == road
        if direction:
            mask &= df["direction"] == direction
        if hours:
            mask &= df["hour"].isin(hours)

        result_df = df[mask].sort_values("hour")

        return result_df.to_dict("records")

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_order.clear()

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "cached_dates": list(self._cache.keys()),
            "cache_size": len(self._cache),
            "max_cache_days": self._cache_max_days,
        }

    def query_range(
        self,
        start_date: str,
        end_date: str,
        site_id: str = None,
        road: str = None
    ) -> List[Dict[str, Any]]:
        """
        查询日期范围内的预测（渐进式加载每一天）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            site_id: 站点ID
            road: 高速公路

        Returns:
            预测记录列表
        """
        from datetime import datetime, timedelta

        results = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            records = self.query(date_str, site_id=site_id, road=road)
            results.extend(records)
            current += timedelta(days=1)

        return results

    def get_daily_summary(
        self,
        date: str,
        site_id: str = None,
        road: str = None
    ) -> Dict[str, Any]:
        """
        获取日度汇总

        Args:
            date: 日期
            site_id: 站点ID
            road: 高速公路

        Returns:
            日度汇总数据
        """
        records = self.query(date, site_id=site_id, road=road)

        if not records:
            return {}

        kfz_values = [r["kfz_h_p50"] for r in records]
        speed_values = [r.get("v_kfz_p50", r.get("v_kfz_pred", 0)) for r in records]

        # 找出高峰小时
        peak_record = max(records, key=lambda x: x["kfz_h_p50"])

        return {
            "date": date,
            "site_id": site_id,
            "road": road,
            "total_volume": sum(kfz_values),
            "avg_hourly_volume": sum(kfz_values) / len(kfz_values),
            "max_hourly_volume": max(kfz_values),
            "min_hourly_volume": min(kfz_values),
            "avg_speed": sum(speed_values) / len(speed_values),
            "peak_hour": peak_record["hour"],
            "peak_volume": peak_record["kfz_h_p50"],
            "is_holiday": records[0].get("is_holiday", False),
            "is_school_holiday": records[0].get("is_school_holiday", False),
            "tagestyp": records[0].get("tagestyp", "w"),
        }

    def get_available_sites(self, sample_date: str = "2026-01-01") -> List[str]:
        """
        获取可用的站点列表（从样本日期推断）

        Args:
            sample_date: 用于采样的日期
        """
        records = self.query(sample_date)
        if not records:
            return []
        return list(set(r["site_id"] for r in records))

    def get_date_range(self) -> Tuple[str, str]:
        """
        获取数据的日期范围

        注意：对于 CSV 文件，这需要扫描整个文件
        建议在应用层面配置日期范围，而不是每次从文件读取
        """
        if not self._init_file():
            return ("", "")

        try:
            min_date, max_date = None, None
            for chunk in pd.read_csv(self._file_path, usecols=["date"], chunksize=50000):
                chunk_min = chunk["date"].min()
                chunk_max = chunk["date"].max()
                if min_date is None or chunk_min < min_date:
                    min_date = chunk_min
                if max_date is None or chunk_max > max_date:
                    max_date = chunk_max
            return (str(min_date), str(max_date))
        except Exception as e:
            print(f"Error getting date range: {e}")
            return ("", "")


class ExternalDataLoader:
    """
    外部数据加载器
    加载假期、天气、活动、施工等数据
    """

    def __init__(self):
        self._holidays_df: Optional[pd.DataFrame] = None
        self._weather_df: Optional[pd.DataFrame] = None
        self._events_df: Optional[pd.DataFrame] = None
        self._construction_df: Optional[pd.DataFrame] = None

    def load_holidays(self) -> bool:
        """加载假期数据"""
        if not HAS_PANDAS:
            return False

        path = DATA_DIR / "合并表格，holiday日级.csv"
        if path.exists():
            try:
                self._holidays_df = read_data_autobahn_csv(path)
                return True
            except Exception as e:
                print(f"Error loading holidays: {e}")
        return False

    def load_weather(self) -> bool:
        """加载天气数据"""
        if not HAS_PANDAS:
            return False

        path = DATA_DIR / "合并表格，weather日级.csv"
        if path.exists():
            try:
                self._weather_df = read_data_autobahn_csv(path)
                return True
            except Exception as e:
                print(f"Error loading weather: {e}")

        return False

    def load_events(self) -> bool:
        """加载活动数据"""
        if not HAS_PANDAS:
            return False

        path = DATA_DIR / "合并表格，special_events日级.csv"
        if path.exists():
            try:
                self._events_df = read_data_autobahn_csv(path)
                return True
            except Exception as e:
                print(f"Error loading events: {e}")
        return False

    def load_construction(self) -> bool:
        """加载施工数据"""
        if not HAS_PANDAS:
            return False

        path = DATA_DIR / "合并表格，construction日级.csv"
        if path.exists():
            try:
                self._construction_df = read_data_autobahn_csv(path)
                return True
            except Exception as e:
                print(f"Error loading construction: {e}")
        return False

    def get_holiday_info(self, date: str) -> Dict[str, Any]:
        """获取指定日期的假期信息"""
        if self._holidays_df is None:
            self.load_holidays()

        if self._holidays_df is None:
            return {"is_holiday": False}

        rows = self._holidays_df[self._holidays_df["date"].astype(str) == date]
        if len(rows) == 0:
            return {"is_holiday": False, "is_school_holiday": False, "holiday_name": None}

        row = rows.iloc[0].to_dict()
        school_count = safe_int(row.get("school_holiday_count"))
        public_count = safe_int(row.get("public_holiday_count"))
        holiday_names = [
            safe_text(row.get("public_names_DE_BY")),
            safe_text(row.get("public_names_AT_SB")),
            safe_text(row.get("public_names_AT_TI")),
        ]
        return {
            "is_holiday": public_count > 0,
            "is_school_holiday": school_count > 0,
            "holiday_name": next((name for name in holiday_names if name), None),
            "school_holiday_count": school_count,
            "public_holiday_count": public_count,
            "traffic_window": row.get("in_traffic_window"),
            "window_risk_level": row.get("window_risk_level"),
        }

    def get_weather_info(self, date: str) -> Dict[str, Any]:
        """获取指定日期的天气信息"""
        if self._weather_df is None:
            self.load_weather()

        if self._weather_df is None:
            return {"weather": "unknown"}

        rows = self._weather_df[self._weather_df["date"].astype(str) == date]
        if len(rows) == 0:
            return {"weather": "unknown"}

        row = rows.iloc[0].to_dict()
        observed = safe_int(row.get("has_observed_weather")) > 0
        precip = safe_number(row.get("precip_mm" if observed else "precip_mm_mean"))
        snowfall = safe_number(row.get("snowfall_mm")) if observed else 0.0
        low_vis = safe_number(row.get("low_vis_hours" if observed else "low_vis_hours_mean"))
        t_min = safe_number(row.get("t_min_c" if observed else "t_min_c_mean"))
        t_max = safe_number(row.get("t_max_c" if observed else "t_max_c_mean"))
        has_ice_risk = safe_int(row.get("has_ice_risk")) > 0 if observed else safe_number(row.get("ice_risk_prob")) > 0.25
        return {
            "weather": row.get("weather_source", "unknown"),
            "precip_mm": precip,
            "snowfall_mm": snowfall,
            "low_vis_hours": low_vis,
            "t_min_c": t_min,
            "t_max_c": t_max,
            "has_ice_risk": has_ice_risk,
            "raw": row,
        }

    def get_events(self, date: str, road: str = None) -> List[Dict[str, Any]]:
        """获取指定日期的活动"""
        if self._events_df is None:
            self.load_events()

        if self._events_df is None:
            return []

        rows = self._events_df[self._events_df["date"].astype(str) == date]
        if road == "A8" and "affects_a8_ost" in self._events_df.columns:
            rows = rows[pd.to_numeric(rows["affects_a8_ost"], errors="coerce").fillna(0).astype(int) > 0]
        elif road == "A93" and "affects_a93_sued" in self._events_df.columns:
            rows = rows[pd.to_numeric(rows["affects_a93_sued"], errors="coerce").fillna(0).astype(int) > 0]
        return rows.to_dict("records")

    def get_construction(self, date: str, road: str = None) -> List[Dict[str, Any]]:
        """获取指定日期的施工信息"""
        if self._construction_df is None:
            self.load_construction()

        if self._construction_df is None:
            return []

        rows = self._construction_df[self._construction_df["date"].astype(str) == date]
        if road == "A8" and "has_a8_construction" in self._construction_df.columns:
            rows = rows[pd.to_numeric(rows["has_a8_construction"], errors="coerce").fillna(0).astype(int) > 0]
        elif road == "A93" and "has_a93_construction" in self._construction_df.columns:
            rows = rows[pd.to_numeric(rows["has_a93_construction"], errors="coerce").fillna(0).astype(int) > 0]
        return rows.to_dict("records")


# ============ 全局实例 ============

# 预测数据加载器
prediction_loader = PredictionDataLoader()

# 外部数据加载器
external_loader = ExternalDataLoader()


# ============ 便捷函数 ============

def get_forecast(
    date: str,
    site_id: str = None,
    road: str = "A8",
    hours: List[int] = None
) -> List[Dict[str, Any]]:
    """
    获取预测数据

    Args:
        date: 日期 YYYY-MM-DD
        site_id: 站点ID
        road: 高速公路
        hours: 小时列表

    Returns:
        预测记录列表
    """
    return prediction_loader.query(date, site_id=site_id, road=road, hours=hours)


def get_daily_forecast(date: str, road: str = "A8") -> Dict[str, Any]:
    """获取日度预测汇总"""
    return prediction_loader.get_daily_summary(date, road=road)


# ============ 生成示例预测数据 ============

def generate_sample_predictions(output_path: str = None) -> str:
    """
    生成示例预测数据文件

    用于测试，实际使用时应该用模型跑出来的真实预测

    Returns:
        输出文件路径
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required")

    import numpy as np
    from datetime import datetime, timedelta

    output_path = output_path or str(DATA_DIR / "sample_predictions.csv")

    # 确保目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 站点列表
    sites = [
        ("A8", "Mch", "MQB25_Mch_H"),
        ("A8", "Mch", "MQQ209_Mch_H"),
        ("A8", "Mch", "MQQ245_Mch_H"),
        ("A8", "Sbg", "MQQ213_Sbg_H"),
        ("A8", "Sbg", "MQQ245_Sbg_H"),
        ("A8", "Sbg", "MQQ37_Sbg_H"),
        ("A93", "Ro", "MQDZ_AD_Inntal_Ro"),
        ("A93", "Ro", "MQDZ_Kiefersfelden_Ro"),
        ("A93", "Ro", "MQ_Gletschergarten_Ro"),
        ("A93", "Kff", "MQDZ_AD_Inntal_Kff"),
        ("A93", "Kff", "MQDZ_Kiefersfelden_Kff"),
        ("A93", "Kff", "MQ_Gletschergarten_Kff"),
    ]

    # 生成 2026 年数据
    start_date = datetime(2026, 1, 1)
    days = 365

    records = []

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()
        is_weekend = weekday >= 5
        month = current_date.month

        # 确定日类型
        if is_weekend:
            tagestyp = "s"
        else:
            tagestyp = "w"

        # 检查假期（简化）
        is_holiday = date_str in [
            "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06",
            "2026-05-01", "2026-05-14", "2026-05-25", "2026-06-04",
            "2026-08-15", "2026-10-03", "2026-11-01", "2026-12-25", "2026-12-26"
        ]

        # 检查学校假期
        is_school_holiday = (
            (month == 7 and current_date.day >= 27) or
            (month == 8) or
            (month == 9 and current_date.day <= 7)
        )

        for road, direction, site_name in sites:
            site_id = f"{road}_{direction}_{site_name}"

            for hour in range(24):
                # 基础流量
                base = 600 if road == "A93" else 800

                # 时段系数
                if 7 <= hour <= 9:
                    mult = 1.8
                elif 16 <= hour <= 18:
                    mult = 2.0
                elif 10 <= hour <= 15:
                    mult = 1.4
                elif 5 <= hour <= 6:
                    mult = 0.8
                else:
                    mult = 0.5

                # 周末调整
                if is_weekend:
                    if 9 <= hour <= 14:
                        mult *= 1.3
                    else:
                        mult *= 0.8

                # 假期调整
                if is_holiday:
                    mult *= 1.4
                elif is_school_holiday:
                    mult *= 1.25

                # 季节调整
                if month in [6, 7, 8]:
                    mult *= 1.2
                elif month in [12, 1, 2]:
                    mult *= 1.1

                # 添加随机噪声
                noise = np.random.normal(1.0, 0.1)
                mult *= noise

                # 计算预测值
                kfz_p50 = int(base * mult)
                kfz_p10 = int(kfz_p50 * 0.75)
                kfz_p90 = int(kfz_p50 * 1.35)
                sv_h = int(kfz_p50 * np.random.uniform(0.08, 0.15))

                # 速度预测
                if kfz_p50 < 1000:
                    v_kfz = 120 + np.random.normal(0, 5)
                elif kfz_p50 < 1500:
                    v_kfz = 100 + np.random.normal(0, 8)
                elif kfz_p50 < 2000:
                    v_kfz = 80 + np.random.normal(0, 10)
                else:
                    v_kfz = max(40, 60 + np.random.normal(0, 10))

                records.append({
                    "date": date_str,
                    "hour": hour,
                    "site_id": site_id,
                    "road": road,
                    "direction": direction,
                    "kfz_h_p10": kfz_p10,
                    "kfz_h_p50": kfz_p50,
                    "kfz_h_p90": kfz_p90,
                    "sv_h_p50": sv_h,
                    "v_kfz_p50": round(v_kfz, 1),
                    "tagestyp": tagestyp,
                    "is_holiday": is_holiday,
                    "is_school_holiday": is_school_holiday,
                })

    # 保存
    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(records)} prediction records to {output_path}")

    return output_path


if __name__ == "__main__":
    # 生成示例数据
    print("Generating sample predictions...")
    output_path = generate_sample_predictions()
    print(f"Done! File saved to: {output_path}")

    # 测试加载
    print("\nTesting data loader...")
    loader = PredictionDataLoader(output_path)
    loader.load()

    # 测试查询
    records = loader.query("2026-07-15", road="A8", hours=[8, 9, 10])
    print(f"\nQuery results for 2026-07-15, A8, hours 8-10:")
    for r in records[:3]:
        print(f"  {r['site_id']} @ {r['hour']}:00 - {r['kfz_h_p50']} vehicles")

    # 测试日度汇总
    summary = loader.get_daily_summary("2026-07-15", road="A8")
    print(f"\nDaily summary for 2026-07-15:")
    print(f"  Peak hour: {summary['peak_hour']}:00")
    print(f"  Peak volume: {summary['peak_volume']}")
    print(f"  Avg hourly: {summary['avg_hourly_volume']:.0f}")
