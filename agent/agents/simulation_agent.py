"""
Simulation Agent (模拟Agent)
负责What-if场景模拟和数字孪生
"""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import random

from ..base import BaseAgent, AgentType, AgentResponse
from ..config import AgentConfig, default_config


@dataclass
class SimulationScenario:
    """模拟场景定义"""
    name: str
    parameters: Dict[str, Any]
    description: str


class SimulationAgent(BaseAgent):
    """
    模拟Agent
    - What-if场景分析
    - 数字孪生模拟
    - 替代方案生成
    """

    # 路段基础容量 (车辆/小时)
    SEGMENT_CAPACITY = {
        "A8_München-Rosenheim": 4500,
        "A8_Rosenheim-Inntal": 4000,
        "A8_Inntal-Border": 3500,
        "A93_Rosenheim-Kiefersfelden": 3800,
        "A93_Kiefersfelden-Border": 3200,
    }

    # 天气对速度的影响系数
    WEATHER_SPEED_FACTOR = {
        "clear": 1.0,
        "cloudy": 0.98,
        "light_rain": 0.90,
        "heavy_rain": 0.75,
        "snow": 0.60,
        "ice": 0.50,
    }

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.SIMULATION, config or default_config)
        self._base_predictions: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """初始化模拟引擎"""
        self._initialized = True
        return True

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        执行What-if模拟

        Request格式:
        {
            "scenario_type": "weather_change" | "traffic_increase" | "accident" | "construction",
            "base_prediction": {...},  # 基准预测
            "parameters": {
                "weather": "heavy_rain",
                "traffic_multiplier": 1.2,
                ...
            },
            "date": "2026-07-15",
            "hours": [8, 9, 10, 11, 12]
        }
        """
        try:
            scenario_type = request.get("scenario_type", "custom")
            base_prediction = request.get("base_prediction", {})
            parameters = request.get("parameters", {})
            date_str = request.get("date", datetime.now().strftime("%Y-%m-%d"))
            hours = request.get("hours", list(range(24)))

            # 执行模拟
            simulation_result = await self._run_simulation(
                scenario_type, base_prediction, parameters, date_str, hours
            )

            # 生成替代方案
            alternatives = self._generate_alternatives(simulation_result, parameters)

            # 生成建议
            recommendations = self._generate_recommendations(simulation_result, alternatives)

            return AgentResponse(
                success=True,
                data={
                    "scenario_type": scenario_type,
                    "parameters": parameters,
                    "simulation_result": simulation_result,
                    "alternatives": alternatives,
                    "recommendations": recommendations,
                    "date": date_str,
                },
                message=f"Simulation completed for scenario: {scenario_type}",
                agent_type=self.agent_type,
                confidence=0.8
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Simulation error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0
            )

    def get_capabilities(self) -> List[str]:
        return [
            "what_if_simulation",
            "traffic_digital_twin",
            "scenario_comparison",
            "alternative_route_generation",
            "delay_estimation",
        ]

    async def _run_simulation(
        self,
        scenario_type: str,
        base_prediction: Dict[str, Any],
        parameters: Dict[str, Any],
        date_str: str,
        hours: List[int]
    ) -> Dict[str, Any]:
        """执行模拟计算"""

        base_predictions = base_prediction.get("predictions", [])
        if not base_predictions:
            # 生成默认基准预测
            base_predictions = [
                {"hour": h, "p50": 1200 + h * 30, "congestion_level": "moderate"}
                for h in hours
            ]

        simulated = []

        for pred in base_predictions:
            hour = pred.get("hour", 12)
            base_volume = pred.get("p50", 1500)
            base_speed = 120  # 基准速度 km/h

            # 应用场景修改
            volume_modifier = 1.0
            speed_modifier = 1.0

            if scenario_type == "weather_change":
                weather = parameters.get("weather", "clear")
                speed_modifier = self.WEATHER_SPEED_FACTOR.get(weather, 1.0)
                # 恶劣天气可能导致部分人取消出行
                if weather in ["heavy_rain", "snow", "ice"]:
                    volume_modifier = 0.85

            elif scenario_type == "traffic_increase":
                volume_modifier = parameters.get("traffic_multiplier", 1.0)

            elif scenario_type == "accident":
                affected_hours = parameters.get("affected_hours", [hour])
                lanes_blocked = parameters.get("lanes_blocked", 1)
                if hour in affected_hours:
                    # 事故导致通行能力下降
                    capacity_reduction = lanes_blocked * 0.3
                    speed_modifier = 1.0 - capacity_reduction
                    # 后续小时有排队效应
                    queue_buildup = 1.1 + (hour - min(affected_hours)) * 0.05
                    volume_modifier = min(queue_buildup, 1.5)

            elif scenario_type == "construction":
                lanes_closed = parameters.get("lanes_closed", 1)
                speed_modifier = 1.0 - (lanes_closed * 0.2)
                volume_modifier = 1.0  # 施工期间流量不变但速度降低

            elif scenario_type == "tourist_surge":
                surge_percent = parameters.get("surge_percent", 20)
                volume_modifier = 1.0 + surge_percent / 100

            # 计算模拟后的值
            sim_volume = int(base_volume * volume_modifier)
            sim_speed = base_speed * speed_modifier

            # 流量接近容量时速度进一步下降
            capacity = 4000  # 默认容量
            utilization = sim_volume / capacity
            if utilization > 0.8:
                congestion_factor = max(0.3, 1.0 - (utilization - 0.8) * 2)
                sim_speed *= congestion_factor

            sim_speed = max(20, sim_speed)  # 最低20km/h

            # 计算延误
            base_travel_time = 100 / base_speed * 60  # 100km基准旅行时间(分钟)
            sim_travel_time = 100 / sim_speed * 60
            delay_min = sim_travel_time - base_travel_time

            # 确定新的拥堵等级
            congestion = self._get_congestion_from_speed(sim_speed)

            simulated.append({
                "hour": hour,
                "base_volume": base_volume,
                "simulated_volume": sim_volume,
                "volume_change_percent": round((volume_modifier - 1) * 100, 1),
                "base_speed_kmh": base_speed,
                "simulated_speed_kmh": round(sim_speed, 1),
                "speed_change_percent": round((speed_modifier - 1) * 100, 1),
                "delay_minutes": round(delay_min, 1),
                "congestion_level": congestion,
                "utilization": round(utilization, 2),
            })

        # 汇总统计
        total_delay = sum(s["delay_minutes"] for s in simulated)
        avg_speed = sum(s["simulated_speed_kmh"] for s in simulated) / len(simulated)
        worst_hour = max(simulated, key=lambda x: x["delay_minutes"])

        return {
            "hourly_results": simulated,
            "summary": {
                "total_delay_minutes": round(total_delay, 1),
                "average_speed_kmh": round(avg_speed, 1),
                "worst_hour": worst_hour["hour"],
                "worst_delay_minutes": worst_hour["delay_minutes"],
                "hours_with_heavy_congestion": sum(
                    1 for s in simulated if s["congestion_level"] in ["heavy", "critical"]
                ),
            },
            "scenario_applied": {
                "type": scenario_type,
                "parameters": parameters
            }
        }

    def _get_congestion_from_speed(self, speed: float) -> str:
        """根据速度判断拥堵等级"""
        if speed >= 100:
            return "smooth"
        elif speed >= 80:
            return "light"
        elif speed >= 60:
            return "moderate"
        elif speed >= 40:
            return "heavy"
        else:
            return "critical"

    def _generate_alternatives(
        self,
        simulation_result: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成替代方案"""
        alternatives = []
        summary = simulation_result.get("summary", {})
        worst_hour = summary.get("worst_hour", 10)

        # 方案1：提前出发
        early_departure = worst_hour - 3
        if early_departure >= 5:
            alternatives.append({
                "id": "early_departure",
                "name": "Early Departure",
                "description": f"Leave at {early_departure:02d}:00 instead of {worst_hour:02d}:00",
                "estimated_time_saved_min": int(summary.get("worst_delay_minutes", 0) * 0.8),
                "trade_off": "Earlier wake-up required",
                "feasibility": "high"
            })

        # 方案2：延迟出发
        late_departure = worst_hour + 4
        if late_departure <= 20:
            alternatives.append({
                "id": "late_departure",
                "name": "Late Departure",
                "description": f"Leave at {late_departure:02d}:00 instead of {worst_hour:02d}:00",
                "estimated_time_saved_min": int(summary.get("worst_delay_minutes", 0) * 0.7),
                "trade_off": "Later arrival at destination",
                "feasibility": "medium"
            })

        # 方案3：替代路线（如果有严重拥堵）
        if summary.get("worst_delay_minutes", 0) > 30:
            alternatives.append({
                "id": "alternative_route",
                "name": "Alternative Route via B roads",
                "description": "Use B307/B21 instead of A8 through Rosenheim",
                "estimated_time_saved_min": int(summary.get("worst_delay_minutes", 0) * 0.5),
                "additional_distance_km": 15,
                "trade_off": "Longer distance but potentially faster",
                "feasibility": "medium"
            })

        # 方案4：改期出行
        if summary.get("total_delay_minutes", 0) > 60:
            alternatives.append({
                "id": "different_day",
                "name": "Travel on Different Day",
                "description": "Consider traveling on a weekday instead",
                "estimated_time_saved_min": int(summary.get("total_delay_minutes", 0) * 0.9),
                "trade_off": "Schedule change required",
                "feasibility": "depends_on_flexibility"
            })

        return alternatives

    def _generate_recommendations(
        self,
        simulation_result: Dict[str, Any],
        alternatives: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成综合建议"""
        summary = simulation_result.get("summary", {})
        total_delay = summary.get("total_delay_minutes", 0)

        if total_delay < 15:
            overall = "proceed"
            message = "Traffic conditions are acceptable. You can proceed with your planned trip."
            risk_level = "low"
        elif total_delay < 45:
            overall = "proceed_with_caution"
            message = "Moderate delays expected. Consider adjusting your departure time."
            risk_level = "medium"
        else:
            overall = "consider_alternatives"
            message = "Significant delays expected. We recommend considering alternative plans."
            risk_level = "high"

        # 找出最佳替代方案
        best_alternative = None
        if alternatives:
            best_alternative = max(
                alternatives,
                key=lambda x: x.get("estimated_time_saved_min", 0)
            )

        return {
            "overall": overall,
            "message": message,
            "risk_level": risk_level,
            "expected_delay_minutes": total_delay,
            "best_alternative": best_alternative,
            "tips": self._generate_tips(simulation_result, alternatives)
        }

    def _generate_tips(
        self,
        simulation_result: Dict[str, Any],
        alternatives: List[Dict[str, Any]]
    ) -> List[str]:
        """生成实用提示"""
        tips = []
        summary = simulation_result.get("summary", {})

        if summary.get("hours_with_heavy_congestion", 0) > 3:
            tips.append("📱 Download offline maps in case of poor connectivity in traffic")

        if summary.get("worst_delay_minutes", 0) > 30:
            tips.append("⛽ Ensure full tank before departure")
            tips.append("🍎 Pack snacks and water for potential delays")

        if summary.get("average_speed_kmh", 100) < 60:
            tips.append("🚗 Expect stop-and-go traffic, stay alert")

        tips.append("📻 Monitor traffic reports during your journey")

        return tips

    async def compare_scenarios(
        self,
        scenarios: List[Dict[str, Any]],
        base_prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """比较多个场景"""
        results = []

        for scenario in scenarios:
            result = await self._run_simulation(
                scenario.get("type", "custom"),
                base_prediction,
                scenario.get("parameters", {}),
                scenario.get("date", datetime.now().strftime("%Y-%m-%d")),
                scenario.get("hours", list(range(24)))
            )
            results.append({
                "scenario": scenario,
                "result": result
            })

        # 排序：按总延误从低到高
        results.sort(key=lambda x: x["result"]["summary"]["total_delay_minutes"])

        return {
            "scenarios_compared": len(scenarios),
            "best_scenario": results[0] if results else None,
            "worst_scenario": results[-1] if results else None,
            "all_results": results
        }
