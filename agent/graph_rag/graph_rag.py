"""
Graph RAG
图增强检索生成
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .knowledge_graph import KnowledgeGraph
from .entities import (
    Node, Edge, NodeType, EdgeType,
    RoadNode, SegmentNode, DateNode, EventNode,
    WeatherNode, CongestionNode, UserNode
)


class GraphRAG:
    """
    Graph RAG - 图增强检索生成
    将交通世界建模为知识图谱，支持推理和解释
    """

    def __init__(self, backend: str = "networkx"):
        self.graph = KnowledgeGraph(backend)
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化知识图谱，加载基础数据"""
        try:
            # 加载道路结构
            self._load_road_structure()

            # 加载用户画像
            self._load_user_profiles()

            # 加载已知事件
            self._load_known_events()

            self._initialized = True
            return True

        except Exception as e:
            print(f"GraphRAG initialization error: {e}")
            return False

    def _load_road_structure(self) -> None:
        """加载道路结构"""
        # A8高速
        a8 = RoadNode(
            road_id="A8",
            name="Autobahn 8",
            total_length_km=505,
            start_point="Karlsruhe",
            end_point="Salzburg"
        )
        self.graph.add_node(a8)

        # A8路段
        a8_segments = [
            SegmentNode("A8_MUC_ROS", "A8", "München-Rosenheim", 0, 65, is_bottleneck=False, capacity=4500),
            SegmentNode("A8_ROS", "A8", "Rosenheim Junction", 65, 75, is_bottleneck=True, capacity=3800),
            SegmentNode("A8_INNTAL", "A8", "Inntal", 75, 110, is_bottleneck=False, capacity=4000),
            SegmentNode("A8_BORDER", "A8", "Border Crossing", 110, 125, is_bottleneck=True, capacity=3500),
        ]

        for seg in a8_segments:
            self.graph.add_node(seg)
            self.graph.add_edge(Edge(
                source_id=a8.id,
                target_id=seg.id,
                type=EdgeType.CONTAINS
            ))

        # A93高速
        a93 = RoadNode(
            road_id="A93",
            name="Autobahn 93",
            total_length_km=271,
            start_point="Hof",
            end_point="Kufstein"
        )
        self.graph.add_node(a93)

        # A93路段
        a93_segments = [
            SegmentNode("A93_ROS_KUF", "A93", "Rosenheim-Kiefersfelden", 0, 35, is_bottleneck=False, capacity=3800),
            SegmentNode("A93_KUF", "A93", "Kiefersfelden", 35, 45, is_bottleneck=True, capacity=3200),
        ]

        for seg in a93_segments:
            self.graph.add_node(seg)
            self.graph.add_edge(Edge(
                source_id=a93.id,
                target_id=seg.id,
                type=EdgeType.CONTAINS
            ))

    def _load_user_profiles(self) -> None:
        """加载用户画像"""
        profiles = [
            UserNode(
                user_type="tourist",
                description="Travelers heading to Alps or Austria for vacation",
                priorities=["best_travel_experience", "scenic_routes", "comfortable_timing"],
                typical_routes=["A8", "A93"]
            ),
            UserNode(
                user_type="resident",
                description="Local residents commuting or running errands",
                priorities=["quick_commute", "avoid_congestion", "familiar_routes"],
                typical_routes=["A8"]
            ),
            UserNode(
                user_type="logistics",
                description="Commercial transport and delivery services",
                priorities=["punctuality", "fuel_efficiency", "truck_friendly_routes"],
                typical_routes=["A8", "A93"]
            ),
            UserNode(
                user_type="tourism_business",
                description="Hotels, restaurants, and tour operators",
                priorities=["customer_arrival_prediction", "peak_times", "preparation"],
                typical_routes=["A8", "A93"]
            ),
            UserNode(
                user_type="authority",
                description="Traffic management and government agencies",
                priorities=["congestion_prevention", "incident_response", "resource_allocation"],
                typical_routes=["A8", "A93"]
            ),
        ]

        for profile in profiles:
            self.graph.add_node(profile)

            # 用户关心拥堵
            for road_id in profile.properties.get("typical_routes", []):
                road_node_id = f"road_{road_id}"
                if self.graph.get_node(road_node_id):
                    self.graph.add_edge(Edge(
                        source_id=profile.id,
                        target_id=road_node_id,
                        type=EdgeType.CARES_ABOUT
                    ))

    def _load_known_events(self) -> None:
        """加载已知事件"""
        events = [
            EventNode(
                event_id="salzburg_festival_2026",
                name="Salzburg Festival 2026",
                event_type="festival",
                start_date="2026-07-18",
                end_date="2026-08-31",
                impact_level="high",
                affected_roads=["A8", "A93"]
            ),
            EventNode(
                event_id="oktoberfest_2026",
                name="Oktoberfest 2026",
                event_type="festival",
                start_date="2026-09-19",
                end_date="2026-10-04",
                impact_level="very_high",
                affected_roads=["A8", "A9", "A94", "A96"]
            ),
            EventNode(
                event_id="summer_holiday_2026",
                name="Bavaria Summer School Holiday",
                event_type="school_holiday",
                start_date="2026-07-27",
                end_date="2026-09-07",
                impact_level="high",
                affected_roads=["A8", "A93"]
            ),
        ]

        for event in events:
            self.graph.add_node(event)

            # 事件影响路段
            for road_id in event.properties.get("affected_roads", []):
                road_node_id = f"road_{road_id}"
                if self.graph.get_node(road_node_id):
                    self.graph.add_edge(Edge(
                        source_id=event.id,
                        target_id=road_node_id,
                        type=EdgeType.AFFECTS,
                        properties={"impact_level": event.properties.get("impact_level")}
                    ))

    def add_prediction(
        self,
        segment_id: str,
        date: str,
        hour: int,
        level: str,
        volume: int = None,
        speed: float = None,
        confidence: float = 0.85
    ) -> bool:
        """添加预测结果到图谱"""
        congestion = CongestionNode(
            segment_id=segment_id,
            date=date,
            hour=hour,
            level=level,
            volume=volume,
            speed_kmh=speed,
            confidence=confidence
        )

        self.graph.add_node(congestion)

        # 连接到路段
        segment_node_id = f"segment_{segment_id}"
        if self.graph.get_node(segment_node_id):
            self.graph.add_edge(Edge(
                source_id=segment_node_id,
                target_id=congestion.id,
                type=EdgeType.PREDICTS
            ))

        # 连接到日期
        date_node_id = f"date_{date}"
        date_node = self.graph.get_node(date_node_id)
        if not date_node:
            dt = datetime.strptime(date, "%Y-%m-%d")
            date_node = DateNode(
                date=dt,
                is_weekend=dt.weekday() >= 5
            )
            self.graph.add_node(date_node)

        self.graph.add_edge(Edge(
            source_id=date_node_id,
            target_id=congestion.id,
            type=EdgeType.TRIGGERS
        ))

        return True

    def query_factors(
        self,
        segment_id: str,
        date: str
    ) -> Dict[str, Any]:
        """查询影响某路段某日的因素"""
        factors = {
            "segment": None,
            "events": [],
            "weather": None,
            "historical_patterns": [],
        }

        # 获取路段信息
        segment_node_id = f"segment_{segment_id}"
        segment = self.graph.get_node(segment_node_id)
        if segment:
            factors["segment"] = segment.to_dict()

        # 查找影响该路段的事件
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        events = self.graph.get_nodes_by_type(NodeType.EVENT)

        for event in events:
            start = datetime.strptime(event.properties["start_date"], "%Y-%m-%d")
            end = datetime.strptime(event.properties["end_date"], "%Y-%m-%d")

            if start <= date_dt <= end:
                # 检查是否影响该路段
                if segment:
                    road_id = segment.properties.get("road_id")
                    if road_id in event.properties.get("affected_roads", []):
                        factors["events"].append(event.to_dict())

        # 查找天气（如果有）
        weather_node_id = f"weather_{date}"
        weather = self.graph.get_node(weather_node_id)
        if weather:
            factors["weather"] = weather.to_dict()

        return factors

    def explain_congestion(
        self,
        segment_id: str,
        date: str,
        hour: int
    ) -> Dict[str, Any]:
        """解释拥堵原因"""
        congestion_id = f"congestion_{segment_id}_{date}_{hour:02d}"
        congestion = self.graph.get_node(congestion_id)

        if not congestion:
            return {"error": "No congestion data found"}

        # 获取相关因素
        factors = self.query_factors(segment_id, date)

        # 构建解释
        explanation = {
            "congestion": congestion.to_dict(),
            "factors": factors,
            "reasoning": [],
        }

        # 生成推理链
        if factors["events"]:
            for event in factors["events"]:
                explanation["reasoning"].append({
                    "factor": "event",
                    "name": event["properties"]["name"],
                    "impact": event["properties"]["impact_level"],
                    "chain": f"Event '{event['properties']['name']}' → affects {segment_id} → causes {congestion.properties['level']} congestion"
                })

        segment = factors.get("segment")
        if segment and segment["properties"].get("is_bottleneck"):
            explanation["reasoning"].append({
                "factor": "bottleneck",
                "name": segment["properties"]["name"],
                "impact": "structural",
                "chain": f"Segment '{segment['properties']['name']}' is a known bottleneck → reduced capacity → congestion"
            })

        return explanation

    def get_user_relevant_info(
        self,
        user_type: str,
        date: str,
        road: str = "A8"
    ) -> Dict[str, Any]:
        """获取与用户相关的信息"""
        user_node_id = f"user_{user_type}"
        user = self.graph.get_node(user_node_id)

        if not user:
            return {"error": f"Unknown user type: {user_type}"}

        # 获取用户关心的路段
        road_node_id = f"road_{road}"
        road_node = self.graph.get_node(road_node_id)

        # 获取路段列表
        segments = []
        if road_node:
            neighbors = self.graph.get_neighbors(road_node_id, EdgeType.CONTAINS)
            segments = [n[0].to_dict() for n in neighbors]

        # 获取相关事件
        factors = self.query_factors(segments[0]["properties"]["segment_id"] if segments else "", date)

        return {
            "user_profile": user.to_dict(),
            "road": road_node.to_dict() if road_node else None,
            "segments": segments,
            "events": factors.get("events", []),
            "priorities": user.properties.get("priorities", []),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计"""
        return self.graph.get_statistics()
