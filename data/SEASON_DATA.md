# 시즌별 데이터 수집·검증 기록

2026-10-01 실제 KBO 네트워크 수집 결과. 경기와 투수는 별도 시즌 CSV로 보관한다.

| 시즌 | 경기 팀 기록 | 실제 경기 | 투수 원본 행 | 선정 시즌 기록 |
|---|---:|---:|---:|---:|
| 2023 | 1,440 | 720 | 279 | 30 |
| 2024 | 1,440 | 720 | 287 | 30 |
| 2025 | 1,440 | 720 | 277 | 30 |
| 2026 | 1,360 | 680 | 283 | 30 |

경기는 [KBO 일정](https://www.koreabaseball.com/Schedule/Schedule.aspx)의 정규시즌 자료다. 2023~2025는 팀마다 완료 경기 144개를 검증했고, 2026은 수집 기준일까지 완료된 경기만 포함했다. 예정·취소 및 forecast는 분석 파일에 포함하지 않는다.

- 경기: `games/game_results_YYYY.csv`
- 투수: `pitchers/pitcher_stats_YYYY.csv`
- 투수 수집 원본: `raw/pitcher_stats_source_YYYY.csv`

투수는 [KBO 투수 기록](https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx)에서 시즌·정규시즌·팀·IP 내림차순 조건을 적용한 첫 페이지(팀별 최대 30행)를 수집했다. 전체 명단 수집은 아니며, 여기서 IP 0 제외 후 팀별 IP 상위 3명을 선정했다. 동률은 `player_id` 문자열 오름차순이다. 120개는 고유 선수 수가 아니라 시즌별 기록 수다.

팀 필터는 공식 페이지 표시 팀을 따른다. 이적 선수 통계가 해당 팀 재적 기간만의 분할 기록임을 보장하지 않으므로, 팀별 등판 분석으로 해석하지 않는다. 은퇴 선수의 공식 기록 URL도 허용하되 URL의 선수 ID와 행의 ID를 검증한다. 과거 시즌 재현에는 시즌 조건이 저장된 원본 CSV를 사용한다.

매핑: `G → games_appeared`, `IP → innings`, `ER → earned_runs`, `ERA → era`, `WHIP → whip`, `SO → strikeouts`. IP의 ⅓·⅔는 0.3333·0.6667로 변환한다. G는 선발 등판 수가 아니다.

`as_of=2026-10-01`은 공식 페이지 확인 날짜다. 공식 사이트의 경기 반영 지연까지 보장하지 않는다. `updated_at`은 실제 CSV 생성 시각이다. 과거 시즌은 최종 통계이므로 경기별 사전 예측 검증에 사용하면 미래 정보가 포함된다. 시즌 비교에는 사용할 수 있으나 사전 검증에는 경기 이전 기록이 필요하다.

## 검증 범위

실제 네트워크 수집과 로컬 TestClient 검증을 구분했다. 로컬에서는 40개 시즌·팀 조합 조회, 투수 120개·오류/중복 0, 경기 공식 ID·양 팀 기록·더블헤더 유지, 시즌별 투수 반영·미선택/한쪽 누락 fallback·이름/ID 불일치 422를 확인했다. 실제 브라우저·Firestore 신규 적재·배포 검증은 별도다.

기존 M1-1 및 부분 기간 파일은 보존하지만 새 서비스 파일과 합치지 않는다. 공식 ID와 임시 ID가 서로 다른 동일 경기의 중복을 피하기 위함이다.

```powershell
python -m unittest backend.scripts.test_season_data -v
python backend/scripts/collect_10_teams.py --years 2023 2024 2025 2026 --completed-only --as-of 2026-10-01 --split-seasons --output data/games
python backend/scripts/collect_pitcher_stats.py --season 2026 --as-of 2026-10-01
```

재수집할 때는 `--as-of`를 실제 확인 날짜로 바꾼다. 수집만으로 Firestore에 적재되지는 않는다.
