"""
GenerationAgent - 响应生成Agent
根据用户画像和时间范围生成针对性的决策建议
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .base import BaseAgent
from .intent_parser import ParsedIntent, TimeRangeType, DataGranularity, TripType
from ..models import (
    AgentRequest, AgentResponse,
    DailyForecast, ExternalFactor, TravelOption, TravelPlan,
    UserType, CongestionLevel, ROUTES,
)
from ..personas import (
    PersonaType, PersonaProfile, PERSONAS,
    get_persona, USER_TYPE_TO_PERSONA,
)
from .prompt import (
    GENERATION_AGENT_SYSTEM_PROMPT,
    build_generation_prompt,
    get_generation_persona_prompt,
)
from ..tools import (
    aggregate_daily_reasons,
    load_factor_contribution_knowledge,
    score_to_stress_index,
    summarize_factor_reasons,
)


class GenerationAgent(BaseAgent):
    """
    响应生成Agent

    核心理念:
    不同用户需要的不是"预测堵车"，而是"基于预测做更好的决定"

    根据时间范围长度调整输出:
    - 1天: 小时级建议
    - 1周: 日级日历
    - 1月+: 周级/最佳窗口推荐
    """

    def __init__(self):
        self.factor_knowledge = load_factor_contribution_knowledge()
        self.system_prompt = GENERATION_AGENT_SYSTEM_PROMPT

    @property
    def name(self) -> str:
        return "GenerationAgent"

    async def process(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent = None,
        forecast: DailyForecast = None,
        context_data: Dict[str, Any] = None,
        context_factors: List[ExternalFactor] = None,
        search_factors: List[ExternalFactor] = None,
    ) -> AgentResponse:
        """生成针对用户画像和时间范围的响应"""
        try:
            # 合并所有外部因素
            all_factors = (context_factors or []) + (search_factors or [])

            # 确定用户画像
            if parsed_intent:
                persona = get_persona(parsed_intent.persona_type)
                time_range = parsed_intent.time_range
                granularity = parsed_intent.data_requirements.granularity
            else:
                persona = self._get_persona(request.user_type)
                time_range = None
                granularity = DataGranularity.DAILY

            # 确定路线
            route = self._determine_route(request.destination, request.road)

            # 根据时间范围长度选择生成策略
            if time_range and time_range.duration_days > 14:
                # 长时间范围（超过2周）：生成最佳窗口推荐
                result = self._generate_long_range_response(
                    request, parsed_intent, forecast, all_factors, route
                )
            elif time_range and time_range.duration_days > 1:
                # 中等时间范围（2-14天）：生成日历视图
                result = self._generate_calendar_response(
                    request, parsed_intent, forecast, all_factors, route, context_data or {}
                )
            else:
                # 短时间范围（1天）：根据用户画像生成
                result = self._generate_persona_response(
                    request, parsed_intent, persona, forecast, all_factors, route
                )

            result = self._attach_generation_prompt(result, persona.type.value)

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

    def _determine_route(self, destination: str, road: str = "A8"):
        """确定路线。

        目的地是慕尼黑时有两条返程线（从 Salzburg 或从 Innsbruck），系统没有
        独立的出发地字段，因此用 road 区分：A93 侧来自 Innsbruck/Kufstein 方向，
        否则默认 A8 侧的 Salzburg。
        """
        if not destination:
            return ROUTES.get("munich_salzburg")

        dest_lower = destination.lower()
        if "innsbruck" in dest_lower or "因斯布鲁克" in dest_lower:
            return ROUTES.get("munich_innsbruck")
        elif "salzburg" in dest_lower or "萨尔茨堡" in dest_lower:
            return ROUTES.get("munich_salzburg")
        elif any(k in dest_lower for k in ("munich", "münchen", "muenchen", "慕尼黑")):
            if str(road).upper() == "A93":
                return ROUTES.get("innsbruck_munich")
            return ROUTES.get("salzburg_munich")

        return ROUTES.get("munich_salzburg")

    def _attach_generation_prompt(self, result: Dict[str, Any], persona: str) -> Dict[str, Any]:
        """Attach the prompt guidance used for this generation pass."""
        if not isinstance(result, dict):
            return result

        data = result.setdefault("data", {})
        data["generation_prompt"] = {
            "system": self.system_prompt,
            "persona": get_generation_persona_prompt(persona),
            "composed": build_generation_prompt(persona),
        }
        return result

    # ============ 长时间范围：最佳窗口推荐 ============

    def _generate_long_range_response(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent,
        forecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """
        生成长时间范围（暑假、冬季等）的建议
        输出：最佳出行窗口 + 避开日期
        """
        time_range = parsed_intent.time_range

        # 分析时间段内的最佳窗口
        windows = self._analyze_best_windows(time_range, factors)
        factor_insights = self._factor_explanations_for_records(
            self._daily_forecast_records(forecast),
            top_n=4,
        )

        # 生成建议文本
        advice = self._format_long_range_advice(
            request, parsed_intent, route, windows, factors, factor_insights
        )

        return {
            "persona": parsed_intent.persona_type.value,
            "core_question": parsed_intent.core_question,
            "time_range_type": "long",
            "advice": advice,
            "data": {
                "windows": windows,
                "duration_days": time_range.duration_days,
                "factor_insights": factor_insights,
                "factor_knowledge_doc": self.factor_knowledge.get("doc_path"),
            },
            "factors": factors,
        }

    def _analyze_best_windows(self, time_range, factors: List[ExternalFactor]) -> List[Dict]:
        """分析最佳出行窗口"""
        windows = []

        try:
            start = datetime.strptime(time_range.start_date, "%Y-%m-%d")
            end = datetime.strptime(time_range.end_date, "%Y-%m-%d")
        except:
            return windows

        # 按周分析
        current = start
        while current <= end:
            week_end = min(current + timedelta(days=6), end)

            # 计算这周的风险
            risk, reasons = self._calculate_week_risk(current, week_end, factors)

            windows.append({
                "start": current.strftime("%Y-%m-%d"),
                "end": week_end.strftime("%Y-%m-%d"),
                "week_label": self._get_week_label(current),
                "risk_level": risk,
                "risk_emoji": {"low": "🟢", "medium": "🟠", "high": "🔴"}.get(risk, "🟠"),
                "reasons": reasons,
            })

            current = week_end + timedelta(days=1)

        return windows

    def _calculate_week_risk(self, start: datetime, end: datetime, factors: List[ExternalFactor]) -> tuple:
        """计算某周的风险等级"""
        risk_score = 0
        reasons = []

        # 检查是否包含周末
        for i in range((end - start).days + 1):
            day = start + timedelta(days=i)
            if day.weekday() >= 5:  # 周末
                risk_score += 10
                if "周末" not in reasons:
                    reasons.append("周末出行高峰")

        # 检查假期因素
        for f in factors:
            if f.type == "holiday" and f.impact in ["high", "very_high"]:
                risk_score += 30
                reasons.append(f.name)
            elif f.type == "school_holiday":
                risk_score += 20
                if "学校假期" not in reasons:
                    reasons.append("学校假期")
            elif f.type == "event" and f.impact in ["high", "very_high"]:
                risk_score += 25
                reasons.append(f.name)

        # 检查月份（旅游季节）
        month = start.month
        if month in [7, 8]:  # 暑假高峰
            risk_score += 15
            if "夏季旅游高峰" not in reasons:
                reasons.append("夏季旅游高峰")
        elif month == 12:  # 圣诞
            risk_score += 20

        # 确定等级
        if risk_score < 20:
            level = "low"
        elif risk_score < 40:
            level = "medium"
        else:
            level = "high"

        return level, reasons[:2]  # 最多2个原因

    def _get_week_label(self, date: datetime) -> str:
        """获取周标签"""
        month = date.month
        day = date.day
        if day <= 10:
            return f"{month}月上旬"
        elif day <= 20:
            return f"{month}月中旬"
        else:
            return f"{month}月下旬"

    def _format_long_range_advice(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent,
        route,
        windows: List[Dict],
        factors: List[ExternalFactor],
        factor_insights: List[Dict[str, Any]],
    ) -> str:
        """格式化长时间范围建议（包含往返）"""
        time_range = parsed_intent.time_range
        trip_plan = parsed_intent.trip_plan
        dest = route.destination if route else request.destination or "目的地"

        lines = [
            f"### 📅 {time_range.description}出行推荐",
            f"**路线**: {route.name if route else 'A8'}",
            f"**时间范围**: {time_range.start_date} 至 {time_range.end_date}",
        ]

        # 如果有往返计划，显示行程类型
        if trip_plan and trip_plan.trip_type == TripType.ROUND_TRIP:
            lines.append(f"**行程类型**: 🔄 往返")
            if trip_plan.stay_days:
                lines.append(f"**预计停留**: {trip_plan.stay_days} 天")

        lines.extend([
            "",
            "#### 🚗 去程推荐",
            "",
            "| 时段 | 拥堵风险 | 原因 |",
            "|------|----------|------|",
        ])

        # 添加窗口（去程视角）
        for w in windows:
            reason_str = ", ".join(w["reasons"]) if w["reasons"] else "-"
            lines.append(
                f"| {w['week_label']} | {w['risk_emoji']} {w['risk_level']} | {reason_str} |"
            )

        lines.append("")

        # 找最佳窗口（去程）
        best_windows = [w for w in windows if w["risk_level"] == "low"]
        if best_windows:
            lines.append(f"✅ **去程推荐**: {best_windows[0]['week_label']}")
        else:
            medium_windows = [w for w in windows if w["risk_level"] == "medium"]
            if medium_windows:
                lines.append(f"✅ **去程相对较好**: {medium_windows[0]['week_label']}")

        # 如果是往返行程，添加返程分析
        if trip_plan and trip_plan.trip_type == TripType.ROUND_TRIP:
            lines.extend([
                "",
                "#### 🔙 返程分析",
                "",
                "**返程规律**:",
                "- 周日下午/傍晚：返城高峰，建议避开 15:00-19:00",
                "- 假期最后一天：拥堵严重，建议提前一天或早上返回",
                "- 工作日返程：相对畅通",
                "",
                "#### 💡 综合建议",
                "",
                "- 去程：选择工作日或周六早上出发",
                "- 返程：避开周日下午高峰，可选择周日早上或周一返回",
            ])

        # 找需要避开的时段
        avoid_windows = [w for w in windows if w["risk_level"] == "high"]
        if avoid_windows:
            lines.append("")
            avoid_str = ", ".join([w["week_label"] for w in avoid_windows[:2]])
            lines.append(f"⚠️ **建议避开**: {avoid_str}")

        if factor_insights:
            lines.extend([
                "",
                "#### 模型归因解读",
            ])
            lines.extend(self._format_factor_insight_lines(factor_insights))

        # 添加重要提醒
        important = [f for f in factors if f.impact in ["high", "very_high"]]
        if important:
            lines.append("")
            lines.append("#### 重要提醒")
            for f in important[:3]:
                icon = {
                    "holiday": "📅",
                    "event": "🎭",
                    "construction": "🚧",
                }.get(f.type, "ℹ️")
                lines.append(f"- {icon} **{f.name}**: {f.description}")

        return "\n".join(lines)

    # ============ 中等时间范围：日历视图 ============

    def _generate_calendar_response(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
        context_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        生成中等时间范围（一周左右）的日历视图
        """
        time_range = parsed_intent.time_range

        # 生成日历
        calendar = self._generate_calendar(time_range, forecast, factors)

        # 找最佳日
        best_day = min(calendar, key=lambda d: d["score"]) if calendar else None
        hourly_recommendations = self._build_hourly_context_recommendations(
            context_data or {},
            best_day["date"] if best_day else None,
            request.hours,
        )

        # 生成建议文本
        advice = self._format_calendar_advice(
            request, parsed_intent, route, calendar, best_day, factors, hourly_recommendations
        )

        return {
            "persona": parsed_intent.persona_type.value,
            "core_question": parsed_intent.core_question,
            "time_range_type": "medium",
            "advice": advice,
            "data": {
                "calendar": calendar,
                "best_day": best_day,
                "hourly_recommendations": hourly_recommendations,
                "factor_knowledge_doc": self.factor_knowledge.get("doc_path"),
            },
            "factors": factors,
        }

    def _generate_calendar(self, time_range, forecast, factors) -> List[Dict]:
        """生成日历数据"""
        calendar = []
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        try:
            start = datetime.strptime(time_range.start_date, "%Y-%m-%d")
            end = datetime.strptime(time_range.end_date, "%Y-%m-%d")
        except:
            return calendar

        current = start
        while current <= end:
            weekday = weekday_names[current.weekday()]
            date_text = current.strftime("%Y-%m-%d")
            score = self._estimate_day_score(current, forecast, factors)
            level, emoji = self._score_to_level(score)
            reasons = self._get_day_reasons(current, factors)
            forecast_records = self._daily_forecast_records_for_date(forecast, date_text)
            factor_explanations = self._factor_explanations_for_records(forecast_records)

            calendar.append({
                "date": date_text,
                "weekday": weekday,
                "score": score,
                "level": level,
                "emoji": emoji,
                "reasons": reasons,
                "factor_explanations": factor_explanations,
            })

            current += timedelta(days=1)

        return calendar

    def _estimate_day_score(self, day: datetime, forecast, factors) -> int:
        """估算某天的拥堵分数"""
        forecast_records = self._daily_forecast_records_for_date(forecast, day.strftime("%Y-%m-%d"))
        forecast_scores = [
            self._to_float(record.get("congestion_score"))
            for record in forecast_records
        ]
        forecast_scores = [score for score in forecast_scores if score is not None]
        if forecast_scores:
            return int(round(sum(forecast_scores) / len(forecast_scores)))

        score = 30  # 基础分

        # 周末加分
        if day.weekday() == 5:  # 周六
            score += 20
        elif day.weekday() == 6:  # 周日
            score += 10
        elif day.weekday() == 4:  # 周五
            score += 15

        # 假期因素
        for f in factors:
            if f.type == "holiday":
                score += 25 if f.impact == "high" else 15
            elif f.type == "school_holiday":
                score += 15
            elif f.type == "event":
                score += 20 if f.impact == "high" else 10

        return min(100, score)

    def _score_to_level(self, score: int) -> tuple:
        """分数转等级"""
        if score < 35:
            return "畅通", "🟢"
        elif score < 55:
            return "中等", "🟠"
        else:
            return "严重", "🔴"

    def _get_day_reasons(self, day: datetime, factors) -> List[str]:
        """获取某天的拥堵原因"""
        reasons = []

        if day.weekday() == 4:
            reasons.append("周五出行高峰")
        elif day.weekday() == 5:
            reasons.append("周末出行")
        elif day.weekday() == 6:
            reasons.append("周日返程")

        for f in factors:
            if f.impact in ["moderate", "high", "very_high"] and self._factor_matches_day(f, day):
                reasons.append(f.name)

        return reasons[:2]

    def _factor_matches_day(self, factor: ExternalFactor, day: datetime) -> bool:
        """Only attach date-specific context factors to the matching calendar day."""
        text = f"{factor.name} {factor.description}"
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
        if not dates:
            return True
        return day.strftime("%Y-%m-%d") in dates

    def _format_calendar_advice(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent,
        route,
        calendar: List[Dict],
        best_day: Dict,
        factors: List[ExternalFactor],
        hourly_recommendations: List[Dict[str, Any]] = None,
    ) -> str:
        """格式化日历建议（包含往返）"""
        time_range = parsed_intent.time_range
        trip_plan = parsed_intent.trip_plan
        range_text = (
            f"{time_range.start_date} 至 {time_range.end_date}"
            if time_range.start_date != time_range.end_date
            else time_range.start_date
        )

        lines = [
            f"### 📅 出行日历: {route.name if route else 'A8'}",
            f"**时间范围**: {range_text}",
        ]

        # 显示行程类型
        if trip_plan and trip_plan.trip_type == TripType.ROUND_TRIP:
            lines.append(f"**行程类型**: 🔄 往返")

        lines.extend([
            "",
            "#### 🚗 去程建议",
            "",
            "| 日期 | 星期 | 拥堵预测 | 原因 |",
            "|------|------|----------|------|",
        ])

        for day in calendar:
            reason_parts = list(day["reasons"] or [])
            factor_labels = self._format_factor_labels(day.get("factor_explanations", []))
            if factor_labels:
                reason_parts.append(factor_labels)
            reason_str = "，".join(reason_parts) if reason_parts else "-"
            lines.append(
                f"| {day['date']} | {day['weekday']} | {day['emoji']} {day['level']} | {reason_str} |"
            )

        lines.append("")

        if best_day:
            lines.append(f"✅ **最佳去程日**: {best_day['weekday']} ({best_day['date']})")
            lines.append("")

            if best_day["level"] == "畅通":
                lines.append(f"💡 {best_day['weekday']}全天路况良好，可灵活安排出发时间")
            else:
                lines.append(f"💡 建议 {best_day['weekday']} 上午出发，避开下午高峰")

            if hourly_recommendations:
                lines.extend([
                    "",
                    "#### 🕒 最佳去程日每小时建议",
                    "",
                    "| 时间 | 建议 | ContextAgent 依据 |",
                    "|------|------|-------------------|",
                ])
                for item in hourly_recommendations:
                    lines.append(
                        f"| {item['time']} | {item['recommendation']} | {item['reason']} |"
                    )

            if best_day.get("factor_explanations"):
                lines.extend([
                    "",
                    "#### 模型归因解读",
                ])
                lines.extend(self._format_factor_insight_lines(best_day["factor_explanations"]))

        # 如果是往返行程，添加返程建议
        if trip_plan and trip_plan.trip_type == TripType.ROUND_TRIP:
            lines.extend([
                "",
                "#### 🔙 返程建议",
                "",
            ])

            best_return = self._choose_return_day(calendar, best_day, trip_plan)
            if best_return:
                lines.append(f"✅ **最佳返程日**: {best_return['weekday']} ({best_return['date']})")
                lines.append("")
                lines.append("💡 **返程时间建议**:")
                lines.append("- 优先选择上午或中午前返程，避开 15:00-19:00 返城高峰")
                lines.append("- 如果必须周日返程，建议 12:00 前上路")
            else:
                lines.append("💡 当前时间范围内没有晚于去程的返程候选日，建议扩大查询范围。")

        # 添加重要警告
        important = [f for f in factors if f.impact in ["high", "very_high"]]
        if important:
            lines.append("")
            lines.append(f"⚠️ {important[0].name}: {important[0].description}")

        return "\n".join(lines)

    def _choose_return_day(
        self,
        calendar: List[Dict[str, Any]],
        best_day: Dict[str, Any],
        trip_plan,
    ) -> Optional[Dict[str, Any]]:
        """Choose a return date that is after the outbound date."""
        if not calendar or not best_day:
            return None

        try:
            outbound = datetime.strptime(best_day["date"], "%Y-%m-%d")
        except (KeyError, TypeError, ValueError):
            return None

        stay_days = getattr(trip_plan, "stay_days", 0) or 1
        earliest_return = outbound + timedelta(days=max(1, stay_days))
        candidates = []
        for day in calendar:
            try:
                date_obj = datetime.strptime(day["date"], "%Y-%m-%d")
            except (KeyError, TypeError, ValueError):
                continue
            if date_obj >= earliest_return:
                candidates.append(day)

        if not candidates:
            return None
        return min(candidates, key=lambda item: item["score"])

    def _build_hourly_context_recommendations(
        self,
        context_data: Dict[str, Any],
        target_date: str,
        hours: List[int],
    ) -> List[Dict[str, Any]]:
        """Build hourly advice from ContextAgent hourly traffic and temperature rows."""
        if not context_data or not target_date:
            return []

        target_hours = sorted(set(hours or list(range(6, 22))))
        traffic_rows = self._context_rows_for_date(context_data.get("hourly_traffic", []), target_date)
        temp_rows = self._context_rows_for_date(context_data.get("temperature_road", []), target_date)
        historical = context_data.get("historical_same_period", {}) if isinstance(context_data, dict) else {}
        historical_traffic_rows = self._context_rows_for_date(
            historical.get("hourly_traffic", []) if isinstance(historical, dict) else [],
            target_date,
        )

        recommendations = []
        for hour in target_hours:
            traffic = self._average_rows([row for row in traffic_rows if self._to_int(row.get("hour")) == hour])
            historical_traffic = self._average_rows([
                row for row in historical_traffic_rows
                if self._to_int(row.get("hour")) == hour
            ])
            temperature = self._average_rows([row for row in temp_rows if self._to_int(row.get("hour")) == hour])

            row = traffic or historical_traffic
            recommendation, reason = self._score_hourly_context(row, temperature, bool(traffic))
            recommendations.append({
                "hour": hour,
                "time": f"{hour:02d}:00",
                "recommendation": recommendation,
                "reason": reason,
            })

        return recommendations

    def _context_rows_for_date(self, rows: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
        return [row for row in rows or [] if isinstance(row, dict) and str(row.get("date")) == target_date]

    def _average_rows(self, rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rows:
            return None

        result: Dict[str, Any] = {"count": len(rows)}
        for field in ["kfz_h", "sv_h", "v_kfz", "air_temp_c", "road_temp_c"]:
            values = [self._to_float(row.get(field)) for row in rows]
            values = [value for value in values if value is not None]
            if values:
                result[field] = round(sum(values) / len(values), 1)

        result["historical_reference"] = any(row.get("historical_reference") for row in rows)
        return result

    def _score_hourly_context(
        self,
        traffic: Optional[Dict[str, Any]],
        temperature: Optional[Dict[str, Any]],
        has_current_context: bool,
    ) -> tuple:
        risk = 0
        reasons = []

        if traffic:
            speed = traffic.get("v_kfz")
            volume = traffic.get("kfz_h")
            if speed is not None:
                reasons.append(f"均速约 {speed:g} km/h")
                if speed < 80:
                    risk += 2
                elif speed < 95:
                    risk += 1
            if volume is not None:
                reasons.append(f"流量约 {volume:g} veh/h")
                if volume >= 3000:
                    risk += 2
                elif volume >= 2200:
                    risk += 1
            if traffic.get("historical_reference") or not has_current_context:
                reasons.append("历史同期参考")
        else:
            reasons.append("无小时交通记录")

        if temperature:
            air_temp = temperature.get("air_temp_c")
            road_temp = temperature.get("road_temp_c")
            if air_temp is not None:
                reasons.append(f"气温约 {air_temp:g}°C")
                if air_temp >= 35:
                    risk += 1
            if road_temp is not None:
                reasons.append(f"路温约 {road_temp:g}°C")
                if road_temp <= 0:
                    risk += 2

        if risk == 0:
            recommendation = "✅ 推荐"
        elif risk == 1:
            recommendation = "🟢 可选"
        elif risk <= 3:
            recommendation = "🟠 谨慎"
        else:
            recommendation = "🔴 避开"

        return recommendation, "，".join(reasons[:4])

    def _daily_forecast_records(self, forecast) -> List[Dict[str, Any]]:
        """Normalize daily forecast payloads into a list of station-day records."""
        if isinstance(forecast, list):
            return [record for record in forecast if isinstance(record, dict)]
        if isinstance(forecast, dict):
            records = forecast.get("daily_forecasts")
            if isinstance(records, list):
                return [record for record in records if isinstance(record, dict)]
        return []

    def _daily_forecast_records_for_date(self, forecast, date: str) -> List[Dict[str, Any]]:
        """Get all station-day forecast records for one date."""
        return [
            record for record in self._daily_forecast_records(forecast)
            if str(record.get("date")) == date
        ]

    def _factor_explanations_for_records(
        self,
        records: List[Dict[str, Any]],
        top_n: int = 3,
    ) -> List[Dict[str, Any]]:
        """Aggregate daily reason shares and map them through FACTOR_CONTRIBUTIONS.md knowledge."""
        aggregated = aggregate_daily_reasons(records)
        return summarize_factor_reasons(aggregated, top_n=top_n, include_baseline=False)

    def _format_factor_labels(self, explanations: List[Dict[str, Any]]) -> str:
        """Compact labels for calendar table cells."""
        labels = []
        for item in explanations[:2]:
            label = item.get("label") or item.get("name")
            value = item.get("value")
            if value is None:
                labels.append(str(label))
            else:
                labels.append(f"{label} {value:.1f}%")
        return "、".join(labels)

    def _format_factor_insight_lines(self, explanations: List[Dict[str, Any]]) -> List[str]:
        """Format markdown-guided factor insights for user-facing advice."""
        lines = []
        for item in explanations[:3]:
            label = item.get("label", item.get("name"))
            value = item.get("value")
            value_text = f" {value:.1f}%" if value is not None else ""
            lines.append(f"- **{label}{value_text}**：{self._short_factor_message(item)}")

        return lines

    def _short_factor_message(self, item: Dict[str, Any]) -> str:
        """Concise factor explanation for the calendar advice."""
        name = item.get("name", "")
        if name == "Weather and Temperature":
            return "表示季节性天气/路温修正，不等同实时天气预报。"
        if name == "Date and Time Pattern":
            return "日期、星期和季节节奏在推动车流。"
        if name == "Special Events":
            return "沿线活动可能增加额外交通，建议结合实时搜索确认。"
        if name == "Construction Impact":
            return "施工影响需结合 ContextAgent 和 Tavily 搜索保守判断。"
        if name == "Holiday Effect":
            return "假期会提高家庭出游和返程流量。"
        return item.get("message") or item.get("explanation") or "模型认为该因素对拥堵有可见贡献。"

    def _to_int(self, value: Any, default: int = None):
        try:
            if value in {None, ""}:
                return default
            return int(float(str(value).replace(",", ".")))
        except (TypeError, ValueError):
            return default

    def _to_float(self, value: Any, default: float = None):
        try:
            if value in {None, ""}:
                return default
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default

    # ============ 短时间范围：按画像生成 ============

    def _generate_persona_response(
        self,
        request: AgentRequest,
        parsed_intent: ParsedIntent,
        persona: PersonaProfile,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """根据用户画像生成短时间范围响应"""
        trip_plan = parsed_intent.trip_plan if parsed_intent else None

        if persona.type == PersonaType.COMMUTER:
            return self._generate_commuter_response(request, forecast, factors, route, trip_plan)
        elif persona.type == PersonaType.LOGISTICS:
            return self._generate_logistics_response(request, forecast, factors, route)
        elif persona.type == PersonaType.OPERATOR:
            return self._generate_operator_response(request, forecast, factors, route)
        else:
            # TOURIST 或 FAMILY_TRAVELER（短时间）
            return self._generate_tourist_response(request, forecast, factors, route, trip_plan)

    # ============ Commuter ============

    def _generate_commuter_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
        trip_plan = None,
    ) -> Dict[str, Any]:
        """通勤者响应（包含早晚通勤）"""
        # 分析早高峰（去程）
        morning_hours = [h for h in request.hours if h < 12]
        best_morning, morning_peaks, morning_saved = self._analyze_commute(forecast, morning_hours or [6, 7, 8, 9])

        # 分析晚高峰（返程）
        evening_hours = [h for h in request.hours if h >= 12]
        best_evening, evening_peaks, evening_saved = self._analyze_commute(forecast, evening_hours or [16, 17, 18, 19])

        advice = self._format_commuter_advice(
            request, best_morning, morning_peaks, morning_saved,
            best_evening, evening_peaks, evening_saved, factors
        )

        return {
            "persona": "commuter",
            "core_question": "Can I arrive on time?",
            "time_range_type": "short",
            "trip_type": "commute",
            "advice": advice,
            "data": {
                "morning": {
                    "best_departure": f"{best_morning:02d}:30",
                    "avoid_hours": morning_peaks,
                    "time_saved_min": morning_saved,
                },
                "evening": {
                    "best_departure": f"{best_evening:02d}:30",
                    "avoid_hours": evening_peaks,
                    "time_saved_min": evening_saved,
                },
            },
            "factors": factors,
        }

    def _analyze_commute(self, forecast, hours):
        """分析通勤时段"""
        if not forecast or not forecast.predictions:
            return 7, [8, 9, 17, 18], 20

        preds_in_range = [p for p in forecast.predictions if p.hour in hours]
        if not preds_in_range:
            preds_in_range = forecast.predictions

        sorted_preds = sorted(preds_in_range, key=lambda p: p.congestion_score)

        best_hour = sorted_preds[0].hour if sorted_preds else 7
        peak_hours = [p.hour for p in sorted_preds[-3:]] if len(sorted_preds) >= 3 else [8, 17]

        best_score = sorted_preds[0].congestion_score if sorted_preds else 20
        worst_score = sorted_preds[-1].congestion_score if sorted_preds else 60
        base_time = 30
        time_saved = int(base_time * (worst_score - best_score) / 100 * 0.5)

        return best_hour, peak_hours, time_saved

    def _format_commuter_advice(self, request, best_morning, morning_peaks, morning_saved,
                                 best_evening, evening_peaks, evening_saved, factors):
        """格式化通勤建议（包含往返）"""
        morning_peak_str = ", ".join([f"{h:02d}:00" for h in sorted(morning_peaks)])
        evening_peak_str = ", ".join([f"{h:02d}:00" for h in sorted(evening_peaks)])

        lines = [
            f"### 🚗 今日通勤建议",
            "",
            "#### 🌅 早上去程",
            "",
            f"**最佳出发时间**: {best_morning:02d}:30",
            f"**避开时段**: {morning_peak_str}",
            f"**预计节省**: ~{morning_saved} 分钟",
        ]

        if morning_peaks:
            worst_morning = max(morning_peaks)
            lines.append(f"⚠️ {worst_morning:02d}:00-{worst_morning+1:02d}:00 为早高峰")

        lines.extend([
            "",
            "#### 🌆 晚上返程",
            "",
            f"**最佳返程时间**: {best_evening:02d}:30",
            f"**避开时段**: {evening_peak_str}",
            f"**预计节省**: ~{evening_saved} 分钟",
        ])

        if evening_peaks:
            worst_evening = max(evening_peaks)
            lines.append(f"⚠️ {worst_evening:02d}:00-{worst_evening+1:02d}:00 为晚高峰")

        important = [f for f in factors if f.impact in ["moderate", "high", "very_high"]]
        if important:
            lines.append("")
            lines.append("#### 影响因素")
            for f in important[:2]:
                lines.append(f"- {f.name}")

        return "\n".join(lines)

    # ============ Logistics ============

    def _generate_logistics_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """物流司机响应"""
        segments = self._analyze_segments(route, forecast, factors)
        total_delay = sum(s["delay_min"] for s in segments)
        recommended = "05:30" if total_delay > 20 else "06:30"

        advice = self._format_logistics_advice(request, route, segments, total_delay, recommended)

        return {
            "persona": "logistics",
            "core_question": "Where will delays happen?",
            "time_range_type": "short",
            "advice": advice,
            "data": {
                "segments": segments,
                "total_delay_min": total_delay,
                "recommended_departure": recommended,
            },
            "factors": factors,
        }

    def _analyze_segments(self, route, forecast, factors):
        """分析路段"""
        if not route:
            return []

        segments = []
        for seg in route.segments:
            base_delay = 0
            reasons = []

            if forecast and forecast.predictions:
                avg_score = forecast.avg_congestion_score
                base_delay = int(seg.free_flow_time_min * avg_score / 100 * 0.3)

            for f in factors:
                if f.type == "construction" and seg.road in f.name:
                    base_delay += 15
                    reasons.append("施工")

            if "salzburg" in seg.name.lower() or "kufstein" in seg.name.lower():
                base_delay += 10
                reasons.append("瓶颈路段")

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
            "",
            "| 路段 | 状态 | 预计延误 | 原因 |",
            "|------|------|----------|------|",
        ]

        for seg in segments:
            reason_str = ", ".join(seg["reasons"]) if seg["reasons"] else "-"
            lines.append(
                f"| {seg['name']} | {seg['emoji']} | +{seg['delay_min']} min | {reason_str} |"
            )

        lines.append("")
        lines.append(f"**总延误估算**: +{total_delay} 分钟")
        lines.append(f"**建议出发时间**: {recommended} 前")

        bottlenecks = [s for s in segments if "瓶颈" in str(s.get("reasons", []))]
        if bottlenecks:
            lines.append("")
            lines.append(f"⚠️ 瓶颈路段: {bottlenecks[0]['name']}")

        return "\n".join(lines)

    # ============ Tourist ============

    def _generate_tourist_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
        trip_plan = None,
    ) -> Dict[str, Any]:
        """游客响应"""
        level, recommended = self._simple_analysis(forecast, factors)

        advice = self._format_tourist_advice(request, route, level, recommended, factors, trip_plan)

        return {
            "persona": "tourist",
            "core_question": "Tell me what I should do.",
            "time_range_type": "short",
            "advice": advice,
            "data": {
                "congestion_level": level,
                "recommended_time": recommended,
                "trip_type": trip_plan.trip_type.value if trip_plan else "one_way",
            },
            "factors": factors,
        }

    def _simple_analysis(self, forecast, factors):
        """简单分析"""
        level = "moderate"
        recommended = "08:00"

        daily_records = self._daily_forecast_records(forecast)
        if daily_records:
            scores = [
                self._to_float(record.get("congestion_score"))
                for record in daily_records
            ]
            scores = [score for score in scores if score is not None]
            avg_score = sum(scores) / len(scores) if scores else 30
            if avg_score < 30:
                level, recommended = "low", "09:00"
            elif avg_score < 50:
                level, recommended = "moderate", "08:00"
            else:
                level, recommended = "high", "07:30"
        elif forecast and forecast.predictions:
            avg_score = forecast.avg_congestion_score
            if avg_score < 30:
                level, recommended = "low", "09:00"
            elif avg_score < 50:
                level, recommended = "moderate", "08:00"
            else:
                level, recommended = "high", "07:30"

        for f in factors:
            if f.impact in ["high", "very_high"]:
                level, recommended = "high", "07:30"
                break

        return level, recommended

    def _format_tourist_advice(self, request, route, level, recommended, factors, trip_plan=None):
        """格式化游客建议（包含往返）"""
        dest = route.destination if route else request.destination or "目的地"

        lines = [
            f"### 🧳 驾驶建议",
            "",
            f"**去{dest}？**",
            "",
        ]

        # 去程建议
        lines.append("#### 🚗 去程")
        lines.append("")

        if level == "low":
            lines.append("路况预计良好，出行轻松。")
            lines.append("")
            lines.append(f"✅ **建议**: 可以灵活安排出发时间")
        elif level == "moderate":
            lines.append("预计有轻微拥堵，稍作规划即可。")
            lines.append("")
            lines.append(f"✅ **建议**: {recommended} 左右出发")
        else:
            reason = "假期/周末交通"
            for f in factors:
                if f.impact in ["high", "very_high"]:
                    reason = f.name
                    break
            lines.append(f"由于{reason}，拥堵风险较高。")
            lines.append("")
            lines.append(f"✅ **建议**: {recommended} 前出发，可以避开大部分车流")

        base_time = route.free_flow_time_min if route else 80
        if level == "low":
            est_time = base_time
        elif level == "moderate":
            est_time = int(base_time * 1.15)
        else:
            est_time = int(base_time * 1.3)

        lines.append("")
        lines.append(f"⏱️ 预计行程: {est_time // 60}小时{est_time % 60}分钟")

        # 返程建议（如果是往返）
        if trip_plan and trip_plan.trip_type == TripType.ROUND_TRIP:
            lines.extend([
                "",
                "#### 🔙 返程",
                "",
                "**返程时间建议**:",
                "- 周日返程：建议 12:00 前出发",
                "- 避开 15:00-19:00 返城高峰",
            ])

        return "\n".join(lines)

    # ============ Operator ============

    def _generate_operator_response(
        self,
        request: AgentRequest,
        forecast: DailyForecast,
        factors: List[ExternalFactor],
        route,
    ) -> Dict[str, Any]:
        """交通管理者响应"""
        contributions = self._analyze_factor_contributions(forecast, factors)
        total_impact = sum(f["contribution"] for f in contributions)
        risk_level = "高" if total_impact > 60 else "中" if total_impact > 30 else "低"
        suggestions = self._generate_management_suggestions(risk_level, contributions)

        advice = self._format_operator_advice(request, route, contributions, risk_level, suggestions)

        return {
            "persona": "operator",
            "core_question": "Why will congestion happen?",
            "time_range_type": "short",
            "advice": advice,
            "data": {
                "factor_contributions": contributions,
                "risk_level": risk_level,
                "management_suggestions": suggestions,
            },
            "factors": factors,
        }

    def _analyze_factor_contributions(self, forecast, factors):
        """分析因素贡献"""
        contributions = []

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

        historical_impact = 30
        contributions.append({
            "name": "历史模式",
            "contribution": historical_impact,
            "bar": "█" * (historical_impact // 5) + "░" * (20 - historical_impact // 5),
        })

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
        if risk_level == "高":
            return [
                "考虑启动可变限速",
                "增派巡逻力量至瓶颈路段",
                "提前发布公众出行建议",
            ]
        elif risk_level == "中":
            return [
                "加强瓶颈路段监控",
                "准备应急疏导方案",
            ]
        else:
            return [
                "常规巡逻即可",
            ]

    def _format_operator_advice(self, request, route, contributions, risk_level, suggestions):
        """格式化管理者报告"""
        risk_emoji = {"高": "🔴", "中": "🟠", "低": "🟢"}.get(risk_level, "🟠")

        lines = [
            f"### 🏢 拥堵分析报告",
            "",
            f"**预测日期**: {request.date}",
            f"**预测路段**: {route.name if route else request.road}",
            f"**风险等级**: {risk_emoji} {risk_level}风险",
            "",
            "#### 影响因素贡献",
            "",
            "```",
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
