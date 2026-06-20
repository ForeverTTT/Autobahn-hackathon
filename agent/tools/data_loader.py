from __future__ import annotations

"""
数据加载工具
渐进式加载预测数据，不一次性读取全部
"""
import csv
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# 数据目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data_autobahn"


class PredictionLoader:
    """
    预测数据加载器（渐进式）

    特点：
    - 按日期分块读取，不一次性加载全部数据
    - LRU 缓存最近查询的日期
    - 支持 CSV 和 Parquet 格式
    """

    def __init__(self, file_path: str = None):
        self.file_path = file_path or str(DATA_DIR / "forecast_2026_2029.csv")
        self.daily_file_path = str(DATA_DIR / "forecast_2026_2029_daily.csv")
        self.factor_file_path = str(DATA_DIR / "factor_attribution_daily.csv")
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_order: List[str] = []
        self._cache_max_days = 7
        self._daily_df: Optional[pd.DataFrame] = None
        self._factor_df: Optional[pd.DataFrame] = None
        self._daily_records: Optional[List[Dict[str, Any]]] = None
        self._factor_records: Optional[List[Dict[str, Any]]] = None
        self._initialized = False

    def _init_file(self) -> bool:
        """初始化文件路径"""
        if self._initialized:
            return True

        if not HAS_PANDAS:
            return False

        path = Path(self.file_path)
        if not path.exists():
            # 尝试其他格式
            for ext in [".csv", ".parquet"]:
                alt_path = path.with_suffix(ext)
                if alt_path.exists():
                    self.file_path = str(alt_path)
                    self._initialized = True
                    return True
            return False

        self._initialized = True
        return True

    def _load_date(self, date: str) -> Optional[pd.DataFrame]:
        """加载指定日期的数据"""
        if date in self._cache:
            # LRU: 移到最后
            self._cache_order.remove(date)
            self._cache_order.append(date)
            return self._cache[date]

        if not self._init_file():
            return None

        try:
            path = Path(self.file_path)

            if path.suffix == ".parquet":
                df = pd.read_parquet(path, filters=[("date", "==", date)])
            else:
                # CSV: 分块读取
                chunks = []
                for chunk in pd.read_csv(path, chunksize=10000):
                    chunk["date"] = chunk["date"].astype(str)
                    filtered = chunk[chunk["date"] == date]
                    if len(filtered) > 0:
                        chunks.append(filtered)
                df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

            # 字段映射
            if "sv_h_pred" in df.columns:
                df["sv_h_p50"] = df["sv_h_pred"]
            if "v_kfz_pred" in df.columns:
                df["v_kfz_p50"] = df["v_kfz_pred"]

            # 缓存
            self._cache[date] = df
            self._cache_order.append(date)

            # LRU 淘汰
            while len(self._cache_order) > self._cache_max_days:
                oldest = self._cache_order.pop(0)
                del self._cache[oldest]

            return df

        except Exception as e:
            print(f"Error loading data for {date}: {e}")
            return None

    def _query_hourly_records_csv(
        self,
        date: str,
        road: str = None,
        site_id: str = None,
        hours: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """使用标准库按需扫描小时级 CSV，供无 pandas 环境使用。"""
        path = Path(self.file_path)
        if not path.exists():
            alt_path = path.with_suffix(".csv")
            if alt_path.exists():
                path = alt_path
            else:
                return []

        if path.suffix != ".csv":
            return []

        hour_set = set(hours) if hours else None
        records = []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for record in csv.DictReader(f):
                    if record.get("date") != date:
                        continue
                    if road and record.get("road") != road:
                        continue
                    if site_id and record.get("site_id") != site_id:
                        continue
                    if hour_set is not None:
                        try:
                            if int(record.get("hour", -1)) not in hour_set:
                                continue
                        except ValueError:
                            continue
                    records.append(record)
        except Exception as e:
            print(f"Error scanning hourly forecast CSV: {e}")
            return []

        return sorted(records, key=lambda x: int(x.get("hour", 0)))

    def query(
        self,
        date: str,
        road: str = None,
        site_id: str = None,
        hours: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        查询预测数据

        Args:
            date: 日期 YYYY-MM-DD
            road: 高速公路 A8/A93
            site_id: 站点ID
            hours: 小时列表

        Returns:
            预测记录列表
        """
        df = self._load_date(date)

        if df is None:
            return self._query_hourly_records_csv(date, road, site_id, hours)

        if len(df) == 0:
            return []

        mask = pd.Series([True] * len(df))

        if road:
            mask &= df["road"] == road
        if site_id:
            mask &= df["site_id"] == site_id
        if hours:
            mask &= df["hour"].isin(hours)

        result = df[mask].sort_values("hour")

        # 如果没有精确匹配 site_id，取第一个站点
        if site_id and len(result) == 0 and road:
            road_df = df[df["road"] == road]
            if len(road_df) > 0:
                first_site = road_df["site_id"].iloc[0]
                mask = (df["site_id"] == first_site)
                if hours:
                    mask &= df["hour"].isin(hours)
                result = df[mask].sort_values("hour")

        return result.to_dict("records")

    def _load_daily_forecast(self) -> Optional[pd.DataFrame]:
        """加载日级预测表。"""
        if self._daily_df is not None:
            return self._daily_df

        if not HAS_PANDAS:
            return None

        path = Path(self.daily_file_path)
        if not path.exists():
            return None

        try:
            df = pd.read_csv(path)
            df["date"] = df["date"].astype(str)
            self._daily_df = df
            return self._daily_df
        except Exception as e:
            print(f"Error loading daily forecast: {e}")
            return None

    def _load_daily_forecast_records(self) -> List[Dict[str, Any]]:
        """使用标准库加载日级预测表，供无 pandas 环境使用。"""
        if self._daily_records is not None:
            return self._daily_records

        path = Path(self.daily_file_path)
        if not path.exists():
            self._daily_records = []
            return self._daily_records

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                self._daily_records = list(csv.DictReader(f))
        except Exception as e:
            print(f"Error loading daily forecast records: {e}")
            self._daily_records = []

        return self._daily_records

    def _load_factor_attribution(self) -> Optional[pd.DataFrame]:
        """加载日级因子归因表。"""
        if self._factor_df is not None:
            return self._factor_df

        if not HAS_PANDAS:
            return None

        path = Path(self.factor_file_path)
        if not path.exists():
            return None

        try:
            df = pd.read_csv(path)
            df["date"] = df["date"].astype(str)
            self._factor_df = df
            return self._factor_df
        except Exception as e:
            print(f"Error loading factor attribution: {e}")
            return None

    def _load_factor_attribution_records(self) -> List[Dict[str, Any]]:
        """使用标准库加载日级因子归因表，供无 pandas 环境使用。"""
        if self._factor_records is not None:
            return self._factor_records

        path = Path(self.factor_file_path)
        if not path.exists():
            self._factor_records = []
            return self._factor_records

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                self._factor_records = list(csv.DictReader(f))
        except Exception as e:
            print(f"Error loading factor attribution records: {e}")
            self._factor_records = []

        return self._factor_records

    def query_daily(
        self,
        start_date: str,
        end_date: str = None,
        road: str = None,
        site_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        查询日级预测数据。

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD，默认等于 start_date
            road: 高速公路 A8/A93
            site_id: 站点ID

        Returns:
            日级预测记录列表
        """
        df = self._load_daily_forecast()
        if df is None:
            records = self._load_daily_forecast_records()
            end_date = end_date or start_date
            result = [
                record for record in records
                if start_date <= record.get("date", "") <= end_date
                and (not road or record.get("road") == road)
                and (not site_id or record.get("site_id") == site_id)
            ]
            return sorted(result, key=lambda x: (x.get("date", ""), x.get("site_id", "")))

        if len(df) == 0:
            return []

        end_date = end_date or start_date
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)

        if road:
            mask &= df["road"] == road
        if site_id:
            mask &= df["site_id"] == site_id

        result = df[mask].sort_values(["date", "site_id"])
        return result.to_dict("records")

    def query_factor_attribution(
        self,
        start_date: str,
        end_date: str = None,
        road: str = None,
        site_id: str = None,
    ) -> List[Dict[str, Any]]:
        """查询日级因子归因数据。"""
        df = self._load_factor_attribution()
        if df is None:
            records = self._load_factor_attribution_records()
            end_date = end_date or start_date
            result = [
                record for record in records
                if start_date <= record.get("date", "") <= end_date
                and (not road or record.get("road") == road)
                and (not site_id or record.get("site_id") == site_id)
            ]
            return sorted(result, key=lambda x: (x.get("date", ""), x.get("site_id", "")))

        if len(df) == 0:
            return []

        end_date = end_date or start_date
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)

        if road:
            mask &= df["road"] == road
        if site_id:
            mask &= df["site_id"] == site_id

        result = df[mask].sort_values(["date", "site_id"])
        return result.to_dict("records")

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_order.clear()
        self._daily_df = None
        self._factor_df = None
        self._daily_records = None
        self._factor_records = None


class ContextLoader:
    """
    上下文数据加载器
    加载 data_autobahn 中的外部因素数据
    """

    def __init__(self):
        self._records_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _load_semicolon_records(self, filename: str) -> List[Dict[str, Any]]:
        """加载分号分隔 CSV，并跳过中文说明行。"""
        if filename in self._records_cache:
            return self._records_cache[filename]

        path = DATA_DIR / filename
        if not path.exists():
            self._records_cache[filename] = []
            return []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                records = [
                    row for row in csv.DictReader(f, delimiter=";")
                    if not self._is_description_row(row)
                ]
            self._records_cache[filename] = records
            return records
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            self._records_cache[filename] = []
            return []

    def _is_description_row(self, row: Dict[str, Any]) -> bool:
        """识别数据文件中的中文字段说明行。"""
        date_value = row.get("date")
        road_value = row.get("road")
        t_start = row.get("t_start")
        return date_value == "日期" or road_value == "高速路编号" or t_start == "原始时刻"

    def _filter_by_date_range(
        self,
        records: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return [
            row for row in records
            if start_date <= str(row.get("date", "")) <= end_date
        ]

    def _filter_road_context(
        self,
        records: List[Dict[str, Any]],
        road: str = None,
    ) -> List[Dict[str, Any]]:
        if not road:
            return records

        road_lower = road.lower()
        return [
            row for row in records
            if row.get("road") == road
            or row.get(f"has_{road_lower}_construction") == "1"
            or row.get(f"{road_lower}_construction_count", "0") not in {"", "0", "0.0"}
            or row.get(f"affects_{road_lower}_ost") == "1"
            or row.get(f"affects_{road_lower}_sued") == "1"
            or row.get(f"{road_lower}_event_count", "0") not in {"", "0", "0.0"}
            or road in str(row.get("active_roads", ""))
        ]

    def query_weather(self, start_date: str, end_date: str = None) -> List[Dict[str, Any]]:
        """查询天气日级数据。"""
        end_date = end_date or start_date
        records = self._load_semicolon_records("合并表格，weather日级.csv")
        return self._filter_by_date_range(records, start_date, end_date)

    def query_holiday(self, start_date: str, end_date: str = None) -> List[Dict[str, Any]]:
        """查询假期日级数据。"""
        end_date = end_date or start_date
        records = self._load_semicolon_records("合并表格，holiday日级.csv")
        return self._filter_by_date_range(records, start_date, end_date)

    def query_events(self, start_date: str, end_date: str = None, road: str = None) -> List[Dict[str, Any]]:
        """查询活动日级数据。"""
        end_date = end_date or start_date
        records = self._load_semicolon_records("合并表格，special_events日级.csv")
        rows = self._filter_by_date_range(records, start_date, end_date)
        return self._filter_road_context(rows, road)

    def query_construction(self, start_date: str, end_date: str = None, road: str = None) -> List[Dict[str, Any]]:
        """查询施工日级数据。"""
        end_date = end_date or start_date
        records = self._load_semicolon_records("合并表格，construction日级.csv")
        rows = self._filter_by_date_range(records, start_date, end_date)
        return self._filter_road_context(rows, road)

    def query_temperature_road(
        self,
        start_date: str,
        end_date: str = None,
        hours: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """查询并按小时聚合气温/路温数据。"""
        end_date = end_date or start_date
        hour_set = set(hours) if hours else None
        path = DATA_DIR / "合并表格，时间，气温，路温.csv"
        if not path.exists():
            return []

        buckets: Dict[tuple, Dict[str, Any]] = {}
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    ts = str(row.get("t_start", ""))
                    if len(ts) < 13:
                        continue
                    date = ts[:10]
                    if not (start_date <= date <= end_date):
                        continue
                    try:
                        hour = int(ts[11:13])
                    except ValueError:
                        continue
                    if hour_set is not None and hour not in hour_set:
                        continue

                    key = (date, hour)
                    bucket = buckets.setdefault(key, {"date": date, "hour": hour, "lt": [], "fbt": []})
                    lt = self._to_float(row.get("lt"))
                    fbt = self._to_float(row.get("fbt"))
                    if lt is not None:
                        bucket["lt"].append(lt)
                    if fbt is not None:
                        bucket["fbt"].append(fbt)
        except Exception as e:
            print(f"Error scanning temperature/road temperature CSV: {e}")
            return []

        result = []
        for bucket in buckets.values():
            lt_values = bucket.pop("lt")
            fbt_values = bucket.pop("fbt")
            bucket["air_temp_c"] = round(sum(lt_values) / len(lt_values), 1) if lt_values else None
            bucket["road_temp_c"] = round(sum(fbt_values) / len(fbt_values), 1) if fbt_values else None
            result.append(bucket)

        result = sorted(result, key=lambda x: (x["date"], x["hour"]))
        if result:
            return result

        return self._query_temperature_road_historical_reference(start_date, end_date, hours)

    def _query_temperature_road_historical_reference(
        self,
        start_date: str,
        end_date: str,
        hours: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """没有精确气温/路温时，按同月同日聚合历史参考。"""
        target_dates = self._date_range(start_date, end_date)
        target_by_suffix = {date[5:]: date for date in target_dates}
        hour_set = set(hours) if hours else None
        path = DATA_DIR / "合并表格，时间，气温，路温.csv"
        buckets: Dict[tuple, Dict[str, Any]] = {}

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    ts = str(row.get("t_start", ""))
                    if len(ts) < 13:
                        continue
                    source_date = ts[:10]
                    target_date = target_by_suffix.get(source_date[5:])
                    if not target_date:
                        continue
                    try:
                        hour = int(ts[11:13])
                    except ValueError:
                        continue
                    if hour_set is not None and hour not in hour_set:
                        continue

                    key = (target_date, hour)
                    bucket = buckets.setdefault(
                        key,
                        {
                            "date": target_date,
                            "hour": hour,
                            "historical_reference": True,
                            "source_dates": set(),
                            "lt": [],
                            "fbt": [],
                        },
                    )
                    bucket["source_dates"].add(source_date)
                    lt = self._to_float(row.get("lt"))
                    fbt = self._to_float(row.get("fbt"))
                    if lt is not None:
                        bucket["lt"].append(lt)
                    if fbt is not None:
                        bucket["fbt"].append(fbt)
        except Exception as e:
            print(f"Error scanning historical temperature/road temperature CSV: {e}")
            return []

        result = []
        for bucket in buckets.values():
            lt_values = bucket.pop("lt")
            fbt_values = bucket.pop("fbt")
            source_dates = sorted(bucket.pop("source_dates"))
            bucket["source_dates"] = source_dates
            bucket["air_temp_c"] = round(sum(lt_values) / len(lt_values), 1) if lt_values else None
            bucket["road_temp_c"] = round(sum(fbt_values) / len(fbt_values), 1) if fbt_values else None
            result.append(bucket)

        return sorted(result, key=lambda x: (x["date"], x["hour"]))

    def query_hourly_traffic(
        self,
        start_date: str,
        end_date: str = None,
        road: str = None,
        hours: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """查询历史小时交通流量。"""
        end_date = end_date or start_date
        hour_set = set(hours) if hours else None
        path = DATA_DIR / "合并表格，小时交通流量.csv"
        if not path.exists():
            return []

        rows = []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    if self._is_description_row(row):
                        continue
                    date = self._parse_german_date(row.get("datum"))
                    if not date or not (start_date <= date <= end_date):
                        continue
                    if road and row.get("road") != road:
                        continue
                    try:
                        hour = int(str(row.get("t_start", "00:00:00"))[:2])
                    except ValueError:
                        continue
                    if hour_set is not None and hour not in hour_set:
                        continue

                    rows.append({
                        "date": date,
                        "hour": hour,
                        "road": row.get("road"),
                        "direction": row.get("direction"),
                        "site_name": row.get("site_name"),
                        "kfz_h": self._to_float(row.get("kfz_h")),
                        "sv_h": self._to_float(row.get("sv_h")),
                        "v_kfz": self._to_float(row.get("v_kfz")),
                    })
        except Exception as e:
            print(f"Error scanning hourly traffic CSV: {e}")
            return []

        rows = sorted(rows, key=lambda x: (x["date"], x["hour"], x.get("site_name") or ""))
        if rows:
            return rows

        return self._query_hourly_traffic_historical_reference(start_date, end_date, road, hours)

    def _query_hourly_traffic_historical_reference(
        self,
        start_date: str,
        end_date: str,
        road: str = None,
        hours: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """没有精确小时交通时，按同月同日使用历史参考。"""
        target_dates = self._date_range(start_date, end_date)
        target_by_suffix = {date[5:]: date for date in target_dates}
        hour_set = set(hours) if hours else None
        path = DATA_DIR / "合并表格，小时交通流量.csv"
        rows = []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    if self._is_description_row(row):
                        continue
                    source_date = self._parse_german_date(row.get("datum"))
                    if not source_date:
                        continue
                    target_date = target_by_suffix.get(source_date[5:])
                    if not target_date:
                        continue
                    if road and row.get("road") != road:
                        continue
                    try:
                        hour = int(str(row.get("t_start", "00:00:00"))[:2])
                    except ValueError:
                        continue
                    if hour_set is not None and hour not in hour_set:
                        continue

                    rows.append({
                        "date": target_date,
                        "source_date": source_date,
                        "historical_reference": True,
                        "hour": hour,
                        "road": row.get("road"),
                        "direction": row.get("direction"),
                        "site_name": row.get("site_name"),
                        "kfz_h": self._to_float(row.get("kfz_h")),
                        "sv_h": self._to_float(row.get("sv_h")),
                        "v_kfz": self._to_float(row.get("v_kfz")),
                    })
        except Exception as e:
            print(f"Error scanning historical hourly traffic CSV: {e}")
            return []

        return sorted(rows, key=lambda x: (x["date"], x["hour"], x.get("site_name") or ""))

    def get_context_range(
        self,
        start_date: str,
        end_date: str = None,
        road: str = None,
        hours: List[int] = None,
    ) -> Dict[str, Any]:
        """汇总指定时间段内所有非预测上下文数据。"""
        end_date = end_date or start_date
        return {
            "weather": self.query_weather(start_date, end_date),
            "holiday": self.query_holiday(start_date, end_date),
            "events": self.query_events(start_date, end_date, road),
            "construction": self.query_construction(start_date, end_date, road),
            "temperature_road": self.query_temperature_road(start_date, end_date, hours),
            "hourly_traffic": self.query_hourly_traffic(start_date, end_date, road, hours),
        }

    def _parse_german_date(self, value: Any) -> Optional[str]:
        try:
            return datetime.strptime(str(value), "%d.%m.%Y").strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            return None

    def _date_range(self, start_date: str, end_date: str) -> List[str]:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end - start).days
        return [
            (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(days + 1)
        ]

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            if value in {None, ""}:
                return None
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def get_weather(self, date: str) -> Dict[str, Any]:
        """获取天气数据"""
        rows = self.query_weather(date, date)
        return rows[0] if rows else {}

    def get_holiday(self, date: str) -> Dict[str, Any]:
        """获取假期数据"""
        rows = self.query_holiday(date, date)
        if rows:
            return rows[0]
        return {"is_holiday": False, "is_school_holiday": False}

    def get_events(self, date: str) -> List[Dict[str, Any]]:
        """获取活动数据"""
        return self.query_events(date, date)

    def get_construction(self, date: str, road: str = None) -> List[Dict[str, Any]]:
        """获取施工数据"""
        return self.query_construction(date, date, road)


# 全局实例
prediction_loader = PredictionLoader()
context_loader = ContextLoader()
