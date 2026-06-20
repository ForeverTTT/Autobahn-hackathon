"""
Orchestrator Agent (调度协调Agent)
负责接收用户请求，协调各专职Agent，汇总结果
"""
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

from .base import BaseAgent, AgentType, AgentResponse, AgentMessage
from .config import AgentConfig, default_config
from .agents import ForecastAgent, ExplanationAgent, RetrievalAgent, SimulationAgent, GraphRAGAgent


class QueryIntent(Enum):
    """用户查询意图"""
    FORECAST = "forecast"           # 预测查询
    EXPLAIN = "explain"             # 解释查询
    WHAT_IF = "what_if"            # What-if模拟
    PLAN_TRIP = "plan_trip"        # 出行规划
    COMPARE = "compare"            # 方案比较
    GENERAL = "general"            # 通用问答


class OrchestratorAgent(BaseAgent):
    """
    调度协调Agent
    - 解析用户意图
    - 分配任务给专职Agent
    - 汇总各Agent结果
    - 生成最终响应
    """

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.ORCHESTRATOR, config or default_config)

        # 初始化各专职Agent
        self.forecast_agent = ForecastAgent(self.config)
        self.explanation_agent = ExplanationAgent(self.config)
        self.retrieval_agent = RetrievalAgent(self.config)
        self.simulation_agent = SimulationAgent(self.config)
        self.graph_rag_agent = GraphRAGAgent(self.config)

        self._agents = {
            AgentType.FORECAST: self.forecast_agent,
            AgentType.EXPLANATION: self.explanation_agent,
            AgentType.RETRIEVAL: self.retrieval_agent,
            AgentType.SIMULATION: self.simulation_agent,
            AgentType.GRAPH_RAG: self.graph_rag_agent,
        }

    async def initialize(self) -> bool:
        """初始化所有Agent"""
        try:
            # 并行初始化所有Agent
            init_tasks = [
                self.forecast_agent.initialize(),
                self.explanation_agent.initialize(),
                self.retrieval_agent.initialize(),
                self.simulation_agent.initialize(),
                self.graph_rag_agent.initialize(),
            ]
            results = await asyncio.gather(*init_tasks)

            self._initialized = all(results)
            return self._initialized

        except Exception as e:
            print(f"Orchestrator initialization error: {e}")
            self._initialized = False
            return False

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        处理用户请求

        Request格式:
        {
            "query": "What's the traffic like on A8 tomorrow?",  # 自然语言查询
            "date": "2026-07-15",  # 可选
            "road": "A8",  # 可选
            "site_id": "A8_Rosenheim",  # 可选
            "direction": "east",  # 可选
            "user_type": "tourist",  # tourist, resident, logistics, tourism_business, authority
            "scenario": {...},  # 可选的What-if场景
        }
        """
        try:
            # 1. 解析意图
            intent = self._parse_intent(request)

            # 2. 提取参数
            params = self._extract_params(request)

            # 3. 根据意图协调Agent
            if intent == QueryIntent.FORECAST:
                result = await self._handle_forecast(params)
            elif intent == QueryIntent.EXPLAIN:
                result = await self._handle_explain(params)
            elif intent == QueryIntent.WHAT_IF:
                result = await self._handle_what_if(params)
            elif intent == QueryIntent.PLAN_TRIP:
                result = await self._handle_plan_trip(params)
            elif intent == QueryIntent.COMPARE:
                result = await self._handle_compare(params)
            else:
                result = await self._handle_general(params)

            # 4. 个性化响应
            personalized = self._personalize_response(
                result, params.get("user_type", "tourist")
            )

            return AgentResponse(
                success=True,
                data=personalized,
                message="Request processed successfully",
                agent_type=self.agent_type,
                confidence=result.get("confidence", 0.85)
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Orchestrator error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0
            )

    def get_capabilities(self) -> List[str]:
        return [
            "intent_parsing",
            "multi_agent_coordination",
            "response_aggregation",
            "personalization",
        ]

    def _parse_intent(self, request: Dict[str, Any]) -> QueryIntent:
        """解析用户意图"""
        query = request.get("query", "").lower()

        # What-if场景
        if request.get("scenario") or any(
            kw in query for kw in ["if", "what if", "假如", "如果", "would"]
        ):
            return QueryIntent.WHAT_IF

        # 出行规划
        if any(kw in query for kw in [
            "plan", "trip", "travel", "route", "when should",
            "best time", "recommend", "规划", "出行", "什么时候"
        ]):
            return QueryIntent.PLAN_TRIP

        # 比较
        if any(kw in query for kw in ["compare", "vs", "versus", "比较", "对比"]):
            return QueryIntent.COMPARE

        # 解释
        if any(kw in query for kw in [
            "why", "reason", "explain", "因为", "为什么", "原因"
        ]):
            return QueryIntent.EXPLAIN

        # 预测（默认）
        if any(kw in query for kw in [
            "traffic", "congestion", "busy", "predict", "forecast",
            "交通", "拥堵", "预测", "流量"
        ]) or request.get("date"):
            return QueryIntent.FORECAST

        return QueryIntent.GENERAL

    def _extract_params(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """提取请求参数"""
        return {
            "query": request.get("query", ""),
            "date": request.get("date", datetime.now().strftime("%Y-%m-%d")),
            "road": request.get("road", "A8"),
            "site_id": request.get("site_id", "A8_Rosenheim"),
            "direction": request.get("direction", "east"),
            "user_type": request.get("user_type", "tourist"),
            "scenario": request.get("scenario"),
            "hours": request.get("hours", list(range(6, 22))),  # 默认6:00-21:00
        }

    async def _handle_forecast(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理预测请求"""
        # 并行执行预测和检索
        forecast_task = self.forecast_agent.process({
            "date": params["date"],
            "road": params["road"],
            "site_id": params["site_id"],
            "direction": params["direction"],
            "hours": params["hours"],
        })

        retrieval_task = self.retrieval_agent.process({
            "date": params["date"],
            "road": params["road"],
            "query_types": ["construction", "events"],
        })

        graph_task = self.graph_rag_agent.process({
            "action": "explain",
            "date": params["date"],
            "road": params["road"],
            "site_id": params["site_id"],
            "hour": params["hours"][0] if params.get("hours") else 8,
        })

        forecast_result, retrieval_result, graph_result = await asyncio.gather(
            forecast_task, retrieval_task, graph_task
        )

        # 获取解释
        explanation_result = await self.explanation_agent.process({
            "date": params["date"],
            "site_id": params["site_id"],
            "prediction": forecast_result.data if forecast_result.success else {},
        })

        return {
            "type": "forecast",
            "forecast": forecast_result.data if forecast_result.success else None,
            "external_factors": retrieval_result.data if retrieval_result.success else None,
            "graph_context": graph_result.data if graph_result.success else None,
            "explanation": explanation_result.data if explanation_result.success else None,
            "confidence": min(
                forecast_result.confidence,
                retrieval_result.confidence,
                explanation_result.confidence,
                graph_result.confidence
            )
        }

    async def _handle_explain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理解释请求"""
        # 先获取预测
        forecast_result = await self.forecast_agent.process({
            "date": params["date"],
            "road": params["road"],
            "site_id": params["site_id"],
            "direction": params["direction"],
            "hours": params["hours"],
        })

        # 再获取解释
        explanation_result = await self.explanation_agent.process({
            "date": params["date"],
            "site_id": params["site_id"],
            "prediction": forecast_result.data if forecast_result.success else {},
        })

        graph_result = await self.graph_rag_agent.process({
            "action": "explain",
            "date": params["date"],
            "road": params["road"],
            "site_id": params["site_id"],
            "hour": params["hours"][0] if params.get("hours") else 8,
        })

        return {
            "type": "explanation",
            "forecast": forecast_result.data if forecast_result.success else None,
            "explanation": explanation_result.data if explanation_result.success else None,
            "graph_context": graph_result.data if graph_result.success else None,
            "confidence": min(explanation_result.confidence, graph_result.confidence)
        }

    async def _handle_what_if(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理What-if请求"""
        # 获取基准预测
        forecast_result = await self.forecast_agent.process({
            "date": params["date"],
            "site_id": params["site_id"],
            "direction": params["direction"],
            "hours": params["hours"],
        })

        # 执行模拟
        scenario = params.get("scenario", {})
        simulation_result = await self.simulation_agent.process({
            "scenario_type": scenario.get("type", "custom"),
            "base_prediction": forecast_result.data if forecast_result.success else {},
            "parameters": scenario.get("parameters", {}),
            "date": params["date"],
            "hours": params["hours"],
        })

        return {
            "type": "what_if",
            "base_forecast": forecast_result.data if forecast_result.success else None,
            "simulation": simulation_result.data if simulation_result.success else None,
            "confidence": simulation_result.confidence
        }

    async def _handle_plan_trip(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理出行规划请求"""
        # 并行获取所有信息
        tasks = [
            self.forecast_agent.process({
                "date": params["date"],
                "road": params["road"],
                "site_id": params["site_id"],
                "direction": params["direction"],
                "hours": list(range(5, 23)),  # 更宽的时间范围
            }),
            self.retrieval_agent.process({
                "date": params["date"],
                "road": params["road"],
                "query_types": ["construction", "events", "incidents"],
            }),
            self.explanation_agent.process({
                "date": params["date"],
                "site_id": params["site_id"],
            }),
            self.graph_rag_agent.process({
                "action": "context",
                "date": params["date"],
                "road": params["road"],
                "user_type": params.get("user_type", "tourist"),
            }),
        ]

        results = await asyncio.gather(*tasks)
        forecast_result, retrieval_result, explanation_result, graph_result = results

        # 生成出行计划
        plan = self._generate_trip_plan(
            forecast_result.data if forecast_result.success else {},
            retrieval_result.data if retrieval_result.success else {},
            explanation_result.data if explanation_result.success else {},
            params
        )

        return {
            "type": "trip_plan",
            "plan": plan,
            "forecast": forecast_result.data if forecast_result.success else None,
            "external_factors": retrieval_result.data if retrieval_result.success else None,
            "explanation": explanation_result.data if explanation_result.success else None,
            "graph_context": graph_result.data if graph_result.success else None,
            "confidence": 0.85
        }

    async def _handle_compare(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理比较请求"""
        # 比较不同时间/场景
        scenarios = params.get("scenarios", [
            {"type": "weather_change", "parameters": {"weather": "clear"}},
            {"type": "weather_change", "parameters": {"weather": "heavy_rain"}},
        ])

        forecast_result = await self.forecast_agent.process({
            "date": params["date"],
            "site_id": params["site_id"],
            "direction": params["direction"],
            "hours": params["hours"],
        })

        comparison = await self.simulation_agent.compare_scenarios(
            scenarios,
            forecast_result.data if forecast_result.success else {}
        )

        return {
            "type": "comparison",
            "comparison": comparison,
            "confidence": 0.8
        }

    async def _handle_general(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理通用请求"""
        # 获取基本信息
        forecast_result = await self.forecast_agent.process({
            "date": params["date"],
            "site_id": params["site_id"],
            "direction": params["direction"],
            "hours": params["hours"],
        })

        return {
            "type": "general",
            "forecast": forecast_result.data if forecast_result.success else None,
            "message": "Here's the traffic forecast for your requested date and location.",
            "confidence": forecast_result.confidence
        }

    def _generate_trip_plan(
        self,
        forecast: Dict[str, Any],
        external: Dict[str, Any],
        explanation: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成出行计划"""
        predictions = forecast.get("predictions", [])
        warnings = external.get("warnings", [])
        impact = external.get("overall_impact", {})

        # 找出最佳出发时间
        best_hours = []
        for pred in predictions:
            if pred.get("congestion_level") in ["smooth", "light"]:
                best_hours.append(pred["hour"])

        # 找出应避开的时间
        avoid_hours = []
        for pred in predictions:
            if pred.get("congestion_level") in ["heavy", "critical"]:
                avoid_hours.append(pred["hour"])

        # 推荐出发时间
        if best_hours:
            # 优先选择早上的好时段
            morning_hours = [h for h in best_hours if 5 <= h <= 9]
            if morning_hours:
                recommended_departure = morning_hours[0]
            else:
                recommended_departure = best_hours[0]
        else:
            # 如果没有好时段，选择拥堵相对轻的
            recommended_departure = min(
                predictions,
                key=lambda x: ["smooth", "light", "moderate", "heavy", "critical"].index(
                    x.get("congestion_level", "moderate")
                )
            )["hour"] if predictions else 7

        # 估算旅行时间
        base_travel_time = 90  # 基准旅行时间（分钟）
        delay_estimate = impact.get("delay_estimate_min", 0)
        total_time = base_travel_time + delay_estimate

        # 压力指数
        stress_index = self._calculate_stress_index(
            forecast, external, params.get("user_type", "tourist")
        )

        return {
            "recommended_departure": f"{recommended_departure:02d}:00",
            "recommended_departure_hour": recommended_departure,
            "alternative_departures": [f"{h:02d}:00" for h in best_hours[:3]],
            "avoid_times": [f"{h:02d}:00" for h in avoid_hours],
            "estimated_travel_time_min": total_time,
            "estimated_arrival": self._calculate_arrival(
                params["date"], recommended_departure, total_time
            ),
            "stress_index": stress_index,
            "warnings": warnings,
            "tips": self._generate_trip_tips(
                forecast, external, params.get("user_type", "tourist")
            ),
        }

    def _calculate_stress_index(
        self,
        forecast: Dict[str, Any],
        external: Dict[str, Any],
        user_type: str
    ) -> Dict[str, Any]:
        """计算出行压力指数"""
        score = 50  # 基准分

        # 根据拥堵情况调整
        predictions = forecast.get("predictions", [])
        heavy_hours = sum(
            1 for p in predictions
            if p.get("congestion_level") in ["heavy", "critical"]
        )
        score += heavy_hours * 5

        # 根据外部因素调整
        impact_level = external.get("overall_impact", {}).get("level", "none")
        impact_scores = {"none": 0, "low": 5, "moderate": 15, "high": 25, "critical": 40}
        score += impact_scores.get(impact_level, 0)

        # 归一化到0-100
        score = min(100, max(0, score))

        if score < 30:
            level = "low"
            emoji = "😊"
            description = "Relaxed travel conditions"
        elif score < 50:
            level = "moderate"
            emoji = "😐"
            description = "Some traffic expected"
        elif score < 70:
            level = "high"
            emoji = "😓"
            description = "Significant delays possible"
        else:
            level = "very_high"
            emoji = "😰"
            description = "Challenging travel conditions"

        return {
            "score": score,
            "level": level,
            "emoji": emoji,
            "description": description
        }

    def _calculate_arrival(
        self,
        date_str: str,
        departure_hour: int,
        travel_time_min: int
    ) -> str:
        """计算预计到达时间"""
        departure = datetime.strptime(f"{date_str} {departure_hour:02d}:00", "%Y-%m-%d %H:%M")
        arrival = departure + __import__('datetime').timedelta(minutes=travel_time_min)
        return arrival.strftime("%H:%M")

    def _generate_trip_tips(
        self,
        forecast: Dict[str, Any],
        external: Dict[str, Any],
        user_type: str
    ) -> List[str]:
        """生成出行提示"""
        tips = []

        # 通用提示
        tips.append("📱 Check real-time traffic before departure")

        # 根据用户类型定制
        if user_type == "tourist":
            tips.append("🗺️ Consider stopping at scenic viewpoints along the way")
            tips.append("⛽ Gas stations near Rosenheim: Shell, Aral available")
        elif user_type == "logistics":
            tips.append("🚚 Truck restrictions may apply on certain sections")
            tips.append("⚖️ Weigh station at km 45 - plan accordingly")
        elif user_type == "resident":
            tips.append("🏠 Local roads via Rosenheim city may be faster during peak hours")

        # 根据外部因素提示
        warnings = external.get("warnings", [])
        if warnings:
            tips.append("⚠️ Check warnings section for special conditions")

        return tips

    def _personalize_response(
        self,
        result: Dict[str, Any],
        user_type: str
    ) -> Dict[str, Any]:
        """根据用户类型个性化响应"""
        result["user_type"] = user_type

        # 添加用户特定的建议
        user_specific = {
            "tourist": {
                "focus": "best travel experience",
                "priority": "scenic route, comfortable timing",
            },
            "resident": {
                "focus": "avoiding local congestion",
                "priority": "quick commute, familiar routes",
            },
            "logistics": {
                "focus": "delivery efficiency",
                "priority": "punctuality, truck-friendly routes",
            },
            "tourism_business": {
                "focus": "customer arrival patterns",
                "priority": "peak visitor times, preparation",
            },
            "authority": {
                "focus": "traffic management",
                "priority": "congestion prevention, resource allocation",
            },
        }

        result["personalization"] = user_specific.get(user_type, user_specific["tourist"])

        return result

    async def health_check(self) -> Dict[str, Any]:
        """检查所有Agent健康状态"""
        status = {
            "orchestrator": self._initialized,
            "agents": {}
        }

        for agent_type, agent in self._agents.items():
            status["agents"][agent_type.value] = await agent.health_check()

        status["all_healthy"] = all(status["agents"].values()) and status["orchestrator"]

        return status
