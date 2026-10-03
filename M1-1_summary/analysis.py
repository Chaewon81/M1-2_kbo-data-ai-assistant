"""분석용 경기 데이터에서 시즌별 성적을 집계하고 KBO 공식 기록과 비교한다."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict, deque
from pathlib import Path


INPUT_PATH = Path("data/processed/game_results.csv")
OUTPUT_PATH = Path("data/processed/season_summary.csv")
MONTHLY_OUTPUT_PATH = Path("data/processed/monthly_summary.csv")
ROLLING_OUTPUT_PATH = Path("data/processed/rolling_win_rate.csv")
ROLLING_WINDOW = 10

# KBO 공식 홈페이지 '역대 구단성적'의 2023~2025 최종 기록.
# 출처: https://www.koreabaseball.com/Record/History/Team/Record.aspx
OFFICIAL_RECORDS = {
    (2023, "KIA"): (144, 73, 69, 2),
    (2023, "삼성"): (144, 61, 82, 1),
    (2024, "KIA"): (144, 87, 55, 2),
    (2024, "삼성"): (144, 78, 64, 2),
    (2025, "KIA"): (144, 65, 75, 4),
    (2025, "삼성"): (144, 74, 68, 2),
}
OUTPUT_COLUMNS = ("season", "team", "games", "wins", "losses", "draws", "win_rate")
MONTHLY_OUTPUT_COLUMNS = ("season", "month", "team", "games", "wins", "losses", "draws", "win_rate")
ROLLING_OUTPUT_COLUMNS = (
    "date",
    "season",
    "month",
    "team",
    "opponent",
    "result",
    "rolling_window_games",
    "rolling_wins",
    "rolling_losses",
    "rolling_draws",
    "rolling_win_rate",
)


def load_and_aggregate() -> dict[tuple[int, str], dict[str, int]]:
    totals: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0}
    )
    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            key = (int(row["season"]), row["team"])
            totals[key]["games"] += 1
            if row["result"] == "W":
                totals[key]["wins"] += 1
            elif row["result"] == "L":
                totals[key]["losses"] += 1
            elif row["result"] == "D":
                totals[key]["draws"] += 1
            else:
                raise ValueError(f"{row_number}행의 result 값이 올바르지 않습니다: {row['result']}")
    return totals


def load_and_aggregate_monthly() -> dict[tuple[int, int, str], dict[str, int]]:
    """시즌·월·팀 단위로 경기 수와 승·패·무를 집계한다."""

    totals: dict[tuple[int, int, str], dict[str, int]] = defaultdict(
        lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0}
    )
    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            key = (int(row["season"]), int(row["month"]), row["team"])
            totals[key]["games"] += 1
            if row["result"] == "W":
                totals[key]["wins"] += 1
            elif row["result"] == "L":
                totals[key]["losses"] += 1
            elif row["result"] == "D":
                totals[key]["draws"] += 1
            else:
                raise ValueError(f"{row_number}행의 result 값이 올바르지 않습니다: {row['result']}")
    return totals


def validate_against_official(totals: dict[tuple[int, str], dict[str, int]]) -> None:
    """계산한 경기·승·패·무가 KBO 공식 최종 기록과 같은지 확인한다."""

    if set(totals) != set(OFFICIAL_RECORDS):
        raise ValueError("집계된 시즌·팀 조합이 검증 대상과 다릅니다.")

    mismatches = []
    for key, official in OFFICIAL_RECORDS.items():
        calculated = totals[key]
        calculated_record = (
            calculated["games"],
            calculated["wins"],
            calculated["losses"],
            calculated["draws"],
        )
        if calculated_record != official:
            mismatches.append(f"{key}: 계산 {calculated_record}, 공식 {official}")
    if mismatches:
        raise ValueError("KBO 공식 기록과 일치하지 않습니다.\n" + "\n".join(mismatches))


def write_summary(totals: dict[tuple[int, str], dict[str, int]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for (season, team), values in sorted(totals.items()):
            win_rate = values["wins"] / (values["wins"] + values["losses"])
            writer.writerow({"season": season, "team": team, **values, "win_rate": f"{win_rate:.3f}"})


def validate_monthly_totals(
    season_totals: dict[tuple[int, str], dict[str, int]],
    monthly_totals: dict[tuple[int, int, str], dict[str, int]],
) -> None:
    """월별 합계가 시즌별 집계와 같은지 확인한다."""

    recalculated: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0}
    )
    for (season, _month, team), values in monthly_totals.items():
        for field, value in values.items():
            recalculated[(season, team)][field] += value
    if dict(recalculated) != dict(season_totals):
        raise ValueError("월별 합계가 시즌별 집계와 일치하지 않습니다.")


def write_monthly_summary(totals: dict[tuple[int, int, str], dict[str, int]]) -> None:
    with MONTHLY_OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MONTHLY_OUTPUT_COLUMNS)
        writer.writeheader()
        for (season, month, team), values in sorted(totals.items()):
            win_rate = values["wins"] / (values["wins"] + values["losses"])
            writer.writerow(
                {"season": season, "month": month, "team": team, **values, "win_rate": f"{win_rate:.3f}"}
            )


def calculate_rolling_win_rate() -> list[dict[str, int | str]]:
    """팀·시즌별 최근 10경기 승률을 계산한다.

    무승부는 10경기 창에는 포함하지만 KBO 방식에 따라 승률 분모에서는 제외한다.
    첫 9경기는 10경기 창이 완성되지 않았으므로 rolling_win_rate를 비워 둔다.
    """

    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    rows.sort(key=lambda row: (int(row["season"]), row["team"], row["date"], row["game_id"]))

    windows: dict[tuple[int, str], deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW))
    output_rows: list[dict[str, int | str]] = []
    for row in rows:
        key = (int(row["season"]), row["team"])
        window = windows[key]
        window.append(row)
        wins = sum(game["result"] == "W" for game in window)
        losses = sum(game["result"] == "L" for game in window)
        draws = sum(game["result"] == "D" for game in window)
        output_rows.append(
            {
                "date": row["date"],
                "season": row["season"],
                "month": row["month"],
                "team": row["team"],
                "opponent": row["opponent"],
                "result": row["result"],
                "rolling_window_games": len(window),
                "rolling_wins": wins,
                "rolling_losses": losses,
                "rolling_draws": draws,
                "rolling_win_rate": f"{wins / (wins + losses):.3f}" if len(window) == ROLLING_WINDOW else "",
            }
        )
    return output_rows


def validate_rolling_rows(rows: list[dict[str, int | str]]) -> None:
    """최근 10경기 창이 각 팀·시즌별로 올바르게 생성됐는지 점검한다."""

    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as file:
        expected_count = sum(1 for _ in csv.DictReader(file))
    if len(rows) != expected_count:
        raise ValueError("Rolling 결과 행 수가 분석용 경기 수와 다릅니다.")
    full_windows = [row for row in rows if row["rolling_window_games"] == ROLLING_WINDOW]
    if any(not row["rolling_win_rate"] for row in full_windows):
        raise ValueError("10경기 창의 승률이 비어 있습니다.")


def write_rolling_summary(rows: list[dict[str, int | str]]) -> None:
    with ROLLING_OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=ROLLING_OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    totals = load_and_aggregate()
    monthly_totals = load_and_aggregate_monthly()
    validate_against_official(totals)
    validate_monthly_totals(totals, monthly_totals)
    rolling_rows = calculate_rolling_win_rate()
    validate_rolling_rows(rolling_rows)
    write_summary(totals)
    write_monthly_summary(monthly_totals)
    write_rolling_summary(rolling_rows)

    print("KBO 공식 최종 기록 검증: 일치")
    for (season, team), values in sorted(totals.items()):
        win_rate = values["wins"] / (values["wins"] + values["losses"])
        print(
            f"{season} {team}: {values['games']}경기 "
            f"{values['wins']}승 {values['losses']}패 {values['draws']}무, 승률 {win_rate:.3f}"
        )
    print(f"저장 완료: {OUTPUT_PATH}")
    print(f"저장 완료: {MONTHLY_OUTPUT_PATH}")
    print(f"저장 완료: {ROLLING_OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1)
