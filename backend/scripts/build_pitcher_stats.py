"""전체 투수 원본 CSV에서 팀별 IP 상위 투수 3명을 선정한다.

원본 CSV는 KBO 공식 기록을 직접 확인해 작성해야 하며, 이 스크립트는
선정·검증·출력만 담당한다. 통계값을 임의로 생성하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs


TEAM_CODES = {
    "KIA": "KIA",
    "삼성": "SAMSUNG",
    "SAMSUNG": "SAMSUNG",
    "LG": "LG",
    "두산": "DOOSAN",
    "DOOSAN": "DOOSAN",
    "SSG": "SSG",
    "KT": "KT",
    "롯데": "LOTTE",
    "LOTTE": "LOTTE",
    "한화": "HANWHA",
    "HANWHA": "HANWHA",
    "NC": "NC",
    "키움": "KIWOOM",
    "KIWOOM": "KIWOOM",
}
TEAM_NAMES = {
    "KIA": "KIA", "SAMSUNG": "삼성", "LG": "LG", "DOOSAN": "두산",
    "SSG": "SSG", "KT": "KT", "LOTTE": "롯데", "HANWHA": "한화",
    "NC": "NC", "KIWOOM": "키움",
}
FIELDS = [
    "season", "team_code", "team", "player_id", "player", "games_appeared",
    "innings", "earned_runs", "era", "whip", "strikeouts", "source_url",
    "as_of", "updated_at",
]
NON_NEGATIVE_INTS = ("games_appeared", "earned_runs", "strikeouts")
NON_NEGATIVE_FLOATS = ("era", "whip")


def parse_ip(value: str) -> float:
    value = " ".join(value.replace("⅓", " 1/3").replace("⅔", " 2/3").split())
    if "/" in value:
        whole, fraction = value.split(" ", 1) if " " in value else ("0", value)
        if fraction not in {"1/3", "2/3"} or not whole.isdigit():
            raise ValueError("IP 분수는 정수 이닝과 1/3 또는 2/3이어야 함")
        return int(whole) + int(fraction[0]) / 3
    return float(value)


def build(input_path: Path, output_path: Path, season: int, top_n: int, as_of: str, updated_at: str | None = None) -> int:
    if top_n < 1:
        raise ValueError("--top-n은 1 이상이어야 합니다")
    if not input_path.exists():
        raise FileNotFoundError(f"원본 CSV가 없습니다: {input_path}")
    datetime.strptime(as_of, "%Y-%m-%d")
    if updated_at is None:
        updated_at = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    else:
        try:
            datetime.fromisoformat(updated_at)
        except ValueError as exc:
            raise ValueError("--updated-at은 ISO 8601 형식이어야 합니다") from exc
    rows: list[dict[str, str]] = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")
        source_keys: set[tuple[int, str, str]] = set()
        for line_no, row in enumerate(reader, start=2):
            try:
                if int(row["season"]) != season:
                    continue
                raw_code = (row.get("team_code") or "").strip()
                raw_team = (row.get("team") or "").strip()
                code = TEAM_CODES.get(raw_code)
                team_from_name = TEAM_CODES.get(raw_team)
                if not code or not team_from_name or code != team_from_name:
                    raise ValueError("team_code와 team이 없거나 서로 일치하지 않음")
                player_id = (row.get("player_id") or "").strip()
                player = (row.get("player") or "").strip()
                if not player_id or not player:
                    raise ValueError("선수 ID·선수명이 비어 있음")
                source_url = (row.get("source_url") or "").strip()
                parsed_source = urlparse(source_url)
                valid_path = parsed_source.path.startswith("/Record/Player/") or parsed_source.path == "/Record/Retire/Pitcher.aspx"
                if not (parsed_source.scheme == "https" and parsed_source.netloc == "www.koreabaseball.com" and valid_path):
                    raise ValueError("공식 KBO 선수 기록 source_url이 비어 있거나 올바르지 않음")
                if parse_qs(parsed_source.query).get("playerId") != [player_id]:
                    raise ValueError("source_url의 playerId가 선수 ID와 다름")
                innings = parse_ip(row["innings"])
                if not math.isfinite(innings) or innings < 0:
                    raise ValueError("innings는 0 이상의 유한한 숫자여야 함")
                source_key = (season, code, player_id)
                if source_key in source_keys:
                    raise ValueError("원본에 season/team_code/player_id 중복이 있음")
                source_keys.add(source_key)
                # 공식 기록의 0이닝 선수는 ERA/WHIP가 '-'일 수 있다.
                if innings == 0:
                    continue
                for field in NON_NEGATIVE_INTS:
                    value = int(row[field])
                    if value < 0:
                        raise ValueError(f"{field}는 0 이상이어야 함")
                for field in NON_NEGATIVE_FLOATS:
                    value = float(row[field])
                    if not math.isfinite(value) or value < 0:
                        raise ValueError(f"{field}는 0 이상이어야 함")
                item = dict(row)
                item["season"] = str(season)
                item["team_code"] = code
                item["team"] = TEAM_NAMES[code]
                item["player_id"] = player_id
                item["player"] = player
                item["source_url"] = source_url
                item["innings"] = f"{innings:.4f}".rstrip("0").rstrip(".")
                item["as_of"] = as_of
                item["updated_at"] = updated_at
                rows.append(item)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{input_path}:{line_no} 행 오류: {exc}") from exc

    selected: list[dict[str, str]] = []
    counts = Counter(row["team_code"] for row in rows)
    for code in TEAM_NAMES:
        team_rows = [row for row in rows if row["team_code"] == code]
        team_rows.sort(key=lambda row: (-parse_ip(row["innings"]), row["player_id"]))
        if len(team_rows) < top_n:
            raise ValueError(f"{code} 투수 데이터가 {top_n}명보다 적습니다: {len(team_rows)}명")
        selected.extend(team_rows[:top_n])

    keys = [(r["season"], r["team_code"], r["player_id"]) for r in selected]
    if len(keys) != len(set(keys)):
        raise ValueError("season/team_code/player_id 중복이 있습니다")
    expected_count = len(TEAM_NAMES) * top_n
    if len(selected) != expected_count:
        raise ValueError(f"최종 결과가 {expected_count}명이 아닙니다: {len(selected)}명")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(selected)
    print(f"선정 완료: {len(selected)}명")
    for code in TEAM_NAMES:
        print(f"  {TEAM_NAMES[code]}({code}): {counts[code]}명 원본 → {top_n}명 선택")
    print(f"출력: {output_path}")
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description="KBO 투수 IP 상위 N명 CSV 생성")
    parser.add_argument("--input", required=True, type=Path, help="KBO 공식 기록을 정리한 원본 CSV")
    parser.add_argument("--output", default=Path("data/raw/pitcher_stats.csv"), type=Path)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--as-of", required=True, help="KBO 기록 기준일 YYYY-MM-DD")
    parser.add_argument("--updated-at", help="CSV 반영 시각 ISO 8601 (생략 시 현재 KST)")
    args = parser.parse_args()
    build(args.input, args.output, args.season, args.top_n, args.as_of, args.updated_at)


if __name__ == "__main__":
    main()
