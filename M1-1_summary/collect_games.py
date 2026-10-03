"""KBO 공식 홈페이지에서 경기일정·결과를 수집한다.

기본 실행은 과제의 최소 단위 테스트인 2025년 4월 KIA·삼성 경기만 대상으로 한다.
KBO의 개발자용 Open API가 아니라, 공식 경기일정 화면이 사용하는 요청을 조회한다.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


KBO_BASE_URL = "https://www.koreabaseball.com"
SCHEDULE_PAGE_URL = f"{KBO_BASE_URL}/Schedule/Schedule.aspx"
SCHEDULE_API_URL = f"{KBO_BASE_URL}/ws/Schedule.asmx/GetScheduleList"
DEFAULT_TEAMS = ("KIA", "삼성")
REGULAR_SEASON_SERIES = "0,9,6"
REGULAR_SEASON_MONTHS = tuple(range(3, 11))
FIELDNAMES = (
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
)


@dataclass(frozen=True)
class GameRecord:
    date: str
    season: int
    team: str
    opponent: str
    home_away: str
    runs_for: int | None
    runs_against: int | None
    stadium: str
    result: str
    status: str
    game_id: str
    source_url: str


class SpanParser(HTMLParser):
    """KBO 일정 응답의 경기 HTML 조각에서 span 텍스트와 class를 읽는다."""

    def __init__(self) -> None:
        super().__init__()
        self.spans: list[tuple[str, str]] = []
        self._span_classes: list[str] = []
        self._text_parts: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "span":
            self._span_classes.append(dict(attrs).get("class") or "")
            self._text_parts.append([])

    def handle_data(self, data: str) -> None:
        if self._text_parts:
            self._text_parts[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._text_parts:
            self.spans.append((self._span_classes.pop(), "".join(self._text_parts.pop()).strip()))


def plain_text(value: str) -> str:
    """HTML 조각을 사람이 읽을 수 있는 텍스트로 바꾼다."""

    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def parse_match(value: str) -> tuple[str, str, int | None, int | None]:
    """'원정 vs 홈' HTML에서 팀명과 점수를 추출한다."""

    parser = SpanParser()
    parser.feed(value)
    texts = [text for _, text in parser.spans if text]
    if "vs" not in texts:
        raise ValueError(f"경기 형식을 해석할 수 없습니다: {plain_text(value)}")

    vs_index = texts.index("vs")
    away_team = texts[0]
    home_team = texts[-1]
    score_texts = [text for css_class, text in parser.spans if css_class in {"win", "lose", "same"}]
    if len(score_texts) == 2 and all(score.isdigit() for score in score_texts):
        return away_team, home_team, int(score_texts[0]), int(score_texts[1])

    # 점수가 없는 일정·취소 경기는 팀명만 남긴다.
    _ = vs_index
    return away_team, home_team, None, None


def fetch_schedule(year: int, month: int) -> dict:
    """KBO 공식 일정 화면과 동일한 GET/POST 흐름으로 한 달 일정을 가져온다."""

    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    query = urlencode({"seriesId": REGULAR_SEASON_SERIES, "year": year, "month": f"{month:02}"})
    page_url = f"{SCHEDULE_PAGE_URL}?{query}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": page_url}

    try:
        opener.open(Request(page_url, headers=headers), timeout=30).read()
        body = urlencode(
            {
                "leId": "1",
                "srIdList": REGULAR_SEASON_SERIES,
                "seasonId": str(year),
                "gameMonth": f"{month:02}",
                "teamId": "",
            }
        ).encode("utf-8")
        response = opener.open(
            Request(
                SCHEDULE_API_URL,
                data=body,
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                },
            ),
            timeout=30,
        )
        return json.loads(response.read().decode("utf-8-sig"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"KBO 일정 데이터를 가져오지 못했습니다: {error}") from error


def get_cell_text(row: list[dict], css_class: str) -> tuple[int, str]:
    for index, cell in enumerate(row):
        if cell.get("Class") == css_class:
            return index, cell.get("Text", "")
    raise ValueError(f"'{css_class}' 셀을 찾지 못했습니다.")


def build_records(payload: dict, year: int, teams: Iterable[str]) -> list[GameRecord]:
    """KBO 응답을 팀별 한 행의 원본 데이터 구조로 변환한다."""

    target_teams = set(teams)
    records: list[GameRecord] = []
    current_date: str | None = None

    for item in payload.get("rows", []):
        row = item.get("row", [])
        try:
            _, date_cell = get_cell_text(row, "day")
            match = re.search(r"(\d{2})\.(\d{2})", plain_text(date_cell))
            if match:
                current_date = f"{year}-{match.group(1)}-{match.group(2)}"
        except ValueError:
            pass

        if current_date is None:
            raise ValueError("첫 경기 행 전에 날짜를 찾지 못했습니다.")

        play_index, play_html = get_cell_text(row, "play")
        away_team, home_team, away_score, home_score = parse_match(play_html)
        if away_team not in target_teams and home_team not in target_teams:
            continue

        # KBO 일정 표에서 구장은 경기 셀 뒤 다섯 번째 셀이다.
        stadium = plain_text(row[play_index + 5].get("Text", ""))
        relay_html = row[play_index + 1].get("Text", "")
        game_id_match = re.search(r"gameId=([^&'\"]+)", relay_html)
        game_id = game_id_match.group(1) if game_id_match else ""
        source_url = (
            f"{KBO_BASE_URL}/Schedule/GameCenter/Main.aspx?gameDate={current_date.replace('-', '')}"
            f"&gameId={game_id}"
            if game_id
            else SCHEDULE_PAGE_URL
        )
        completed = away_score is not None and home_score is not None

        for team, opponent, home_away, runs_for, runs_against in (
            (away_team, home_team, "away", away_score, home_score),
            (home_team, away_team, "home", home_score, away_score),
        ):
            if team not in target_teams:
                continue
            result = ""
            if completed:
                result = "W" if runs_for > runs_against else "L" if runs_for < runs_against else "D"
            records.append(
                GameRecord(
                    date=current_date,
                    season=year,
                    team=team,
                    opponent=opponent,
                    home_away=home_away,
                    runs_for=runs_for,
                    runs_against=runs_against,
                    stadium=stadium,
                    result=result,
                    status="completed" if completed else "not_completed",
                    game_id=game_id,
                    source_url=source_url,
                )
            )
    return records


def write_csv(records: list[GameRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def record_key(record: GameRecord) -> tuple[str, ...]:
    """같은 경기를 월별 요청에서 중복 저장하지 않기 위한 키를 만든다."""

    if record.game_id:
        return (record.game_id, record.team)
    return (record.date, record.team, record.opponent, record.home_away, record.status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KBO 공식 경기일정·결과 수집")
    parser.add_argument("--years", "--year", dest="years", nargs="+", type=int, default=[2025], help="수집 연도(들) (기본값: 2025)")
    parser.add_argument("--months", "--month", dest="months", nargs="+", type=int, choices=range(1, 13), default=[4], help="수집 월(들) (기본값: 4)")
    parser.add_argument("--all-seasons", action="store_true", help="2023~2025 정규시즌(3~10월)을 모두 수집")
    parser.add_argument("--teams", nargs="+", default=list(DEFAULT_TEAMS), help="대상 팀명 (기본값: KIA 삼성)")
    parser.add_argument("--output", type=Path, default=Path("data/raw/game_results_raw.csv"), help="저장할 CSV 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = (2023, 2024, 2025) if args.all_seasons else args.years
    months = REGULAR_SEASON_MONTHS if args.all_seasons else args.months
    records_by_key: dict[tuple[str, ...], GameRecord] = {}

    for year in years:
        for month in months:
            print(f"수집 중: {year}-{month:02}")
            payload = fetch_schedule(year, month)
            for record in build_records(payload, year, args.teams):
                records_by_key[record_key(record)] = record

    records = sorted(records_by_key.values(), key=lambda record: (record.date, record.game_id, record.team))
    if not records:
        raise RuntimeError("대상 팀 경기 데이터를 찾지 못했습니다. 연도·월·팀명을 확인하세요.")
    write_csv(records, args.output)

    print(f"저장 완료: {args.output} ({len(records)}행)")
    for year in years:
        year_records = [record for record in records if record.season == year]
        completed = sum(record.status == "completed" for record in year_records)
        print(f"{year}: {len(year_records)}행 (완료 {completed}행, 미완료/취소 {len(year_records) - completed}행)")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1)
