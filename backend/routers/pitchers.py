from fastapi import APIRouter, Query

from backend.models.schemas import PitcherListResponse
from backend.services.pitcher_service import pitcher_service


router = APIRouter(prefix="/api/pitchers", tags=["pitchers"])


@router.get("", response_model=PitcherListResponse)
def list_pitchers(
    season: int | None = Query(default=None, ge=1900, le=2100),
    team: str | None = None,
    name: str | None = None,
    player_id: str | None = None,
) -> PitcherListResponse:
    result = pitcher_service.list(season=season, team=team, name=name, player_id=player_id)
    return PitcherListResponse(count=len(result.items), items=result.items, invalid_count=result.invalid_count, duplicate_count=result.duplicate_count)
