"""KBO 정규시즌 투수 기록을 팀별 IP 내림차순으로 수집한다."""

from __future__ import annotations

import argparse
import csv
from http.cookiejar import CookieJar
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode

try:
    from .build_pitcher_stats import FIELDS, TEAM_NAMES, build, parse_ip
except ImportError:
    from build_pitcher_stats import FIELDS, TEAM_NAMES, build, parse_ip

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx"
PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"
KBO_CODES = dict(zip(TEAM_NAMES, ("HT", "SS", "LG", "OB", "SK", "KT", "LT", "HH", "NC", "WO")))
OPENER = build_opener(HTTPCookieProcessor(CookieJar()))


class RecordPage(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.form: dict[str, str] = {}
        self.rows: list[list[str]] = []
        self.links: dict[int, str] = {}
        self.select = ""
        self.cell: list[str] | None = None
        self.row: list[str] | None = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "input" and attrs.get("name"):
            self.form[attrs["name"]] = attrs.get("value", "")
        elif tag == "select":
            self.select = attrs.get("name", "")
        elif tag == "option" and self.select:
            if self.select not in self.form or "selected" in attrs:
                self.form[self.select] = attrs.get("value", "")
        elif tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []
        elif tag == "a" and self.row is not None and "playerId=" in attrs.get("href", ""):
            self.links[len(self.rows)] = urljoin(URL, attrs["href"])

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = ""
        elif tag == "td" and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def fetch(form=None) -> RecordPage:
    data = urlencode(form).encode() if form is not None else None
    request = Request(URL, data=data, headers={"User-Agent": "Mozilla/5.0"})
    with OPENER.open(request, timeout=30) as response:
        html = response.read().decode("utf-8-sig")
        page = RecordPage(html)
        if not page.form:
            raise ValueError(f"KBO 응답에 기록 폼이 없습니다: {html[:300]!r}")
        return page


def get_team(code: str, season: int) -> list[dict[str, str]]:
    initial = fetch()
    if initial.form.get(PREFIX + "ddlSeason$ddlSeason") != str(season):
        # 시즌 변경 시 사이트가 팀 목록을 다시 구성하므로 먼저 별도 요청한다.
        season_form = initial.form.copy()
        season_form.update({
            "__EVENTTARGET": PREFIX + "ddlSeason$ddlSeason", "__EVENTARGUMENT": "",
            PREFIX + "ddlSeason$ddlSeason": str(season),
        })
        initial = fetch(season_form)
    form = initial.form.copy()
    form.update({
        "__EVENTTARGET": PREFIX + "lbtnOrderBy", "__EVENTARGUMENT": "",
        PREFIX + "ddlSeason$ddlSeason": str(season),
        PREFIX + "ddlSeries$ddlSeries": "0",
        PREFIX + "ddlTeam$ddlTeam": KBO_CODES[code],
        PREFIX + "hfOrderByCol": "INN2_CN", PREFIX + "hfOrderBy": "DESC",
        PREFIX + "hfPage": "1",
    })
    page = fetch(form)
    expected = {
        PREFIX + "ddlSeason$ddlSeason": str(season),
        PREFIX + "ddlSeries$ddlSeries": "0",
        PREFIX + "ddlTeam$ddlTeam": KBO_CODES[code],
        PREFIX + "hfOrderByCol": "INN2_CN", PREFIX + "hfOrderBy": "DESC",
    }
    for field, value in expected.items():
        if page.form.get(field) != value:
            raise ValueError(f"공식 기록 조회 조건 적용 실패: {field}")
    records = []
    for index, cells in enumerate(page.rows):
        if index not in page.links or len(cells) != 19:
            continue
        if cells[2] != TEAM_NAMES[code]:
            raise ValueError(f"팀별 기록 대신 다른 팀/통합 기록이 반환됨: {cells[2]}")
        source = page.links[index]
        player_id = parse_qs(urlparse(source).query)["playerId"][0]
        records.append(dict(zip(FIELDS, (
            str(season), code, cells[2], player_id, cells[1], cells[4],
            cells[10], cells[17], cells[3], cells[18], cells[15], source, "", "",
        ))))
    if len(records) < 3:
        raise ValueError(f"{code}: 투수 기록이 3명 미만입니다 ({len(records)})")
    innings = [parse_ip(row["innings"]) for row in records]
    if innings != sorted(innings, reverse=True):
        raise ValueError(f"{code}: 공식 페이지 IP 내림차순 정렬 실패")
    # IP 내림차순 첫 페이지(최대 30명)면 상위 3명을 선정할 수 있다.
    # 전체 투수 명단을 모두 수집했다는 의미는 아니다.
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--as-of", required=True, help="공식 페이지 스냅샷 기준일 YYYY-MM-DD")
    parser.add_argument("--source", type=Path, help="원본 CSV 경로 (기본: 시즌별 파일)")
    parser.add_argument("--output", type=Path, help="최종 CSV 경로 (기본: data/pitchers/pitcher_stats_시즌.csv)")
    args = parser.parse_args()
    if args.source is None:
        args.source = ROOT / f"data/raw/pitcher_stats_source_{args.season}.csv"
    if args.output is None:
        args.output = ROOT / f"data/pitchers/pitcher_stats_{args.season}.csv"
    datetime.strptime(args.as_of, "%Y-%m-%d")
    updated_at = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    records = []
    for code in TEAM_NAMES:
        team_records = get_team(code, args.season)
        for record in team_records:
            record["as_of"] = args.as_of
            record["updated_at"] = updated_at
        records.extend(team_records)
        print(f"{code}: {len(team_records)} rows", flush=True)
    args.source.parent.mkdir(parents=True, exist_ok=True)
    with args.source.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    build(args.source, args.output, args.season, 3, args.as_of, updated_at)


if __name__ == "__main__":
    main()
