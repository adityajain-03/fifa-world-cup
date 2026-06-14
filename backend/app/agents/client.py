"""Thin Anthropic wrapper used by the Scout and Analyst agents.

Centralises model choice, prompt caching, structured-output parsing, and
graceful degradation when no API key is configured.
"""
from __future__ import annotations

import logging
from typing import Optional, TypeVar

from pydantic import BaseModel

from ..config import settings

log = logging.getLogger("fifa.agents")

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    def __init__(self) -> None:
        self.available = settings.predictions_enabled
        self._client = None
        if self.available:
            try:
                import anthropic

                # Generous timeout + SDK retries: web_search calls are slow and,
                # run concurrently, can otherwise hit read timeouts and fall back
                # to priors (losing news grounding).
                self._client = anthropic.Anthropic(
                    api_key=settings.anthropic_api_key, timeout=300.0, max_retries=3,
                )
            except Exception:  # noqa: BLE001
                log.exception("Failed to initialise Anthropic client; disabling predictions")
                self.available = False

    def parse(
        self, system: str, user: str, schema: type[T], *, tools: list | None = None
    ) -> Optional[T]:
        """Single structured-output call returning a validated `schema` instance.

        Optional server-side `tools` (e.g. web_search) run within the call before
        the final structured answer is produced.
        """
        if not self.available or self._client is None:
            return None
        kwargs = dict(
            model=settings.claude_model,
            max_tokens=6000,
            thinking={"type": "adaptive"},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if tools:
            kwargs["tools"] = tools
        # The structured-output grammar is compiled+cached server-side on first use;
        # the first call can occasionally time out ("Grammar compilation timed out").
        # Retry a couple of times so later teams benefit from the warmed cache.
        import time as _time

        last_exc = None
        for attempt in range(3):
            try:
                resp = self._client.messages.parse(**kwargs)
                if resp.stop_reason == "refusal":
                    log.warning("Scout refused: %s", getattr(resp, "stop_details", None))
                    return None
                return resp.parsed_output
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc).lower()
                if "grammar" in msg or "timed out" in msg or "overloaded" in msg:
                    _time.sleep(2 + attempt * 3)
                    continue
                break
        log.warning("Structured Claude call failed: %s", last_exc)
        return None

    def complete(
        self, system: str, user: str, max_tokens: int = 1500, *,
        tools: list | None = None, thinking: dict | None = None,
    ) -> str:
        """Plain-text completion. Optional server-side `tools` (e.g. web_search) run
        within the call; we resume across `pause_turn` until a final answer.

        `thinking` defaults to adaptive; pass {"type": "disabled"} for fast,
        non-reasoning calls like summarising web-search results.
        """
        if not self.available or self._client is None:
            return ""
        messages = [{"role": "user", "content": user}]
        kwargs = dict(
            model=settings.claude_model,
            max_tokens=max_tokens,
            thinking=thinking or {"type": "adaptive"},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        )
        if tools:
            kwargs["tools"] = tools
        import time as _time

        # Outer retry so a transient timeout/overload on a web-search call doesn't
        # silently drop a team to its rank-prior (losing news grounding).
        for attempt in range(3):
            messages = [{"role": "user", "content": user}]
            try:
                for _ in range(4):  # bounded resume loop for server-tool pauses
                    resp = self._client.messages.create(messages=messages, **kwargs)
                    if resp.stop_reason == "refusal":
                        return ""
                    if resp.stop_reason == "pause_turn":
                        messages.append({"role": "assistant", "content": resp.content})
                        continue
                    return "".join(b.text for b in resp.content if b.type == "text").strip()
                return ""
            except Exception as exc:  # noqa: BLE001
                log.warning("Text call attempt %d failed: %s", attempt + 1, exc)
                _time.sleep(3 + attempt * 4)
        return ""
