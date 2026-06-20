"""
Forecast Agent (预测Agent)
负责调用CatBoost/TFT模型进行交通流量预测
"""
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

from ..base import BaseAgent, AgentType, AgentResponse
from ..config import AgentConfig, default_config

try:
    from catboost import CatBoostRegressor
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class ForecastAgent(BaseAgent):
    """
    预测Agent
    - 调用CatBoost模型获取P10/P50/P90流量预测
    - 返回预测结果和置信区间
    """

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.FORECAST, config or default_config)
        self.models: Dict[str, Dict[str, Any]] = {}
        self._feature_columns: List[str] = []

    async def initialize(self) -> bool:
        """加载预测模型"""
        if not HAS_CATBOOST:
            print("Warning: CatBoost not installed. Using mock predictions.")
            self._initialized = True
            return True

        models_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..",
            self.config.model.models_dir
        )

        try:
            # 加载各目标的分位数模型
            for target in self.config.model.targets:
                target_dir = os.path.join(models_dir, target)
                if os.path.exists(target_dir):
                    self.models[target] = {}
                    for q in ["p10", "p50", "p90"]:
                        model_path = os.path.join(target_dir, f"{q}.cbm")
                        if os.path.exists(model_path):
                            model = CatBoostRegressor()
                            model.load_model(model_path)
                            self.models[target][q] = model

            self._initialized = True
            return True
        except Exception as e:
            print(f"Error loading models: {e}")
            self._initialized = False
            return False

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        处理预测请求

        Request格式:
        {
            "date": "2026-07-15",
            "site_id": "A8_Rosenheim",
            "direction": "east",  # east/west
            "hours": [8, 9, 10, 11, 12]  # 可选，默认全天24小时
        }

        Response:
        {
            "predictions": [
                {"hour": 8, "p10": 1200, "p50": 1500, "p90": 1800, "congestion_level": "moderate"},
                ...
            ],
            "peak_hour": 10,
            "daily_summary": {...}
        }
        """
        try:
            date_str = request.get("date", datetime.now().strftime("%Y-%m-%d"))
            site_id = request.get("site_id", "A8_001")
            direction = request.get("direction", "east")
            hours = request.get("hours", list(range(24)))

            # 构建特征
            features = self._build_features(date_str, site_id, direction, hours)

            # 进行预测
            predictions = await self._predict(features, hours)

            # 计算峰值小时
            peak_hour = self._find_peak_hour(predictions)

            # 生成日度汇总
            daily_summary = self._generate_daily_summary(predictions)

            return AgentResponse(
                success=True,
                data={
                    "predictions": predictions,
                    "peak_hour": peak_hour,
                    "daily_summary": daily_summary,
                    "site_id": site_id,
                    "date": date_str,
                    "direction": direction,
                },
                message="Forecast completed successfully",
                agent_type=self.agent_type,
                confidence=0.85
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Forecast error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0
            )

    def get_capabilities(self) -> List[str]:
        return [
            "hourly_traffic_forecast",
            "quantile_prediction",
            "peak_hour_identification",
            "congestion_level_assessment",
        ]

    def _build_features(
        self,
        date_str: str,
        site_id: str,
        direction: str,
        hours: List[int]
    ) -> List[Dict[str, Any]]:
        """构建预测特征"""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        features = []

        for hour in hours:
            feat = {
                "site_id": site_id,
                "direction": direction,
                "year": date.year,
                "month": date.month,
                "day": date.day,
                "hour": hour,
                "weekday": date.weekday(),
                "is_weekend": 1 if date.weekday() >= 5 else 0,
                # 周期性编码
                "hour_sin": np.sin(2 * np.pi * hour / 24),
                "hour_cos": np.cos(2 * np.pi * hour / 24),
                "month_sin": np.sin(2 * np.pi * date.month / 12),
                "month_cos": np.cos(2 * np.pi * date.month / 12),
                "weekday_sin": np.sin(2 * np.pi * date.weekday() / 7),
                "weekday_cos": np.cos(2 * np.pi * date.weekday() / 7),
            }
            features.append(feat)

        return features

    async def _predict(
        self,
        features: List[Dict[str, Any]],
        hours: List[int]
    ) -> List[Dict[str, Any]]:
        """执行预测"""
        predictions = []

        for i, (feat, hour) in enumerate(zip(features, hours)):
            if self.models and "kfz_h" in self.models:
                # 使用真实模型预测
                # TODO: 转换特征为模型输入格式
                p10 = 1000 + hour * 50  # 占位
                p50 = 1200 + hour * 60
                p90 = 1500 + hour * 70
            else:
                # Mock预测（基于时间的简单模式）
                base = 800
                # 早高峰 7-9, 晚高峰 16-18
                if 7 <= hour <= 9:
                    multiplier = 1.8
                elif 16 <= hour <= 18:
                    multiplier = 2.0
                elif 10 <= hour <= 15:
                    multiplier = 1.4
                elif 5 <= hour <= 6:
                    multiplier = 0.8
                else:
                    multiplier = 0.5

                # 周末调整
                if feat.get("is_weekend"):
                    if 9 <= hour <= 14:
                        multiplier *= 1.3  # 周末出游高峰
                    else:
                        multiplier *= 0.8

                p50 = int(base * multiplier)
                p10 = int(p50 * 0.75)
                p90 = int(p50 * 1.35)

            # 计算拥堵等级
            congestion = self._get_congestion_level(p50)

            predictions.append({
                "hour": hour,
                "p10": p10,
                "p50": p50,
                "p90": p90,
                "congestion_level": congestion,
                "confidence": 0.85 - abs(hour - 12) * 0.01  # 中午预测更准
            })

        return predictions

    def _get_congestion_level(self, traffic_volume: int) -> str:
        """根据流量判断拥堵等级"""
        if traffic_volume < 800:
            return "smooth"
        elif traffic_volume < 1200:
            return "light"
        elif traffic_volume < 1600:
            return "moderate"
        elif traffic_volume < 2000:
            return "heavy"
        else:
            return "critical"

    def _find_peak_hour(self, predictions: List[Dict[str, Any]]) -> int:
        """找出峰值小时"""
        if not predictions:
            return 12
        return max(predictions, key=lambda x: x["p50"])["hour"]

    def _generate_daily_summary(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成日度汇总"""
        if not predictions:
            return {}

        p50_values = [p["p50"] for p in predictions]
        congestion_counts = {}
        for p in predictions:
            level = p["congestion_level"]
            congestion_counts[level] = congestion_counts.get(level, 0) + 1

        # 确定全天主要拥堵等级
        main_congestion = max(congestion_counts, key=congestion_counts.get)

        return {
            "total_volume": sum(p50_values),
            "avg_hourly_volume": int(np.mean(p50_values)),
            "max_hourly_volume": max(p50_values),
            "min_hourly_volume": min(p50_values),
            "main_congestion_level": main_congestion,
            "congestion_hours": {
                "smooth": congestion_counts.get("smooth", 0),
                "light": congestion_counts.get("light", 0),
                "moderate": congestion_counts.get("moderate", 0),
                "heavy": congestion_counts.get("heavy", 0),
                "critical": congestion_counts.get("critical", 0),
            }
        }
