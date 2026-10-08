"""v0.8 investigation endpoints (GET /api/functions, POST /api/investigate, GET /api/investigate/{id}).
Kept out of api/main.py so the investigation and the plans/feedback work can change in parallel."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
