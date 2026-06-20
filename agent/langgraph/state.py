"""
LangGraph State Definition
定义Agent工作流的状态
"""
from typing import Any, Dict, List, Optional, Annotated, TypedDict, Literal
from datetime import datetime
import operator


class AgentState(TypedDict):
    """
    Agent工作流状态

    LangGraph 使用 TypedDict 定义状态，状态在节点之间传递和更新
    """
    # 用户输入
    query: str                          # 用户原始查询
    user_type: str                      # 用户类型: tourist, resident, logistics, etc.

    # 解析后的参数
    intent: str                         # 解析的意图: forecast, plan, whatif, explain, chat
    date: str                           # 目标日期 YYYY-MM-DD
    road: str                           # 高速公路: A8, A93
    site_id: str                        # 站点ID
    direction: str                      # 方向: east, west
    hours: List[int]                    # 预测小时列表
    scenario: Optional[Dict[str, Any]]  # What-if场景参数

    # Agent执行结果 (使用Annotated支持累加)
    forecast_result: Optional[Dict[str, Any]]      # 预测结果
    explanation_result: Optional[Dict[str, Any]]   # 解释结果
    retrieval_result: Optional[Dict[str, Any]]     # 检索结果
    simulation_result: Optional[Dict[str, Any]]    # 模拟结果

    # 消息历史 (支持累加)
    messages: Annotated[List[Dict[str, Any]], operator.add]

    # 最终输出
    final_response: Optional[Dict[str, Any]]

    # 控制流
    next_step: str                      # 下一步要执行的节点
    error: Optional[str]                # 错误信息


def create_initial_state(
    query: str,
    user_type: str = "tourist",
    date: str = None,
    road: str = "A8",
    **kwargs
) -> AgentState:
    """创建初始状态"""
    return AgentState(
        query=query,
        user_type=user_type,
        intent="",
        date=date or datetime.now().strftime("%Y-%m-%d"),
        road=road,
        site_id=kwargs.get("site_id", f"{road}_Rosenheim"),
        direction=kwargs.get("direction", "east"),
        hours=kwargs.get("hours", list(range(6, 22))),
        scenario=kwargs.get("scenario"),
        forecast_result=None,
        explanation_result=None,
        retrieval_result=None,
        simulation_result=None,
        messages=[],
        final_response=None,
        next_step="parse_intent",
        error=None,
    )
