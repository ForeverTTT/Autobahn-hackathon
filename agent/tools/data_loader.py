from __future__ import annotations

"""
数据加载工具
渐进式加载预测数据，不一次性读取全部
"""
import csv
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

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
        self._weather_df: Optional[pd.DataFrame] = None
        self._holiday_df: Optional[pd.DataFrame] = None
        self._events_df: Optional[pd.DataFrame] = None
        self._construction_df: Optional[pd.DataFrame] = None

    def _load_csv(self, filename: str) -> Optional[pd.DataFrame]:
        """加载 CSV 文件"""
        if not HAS_PANDAS:
            return None

        path = DATA_DIR / filename
        if not path.exists():
            return None

        try:
            # 尝试不同分隔符
            for sep in [",", ";"]:
                try:
                    return pd.read_csv(path, sep=sep)
                except:
                    continue
            return None
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return None

    def get_weather(self, date: str) -> Dict[str, Any]:
        """获取天气数据"""
        if self._weather_df is None:
            self._weather_df = self._load_csv("合并表格，weather日级.csv")

        if self._weather_df is None:
            return {}

        try:
            row = self._weather_df[self._weather_df["date"].astype(str) == date]
            if len(row) > 0:
                return row.iloc[0].to_dict()
        except:
            pass

        return {}

    def get_holiday(self, date: str) -> Dict[str, Any]:
        """获取假期数据"""
        if self._holiday_df is None:
            self._holiday_df = self._load_csv("合并表格，holiday日级.csv")

        if self._holiday_df is None:
            return {"is_holiday": False, "is_school_holiday": False}

        try:
            row = self._holiday_df[self._holiday_df["date"].astype(str) == date]
            if len(row) > 0:
                return row.iloc[0].to_dict()
        except:
            pass

        return {"is_holiday": False, "is_school_holiday": False}

    def get_events(self, date: str) -> List[Dict[str, Any]]:
        """获取活动数据"""
        if self._events_df is None:
            self._events_df = self._load_csv("合并表格，special_events日级.csv")

        if self._events_df is None:
            return []

        try:
            rows = self._events_df[self._events_df["date"].astype(str) == date]
            return rows.to_dict("records")
        except:
            pass

        return []

    def get_construction(self, date: str, road: str = None) -> List[Dict[str, Any]]:
        """获取施工数据"""
        if self._construction_df is None:
            self._construction_df = self._load_csv("合并表格，construction日级.csv")

        if self._construction_df is None:
            return []

        try:
            mask = self._construction_df["date"].astype(str) == date
            if road:
                mask &= self._construction_df["road"] == road
            rows = self._construction_df[mask]
            return rows.to_dict("records")
        except:
            pass

        return []


# 全局实例
prediction_loader = PredictionLoader()
context_loader = ContextLoader()
