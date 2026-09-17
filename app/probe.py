"""Discover which chat and embedding deployments the GW Azure resource exposes.
Sends one tiny request per candidate. Prints names only; never prints the key.
  python -m app.probe
"""
from __future__ import annotations

from app import config

CHAT_CANDIDATES = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-4.1-nano", "gpt-5-mini", "gpt-5",
                   "gpt-5-nano", "o4-mini", "gpt-35-turbo", "gpt-4"]
EMBED_CANDIDATES = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]


def main():
    if not config.has_key():
        print("No key found in .env"); return
    from openai import AzureOpenAI, OpenAI
    if config.is_azure():
        c = AzureOpenAI(api_key=config.api_key(), azure_endpoint=config.azure_endpoint(), api_version=config.API_VERSION, timeout=30, max_retries=0)
    else:
        c = OpenAI(api_key=config.api_key(), base_url=config.azure_endpoint(), timeout=30, max_retries=0)
    print(f"endpoint: {config.azure_endpoint()}  api_version: {config.API_VERSION}")
    ok_chat, ok_embed = [], []
    for m in CHAT_CANDIDATES:
        try:
            kwargs = {"model": m, "messages": [{"role": "user", "content": "Reply with the single word OK."}]}
            r = c.chat.completions.create(**kwargs, max_completion_tokens=60, **({"reasoning_effort": "minimal"} if m.startswith("gpt-5") else {}))
            print(f"  chat  {m:24s} OK   -> {r.choices[0].message.content!r}")
            ok_chat.append(m)
        except Exception as e:
            msg = str(e).splitlines()[0][:110]
            print(f"  chat  {m:24s} no   ({type(e).__name__}: {msg})")
    for m in EMBED_CANDIDATES:
        try:
            r = c.embeddings.create(model=m, input=["ok"])
            print(f"  embed {m:24s} OK   (dim {len(r.data[0].embedding)})")
            ok_embed.append(m)
        except Exception as e:
            msg = str(e).splitlines()[0][:110]
            print(f"  embed {m:24s} no   ({type(e).__name__}: {msg})")
    print("\nWorking chat deployments:", ok_chat or "none")
    print("Working embedding deployments:", ok_embed or "none")
    if ok_chat:
        print(f"\nSet in .env:  OPENAI_MODEL={ok_chat[0]}")
    if ok_embed:
        print(f"Set in .env:  OPENAI_EMBED_MODEL={ok_embed[0]}")


if __name__ == "__main__":
    main()
