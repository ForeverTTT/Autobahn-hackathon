"""
ForecastAgent - 预测Agent
读取预测数据，计算拥堵分数
"""
from typing import Any, Dict, List
from datetime import datetime

from .base import BaseAgent
from ..models import (
    AgentRequest, AgentResponse,
    HourlyPrediction, DailyForecast, CongestionLevel
)
from ..tools import (
    prediction_loader,
    calculate_congestion,
    TrafficInput, RoadInput, ExternalInput,
    score_to_stress_index
)


class ForecastAgent(BaseAgent):
    """
    预测Agent

    职责:
    - 从 forecast_2026_2029.csv 读取预测数据
    - 计算每小时拥堵分数
    - 返回日度汇总
    """

    @property
    def name(self) -> str:
        return "ForecastAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理预测请求"""
        try:
            date = request.date
            road = request.road
            hours = request.hours

            # 查询预测数据
            records = prediction_loader.query(
                date=date,
                road=road,
                site_id=request.site_id,
                hours=hours
            )

            if not records:
                # 无数据时使用模拟
                predictions = self._generate_mock(date, road, hours)
                data_source = "mock"
            else:
                predictions = self._process_records(records, date)
                data_source = "forecast_csv"

            # 汇总
            peak_hour = max(predictions, key=lambda x: x.congestion_score).hour
            avg_score = sum(p.congestion_score for p in predictions) / len(predictions)
            total_volume = sum(int(p.kfz_h_p50) for p in predictions)

            forecast = DailyForecast(
                date=date,
                road=road,
                site_id=request.site_id or f"{road}_default",
                predictions=predictions,
                peak_hour=peak_hour,
                avg_congestion_score=round(avg_score, 1),
                total_volume=total_volume
            )

            return self._success({
                "forecast": forecast,
                "data_source": data_source,
            })

        except Exception as e:
            return self._error(f"Forecast error: {str(e)}")

    def _process_records(
        self,
        records: List[Dict[str, Any]],
        date: str
    ) -> List[HourlyPrediction]:
        """处理预测记录"""
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []

        for record in records:
            hour = record["hour"]
            kfz_h = record.get("kfz_h_p50", record.get("kfz_h", 1000))
            sv_h = record.get("sv_h_p50", record.get("sv_h_pred", kfz_h * 0.1))
            v_kfz = record.get("v_kfz_p50", record.get("v_kfz_pred", 120))

            # 计算拥堵分数
            traffic = TrafficInput(kfz_h=kfz_h, sv_h=sv_h, v_kfz=v_kfz)
            road_input = RoadInput(capacity=4000, is_bottleneck=False)
            external = ExternalInput(
                is_weekend=is_weekend,
                is_peak_hour=(7 <= hour <= 9) or (16 <= hour <= 18),
                is_holiday=record.get("is_holiday", False),
                is_school_holiday=record.get("is_school_holiday", False),
            )

            result = calculate_congestion(traffic, road_input, external)

            predictions.append(HourlyPrediction(
                hour=hour,
                kfz_h_p10=record.get("kfz_h_p10", kfz_h * 0.75),
                kfz_h_p50=kfz_h,
                kfz_h_p90=record.get("kfz_h_p90", kfz_h * 1.35),
                sv_h=sv_h,
                v_kfz=v_kfz,
                congestion_score=result.total_score,
                congestion_level=result.level,
            ))

        return sorted(predictions, key=lambda x: x.hour)

    def _generate_mock(
        self,
        date: str,
        road: str,
        hours: List[int]
    ) -> List[HourlyPrediction]:
        """生成模拟数据"""
        import numpy as np

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []

        for hour in hours:
            # 基于时段的流量模式
            if 7 <= hour <= 9:
                base = 1600 if not is_weekend else 1000
            elif 16 <= hour <= 18:
                base = 1800 if not is_weekend else 1200
            elif 10 <= hour <= 15:
                base = 1200
            else:
                base = 600

            # 添加随机波动
            kfz_h = base + np.random.randint(-200, 200)
            sv_h = kfz_h * np.random.uniform(0.08, 0.15)
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
