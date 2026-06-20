"""
Chat Assistant - 对话式出行助手
支持自然语言问答

使用方式：
1. 命令行: python -m agent.chat_assistant
2. API: 集成到 FastAPI/Flask
3. Streamlit: 可视化界面
"""
import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from .travel_assistant import (
    TravelAssistant,
    UserType,
    TravelPlan,
    ROUTES,
    TOOLS_SCHEMA,
)

# 尝试导入 LLM 库
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ============ 对话状态 ============

@dataclass
class ConversationState:
    """对话状态"""
    user_type: UserType = UserType.TRAVELER
    preferred_date: Optional[str] = None
    preferred_route: Optional[str] = None
    origin: str = "München"
    destination: Optional[str] = None
    history: List[Dict[str, str]] = None

    def __post_init__(self):
        if self.history is None:
            self.history = []


# ============ 意图解析（规则 + LLM） ============

class IntentParser:
    """意图解析器"""

    # 路线关键词映射
    DESTINATION_KEYWORDS = {
        "salzburg": ["萨尔茨堡", "salzburg", "奥地利"],
        "innsbruck": ["因斯布鲁克", "innsbruck", "滑雪", "阿尔卑斯"],
    }

    # 用户类型关键词
    USER_TYPE_KEYWORDS = {
        UserType.TRAVELER: ["旅游", "度假", "游客", "旅行", "出游", "玩"],
        UserType.RESIDENT: ["居民", "住在", "本地", "通勤", "上班"],
        UserType.LOGISTICS: ["物流", "货运", "运输", "送货", "快递", "卡车"],
        UserType.TOURISM: ["酒店", "餐厅", "旅游业", "游客接待", "民宿"],
        UserType.AUTHORITY: ["交通管理", "警察", "管理部门", "交警"],
    }

    # 日期关键词
    DATE_KEYWORDS = {
        "今天": 0, "明天": 1, "后天": 2,
        "周一": "monday", "周二": "tuesday", "周三": "wednesday",
        "周四": "thursday", "周五": "friday", "周六": "saturday", "周日": "sunday",
        "这周末": "weekend", "下周末": "next_weekend",
    }

    def parse(self, query: str, state: ConversationState) -> Dict[str, Any]:
        """
        解析用户意图

        Returns:
            {
                "intent": "plan" | "forecast" | "construction" | "compare" | "chat",
                "date": "2026-07-25",
                "destination": "salzburg",
                "user_type": UserType,
                "parameters": {...}
            }
        """
        query_lower = query.lower()

        result = {
            "intent": "chat",
            "date": state.preferred_date,
            "destination": state.destination,
            "user_type": state.user_type,
            "parameters": {},
        }

        # 1. 解析日期
        date = self._parse_date(query)
        if date:
            result["date"] = date

        # 2. 解析目的地
        for dest, keywords in self.DESTINATION_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                result["destination"] = dest
                break

        # 3. 解析用户类型
        for user_type, keywords in self.USER_TYPE_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                result["user_type"] = user_type
                break

        # 4. 解析意图
        if any(kw in query for kw in ["出发", "什么时候", "几点", "最佳时间", "推荐", "建议", "怎么走", "计划"]):
            result["intent"] = "plan"
        elif any(kw in query for kw in ["施工", "修路", "封路", "绕行"]):
            result["intent"] = "construction"
        elif any(kw in query for kw in ["预测", "拥堵", "交通", "路况", "堵车"]):
            result["intent"] = "forecast"
        elif any(kw in query for kw in ["对比", "比较", "哪个好", "vs"]):
            result["intent"] = "compare"
        elif any(kw in query for kw in ["活动", "音乐节", "啤酒节", "节日"]):
            result["intent"] = "events"

        return result

    def _parse_date(self, query: str) -> Optional[str]:
        """解析日期"""
        today = datetime.now()

        # 检查相对日期
        for keyword, offset in self.DATE_KEYWORDS.items():
            if keyword in query:
                if isinstance(offset, int):
                    target = today + timedelta(days=offset)
                    return target.strftime("%Y-%m-%d")
                elif offset == "weekend":
                    # 找到这个周末
                    days_until_saturday = (5 - today.weekday()) % 7
                    if days_until_saturday == 0 and today.weekday() == 5:
                        days_until_saturday = 0
                    target = today + timedelta(days=days_until_saturday)
                    return target.strftime("%Y-%m-%d")
                elif offset == "next_weekend":
                    days_until_saturday = (5 - today.weekday()) % 7 + 7
                    target = today + timedelta(days=days_until_saturday)
                    return target.strftime("%Y-%m-%d")

        # 检查具体日期格式
        # 7月25日, 7-25, 2026-07-25
        patterns = [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",  # 2026-07-25
            r"(\d{1,2})月(\d{1,2})[日号]?",   # 7月25日
            r"(\d{1,2})[/-](\d{1,2})",        # 7-25 or 7/25
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups
                elif len(groups) == 2:
                    year = str(today.year)
                    month, day = groups
                else:
                    continue

                try:
                    date = datetime(int(year), int(month), int(day))
                    return date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        return None


# ============ 对话式助手 ============

class ChatAssistant:
    """
    对话式出行助手

    支持：
    1. 自然语言问答
    2. 上下文记忆
    3. 多轮对话
    4. 个性化推荐
    """

    def __init__(self, llm_provider: str = "rule"):
        """
        初始化

        Args:
            llm_provider: "openai" | "anthropic" | "rule" (无 LLM，纯规则)
        """
        self.travel_assistant = TravelAssistant()
        self.intent_parser = IntentParser()
        self.state = ConversationState()
        self.llm_provider = llm_provider

        # 初始化 LLM 客户端
        self.llm_client = None
        if llm_provider == "openai" and HAS_OPENAI:
            self.llm_client = OpenAI()
        elif llm_provider == "anthropic" and HAS_ANTHROPIC:
            self.llm_client = anthropic.Anthropic()

    def chat(self, user_message: str) -> str:
        """
        处理用户消息

        Args:
            user_message: 用户输入

        Returns:
            助手回复
        """
        # 1. 解析意图
        parsed = self.intent_parser.parse(user_message, self.state)

        # 2. 更新状态
        if parsed["date"]:
            self.state.preferred_date = parsed["date"]
        if parsed["destination"]:
            self.state.destination = parsed["destination"]
        if parsed["user_type"]:
            self.state.user_type = parsed["user_type"]

        # 3. 记录历史
        self.state.history.append({"role": "user", "content": user_message})

        # 4. 根据意图处理
        intent = parsed["intent"]

        if intent == "plan":
            response = self._handle_plan(parsed)
        elif intent == "forecast":
            response = self._handle_forecast(parsed)
        elif intent == "construction":
            response = self._handle_construction(parsed)
        elif intent == "events":
            response = self._handle_events(parsed)
        elif intent == "compare":
            response = self._handle_compare(parsed)
        else:
            response = self._handle_chat(user_message, parsed)

        # 5. 记录回复
        self.state.history.append({"role": "assistant", "content": response})

        return response

    def _handle_plan(self, parsed: Dict) -> str:
        """处理出行计划请求"""
        date = parsed["date"] or datetime.now().strftime("%Y-%m-%d")
        destination = parsed["destination"] or "salzburg"
        user_type = parsed["user_type"]

        # 确定路线
        route_id = f"munich_{destination}_a8" if destination == "salzburg" else f"munich_{destination}_a93"
        if route_id not in ROUTES:
            route_id = "munich_salzburg_a8"

        try:
            plan = self.travel_assistant.generate_plan(route_id, date, user_type)
            return plan.personalized_advice
        except Exception as e:
            return f"抱歉，生成计划时出错: {str(e)}"

    def _handle_forecast(self, parsed: Dict) -> str:
        """处理交通预测请求"""
        date = parsed["date"] or datetime.now().strftime("%Y-%m-%d")
        road = "A8"  # 默认 A8

        forecast = self.travel_assistant.get_traffic_forecast(date, road)

        # 生成回复
        lines = [
            f"## 📊 {date} {road} 高速交通预测",
            "",
            f"**最佳时段**: {forecast['best_hour']}:00 (拥堵最低)",
            f"**避开时段**: {forecast['worst_hour']}:00 (拥堵最高)",
            f"**全天平均拥堵指数**: {forecast['avg_congestion']}/100",
            "",
            "### 各时段预测",
            "| 时间 | 拥堵指数 | 等级 |",
            "|------|----------|------|",
        ]

        for p in forecast["predictions"][::2]:  # 每隔2小时显示
            emoji = {"smooth": "🟢", "light": "🟡", "moderate": "🟠", "heavy": "🔴", "critical": "⛔"}.get(p["congestion_level"], "⚪")
            lines.append(f"| {p['hour']:02d}:00 | {p['congestion_score']:.0f} | {emoji} {p['congestion_level']} |")

        return "\n".join(lines)

    def _handle_construction(self, parsed: Dict) -> str:
        """处理施工查询"""
        date = parsed["date"] or datetime.now().strftime("%Y-%m-%d")
        road = "A8"

        factors = self.travel_assistant.search_external_factors(date, road)
        constructions = [f for f in factors if f["type"] == "construction"]

        if not constructions:
            return f"✅ {date} {road} 高速暂无施工信息。"

        lines = [f"## 🚧 {date} {road} 高速施工信息", ""]
        for c in constructions:
            lines.append(f"### {c['title']}")
            lines.append(f"- **位置**: {c.get('location', '未知')}")
            lines.append(f"- **影响**: {c.get('description', '')}")
            if c.get("detour"):
                lines.append(f"- **绕行**: {c['detour']}")
            lines.append("")

        return "\n".join(lines)

    def _handle_events(self, parsed: Dict) -> str:
        """处理活动查询"""
        date = parsed["date"] or datetime.now().strftime("%Y-%m-%d")
        road = "A8"

        factors = self.travel_assistant.search_external_factors(date, road)
        events = [f for f in factors if f["type"] == "event"]
        holidays = [f for f in factors if f["type"] in ["holiday", "school_holiday"]]

        lines = [f"## 🎭 {date} 活动/假期信息", ""]

        if events:
            for e in events:
                lines.append(f"### {e['title']}")
                lines.append(f"{e.get('description', '')}")
                if e.get("recommendation"):
                    lines.append(f"- **交通影响**: {e['recommendation']}")
                lines.append("")

        if holidays:
            for h in holidays:
                lines.append(f"### 📅 {h['title']}")
                lines.append(f"{h.get('description', '')}")
                lines.append("")

        if not events and not holidays:
            lines.append("当天暂无重大活动或假期。")

        return "\n".join(lines)

    def _handle_compare(self, parsed: Dict) -> str:
        """处理方案对比"""
        date = parsed["date"] or datetime.now().strftime("%Y-%m-%d")
        destination = parsed["destination"] or "salzburg"
        user_type = parsed["user_type"]

        route_id = f"munich_{destination}_a8" if destination == "salzburg" else f"munich_{destination}_a93"
        if route_id not in ROUTES:
            route_id = "munich_salzburg_a8"

        options = self.travel_assistant.calculate_travel_options(route_id, date)

        lines = [
            f"## 📋 {date} 出行方案对比",
            "",
            "| 出发 | 到达 | 时长 | 延误 | 压力指数 | 推荐 |",
            "|------|------|------|------|----------|------|",
        ]

        for opt in options:
            stress_bar = "🟢" * (10 - opt.stress_index) + "🔴" * opt.stress_index
            lines.append(f"| {opt.departure_time} | {opt.arrival_time} | {opt.travel_time_min}分钟 | +{opt.delay_min}分钟 | {opt.stress_index}/10 | {opt.recommendation[:10]} |")

        lines.append("")
        best = min(options, key=lambda x: x.stress_index)
        lines.append(f"**推荐**: {best.departure_time} 出发，预计 {best.arrival_time} 到达")

        return "\n".join(lines)

    def _handle_chat(self, message: str, parsed: Dict) -> str:
        """处理一般聊天"""
        # 如果有 LLM，使用 LLM 回复
        if self.llm_client and self.llm_provider == "openai":
            return self._llm_chat_openai(message)
        elif self.llm_client and self.llm_provider == "anthropic":
            return self._llm_chat_anthropic(message)

        # 规则回复
        greetings = ["你好", "hi", "hello", "嗨", "您好"]
        if any(g in message.lower() for g in greetings):
            return self._get_greeting()

        # 默认引导
        return self._get_help_message()

    def _get_greeting(self) -> str:
        return """## 👋 你好！我是 AlpineFlow 出行助手

我可以帮你：
- 🚗 规划从慕尼黑出发的最佳出行时间
- 📊 查询高速公路交通预测
- 🚧 查询施工和绕行信息
- 🎭 查询活动和假期对交通的影响

**试试问我**：
- "这周六去萨尔茨堡，什么时候出发最好？"
- "A8 高速明天有施工吗？"
- "啤酒节期间交通怎么样？"
"""

    def _get_help_message(self) -> str:
        return """我不太确定你想问什么，你可以试试：

- **出行计划**: "周六去萨尔茨堡，几点出发好？"
- **交通预测**: "明天 A8 高速拥堵吗？"
- **施工信息**: "A8 有施工吗？"
- **活动影响**: "萨尔茨堡音乐节什么时候？"

或者告诉我你的**目的地**和**出行日期**，我来帮你规划！
"""

    def _llm_chat_openai(self, message: str) -> str:
        """使用 OpenAI 进行对话"""
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    *self.state.history[-10:],  # 最近10轮对话
                    {"role": "user", "content": message}
                ],
                tools=[{"type": "function", "function": t} for t in TOOLS_SCHEMA],
                tool_choice="auto",
            )

            # 处理工具调用
            if response.choices[0].message.tool_calls:
                return self._handle_tool_calls(response.choices[0].message.tool_calls)

            return response.choices[0].message.content

        except Exception as e:
            return f"LLM 调用出错: {str(e)}"

    def _llm_chat_anthropic(self, message: str) -> str:
        """使用 Anthropic Claude 进行对话"""
        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self._get_system_prompt(),
                messages=[
                    *self.state.history[-10:],
                    {"role": "user", "content": message}
                ],
                tools=[{
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters"]
                } for t in TOOLS_SCHEMA],
            )

            # 处理工具调用
            for block in response.content:
                if block.type == "tool_use":
                    return self._handle_tool_call(block.name, block.input)
                elif block.type == "text":
                    return block.text

            return "抱歉，我没有理解你的问题。"

        except Exception as e:
            return f"LLM 调用出错: {str(e)}"

    def _get_system_prompt(self) -> str:
        return """你是 AlpineFlow 出行助手，专门帮助用户规划德国高速公路 (A8/A93) 的出行。

你的能力：
1. 查询交通预测数据
2. 搜索施工、活动、假期信息
3. 计算最佳出发时间
4. 根据用户类型（游客/居民/物流/旅游业/交通管理）提供个性化建议

回复要求：
- 使用中文
- 简洁友好
- 提供具体的时间和数据
- 使用 Markdown 格式

当前用户类型: {user_type}
""".format(user_type=self.state.user_type.value)

    def _handle_tool_calls(self, tool_calls) -> str:
        """处理 OpenAI 工具调用"""
        results = []
        for tc in tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = self._handle_tool_call(name, args)
            results.append(result)
        return "\n\n".join(results)

    def _handle_tool_call(self, name: str, args: Dict) -> str:
        """执行单个工具调用"""
        if name == "get_traffic_forecast":
            forecast = self.travel_assistant.get_traffic_forecast(**args)
            return f"预测数据: 最佳时段 {forecast['best_hour']}:00，平均拥堵 {forecast['avg_congestion']}"

        elif name == "search_external_factors":
            factors = self.travel_assistant.search_external_factors(**args)
            return f"找到 {len(factors)} 个外部因素: {[f['title'] for f in factors]}"

        elif name == "calculate_travel_options":
            options = self.travel_assistant.calculate_travel_options(**args)
            best = min(options, key=lambda x: x.stress_index)
            return f"推荐 {best.departure_time} 出发，预计 {best.arrival_time} 到达"

        elif name == "generate_plan":
            user_type = UserType(args.get("user_type", "traveler"))
            plan = self.travel_assistant.generate_plan(
                args["route_id"], args["date"], user_type
            )
            return plan.personalized_advice

        return "未知工具"

    def reset(self):
        """重置对话状态"""
        self.state = ConversationState()

    def set_user_type(self, user_type: str):
        """设置用户类型"""
        self.state.user_type = UserType(user_type.lower())


# ============ 命令行界面 ============

def run_cli():
    """运行命令行对话界面"""
    print("=" * 60)
    print("🚗 AlpineFlow 出行助手")
    print("=" * 60)
    print("输入 'quit' 退出, 'reset' 重置对话")
    print("=" * 60)

    # 检测可用的 LLM
    if HAS_OPENAI and os.getenv("OPENAI_API_KEY"):
        provider = "openai"
        print("✅ 使用 OpenAI GPT")
    elif HAS_ANTHROPIC and os.getenv("ANTHROPIC_API_KEY"):
        provider = "anthropic"
        print("✅ 使用 Anthropic Claude")
    else:
        provider = "rule"
        print("ℹ️ 使用规则引擎 (无 LLM)")

    assistant = ChatAssistant(llm_provider=provider)
    print(assistant.chat("你好"))

    while True:
        try:
            user_input = input("\n👤 你: ").strip()

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("再见！")
                break
            if user_input.lower() == "reset":
                assistant.reset()
                print("对话已重置。")
                continue

            response = assistant.chat(user_input)
            print(f"\n🤖 助手:\n{response}")

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    run_cli()
