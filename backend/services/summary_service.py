from __future__ import annotations

from collections.abc import Sequence

from backend.models.schemas import DataRecord


def build_summary(items: Sequence[DataRecord], *, team: str | None = None, season: int | None = None, last_n: int | None = None) -> dict:
    # 승률·득실차는 실제 완료 경기만 사용한다.
    filtered = [item for item in items if item.status == "completed" and item.result is not None and item.run_diff is not None]
    if team:
        filtered = [item for item in filtered if item.team == team]
    if season:
        filtered = [item for item in filtered if item.season == season]
    filtered.sort(key=lambda item: (item.date, item.game_id), reverse=True)

    selected = filtered[:last_n] if last_n else filtered
    if not selected:
        return {
            "period": None,
            "count": 0,
            "filters": {"team": team, "season": season, "last_n": last_n},
            "metrics": {},
            "trend": "데이터 없음",
        }

    wins = sum(item.result == "W" for item in selected)
    losses = sum(item.result == "L" for item in selected)
    draws = sum(item.result == "D" for item in selected)
    decisions = wins + losses
    run_diffs = [item.run_diff for item in selected]
    recent = selected[: min(5, len(selected))]
    previous = selected[min(5, len(selected)) : min(10, len(selected))]
    recent_rate = sum(item.result == "W" for item in recent) / max(1, sum(item.result in ("W", "L") for item in recent))
    previous_rate = sum(item.result == "W" for item in previous) / max(1, sum(item.result in ("W", "L") for item in previous)) if previous else recent_rate
    change = recent_rate - previous_rate
    trend = "상승" if change >= 0.1 else "하락" if change <= -0.1 else "유지"
    return {
        "period": {"from": str(min(item.date for item in selected)), "to": str(max(item.date for item in selected))},
        "count": len(selected),
        "filters": {"team": team, "season": season, "last_n": last_n},
        "metrics": {
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round(wins / decisions, 4) if decisions else None,
            "average_run_diff": round(sum(run_diffs) / len(run_diffs), 4),
            "max_run_diff": max(run_diffs),
            "min_run_diff": min(run_diffs),
        },
        "recent": {"window": len(recent), "win_rate": round(recent_rate, 4)},
        "trend": trend,
    }
