"""
数据模型定义
低耦合：所有数据结构集中在此，其他模块只依赖此文件
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime


# ============ 用户类型 ============

class UserType(str, Enum):
    """用户类型枚举"""
    TRAVELER = "traveler"      # 👨‍👩‍👧 游客/旅行者
    RESIDENT = "resident"      # 🏠 本地居民
    LOGISTICS = "logistics"    # 🚚 物流运输
    TOURISM = "tourism"        # 🏨 旅游业者
    AUTHORITY = "authority"    # 🚦 交通管理部门


# ============ 拥堵等级 ============

class CongestionLevel(str, Enum):
    """拥堵等级"""
    SMOOTH = "smooth"        # 畅通
    LIGHT = "light"          # 轻微
    MODERATE = "moderate"    # 中等
    HEAVY = "heavy"          # 严重
    CRITICAL = "critical"    # 拥堵


# ============ 预测数据 ============

@dataclass
class HourlyPrediction:
    """小时级预测数据"""
    hour: int
    kfz_h_p10: float          # 流量 P10
    kfz_h_p50: float          # 流量 P50 (中位数)
    kfz_h_p90: float          # 流量 P90
    sv_h: float               # 重车流量
    v_kfz: float              # 平均车速 km/h
    congestion_score: float   # 拥堵分数 0-100
    congestion_level: CongestionLevel


@dataclass
class DailyForecast:
    """日度预测汇总"""
    date: str
    road: str
    site_id: str
    predictions: List[HourlyPrediction]
    peak_hour: int
    avg_congestion_score: float
    total_volume: int


# ============ 外部因素 ============

@dataclass
class ExternalFactor:
    """外部影响因素"""
    type: str                 # weather, holiday, event, construction, season
    name: str
    description: str
    impact: str               # low, moderate, high, very_high
    source: str = "context"   # context (离线) / search (实时)


# ============ 出行方案 ============

@dataclass
class TravelOption:
    """出行方案"""
    departure_time: str       # 出发时间 HH:MM
    arrival_time: str         # 预计到达时间
    travel_time_min: int      # 预计行程时间（分钟）
    delay_min: int            # 预计延误（分钟）
    congestion_score: float   # 综合拥堵指数
    stress_index: int         # 出行压力指数 1-10
    recommendation: str       # 推荐理由


@dataclass
class TravelPlan:
    """完整出行计划"""
    route_name: str
    origin: str
    destination: str
    date: str
    user_type: UserType
    options: List[TravelOption]
    best_option: TravelOption
    external_factors: List[ExternalFactor]
    personalized_advice: str


# ============ Agent 请求/响应 ============

@dataclass
class AgentRequest:
    """Agent 请求"""
    query: str
    date: str
    road: str = "A8"
    site_id: Optional[str] = None
    hours: List[int] = field(default_factory=lambda: list(range(6, 22)))
    user_type: UserType = UserType.TRAVELER
    destination: Optional[str] = None


@dataclass
class AgentResponse:
    """Agent 响应"""
    success: bool
    data: Dict[str, Any]
    message: str = ""


# ============ 路线定义 ============

@dataclass
class RouteSegment:
    """路段"""
    name: str
    road: str
    distance_km: float
    free_flow_time_min: float
    sites: List[str]


@dataclass
class Route:
    """完整路线"""
    id: str
    name: str
    origin: str
    destination: str
    segments: List[RouteSegment]
    total_distance_km: float
    free_flow_time_min: float


# ============ 预定义路线 ============

ROUTES: Dict[str, Route] = {
    "munich_salzburg": Route(
        id="munich_salzburg",
        name="慕尼黑 → 萨尔茨堡 (A8)",
        origin="München",
        destination="Salzburg",
        segments=[
            RouteSegment("München → Rosenheim", "A8", 65, 35, ["A8_Mch_MQB25_Mch_H"]),
            RouteSegment("Rosenheim → Salzburg", "A8", 75, 45, ["A8_Sbg_MQQ245_Sbg_H"]),
        ],
        total_distance_km=140,
        free_flow_time_min=80
    ),
    "munich_innsbruck": Route(
        id="munich_innsbruck",
        name="慕尼黑 → 因斯布鲁克 (A8+A93)",
        origin="München",
        destination="Innsbruck",
        segments=[
            RouteSegment("München → Rosenheim", "A8", 65, 35, ["A8_Mch_MQB25_Mch_H"]),
            RouteSegment("Rosenheim → Kufstein", "A93", 45, 30, ["A93_Ro_MQDZ_AD_Inntal_Ro"]),
            RouteSegment("Kufstein → Innsbruck", "A93", 40, 25, ["A93_Kff_MQDZ_Kiefersfelden_Kff"]),
        ],
        total_distance_km=150,
        free_flow_time_min=90
    ),
}


# ============ 用户画像 ============

USER_PROFILES: Dict[UserType, Dict[str, Any]] = {
    UserType.TRAVELER: {
        "emoji": "👨‍👩‍👧",
        "priorities": ["舒适体验", "最佳时间", "避开拥堵"],
        "style": "推荐最佳出发日期和时间，确保旅途轻松愉快",
        "tips": ["建议携带足够的水和零食", "可在 Chiemsee 服务区休息"]
    },
    UserType.RESIDENT: {
        "emoji": "🏠",
        "priorities": ["避开高峰", "快速通勤"],
        "style": "帮助避开本地交通影响，优化日常出行",
        "tips": ["避开 07:00-09:00 和 16:00-18:00 高峰时段"]
    },
    UserType.LOGISTICS: {
        "emoji": "🚚",
        "priorities": ["准时送达", "避免延误"],
        "style": "优化运输时间，降低延误风险",
        "tips": ["建议 06:00 前出发", "注意大车限速路段"]
    },
    UserType.TOURISM: {
        "emoji": "🏨",
        "priorities": ["客流预测", "运营调整"],
        "style": "预测游客高峰时段，帮助调整运营安排",
        "tips": ["关注周末和假期客流高峰"]
    },
    UserType.AUTHORITY: {
        "emoji": "🚦",
        "priorities": ["交通管控", "提前预警"],
        "style": "提前制定交通管理措施，发布公众建议",
        "tips": ["关注瓶颈路段实时监控", "考虑启动可变限速"]
    },
}
