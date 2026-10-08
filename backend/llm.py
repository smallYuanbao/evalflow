import json

from openai import OpenAI

from backend.config import settings

_client = OpenAI(api_key=settings.chat_api_key, base_url=settings.chat_base_url)


def chat(messages: list[dict], temperature: float = 0.0) -> str:
    r = _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
    )
    return r.choices[0].message.content or ""


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict | None:
    """JSON mode 强制输出 JSON;解析失败返回 None(调用方按失败处理)。"""
    r = _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = r.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None
