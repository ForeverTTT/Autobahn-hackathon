"""
LLM 客户端工具
支持 OpenAI 和 Anthropic 的异步文本/JSON 生成。
"""
import json
import os
from typing import Any, Dict, Optional


class LLMClient:
    """
    LLM 客户端

    支持:
    - OpenAI (gpt-4o, gpt-4o-mini)
    - Anthropic (claude-3-5-sonnet)

    配置:
        设置环境变量 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
        设置 LLM_PROVIDER 选择提供商 (openai/anthropic)
    """

    def __init__(
        self,
        provider: str = None,
        model: str = None,
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai")

        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self._init_openai()
        elif self.provider == "anthropic":
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            self._init_anthropic()
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _init_openai(self):
        """初始化 OpenAI 客户端。"""
        try:
            from openai import AsyncOpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self.client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def _init_anthropic(self):
        """初始化 Anthropic 客户端。"""
        try:
            from anthropic import AsyncAnthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """生成文本。"""
        if self.provider == "openai":
            return await self._generate_openai(prompt, system, temperature, max_tokens)
        return await self._generate_anthropic(prompt, system, temperature, max_tokens)

    async def _generate_openai(
        self,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenAI 生成。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def _generate_anthropic(
        self,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Anthropic 生成。"""
        response = await self.client.messages.create(
            model=self.model,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text

    async def generate_json(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """生成 JSON，并自动解析返回值。"""
        json_prompt = f"{prompt}\n\nReturn ONLY valid JSON, no other text."
        response = await self.generate(json_prompt, system, temperature)

        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        return json.loads(response)


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例。"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def generate(prompt: str, system: str = None) -> str:
    """快捷生成函数。"""
    client = get_llm_client()
    return await client.generate(prompt, system)


async def generate_json(prompt: str, system: str = None) -> Dict[str, Any]:
    """快捷 JSON 生成函数。"""
    client = get_llm_client()
    return await client.generate_json(prompt, system)
