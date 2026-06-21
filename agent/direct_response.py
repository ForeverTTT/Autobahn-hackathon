"""Direct replies for messages that should not trigger the traffic agent chain."""

from typing import Optional


_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "你好",
    "您好",
    "嗨",
    "哈喽",
    "hello!",
    "hi!",
    "Hallo",
    "Hallo!",
    "Hallo, wie geht's?",
    "Hallo, wie geht's?
}


def get_direct_response(query: str) -> Optional[str]:
    """Return a direct chat response for simple non-traffic messages."""
    text = (query or "").strip().lower()
    normalized = text.rstrip("!！。,.， ")

    if normalized in _GREETINGS:
        return "你好！我是 AlpineFlow，可以帮你分析 A8/A93 出行时间、拥堵风险、施工和返程建议。你可以直接告诉我目的地和日期。"

    return None
