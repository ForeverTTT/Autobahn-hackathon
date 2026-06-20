"""
IntentParser - 意图解析器
使用 LLM 充分理解用户自然语言输入，智能识别用户画像和时间范围
LLM 失败时自动降级到关键词匹配
"""
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ..models import UserType
from ..personas import PersonaType, PersonaProfile, get_persona


class TimeRangeType(str, Enum):
    """时间范围类型"""
    TODAY = "today"              # 今天
    TOMORROW = "tomorrow"        # 明天
    THIS_WEEK = "this_week"      # 本周
    NEXT_WEEK = "next_week"      # 下周
    THIS_WEEKEND = "this_weekend"  # 这周末
    NEXT_WEEKEND = "next_weekend"  # 下周末
    THIS_MONTH = "this_month"    # 本月
    NEXT_MONTH = "next_month"    # 下月
    SUMMER = "summer"            # 暑假 (7-8月)
    WINTER = "winter"            # 寒假/冬季 (12-2月)
    CHRISTMAS = "christmas"      # 圣诞节期间
    EASTER = "easter"            # 复活节期间
    CUSTOM = "custom"            # 自定义范围
    FLEXIBLE = "flexible"        # 灵活/未指定


class TripType(str, Enum):
    """行程类型"""
    ONE_WAY = "one_way"          # 单程
    ROUND_TRIP = "round_trip"    # 往返
    COMMUTE = "commute"          # 通勤（每日往返）


class DataGranularity(str, Enum):
    """数据粒度"""
    HOURLY = "hourly"      # 小时级 - 今天
    DAILY = "daily"        # 日级 - 一周内
    WEEKLY = "weekly"      # 周级 - 一个月以上
    MONTHLY = "monthly"    # 月级 - 跨季度


@dataclass
class TimeRange:
    """时间范围"""
    type: TimeRangeType
    start_date: str              # YYYY-MM-DD
    end_date: str                # YYYY-MM-DD
    duration_days: int           # 天数
    description: str             # "暑假", "下周末" 等


@dataclass
class TripPlan:
    """行程计划（支持往返）"""
    trip_type: TripType
    # 去程
    outbound_date: Optional[str] = None      # 出发日期
    outbound_time: Optional[str] = None      # 建议出发时间
    # 返程
    return_date: Optional[str] = None        # 返回日期
    return_time: Optional[str] = None        # 建议返回时间
    # 停留
    stay_days: int = 0                       # 停留天数
    # LLM 分析结果
    outbound_analysis: Optional[str] = None  # 去程分析
    return_analysis: Optional[str] = None    # 返程分析
    recommendation: Optional[str] = None     # 综合建议


@dataclass
class DataRequirements:
    """数据需求"""
    time_range: TimeRange
    granularity: DataGranularity
    hours: List[int]
    features: List[str]


@dataclass
class ParsedIntent:
    """解析结果"""
    # 基础信息
    user_type: UserType
    persona_type: PersonaType
    destination: Optional[str]
    road: str
    intent: str

    # 用户画像
    core_question: str

    # 时间范围（智能识别）
    time_range: TimeRange

    # 行程计划（支持往返）
    trip_plan: Optional[TripPlan] = None

    # 数据需求
    data_requirements: DataRequirements = None


# ============ LLM System Prompt ============

SYSTEM_PROMPT = """你是 AlpineFlow 交通智能助手。

你的任务是**充分理解**用户的自然语言输入，进行**完整的意图分析**，包括：
1. 识别用户画像
2. 理解时间范围
3. 判断是否需要往返
4. 给出初步的出行建议

## 1. persona (用户画像)

| persona | 核心问题 | 特征 |
|---------|----------|------|
| commuter | 几点出发能准时？ | 上班、下班、通勤、每天 |
| traveler | 哪天出行最好？ | 带家人、度假、自驾游、暑假 |
| logistics | 哪段路会延误？ | 送货、货车、运输、物流 |
| tourist | 告诉我怎么做 | 第一次来、不熟悉、游客 |
| operator | 为什么会拥堵？ | 管理、监控、分析原因 |

## 2. trip_type (行程类型) - 重要！

判断用户是否需要往返：

| 类型 | 场景 | 示例 |
|------|------|------|
| round_trip | 旅行、度假、周末游 | "周末去萨尔茨堡" → 需要返程 |
| commute | 每日通勤 | "上班" → 早去晚回 |
| one_way | 单程、搬家、送人 | "送朋友去机场" → 单程 |

**默认规则**：
- 旅行/度假场景 → round_trip
- 通勤场景 → commute
- 明确说"去"但没说"回" → 推断为 round_trip

## 3. time_range (时间范围)

| 类型 | 用户表达 | 计算规则 |
|------|----------|----------|
| today | 今天 | 当天 |
| tomorrow | 明天 | 明天 |
| this_weekend | 这周末 | 本周六-周日 |
| next_weekend | 下周末 | 下周六-周日 |
| summer | 暑假、夏天 | 7月1日-8月31日 |
| winter | 寒假、滑雪 | 12月1日-2月28日 |
| christmas | 圣诞节 | 12月20日-1月6日 |

## 4. stay_days (停留天数)

根据场景推断：
- "周末去" → 1-2天
- "暑假旅行" → 用户可能停留3-7天，需要询问
- "度假一周" → 7天
- 通勤 → 0天（当天往返）

## 输出格式

```json
{
    "persona": "traveler",
    "trip_type": "round_trip",
    "time_range": {
        "type": "summer",
        "start_date": "2026-07-01",
        "end_date": "2026-08-31",
        "description": "暑假"
    },
    "trip_plan": {
        "outbound_date": "建议的出发日期或null",
        "outbound_time": "建议的出发时间或null",
        "return_date": "建议的返回日期或null",
        "return_time": "建议的返回时间或null",
        "stay_days": 3,
        "outbound_analysis": "去程交通分析",
        "return_analysis": "返程交通分析",
        "recommendation": "综合建议"
    },
    "destination": "salzburg",
    "road": "A8",
    "intent": "plan",
    "needs_clarification": false,
    "clarification_question": null
}
```

## 分析要点

1. **往返分析**：去程和返程的交通状况通常不同
   - 周五去程拥堵（大家出城）
   - 周日返程拥堵（大家回城）
   - 暑假期间双向都可能拥堵

2. **时间建议**：
   - 去程：建议避开出城高峰
   - 返程：建议避开返城高峰
   - 给出具体时间点

3. **如果信息不足**：设置 needs_clarification=true，并提供 clarification_question
"""


class IntentParser:
    """
    意图解析器

    核心功能:
    1. 使用 LLM 进行完整意图分析（包括往返判断）
    2. LLM 失败时自动降级到关键词匹配
    3. 智能识别时间范围（支持模糊时间如"暑假"）
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self._llm_client = None

    def _get_llm_client(self):
        """延迟加载 LLM 客户端"""
        if self._llm_client is None:
            try:
                from ..llm import LLMClient
                self._llm_client = LLMClient()
            except Exception as e:
                print(f"Warning: LLM client init failed: {e}")
                self._llm_client = False
        return self._llm_client

    async def parse_async(self, query: str, default_user_type: UserType = None) -> ParsedIntent:
        """异步解析用户查询 (优先使用 LLM，失败时降级到关键词匹配)"""
        if self.use_llm:
            llm_client = self._get_llm_client()
            if llm_client:
                try:
                    return await self._parse_with_llm(query, default_user_type, llm_client)
                except Exception as e:
                    print(f"LLM parsing failed: {e}, falling back to keyword matching")

        # Fallback: 关键词匹配
        return self.parse(query, default_user_type)

    async def _parse_with_llm(
        self,
        query: str,
        default_user_type: UserType,
        llm_client,
    ) -> ParsedIntent:
        """使用 LLM 直接进行完整的意图分析"""
        today = datetime.now()
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        # 构建上下文信息
        context = f"""今天是 {today.strftime("%Y-%m-%d")} ({weekday_names[today.weekday()]})
今年是 {today.year} 年

已知的交通规律：
- 周五下午/傍晚：出城方向拥堵（大家去度假）
- 周日下午/傍晚：返城方向拥堵（大家回家）
- 暑假期间（7-8月）：双向都可能拥堵，尤其是周末
- 圣诞/新年：12月23-26日、1月1-2日是高峰
- 滑雪季：周六早上去、周日下午回

用户输入: "{query}"

请进行完整的意图分析，包括：
1. 识别用户画像
2. 理解时间范围（计算具体日期）
3. 判断是否需要往返
4. 分析去程和返程的交通状况
5. 给出具体的出行建议

返回 JSON 格式。"""

        result = await llm_client.generate_json(context, SYSTEM_PROMPT)

        # 解析 persona
        persona_str = result.get("persona", "tourist")
        persona_type = self._str_to_persona(persona_str)
        user_type = self._persona_to_user_type(persona_type, default_user_type)

        # 解析时间范围
        time_range = self._parse_time_range(result.get("time_range", {}), today)

        # 解析行程计划（往返）
        trip_plan = self._parse_trip_plan(result, persona_type)

        # 解析其他字段
        destination = result.get("destination")
        if destination == "null" or destination is None:
            destination = None

        road = result.get("road", "A8")
        intent = result.get("intent", "general")

        # 获取用户画像
        persona = get_persona(persona_type)

        # 根据时间范围确定数据需求
        data_req = self._build_data_requirements(persona, time_range)

        return ParsedIntent(
            user_type=user_type,
            persona_type=persona_type,
            destination=destination,
            road=road,
            intent=intent,
            core_question=persona.core_question,
            time_range=time_range,
            trip_plan=trip_plan,
            data_requirements=data_req,
        )

    def _parse_trip_plan(self, result: Dict, persona_type: PersonaType) -> TripPlan:
        """解析行程计划"""
        # 获取行程类型
        trip_type_str = result.get("trip_type", "round_trip")
        try:
            trip_type = TripType(trip_type_str)
        except ValueError:
            # 根据用户画像推断
            if persona_type == PersonaType.COMMUTER:
                trip_type = TripType.COMMUTE
            elif persona_type in [PersonaType.FAMILY_TRAVELER, PersonaType.TOURIST]:
                trip_type = TripType.ROUND_TRIP
            else:
                trip_type = TripType.ONE_WAY

        # 解析 LLM 返回的行程计划
        plan_data = result.get("trip_plan", {})

        return TripPlan(
            trip_type=trip_type,
            outbound_date=plan_data.get("outbound_date"),
            outbound_time=plan_data.get("outbound_time"),
            return_date=plan_data.get("return_date"),
            return_time=plan_data.get("return_time"),
            stay_days=plan_data.get("stay_days", 0),
            outbound_analysis=plan_data.get("outbound_analysis"),
            return_analysis=plan_data.get("return_analysis"),
            recommendation=plan_data.get("recommendation"),
        )

    def _parse_time_range(self, time_range_data: Dict, today: datetime) -> TimeRange:
        """解析时间范围"""
        range_type_str = time_range_data.get("type", "flexible")
        start_str = time_range_data.get("start_date")
        end_str = time_range_data.get("end_date")
        description = time_range_data.get("description", "")

        # 转换类型
        try:
            range_type = TimeRangeType(range_type_str)
        except ValueError:
            range_type = TimeRangeType.FLEXIBLE

        # 解析日期
        if start_str and start_str != "null":
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
            except:
                start_date = today
        else:
            start_date = today

        if end_str and end_str != "null":
            try:
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
            except:
                end_date = start_date
        else:
            end_date = start_date

        # 如果 LLM 没返回具体日期，根据类型计算
        if range_type != TimeRangeType.FLEXIBLE and start_str is None:
            start_date, end_date = self._calculate_date_range(range_type, today)

        duration_days = (end_date - start_date).days + 1

        return TimeRange(
            type=range_type,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            duration_days=duration_days,
            description=description or range_type.value,
        )

    def _calculate_date_range(self, range_type: TimeRangeType, today: datetime) -> Tuple[datetime, datetime]:
        """根据时间范围类型计算具体日期"""
        year = today.year

        if range_type == TimeRangeType.TODAY:
            return today, today

        elif range_type == TimeRangeType.TOMORROW:
            tomorrow = today + timedelta(days=1)
            return tomorrow, tomorrow

        elif range_type == TimeRangeType.THIS_WEEK:
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return start, end

        elif range_type == TimeRangeType.NEXT_WEEK:
            start = today - timedelta(days=today.weekday()) + timedelta(days=7)
            end = start + timedelta(days=6)
            return start, end

        elif range_type == TimeRangeType.THIS_WEEKEND:
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0 and today.weekday() == 6:  # 今天是周日
                start = today - timedelta(days=1)
            else:
                start = today + timedelta(days=days_until_saturday)
            end = start + timedelta(days=1)
            return start, end

        elif range_type == TimeRangeType.NEXT_WEEKEND:
            days_until_saturday = (5 - today.weekday()) % 7
            start = today + timedelta(days=days_until_saturday + 7)
            end = start + timedelta(days=1)
            return start, end

        elif range_type == TimeRangeType.SUMMER:
            # 暑假: 7月1日 - 8月31日
            start = datetime(year, 7, 1)
            end = datetime(year, 8, 31)
            # 如果已经过了暑假，看明年
            if today > end:
                start = datetime(year + 1, 7, 1)
                end = datetime(year + 1, 8, 31)
            return start, end

        elif range_type == TimeRangeType.WINTER:
            # 冬季/滑雪季: 12月1日 - 2月28日
            if today.month >= 12:
                start = datetime(year, 12, 1)
                end = datetime(year + 1, 2, 28)
            elif today.month <= 2:
                start = datetime(year - 1, 12, 1)
                end = datetime(year, 2, 28)
            else:
                start = datetime(year, 12, 1)
                end = datetime(year + 1, 2, 28)
            return start, end

        elif range_type == TimeRangeType.CHRISTMAS:
            # 圣诞期间: 12月20日 - 1月6日
            if today.month >= 12 or today.month == 1:
                if today.month == 1:
                    start = datetime(year - 1, 12, 20)
                    end = datetime(year, 1, 6)
                else:
                    start = datetime(year, 12, 20)
                    end = datetime(year + 1, 1, 6)
            else:
                start = datetime(year, 12, 20)
                end = datetime(year + 1, 1, 6)
            return start, end

        elif range_type == TimeRangeType.EASTER:
            # 复活节: 简化处理，假设在4月
            start = datetime(year, 4, 1)
            end = datetime(year, 4, 15)
            if today > end:
                start = datetime(year + 1, 4, 1)
                end = datetime(year + 1, 4, 15)
            return start, end

        else:
            # FLEXIBLE 或 CUSTOM
            return today, today

    def _build_data_requirements(self, persona: PersonaProfile, time_range: TimeRange) -> DataRequirements:
        """根据用户画像和时间范围构建数据需求"""
        duration = time_range.duration_days

        # 根据时间跨度确定粒度
        if duration <= 1:
            granularity = DataGranularity.HOURLY
        elif duration <= 7:
            granularity = DataGranularity.DAILY
        elif duration <= 60:
            granularity = DataGranularity.WEEKLY
        else:
            granularity = DataGranularity.MONTHLY

        # 根据画像和粒度确定小时
        if granularity == DataGranularity.HOURLY:
            # 小时级：根据画像
            hours = persona.data_needs.get("hours", list(range(6, 22)))
        else:
            # 日级/周级/月级：全天
            hours = list(range(6, 22))

        # 功能列表
        features = persona.data_needs.get("features", [])

        # 根据时间跨度添加额外功能
        if duration > 7:
            features = features + ["holiday_calendar", "event_calendar", "best_windows"]
        if duration > 30:
            features = features + ["seasonal_analysis", "monthly_comparison"]

        return DataRequirements(
            time_range=time_range,
            granularity=granularity,
            hours=hours,
            features=list(set(features)),  # 去重
        )

    def _str_to_persona(self, persona_str: str) -> PersonaType:
        """字符串转 PersonaType"""
        mapping = {
            "commuter": PersonaType.COMMUTER,
            "traveler": PersonaType.FAMILY_TRAVELER,
            "logistics": PersonaType.LOGISTICS,
            "tourist": PersonaType.TOURIST,
            "operator": PersonaType.OPERATOR,
        }
        return mapping.get(persona_str.lower(), PersonaType.TOURIST)

    def _persona_to_user_type(self, persona: PersonaType, default: UserType = None) -> UserType:
        """PersonaType 转 UserType"""
        mapping = {
            PersonaType.COMMUTER: UserType.RESIDENT,
            PersonaType.FAMILY_TRAVELER: UserType.TRAVELER,
            PersonaType.LOGISTICS: UserType.LOGISTICS,
            PersonaType.TOURIST: UserType.TRAVELER,
            PersonaType.OPERATOR: UserType.AUTHORITY,
        }
        return mapping.get(persona, default or UserType.TRAVELER)

    # ============ Fallback: 关键词匹配 ============

    def parse(self, query: str, default_user_type: UserType = None) -> ParsedIntent:
        """同步解析 (关键词匹配，作为 LLM 的 fallback)"""
        query_lower = query.lower()
        today = datetime.now()

        # 1. 识别 persona
        persona_type = self._parse_persona_keywords(query_lower)
        user_type = self._persona_to_user_type(persona_type, default_user_type)

        # 2. 解析时间范围
        time_range = self._parse_time_range_keywords(query, today)

        # 3. 推断行程类型
        trip_plan = self._infer_trip_plan(persona_type, time_range)

        # 4. 解析目的地和道路
        destination = self._parse_destination_keywords(query_lower)
        road = self._parse_road_keywords(query_lower)

        # 5. 解析意图
        intent = self._parse_intent_keywords(query_lower)

        # 6. 获取画像和数据需求
        persona = get_persona(persona_type)
        data_req = self._build_data_requirements(persona, time_range)

        return ParsedIntent(
            user_type=user_type,
            persona_type=persona_type,
            destination=destination,
            road=road,
            intent=intent,
            core_question=persona.core_question,
            time_range=time_range,
            trip_plan=trip_plan,
            data_requirements=data_req,
        )

    def _infer_trip_plan(self, persona_type: PersonaType, time_range: TimeRange) -> TripPlan:
        """根据画像和时间范围推断行程类型"""
        if persona_type == PersonaType.COMMUTER:
            trip_type = TripType.COMMUTE
        elif persona_type in [PersonaType.FAMILY_TRAVELER, PersonaType.TOURIST]:
            trip_type = TripType.ROUND_TRIP
        else:
            trip_type = TripType.ONE_WAY

        # 推断停留天数
        if trip_type == TripType.ROUND_TRIP:
            if time_range.type == TimeRangeType.THIS_WEEKEND:
                stay_days = 1
            elif time_range.type == TimeRangeType.NEXT_WEEKEND:
                stay_days = 1
            else:
                stay_days = min(3, time_range.duration_days)
        else:
            stay_days = 0

        return TripPlan(
            trip_type=trip_type,
            stay_days=stay_days,
        )

    def _parse_time_range_keywords(self, query: str, today: datetime) -> TimeRange:
        """使用关键词解析时间范围"""
        # 检测时间范围关键词
        if any(kw in query for kw in ["暑假", "夏天", "暑期", "summer"]):
            range_type = TimeRangeType.SUMMER
            start, end = self._calculate_date_range(range_type, today)
            desc = "暑假"

        elif any(kw in query for kw in ["寒假", "冬天", "滑雪", "winter", "ski"]):
            range_type = TimeRangeType.WINTER
            start, end = self._calculate_date_range(range_type, today)
            desc = "冬季"

        elif any(kw in query for kw in ["圣诞", "christmas", "新年"]):
            range_type = TimeRangeType.CHRISTMAS
            start, end = self._calculate_date_range(range_type, today)
            desc = "圣诞期间"

        elif any(kw in query for kw in ["复活节", "easter"]):
            range_type = TimeRangeType.EASTER
            start, end = self._calculate_date_range(range_type, today)
            desc = "复活节"

        elif any(kw in query for kw in ["下周末", "next weekend"]):
            range_type = TimeRangeType.NEXT_WEEKEND
            start, end = self._calculate_date_range(range_type, today)
            desc = "下周末"

        elif any(kw in query for kw in ["这周末", "周末", "this weekend", "weekend"]):
            range_type = TimeRangeType.THIS_WEEKEND
            start, end = self._calculate_date_range(range_type, today)
            desc = "这周末"

        elif any(kw in query for kw in ["下周", "next week"]):
            range_type = TimeRangeType.NEXT_WEEK
            start, end = self._calculate_date_range(range_type, today)
            desc = "下周"

        elif any(kw in query for kw in ["这周", "本周", "this week"]):
            range_type = TimeRangeType.THIS_WEEK
            start, end = self._calculate_date_range(range_type, today)
            desc = "本周"

        elif any(kw in query for kw in ["明天", "tomorrow"]):
            range_type = TimeRangeType.TOMORROW
            start, end = self._calculate_date_range(range_type, today)
            desc = "明天"

        elif any(kw in query for kw in ["今天", "today"]):
            range_type = TimeRangeType.TODAY
            start, end = self._calculate_date_range(range_type, today)
            desc = "今天"

        else:
            # 尝试解析具体日期
            date = self._parse_specific_date(query, today)
            if date:
                range_type = TimeRangeType.CUSTOM
                start, end = date, date
                desc = date.strftime("%Y-%m-%d")
            else:
                range_type = TimeRangeType.FLEXIBLE
                start, end = today, today
                desc = "灵活"

        duration = (end - start).days + 1

        return TimeRange(
            type=range_type,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            duration_days=duration,
            description=desc,
        )

    def _parse_specific_date(self, query: str, today: datetime) -> Optional[datetime]:
        """解析具体日期"""
        # 周几
        weekday_map = {
            "周一": 0, "周二": 1, "周三": 2, "周四": 3,
            "周五": 4, "周六": 5, "周日": 6, "周天": 6,
        }
        for keyword, target_weekday in weekday_map.items():
            if keyword in query:
                current_weekday = today.weekday()
                days_ahead = (target_weekday - current_weekday) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return today + timedelta(days=days_ahead)

        # 具体日期格式
        patterns = [
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            (r"(\d{1,2})月(\d{1,2})[日号]?", lambda m: datetime(today.year, int(m.group(1)), int(m.group(2)))),
            (r"(\d{1,2})[/-](\d{1,2})", lambda m: datetime(today.year, int(m.group(1)), int(m.group(2)))),
        ]
        for pattern, parser in patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    return parser(match)
                except:
                    continue

        return None

    # ============ 关键词常量 ============

    PERSONA_KEYWORDS = {
        PersonaType.COMMUTER: ["上班", "下班", "通勤", "每天", "工作日", "commute", "daily", "work"],
        PersonaType.FAMILY_TRAVELER: ["带家人", "带孩子", "周末出游", "度假", "旅行", "自驾游", "暑假", "假期", "family", "vacation", "trip", "holiday"],
        PersonaType.LOGISTICS: ["送货", "运输", "货车", "物流", "配送", "快递", "卡车", "拉货", "truck", "delivery", "logistics"],
        PersonaType.TOURIST: ["第一次", "不熟悉", "游客", "旅游", "tourist", "visit", "new to"],
        PersonaType.OPERATOR: ["管理", "监控", "交警", "为什么堵", "原因", "分析", "operator", "manage", "why"],
    }

    DESTINATION_KEYWORDS = {
        "salzburg": ["萨尔茨堡", "salzburg", "奥地利", "austria"],
        "innsbruck": ["因斯布鲁克", "innsbruck", "滑雪", "阿尔卑斯", "alps"],
    }

    def _parse_persona_keywords(self, query: str) -> PersonaType:
        """使用关键词解析用户画像"""
        for persona, keywords in self.PERSONA_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return persona
        return PersonaType.TOURIST

    def _parse_destination_keywords(self, query: str) -> Optional[str]:
        """使用关键词解析目的地"""
        for dest, keywords in self.DESTINATION_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return dest
        return None

    def _parse_road_keywords(self, query: str) -> str:
        """使用关键词解析道路"""
        if "a93" in query or "93" in query:
            return "A93"
        return "A8"

    def _parse_intent_keywords(self, query: str) -> str:
        """使用关键词解析意图"""
        if any(kw in query for kw in ["出发", "什么时候", "几点", "最佳", "推荐", "建议", "plan"]):
            return "plan"
        elif any(kw in query for kw in ["对比", "比较", "哪天好", "compare"]):
            return "compare"
        elif any(kw in query for kw in ["施工", "修路", "封路", "construction"]):
            return "construction"
        elif any(kw in query for kw in ["活动", "音乐节", "啤酒节", "event"]):
            return "events"
        elif any(kw in query for kw in ["预测", "拥堵", "路况", "forecast"]):
            return "forecast"
        else:
            return "general"
