"""월별 승률의 단순 기준선 예측을 만들고 결과를 시각화한다.

이 스크립트는 복잡한 AI 모델이 아니라, 과거 같은 달의 승·패를 합산한
승률을 미래의 기준선 예측값으로 사용한다.
"""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DATA_DIR = Path("data/processed")
IMAGE_DIR = Path("images")
TEAMS = ("KIA", "삼성")
MONTHS = tuple(range(3, 11))
COLORS = {"KIA": "#E62E2E", "삼성": "#1F5AA6", "예측": "#5F6368"}


def get_font(size: int, bold: bool = False):
    paths = [Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf")]
    paths.append(Path("C:/Windows/Fonts/gulim.ttc"))
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def read_monthly_rows() -> list[dict[str, str]]:
    with (DATA_DIR / "monthly_summary.csv").open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def rate(wins: int, losses: int) -> float:
    return wins / (wins + losses) if wins + losses else 0.0


def baseline(rows: list[dict[str, str]], team: str, month: int, seasons: set[int]) -> float:
    selected = [
        row
        for row in rows
        if row["team"] == team and int(row["month"]) == month and int(row["season"]) in seasons
    ]
    wins = sum(int(row["wins"]) for row in selected)
    losses = sum(int(row["losses"]) for row in selected)
    return rate(wins, losses)


def write_csv(filename: str, columns: list[str], rows: list[dict[str, str]]) -> None:
    with (DATA_DIR / filename).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def make_2025_evaluation(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    actual = {(row["team"], int(row["month"])): row for row in rows if int(row["season"]) == 2025}
    output: list[dict[str, str]] = []
    for team in TEAMS:
        for month in MONTHS:
            row = actual.get((team, month))
            if row is None:
                continue
            prediction = baseline(rows, team, month, {2023, 2024})
            actual_rate = float(row["win_rate"])
            output.append(
                {
                    "team": team,
                    "month": str(month),
                    "training_period": "2023-2024",
                    "predicted_win_rate": f"{prediction:.3f}",
                    "actual_win_rate": f"{actual_rate:.3f}",
                    "abs_error": f"{abs(prediction - actual_rate):.3f}",
                    "actual_games": row["games"],
                }
            )
    write_csv(
        "monthly_forecast_evaluation.csv",
        ["team", "month", "training_period", "predicted_win_rate", "actual_win_rate", "abs_error", "actual_games"],
        output,
    )
    return output


def make_2026_forecast(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    monthly: list[dict[str, str]] = []
    season: list[dict[str, str]] = []
    for team in TEAMS:
        for month in MONTHS:
            monthly.append(
                {
                    "team": team,
                    "month": str(month),
                    "training_period": "2023-2025",
                    "predicted_win_rate": f"{baseline(rows, team, month, {2023, 2024, 2025}):.3f}",
                }
            )
        team_rows = [row for row in rows if row["team"] == team and int(row["season"]) in {2023, 2024, 2025}]
        wins = sum(int(row["wins"]) for row in team_rows)
        losses = sum(int(row["losses"]) for row in team_rows)
        prediction = rate(wins, losses)
        season.append(
            {
                "team": team,
                "training_period": "2023-2025",
                "historical_wins": str(wins),
                "historical_losses": str(losses),
                "predicted_2026_win_rate": f"{prediction:.3f}",
                "reference": "3개 시즌 전체 승/패 합산 승률",
            }
        )
    write_csv("monthly_2026_forecast.csv", ["team", "month", "training_period", "predicted_win_rate"], monthly)
    write_csv(
        "season_2026_forecast.csv",
        ["team", "training_period", "historical_wins", "historical_losses", "predicted_2026_win_rate", "reference"],
        season,
    )
    return monthly, season


def center(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font, fill="#202124") -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((x - (box[2] - box[0]) / 2, y), text, font=font, fill=fill)


def grid(draw: ImageDraw.ImageDraw, left: int, top: int, right: int, bottom: int) -> None:
    for index in range(6):
        value = index / 5
        y = bottom - (bottom - top) * value
        draw.line((left, y, right, y), fill="#D9DEE5")
        label = f"{value:.0%}"
        box = draw.textbbox((0, 0), label, font=get_font(14))
        draw.text((left - 12 - (box[2] - box[0]), y - 9), label, font=get_font(14), fill="#5F6368")


def draw_evaluation(evaluation: list[dict[str, str]]) -> None:
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    center(draw, 600, 22, "기준선 예측 검증: 2023~2024년으로 2025년 월별 승률 예측", get_font(27, True))
    draw.text((850, 80), "실제", font=get_font(16), fill="#202124")
    draw.line((800, 90, 840, 90), fill="#202124", width=4)
    draw.text((1005, 80), "예측", font=get_font(16), fill="#202124")
    draw.line((955, 90, 995, 90), fill=COLORS["예측"], width=3)
    for index, team in enumerate(TEAMS):
        panel_left, panel_right = 35 + index * 580, 600 + index * 580
        center(draw, (panel_left + panel_right) / 2, 115, f"{team}", get_font(21, True), COLORS[team])
        left, top, right, bottom = panel_left + 65, 165, panel_right - 25, 545
        grid(draw, left, top, right, bottom)
        x_values = [left + (right - left) * i / 7 for i in range(8)]
        team_rows = {int(row["month"]): row for row in evaluation if row["team"] == team}
        actual_points, predicted_points = [], []
        for x, month in zip(x_values, MONTHS):
            row = team_rows.get(month)
            if row is None:
                continue
            actual_points.append((x, bottom - (bottom - top) * float(row["actual_win_rate"])))
            predicted_points.append((x, bottom - (bottom - top) * float(row["predicted_win_rate"])))
            center(draw, x, bottom + 15, f"{month:02}", get_font(14), "#5F6368")
        if len(actual_points) >= 2:
            draw.line(actual_points, fill=COLORS[team], width=4)
            draw.line(predicted_points, fill=COLORS["예측"], width=3)
        for x, y in actual_points:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=COLORS[team])
        for x, y in predicted_points:
            draw.rectangle((x - 4, y - 4, x + 4, y + 4), fill=COLORS["예측"])
    image.save(IMAGE_DIR / "05_baseline_2025_evaluation.png")


def draw_2026_forecast(monthly: list[dict[str, str]], season: list[dict[str, str]]) -> None:
    image = Image.new("RGB", (1200, 650), "white")
    draw = ImageDraw.Draw(image)
    center(draw, 600, 22, "2026년 기준선 승률 예측 (2023~2025년 데이터 기반)", get_font(28, True))
    left, top, right, bottom = 100, 125, 760, 545
    grid(draw, left, top, right, bottom)
    x_values = [left + (right - left) * i / 7 for i in range(8)]
    for team in TEAMS:
        values = {int(row["month"]): float(row["predicted_win_rate"]) for row in monthly if row["team"] == team}
        points = [(x, bottom - (bottom - top) * values[month]) for x, month in zip(x_values, MONTHS)]
        draw.line(points, fill=COLORS[team], width=4)
        for x, y in points:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=COLORS[team])
        for x, month in zip(x_values, MONTHS):
            center(draw, x, bottom + 15, f"{month:02}", get_font(14), "#5F6368")
    draw.rectangle((835, 155, 1140, 455), outline="#D9DEE5", width=2)
    center(draw, 987, 180, "시즌 예상 승률", get_font(22, True))
    for index, row in enumerate(season):
        y = 245 + index * 105
        prediction = float(row["predicted_2026_win_rate"])
        draw.text((860, y), row["team"], font=get_font(20, True), fill=COLORS[row["team"]])
        draw.rectangle((860, y + 37, 1090, y + 65), fill="#E8EAED")
        draw.rectangle((860, y + 37, 860 + 230 * prediction, y + 65), fill=COLORS[row["team"]])
        draw.text((1015, y), f"{prediction:.3f}", font=get_font(20, True), fill="#202124")
    center(draw, 600, 595, "주의: 과거 승률 평균을 사용한 비교 기준선이며 실제 2026년 성적을 보장하지 않습니다.", get_font(16), "#5F6368")
    image.save(IMAGE_DIR / "06_2026_baseline_forecast.png")


def main() -> None:
    IMAGE_DIR.mkdir(exist_ok=True)
    rows = read_monthly_rows()
    evaluation = make_2025_evaluation(rows)
    monthly, season = make_2026_forecast(rows)
    draw_evaluation(evaluation)
    draw_2026_forecast(monthly, season)
    for team in TEAMS:
        errors = [float(row["abs_error"]) for row in evaluation if row["team"] == team]
        print(f"{team} 2025 월별 예측 MAE: {sum(errors) / len(errors):.3f}")
    print("2026 기준선 예측과 그래프를 저장했습니다.")


if __name__ == "__main__":
    main()
