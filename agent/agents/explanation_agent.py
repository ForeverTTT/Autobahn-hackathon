"""
Explanation Agent (解释Agent)
负责分析影响因素，解释预测结果
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from ..base import BaseAgent, AgentType, AgentResponse
from ..config import AgentConfig, default_config
from ..graph_rag import GraphRAG


class ExplanationAgent(BaseAgent):
    """
    解释Agent
    - 分析影响交通的因素（假期、天气、历史模式等）
    - 生成可解释的归因报告
    """

    # 德国巴伐利亚州假期（简化版）
    HOLIDAYS_2026 = {
        "2026-01-01": "New Year's Day",
        "2026-01-06": "Epiphany",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Easter Monday",
        "2026-05-01": "Labour Day",
        "2026-05-14": "Ascension Day",
        "2026-05-25": "Whit Monday",
        "2026-06-04": "Corpus Christi",
        "2026-08-15": "Assumption Day",
        "2026-10-03": "German Unity Day",
        "2026-11-01": "All Saints' Day",
        "2026-12-25": "Christmas Day",
        "2026-12-26": "St. Stephen's Day",
    }

    # 学校假期（巴伐利亚2026预估）
    SCHOOL_HOLIDAYS_2026 = [
        ("2026-02-14", "2026-02-22", "Winter Break"),
        ("2026-03-28", "2026-04-12", "Easter Break"),
        ("2026-05-23", "2026-06-07", "Whitsun Break"),
        ("2026-07-27", "2026-09-07", "Summer Break"),
        ("2026-10-31", "2026-11-08", "Autumn Break"),
        ("2026-12-23", "2027-01-05", "Christmas Break"),
    ]

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.EXPLANATION, config or default_config)
        self._holiday_cache: Dict[str, str] = {}
        self.graph = GraphRAG()

    async def initialize(self) -> bool:
        """加载假期、事件和 GraphRAG 数据"""
        self._holiday_cache = self.HOLIDAYS_2026.copy()
        await self.graph.initialize()
        self._initialized = True
        return True

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        分析并解释预测结果

        Request格式:
        {
            "date": "2026-07-15",
            "site_id": "A8_Rosenheim",
            "prediction": {...},  # 来自ForecastAgent的预测
            "weather": {...}  # 可选的天气信息
        }

        Response:
        {
            "factors": [...],
            "explanation": "...",
            "confidence_factors": {...}
        }
        """
        try:
            date_str = request.get("date", datetime.now().strftime("%Y-%m-%d"))
            site_id = request.get("site_id", "A8_001")
            road = request.get("road")
            hour = int(request.get("hour", 8))
            prediction = request.get("prediction", {})
            weather = request.get("weather", {})

            date = datetime.strptime(date_str, "%Y-%m-%d")

            # 分析各项因素
            factors = []

            # 1. 假期因素
            holiday_factor = self._analyze_holiday(date_str, date)
            if holiday_factor:
                factors.append(holiday_factor)

            # 2. 学校假期因素
            school_factor = self._analyze_school_holiday(date_str)
            if school_factor:
                factors.append(school_factor)

            # 3. 周末因素
            weekend_factor = self._analyze_weekend(date)
            if weekend_factor:
                factors.append(weekend_factor)

            # 4. 季节因素
            season_factor = self._analyze_season(date)
            factors.append(season_factor)

            # 5. 天气因素（如果提供）
            if weather:
                weather_factor = self._analyze_weather(weather)
                if weather_factor:
                    factors.append(weather_factor)

            # 6. 路段特性
            segment_factor = self._analyze_segment(site_id)
            if segment_factor:
                factors.append(segment_factor)

            # 7. GraphRAG 因素：从本地虚拟图读取天气、施工、节假日、活动和预测上下文
            graph_context = self.graph.explain_congestion(site_id, date_str, hour)
            graph_factors = self._normalize_graph_factors(graph_context.get("factors", []))
            factors.extend(graph_factors)

            # 生成综合解释
            explanation = self._generate_explanation(factors, date, prediction)

            # 计算各因素对置信度的影响
            confidence_factors = self._calculate_confidence_factors(factors)

            return AgentResponse(
                success=True,
                data={
                    "factors": factors,
                    "explanation": explanation,
                    "confidence_factors": confidence_factors,
                    "graph_context": graph_context,
                    "date": date_str,
                    "site_id": site_id,
                    "road": road or graph_context.get("road"),
                    "hour": hour,
                },
                message="Explanation generated successfully",
                agent_type=self.agent_type,
                confidence=0.9
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Explanation error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0
            )

    def get_capabilities(self) -> List[str]:
        return [
            "holiday_impact_analysis",
            "weather_impact_analysis",
            "historical_pattern_matching",
            "factor_attribution",
            "graph_rag_factor_attribution",
            "natural_language_explanation",
        ]

    def _normalize_graph_factors(self, graph_factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert GraphRAG factor nodes into explanation factors."""
        normalized = []
        impact_magnitude = {
            "very_high": 0.6,
            "high": 0.4,
            "moderate": 0.25,
            "low": 0.1,
            "none": 0.0,
        }

        for factor in graph_factors:
            impact = str(factor.get("impact", "low"))
            normalized.append({
                "type": factor.get("type", "graph_factor"),
                "name": factor.get("name", "GraphRAG factor"),
                "impact": impact,
                "direction": "increase" if impact in {"moderate", "high", "very_high"} else "normal",
                "magnitude": impact_magnitude.get(impact, 0.1),
                "description": factor.get("description", "GraphRAG detected a relevant traffic factor"),
                "source": "graph_rag",
            })

        return normalized

    def _analyze_holiday(self, date_str: str, date: datetime) -> Optional[Dict[str, Any]]:
        """分析公共假期影响"""
        if date_str in self._holiday_cache:
            return {
                "type": "public_holiday",
                "name": self._holiday_cache[date_str],
                "impact": "high",
                "direction": "increase",
                "magnitude": 0.4,  # 40%流量增加
                "description": f"Public holiday ({self._holiday_cache[date_str]}) - expect higher traffic"
            }

        # 检查假期前后
        for delta in [1, -1]:
            check_date = (date + __import__('datetime').timedelta(days=delta)).strftime("%Y-%m-%d")
            if check_date in self._holiday_cache:
                position = "before" if delta == 1 else "after"
                return {
                    "type": "holiday_adjacent",
                    "name": f"Day {position} {self._holiday_cache[check_date]}",
                    "impact": "moderate",
                    "direction": "increase",
                    "magnitude": 0.25,
                    "description": f"Day {position} holiday - moderate traffic increase expected"
                }

        return None

    def _analyze_school_holiday(self, date_str: str) -> Optional[Dict[str, Any]]:
        """分析学校假期影响"""
        date = datetime.strptime(date_str, "%Y-%m-%d")

        for start, end, name in self.SCHOOL_HOLIDAYS_2026:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")

            if start_date <= date <= end_date:
                # 假期开始/结束几天流量更高
                days_from_start = (date - start_date).days
                days_to_end = (end_date - date).days

                if days_from_start <= 2:
                    impact = "very_high"
                    magnitude = 0.6
                    desc = f"Start of {name} - peak departure traffic"
                elif days_to_end <= 2:
                    impact = "very_high"
                    magnitude = 0.5
                    desc = f"End of {name} - peak return traffic"
                else:
                    impact = "moderate"
                    magnitude = 0.2
                    desc = f"During {name} - elevated leisure traffic"

                return {
                    "type": "school_holiday",
                    "name": name,
                    "impact": impact,
                    "direction": "increase",
                    "magnitude": magnitude,
                    "description": desc
                }

        return None

    def _analyze_weekend(self, date: datetime) -> Optional[Dict[str, Any]]:
        """分析周末因素"""
        weekday = date.weekday()

        if weekday == 4:  # Friday
            return {
                "type": "weekend",
                "name": "Friday",
                "impact": "moderate",
                "direction": "increase",
                "magnitude": 0.15,
                "peak_hours": [14, 15, 16, 17, 18],
                "description": "Friday afternoon - weekend departure traffic"
            }
        elif weekday == 5:  # Saturday
            return {
                "type": "weekend",
                "name": "Saturday",
                "impact": "moderate",
                "direction": "shift",
                "magnitude": 0.1,
                "peak_hours": [9, 10, 11],
                "description": "Saturday - leisure travel, later morning peak"
            }
        elif weekday == 6:  # Sunday
            return {
                "type": "weekend",
                "name": "Sunday",
                "impact": "moderate",
                "direction": "increase",
                "magnitude": 0.2,
                "peak_hours": [15, 16, 17, 18, 19],
                "description": "Sunday afternoon - weekend return traffic"
            }

        return None

    def _analyze_season(self, date: datetime) -> Dict[str, Any]:
        """分析季节因素"""
        month = date.month

        if month in [6, 7, 8]:
            return {
                "type": "season",
                "name": "Summer",
                "impact": "high",
                "direction": "increase",
                "magnitude": 0.3,
                "description": "Summer season - high tourist traffic towards Alps"
            }
        elif month in [12, 1, 2]:
            return {
                "type": "season",
                "name": "Winter",
                "impact": "moderate",
                "direction": "increase",
                "magnitude": 0.2,
                "description": "Winter season - ski traffic towards Austria"
            }
        elif month in [3, 4, 5]:
            return {
                "type": "season",
                "name": "Spring",
                "impact": "low",
                "direction": "normal",
                "magnitude": 0.05,
                "description": "Spring - moderate traffic levels"
            }
        else:
            return {
                "type": "season",
                "name": "Autumn",
                "impact": "low",
                "direction": "normal",
                "magnitude": 0.05,
                "description": "Autumn - moderate traffic levels"
            }

    def _analyze_weather(self, weather: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """分析天气影响"""
        condition = weather.get("condition", "clear")
        rain = weather.get("rain_mm", 0)
        snow = weather.get("snow", False)

        if snow:
            return {
                "type": "weather",
                "name": "Snow",
                "impact": "high",
                "direction": "decrease_speed",
                "magnitude": -0.3,
                "description": "Snow conditions - reduced speeds, potential delays"
            }
        elif rain > 10:
            return {
                "type": "weather",
                "name": "Heavy Rain",
                "impact": "moderate",
                "direction": "decrease_speed",
                "magnitude": -0.15,
                "description": "Heavy rain - reduced visibility and speeds"
            }
        elif condition == "sunny" and weather.get("temp_c", 20) > 25:
            return {
                "type": "weather",
                "name": "Good Weather",
                "impact": "moderate",
                "direction": "increase",
                "magnitude": 0.1,
                "description": "Good weather - increased leisure travel"
            }

        return None

    def _analyze_segment(self, site_id: str) -> Optional[Dict[str, Any]]:
        """分析路段特性"""
        # 已知瓶颈路段
        bottlenecks = {
            "A8_Rosenheim": {
                "type": "segment",
                "name": "Rosenheim Junction",
                "impact": "high",
                "direction": "bottleneck",
                "magnitude": 0.25,
                "description": "Major junction - frequent congestion point"
            },
            "A8_Inntal": {
                "type": "segment",
                "name": "Inn Valley",
                "impact": "moderate",
                "direction": "bottleneck",
                "magnitude": 0.15,
                "description": "Border crossing area - customs delays possible"
            }
        }

        return bottlenecks.get(site_id)

    def _generate_explanation(
        self,
        factors: List[Dict[str, Any]],
        date: datetime,
        prediction: Dict[str, Any]
    ) -> str:
        """生成自然语言解释"""
        date_str = date.strftime("%A, %B %d, %Y")

        if not factors:
            return f"On {date_str}, traffic is expected to be at normal levels."

        # 按影响程度排序
        sorted_factors = sorted(
            factors,
            key=lambda x: abs(x.get("magnitude", 0)),
            reverse=True
        )

        main_factor = sorted_factors[0]
        explanation_parts = [f"On {date_str}:"]

        # 主要因素
        explanation_parts.append(f"• {main_factor['description']}")

        # 其他显著因素
        for factor in sorted_factors[1:3]:  # 最多额外2个因素
            if abs(factor.get("magnitude", 0)) > 0.1:
                explanation_parts.append(f"• {factor['description']}")

        # 综合建议
        total_magnitude = sum(f.get("magnitude", 0) for f in factors)
        if total_magnitude > 0.5:
            explanation_parts.append("\n⚠️ High traffic expected. Consider traveling during off-peak hours.")
        elif total_magnitude > 0.25:
            explanation_parts.append("\n📊 Moderate traffic increase expected.")

        return "\n".join(explanation_parts)

    def _calculate_confidence_factors(self, factors: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算各因素对预测置信度的影响"""
        confidence_map = {}

        for factor in factors:
            factor_type = factor.get("type", "unknown")
            impact = factor.get("impact", "low")

            # 高影响因素增加不确定性
            if impact == "very_high":
                confidence_map[factor_type] = 0.7
            elif impact == "high":
                confidence_map[factor_type] = 0.8
            elif impact == "moderate":
                confidence_map[factor_type] = 0.9
            else:
                confidence_map[factor_type] = 0.95

        return confidence_map
