"""
Graph RAG Entities
知识图谱的节点和边定义
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class NodeType(Enum):
    """节点类型"""
    ROAD = "road"              # 高速公路
    SEGMENT = "segment"        # 路段/瓶颈
    DATE = "date"              # 日期
    EVENT = "event"            # 假期/活动
    WEATHER = "weather"        # 天气
    CONGESTION = "congestion"  # 拥堵等级
    USER = "user"              # 用户画像


class EdgeType(Enum):
    """边类型"""
    CONTAINS = "contains"      # 高速包含路段
    PASSES_THROUGH = "passes_through"  # 经过
    TRIGGERS = "triggers"      # 日期触发事件
    AFFECTS = "affects"        # 影响
    PREDICTS = "predicts"      # 预测
    CARES_ABOUT = "cares_about"  # 用户关心


@dataclass
class Node:
    """图节点基类"""
    id: str
    type: NodeType
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "properties": self.properties,
        }


@dataclass
class Edge:
    """图边"""
    source_id: str
    target_id: str
    type: EdgeType
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.type.value,
            "properties": self.properties,
            "weight": self.weight,
        }


@dataclass
class RoadNode(Node):
    """高速公路节点"""
    def __init__(
        self,
        road_id: str,
        name: str,
        total_length_km: float,
        start_point: str,
        end_point: str,
        **kwargs
    ):
        super().__init__(
            id=f"road_{road_id}",
            type=NodeType.ROAD,
            properties={
                "road_id": road_id,
                "name": name,
                "total_length_km": total_length_km,
                "start_point": start_point,
                "end_point": end_point,
                **kwargs
            }
        )


@dataclass
class SegmentNode(Node):
    """路段/瓶颈节点"""
    def __init__(
        self,
        segment_id: str,
        road_id: str,
        name: str,
        km_start: float,
        km_end: float,
        is_bottleneck: bool = False,
        capacity: int = 4000,
        **kwargs
    ):
        super().__init__(
            id=f"segment_{segment_id}",
            type=NodeType.SEGMENT,
            properties={
                "segment_id": segment_id,
                "road_id": road_id,
                "name": name,
                "km_start": km_start,
                "km_end": km_end,
                "is_bottleneck": is_bottleneck,
                "capacity": capacity,
                **kwargs
            }
        )


@dataclass
class DateNode(Node):
    """日期节点"""
    def __init__(
        self,
        date: datetime,
        is_weekend: bool = False,
        is_holiday: bool = False,
        season: str = "spring",
        **kwargs
    ):
        date_str = date.strftime("%Y-%m-%d")
        super().__init__(
            id=f"date_{date_str}",
            type=NodeType.DATE,
            properties={
                "date": date_str,
                "year": date.year,
                "month": date.month,
                "day": date.day,
                "weekday": date.weekday(),
                "weekday_name": date.strftime("%A"),
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "season": season,
                **kwargs
            }
        )


@dataclass
class EventNode(Node):
    """假期/活动节点"""
    def __init__(
        self,
        event_id: str,
        name: str,
        event_type: str,  # holiday, festival, sports, construction
        start_date: str,
        end_date: str = None,
        impact_level: str = "moderate",
        affected_roads: List[str] = None,
        **kwargs
    ):
        super().__init__(
            id=f"event_{event_id}",
            type=NodeType.EVENT,
            properties={
                "event_id": event_id,
                "name": name,
                "event_type": event_type,
                "start_date": start_date,
                "end_date": end_date or start_date,
                "impact_level": impact_level,
                "affected_roads": affected_roads or [],
                **kwargs
            }
        )


@dataclass
class WeatherNode(Node):
    """天气节点"""
    def __init__(
        self,
        date: str,
        condition: str,  # clear, cloudy, rain, snow, etc.
        temperature_c: float = None,
        precipitation_mm: float = 0,
        visibility_km: float = 10,
        **kwargs
    ):
        super().__init__(
            id=f"weather_{date}",
            type=NodeType.WEATHER,
            properties={
                "date": date,
                "condition": condition,
                "temperature_c": temperature_c,
                "precipitation_mm": precipitation_mm,
                "visibility_km": visibility_km,
                **kwargs
            }
        )


@dataclass
class CongestionNode(Node):
    """拥堵等级节点"""
    def __init__(
        self,
        segment_id: str,
        date: str,
        hour: int,
        level: str,  # smooth, light, moderate, heavy, critical
        volume: int = None,
        speed_kmh: float = None,
        confidence: float = 1.0,
        **kwargs
    ):
        super().__init__(
            id=f"congestion_{segment_id}_{date}_{hour:02d}",
            type=NodeType.CONGESTION,
            properties={
                "segment_id": segment_id,
                "date": date,
                "hour": hour,
                "level": level,
                "volume": volume,
                "speed_kmh": speed_kmh,
                "confidence": confidence,
                **kwargs
            }
        )


@dataclass
class UserNode(Node):
    """用户画像节点"""
    def __init__(
        self,
        user_type: str,  # tourist, resident, logistics, tourism_business, authority
        description: str,
        priorities: List[str] = None,
        typical_routes: List[str] = None,
        **kwargs
    ):
        super().__init__(
            id=f"user_{user_type}",
            type=NodeType.USER,
            properties={
                "user_type": user_type,
                "description": description,
                "priorities": priorities or [],
                "typical_routes": typical_routes or [],
                **kwargs
            }
        )
