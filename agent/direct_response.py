"""Direct replies for messages that should not trigger the traffic agent chain."""

from typing import Optional

from .agents.prompt import CONFIRM_RESPONSE, DIRECT_GREETING_RESPONSE


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
    "Hallo, wie geht's"
}

_CONFIRMATIONS = {
    "ok",
    "okay",
    "thanks",
    "thank you",
    "好的",
    "可以",
    "好",
    "谢谢",
}


def get_direct_response(query: str) -> Optional[str]:
    """Return a direct chat response for simple non-traffic messages."""
    text = (query or "").strip().lower()
    normalized = text.rstrip("!！。,.， ")

    if normalized in _GREETINGS:
        return DIRECT_GREETING_RESPONSE
    if normalized in _CONFIRMATIONS:
        return CONFIRM_RESPONSE

    return None
