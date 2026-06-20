"""
IntentParser - 意图解析器
使用 LLM 理解用户自然语言输入，识别用户画像并确定数据需求
"""
import re
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..models import UserType
from ..personas import (
    PersonaType, PersonaProfile, PERSONAS,
    get_persona, get_data_needs, USER_TYPE_TO_PERSONA,
)


@dataclass
class DataRequirements:
    """数据需求"""
    time_range: str          # today, week, flexible
    granularity: str         # hourly, daily, segment, simple, detailed
    hours: List[int]         # 关注的小时
    features: List[str]      # 需要的功能


@dataclass
class ParsedIntent:
    """解析结果"""
    # 基础信息
    user_type: UserType
    persona_type: PersonaType
    date: str
    destination: Optional[str]
    road: str
    intent: str

    # 用户画像
    core_question: str       # 用户核心问题

    # 数据需求
    data_requirements: DataRequirements


# LLM 系统提示
SYSTEM_PROMPT = """你是 AlpineFlow 交通助手的意图解析器。

你的任务是理解用户的自然语言输入，识别：

1. **persona** (用户画像) - 最重要！决定了用户需要什么样的帮助：
   - commuter: 日常通勤者，每天开车上下班，关心"能否准时到达"
   - traveler: 家庭旅行者，周末/假期出游，关心"哪天出行最好"
   - logistics: 物流司机，货运/快递，关心"哪里会延误"
   - tourist: 游客，不熟悉德国交通，需要"简单直接的建议"
   - operator: 交通管理者，关心"为什么会拥堵"

2. **date**: 目标日期 (YYYY-MM-DD)
   - "今天" → 今天日期
   - "明天" → 明天日期
   - "周六" → 最近的周六
   - "下周" → 需要一周的数据
   - 没提到 → null

3. **destination**: 目的地
   - salzburg: 萨尔茨堡、奥地利
   - innsbruck: 因斯布鲁克、滑雪、阿尔卑斯
   - 没提到 → null

4. **road**: 高速公路
   - A8: 慕尼黑-萨尔茨堡 (默认)
   - A93: 慕尼黑-因斯布鲁克

5. **intent**: 具体意图
   - plan: 规划出行
   - forecast: 查看预测
   - construction: 施工信息
   - events: 活动信息
   - general: 一般问题

识别 persona 的关键词示例：
- commuter: "上班"、"通勤"、"每天"、"下班"
- traveler: "带家人"、"周末出游"、"度假"、"旅行"
- logistics: "送货"、"运输"、"货车"、"物流"、"配送"
- tourist: "第一次来"、"不熟悉"、"游客"、"旅游"
- operator: "管理"、"监控"、"交警"、"为什么堵"

返回 JSON，不要其他文本。"""


class IntentParser:
    """
    意图解析器

    核心功能:
    1. 识别用户画像 (Persona)
    2. 理解用户核心问题
    3. 确定数据需求 (时间范围、粒度、功能)
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
        """
        异步解析用户查询 (使用 LLM)
        """
        if self.use_llm:
            llm_client = self._get_llm_client()
            if llm_client:
                try:
                    return await self._parse_with_llm(query, default_user_type, llm_client)
                except Exception as e:
                    print(f"LLM parsing failed: {e}, falling back to keyword matching")

        return self.parse(query, default_user_type)

    async def _parse_with_llm(
        self,
        query: str,
        default_user_type: UserType,
        llm_client,
    ) -> ParsedIntent:
        """使用 LLM 解析"""
        today = datetime.now()

        prompt = f"""今天是 {today.strftime("%Y-%m-%d")} ({["周一","周二","周三","周四","周五","周六","周日"][today.weekday()]})

用户输入: "{query}"

请分析并返回 JSON:
{{
    "persona": "commuter|traveler|logistics|tourist|operator",
    "date": "YYYY-MM-DD 或 null",
    "destination": "salzburg|innsbruck|null",
    "road": "A8|A93",
    "intent": "plan|forecast|construction|events|general"
}}"""

        result = await llm_client.generate_json(prompt, SYSTEM_PROMPT)

        # 解析 persona
        persona_str = result.get("persona", "tourist")
        persona_type = self._str_to_persona(persona_str)

        # 获取对应的 UserType (为了兼容)
        user_type = self._persona_to_user_type(persona_type, default_user_type)

        # 解析日期
        date = result.get("date")
        if not date:
            date = today.strftime("%Y-%m-%d")

        # 解析目的地
        destination = result.get("destination")
        if destination == "null" or destination is None:
            destination = None

        # 解析道路和意图
        road = result.get("road", "A8")
        intent = result.get("intent", "general")

        # 获取用户画像和数据需求
        persona = get_persona(persona_type)
        data_req = self._build_data_requirements(persona, date)

        return ParsedIntent(
            user_type=user_type,
            persona_type=persona_type,
            date=date,
            destination=destination,
            road=road,
            intent=intent,
            core_question=persona.core_question,
            data_requirements=data_req,
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
            PersonaType.TOURIST: UserType.TRAVELER,  # 游客也用 traveler
            PersonaType.OPERATOR: UserType.AUTHORITY,
        }
        return mapping.get(persona, default or UserType.TRAVELER)

    def _build_data_requirements(self, persona: PersonaProfile, date: str) -> DataRequirements:
        """根据用户画像构建数据需求"""
        needs = persona.data_needs

        return DataRequirements(
            time_range=needs.get("time_range", "today"),
            granularity=needs.get("granularity", "hourly"),
            hours=needs.get("hours", list(range(6, 22))),
            features=needs.get("features", []),
        )

    def parse(self, query: str, default_user_type: UserType = None) -> ParsedIntent:
        """
        同步解析 (关键词匹配，作为 fallback)
        """
        query_lower = query.lower()
        today = datetime.now()

        # 1. 识别 persona
        persona_type = self._parse_persona(query_lower)
        user_type = self._persona_to_user_type(persona_type, default_user_type)

        # 2. 解析日期
        date = self._parse_date(query) or today.strftime("%Y-%m-%d")

        # 3. 解析目的地和道路
        destination = self._parse_destination(query_lower)
        road = self._parse_road(query_lower)

        # 4. 解析意图
        intent = self._parse_intent(query_lower)

        # 5. 获取画像和数据需求
        persona = get_persona(persona_type)
        data_req = self._build_data_requirements(persona, date)

        return ParsedIntent(
            user_type=user_type,
            persona_type=persona_type,
            date=date,
            destination=destination,
            road=road,
            intent=intent,
            core_question=persona.core_question,
            data_requirements=data_req,
        )

    # ============ 关键词匹配 ============

    PERSONA_KEYWORDS = {
        PersonaType.COMMUTER: [
            "上班", "下班", "通勤", "每天", "工作日", "commute", "daily", "work"
        ],
        PersonaType.FAMILY_TRAVELER: [
            "带家人", "带孩子", "周末出游", "度假", "旅行", "family", "vacation", "trip"
        ],
        PersonaType.LOGISTICS: [
            "送货", "运输", "货车", "物流", "配送", "快递", "卡车", "truck", "delivery", "logistics"
        ],
        PersonaType.TOURIST: [
            "第一次", "不熟悉", "游客", "旅游", "tourist", "visit", "new to"
        ],
        PersonaType.OPERATOR: [
            "管理", "监控", "交警", "为什么堵", "原因", "分析", "operator", "manage", "why"
        ],
    }

    DESTINATION_KEYWORDS = {
        "salzburg": ["萨尔茨堡", "salzburg", "奥地利", "austria"],
        "innsbruck": ["因斯布鲁克", "innsbruck", "滑雪", "阿尔卑斯", "alps"],
    }

    DATE_KEYWORDS = {
        "今天": 0, "明天": 1, "后天": 2, "大后天": 3,
    }

    def _parse_persona(self, query: str) -> PersonaType:
        """解析用户画像"""
        for persona, keywords in self.PERSONA_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return persona
        return PersonaType.TOURIST  # 默认当游客

    def _parse_destination(self, query: str) -> Optional[str]:
        """解析目的地"""
        for dest, keywords in self.DESTINATION_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return dest
        return None

    def _parse_road(self, query: str) -> str:
        """解析道路"""
        if "a93" in query or "93" in query:
            return "A93"
        return "A8"

    def _parse_intent(self, query: str) -> str:
        """解析意图"""
        if any(kw in query for kw in ["出发", "什么时候", "几点", "最佳时间", "推荐", "建议", "plan"]):
            return "plan"
        elif any(kw in query for kw in ["施工", "修路", "封路", "construction"]):
            return "construction"
        elif any(kw in query for kw in ["活动", "音乐节", "啤酒节", "event"]):
            return "events"
        elif any(kw in query for kw in ["预测", "拥堵", "路况", "forecast"]):
            return "forecast"
        else:
            return "general"

    def _parse_date(self, query: str) -> Optional[str]:
        """解析日期"""
        today = datetime.now()

        # 相对日期
        for keyword, offset in self.DATE_KEYWORDS.items():
            if keyword in query:
                target = today + timedelta(days=offset)
                return target.strftime("%Y-%m-%d")

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
                target = today + timedelta(days=days_ahead)
                return target.strftime("%Y-%m-%d")

        # 具体日期格式
        patterns = [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
            r"(\d{1,2})月(\d{1,2})[日号]?",
            r"(\d{1,2})[/-](\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        return f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                    elif len(groups) == 2:
                        return f"{today.year}-{int(groups[0]):02d}-{int(groups[1]):02d}"
                except:
                    continue

        return None
