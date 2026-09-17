"""Thin wrapper around the OpenAI client (GW-provided key only). Every call has a timeout and
returns None on failure so callers can fall back. Nothing here does arithmetic."""
from __future__ import annotations

import json
from typing import Any

from app import config


class LLMUnavailable(Exception):
    pass


_client = None


def client():
    global _client
    if _client is None:
        if not config.has_key():
            raise LLMUnavailable("No API key in .env")
        if config.is_azure():
            from openai import AzureOpenAI
            _client = AzureOpenAI(api_key=config.api_key(), azure_endpoint=config.azure_endpoint(),
                                  api_version=config.API_VERSION, timeout=40.0, max_retries=1)
        else:
            from openai import OpenAI
            _client = OpenAI(api_key=config.api_key(), base_url=config.azure_endpoint(), timeout=40.0, max_retries=1)
    return _client


def _reasoning_family(model: str) -> bool:
    m = model.lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


def chat_json(system: str, user: str, temperature: float = 0.1, effort: str = "low") -> dict[str, Any]:
    """Ask for a JSON object. Raises LLMUnavailable on any failure.
    `effort` applies to reasoning models only: 'minimal' for extraction, 'low' for writing."""
    try:
        kwargs: dict[str, Any] = dict(
            model=config.MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )
        if _reasoning_family(config.MODEL):
            kwargs["reasoning_effort"] = effort   # gpt-5 family: no temperature; keep reasoning short for latency
        else:
            kwargs["temperature"] = temperature
        resp = client().chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)
    except LLMUnavailable:
        raise
    except Exception as e:  # network, auth, model, parse
        raise LLMUnavailable(f"{type(e).__name__}: {e}") from e


def embed(texts: list[str]) -> list[list[float]]:
    try:
        out = []
        for i in range(0, len(texts), 64):
            batch = texts[i:i + 64]
            resp = client().embeddings.create(model=config.EMBED_MODEL, input=batch)
            out.extend([d.embedding for d in resp.data])
        return out
    except LLMUnavailable:
        raise
    except Exception as e:
        raise LLMUnavailable(f"{type(e).__name__}: {e}") from e
