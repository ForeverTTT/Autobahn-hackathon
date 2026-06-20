"""
Agent 基类
定义所有 Agent 的统一接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models import AgentRequest, AgentResponse


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 必须实现:
    - name: Agent 名称
    - process(): 处理请求
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名称"""
        pass

    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        处理请求

        Args:
            request: Agent 请求

        Returns:
            AgentResponse
        """
        pass

    def _success(self, data: Dict[str, Any], message: str = "") -> AgentResponse:
        """创建成功响应"""
        return AgentResponse(success=True, data=data, message=message)

    def _error(self, message: str) -> AgentResponse:
        """创建错误响应"""
        return AgentResponse(success=False, data={}, message=message)
