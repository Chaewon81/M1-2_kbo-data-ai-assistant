"""원본 경기 데이터를 분석용 데이터로 정제한다.

처리 기준:
- `status`가 `completed`인 실제 완료 경기만 분석 대상에 포함한다.
- 취소·미완료 경기는 점수와 결과가 없으므로 제외하되, 원본 CSV에는 보존한다.
- 점수 차이가 큰 실제 완료 경기는 이상치로 삭제하지 않는다.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path


RAW_PATH = Path("data/raw/game_results_raw.csv")
PROCESSED_PATH = Path("data/processed/game_results.csv")
RAW_REQUIRED_COLUMNS = {
    "date",
    "season",
    "team",
    "opponent",
    "home_away",
    "runs_for",
    "runs_against",
    "stadium",
    "result",
    "status",
    "game_id",
    "source_url",
}
PROCESSED_COLUMNS = (
    "date",
    "season",
    "month",
    "team",
    "opponent",
    "home_away",
    "runs_for",
    "runs_against",
    "result",
    "win",
    "loss",
    "draw",
    "run_diff",
    "stadium",
    "game_id",
    "source_url",
)


def validate_completed_row(row: dict[str, str], row_number: int) -> None:
    """완료 경기 행에 분석에 필요한 값이 모두 있는지 확인한다."""

    missing = [field for field in RAW_REQUIRED_COLUMNS if not row.get(field)]
    if missing:
        raise ValueError(f"{row_number}행에 필수값이 없습니다: {', '.join(sorted(missing))}")

    try:
        parsed_date = date.fromisoformat(row["date"])
        season = int(row["season"])
        runs_for = int(row["runs_for"])
        runs_against = int(row["runs_against"])
    except ValueError as error:
        raise ValueError(f"{row_number}행의 날짜·시즌·점수 형식이 올바르지 않습니다.") from error

    if parsed_date.year != season:
        raise ValueError(f"{row_number}행의 날짜 연도와 season 값이 다릅니다.")
    if runs_for < 0 or runs_against < 0:
        raise ValueError(f"{row_number}행의 점수는 음수일 수 없습니다.")

    expected_result = "W" if runs_for > runs_against else "L" if runs_for < runs_against else "D"
    if row["result"] != expected_result:
        raise ValueError(
            f"{row_number}행의 결과가 점수와 다릅니다: "
            f"{runs_for}-{runs_against}이면 {expected_result}여야 합니다."
        )


def make_processed_row(row: dict[str, str]) -> dict[str, int | str]:
    runs_for = int(row["runs_for"])
    runs_against = int(row["runs_against"])
    return {
        "date": row["date"],
        "season": int(row["season"]),
        "month": int(row["date"].split("-")[1]),
        "team": row["team"],
        "opponent": row["opponent"],
        "home_away": row["home_away"],
        "runs_for": runs_for,
        "runs_against": runs_against,
        "result": row["result"],
        "win": int(row["result"] == "W"),
        "loss": int(row["result"] == "L"),
        "draw": int(row["result"] == "D"),
        "run_diff": runs_for - runs_against,
        "stadium": row["stadium"],
        "game_id": row["game_id"],
        "source_url": row["source_url"],
    }


def main() -> None:
    with RAW_PATH.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or not RAW_REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("원본 CSV의 필수 컬럼이 누락되었습니다.")
        raw_rows = list(reader)

    completed_rows = [row for row in raw_rows if row["status"] == "completed"]
    excluded_rows = [row for row in raw_rows if row["status"] != "completed"]
    for row_number, row in enumerate(completed_rows, start=2):
        validate_completed_row(row, row_number)

    processed_rows = [make_processed_row(row) for row in completed_rows]
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PROCESSED_COLUMNS)
        writer.writeheader()
        writer.writerows(processed_rows)

    print(f"원본 행 수: {len(raw_rows)}")
    print(f"분석용 완료 경기: {len(processed_rows)}")
    print(f"제외한 미완료/취소 경기: {len(excluded_rows)}")
    print(f"저장 완료: {PROCESSED_PATH}")
    for (season, team), count in sorted(Counter((row["season"], row["team"]) for row in processed_rows).items()):
        print(f"{season} {team}: {count}경기")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1)
