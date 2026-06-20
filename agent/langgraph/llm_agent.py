"""
LLM-powered Agent using LangGraph
使用LLM进行意图理解和响应生成的Agent
"""
from typing import Any, Dict, List, Literal, Optional
import os

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .state import AgentState
from .tools import TRAFFIC_TOOLS

# 尝试导入LLM
try:
    from langchain_openai import ChatOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from langchain_anthropic import ChatAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# 系统提示词
SYSTEM_PROMPT = """You are AlpineFlow AI, an intelligent traffic assistant for the Autobahn (German highways), specifically A8 and A93 routes between Munich and Austria.

Your capabilities:
1. **Traffic Forecast**: Predict hourly traffic volumes and congestion levels
2. **Trip Planning**: Recommend best departure times based on traffic patterns
3. **Event Awareness**: Know about festivals, holidays, and their traffic impact
4. **What-if Analysis**: Simulate scenarios like bad weather or accidents
5. **Explanation**: Explain why traffic is expected to be heavy or light

User Types you serve:
- Tourist: Focus on best travel experience and timing
- Resident: Focus on avoiding local congestion
- Logistics: Focus on delivery efficiency and punctuality
- Tourism Business: Focus on customer arrival patterns
- Authority: Focus on traffic management

Current context:
- Date: {date}
- Road: {road}
- User Type: {user_type}

Always provide actionable advice with specific times and clear reasoning.
When uncertain, say so and provide a confidence level.
"""


def create_llm_agent(
    provider: str = "openai",
    model: str = None,
    api_key: str = None
):
    """
    创建LLM驱动的Agent

    Args:
        provider: LLM提供商 (openai, anthropic)
        model: 模型名称
        api_key: API密钥

    Returns:
        编译后的LangGraph应用
    """
    # 选择LLM
    if provider == "openai":
        if not HAS_OPENAI:
            raise ImportError("请安装 langchain-openai: pip install langchain-openai")
        llm = ChatOpenAI(
            model=model or "gpt-4o",
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            temperature=0.7,
        )
    elif provider == "anthropic":
        if not HAS_ANTHROPIC:
            raise ImportError("请安装 langchain-anthropic: pip install langchain-anthropic")
        llm = ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.7,
        )
    else:
        raise ValueError(f"不支持的提供商: {provider}")

    # 绑定工具
    llm_with_tools = llm.bind_tools(TRAFFIC_TOOLS)

    # 定义状态
    from typing import Annotated, TypedDict
    from langgraph.graph.message import add_messages

    class LLMAgentState(TypedDict):
        messages: Annotated[list, add_messages]
        date: str
        road: str
        user_type: str

    # 定义节点
    def agent_node(state: LLMAgentState) -> Dict[str, Any]:
        """Agent节点：调用LLM"""
        system_message = SystemMessage(content=SYSTEM_PROMPT.format(
            date=state.get("date", "today"),
            road=state.get("road", "A8"),
            user_type=state.get("user_type", "tourist"),
        ))

        messages = [system_message] + state["messages"]
        response = llm_with_tools.invoke(messages)

        return {"messages": [response]}

    # 工具节点
    tool_node = ToolNode(TRAFFIC_TOOLS)

    # 路由函数
    def should_continue(state: LLMAgentState) -> Literal["tools", "__end__"]:
        """判断是否需要调用工具"""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "__end__"

    # 构建图
    workflow = StateGraph(LLMAgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    # 编译
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


class LLMTrafficAgent:
    """
    LLM交通Agent封装类
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = None,
        api_key: str = None
    ):
        self.app = create_llm_agent(provider, model, api_key)

    def chat(
        self,
        message: str,
        date: str = None,
        road: str = "A8",
        user_type: str = "tourist",
        thread_id: str = "default"
    ) -> str:
        """
        对话接口

        Args:
            message: 用户消息
            date: 日期上下文
            road: 道路上下文
            user_type: 用户类型
            thread_id: 会话ID

        Returns:
            AI响应文本
        """
        from datetime import datetime

        state = {
            "messages": [HumanMessage(content=message)],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "road": road,
            "user_type": user_type,
        }

        config = {"configurable": {"thread_id": thread_id}}

        result = self.app.invoke(state, config)

        # 提取最后的AI消息
        last_message = result["messages"][-1]
        return last_message.content

    async def achat(
        self,
        message: str,
        date: str = None,
        road: str = "A8",
        user_type: str = "tourist",
        thread_id: str = "default"
    ) -> str:
        """异步对话接口"""
        from datetime import datetime

        state = {
            "messages": [HumanMessage(content=message)],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "road": road,
            "user_type": user_type,
        }

        config = {"configurable": {"thread_id": thread_id}}

        result = await self.app.ainvoke(state, config)

        last_message = result["messages"][-1]
        return last_message.content

    def stream_chat(
        self,
        message: str,
        date: str = None,
        road: str = "A8",
        user_type: str = "tourist",
        thread_id: str = "default"
    ):
        """流式对话接口"""
        from datetime import datetime

        state = {
            "messages": [HumanMessage(content=message)],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "road": road,
            "user_type": user_type,
        }

        config = {"configurable": {"thread_id": thread_id}}

        for event in self.app.stream(state, config, stream_mode="values"):
            yield event


# ============ 快速使用函数 ============

def chat_with_traffic_ai(
    message: str,
    provider: str = "openai",
    **kwargs
) -> str:
    """
    快速对话函数

    Example:
        >>> response = chat_with_traffic_ai("What's the traffic like on A8 tomorrow?")
        >>> print(response)
    """
    agent = LLMTrafficAgent(provider=provider)
    return agent.chat(message, **kwargs)
