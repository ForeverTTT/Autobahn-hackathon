"""
Travel Assistant - Personalized AI Agent
个性化出行助手

功能：
1. 读取预测数据 + 计算拥堵分数
2. 联网搜索施工/活动信息
3. 针对不同用户类型生成个性化建议
4. 提供完整出行方案对比
"""
import os
import json
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from .data_loader import external_loader, prediction_loader, safe_int
from .congestion_score import (
    CongestionScoreCalculator,
    TrafficData,
    RoadInfo,
    ExternalFactors,
    CongestionLevel
)


# ============ 用户类型定义 ============

class UserType(str, Enum):
    TRAVELER = "traveler"       # 👨‍👩‍👧 游客/旅行者
    RESIDENT = "resident"       # 🏠 本地居民
    LOGISTICS = "logistics"     # 🚚 物流运输
    TOURISM = "tourism"         # 🏨 旅游业者
    AUTHORITY = "authority"     # 🚦 交通管理部门


@dataclass
class UserProfile:
    """用户画像"""
    user_type: UserType
    priorities: List[str]
    concerns: List[str]
    recommendation_style: str


USER_PROFILES = {
    UserType.TRAVELER: UserProfile(
        user_type=UserType.TRAVELER,
        priorities=["舒适体验", "最佳时间", "避开拥堵"],
        concerns=["旅途时间", "沿途风景", "休息站"],
        recommendation_style="推荐最佳出发日期和时间，确保旅途轻松愉快"
    ),
    UserType.RESIDENT: UserProfile(
        user_type=UserType.RESIDENT,
        priorities=["避开高峰", "快速通勤", "本地路况"],
        concerns=["日常通勤影响", "施工绕行", "本地活动"],
        recommendation_style="帮助避开本地交通影响，优化日常出行"
    ),
    UserType.LOGISTICS: UserProfile(
        user_type=UserType.LOGISTICS,
        priorities=["准时送达", "成本控制", "避免延误"],
        concerns=["货运时间窗口", "大车限制", "夜间运输"],
        recommendation_style="优化运输时间，降低延误风险，确保准时交付"
    ),
    UserType.TOURISM: UserProfile(
        user_type=UserType.TOURISM,
        priorities=["客流预测", "运营调整", "高峰准备"],
        concerns=["游客到达时间", "周末/假期高峰", "活动影响"],
        recommendation_style="预测游客高峰时段，帮助调整运营安排"
    ),
    UserType.AUTHORITY: UserProfile(
        user_type=UserType.AUTHORITY,
        priorities=["交通管控", "提前预警", "资源调度"],
        concerns=["拥堵热点", "事故风险", "应急响应"],
        recommendation_style="提前制定交通管理措施，发布公众出行建议"
    ),
}


# ============ 路线定义 ============

@dataclass
class RouteSegment:
    """路段"""
    name: str
    road: str
    distance_km: float
    free_flow_time_min: float  # 自由流时间（分钟）
    sites: List[str]  # 途经站点


@dataclass
class Route:
    """完整路线"""
    name: str
    origin: str
    destination: str
    segments: List[RouteSegment]
    total_distance_km: float
    free_flow_time_min: float


# 预定义路线
ROUTES = {
    "munich_salzburg_a8": Route(
        name="慕尼黑 → 萨尔茨堡 (A8)",
        origin="München",
        destination="Salzburg",
        segments=[
            RouteSegment("München → Rosenheim", "A8", 65, 35, ["A8_Mch_MQB25_Mch_H"]),
            RouteSegment("Rosenheim → Bad Aibling", "A8", 25, 15, ["A8_Mch_MQQ209_Mch_H"]),
            RouteSegment("Bad Aibling → Salzburg", "A8", 50, 30, ["A8_Sbg_MQQ245_Sbg_H"]),
        ],
        total_distance_km=140,
        free_flow_time_min=80
    ),
    "munich_innsbruck_a93": Route(
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


# ============ 出行方案 ============

@dataclass
class TravelOption:
    """出行方案"""
    departure_time: str           # 出发时间 HH:MM
    arrival_time: str             # 预计到达时间
    travel_time_min: int          # 预计行程时间（分钟）
    delay_min: int                # 预计延误（分钟）
    congestion_score: float       # 综合拥堵指数 (0-100)
    congestion_level: str         # 拥堵等级
    stress_index: int             # 出行压力指数 (1-10)
    warnings: List[str]           # 预警信息
    recommendation: str           # 推荐理由


@dataclass
class TravelPlan:
    """完整出行计划"""
    route: Route
    date: str
    user_type: UserType
    options: List[TravelOption]
    best_option: TravelOption
    external_factors: List[Dict[str, Any]]  # 施工/活动等
    personalized_advice: str
    summary: Dict[str, Any]


# ============ 核心助手类 ============

class TravelAssistant:
    """
    个性化出行助手

    功能：
    1. get_traffic_forecast() - 获取交通预测
    2. search_external_factors() - 搜索施工/活动
    3. calculate_travel_options() - 计算出行方案
    4. generate_recommendation() - 生成个性化建议
    """

    def __init__(self):
        self.data_loader = prediction_loader
        self.score_calculator = CongestionScoreCalculator()

    # ============ 工具1: 交通预测 ============

    def get_traffic_forecast(
        self,
        date: str,
        road: str,
        hours: List[int] = None
    ) -> Dict[str, Any]:
        """
        获取交通预测数据

        Args:
            date: 日期 YYYY-MM-DD
            road: 高速公路 A8/A93
            hours: 小时列表，默认 6-22

        Returns:
            预测结果，包含每小时拥堵分数
        """
        hours = hours or list(range(6, 22))

        records = self.data_loader.query(date, road=road, hours=hours)

        if not records:
            # Fallback: 生成模拟数据
            return self._generate_mock_forecast(date, road, hours)

        # 按小时聚合（取第一个站点）
        first_site = records[0]["site_id"]
        site_records = [r for r in records if r["site_id"] == first_site]

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []
        for record in site_records:
            hour = record["hour"]
            kfz_h = record.get("kfz_h_p50", 1000)
            v_kfz = record.get("v_kfz_p50", record.get("v_kfz_pred", 120))
            sv_h = record.get("sv_h_p50", record.get("sv_h_pred", int(kfz_h * 0.1)))

            # 计算拥堵分数
            traffic = TrafficData(kfz_h=kfz_h, sv_h=sv_h, v_kfz=v_kfz)
            road_info = RoadInfo(
                road_id=road,
                segment_id=first_site,
                capacity=4000 if road == "A8" else 3500,
                is_bottleneck=False
            )
            external = ExternalFactors(
                is_weekend=is_weekend,
                is_peak_hour=(7 <= hour <= 9) or (16 <= hour <= 18),
                is_school_holiday=record.get("is_school_holiday", False),
                is_public_holiday=record.get("is_holiday", False),
            )

            result = self.score_calculator.calculate(traffic, road_info, external)

            predictions.append({
                "hour": hour,
                "volume": kfz_h,
                "speed_kmh": round(v_kfz, 1),
                "congestion_score": result.total_score,
                "congestion_level": result.level.value,
                "color": result.color,
            })

        # 找最佳和最差时段
        best_hour = min(predictions, key=lambda x: x["congestion_score"])
        worst_hour = max(predictions, key=lambda x: x["congestion_score"])

        return {
            "date": date,
            "road": road,
            "predictions": predictions,
            "best_hour": best_hour["hour"],
            "worst_hour": worst_hour["hour"],
            "avg_congestion": round(sum(p["congestion_score"] for p in predictions) / len(predictions), 1),
            "data_source": "data_autobahn_csv",
        }

    def _generate_mock_forecast(self, date: str, road: str, hours: List[int]) -> Dict[str, Any]:
        """生成模拟预测（当无数据时）"""
        import numpy as np

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        is_weekend = date_obj.weekday() >= 5

        predictions = []
        for hour in hours:
            # 基于时段的拥堵模式
            if 7 <= hour <= 9:
                base_score = 55 if not is_weekend else 25
            elif 16 <= hour <= 18:
                base_score = 60 if not is_weekend else 35
            elif 10 <= hour <= 15:
                base_score = 35
            else:
                base_score = 20

            # 添加随机波动
            score = base_score + np.random.randint(-5, 10)
            score = max(0, min(100, score))

            level = self._score_to_level(score)

            predictions.append({
                "hour": hour,
                "volume": 800 + int(score * 15),
                "speed_kmh": max(60, 130 - score),
                "congestion_score": score,
                "congestion_level": level,
                "color": self._level_to_color(level),
            })

        best_hour = min(predictions, key=lambda x: x["congestion_score"])
        worst_hour = max(predictions, key=lambda x: x["congestion_score"])

        return {
            "date": date,
            "road": road,
            "predictions": predictions,
            "best_hour": best_hour["hour"],
            "worst_hour": worst_hour["hour"],
            "avg_congestion": round(sum(p["congestion_score"] for p in predictions) / len(predictions), 1),
            "data_source": "mock"
        }

    def _score_to_level(self, score: float) -> str:
        if score < 20: return "smooth"
        elif score < 40: return "light"
        elif score < 60: return "moderate"
        elif score < 80: return "heavy"
        else: return "critical"

    def _level_to_color(self, level: str) -> str:
        colors = {
            "smooth": "#22c55e",
            "light": "#eab308",
            "moderate": "#f97316",
            "heavy": "#ef4444",
            "critical": "#991b1b"
        }
        return colors.get(level, "#6b7280")

    # ============ 工具2: 外部因素搜索 ============

    def search_external_factors(
        self,
        date: str,
        road: str,
        query: str = None
    ) -> List[Dict[str, Any]]:
        """
        搜索外部因素（施工、活动、天气等）

        当前从 data_autobahn 的日级 CSV 表读取。

        Args:
            date: 日期
            road: 高速公路
            query: 搜索关键词

        Returns:
            外部因素列表
        """
        factors = []

        constructions = self._get_construction_data(date, road)
        factors.extend(constructions)

        events = self._get_events_data(date, road)
        factors.extend(events)

        # === 假期信息 ===
        holidays = self._get_holiday_info(date)
        factors.extend(holidays)

        weather = self._get_weather_data(date)
        factors.extend(weather)

        return factors

    def _get_construction_data(self, date: str, road: str) -> List[Dict[str, Any]]:
        """获取施工数据"""
        factors = []
        for row in external_loader.get_construction(date, road):
            factors.append({
                "type": "construction",
                "title": row.get("construction_titles") or "施工影响",
                "location": row.get("active_roads") or road,
                "description": f"施工记录 {row.get('construction_count', 0)} 条，最大关闭车道 {row.get('max_closed_lanes', 0)}",
                "impact": "high" if safe_int(row.get("has_2_plus_0")) else "moderate",
                "time_range": "日级数据",
                "detour": None,
                "data_source": "data_autobahn_csv",
            })
        return factors

    def _get_events_data(self, date: str, road: str) -> List[Dict[str, Any]]:
        """获取活动数据"""
        factors = []
        for row in external_loader.get_events(date, road):
            impact_score = safe_int(row.get("impact_score"))
            factors.append({
                "type": "event",
                "title": row.get("active_event_names") or "特殊活动",
                "location": row.get("active_event_cities") or row.get("nearest_corridor_nodes"),
                "description": f"活动数量 {row.get('active_event_count', 0)}，影响等级 {row.get('max_impact_level') or impact_score}",
                "impact": "high" if impact_score >= 3 else "moderate" if impact_score >= 2 else "light",
                "recommendation": "活动可能影响走廊交通，请避开对应高峰时段",
                "data_source": "data_autobahn_csv",
            })
        return factors

    def _get_holiday_info(self, date: str) -> List[Dict[str, Any]]:
        """获取假期信息"""
        info = external_loader.get_holiday_info(date)
        factors = []
        if info.get("is_holiday"):
            factors.append({
                "type": "holiday",
                "title": info.get("holiday_name") or "公共假期",
                "description": f"公共假期地区数：{info.get('public_holiday_count', 0)}",
                "impact": "high" if info.get("public_holiday_count", 0) >= 2 else "moderate",
                "recommendation": "假期出行高峰，建议提前或延后出发",
                "data_source": "data_autobahn_csv",
            })
        if info.get("is_school_holiday"):
            factors.append({
                "type": "school_holiday",
                "title": "学校假期",
                "description": f"学校假期地区数：{info.get('school_holiday_count', 0)}",
                "impact": "moderate",
                "recommendation": "周末和假期开始/结束日交通压力大",
                "data_source": "data_autobahn_csv",
            })
        return factors

    def _get_weather_data(self, date: str) -> List[Dict[str, Any]]:
        """获取天气数据"""
        info = external_loader.get_weather_info(date)
        if info.get("weather") == "unknown":
            return []
        precip = float(info.get("precip_mm") or 0)
        snow = float(info.get("snowfall_mm") or 0)
        low_vis = int(info.get("low_vis_hours") or 0)
        has_ice = bool(info.get("has_ice_risk"))
        impact = "high" if has_ice or snow > 5 else "moderate" if precip > 10 or low_vis >= 3 else "light"
        if impact == "light" and precip == 0 and snow == 0 and low_vis == 0 and not has_ice:
            return []
        return [{
            "type": "weather",
            "title": f"天气: {info.get('weather')}",
            "description": f"降水 {precip:.1f}mm，降雪 {snow:.1f}mm，低能见度 {low_vis} 小时",
            "impact": impact,
            "data_source": "data_autobahn_csv",
        }]

    # ============ 工具3: 计算出行方案 ============

    def calculate_travel_options(
        self,
        route_id: str,
        date: str,
        departure_hours: List[int] = None
    ) -> List[TravelOption]:
        """
        计算多个出行方案

        Args:
            route_id: 路线ID
            date: 日期
            departure_hours: 候选出发时间列表

        Returns:
            出行方案列表
        """
        route = ROUTES.get(route_id)
        if not route:
            raise ValueError(f"Unknown route: {route_id}")

        departure_hours = departure_hours or [6, 7, 8, 9, 10, 12, 14, 16, 18]

        options = []

        for dep_hour in departure_hours:
            option = self._calculate_single_option(route, date, dep_hour)
            options.append(option)

        return sorted(options, key=lambda x: x.stress_index)

    def _calculate_single_option(
        self,
        route: Route,
        date: str,
        departure_hour: int
    ) -> TravelOption:
        """计算单个出行方案"""
        total_delay = 0
        total_score = 0
        segment_count = 0
        warnings = []

        current_hour = departure_hour

        for segment in route.segments:
            # 获取该路段该时段的预测
            forecast = self.get_traffic_forecast(
                date,
                segment.road,
                hours=[current_hour, current_hour + 1]
            )

            # 取该时段的平均拥堵分数
            preds = forecast.get("predictions", [])
            if preds:
                seg_score = sum(p["congestion_score"] for p in preds) / len(preds)
            else:
                seg_score = 30  # 默认

            total_score += seg_score
            segment_count += 1

            # 计算延误
            delay_factor = seg_score / 100  # 0-1
            segment_delay = segment.free_flow_time_min * delay_factor * 0.5  # 最多增加50%时间
            total_delay += segment_delay

            # 检查警告
            if seg_score >= 60:
                warnings.append(f"⚠️ {segment.name}: 预计拥堵 ({seg_score:.0f}分)")

            # 更新时间
            travel_min = segment.free_flow_time_min + segment_delay
            current_hour += int(travel_min / 60)

        # 计算总分
        avg_score = total_score / segment_count if segment_count > 0 else 50
        total_time = route.free_flow_time_min + total_delay

        # 计算压力指数 (1-10)
        stress = min(10, max(1, int(avg_score / 10)))

        # 生成推荐理由
        if stress <= 3:
            recommendation = "✅ 最佳时段，路况畅通"
        elif stress <= 5:
            recommendation = "👍 较好时段，轻微拥堵"
        elif stress <= 7:
            recommendation = "⚠️ 一般时段，预计有延误"
        else:
            recommendation = "❌ 不推荐，严重拥堵"

        # 计算到达时间
        dep_time = f"{departure_hour:02d}:00"
        arrival_minutes = departure_hour * 60 + int(total_time)
        arrival_hour = arrival_minutes // 60
        arrival_min = arrival_minutes % 60
        arrival_time = f"{arrival_hour:02d}:{arrival_min:02d}"

        return TravelOption(
            departure_time=dep_time,
            arrival_time=arrival_time,
            travel_time_min=int(total_time),
            delay_min=int(total_delay),
            congestion_score=round(avg_score, 1),
            congestion_level=self._score_to_level(avg_score),
            stress_index=stress,
            warnings=warnings,
            recommendation=recommendation,
        )

    # ============ 工具4: 生成个性化建议 ============

    def generate_plan(
        self,
        route_id: str,
        date: str,
        user_type: UserType,
        departure_hours: List[int] = None
    ) -> TravelPlan:
        """
        生成完整出行计划

        Args:
            route_id: 路线ID
            date: 日期
            user_type: 用户类型
            departure_hours: 候选出发时间

        Returns:
            完整出行计划
        """
        route = ROUTES.get(route_id)
        if not route:
            raise ValueError(f"Unknown route: {route_id}")

        profile = USER_PROFILES[user_type]

        # 1. 获取出行方案
        options = self.calculate_travel_options(route_id, date, departure_hours)

        # 2. 根据用户类型选择最佳方案
        best_option = self._select_best_for_user(options, user_type)

        # 3. 搜索外部因素
        external_factors = []
        for segment in route.segments:
            factors = self.search_external_factors(date, segment.road)
            external_factors.extend(factors)
        # 去重
        seen = set()
        unique_factors = []
        for f in external_factors:
            key = f.get("title", "")
            if key not in seen:
                seen.add(key)
                unique_factors.append(f)

        # 4. 生成个性化建议
        advice = self._generate_personalized_advice(
            route, date, user_type, profile, best_option, unique_factors
        )

        # 5. 汇总
        summary = {
            "route": route.name,
            "date": date,
            "user_type": user_type.value,
            "best_departure": best_option.departure_time,
            "estimated_arrival": best_option.arrival_time,
            "estimated_time_min": best_option.travel_time_min,
            "stress_index": best_option.stress_index,
            "external_factors_count": len(unique_factors),
        }

        return TravelPlan(
            route=route,
            date=date,
            user_type=user_type,
            options=options,
            best_option=best_option,
            external_factors=unique_factors,
            personalized_advice=advice,
            summary=summary,
        )

    def _select_best_for_user(
        self,
        options: List[TravelOption],
        user_type: UserType
    ) -> TravelOption:
        """根据用户类型选择最佳方案"""

        if user_type == UserType.LOGISTICS:
            # 物流：优先早出发，避开高峰
            early_options = [o for o in options if int(o.departure_time[:2]) <= 7]
            if early_options:
                return min(early_options, key=lambda x: x.stress_index)

        elif user_type == UserType.TRAVELER:
            # 游客：舒适优先，不必太早
            comfortable_options = [o for o in options if 8 <= int(o.departure_time[:2]) <= 10]
            if comfortable_options:
                return min(comfortable_options, key=lambda x: x.stress_index)

        elif user_type == UserType.RESIDENT:
            # 居民：避开通勤高峰
            off_peak = [o for o in options if int(o.departure_time[:2]) not in [7, 8, 9, 17, 18]]
            if off_peak:
                return min(off_peak, key=lambda x: x.stress_index)

        # 默认：选压力最低的
        return min(options, key=lambda x: x.stress_index)

    def _generate_personalized_advice(
        self,
        route: Route,
        date: str,
        user_type: UserType,
        profile: UserProfile,
        best_option: TravelOption,
        factors: List[Dict[str, Any]]
    ) -> str:
        """生成个性化建议文本"""

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[date_obj.weekday()]

        lines = []

        # 标题
        lines.append(f"## 🚗 {route.name}")
        lines.append(f"**日期**: {date} ({weekday})")
        lines.append(f"**用户类型**: {self._user_type_emoji(user_type)} {user_type.value.title()}")
        lines.append("")

        # 推荐方案
        lines.append("### ✨ 推荐出行方案")
        lines.append(f"- **出发时间**: {best_option.departure_time}")
        lines.append(f"- **预计到达**: {best_option.arrival_time}")
        lines.append(f"- **预计行程**: {best_option.travel_time_min} 分钟 (延误约 {best_option.delay_min} 分钟)")
        lines.append(f"- **出行压力指数**: {'🟢' * (10 - best_option.stress_index)}{'🔴' * best_option.stress_index} ({best_option.stress_index}/10)")
        lines.append("")

        # 外部因素
        if factors:
            lines.append("### ⚠️ 注意事项")
            for f in factors[:3]:
                icon = {"construction": "🚧", "event": "🎭", "holiday": "📅",
                        "school_holiday": "🎒", "weather": "🌧️"}.get(f["type"], "ℹ️")
                lines.append(f"- {icon} **{f['title']}**: {f.get('description', '')}")
            lines.append("")

        # 个性化建议
        lines.append("### 💡 个性化建议")
        lines.append(f"*{profile.recommendation_style}*")
        lines.append("")

        if user_type == UserType.TRAVELER:
            lines.append("- 建议携带足够的水和零食")
            lines.append("- 可在 Chiemsee 服务区休息，欣赏湖景")
            if best_option.stress_index <= 4:
                lines.append("- 今日路况良好，旅途愉快！")

        elif user_type == UserType.LOGISTICS:
            lines.append(f"- 建议 {best_option.departure_time} 前出发，避开早高峰")
            lines.append("- 注意大车限速路段")
            if any(f["type"] == "construction" for f in factors):
                lines.append("- 有施工路段，预留额外时间")

        elif user_type == UserType.RESIDENT:
            lines.append("- 避开 07:00-09:00 和 16:00-18:00 高峰时段")
            if date_obj.weekday() == 4:  # 周五
                lines.append("- 周五下午出城方向拥堵加剧")

        elif user_type == UserType.TOURISM:
            lines.append(f"- 预计客流高峰: {best_option.departure_time} 后 2-3 小时")
            lines.append("- 建议提前准备接待/运营资源")

        elif user_type == UserType.AUTHORITY:
            if best_option.stress_index >= 6:
                lines.append("- 🚨 建议增派警力/救援资源")
                lines.append("- 考虑启动可变限速/信息牌提示")
            lines.append("- 关注瓶颈路段实时监控")

        return "\n".join(lines)

    def _user_type_emoji(self, user_type: UserType) -> str:
        emojis = {
            UserType.TRAVELER: "👨‍👩‍👧",
            UserType.RESIDENT: "🏠",
            UserType.LOGISTICS: "🚚",
            UserType.TOURISM: "🏨",
            UserType.AUTHORITY: "🚦",
        }
        return emojis.get(user_type, "👤")


# ============ 便捷函数 ============

def create_assistant() -> TravelAssistant:
    """创建助手实例"""
    return TravelAssistant()


def quick_plan(
    origin: str = "munich",
    destination: str = "salzburg",
    date: str = None,
    user_type: str = "traveler"
) -> TravelPlan:
    """
    快速生成出行计划

    Args:
        origin: 出发地 (munich)
        destination: 目的地 (salzburg, innsbruck)
        date: 日期，默认今天
        user_type: 用户类型

    Returns:
        出行计划
    """
    assistant = TravelAssistant()

    # 确定路线
    route_map = {
        ("munich", "salzburg"): "munich_salzburg_a8",
        ("munich", "innsbruck"): "munich_innsbruck_a93",
    }
    route_id = route_map.get((origin.lower(), destination.lower()), "munich_salzburg_a8")

    # 日期
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # 用户类型
    user_type_enum = UserType(user_type.lower())

    return assistant.generate_plan(route_id, date, user_type_enum)


# ============ LLM 工具定义 (用于 Function Calling) ============

TOOLS_SCHEMA = [
    {
        "name": "get_traffic_forecast",
        "description": "获取指定日期和高速公路的交通预测数据，包括每小时拥堵分数",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                "road": {"type": "string", "enum": ["A8", "A93"], "description": "高速公路"},
                "hours": {"type": "array", "items": {"type": "integer"}, "description": "小时列表"}
            },
            "required": ["date", "road"]
        }
    },
    {
        "name": "search_external_factors",
        "description": "搜索施工、活动、假期、天气等影响交通的外部因素",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期"},
                "road": {"type": "string", "description": "高速公路"},
            },
            "required": ["date", "road"]
        }
    },
    {
        "name": "calculate_travel_options",
        "description": "计算从慕尼黑出发的多个出行方案，包括出发时间、预计到达、延误、压力指数",
        "parameters": {
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "enum": ["munich_salzburg_a8", "munich_innsbruck_a93"],
                    "description": "路线ID"
                },
                "date": {"type": "string", "description": "日期"},
                "departure_hours": {"type": "array", "items": {"type": "integer"}, "description": "候选出发小时"}
            },
            "required": ["route_id", "date"]
        }
    },
    {
        "name": "generate_plan",
        "description": "生成完整的个性化出行计划，包括最佳方案、外部因素、个性化建议",
        "parameters": {
            "type": "object",
            "properties": {
                "route_id": {"type": "string", "description": "路线ID"},
                "date": {"type": "string", "description": "日期"},
                "user_type": {
                    "type": "string",
                    "enum": ["traveler", "resident", "logistics", "tourism", "authority"],
                    "description": "用户类型"
                }
            },
            "required": ["route_id", "date", "user_type"]
        }
    }
]
