"""Configuration: reads .env next to the prototype folder. Never prints the key.

The GW-provided resource is Azure OpenAI (endpoint https://gw-sb-04.openai.azure.com/).
The instructor's variable name is GW_AZURE_OPENAI_KEY; OPENAI_API_KEY is accepted as an alias.
Model names are Azure *deployment* names for that resource."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PLACEHOLDERS = {"", "paste-the-gw-key-here", "your-key", "xyz"}
GW_ENDPOINT_DEFAULT = "https://gw-sb-04.openai.azure.com/"


def api_key() -> str | None:
    for name in ("GW_AZURE_OPENAI_KEY", "OPENAI_API_KEY"):
        k = os.environ.get(name, "").strip().strip('"').strip("'")
        if k and k not in PLACEHOLDERS:
            return k
    return None


def has_key() -> bool:
    return api_key() is not None


def azure_endpoint() -> str:
    for name in ("AZURE_OPENAI_ENDPOINT", "OPENAI_BASE_URL"):
        b = os.environ.get(name, "").strip()
        if b:
            return b
    return GW_ENDPOINT_DEFAULT


def is_azure() -> bool:
    return "openai.azure.com" in azure_endpoint()


API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "").strip() or "2024-10-21"
MODEL = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-5-mini"            # Azure deployment name
EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "").strip() or "text-embedding-3-small"
MIN_N = 4
DATA_DIR = ROOT / "data" / "generated"
DOCS_DIR = ROOT / "data" / "docs"
CACHE_DIR = ROOT / "data" / "cache"
APPROVALS_PATH = ROOT / "approvals.jsonl"
