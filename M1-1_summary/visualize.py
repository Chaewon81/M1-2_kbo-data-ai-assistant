"""분석 결과 CSV를 과제용 PNG 그래프로 만드는 스크립트입니다."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DATA_DIR = Path("data/processed")
IMAGE_DIR = Path("images")
FONT_PATHS = (
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/gulim.ttc"),
)
BOLD_FONT_PATHS = (
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    *FONT_PATHS,
)
TEAM_COLORS = {"KIA": "#E62E2E", "삼성": "#1F5AA6"}
TEXT = "#202124"
GRID = "#D9DEE5"


def get_font(size: int, bold: bool = False):
    """Windows 한글 글꼴을 우선 사용하고, 없으면 기본 글꼴을 사용한다."""
    paths = BOLD_FONT_PATHS if bold else FONT_PATHS
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def read_csv(filename: str) -> list[dict[str, str]]:
    # utf-8-sig는 CSV 첫 칸에 붙을 수 있는 BOM 표시를 함께 처리한다.
    with (DATA_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def center_text(draw: ImageDraw.ImageDraw, x: float, y: float, value: str, font, fill=TEXT):
    box = draw.textbbox((0, 0), value, font=font)
    draw.text((x - (box[2] - box[0]) / 2, y), value, font=font, fill=fill)


def y_label(value: float, maximum: float, percent: bool) -> str:
    if percent:
        return f"{value:.0%}"
    if maximum <= 2:
        return f"{value:.2f}"
    return f"{value:.0f}"


def draw_y_grid(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    right: int,
    bottom: int,
    maximum: float,
    percent: bool = False,
) -> None:
    small = get_font(15)
    for step in range(6):
        value = maximum * step / 5
        y = bottom - (bottom - top) * step / 5
        draw.line((left, y, right, y), fill=GRID, width=1)
        label = y_label(value, maximum, percent)
        box = draw.textbbox((0, 0), label, font=small)
        draw.text((left - 12 - (box[2] - box[0]), y - 10), label, font=small, fill="#5F6368")


def draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    font = get_font(17)
    for index, team in enumerate(("KIA", "삼성")):
        position = x + index * 105
        draw.rectangle((position, y, position + 18, y + 18), fill=TEAM_COLORS[team])
        draw.text((position + 25, y - 2), team, font=font, fill=TEXT)


def save_yearly_win_rate(rows: list[dict[str, str]]) -> None:
    image = Image.new("RGB", (1000, 650), "white")
    draw = ImageDraw.Draw(image)
    title_font, label_font, value_font = get_font(30, True), get_font(18), get_font(16, True)
    center_text(draw, 500, 28, "연도별 승률 비교", title_font)
    draw_legend(draw, 735, 77)

    left, top, right, bottom = 105, 130, 930, 550
    draw_y_grid(draw, left, top, right, bottom, 0.7, percent=True)
    years = [2023, 2024, 2025]
    values = {(int(row["season"]), row["team"]): float(row["win_rate"]) for row in rows}
    group_width = (right - left) / len(years)
    bar_width = 58
    for index, season in enumerate(years):
        center = left + group_width * (index + 0.5)
        for team_index, team in enumerate(("KIA", "삼성")):
            rate = values[(season, team)]
            x1 = center + (team_index - 0.5) * (bar_width + 12) - bar_width / 2
            x2 = x1 + bar_width
            y = bottom - (bottom - top) * rate / 0.7
            draw.rectangle((x1, y, x2, bottom), fill=TEAM_COLORS[team])
            center_text(draw, (x1 + x2) / 2, y - 28, f"{rate:.3f}", value_font, TEAM_COLORS[team])
        center_text(draw, center, bottom + 20, str(season), label_font)
    image.save(IMAGE_DIR / "01_yearly_win_rate.png")


def draw_line_panel(
    draw: ImageDraw.ImageDraw,
    area: tuple[int, int, int, int],
    title: str,
    x_labels: list[str],
    team_values: dict[str, list[float | None]],
    maximum: float,
    percent: bool = False,
) -> None:
    panel_left, panel_top, panel_right, panel_bottom = area
    title_font, label_font = get_font(20, True), get_font(15)
    center_text(draw, (panel_left + panel_right) / 2, panel_top, title, title_font)
    left, top, right, bottom = panel_left + 62, panel_top + 48, panel_right - 20, panel_bottom - 48
    draw_y_grid(draw, left, top, right, bottom, maximum, percent)
    points_x = [left + (right - left) * index / (len(x_labels) - 1) for index in range(len(x_labels))]
    for x, label in zip(points_x, x_labels):
        center_text(draw, x, bottom + 15, label, label_font, "#5F6368")
    for team in ("KIA", "삼성"):
        segment: list[tuple[float, float]] = []
        for x, value in zip(points_x, team_values[team]):
            if value is None:
                if len(segment) >= 2:
                    draw.line(segment, fill=TEAM_COLORS[team], width=4)
                segment = []
                continue
            point = (x, bottom - (bottom - top) * value / maximum)
            segment.append(point)
            draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=TEAM_COLORS[team])
        if len(segment) >= 2:
            draw.line(segment, fill=TEAM_COLORS[team], width=4)


def save_monthly_win_rate(rows: list[dict[str, str]]) -> None:
    image = Image.new("RGB", (1500, 620), "white")
    draw = ImageDraw.Draw(image)
    center_text(draw, 750, 22, "월별 승률 흐름", get_font(30, True))
    draw_legend(draw, 1190, 75)
    months = list(range(3, 11))
    for index, season in enumerate((2023, 2024, 2025)):
        values = {team: [] for team in ("KIA", "삼성")}
        for team in values:
            by_month = {
                int(row["month"]): float(row["win_rate"])
                for row in rows
                if int(row["season"]) == season and row["team"] == team
            }
            values[team] = [by_month.get(month) for month in months]
        draw_line_panel(
            draw,
            (20 + index * 495, 105, 495 + index * 495, 590),
            f"{season}년",
            [f"{month:02}" for month in months],
            values,
            1.0,
            percent=True,
        )
    image.save(IMAGE_DIR / "02_monthly_win_rate.png")


def save_player_trend(rows: list[dict[str, str]], rate: bool) -> None:
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    title = "주요 선수 비율 지표 변화" if rate else "주요 선수 누적 지표 변화"
    center_text(draw, 600, 22, title, get_font(30, True))
    draw_legend(draw, 905, 75)
    if rate:
        panels = (("타율 (AVG)", "avg", 0.4), ("OPS", "ops", 1.1))
        output = "03_player_rate_trend.png"
    else:
        panels = (("홈런 (HR)", "hr", 45), ("타점 (RBI)", "rbi", 120))
        output = "04_player_count_trend.png"
    for index, (title, column, maximum) in enumerate(panels):
        values = {team: [] for team in ("KIA", "삼성")}
        for team in values:
            by_season = {int(row["season"]): float(row[column]) for row in rows if row["team"] == team}
            values[team] = [by_season[season] for season in (2023, 2024, 2025)]
        draw_line_panel(
            draw,
            (35 + index * 580, 105, 600 + index * 580, 590),
            title,
            ["2023", "2024", "2025"],
            values,
            maximum,
        )
    image.save(IMAGE_DIR / output)


def main() -> None:
    IMAGE_DIR.mkdir(exist_ok=True)
    save_yearly_win_rate(read_csv("season_summary.csv"))
    save_monthly_win_rate(read_csv("monthly_summary.csv"))
    player_rows = read_csv("player_stats.csv")
    save_player_trend(player_rows, rate=True)
    save_player_trend(player_rows, rate=False)
    print("그래프 4개를 images 폴더에 저장했습니다.")


if __name__ == "__main__":
    main()
