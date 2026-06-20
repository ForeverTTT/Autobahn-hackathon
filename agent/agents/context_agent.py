"""
ContextAgent - 上下文Agent
查询 data_autobahn 中除预测表以外的上下文数据。
"""
from typing import Any, Dict, List

from .base import BaseAgent
from ..models import AgentRequest, AgentResponse, ExternalFactor
from ..tools import context_loader


class ContextAgent(BaseAgent):
    """
    上下文Agent

    职责:
    - 根据 Intent/Orchestrator 给到的日期或日期范围收集上下文
    - 覆盖气温/路温、历史小时交通、施工、假期、活动、天气
    - 输出完整结构化 context，同时生成给 GenerationAgent 使用的 factors
    """

    @property
    def name(self) -> str:
        return "ContextAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理上下文请求。"""
        try:
            start_date = request.start_date or request.date
            end_date = request.end_date or start_date
            road = request.road
            hours = request.hours or list(range(6, 22))

            context = context_loader.get_context_range(
                start_date=start_date,
                end_date=end_date,
                road=road,
                hours=hours,
            )
            summary = self._summarize_context(context)
            factors = self._build_factors(context, road)

            return self._success({
                "factors": factors,
                "context": context,
                "summary": summary,
                "date": request.date,
                "start_date": start_date,
                "end_date": end_date,
                "road": road,
                "hours": hours,
            })

        except Exception as e:
            return self._error(f"Context error: {str(e)}")

    def _summarize_context(self, context: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """生成前端/调试友好的上下文摘要。"""
        traffic = context.get("hourly_traffic", [])
        temperature = context.get("temperature_road", [])
        historical = context.get("historical_same_period", {})
        historical_traffic = historical.get("hourly_traffic", []) if isinstance(historical, dict) else []
        historical_temperature = historical.get("temperature_road", []) if isinstance(historical, dict) else []

        speeds = [self._to_float(row.get("v_kfz")) for row in traffic]
        speeds = [value for value in speeds if value is not None]
        volumes = [self._to_float(row.get("kfz_h")) for row in traffic]
        volumes = [value for value in volumes if value is not None]
        air_temps = [self._to_float(row.get("air_temp_c")) for row in temperature]
        air_temps = [value for value in air_temps if value is not None]
        road_temps = [self._to_float(row.get("road_temp_c")) for row in temperature]
        road_temps = [value for value in road_temps if value is not None]
        historical_speeds = [self._to_float(row.get("v_kfz")) for row in historical_traffic]
        historical_speeds = [value for value in historical_speeds if value is not None]
        historical_volumes = [self._to_float(row.get("kfz_h")) for row in historical_traffic]
        historical_volumes = [value for value in historical_volumes if value is not None]

        return {
            "weather_days": len(context.get("weather", [])),
            "holiday_days": len(context.get("holiday", [])),
            "construction_days": self._count_active_days(context.get("construction", []), "has_construction"),
            "event_days": self._count_active_days(context.get("events", []), "has_special_event"),
            "temperature_hours": len(temperature),
            "traffic_records": len(traffic),
            "avg_speed_kmh": round(sum(speeds) / len(speeds), 1) if speeds else None,
            "max_hourly_volume": max(volumes) if volumes else None,
            "min_air_temp_c": min(air_temps) if air_temps else None,
            "max_air_temp_c": max(air_temps) if air_temps else None,
            "min_road_temp_c": min(road_temps) if road_temps else None,
            "max_road_temp_c": max(road_temps) if road_temps else None,
            "historical_same_period": {
                "years": self._source_years(historical),
                "weather_days": len(historical.get("weather", [])) if isinstance(historical, dict) else 0,
                "holiday_days": len(historical.get("holiday", [])) if isinstance(historical, dict) else 0,
                "construction_days": len(historical.get("construction", [])) if isinstance(historical, dict) else 0,
                "event_days": len(historical.get("events", [])) if isinstance(historical, dict) else 0,
                "temperature_hours": len(historical_temperature),
                "traffic_records": len(historical_traffic),
                "avg_speed_kmh": round(sum(historical_speeds) / len(historical_speeds), 1) if historical_speeds else None,
                "max_hourly_volume": max(historical_volumes) if historical_volumes else None,
            },
        }

    def _build_factors(self, context: Dict[str, List[Dict[str, Any]]], road: str) -> List[ExternalFactor]:
        """从上下文数据中提取关键影响因素。"""
        factors: List[ExternalFactor] = []
        factors.extend(self._weather_factors(context.get("weather", [])))
        factors.extend(self._temperature_factors(context.get("temperature_road", [])))
        factors.extend(self._holiday_factors(context.get("holiday", []), road))
        factors.extend(self._construction_factors(context.get("construction", []), road))
        factors.extend(self._event_factors(context.get("events", [])))
        factors.extend(self._traffic_factors(context.get("hourly_traffic", []), road))
        factors.extend(self._historical_same_period_factors(context.get("historical_same_period", {}), road))
        return factors

    def _weather_factors(self, rows: List[Dict[str, Any]]) -> List[ExternalFactor]:
        factors = []
        for row in rows:
            date = row.get("date")
            precip = self._first_number(row, ["precip_mm", "precip_mm_mean"])
            snow = self._first_number(row, ["snowfall_mm"])
            low_vis = self._first_number(row, ["low_vis_hours", "low_vis_hours_mean"])
            ice = self._truthy(row.get("has_ice_risk")) or self._to_float(row.get("ice_risk_prob"), 0) >= 0.5
            t_max = self._first_number(row, ["t_max_c", "t_max_c_mean"])

            if precip is not None and precip >= 5:
                factors.append(ExternalFactor(
                    type="weather",
                    name=f"{date} 降雨",
                    description=f"日降水量约 {precip:g} mm，路面湿滑风险增加",
                    impact="moderate" if precip < 15 else "high",
                    source="context",
                ))
            if snow is not None and snow > 0:
                factors.append(ExternalFactor(
                    type="weather",
                    name=f"{date} 降雪",
                    description=f"日降雪量约 {snow:g} mm，可能影响行车速度",
                    impact="high",
                    source="context",
                ))
            if low_vis is not None and low_vis >= 2:
                factors.append(ExternalFactor(
                    type="weather",
                    name=f"{date} 低能见度",
                    description=f"低能见度小时数约 {low_vis:g} 小时",
                    impact="moderate",
                    source="context",
                ))
            if ice:
                factors.append(ExternalFactor(
                    type="weather",
                    name=f"{date} 结冰风险",
                    description="存在结冰风险或气候态结冰概率较高",
                    impact="high",
                    source="context",
                ))
            if t_max is not None and t_max >= 35:
                factors.append(ExternalFactor(
                    type="weather",
                    name=f"{date} 高温",
                    description=f"最高气温约 {t_max:g}°C，事故和疲劳风险增加",
                    impact="moderate",
                    source="context",
                ))
        return factors

    def _temperature_factors(self, rows: List[Dict[str, Any]]) -> List[ExternalFactor]:
        factors = []
        cold = [row for row in rows if self._to_float(row.get("road_temp_c"), 99) <= 0]
        hot = [row for row in rows if self._to_float(row.get("air_temp_c"), -99) >= 35]

        if cold:
            first = cold[0]
            factors.append(ExternalFactor(
                type="temperature",
                name="低路温风险",
                description=f"{first['date']} {first['hour']:02d}:00 附近路温接近或低于 0°C",
                impact="high",
                source="context",
            ))
        if hot:
            first = hot[0]
            factors.append(ExternalFactor(
                type="temperature",
                name="高温时段",
                description=f"{first['date']} {first['hour']:02d}:00 附近气温较高",
                impact="moderate",
                source="context",
            ))
        return factors

    def _holiday_factors(self, rows: List[Dict[str, Any]], road: str) -> List[ExternalFactor]:
        factors = []
        for row in rows:
            date = row.get("date")
            public_count = self._to_float(row.get("public_holiday_count"), 0)
            school_count = self._to_float(row.get("school_holiday_count"), 0)
            in_window = self._truthy(row.get("in_traffic_window"))
            road_direction = row.get(f"{road.lower()}_direction", "") if road else ""

            if public_count > 0:
                names = self._join_names(row, ["public_names_DE_BY", "public_names_AT_SB", "public_names_AT_TI"])
                factors.append(ExternalFactor(
                    type="holiday",
                    name=f"{date} 公共假期",
                    description=names or "公共假期叠加，预计出行需求增加",
                    impact="high",
                    source="context",
                ))
            if school_count > 0:
                names = self._join_names(row, ["school_names_DE_BY", "school_names_AT_SB", "school_names_AT_TI"])
                factors.append(ExternalFactor(
                    type="school_holiday",
                    name=f"{date} 学校假期",
                    description=names or "学校假期期间家庭出游增多",
                    impact="moderate",
                    source="context",
                ))
            if in_window:
                direction_text = f"，{road} 方向: {road_direction}" if road_direction else ""
                risk = row.get("window_risk_level", "")
                factors.append(ExternalFactor(
                    type="holiday_window",
                    name=f"{date} 假期交通窗口",
                    description=f"风险等级 {risk}{direction_text}",
                    impact="high" if risk == "high" else "moderate",
                    source="context",
                ))
        return factors

    def _construction_factors(self, rows: List[Dict[str, Any]], road: str) -> List[ExternalFactor]:
        factors = []
        road_lower = road.lower() if road else ""
        for row in rows:
            date = row.get("date")
            road_count = self._to_float(row.get(f"{road_lower}_construction_count"), 0) if road_lower else 0
            total_count = self._to_float(row.get("construction_count"), 0)
            if road_count <= 0 and total_count <= 0:
                continue

            closed_lanes = self._to_float(row.get("sum_closed_lanes"), 0)
            titles = row.get("construction_titles") or ""
            factors.append(ExternalFactor(
                type="construction",
                name=f"{date} {road} 施工",
                description=(
                    f"施工记录 {int(road_count or total_count)} 条，关闭车道合计 {closed_lanes:g}。"
                    f"{titles[:160]}"
                ),
                impact="high" if closed_lanes >= 2 else "moderate",
                source="context",
            ))
        return factors

    def _event_factors(self, rows: List[Dict[str, Any]]) -> List[ExternalFactor]:
        factors = []
        for row in rows:
            if not self._truthy(row.get("has_special_event")):
                continue

            score = self._to_float(row.get("impact_score"), 0)
            names = row.get("active_event_names") or row.get("start_event_names") or "特殊活动"
            cities = row.get("active_event_cities") or ""
            factors.append(ExternalFactor(
                type="event",
                name=f"{row.get('date')} 活动影响",
                description=f"{names[:180]} {cities}".strip(),
                impact="high" if score >= 3 else "moderate" if score >= 2 else "low",
                source="context",
            ))
        return factors

    def _traffic_factors(self, rows: List[Dict[str, Any]], road: str) -> List[ExternalFactor]:
        if not rows:
            return []

        slow_rows = [row for row in rows if self._to_float(row.get("v_kfz"), 999) <= 80]
        heavy_rows = [row for row in rows if self._to_float(row.get("kfz_h"), 0) >= 2500]
        factors = []

        if slow_rows:
            row = min(slow_rows, key=lambda item: self._to_float(item.get("v_kfz"), 999))
            factors.append(ExternalFactor(
                type="historical_traffic",
                name="历史低速参考",
                description=(
                    f"{row['date']} {row['hour']:02d}:00 {road} {row.get('site_name')} "
                    f"历史速度约 {row.get('v_kfz')} km/h"
                ),
                impact="moderate",
                source="context",
            ))
        if heavy_rows:
            row = max(heavy_rows, key=lambda item: self._to_float(item.get("kfz_h"), 0))
            factors.append(ExternalFactor(
                type="historical_traffic",
                name="历史高流量参考",
                description=(
                    f"{row['date']} {row['hour']:02d}:00 {road} {row.get('site_name')} "
                    f"历史流量约 {row.get('kfz_h')} 辆/小时"
                ),
                impact="moderate",
                source="context",
            ))
        return factors

    def _historical_same_period_factors(self, historical: Dict[str, List[Dict[str, Any]]], road: str) -> List[ExternalFactor]:
        """从往年同期数据中生成参考因素。"""
        if not isinstance(historical, dict):
            return []

        traffic = historical.get("hourly_traffic", [])
        temperature = historical.get("temperature_road", [])
        construction = historical.get("construction", [])
        events = historical.get("events", [])
        factors = []

        traffic_speeds = [self._to_float(row.get("v_kfz")) for row in traffic]
        traffic_speeds = [value for value in traffic_speeds if value is not None]
        traffic_volumes = [self._to_float(row.get("kfz_h")) for row in traffic]
        traffic_volumes = [value for value in traffic_volumes if value is not None]
        years = self._source_years(historical)
        year_text = ", ".join(years) if years else "往年"

        if traffic_speeds or traffic_volumes:
            avg_speed = round(sum(traffic_speeds) / len(traffic_speeds), 1) if traffic_speeds else None
            max_volume = max(traffic_volumes) if traffic_volumes else None
            details = []
            if avg_speed is not None:
                details.append(f"平均速度约 {avg_speed:g} km/h")
            if max_volume is not None:
                details.append(f"最高小时流量约 {max_volume:g} 辆/小时")

            impact = "moderate"
            if (avg_speed is not None and avg_speed <= 80) or (max_volume is not None and max_volume >= 3000):
                impact = "high"

            factors.append(ExternalFactor(
                type="historical_same_period",
                name="往年同期交通参考",
                description=f"{year_text} 同期 {road} 共有 {len(traffic)} 条小时交通记录，" + "，".join(details),
                impact=impact,
                source="context_history",
            ))

        hot_rows = [row for row in temperature if self._to_float(row.get("air_temp_c"), -99) >= 35]
        cold_rows = [row for row in temperature if self._to_float(row.get("road_temp_c"), 99) <= 0]
        if hot_rows:
            first = hot_rows[0]
            factors.append(ExternalFactor(
                type="historical_same_period_weather",
                name="往年同期高温参考",
                description=f"{first.get('source_date')} {first.get('hour'):02d}:00 同期气温较高，目标日期映射为 {first.get('date')}",
                impact="moderate",
                source="context_history",
            ))
        if cold_rows:
            first = cold_rows[0]
            factors.append(ExternalFactor(
                type="historical_same_period_weather",
                name="往年同期低路温参考",
                description=f"{first.get('source_date')} {first.get('hour'):02d}:00 同期路温接近或低于 0°C",
                impact="high",
                source="context_history",
            ))

        if construction:
            factors.append(ExternalFactor(
                type="historical_same_period_construction",
                name="往年同期施工参考",
                description=f"{year_text} 同期找到 {len(construction)} 条施工日级记录，可作为季节性道路施工参考",
                impact="moderate",
                source="context_history",
            ))

        if events:
            factors.append(ExternalFactor(
                type="historical_same_period_event",
                name="往年同期活动参考",
                description=f"{year_text} 同期找到 {len(events)} 条活动日级记录，可辅助判断旅游季活动影响",
                impact="moderate",
                source="context_history",
            ))

        return factors

    def _count_active_days(self, rows: List[Dict[str, Any]], flag: str) -> int:
        return sum(1 for row in rows if self._truthy(row.get(flag)))

    def _truthy(self, value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def _to_float(self, value: Any, default: float = None):
        try:
            if value in {None, ""}:
                return default
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default

    def _first_number(self, row: Dict[str, Any], keys: List[str]):
        for key in keys:
            value = self._to_float(row.get(key))
            if value is not None:
                return value
        return None

    def _join_names(self, row: Dict[str, Any], keys: List[str]) -> str:
        names = []
        for key in keys:
            value = str(row.get(key, "")).strip()
            if value and value not in names:
                names.append(value)
        return "; ".join(names)

    def _source_years(self, historical: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        if not isinstance(historical, dict):
            return []

        years = set()
        for rows in historical.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                year = row.get("source_year") or str(row.get("source_date", ""))[:4]
                if year:
                    years.add(str(year))
        return sorted(years)