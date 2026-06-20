"""
SearchAgent - 搜索Agent
实时搜索更新数据（天气预报、施工公告、活动信息）
"""
from typing import List
from datetime import datetime, timedelta

from .base import BaseAgent
from ..models import AgentRequest, AgentResponse, ExternalFactor


class SearchAgent(BaseAgent):
    """
    搜索Agent

    职责:
    - 实时搜索天气预报（最近15天）
    - 搜索政府施工公告
    - 搜索活动信息（音乐节、啤酒节等）
    - 搜索事故/临时封路信息

    注: 当前使用模拟数据，实际应接入:
    - 天气 API: OpenWeatherMap / DWD
    - 施工 API: https://autobahn.api.bund.dev/
    - 活动 API: 本地活动日历
    """

    @property
    def name(self) -> str:
        return "SearchAgent"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理搜索请求"""
        try:
            date = request.date
            road = request.road

            factors: List[ExternalFactor] = []

            # 1. 天气预报（实时）
            weather = await self._search_weather(date)
            factors.extend(weather)

            # 2. 施工公告（实时）
            construction = await self._search_construction(date, road)
            factors.extend(construction)

            # 3. 活动信息（实时）
            events = await self._search_events(date)
            factors.extend(events)

            # 4. 事故信息（实时）
            incidents = await self._search_incidents(date, road)
            factors.extend(incidents)

            return self._success({
                "factors": factors,
                "date": date,
                "road": road,
                "search_time": datetime.now().isoformat(),
            })

        except Exception as e:
            return self._error(f"Search error: {str(e)}")

    async def _search_weather(self, date: str) -> List[ExternalFactor]:
        """
        搜索天气预报

        实际应接入: OpenWeatherMap API / DWD (德国气象局)
        限制: 只能获取未来 15 天
        """
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        today = datetime.now()
        days_ahead = (date_obj - today).days

        # 只能预报未来15天
        if days_ahead > 15:
            factors.append(ExternalFactor(
                type="weather",
                name="天气预报不可用",
                description=f"距离目标日期 {days_ahead} 天，超出15天预报范围",
                impact="low",
                source="search"
            ))
            return factors

        # 模拟天气预报（实际应调用 API）
        # TODO: 接入真实天气 API
        import random
        weather_options = [
            ("sunny", "晴天", "none"),
            ("cloudy", "多云", "none"),
            ("light_rain", "小雨", "low"),
            ("heavy_rain", "大雨", "moderate"),
            ("snow", "降雪", "high"),
        ]

        # 根据月份调整概率
        month = date_obj.month
        if month in [11, 12, 1, 2]:
            weights = [0.2, 0.3, 0.2, 0.1, 0.2]  # 冬季更可能降雪
        elif month in [4, 5, 10]:
            weights = [0.3, 0.3, 0.3, 0.1, 0.0]  # 春秋多雨
        else:
            weights = [0.5, 0.3, 0.15, 0.05, 0.0]  # 夏季多晴

        weather_code, weather_name, impact = random.choices(weather_options, weights)[0]

        if impact != "none":
            factors.append(ExternalFactor(
                type="weather",
                name=f"天气预报: {weather_name}",
                description=f"预计 {date} {weather_name}，请注意行车安全",
                impact=impact,
                source="search"
            ))

        return factors

    async def _search_construction(self, date: str, road: str) -> List[ExternalFactor]:
        """
        搜索施工公告

        实际应接入: https://autobahn.api.bund.dev/
        """
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")

        # 模拟施工数据（实际应调用 Autobahn API）
        # TODO: 接入 Autobahn API

        # A8 施工
        if road == "A8":
            if datetime(2026, 6, 1) <= date_obj <= datetime(2026, 9, 30):
                factors.append(ExternalFactor(
                    type="construction",
                    name="A8 桥梁翻新工程",
                    description="Rosenheim 附近 (km 85-90)，右车道封闭，预计延误 10-15 分钟",
                    impact="moderate",
                    source="search"
                ))

        # A93 施工
        if road == "A93":
            if datetime(2026, 7, 1) <= date_obj <= datetime(2026, 8, 31):
                factors.append(ExternalFactor(
                    type="construction",
                    name="A93 路面维修",
                    description="Kiefersfelden 边境附近，限速 80 km/h",
                    impact="low",
                    source="search"
                ))

        return factors

    async def _search_events(self, date: str) -> List[ExternalFactor]:
        """
        搜索活动信息

        重大活动对交通影响很大
        """
        factors = []

        date_obj = datetime.strptime(date, "%Y-%m-%d")

        # 萨尔茨堡音乐节 (7月中 - 8月底)
        if datetime(2026, 7, 18) <= date_obj <= datetime(2026, 8, 31):
            factors.append(ExternalFactor(
                type="event",
                name="萨尔茨堡音乐节",
                description="Salzburg Festival 期间，A8 往萨尔茨堡方向下午拥堵加剧",
                impact="high",
                source="search"
            ))

        # 慕尼黑啤酒节 (9月中 - 10月初)
        if datetime(2026, 9, 19) <= date_obj <= datetime(2026, 10, 4):
            factors.append(ExternalFactor(
                type="event",
                name="慕尼黑啤酒节",
                description="Oktoberfest 期间，慕尼黑周边交通压力极大，周末尤为严重",
                impact="very_high",
                source="search"
            ))

        # 圣诞市场 (11月底 - 12月底)
        if datetime(2026, 11, 25) <= date_obj <= datetime(2026, 12, 26):
            factors.append(ExternalFactor(
                type="event",
                name="圣诞市场季",
                description="各地圣诞市场开放，周末市区及周边交通繁忙",
                impact="moderate",
                source="search"
            ))

        return factors

    async def _search_incidents(self, date: str, road: str) -> List[ExternalFactor]:
        """
        搜索事故/临时封路信息

        实际应接入实时交通信息 API
        """
        # 当前不模拟事故（事故是实时的，无法预测）
        # 实际应用中应接入实时交通信息 API

        return []
