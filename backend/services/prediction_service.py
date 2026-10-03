from __future__ import annotations

from datetime import datetime, timezone, timedelta

from backend.models.schemas import PredictionRequest, PredictionResponse
from backend.services.data_store import store
from backend.services.summary_service import build_summary
from backend.services.pitcher_service import pitcher_service


class PredictionService:
    @staticmethod
    def _find_pitcher(request_name: str | None, request_id: str | None, team: str, season: int | None):
        if not request_name and not request_id:
            return []
        if season is None:
            raise ValueError("투수 통계를 사용할 시즌을 선택해야 합니다.")
        result = pitcher_service.list(season=season, team=team, name=request_name, player_id=request_id)
        if request_name and request_id:
            by_id = pitcher_service.list(season=season, team=team, player_id=request_id).items
            if not by_id or by_id[0].player != request_name:
                raise ValueError("투수 이름과 player_id가 일치하지 않습니다.")
        if len(result.items) > 1:
            raise ValueError("투수 이름이 여러 기록과 일치합니다. player_id로 선택하세요.")
        return result.items

    @staticmethod
    def _pitcher_score(stat) -> float:
        # ERA·WHIP는 낮을수록, 이닝·탈삼진은 높을수록 좋은 방향으로 정규화한다.
        return (1 / max(stat.era, 0.01)) + (1 / max(stat.whip, 0.01)) + (stat.innings / 200) + (stat.strikeouts / 200)

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        if request.team_a == request.team_b:
            raise ValueError("서로 다른 두 팀을 선택해야 합니다.")
        items = store.list(limit=100000)
        summary_a = build_summary(items, team=request.team_a, season=request.season, last_n=request.last_n)
        summary_b = build_summary(items, team=request.team_b, season=request.season, last_n=request.last_n)
        rate_a = summary_a.get("metrics", {}).get("win_rate")
        rate_b = summary_b.get("metrics", {}).get("win_rate")
        if rate_a is None or rate_b is None:
            raise LookupError("두 팀 모두 분석할 완료 경기 데이터가 필요합니다.")
        total = rate_a + rate_b
        probability_a = rate_a / total if total else 0.5
        probability_b = rate_b / total if total else 0.5
        pitcher_a_stats = self._find_pitcher(request.pitcher_a, request.pitcher_a_id, request.team_a, request.season)
        pitcher_b_stats = self._find_pitcher(request.pitcher_b, request.pitcher_b_id, request.team_b, request.season)
        pitcher_applied = bool(pitcher_a_stats and pitcher_b_stats)
        method = "recent_form_win_rate_baseline"
        if pitcher_applied:
            pitcher_score_a = self._pitcher_score(pitcher_a_stats[0])
            pitcher_score_b = self._pitcher_score(pitcher_b_stats[0])
            pitcher_total = pitcher_score_a + pitcher_score_b
            pitcher_probability_a = pitcher_score_a / pitcher_total if pitcher_total else 0.5
            pitcher_probability_b = pitcher_score_b / pitcher_total if pitcher_total else 0.5
            probability_a = (probability_a * 0.8) + (pitcher_probability_a * 0.2)
            probability_b = (probability_b * 0.8) + (pitcher_probability_b * 0.2)
            method = "recent_form_win_rate_plus_pitcher_season_stats_baseline"
        limitations = [
            "선택한 투수 통계가 없거나 한쪽만 있어 팀 성적 기준으로 계산함" if not pitcher_applied else "선택한 투수의 시즌 지표를 20% 가중한 기준선입니다.",
            "부상·당일 라인업·불펜 소모·날씨 미반영",
            "과거 데이터 기반 기준선이며 실제 승패를 보장하지 않음",
        ]
        current_year = datetime.now(timezone(timedelta(hours=9))).year
        if request.season is not None and request.season < current_year:
            limitations.append("과거 시즌 최종 기록을 사용하는 비교입니다. 경기 이후 정보가 포함되어 경기별 사전 예측 검증에는 사용할 수 없습니다.")
        return PredictionResponse(
            team_a=request.team_a,
            team_b=request.team_b,
            team_a_probability=round(probability_a, 4),
            team_b_probability=round(probability_b, 4),
            method=method,
            season=request.season,
            last_n=request.last_n,
            pitchers={"team_a": request.pitcher_a, "team_b": request.pitcher_b},
            limitations=limitations,
            pitcher_stats_applied=pitcher_applied,
            pitcher_stats_as_of={
                "team_a": pitcher_a_stats[0].as_of if pitcher_a_stats else None,
                "team_b": pitcher_b_stats[0].as_of if pitcher_b_stats else None,
            },
            pitcher_data_count={"team_a": len(pitcher_a_stats), "team_b": len(pitcher_b_stats)},
        )


prediction_service = PredictionService()
