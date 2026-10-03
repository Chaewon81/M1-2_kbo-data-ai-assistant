from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from backend.config import settings
from backend.models.schemas import PitcherStat

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PitcherQueryResult:
    items: list[PitcherStat]
    invalid_count: int = 0
    duplicate_count: int = 0


class PitcherService:
    @staticmethod
    def _read_rows():
        sources = settings.pitcher_data_paths or (settings.pitcher_data_path,)
        for source in sources:
            path = Path(source)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[2] / path
            if not path.exists():
                logger.warning("투수 CSV 파일 없음: %s", path)
                continue
            with path.open(encoding="utf-8-sig", newline="") as file:
                yield from csv.DictReader(file)

    def list(self, *, season: int | None = None, team: str | None = None, name: str | None = None, player_id: str | None = None) -> PitcherQueryResult:
        invalid_count = 0
        duplicate_count = 0
        items: list[PitcherStat] = []
        seen: set[tuple[int, str, str]] = set()
        for row in self._read_rows():
            try:
                item = PitcherStat.model_validate({
                    "season": int(row["season"]),
                    "team_code": row["team_code"],
                    "team": row["team"],
                    "player_id": row["player_id"],
                    "player": row["player"],
                    "games_appeared": int(row["games_appeared"]),
                    "innings": float(row["innings"]),
                    "earned_runs": int(row["earned_runs"]),
                    "era": float(row["era"]),
                    "whip": float(row["whip"]),
                    "strikeouts": int(row["strikeouts"]),
                    "source_url": row.get("source_url", ""),
                    "as_of": row.get("as_of", ""),
                    "updated_at": row.get("updated_at", ""),
                })
            except (KeyError, TypeError, ValueError) as error:
                invalid_count += 1
                logger.warning("투수 통계 CSV 행을 건너뜀: %s", error)
                continue
            try:
                if item.as_of:
                    date.fromisoformat(item.as_of)
                if item.updated_at:
                    datetime.fromisoformat(item.updated_at.replace("Z", "+00:00"))
            except ValueError:
                invalid_count += 1
                logger.warning("투수 통계 기준일 형식 오류: %s", item.as_of)
                continue
            key = (item.season, item.team_code, item.player_id)
            if key in seen:
                duplicate_count += 1
                logger.warning("투수 통계 중복 행: %s", key)
                continue
            seen.add(key)
            if season is not None and item.season != season:
                continue
            if team and team not in {item.team, item.team_code}:
                continue
            if name and name not in item.player:
                continue
            if player_id and item.player_id != player_id:
                continue
            items.append(item)
        return PitcherQueryResult(items=items, invalid_count=invalid_count, duplicate_count=duplicate_count)


pitcher_service = PitcherService()
