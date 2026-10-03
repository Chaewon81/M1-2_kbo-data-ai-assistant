from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services.data_store import store
from backend.services.summary_service import build_summary


router = APIRouter(prefix="/api/data", tags=["summary"])


@router.get("/summary")
def get_summary(
    team: str | None = None,
    season: int | None = Query(default=None, ge=1900, le=2100),
    last_n: int | None = Query(default=None, ge=1, le=100),
) -> dict:
    items = store.list(team=team, season=season, limit=100000)
    return build_summary(items, team=team, season=season, last_n=last_n)
