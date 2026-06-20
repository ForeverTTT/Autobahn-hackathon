"""
ForecastAgent - 预测Agent
按请求粒度调度小时级预测表或日级预测表。
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .base import BaseAgent
from ..models import AgentRequest, AgentResponse, HourlyPrediction, DailyForecast
from ..tools import (
    prediction_loader,
    calculate_congestion,
    TrafficInput, RoadInput, ExternalInput,
)


class ForecastAgent(BaseAgent):
    """
    预测Agent

    两种调度模式:
    - hourly: Intent/Orchestrator 调用，使用 request.date + request.hours 查询小时级预测表
    - daily: 前端日历/趋势调用，使用 start_date/end_date 查询日级预测表和因子归因表
    """

    @property
    def name(self) -> str:
        return "ForecastAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理预测请求。"""
        try:
            if self._should_use_daily_forecast(request):
                return self._process_daily_request(request)
            return self._process_hourly_request(request)
        except Exception as e:
            return self._error(f"Forecast error: {str(e)}")

    def _should_use_daily_forecast(self, request: AgentRequest) -> bool:
        """判断是否使用日级预测表。"""
        granularity = (getattr(request, "granularity", "hourly") or "hourly").lower()
        if granularity == "daily":
            return True

        start_date = getattr(request, "start_date", None)
        end_date = getattr(request, "end_date", None)
        return bool(start_date and end_date and start_date != end_date)

    def _process_hourly_request(self, request: AgentRequest) -> AgentResponse:
        """Intent/Orchestrator 路径：按小时查询预测表。"""
        date = request.date
        road = request.road
        hours = request.hours or list(range(6, 22))

        records = prediction_loader.query(
            date=date,
            road=road,
            site_id=request.site_id,
            hours=hours,
        )

        if not records:
            predictions = self._generate_mock(date, road, hours)
            data_source = "mock"
        else:
            predictions = self._process_hourly_records(records, date)
            data_source = "forecast_csv"

        forecast = self._build_daily_summary(
            date=date,
            road=road,
            site_id=request.site_id or f"{road}_default",
            predictions=predictions,
        )

        return self._success({
            "mode": "hourly",
            "forecast": forecast,
            "data_source": data_source,
            "hours": hours,
        })

    def _process_daily_request(self, request: AgentRequest) -> AgentResponse:
        """前端路径：按日期范围查询日级预测和因子归因。"""
        start_date = request.start_date or request.date
        end_date = request.end_date or start_date
        road = request.road

        records = prediction_loader.query_daily(
            start_date=start_date,
            end_date=end_date,
            road=road,
            site_id=request.site_id,
        )

        factor_lookup: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
        if request.include_factors:
            factor_records = prediction_loader.query_factor_attribution(
                start_date=start_date,
                end_date=end_date,
                road=road,
                site_id=request.site_id,
            )
            factor_lookup = self._build_factor_lookup(factor_records)

        daily_forecasts = [
            self._process_daily_record(record, factor_lookup)
            for record in records
        ]

        return self._success({
            "mode": "daily",
            "daily_forecasts": daily_forecasts,
            "data_source": "forecast_daily_csv" if records else "daily_not_found",
            "start_date": start_date,
            "end_date": end_date,
            "road": road,
            "site_id": request.site_id,
            "include_factors": request.include_factors,
        })

    def _process_hourly_records(
        self,
        records: List[Dict[str, Any]],
        date: str,
    ) -> List[HourlyPrediction]:
        """处理小时级预测记录。"""
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []

        for record in records:
            hour = int(record["hour"])
            kfz_h = float(record.get("kfz_h_p50", record.get("kfz_h", 1000)))
            sv_h = float(record.get("sv_h_p50", record.get("sv_h_pred", kfz_h * 0.1)))
            v_kfz = float(record.get("v_kfz_p50", record.get("v_kfz_pred", 120)))

            traffic = TrafficInput(kfz_h=kfz_h, sv_h=sv_h, v_kfz=v_kfz)
            road_input = RoadInput(capacity=4000, is_bottleneck=False)
            external = ExternalInput(
                is_weekend=is_weekend,
                is_peak_hour=(7 <= hour <= 9) or (16 <= hour <= 18),
                is_holiday=self._as_bool(record.get("is_holiday", False)),
                is_school_holiday=self._as_bool(record.get("is_school_holiday", False)),
            )

            result = calculate_congestion(traffic, road_input, external)

            predictions.append(HourlyPrediction(
                hour=hour,
                kfz_h_p10=float(record.get("kfz_h_p10", kfz_h * 0.75)),
                kfz_h_p50=kfz_h,
                kfz_h_p90=float(record.get("kfz_h_p90", kfz_h * 1.35)),
                sv_h=sv_h,
                v_kfz=v_kfz,
                congestion_score=result.total_score,
                congestion_level=result.level,
            ))

        return sorted(predictions, key=lambda x: x.hour)

    def _build_daily_summary(
        self,
        date: str,
        road: str,
        site_id: str,
        predictions: List[HourlyPrediction],
    ) -> DailyForecast:
        """从小时级预测汇总出 DailyForecast。"""
        peak_hour = max(predictions, key=lambda x: x.congestion_score).hour
        avg_score = sum(p.congestion_score for p in predictions) / len(predictions)
        total_volume = sum(int(p.kfz_h_p50) for p in predictions)

        return DailyForecast(
            date=date,
            road=road,
            site_id=site_id,
            predictions=predictions,
            peak_hour=peak_hour,
            avg_congestion_score=round(avg_score, 1),
            total_volume=total_volume,
        )

    def _process_daily_record(
        self,
        record: Dict[str, Any],
        factor_lookup: Dict[Tuple[str, str, str, str], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """处理单条日级预测记录。"""
        date = str(record.get("date"))
        road = str(record.get("road", ""))
        site_id = str(record.get("site_id", ""))
        direction = str(record.get("direction", ""))
        factor_record = factor_lookup.get((date, road, site_id, direction), {})

        kfz_h_p50 = self._to_float(record.get("kfz_h_p50"), 0)
        sv_h_pred = self._to_float(record.get("sv_h_pred"), 0)
        v_kfz_pred = self._to_float(record.get("v_kfz_pred"), 120)
        congestion = self._calculate_daily_congestion(date, kfz_h_p50, sv_h_pred, v_kfz_pred)

        return {
            "date": date,
            "road": road,
            "direction": direction,
            "site_id": site_id,
            "site_name": record.get("site_name"),
            "kfz_h_p10": self._to_float(record.get("kfz_h_p10"), 0),
            "kfz_h_p50": kfz_h_p50,
            "kfz_h_p90": self._to_float(record.get("kfz_h_p90"), 0),
            "sv_h_pred": sv_h_pred,
            "v_kfz_pred": v_kfz_pred,
            "interval_width": self._to_float(record.get("interval_width"), 0),
            "relative_interval_width": self._to_float(record.get("relative_interval_width"), 0),
            "congestion_score": congestion.total_score,
            "congestion_level": congestion.level.value,
            "reasons": self._parse_reasons(record.get("原因", "")),
            "factor_codes": self._parse_factor_codes(factor_record.get("factors", "")),
        }

    def _calculate_daily_congestion(
        self,
        date: str,
        daily_kfz: float,
        daily_sv: float,
        v_kfz: float,
    ):
        """用日总量折算平均小时量，生成前端可排序的日级拥堵分数。"""
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        avg_hourly_kfz = daily_kfz / 24 if daily_kfz else 0
        avg_hourly_sv = daily_sv / 24 if daily_sv else 0

        traffic = TrafficInput(kfz_h=avg_hourly_kfz, sv_h=avg_hourly_sv, v_kfz=v_kfz)
        external = ExternalInput(is_weekend=date_obj.weekday() >= 5)
        return calculate_congestion(traffic, RoadInput(capacity=4000), external)

    def _build_factor_lookup(self, records: List[Dict[str, Any]]) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
        """构建因子归因查找表。"""
        lookup = {}
        for record in records:
            key = (
                str(record.get("date")),
                str(record.get("road", "")),
                str(record.get("site_id", "")),
                str(record.get("direction", "")),
            )
            lookup[key] = record
        return lookup

    def _parse_reasons(self, reason_text: Any) -> List[Dict[str, float]]:
        """解析日级预测表中的“原因”字段。"""
        if not reason_text:
            return []

        reasons = []
        for part in re.split(r"[;；]", str(reason_text)):
            if ":" not in part:
                continue
            name, value = part.split(":", 1)
            value_num = self._to_float(value.replace("%", "").replace("％", ""), 0)
            reasons.append({
                "name": name.strip(),
                "value": value_num,
            })
        return reasons

    def _parse_factor_codes(self, factors: Any) -> Dict[str, float]:
        """解析 factor_attribution_daily.csv 中的 TT:74;CA:13 格式。"""
        if not factors:
            return {}

        parsed = {}
        for part in str(factors).split(";"):
            if ":" not in part:
                continue
            code, value = part.split(":", 1)
            parsed[code.strip()] = self._to_float(value, 0)
        return parsed

    def _generate_mock(
        self,
        date: str,
        road: str,
        hours: List[int],
    ) -> List[HourlyPrediction]:
        """生成小时级模拟数据。"""
        import random

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []

        for hour in hours:
            if 7 <= hour <= 9:
                base = 1600 if not is_weekend else 1000
            elif 16 <= hour <= 18:
                base = 1800 if not is_weekend else 1200
            elif 10 <= hour <= 15:
                base = 1200
            else:
                base = 600

            kfz_h = base + random.randint(-200, 200)
            sv_h = kfz_h * random.uniform(0.08, 0.15)
            v_kfz = max(60, 130 - kfz_h * 0.03)

            traffic = TrafficInput(kfz_h=kfz_h, sv_h=sv_h, v_kfz=v_kfz)
            external = ExternalInput(
                is_weekend=is_weekend,
                is_peak_hour=(7 <= hour <= 9) or (16 <= hour <= 18),
            )
            result = calculate_congestion(traffic, external=external)

            predictions.append(HourlyPrediction(
                hour=hour,
                kfz_h_p10=int(kfz_h * 0.75),
                kfz_h_p50=kfz_h,
                kfz_h_p90=int(kfz_h * 1.35),
                sv_h=sv_h,
                v_kfz=round(v_kfz, 1),
                congestion_score=result.total_score,
                congestion_level=result.level,
            ))

        return predictions

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def _to_float(self, value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default