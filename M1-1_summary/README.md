# KIA 타이거즈 vs 삼성 라이온즈 성적 트렌드 분석

KBO 공식 데이터를 사용해 KIA 타이거즈와 삼성 라이온즈의 2023~2025년 정규시즌 성적을 비교한 Python 프로젝트입니다. 시즌·월별 승률, 최근 10경기 승률, 구자욱·김도영의 시즌별 타격 기록을 분석합니다.

- GitHub 저장소: <https://github.com/Chaewon81/M1-1_baseball_analysis>

## 분석 질문

1. 두 팀의 시즌 성적은 2023~2025년에 어떻게 변했는가?
2. 월별 승률은 어떤 흐름을 보이는가?
3. 구자욱과 김도영의 주요 타격 지표는 어떻게 변했는가?

## 결과 요약

- KIA 승률: 0.514(2023) → 0.613(2024) → 0.464(2025)
- 삼성 승률: 0.427(2023) → 0.549(2024) → 0.521(2025)
- 두 선수 모두 2024년에 세 시즌 중 가장 높은 AVG·HR·RBI·OPS를 기록했다.
- 자세한 근거·해석·한계점은 [REPORT.md](REPORT.md)에서 확인할 수 있다.

## 프로젝트 구조

```text
data/
├── raw/game_results_raw.csv          # 수집 원본 (완료·미완료 일정 포함)
└── processed/
    ├── game_results.csv              # 완료 경기 분석 데이터
    ├── season_summary.csv            # 시즌별 팀 집계
    ├── monthly_summary.csv           # 월별 팀 집계
    ├── rolling_win_rate.csv          # 최근 10경기 승률
    └── player_stats.csv              # 주요 선수 시즌 기록
images/                               # 생성한 그래프 4개
collect_games.py                      # 경기 데이터 수집
preprocess_games.py                   # 완료 경기만 전처리
analysis.py                           # 팀 성적 집계·검증
visualize.py                          # PNG 그래프 생성
```

## 실행 환경 및 설치

Python 3.14에서 작성·실행했다. 그래프 생성에는 Pillow를 사용한다.

```powershell
python -m pip install -r requirements.txt
```

## 실행 순서

아래 명령은 프로젝트 최상위 폴더에서 순서대로 실행한다.

```powershell
# 1. 2023~2025년 KIA·삼성 정규시즌 경기 수집
python collect_games.py --all-seasons

# 2. 완료 경기만 분석용 CSV로 변환
python preprocess_games.py

# 3. 시즌별·월별·최근 10경기 승률 집계
python analysis.py

# 4. 그래프 4개 생성
python visualize.py

# 5. 보너스: 기준선 예측 검증과 2026년 예측
python forecast.py
```

`collect_games.py`만 간단히 확인하고 싶다면 기본 명령인 `python collect_games.py`를 실행하면 2025년 4월 데이터만 수집한다.

## 생성 결과

- `images/01_yearly_win_rate.png`: 시즌별 승률 비교
- `images/02_monthly_win_rate.png`: 월별 승률 흐름 (경기가 없는 달은 빈 구간)
- `images/03_player_rate_trend.png`: AVG와 OPS 변화
- `images/04_player_count_trend.png`: HR과 RBI 변화
- `images/05_baseline_2025_evaluation.png`: 2023~2024년으로 만든 2025년 월별 승률 예측과 실제값 비교
- `images/06_2026_baseline_forecast.png`: 2023~2025년 데이터를 이용한 2026년 기준선 승률 예측

## 데이터 검증 기준

- 수집 결과의 시즌별 144경기와 승·패·무를 KBO 공식 역대 구단성적과 비교했다.
- 2025년 4월 표본 경기와 큰 점수 차 경기 표본을 KBO 경기센터와 대조했다.
- 분석 CSV에서 팀-경기 조합 중복 및 필수 값 누락이 없는지 확인했다.
- 선수 기록은 KBO 공식 선수 기록을 사용했으며, OPS는 출루율과 장타율의 합으로 계산했다.

## 데이터 출처

- [KBO 공식 경기일정 및 경기센터](https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx)
- [KBO 공식 역대 구단성적](https://www.koreabaseball.com/Record/History/Team/Record.aspx)
- [구자욱 공식 선수 기록](https://www.koreabaseball.com/Record/Player/HitterDetail/Total.aspx?playerId=62404)
- [김도영 공식 선수 기록](https://www.koreabaseball.com/Record/Player/HitterDetail/Total.aspx?playerId=52605)

## 데이터 이용 및 라이선스 유의사항

이 프로젝트의 경기·선수 기록은 교육용 분석을 위해 KBO 공식 웹페이지에서 수집·정리했다. 원본 데이터의 권리와 이용 조건은 KBO에 있을 수 있으므로, 데이터를 재배포하거나 상업적으로 이용하기 전에는 KBO의 최신 이용 조건을 별도로 확인해야 한다. 보고서와 결과물에는 항상 KBO 출처를 표시한다.

## 해석 시 주의점

이 프로젝트는 두 팀과 두 명의 타자를 대상으로 한 비교 분석이다. 월별 경기 수의 차이, 김도영의 2025년 30경기 기록, 팀 성적과 개인 성적 사이의 인과관계를 단정할 수 없다는 점을 고려해야 한다.

보너스 예측은 과거 같은 달의 승률을 활용한 단순 기준선이다. 2026년 실제 기록이나 선수·일정·부상 같은 외부 변수는 사용하지 않았으므로, 실제 성적을 보장하거나 단정하는 예측이 아니다.
