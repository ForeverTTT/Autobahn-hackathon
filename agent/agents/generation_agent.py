"""
GenerationAgent - 响应生成Agent
根据用户画像生成针对性的决策建议
"""
from typing import Any, Dict, List
from datetime import datetime, timedelta

from .base import BaseAgent
from ..models import (
    AgentRequest, AgentResponse,
    DailyForecast, ExternalFactor, TravelOption, TravelPlan,
    UserType, CongestionLevel, ROUTES,
)
from ..personas import (
    PersonaType, PersonaProfile, PERSONAS,
    get_persona, USER_TYPE_TO_PERSONA,
)
from ..tools import score_to_stress_index


class GenerationAgent(BaseAgent):
    """
    响应生成Agent

    核心理念:
    不同用户需要的不是"预测堵车"，而是"基于预测做更好的决定"

    用户类型 → 核心问题:
    - Commuter:       "Can I arrive on time?"
    - Family Traveler: "Which day should we travel?"
    - Logistics:       "Where will delays happen?"
    - Tourist:         "Tell me what I should do."
    - Operator:        "Why will congestion happen?"
    """

    @property
    def name(self) -> str:
        return "GenerationAgent"

    async def process(
        self,
        request: AgentRequest,
        forecast: DailyForecast = None,
        context_factors: List[ExternalFactor] = None,
        search_factors: List[ExternalFactor] = None,
    ) -> AgentResponse:
        """生成针对用户画像的响应"""
        try:
            # 合并所有外部因素
            all_factors = (context_factors or []) + (search_factors or [])

            # 确定用户画像
            persona = self._get_persona(request.user_type)

            # 确定路线
            route = self._determine_route(request.destination)

            # 根据用户画像生成不同的输出
            if persona.type == PersonaType.COMMUTER:
                result = self._generate_commuter_response(
                    request, forecast, all_factors, route
                )
            elif persona.type == PersonaType.FAMILY_TRAVELER:
                result = self._generate_traveler_response(
                    request, forecast, all_factors, route
                )
            elif persona.type == PersonaType.LOGISTICS:
                result = self._generate_logistics_response(
                    request, forecast, all_factors, route
                )
            elif persona.type == PersonaType.TOURIST:
                result = self._generate_tourist_response(
                    request, forecast, all_factors, route
                )
            elif persona.type == PersonaType.OPERATOR:
                result = self._generate_operator_response(
                    request, forecast, all_factors, route
                )
            else:
                result = self._generate_tourist_response(
                    request, forecast, all_factors, route
                )

            return self._success(result)

        except Exception as e:
            return self._error(f"Generation error: {str(e)}")

    def _get_persona(self, user_type: UserType) -> PersonaProfile:
        """获取用户画像"""
        persona_type = USER_TYPE_TO_PERSONA.get(
            user_type.value,
            PersonaType.TOURIST
        )
        return get_persona(persona_type)

    def _determine_route(self, destination: str):
        """确定路线"""
        if not destination:
            return ROUTES.get("munich_salzburg")

        dest_lower = destination.lower()
        if "salzburg" in dest_lower or "萨尔茨堡" in dest_lower:
            return ROUTES.get("munich_salzburg")
        elif "innsbruck" in dest_lower or "因斯布鲁克" in dest_lower:
            return ROUTES.get("munich_innsbruck")

        return ROUTES.get("munich_salzburg")

    # ============ Commuter: "Can I arrive on time?" ============

    def _generate_commuter_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        通勤者需要:
        - 今日小时级预测
        - 最佳出发时间
        - 高峰时段警告
        - 可节省时间
        """
        # 找出最佳出发时间和高峰时段
        best_hour, peak_hours, time_saved = self._analyze_commute(forecast, request.hours)

        # 生成建议文本
        advice = self._format_commuter_advice(
            request, best_hour, peak_hours, time_saved, factors
        )

        return {
            "persona": "commuter",
            "core_question": "Can I arrive on time?",
            "advice": advice,
            "data": {
                "best_departure": f"{best_hour:02d}:30",
                "avoid_hours": peak_hours,
                "time_saved_min": time_saved,
            },
            "factors": factors,
        }

    def _analyze_commute(self, forecast, hours):
        """分析通勤时段"""
        if not forecast or not forecast.predictions:
            return 7, [8, 9, 17, 18], 20

        # 按拥堵分数排序
        preds_in_range = [p for p in forecast.predictions if p.hour in hours]
        if not preds_in_range:
            preds_in_range = forecast.predictions

        sorted_preds = sorted(preds_in_range, key=lambda p: p.congestion_score)

        best_hour = sorted_preds[0].hour if sorted_preds else 7
        peak_hours = [p.hour for p in sorted_preds[-3:]] if len(sorted_preds) >= 3 else [8, 17]

        # 估算节省时间
        best_score = sorted_preds[0].congestion_score if sorted_preds else 20
        worst_score = sorted_preds[-1].congestion_score if sorted_preds else 60
        base_time = 30  # 假设基础通勤30分钟
        time_saved = int(base_time * (worst_score - best_score) / 100 * 0.5)

        return best_hour, peak_hours, time_saved

    def _format_commuter_advice(self, request, best_hour, peak_hours, time_saved, factors):
        """格式化通勤建议"""
        peak_str = ", ".join([f"{h:02d}:00" for h in sorted(peak_hours)])

        lines = [
            f"### 🚗 今日通勤建议",
            f"",
            f"**最佳出发时间**: {best_hour:02d}:30",
            f"**避开时段**: {peak_str}",
            f"",
            f"预计节省 **~{time_saved} 分钟**",
            f"",
        ]

        # 添加警告
        if peak_hours:
            worst = max(peak_hours)
            lines.append(f"⚠️ {worst:02d}:00-{worst+1:02d}:00 为今日最拥堵时段")

        # 添加影响因素
        important = [f for f in factors if f.impact in ["moderate", "high", "very_high"]]
        if important:
            lines.append("")
            lines.append("**影响因素**:")
            for f in important[:2]:
                lines.append(f"- {f.name}")

        return "\n".join(lines)

    # ============ Family Traveler: "Which day should we travel?" ============

    def _generate_traveler_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        家庭旅行者需要:
        - 日历视图（未来几天拥堵等级）
        - 最佳出行日
        - 拥堵原因解释
        """
        # 生成日历数据
        calendar = self._generate_calendar(request.date, forecast, factors)

        # 找最佳日
        best_day = min(calendar, key=lambda d: d["score"])

        # 生成建议文本
        advice = self._format_traveler_advice(request, calendar, best_day, factors, route)

        return {
            "persona": "traveler",
            "core_question": "Which day should we travel?",
            "advice": advice,
            "data": {
                "calendar": calendar,
                "best_day": best_day["date"],
                "best_day_level": best_day["level"],
            },
            "factors": factors,
        }

    def _generate_calendar(self, base_date, forecast, factors):
        """生成未来几天的日历"""
        try:
            start = datetime.strptime(base_date, "%Y-%m-%d")
        except:
            start = datetime.now()

        calendar = []
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for i in range(5):  # 未来5天
            day = start + timedelta(days=i)
            weekday = weekday_names[day.weekday()]

            # 计算该日拥堵分数
            score = self._estimate_day_score(day, forecast, factors)
            level, emoji = self._score_to_level(score)

            # 找原因
            reasons = self._get_day_reasons(day, factors)

            calendar.append({
                "date": day.strftime("%Y-%m-%d"),
                "weekday": weekday,
                "score": score,
                "level": level,
                "emoji": emoji,
                "reasons": reasons,
            })

        return calendar

    def _estimate_day_score(self, day, forecast, factors):
        """估算某天的拥堵分数"""
        base_score = 30

        # 周末加分
        if day.weekday() >= 5:
            base_score += 15

        # 周五下午加分
        if day.weekday() == 4:
            base_score += 20

        # 假期因素
        for f in factors:
            if f.type == "holiday" and f.impact == "high":
                base_score += 25
            elif f.type == "school_holiday":
                base_score += 15
            elif f.type == "event":
                base_score += 20

        return min(100, base_score)

    def _score_to_level(self, score):
        """分数转等级"""
        if score < 30:
            return "畅通", "🟢"
        elif score < 50:
            return "中等", "🟠"
        else:
            return "严重", "🔴"

    def _get_day_reasons(self, day, factors):
        """获取某天的拥堵原因"""
        reasons = []

        if day.weekday() == 4:
            reasons.append("周五出行高峰")
        elif day.weekday() == 5:
            reasons.append("周末出行")
        elif day.weekday() == 6:
            reasons.append("周日返程")

        for f in factors:
            if f.impact in ["moderate", "high", "very_high"]:
                reasons.append(f.name)

        return reasons[:2]  # 最多2个原因

    def _format_traveler_advice(self, request, calendar, best_day, factors, route):
        """格式化旅行建议"""
        dest = route.destination if route else "目的地"

        lines = [
            f"### 📅 出行日历: {route.name if route else '行程'}",
            f"",
            f"| 日期 | 星期 | 拥堵预测 | 原因 |",
            f"|------|------|----------|------|",
        ]

        for day in calendar:
            reason_str = ", ".join(day["reasons"]) if day["reasons"] else "-"
            lines.append(
                f"| {day['date']} | {day['weekday']} | {day['emoji']} {day['level']} | {reason_str} |"
            )

        lines.append("")
        lines.append(f"✅ **最佳出行日**: {best_day['weekday']} ({best_day['date']})")
        lines.append("")

        # 添加建议
        if best_day["level"] == "畅通":
            lines.append(f"💡 {best_day['weekday']}全天路况良好，可灵活安排出发时间")
        else:
            lines.append(f"💡 建议 {best_day['weekday']} 上午出发，避开下午高峰")

        # 添加重要警告
        important = [f for f in factors if f.impact in ["high", "very_high"]]
        if important:
            lines.append("")
            lines.append(f"⚠️ {important[0].name}: {important[0].description}")

        return "\n".join(lines)

    # ============ Logistics: "Where will delays happen?" ============

    def _generate_logistics_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        物流司机需要:
        - 路段级预测
        - 瓶颈检测
        - 延误估算
        """
        # 生成路段预测
        segments = self._analyze_segments(route, forecast, factors)

        # 计算总延误
        total_delay = sum(s["delay_min"] for s in segments)

        # 推荐出发时间
        recommended_departure = "05:30" if total_delay > 20 else "06:30"

        # 生成建议
        advice = self._format_logistics_advice(
            request, route, segments, total_delay, recommended_departure
        )

        return {
            "persona": "logistics",
            "core_question": "Where will delays happen?",
            "advice": advice,
            "data": {
                "segments": segments,
                "total_delay_min": total_delay,
                "recommended_departure": recommended_departure,
            },
            "factors": factors,
        }

    def _analyze_segments(self, route, forecast, factors):
        """分析路段"""
        if not route:
            return []

        segments = []
        for seg in route.segments:
            # 估算延误
            base_delay = 0
            reasons = []

            # 基于预测
            if forecast and forecast.predictions:
                avg_score = forecast.avg_congestion_score
                base_delay = int(seg.free_flow_time_min * avg_score / 100 * 0.3)

            # 检查施工
            for f in factors:
                if f.type == "construction" and seg.road in f.name:
                    base_delay += 15
                    reasons.append("施工")

            # 检查瓶颈
            if "salzburg" in seg.name.lower() or "kufstein" in seg.name.lower():
                base_delay += 10
                reasons.append("瓶颈路段")

            # 确定状态
            if base_delay <= 5:
                status, emoji = "畅通", "🟢"
            elif base_delay <= 15:
                status, emoji = "轻微延误", "🟠"
            else:
                status, emoji = "严重延误", "🔴"

            segments.append({
                "name": seg.name,
                "road": seg.road,
                "delay_min": base_delay,
                "status": status,
                "emoji": emoji,
                "reasons": reasons,
            })

        return segments

    def _format_logistics_advice(self, request, route, segments, total_delay, recommended):
        """格式化物流建议"""
        lines = [
            f"### 🚚 路段预测: {route.name if route else 'A8'}",
            f"",
            f"| 路段 | 状态 | 预计延误 | 原因 |",
            f"|------|------|----------|------|",
        ]

        for seg in segments:
            reason_str = ", ".join(seg["reasons"]) if seg["reasons"] else "-"
            lines.append(
                f"| {seg['name']} | {seg['emoji']} | +{seg['delay_min']} min | {reason_str} |"
            )

        lines.append("")
        lines.append(f"**总延误估算**: +{total_delay} 分钟")
        lines.append(f"**建议出发时间**: {recommended} 前")

        # 瓶颈警告
        bottlenecks = [s for s in segments if "瓶颈" in str(s.get("reasons", []))]
        if bottlenecks:
            lines.append("")
            lines.append(f"⚠️ 瓶颈路段: {bottlenecks[0]['name']}")

        return "\n".join(lines)

    # ============ Tourist: "Tell me what I should do." ============

    def _generate_tourist_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        游客需要:
        - 简单直接的建议
        - 不要复杂数据
        - 像朋友建议
        """
        # 简单分析
        congestion_level, recommended_time = self._simple_analysis(forecast, factors)

        # 生成简单建议
        advice = self._format_tourist_advice(
            request, route, congestion_level, recommended_time, factors
        )

        return {
            "persona": "tourist",
            "core_question": "Tell me what I should do.",
            "advice": advice,
            "data": {
                "congestion_level": congestion_level,
                "recommended_time": recommended_time,
            },
            "factors": factors,
        }

    def _simple_analysis(self, forecast, factors):
        """简单分析"""
        # 默认值
        level = "moderate"
        recommended = "08:00"

        if forecast and forecast.predictions:
            avg_score = forecast.avg_congestion_score
            if avg_score < 30:
                level = "low"
                recommended = "09:00"  # 可以晚点出发
            elif avg_score < 50:
                level = "moderate"
                recommended = "08:00"
            else:
                level = "high"
                recommended = "07:30"  # 需要早出发

        # 假期影响
        for f in factors:
            if f.impact in ["high", "very_high"]:
                level = "high"
                recommended = "07:30"
                break

        return level, recommended

    def _format_tourist_advice(self, request, route, level, recommended, factors):
        """格式化游客建议（简单友好）"""
        dest = route.destination if route else request.destination or "目的地"
        date_obj = datetime.strptime(request.date, "%Y-%m-%d")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[date_obj.weekday()]

        lines = [
            f"### 🧳 驾驶建议",
            f"",
            f"**{weekday}去{dest}？**",
            f"",
        ]

        # 简单描述风险
        if level == "low":
            lines.append("路况预计良好，出行轻松。")
            lines.append("")
            lines.append(f"✅ **建议**: 可以灵活安排出发时间")
        elif level == "moderate":
            lines.append("预计有轻微拥堵，稍作规划即可。")
            lines.append("")
            lines.append(f"✅ **建议**: {recommended} 左右出发")
        else:
            # 找原因
            reason = "假期/周末交通"
            for f in factors:
                if f.impact in ["high", "very_high"]:
                    reason = f.name
                    break
            lines.append(f"由于{reason}，拥堵风险较高。")
            lines.append("")
            lines.append(f"✅ **建议**: {recommended} 前出发，可以避开大部分车流")

        # 预计行程
        base_time = route.free_flow_time_min if route else 80
        if level == "low":
            est_time = base_time
        elif level == "moderate":
            est_time = int(base_time * 1.15)
        else:
            est_time = int(base_time * 1.3)

        lines.append("")
        lines.append(f"🚗 预计行程: {est_time // 60}小时{est_time % 60}分钟")

        return "\n".join(lines)

    # ============ Operator: "Why will congestion happen?" ============

    def _generate_operator_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        交通管理者需要:
        - 可解释的预测
        - 因素贡献分析
        - 管理建议
        """
        # 分析因素贡献
        factor_contributions = self._analyze_factor_contributions(forecast, factors)

        # 确定风险等级
        total_impact = sum(f["contribution"] for f in factor_contributions)
        risk_level = "高" if total_impact > 60 else "中" if total_impact > 30 else "低"

        # 生成管理建议
        management_suggestions = self._generate_management_suggestions(
            risk_level, factor_contributions
        )

        # 生成报告
        advice = self._format_operator_advice(
            request, route, factor_contributions, risk_level, management_suggestions
        )

        return {
            "persona": "operator",
            "core_question": "Why will congestion happen?",
            "advice": advice,
            "data": {
                "factor_contributions": factor_contributions,
                "risk_level": risk_level,
                "management_suggestions": management_suggestions,
            },
            "factors": factors,
        }

    def _analyze_factor_contributions(self, forecast, factors):
        """分析各因素贡献"""
        contributions = []

        # 假期效应
        holiday_impact = 0
        for f in factors:
            if f.type == "holiday":
                holiday_impact = 35 if f.impact == "high" else 20
                break
        if holiday_impact:
            contributions.append({
                "name": "假期效应",
                "contribution": holiday_impact,
                "bar": "█" * (holiday_impact // 5) + "░" * (20 - holiday_impact // 5),
            })

        # 周末效应
        weekend_impact = 0
        for f in factors:
            if f.type == "weekend":
                weekend_impact = 25
                break
        if weekend_impact:
            contributions.append({
                "name": "周末效应",
                "contribution": weekend_impact,
                "bar": "█" * (weekend_impact // 5) + "░" * (20 - weekend_impact // 5),
            })

        # 历史模式
        historical_impact = 30
        contributions.append({
            "name": "历史模式",
            "contribution": historical_impact,
            "bar": "█" * (historical_impact // 5) + "░" * (20 - historical_impact // 5),
        })

        # 天气因素
        weather_impact = 0
        for f in factors:
            if f.type == "weather" and f.impact in ["moderate", "high"]:
                weather_impact = 15 if f.impact == "high" else 10
                break
        if weather_impact:
            contributions.append({
                "name": "天气因素",
                "contribution": weather_impact,
                "bar": "█" * (weather_impact // 5) + "░" * (20 - weather_impact // 5),
            })

        return contributions

    def _generate_management_suggestions(self, risk_level, factors):
        """生成管理建议"""
        suggestions = []

        if risk_level == "高":
            suggestions = [
                "考虑启动可变限速",
                "增派巡逻力量至瓶颈路段",
                "提前发布公众出行建议",
            ]
        elif risk_level == "中":
            suggestions = [
                "加强瓶颈路段监控",
                "准备应急疏导方案",
            ]
        else:
            suggestions = [
                "常规巡逻即可",
            ]

        return suggestions

    def _format_operator_advice(self, request, route, contributions, risk_level, suggestions):
        """格式化管理者报告"""
        risk_emoji = {"高": "🔴", "中": "🟠", "低": "🟢"}.get(risk_level, "🟠")

        lines = [
            f"### 🏢 拥堵分析报告",
            f"",
            f"**预测日期**: {request.date}",
            f"**预测路段**: {route.name if route else request.road}",
            f"**风险等级**: {risk_emoji} {risk_level}风险",
            f"",
            f"#### 影响因素贡献",
            f"",
            f"```",
        ]

        for f in contributions:
            name_padded = f"{f['name']:<12}"
            lines.append(f"{name_padded} {f['bar']}  +{f['contribution']}%")

        lines.append("```")
        lines.append("")
        lines.append("#### 建议措施")
        lines.append("")

        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}. {s}")

        return "\n".join(lines)
