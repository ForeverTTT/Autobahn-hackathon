"""
Congestion Score Calculator
德国高速公路拥堵评分计算器

融合多源数据计算综合拥堵评分 (0-100)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import math


class CongestionLevel(Enum):
    """拥堵等级"""
    SMOOTH = "smooth"       # 0-20: 畅通
    LIGHT = "light"         # 20-40: 轻微拥堵
    MODERATE = "moderate"   # 40-60: 中度拥堵
    HEAVY = "heavy"         # 60-80: 严重拥堵
    CRITICAL = "critical"   # 80-100: 极度拥堵


@dataclass
class TrafficData:
    """交通流量数据"""
    kfz_h: float        # 小时总车流量 (辆/h)
    sv_h: float = 0     # 小时重型车流量 (辆/h)
    v_kfz: float = 120  # 平均车速 (km/h)


@dataclass
class RoadInfo:
    """道路信息"""
    road_id: str            # 道路ID (A8, A93)
    segment_id: str         # 路段ID
    capacity: int = 4000    # 设计容量 (辆/h)
    lanes: int = 3          # 车道数
    speed_limit: int = 130  # 限速 (km/h)
    is_bottleneck: bool = False  # 是否为瓶颈路段


@dataclass
class ExternalFactors:
    """外部影响因素"""
    # 时间因素
    is_weekend: bool = False
    is_friday_afternoon: bool = False
    is_sunday_afternoon: bool = False
    is_peak_hour: bool = False      # 7-9 或 16-18

    # 假期因素
    is_public_holiday: bool = False
    is_school_holiday: bool = False
    holiday_type: str = ""          # 假期类型

    # 天气因素
    weather: str = "clear"          # clear, cloudy, rain, heavy_rain, snow, ice
    temperature_c: float = 20
    visibility_km: float = 10

    # 活动因素
    has_major_event: bool = False
    event_name: str = ""
    event_impact: str = "none"      # none, low, moderate, high, very_high

    # 施工因素
    has_construction: bool = False
    lanes_closed: int = 0
    construction_impact: str = "none"


@dataclass
class CongestionScore:
    """拥堵评分结果"""
    total_score: float          # 总分 0-100
    level: CongestionLevel      # 拥堵等级
    level_name: str             # 等级名称
    color: str                  # 颜色代码

    # 分项得分
    traffic_score: float        # 流量得分
    speed_score: float          # 速度得分
    capacity_score: float       # 容量利用率得分
    external_score: float       # 外部因素得分

    # 详细信息
    factors: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""


class CongestionScoreCalculator:
    """
    拥堵评分计算器

    计算公式:
    Total Score = w1 * Traffic Score
                + w2 * Speed Score
                + w3 * Capacity Score
                + w4 * External Score

    权重:
    - Traffic Score:  25% (基于流量绝对值)
    - Speed Score:    30% (基于速度下降比例)
    - Capacity Score: 25% (基于容量利用率)
    - External Score: 20% (基于外部因素)
    """

    # 权重配置
    WEIGHTS = {
        "traffic": 0.25,
        "speed": 0.30,
        "capacity": 0.25,
        "external": 0.20,
    }

    # 流量阈值 (辆/小时)
    TRAFFIC_THRESHOLDS = {
        "smooth": 800,
        "light": 1200,
        "moderate": 1600,
        "heavy": 2000,
        "critical": 2500,
    }

    # 速度阈值 (km/h)
    SPEED_THRESHOLDS = {
        "smooth": 100,      # >= 100 km/h
        "light": 80,        # 80-100 km/h
        "moderate": 60,     # 60-80 km/h
        "heavy": 40,        # 40-60 km/h
        "critical": 20,     # < 40 km/h
    }

    # 天气影响系数
    WEATHER_FACTORS = {
        "clear": 0,
        "cloudy": 2,
        "light_rain": 8,
        "rain": 15,
        "heavy_rain": 25,
        "snow": 35,
        "ice": 50,
    }

    # 活动影响系数
    EVENT_FACTORS = {
        "none": 0,
        "low": 5,
        "moderate": 15,
        "high": 25,
        "very_high": 40,
    }

    def __init__(self):
        self.factors_log: List[Dict[str, Any]] = []

    def calculate(
        self,
        traffic: TrafficData,
        road: RoadInfo,
        external: ExternalFactors = None
    ) -> CongestionScore:
        """
        计算综合拥堵评分

        Args:
            traffic: 交通流量数据
            road: 道路信息
            external: 外部影响因素

        Returns:
            CongestionScore: 拥堵评分结果
        """
        self.factors_log = []
        external = external or ExternalFactors()

        # 1. 计算流量得分 (0-100)
        traffic_score = self._calculate_traffic_score(traffic.kfz_h)

        # 2. 计算速度得分 (0-100)
        speed_score = self._calculate_speed_score(traffic.v_kfz, road.speed_limit)

        # 3. 计算容量利用率得分 (0-100)
        capacity_score = self._calculate_capacity_score(
            traffic.kfz_h, road.capacity, traffic.sv_h
        )

        # 4. 计算外部因素得分 (0-100)
        external_score = self._calculate_external_score(external, road)

        # 5. 加权汇总
        total_score = (
            self.WEIGHTS["traffic"] * traffic_score +
            self.WEIGHTS["speed"] * speed_score +
            self.WEIGHTS["capacity"] * capacity_score +
            self.WEIGHTS["external"] * external_score
        )

        # 限制在 0-100
        total_score = max(0, min(100, total_score))

        # 6. 确定拥堵等级
        level, level_name, color = self._get_congestion_level(total_score)

        # 7. 生成建议
        recommendation = self._generate_recommendation(
            total_score, level, traffic, external
        )

        return CongestionScore(
            total_score=round(total_score, 1),
            level=level,
            level_name=level_name,
            color=color,
            traffic_score=round(traffic_score, 1),
            speed_score=round(speed_score, 1),
            capacity_score=round(capacity_score, 1),
            external_score=round(external_score, 1),
            factors=self.factors_log,
            recommendation=recommendation,
        )

    def _calculate_traffic_score(self, kfz_h: float) -> float:
        """
        计算流量得分

        流量越高，得分越高（表示越拥堵）
        """
        if kfz_h < self.TRAFFIC_THRESHOLDS["smooth"]:
            score = kfz_h / self.TRAFFIC_THRESHOLDS["smooth"] * 20
        elif kfz_h < self.TRAFFIC_THRESHOLDS["light"]:
            score = 20 + (kfz_h - 800) / 400 * 20
        elif kfz_h < self.TRAFFIC_THRESHOLDS["moderate"]:
            score = 40 + (kfz_h - 1200) / 400 * 20
        elif kfz_h < self.TRAFFIC_THRESHOLDS["heavy"]:
            score = 60 + (kfz_h - 1600) / 400 * 20
        else:
            score = 80 + min(20, (kfz_h - 2000) / 500 * 20)

        self.factors_log.append({
            "type": "traffic_volume",
            "value": kfz_h,
            "unit": "vehicles/h",
            "score": round(score, 1),
            "weight": self.WEIGHTS["traffic"],
            "contribution": round(score * self.WEIGHTS["traffic"], 1),
        })

        return score

    def _calculate_speed_score(self, v_kfz: float, speed_limit: int) -> float:
        """
        计算速度得分

        速度越低，得分越高（表示越拥堵）
        """
        # 速度占限速的比例
        speed_ratio = v_kfz / speed_limit

        if speed_ratio >= 0.85:  # >= 85% 限速
            score = (1 - speed_ratio) / 0.15 * 20
        elif speed_ratio >= 0.65:  # 65-85% 限速
            score = 20 + (0.85 - speed_ratio) / 0.20 * 20
        elif speed_ratio >= 0.50:  # 50-65% 限速
            score = 40 + (0.65 - speed_ratio) / 0.15 * 20
        elif speed_ratio >= 0.35:  # 35-50% 限速
            score = 60 + (0.50 - speed_ratio) / 0.15 * 20
        else:  # < 35% 限速
            score = 80 + min(20, (0.35 - speed_ratio) / 0.20 * 20)

        self.factors_log.append({
            "type": "average_speed",
            "value": v_kfz,
            "unit": "km/h",
            "speed_ratio": round(speed_ratio, 2),
            "score": round(score, 1),
            "weight": self.WEIGHTS["speed"],
            "contribution": round(score * self.WEIGHTS["speed"], 1),
        })

        return score

    def _calculate_capacity_score(
        self,
        kfz_h: float,
        capacity: int,
        sv_h: float
    ) -> float:
        """
        计算容量利用率得分

        考虑:
        1. 基础流量/容量比
        2. 大车占比（大车占用更多道路空间）
        """
        # 基础利用率
        base_ratio = kfz_h / capacity

        # 大车修正（每辆大车约等于2辆小车）
        lkw_ratio = sv_h / kfz_h if kfz_h > 0 else 0
        effective_ratio = base_ratio * (1 + lkw_ratio * 0.5)

        # 转换为得分
        if effective_ratio < 0.5:
            score = effective_ratio / 0.5 * 20
        elif effective_ratio < 0.7:
            score = 20 + (effective_ratio - 0.5) / 0.2 * 20
        elif effective_ratio < 0.85:
            score = 40 + (effective_ratio - 0.7) / 0.15 * 20
        elif effective_ratio < 1.0:
            score = 60 + (effective_ratio - 0.85) / 0.15 * 20
        else:  # 超过容量
            score = 80 + min(20, (effective_ratio - 1.0) / 0.3 * 20)

        self.factors_log.append({
            "type": "capacity_utilization",
            "base_ratio": round(base_ratio, 2),
            "lkw_ratio": round(lkw_ratio, 2),
            "effective_ratio": round(effective_ratio, 2),
            "score": round(score, 1),
            "weight": self.WEIGHTS["capacity"],
            "contribution": round(score * self.WEIGHTS["capacity"], 1),
        })

        return score

    def _calculate_external_score(
        self,
        external: ExternalFactors,
        road: RoadInfo
    ) -> float:
        """
        计算外部因素得分

        综合考虑:
        1. 时间因素（周末、高峰时段）
        2. 假期因素
        3. 天气因素
        4. 活动因素
        5. 施工因素
        6. 瓶颈路段
        """
        score = 0
        factors = []

        # 1. 时间因素
        time_score = 0
        if external.is_peak_hour:
            time_score += 10
            factors.append({"name": "Peak Hour", "impact": 10})
        if external.is_friday_afternoon:
            time_score += 8
            factors.append({"name": "Friday Afternoon", "impact": 8})
        if external.is_sunday_afternoon:
            time_score += 8
            factors.append({"name": "Sunday Afternoon", "impact": 8})
        if external.is_weekend and not (external.is_friday_afternoon or external.is_sunday_afternoon):
            time_score += 3
            factors.append({"name": "Weekend", "impact": 3})

        score += min(15, time_score)  # 时间因素最高贡献15分

        # 2. 假期因素
        holiday_score = 0
        if external.is_public_holiday:
            holiday_score += 15
            factors.append({"name": f"Public Holiday ({external.holiday_type})", "impact": 15})
        if external.is_school_holiday:
            holiday_score += 10
            factors.append({"name": "School Holiday", "impact": 10})

        score += min(20, holiday_score)  # 假期因素最高贡献20分

        # 3. 天气因素
        weather_score = self.WEATHER_FACTORS.get(external.weather, 0)
        if weather_score > 0:
            factors.append({"name": f"Weather ({external.weather})", "impact": weather_score})
        score += min(25, weather_score)  # 天气因素最高贡献25分

        # 4. 活动因素
        event_score = self.EVENT_FACTORS.get(external.event_impact, 0)
        if event_score > 0:
            factors.append({"name": f"Event ({external.event_name})", "impact": event_score})
        score += min(20, event_score)  # 活动因素最高贡献20分

        # 5. 施工因素
        if external.has_construction:
            construction_score = external.lanes_closed * 12
            factors.append({"name": f"Construction ({external.lanes_closed} lanes closed)", "impact": construction_score})
            score += min(25, construction_score)  # 施工因素最高贡献25分

        # 6. 瓶颈路段
        if road.is_bottleneck:
            bottleneck_score = 8
            factors.append({"name": "Bottleneck Segment", "impact": bottleneck_score})
            score += bottleneck_score

        # 归一化到 0-100
        score = min(100, score)

        self.factors_log.append({
            "type": "external_factors",
            "details": factors,
            "score": round(score, 1),
            "weight": self.WEIGHTS["external"],
            "contribution": round(score * self.WEIGHTS["external"], 1),
        })

        return score

    def _get_congestion_level(
        self,
        score: float
    ) -> Tuple[CongestionLevel, str, str]:
        """
        根据得分确定拥堵等级
        """
        if score < 20:
            return CongestionLevel.SMOOTH, "Smooth", "#22c55e"  # 绿色
        elif score < 40:
            return CongestionLevel.LIGHT, "Light", "#eab308"    # 黄色
        elif score < 60:
            return CongestionLevel.MODERATE, "Moderate", "#f97316"  # 橙色
        elif score < 80:
            return CongestionLevel.HEAVY, "Heavy", "#ef4444"    # 红色
        else:
            return CongestionLevel.CRITICAL, "Critical", "#1f2937"  # 黑色

    def _generate_recommendation(
        self,
        score: float,
        level: CongestionLevel,
        traffic: TrafficData,
        external: ExternalFactors
    ) -> str:
        """
        生成建议
        """
        recommendations = []

        if level == CongestionLevel.SMOOTH:
            recommendations.append("✅ Traffic is flowing smoothly. Good conditions for travel.")

        elif level == CongestionLevel.LIGHT:
            recommendations.append("🟡 Light traffic. Minor delays possible.")
            if external.is_peak_hour:
                recommendations.append("Consider traveling outside peak hours for best experience.")

        elif level == CongestionLevel.MODERATE:
            recommendations.append("🟠 Moderate congestion expected.")
            if traffic.v_kfz < 80:
                recommendations.append(f"Average speed reduced to {traffic.v_kfz:.0f} km/h.")
            recommendations.append("Plan extra travel time.")

        elif level == CongestionLevel.HEAVY:
            recommendations.append("🔴 Heavy congestion. Significant delays expected.")
            recommendations.append("Consider alternative departure times or routes.")
            if external.has_major_event:
                recommendations.append(f"Impact from: {external.event_name}")

        else:  # CRITICAL
            recommendations.append("⚫ Critical congestion! Major delays expected.")
            recommendations.append("Strongly recommend postponing travel or using alternative routes.")
            if external.has_construction:
                recommendations.append(f"Construction: {external.lanes_closed} lane(s) closed.")

        return " ".join(recommendations)


# ============ 便捷函数 ============

def calculate_congestion_score(
    kfz_h: float,
    v_kfz: float = 120,
    sv_h: float = 0,
    capacity: int = 4000,
    **kwargs
) -> CongestionScore:
    """
    快速计算拥堵评分

    Args:
        kfz_h: 小时车流量
        v_kfz: 平均车速 (km/h)
        sv_h: 重型车流量
        capacity: 道路容量
        **kwargs: 其他外部因素

    Returns:
        CongestionScore
    """
    calculator = CongestionScoreCalculator()

    traffic = TrafficData(kfz_h=kfz_h, sv_h=sv_h, v_kfz=v_kfz)
    road = RoadInfo(
        road_id=kwargs.get("road_id", "A8"),
        segment_id=kwargs.get("segment_id", "default"),
        capacity=capacity,
        is_bottleneck=kwargs.get("is_bottleneck", False),
    )

    external = ExternalFactors(
        is_weekend=kwargs.get("is_weekend", False),
        is_peak_hour=kwargs.get("is_peak_hour", False),
        is_public_holiday=kwargs.get("is_public_holiday", False),
        is_school_holiday=kwargs.get("is_school_holiday", False),
        weather=kwargs.get("weather", "clear"),
        has_major_event=kwargs.get("has_major_event", False),
        event_name=kwargs.get("event_name", ""),
        event_impact=kwargs.get("event_impact", "none"),
        has_construction=kwargs.get("has_construction", False),
        lanes_closed=kwargs.get("lanes_closed", 0),
    )

    return calculator.calculate(traffic, road, external)


def get_congestion_level_simple(kfz_h: float, v_kfz: float = 120) -> str:
    """
    简单版本：只根据流量和速度判断拥堵等级

    Returns:
        str: smooth/light/moderate/heavy/critical
    """
    score = calculate_congestion_score(kfz_h, v_kfz)
    return score.level.value


# ============ 示例 ============

def example():
    """使用示例"""
    print("=" * 60)
    print("Congestion Score Calculator - Examples")
    print("=" * 60)

    # 示例1: 正常工作日
    print("\n📊 Example 1: Normal Weekday Morning")
    score1 = calculate_congestion_score(
        kfz_h=1000,
        v_kfz=110,
        sv_h=150,
        is_peak_hour=True,
    )
    print(f"   Score: {score1.total_score} ({score1.level_name})")
    print(f"   Color: {score1.color}")
    print(f"   {score1.recommendation}")

    # 示例2: 周五下午 + 学校假期
    print("\n📊 Example 2: Friday Afternoon + School Holiday")
    score2 = calculate_congestion_score(
        kfz_h=1800,
        v_kfz=75,
        sv_h=200,
        is_peak_hour=True,
        is_weekend=True,
        is_school_holiday=True,
    )
    print(f"   Score: {score2.total_score} ({score2.level_name})")
    print(f"   {score2.recommendation}")

    # 示例3: 暴雨 + 施工
    print("\n📊 Example 3: Heavy Rain + Construction")
    score3 = calculate_congestion_score(
        kfz_h=1500,
        v_kfz=50,
        sv_h=180,
        weather="heavy_rain",
        has_construction=True,
        lanes_closed=1,
    )
    print(f"   Score: {score3.total_score} ({score3.level_name})")
    print(f"   {score3.recommendation}")

    # 示例4: Oktoberfest 期间
    print("\n📊 Example 4: During Oktoberfest")
    score4 = calculate_congestion_score(
        kfz_h=2200,
        v_kfz=45,
        sv_h=100,
        is_weekend=True,
        has_major_event=True,
        event_name="Oktoberfest",
        event_impact="very_high",
    )
    print(f"   Score: {score4.total_score} ({score4.level_name})")
    print(f"   {score4.recommendation}")

    # 示例5: 查看分项得分
    print("\n📊 Example 5: Detailed Breakdown")
    score5 = calculate_congestion_score(
        kfz_h=1600,
        v_kfz=70,
        sv_h=240,
        capacity=4000,
        is_peak_hour=True,
        weather="rain",
    )
    print(f"   Total Score: {score5.total_score}")
    print(f"   - Traffic Score:  {score5.traffic_score} (weight: 25%)")
    print(f"   - Speed Score:    {score5.speed_score} (weight: 30%)")
    print(f"   - Capacity Score: {score5.capacity_score} (weight: 25%)")
    print(f"   - External Score: {score5.external_score} (weight: 20%)")
    print(f"\n   Factors:")
    for factor in score5.factors:
        print(f"   - {factor['type']}: contribution = {factor['contribution']}")


if __name__ == "__main__":
    example()
