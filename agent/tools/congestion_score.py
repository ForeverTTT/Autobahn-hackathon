"""
拥堵分数计算工具
融合多个因素计算综合拥堵指数
"""
from dataclasses import dataclass
from typing import Dict, Tuple

from ..models import CongestionLevel


@dataclass
class TrafficInput:
    """交通输入数据"""
    kfz_h: float      # 总车流量
    sv_h: float       # 重车流量
    v_kfz: float      # 平均车速 km/h


@dataclass
class RoadInput:
    """道路输入数据"""
    capacity: float = 4000       # 道路容量
    free_flow_speed: float = 130 # 自由流速度
    is_bottleneck: bool = False  # 是否瓶颈路段


@dataclass
class ExternalInput:
    """外部因素输入"""
    is_weekend: bool = False
    is_holiday: bool = False
    is_school_holiday: bool = False
    is_peak_hour: bool = False
    weather_impact: float = 0    # 0-1, 0=无影响


@dataclass
class CongestionResult:
    """拥堵计算结果"""
    total_score: float           # 总分 0-100
    level: CongestionLevel       # 拥堵等级
    color: str                   # 颜色代码
    components: Dict[str, float] # 分项得分


# 权重配置
WEIGHTS = {
    "traffic": 0.25,    # 流量因子
    "speed": 0.30,      # 速度因子
    "capacity": 0.25,   # 容量因子
    "external": 0.20,   # 外部因子
}


def calculate_congestion(
    traffic: TrafficInput,
    road: RoadInput = None,
    external: ExternalInput = None
) -> CongestionResult:
    """
    计算拥堵分数

    Args:
        traffic: 交通数据
        road: 道路数据
        external: 外部因素

    Returns:
        CongestionResult
    """
    road = road or RoadInput()
    external = external or ExternalInput()

    # 1. 流量因子 (0-100)
    volume_ratio = traffic.kfz_h / road.capacity
    traffic_score = min(100, volume_ratio * 100)

    # 2. 速度因子 (0-100)
    speed_ratio = traffic.v_kfz / road.free_flow_speed
    speed_score = max(0, (1 - speed_ratio) * 100)

    # 3. 容量因子 (0-100)
    capacity_score = 0
    if road.is_bottleneck:
        capacity_score += 20
    if traffic.sv_h > 0:
        heavy_ratio = traffic.sv_h / traffic.kfz_h
        capacity_score += heavy_ratio * 50
    capacity_score = min(100, capacity_score)

    # 4. 外部因子 (0-100)
    external_score = 0
    if external.is_weekend:
        external_score += 10
    if external.is_holiday:
        external_score += 25
    if external.is_school_holiday:
        external_score += 15
    if external.is_peak_hour:
        external_score += 20
    external_score += external.weather_impact * 30
    external_score = min(100, external_score)

    # 加权总分
    total_score = (
        WEIGHTS["traffic"] * traffic_score +
        WEIGHTS["speed"] * speed_score +
        WEIGHTS["capacity"] * capacity_score +
        WEIGHTS["external"] * external_score
    )

    # 确定等级
    level, color = _score_to_level(total_score)

    return CongestionResult(
        total_score=round(total_score, 1),
        level=level,
        color=color,
        components={
            "traffic": round(traffic_score, 1),
            "speed": round(speed_score, 1),
            "capacity": round(capacity_score, 1),
            "external": round(external_score, 1),
        }
    )


def _score_to_level(score: float) -> Tuple[CongestionLevel, str]:
    """分数转等级"""
    if score < 20:
        return CongestionLevel.SMOOTH, "#22c55e"    # 绿色
    elif score < 40:
        return CongestionLevel.LIGHT, "#eab308"     # 黄色
    elif score < 60:
        return CongestionLevel.MODERATE, "#f97316"  # 橙色
    elif score < 80:
        return CongestionLevel.HEAVY, "#ef4444"     # 红色
    else:
        return CongestionLevel.CRITICAL, "#991b1b"  # 深红


def score_to_stress_index(score: float) -> int:
    """拥堵分数转压力指数 (1-10)"""
    return min(10, max(1, int(score / 10) + 1))
