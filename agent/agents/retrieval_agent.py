"""
Retrieval Agent (检索Agent)
负责联网搜索实时信息（修路、活动、事故等）
"""
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from ..base import BaseAgent, AgentType, AgentResponse
from ..config import AgentConfig, default_config
from ..graph_rag import GraphRAG


class RetrievalAgent(BaseAgent):
    """
    检索Agent
    - 查询修路/施工信息
    - 获取特殊活动（音乐节、体育赛事等）
    - 检索实时交通事件
    """

    # Mock数据：已知施工信息
    KNOWN_CONSTRUCTIONS = [
        {
            "id": "C001",
            "road": "A8",
            "segment": "München-Rosenheim",
            "km_start": 45.2,
            "km_end": 48.7,
            "start_date": "2026-06-01",
            "end_date": "2026-09-30",
            "type": "lane_closure",
            "lanes_affected": 1,
            "description": "Bridge renovation - right lane closed",
            "impact": "moderate"
        },
        {
            "id": "C002",
            "road": "A93",
            "segment": "Rosenheim-Kufstein",
            "km_start": 12.0,
            "km_end": 15.5,
            "start_date": "2026-07-15",
            "end_date": "2026-08-15",
            "type": "full_closure_night",
            "description": "Tunnel maintenance - night closures 22:00-05:00",
            "impact": "high"
        }
    ]

    # Mock数据：特殊活动
    SPECIAL_EVENTS = [
        {
            "id": "E001",
            "name": "Salzburg Festival",
            "location": "Salzburg, Austria",
            "start_date": "2026-07-18",
            "end_date": "2026-08-31",
            "type": "cultural",
            "expected_visitors": 250000,
            "affected_roads": ["A8", "A93"],
            "peak_days": ["saturday", "sunday"],
            "description": "Major classical music festival"
        },
        {
            "id": "E002",
            "name": "Oktoberfest",
            "location": "Munich, Germany",
            "start_date": "2026-09-19",
            "end_date": "2026-10-04",
            "type": "festival",
            "expected_visitors": 6000000,
            "affected_roads": ["A8", "A9", "A94", "A96"],
            "peak_days": ["saturday", "sunday", "opening_day", "closing_day"],
            "description": "World's largest beer festival"
        },
        {
            "id": "E003",
            "name": "FC Bayern Home Game",
            "location": "Munich, Allianz Arena",
            "date": "2026-07-20",
            "type": "sports",
            "expected_visitors": 75000,
            "affected_roads": ["A9"],
            "description": "Bundesliga match"
        }
    ]

    def __init__(self, config: AgentConfig = None):
        super().__init__(AgentType.RETRIEVAL, config or default_config)
        self._api_available = False
        self.graph = GraphRAG()

    async def initialize(self) -> bool:
        """初始化API连接和 GraphRAG 数据"""
        # TODO: 初始化真实API连接（Autobahn API, Event APIs等）
        await self.graph.initialize()
        self._api_available = True
        self._initialized = True
        return True

    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        检索相关信息

        Request格式:
        {
            "date": "2026-07-15",
            "road": "A8",  # 可选
            "query_types": ["construction", "events", "incidents"],
            "radius_km": 50  # 搜索范围
        }
        """
        try:
            date_str = request.get("date", datetime.now().strftime("%Y-%m-%d"))
            road = request.get("road")
            site_id = request.get("site_id")
            user_type = request.get("user_type", "tourist")
            query_types = request.get("query_types", ["construction", "events"])

            results = {
                "date": date_str,
                "road": road,
                "constructions": [],
                "events": [],
                "incidents": [],
                "graph_factors": [],
                "graph_context": None,
                "warnings": []
            }

            # 并行查询各类信息
            tasks = []

            if "construction" in query_types:
                tasks.append(self._query_constructions(date_str, road))

            if "events" in query_types:
                tasks.append(self._query_events(date_str, road))

            if "incidents" in query_types:
                tasks.append(self._query_incidents(date_str, road))

            query_results = await asyncio.gather(*tasks)

            # 合并结果
            for result in query_results:
                if result:
                    results.update(result)

            graph_context = self.graph.get_user_relevant_info(user_type, date_str, road or "A8")
            graph_factor_result = self.graph.query_factors(site_id or road or "A8", date_str)
            results["graph_context"] = graph_context
            results["graph_factors"] = graph_factor_result.get("factors", [])

            # 生成警告
            results["warnings"] = self._generate_warnings(results)

            # 计算整体影响
            results["overall_impact"] = self._calculate_overall_impact(results)

            return AgentResponse(
                success=True,
                data=results,
                message=f"Retrieved {len(results.get('constructions', []))} constructions, "
                        f"{len(results.get('events', []))} events",
                agent_type=self.agent_type,
                confidence=0.95
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                data=None,
                message=f"Retrieval error: {str(e)}",
                agent_type=self.agent_type,
                confidence=0.0
            )

    def get_capabilities(self) -> List[str]:
        return [
            "construction_info_retrieval",
            "event_search",
            "incident_monitoring",
            "graph_rag_context_retrieval",
            "real_time_updates",
            "web_search",
        ]

    async def _query_constructions(
        self,
        date_str: str,
        road: Optional[str]
    ) -> Dict[str, List]:
        """查询施工信息"""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        active_constructions = []

        for construction in self.KNOWN_CONSTRUCTIONS:
            start = datetime.strptime(construction["start_date"], "%Y-%m-%d")
            end = datetime.strptime(construction["end_date"], "%Y-%m-%d")

            # 检查日期范围
            if start <= date <= end:
                # 检查道路匹配
                if road is None or construction["road"] == road:
                    active_constructions.append(construction)

        return {"constructions": active_constructions}

    async def _query_events(
        self,
        date_str: str,
        road: Optional[str]
    ) -> Dict[str, List]:
        """查询特殊活动"""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        relevant_events = []

        for event in self.SPECIAL_EVENTS:
            # 单日活动
            if "date" in event:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d")
                if event_date == date:
                    if road is None or road in event.get("affected_roads", []):
                        relevant_events.append(event)
            # 多日活动
            elif "start_date" in event and "end_date" in event:
                start = datetime.strptime(event["start_date"], "%Y-%m-%d")
                end = datetime.strptime(event["end_date"], "%Y-%m-%d")
                if start <= date <= end:
                    if road is None or road in event.get("affected_roads", []):
                        # 标记是否为高峰日
                        weekday = date.strftime("%A").lower()
                        event_copy = event.copy()
                        event_copy["is_peak_day"] = weekday in event.get("peak_days", [])
                        relevant_events.append(event_copy)

        return {"events": relevant_events}

    async def _query_incidents(
        self,
        date_str: str,
        road: Optional[str]
    ) -> Dict[str, List]:
        """查询实时事故/事件（Mock）"""
        # 实际应用中会调用实时交通API
        return {"incidents": []}

    def _generate_warnings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成警告信息"""
        warnings = []

        # 施工警告
        for construction in results.get("constructions", []):
            if construction.get("impact") == "high":
                warnings.append({
                    "type": "construction",
                    "severity": "high",
                    "message": f"⚠️ {construction['road']}: {construction['description']}",
                    "recommendation": "Consider alternative routes or travel times"
                })

        # 活动警告
        for event in results.get("events", []):
            if event.get("expected_visitors", 0) > 100000 or event.get("is_peak_day"):
                warnings.append({
                    "type": "event",
                    "severity": "moderate",
                    "message": f"🎭 {event['name']} in progress - high traffic expected",
                    "recommendation": "Plan extra travel time"
                })

        # GraphRAG 因素警告
        for factor in results.get("graph_factors", []):
            if factor.get("impact") in {"high", "very_high"}:
                warnings.append({
                    "type": factor.get("type", "graph_factor"),
                    "severity": factor.get("impact", "high"),
                    "message": factor.get("description", factor.get("name", "GraphRAG factor detected")),
                    "recommendation": "Use GraphRAG context when planning departure time"
                })

        return warnings

    def _calculate_overall_impact(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算整体影响"""
        impact_score = 0.0

        # 施工影响
        for construction in results.get("constructions", []):
            if construction.get("impact") == "high":
                impact_score += 0.3
            elif construction.get("impact") == "moderate":
                impact_score += 0.15

        # 活动影响
        for event in results.get("events", []):
            visitors = event.get("expected_visitors", 0)
            if visitors > 1000000:
                impact_score += 0.4
            elif visitors > 100000:
                impact_score += 0.2
            elif visitors > 50000:
                impact_score += 0.1

            if event.get("is_peak_day"):
                impact_score += 0.1

        # 事故影响
        impact_score += len(results.get("incidents", [])) * 0.2

        # GraphRAG 因素影响
        graph_impact_scores = {
            "very_high": 0.35,
            "high": 0.25,
            "moderate": 0.15,
            "low": 0.05,
        }
        for factor in results.get("graph_factors", []):
            impact_score += graph_impact_scores.get(str(factor.get("impact", "low")), 0.0)

        # 归一化
        impact_score = min(1.0, impact_score)

        if impact_score > 0.6:
            level = "critical"
        elif impact_score > 0.4:
            level = "high"
        elif impact_score > 0.2:
            level = "moderate"
        elif impact_score > 0:
            level = "low"
        else:
            level = "none"

        return {
            "score": round(impact_score, 2),
            "level": level,
            "delay_estimate_min": int(impact_score * 45)  # 最高45分钟延误
        }

    async def search_web(self, query: str) -> List[Dict[str, Any]]:
        """
        网络搜索（需要集成搜索API）
        """
        # TODO: 集成Google Search API或其他搜索服务
        return []

    async def fetch_autobahn_api(self, road: str) -> Dict[str, Any]:
        """
        调用德国高速公路官方API
        https://autobahn.api.bund.dev/
        """
        # TODO: 实现真实API调用
        return {}
