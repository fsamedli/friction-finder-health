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


def _retry(call, retries: int = 1, backoff: float = 1.5):
    """Run call(); on a transient failure wait and try once more. Raises the last error."""
    import time
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as e:  # noqa: BLE001 - classified below
            status = getattr(e, "status_code", None)
            if attempt >= retries or (status is not None and 400 <= status < 500 and status != 429):
                raise
            time.sleep(backoff * (attempt + 1))


def choose_tool(system: str, user: str, tools: list[dict], effort: str = "low", strict: bool = True) -> dict[str, Any]:
    """The model picks the next tool from a fixed registry by function calling.

    `tools` = [{"name", "description", "parameters" (JSON schema)}]. Returns
    {"name": str, "args": dict, "selection": "function_calling", "attempts": int}. On a deployment that rejects
    function calling, falls back to a JSON object {"tool": name, "args": {...}} validated by the caller
    ("selection": "json_schema"). Raises LLMUnavailable when the model cannot be reached after one retry."""
    attempts = {"n": 0}
    specs = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["parameters"], **({"strict": True} if strict else {})}} for t in tools]

    def call():
        attempts["n"] += 1
        kwargs: dict[str, Any] = dict(model=config.MODEL, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                      tools=specs, tool_choice="required", max_completion_tokens=1200)
        if _reasoning_family(config.MODEL):
            kwargs["reasoning_effort"] = effort
        return client().chat.completions.create(**kwargs)

    try:
        resp = _retry(call)
        tc = (resp.choices[0].message.tool_calls or [None])[0]
        if tc is None:
            raise LLMUnavailable("the model returned no tool call")
        return {"name": tc.function.name, "args": json.loads(tc.function.arguments or "{}"), "selection": "function_calling", "attempts": attempts["n"]}
    except LLMUnavailable:
        raise
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 400:  # this deployment or API version does not take tools (or strict schemas): JSON next-tool schema
            names = [t["name"] for t in tools]
            sys2 = system + ("\n\nReturn ONLY a JSON object {\"tool\": one of " + json.dumps(names) +
                             ", \"args\": object matching that tool's parameters}. Tools:\n" +
                             "\n".join(f"- {t['name']}: {t['description']} parameters={json.dumps(t['parameters'])}" for t in tools))
            try:
                out = _retry(lambda: chat_json(sys2, user, effort=effort))
            except LLMUnavailable:
                raise
            attempts["n"] += 1
            return {"name": str(out.get("tool", "")), "args": out.get("args") or {}, "selection": "json_schema", "attempts": attempts["n"]}
        raise LLMUnavailable(f"{type(e).__name__}: {e}") from e
