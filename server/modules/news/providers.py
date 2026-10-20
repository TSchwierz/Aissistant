"""AI digest providers — Mistral → Claude → ChatGPT → Gemini with retry."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from server.config import Settings, get_settings

logger = logging.getLogger(__name__)

PROVIDER_ORDER = ("mistral", "claude", "chatgpt", "gemini")
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1.0


@dataclass
class SummarizeResult:
    text: str
    provider: str


@dataclass
class ProviderAttempt:
    provider: str
    ok: bool
    error: str | None = None


def configured_providers(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    available: list[str] = []
    if settings.mistral_api_key:
        available.append("mistral")
    if settings.anthropic_api_key:
        available.append("claude")
    if settings.openai_api_key:
        available.append("chatgpt")
    if settings.gemini_api_key:
        available.append("gemini")
    return [p for p in PROVIDER_ORDER if p in available]


def _build_prompt(*, label: str, goal: str, items_block: str) -> tuple[str, str]:
    system = (
        "You write concise English morning news digests for a personal assistant. "
        "Be factual, neutral, and brief. No markdown headings. "
        "Output 1–3 short paragraphs suitable for listening aloud."
    )
    user = (
        f"Topic: {label}\n"
        f"Goal: {goal or 'Summarize the most important developments.'}\n\n"
        f"Source headlines and snippets:\n{items_block}\n\n"
        "Write an English digest covering the material above."
    )
    return system, user


def _with_retries(provider: str, fn: Callable[[], str]) -> str:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            delay = BASE_BACKOFF_SECONDS * (2**attempt)
            logger.warning(
                "Provider %s attempt %s failed: %s; retry in %.1fs",
                provider,
                attempt + 1,
                exc,
                delay,
            )
            time.sleep(delay)
    assert last_err is not None
    raise last_err


def _mistral(system: str, user: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"]).strip()


def _claude(system: str, user: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-haiku-latest",
                "max_tokens": 800,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        parts = data.get("content") or []
        text = "".join(
            p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"
        )
        return text.strip()


def _chatgpt(system: str, user: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"]).strip()


def _gemini(system: str, user: str, api_key: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.3},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates") or []
        parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return text.strip()


def summarize_digest(
    *,
    label: str,
    goal: str,
    items_block: str,
    settings: Settings | None = None,
) -> tuple[SummarizeResult | None, list[ProviderAttempt]]:
    """Try providers in order. Returns (result_or_None, attempts)."""
    settings = settings or get_settings()
    system, user = _build_prompt(label=label, goal=goal, items_block=items_block)
    attempts: list[ProviderAttempt] = []
    providers = configured_providers(settings)
    if not providers:
        return None, []

    runners = {
        "mistral": lambda: _mistral(system, user, settings.mistral_api_key),
        "claude": lambda: _claude(system, user, settings.anthropic_api_key),
        "chatgpt": lambda: _chatgpt(system, user, settings.openai_api_key),
        "gemini": lambda: _gemini(system, user, settings.gemini_api_key),
    }

    for name in providers:
        try:
            text = _with_retries(name, runners[name])
            if not text:
                raise RuntimeError("empty response")
            attempts.append(ProviderAttempt(provider=name, ok=True))
            return SummarizeResult(text=text, provider=name), attempts
        except Exception as exc:  # noqa: BLE001
            attempts.append(ProviderAttempt(provider=name, ok=False, error=str(exc)))
            logger.exception("Provider %s exhausted retries", name)

    return None, attempts


def _retry_call(provider: str, fn: Callable[[], str]) -> str:
    """Same attempt count and backoff as digest summarization, without logging secrets."""
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            delay = BASE_BACKOFF_SECONDS * (2**attempt)
            logger.warning(
                "Provider %s attempt %s failed (%s); retry in %.1fs",
                provider,
                attempt + 1,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)
    assert last_err is not None
    raise last_err


def _completion_text(data: dict) -> str:
    choices = data.get("choices") or []
    message = (choices[0] or {}).get("message") if choices else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts).strip()
    return str(content or "").strip()


def complete_text(system: str, user: str, settings: Settings | None = None) -> str | None:
    """Run a text completion through the digest provider chain.

    Returns None when no provider is configured or every provider fails.
    Does not log API keys.
    """
    settings = settings or get_settings()
    providers = configured_providers(settings)
    if not providers:
        return None
    runners: dict[str, Callable[[], str]] = {
        "mistral": lambda: _mistral(system, user, settings.mistral_api_key),
        "claude": lambda: _claude(system, user, settings.anthropic_api_key),
        "chatgpt": lambda: _chatgpt(system, user, settings.openai_api_key),
        "gemini": lambda: _gemini(system, user, settings.gemini_api_key),
    }
    for name in providers:
        try:
            text = _retry_call(name, runners[name])
        except Exception:  # noqa: BLE001
            logger.error("Provider %s failed for text completion", name)
            continue
        if text and text.strip():
            return text.strip()
        logger.error("Provider %s returned an empty text completion", name)
    return None


_VISION_USER = "Follow the system instructions for this image."


def _mistral_vision(system: str, data_uri: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "pixtral-12b-latest",
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VISION_USER},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    },
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        return _completion_text(resp.json())


def _claude_vision(system: str, image_b64: str, media_type: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-haiku-latest",
                "max_tokens": 1024,
                "system": system,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": _VISION_USER},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
    parts = data.get("content") or []
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text"
    )
    return text.strip()


def _chatgpt_vision(system: str, data_uri: str, api_key: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VISION_USER},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    },
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        return _completion_text(resp.json())


def _gemini_vision(system: str, image_b64: str, media_type: str, api_key: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash:generateContent"
    )
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": _VISION_USER},
                            {"inline_data": {"mime_type": media_type, "data": image_b64}},
                        ],
                    }
                ],
                "generationConfig": {"temperature": 0.3},
            },
        )
        resp.raise_for_status()
        data = resp.json()
    candidates = data.get("candidates") or []
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    return text.strip()


def complete_vision(
    system: str,
    image: bytes,
    media_type: str,
    settings: Settings | None = None,
) -> str | None:
    """Run a vision completion through the same provider order as digests.

    Image bytes are sent only in the provider request. They are not logged or stored.
    Returns None when no provider is configured or every provider fails.
    """
    import base64

    settings = settings or get_settings()
    providers = configured_providers(settings)
    if not providers:
        return None
    media_type = (media_type or "image/jpeg").split(";", 1)[0].strip() or "image/jpeg"
    image_b64 = base64.standard_b64encode(image).decode("ascii")
    data_uri = f"data:{media_type};base64,{image_b64}"
    runners: dict[str, Callable[[], str]] = {
        "mistral": lambda: _mistral_vision(system, data_uri, settings.mistral_api_key),
        "claude": lambda: _claude_vision(system, image_b64, media_type, settings.anthropic_api_key),
        "chatgpt": lambda: _chatgpt_vision(system, data_uri, settings.openai_api_key),
        "gemini": lambda: _gemini_vision(system, image_b64, media_type, settings.gemini_api_key),
    }
    for name in providers:
        try:
            text = _retry_call(name, runners[name])
        except Exception:  # noqa: BLE001
            logger.error("Provider %s failed for vision completion", name)
            continue
        if text and text.strip():
            return text.strip()
        logger.error("Provider %s returned an empty vision completion", name)
    return None
