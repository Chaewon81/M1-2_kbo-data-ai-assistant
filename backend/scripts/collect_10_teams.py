"""KBO 공식 일정에서 10개 구단 경기 데이터를 수집하고 검증한다.

기존 M1-1 수집기를 재사용하되, 수집 전에 팀 목록과 중복·누락을 검증한다.
"""

from __future__ import annotations

import argparse
import sys
import re
from collections import Counter, defaultdict
from datetime import date
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "M1-1_summary"))

from collect_games import (
    REGULAR_SEASON_MONTHS,
    build_records,
    fetch_schedule,
    record_key,
    write_csv,
)


TEAMS = ("KIA", "삼성", "LG", "두산", "SSG", "KT", "롯데", "한화", "NC", "키움")


def validate(records: list, years: tuple[int, ...], months: tuple[int, ...]) -> None:
    if not records:
        raise RuntimeError("수집된 데이터가 없습니다.")
    keys = [record_key(record) for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("중복 game_id/team 기록이 발견되었습니다.")
    missing = sorted(set(TEAMS) - {record.team for record in records})
    if missing:
        raise RuntimeError(f"데이터가 없는 구단: {', '.join(missing)}")
    for record in records:
        try:
            parsed_date = date.fromisoformat(record.date)
        except ValueError as error:
            raise RuntimeError(f"잘못된 날짜: {record.date}") from error
        if parsed_date.year != record.season or record.team not in TEAMS or record.opponent not in TEAMS:
            raise RuntimeError(f"팀·시즌·날짜 검증 실패: {record}")
        if record.status == "completed" and not record.game_id:
            raise RuntimeError(f"완료 경기의 game_id가 비어 있습니다: {record}")
        if record.runs_for is not None and record.runs_for < 0 or record.runs_against is not None and record.runs_against < 0:
            raise RuntimeError(f"음수 점수: {record}")
        if record.status == "completed" and (record.runs_for is None or record.runs_against is None or not record.result):
            raise RuntimeError(f"완료 경기 필수값 누락: {record}")
        if record.status not in {"completed", "not_completed", "scheduled", "cancelled", "postponed"}:
            raise RuntimeError(f"알 수 없는 경기 상태: {record.status}")
        if record.status == "completed":
            expected = "W" if record.runs_for > record.runs_against else "L" if record.runs_for < record.runs_against else "D"
            if record.result != expected:
                raise RuntimeError(f"점수와 결과가 일치하지 않습니다: {record}")

    by_game = defaultdict(list)
    for record in records:
        by_game[record.game_id].append(record)
    for game_id, pair in by_game.items():
        if len(pair) != 2:
            raise RuntimeError(f"{game_id}: 양 팀 기록이 2건이 아닙니다 ({len(pair)}건)")
        first, second = pair
        if first.team != second.opponent or second.team != first.opponent:
            raise RuntimeError(f"{game_id}: 팀·상대팀이 서로 일치하지 않습니다.")
        if first.home_away == second.home_away:
            raise RuntimeError(f"{game_id}: 홈·원정 정보가 일치하지 않습니다.")
        if (first.date, first.season, first.status, first.stadium) != (second.date, second.season, second.status, second.stadium):
            raise RuntimeError(f"{game_id}: 날짜·시즌·상태·구장이 양 팀 기록에서 다릅니다.")
        if first.runs_for != second.runs_against or first.runs_against != second.runs_for:
            raise RuntimeError(f"{game_id}: 양 팀 점수가 서로 일치하지 않습니다.")
        if first.result == "W" and second.result != "L" or first.result == "L" and second.result != "W" or first.result == "D" and second.result != "D":
            raise RuntimeError(f"{game_id}: 양 팀 결과가 서로 반대가 아닙니다.")

    counts = Counter((record.season, record.team) for record in records)
    completed_months = set(REGULAR_SEASON_MONTHS).issubset(set(months))
    print("팀별 수집 건수:")
    for team in TEAMS:
        team_records = [record for record in records if record.team == team]
        completed = sum(record.status == "completed" for record in team_records)
        print(f"  {team}: 전체 {len(team_records)}건 / 완료 {completed}건")
    for year in years:
        count = sum(record.season == year for record in records)
        print(f"{year} 시즌: {count}건")
        for team in TEAMS:
            team_count = counts[(year, team)]
            if team_count == 0:
                raise RuntimeError(f"{year} 시즌 {team} 데이터가 없습니다.")
            if completed_months and year < date.today().year:
                completed_count = sum(record.status == "completed" for record in records if record.season == year and record.team == team)
                if completed_count != 144:
                    raise RuntimeError(f"{year} 시즌 {team} 완료 경기 수가 144가 아닙니다: {completed_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="KBO 10개 구단 경기 데이터 수집")
    parser.add_argument("--years", nargs="+", type=int, default=[2025])
    parser.add_argument("--months", nargs="+", type=int, default=list(REGULAR_SEASON_MONTHS))
    parser.add_argument("--output", type=Path, default=Path("data/raw/game_results_10teams.csv"))
    parser.add_argument("--all-seasons", action="store_true", help="2023~2025 정규시즌 전체 수집")
    parser.add_argument("--completed-only", action="store_true", help="완료 경기만 저장, 공식 game_id 필수")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="수집 기준일 YYYY-MM-DD")
    parser.add_argument("--split-seasons", action="store_true", help="--output 디렉터리에 시즌별 CSV 저장")
    args = parser.parse_args()
    years = (2023, 2024, 2025) if args.all_seasons else tuple(args.years)
    months = tuple(REGULAR_SEASON_MONTHS) if args.all_seasons else tuple(args.months)

    records_by_key = {}
    for year in years:
        for month in months:
            print(f"수집 중: {year}-{month:02}")
            payload = fetch_schedule(year, month)
            for record in build_records(payload, year, TEAMS):
                if date.fromisoformat(record.date) > args.as_of:
                    continue
                if args.completed_only:
                    if record.status != "completed":
                        continue
                    if not re.fullmatch(r"\d{8}[A-Z]{4}\d", record.game_id):
                        raise RuntimeError(f"완료 경기의 공식 game_id 확인 필요: {record}")
                if not record.game_id:
                    teams_key = "_".join(sorted((record.team, record.opponent)))
                    record = replace(record, game_id=f"{record.date}_{teams_key}")
                key = record_key(record)
                if key in records_by_key and records_by_key[key] != record:
                    raise RuntimeError(f"같은 경기 ID에 다른 기록이 있습니다: {key}")
                records_by_key[key] = record

    records = sorted(records_by_key.values(), key=lambda record: (record.date, record.game_id, record.team))
    validate(records, years, months)
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if args.split_seasons:
        for year in years:
            season_records = [record for record in records if record.season == year]
            path = output_path / f"game_results_{year}.csv"
            write_csv(season_records, path)
            print(f"저장 완료: {path} ({len(season_records)}행)")
    else:
        write_csv(records, output_path)
        print(f"저장 완료: {output_path} ({len(records)}행)")


if __name__ == "__main__":
    main()
