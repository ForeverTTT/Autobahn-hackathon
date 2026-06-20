"""
ContextAgent - 上下文Agent
查询 data_autobahn 中的外部因素（天气、假期、历史参考等）
"""
from typing import List
from datetime import datetime

from .base import BaseAgent
from ..models import AgentRequest, AgentResponse, ExternalFactor
from ..tools import context_loader


class ContextAgent(BaseAgent):
    """
    上下文Agent

    职责:
    - 查询 data_autobahn 中的外部因素
    - 天气、气温
    - 假期、学校假期
    - 季节性因素
    - 历史交通参考
    """

    @property
    def name(self) -> str:
        return "ContextAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理上下文请求"""
        try:
            date = request.date
            road = request.road

            factors: List[ExternalFactor] = []

            # 1. 天气因素
            weather_factors = self._get_weather_factors(date)
            factors.extend(weather_factors)

            # 2. 假期因素
            holiday_factors = self._get_holiday_factors(date)
            factors.extend(holiday_factors)

            # 3. 季节因素
            season_factors = self._get_season_factors(date)
            factors.extend(season_factors)

            # 4. 周末因素
            weekend_factors = self._get_weekend_factors(date)
            factors.extend(weekend_factors)

            # 5. 历史参考
            historical_ref = self._get_historical_reference(date, road)
            factors.extend(historical_ref)

            return self._success({
                "factors": factors,
                "date": date,
                "road": road,
            })

        except Exception as e:
            return self._error(f"Context error: {str(e)}")

    def _get_weather_factors(self, date: str) -> List[ExternalFactor]:
        """获取天气因素"""
        factors = []

        weather_data = context_loader.get_weather(date)

        if weather_data:
            # 根据实际数据字段处理
            temp = weather_data.get("temperature", weather_data.get("temp"))
            if temp and temp > 35:
                factors.append(ExternalFactor(
                    type="weather",
                    name="高温天气",
                    description=f"气温 {temp}°C，注意防暑",
                    impact="moderate",
                    source="context"
                ))

            rain = weather_data.get("rain", weather_data.get("precipitation"))
            if rain and rain > 5:
                factors.append(ExternalFactor(
                    type="weather",
                    name="降雨",
                    description="有降雨，路面湿滑，建议保持车距",
                    impact="moderate",
                    source="context"
                ))

        return factors

    def _get_holiday_factors(self, date: str) -> List[ExternalFactor]:
        """获取假期因素"""
        factors = []

        # 从数据文件获取
        holiday_data = context_loader.get_holiday(date)

        if holiday_data.get("is_holiday"):
            name = holiday_data.get("holiday_name", "公共假期")
            factors.append(ExternalFactor(
                type="holiday",
                name=name,
                description=f"{name} - 预计交通流量增加",
                impact="high",
                source="context"
            ))

        if holiday_data.get("is_school_holiday"):
            factors.append(ExternalFactor(
                type="school_holiday",
                name="学校假期",
                description="学校假期期间，家庭出游增多",
                impact="moderate",
                source="context"
            ))

        # 硬编码的德国假期（补充）
        german_holidays = {
            "01-01": ("元旦", "high"),
            "01-06": ("主显节", "moderate"),
            "05-01": ("劳动节", "moderate"),
            "10-03": ("德国统一日", "high"),
            "12-25": ("圣诞节", "very_high"),
            "12-26": ("圣诞节次日", "very_high"),
        }

        date_suffix = date[5:]  # MM-DD
        if date_suffix in german_holidays:
            name, impact = german_holidays[date_suffix]
            if not any(f.name == name for f in factors):
                factors.append(ExternalFactor(
                    type="holiday",
                    name=name,
                    description=f"{name} - 公共假期",
                    impact=impact,
                    source="context"
                ))

        return factors

    def _get_season_factors(self, date: str) -> List[ExternalFactor]:
        """获取季节因素"""
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        month = date_obj.month

        if month in [6, 7, 8]:
            factors.append(ExternalFactor(
                type="season",
                name="夏季旅游季",
                description="夏季旅游高峰，前往阿尔卑斯方向交通增加",
                impact="high",
                source="context"
            ))
        elif month in [12, 1, 2]:
            factors.append(ExternalFactor(
                type="season",
                name="冬季滑雪季",
                description="冬季滑雪季，前往奥地利方向交通增加",
                impact="moderate",
                source="context"
            ))

        return factors

    def _get_weekend_factors(self, date: str) -> List[ExternalFactor]:
        """获取周末因素"""
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.weekday()

        if weekday == 4:  # Friday
            factors.append(ExternalFactor(
                type="weekend",
                name="周五出行高峰",
                description="周五下午出城方向拥堵加剧",
                impact="moderate",
                source="context"
            ))
        elif weekday == 6:  # Sunday
            factors.append(ExternalFactor(
                type="weekend",
                name="周日返程高峰",
                description="周日下午返城方向拥堵加剧",
                impact="moderate",
                source="context"
            ))
        elif weekday >= 5:  # Weekend
            factors.append(ExternalFactor(
                type="weekend",
                name="周末",
                description="周末出游流量，上午出城、下午返程",
                impact="low",
                source="context"
            ))

        return factors

    def _get_historical_reference(self, date: str, road: str) -> List[ExternalFactor]:
        """获取历史参考"""
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")

        # 去年同期参考
        last_year = date_obj.replace(year=date_obj.year - 1)
        last_year_str = last_year.strftime("%Y-%m-%d")

        records = context_loader.get_construction(last_year_str, road)
        if records:
            factors.append(ExternalFactor(
                type="historical",
                name="历史参考",
                description=f"去年同期 ({last_year_str}) 有 {len(records)} 处施工",
                impact="low",
                source="context"
            ))

        return factors
