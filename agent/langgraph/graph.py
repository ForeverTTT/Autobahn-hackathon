"""
LangGraph Traffic Agent Graph
定义完整的Agent工作流图
"""
from typing import Any, Dict, Literal
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState, create_initial_state
from .nodes import (
    parse_intent_node,
    forecast_node,
    explain_node,
    retrieve_node,
    simulate_node,
    generate_response_node,
    route_node,
)


def create_traffic_graph() -> StateGraph:
    """
    创建交通Agent工作流图

    图结构:

    START
      │
      ▼
    ┌─────────────┐
    │ parse_intent│  解析用户意图
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │    route    │  路由决策
    └─────────────┘
           │
      ┌────┴────┐
      ▼         ▼
    parallel   forecast_first
      │             │
      ▼             ▼
    ┌───┬───┬───┐ ┌────────┐
    │ F │ E │ R │ │forecast│
    └───┴───┴───┘ └────────┘
      │                │
      │                ▼
      │          ┌──────────┐
      │          │ simulate │
      │          └──────────┘
      │                │
      └───────┬────────┘
              ▼
       ┌─────────────┐
       │  generate   │  生成响应
       └─────────────┘
              │
              ▼
            END
    """

    # 创建状态图
    workflow = StateGraph(AgentState)

    # ============ 添加节点 ============

    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("route", route_node)
    workflow.add_node("forecast", forecast_node)
    workflow.add_node("explain", explain_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("simulate", simulate_node)
    workflow.add_node("generate_response", generate_response_node)

    # 并行执行节点（forecast + explain + retrieve）
    def parallel_agents_node(state: AgentState) -> Dict[str, Any]:
        """并行执行多个Agent"""
        # 在同步环境中顺序执行（LangGraph会自动处理）
        forecast_result = forecast_node(state)
        explain_result = explain_node(state)
        retrieve_result = retrieve_node(state)

        return {
            "forecast_result": forecast_result.get("forecast_result"),
            "explanation_result": explain_result.get("explanation_result"),
            "retrieval_result": retrieve_result.get("retrieval_result"),
            "messages": [{"role": "system", "content": "Parallel agents completed"}],
        }

    workflow.add_node("parallel_agents", parallel_agents_node)

    # forecast优先节点（用于what-if场景）
    def forecast_first_node(state: AgentState) -> Dict[str, Any]:
        """先执行预测，再执行模拟"""
        forecast_result = forecast_node(state)

        # 更新state以便simulate使用
        new_state = {**state, "forecast_result": forecast_result.get("forecast_result")}
        simulate_result = simulate_node(new_state)

        return {
            "forecast_result": forecast_result.get("forecast_result"),
            "simulation_result": simulate_result.get("simulation_result"),
            "messages": [{"role": "system", "content": "Forecast-first flow completed"}],
        }

    workflow.add_node("forecast_first", forecast_first_node)

    # ============ 添加边 ============

    # 入口点
    workflow.set_entry_point("parse_intent")

    # parse_intent -> route
    workflow.add_edge("parse_intent", "route")

    # route -> 条件分支
    def route_decision(state: AgentState) -> Literal["parallel_agents", "forecast_first"]:
        """路由决策函数"""
        return state.get("next_step", "parallel_agents")

    workflow.add_conditional_edges(
        "route",
        route_decision,
        {
            "parallel_agents": "parallel_agents",
            "forecast_first": "forecast_first",
        }
    )

    # parallel_agents -> generate_response
    workflow.add_edge("parallel_agents", "generate_response")

    # forecast_first -> generate_response
    workflow.add_edge("forecast_first", "generate_response")

    # generate_response -> END
    workflow.add_edge("generate_response", END)

    return workflow


class TrafficAgentGraph:
    """
    交通Agent图的封装类
    提供简洁的API
    """

    def __init__(self, enable_memory: bool = True):
        """
        初始化

        Args:
            enable_memory: 是否启用对话记忆
        """
        self.workflow = create_traffic_graph()

        if enable_memory:
            self.memory = MemorySaver()
            self.app = self.workflow.compile(checkpointer=self.memory)
        else:
            self.app = self.workflow.compile()

    def invoke(
        self,
        query: str,
        user_type: str = "tourist",
        date: str = None,
        road: str = "A8",
        scenario: Dict[str, Any] = None,
        thread_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        同步调用

        Args:
            query: 用户查询
            user_type: 用户类型
            date: 目标日期
            road: 高速公路
            scenario: What-if场景
            thread_id: 会话ID（用于记忆）

        Returns:
            最终响应
        """
        initial_state = create_initial_state(
            query=query,
            user_type=user_type,
            date=date,
            road=road,
            scenario=scenario,
            **kwargs
        )

        config = {"configurable": {"thread_id": thread_id}}

        result = self.app.invoke(initial_state, config)

        return result.get("final_response", result)

    async def ainvoke(
        self,
        query: str,
        user_type: str = "tourist",
        date: str = None,
        road: str = "A8",
        scenario: Dict[str, Any] = None,
        thread_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        异步调用
        """
        initial_state = create_initial_state(
            query=query,
            user_type=user_type,
            date=date,
            road=road,
            scenario=scenario,
            **kwargs
        )

        config = {"configurable": {"thread_id": thread_id}}

        result = await self.app.ainvoke(initial_state, config)

        return result.get("final_response", result)

    def stream(
        self,
        query: str,
        user_type: str = "tourist",
        date: str = None,
        road: str = "A8",
        thread_id: str = "default",
        **kwargs
    ):
        """
        流式输出

        Yields:
            每个节点的输出
        """
        initial_state = create_initial_state(
            query=query,
            user_type=user_type,
            date=date,
            road=road,
            **kwargs
        )

        config = {"configurable": {"thread_id": thread_id}}

        for event in self.app.stream(initial_state, config):
            yield event

    def get_graph_image(self) -> bytes:
        """
        生成图的可视化图像

        Returns:
            PNG图像字节
        """
        try:
            return self.app.get_graph().draw_mermaid_png()
        except Exception:
            return None

    def get_graph_mermaid(self) -> str:
        """
        获取Mermaid格式的图定义

        Returns:
            Mermaid字符串
        """
        return self.app.get_graph().draw_mermaid()


# ============ 便捷函数 ============

def create_agent() -> TrafficAgentGraph:
    """创建Agent实例"""
    return TrafficAgentGraph()


def quick_forecast(date: str, road: str = "A8") -> Dict[str, Any]:
    """快速获取预测"""
    agent = TrafficAgentGraph(enable_memory=False)
    return agent.invoke(
        query=f"What's the traffic on {road}?",
        date=date,
        road=road,
    )


def quick_plan(date: str, user_type: str = "tourist") -> Dict[str, Any]:
    """快速获取出行计划"""
    agent = TrafficAgentGraph(enable_memory=False)
    return agent.invoke(
        query="Plan my trip",
        date=date,
        user_type=user_type,
    )
