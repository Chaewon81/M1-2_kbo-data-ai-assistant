# M1-2 AI Agent 개발 프로젝트 Summary

## 최신 보완 — 배포 및 상대전적 Chat (2026-10-03)

Render/Vercel 배포 연결 확인. 화면 https://m1-2kbo-data-ai-assistant.vercel.app/ · API https://m1-2-kbo-data-ai-assistant.onrender.com. 사용자 Firestore 연결 및 실제 Chat 응답 확인, 필수 배포 캡처는 대기 중이다.

Chat에서 두 팀을 명시한 상대전적 질문은 선택 시즌의 저장된 완료 맞대결 전체를 계산해 전달·저장한다. 기아/KIA·엘지/LG 등 별칭 지원, 최근 경기 수 필터 미적용, 한 팀 관점 집계. 질문·답변·상대전적 Summary는 함께 저장되며 기존 대화는 자동 변경하지 않는다. 이전 대화 문맥 추론/투수 Chat 분석은 별도 미구현이다. 관련 회귀 14개 PASS, 이번 변경의 실제 GPT 응답은 배포 후 검증한다. 아래 내용은 개발 당시 기록과 구분한다.

## 2026-10-02 재개 작업 검토

최신 연결: 접속/새로고침 자동 갱신 백엔드·UI 구현과 모의 검증 통과. 실제 KBO 최근 7일 수집도 통과했지만 Firestore 최신 날짜 조회용 인덱스가 필요해 실제 완료 검증은 남았다. [자동 갱신 안내](AUTO_UPDATE_TEST_GUIDE.md). 아래 1340건은 초기 비교 이력이며 이후 1360/1360 재비교·현재 Summary/저장 대화 보존을 사용자에게서 확인받았다.

사용자 보고 GPT + Firestore 재시작 저장 검증 PASS. 실제 읽기 전용 DB/CSV 비교에서 2026 CSV 1,360개 대비 DB 1,340개, 09-29·09-30 완료 20개 팀 기록(10경기) 누락 확인. DB 수정·자동 갱신 구현은 아직 하지 않았다. [검토 요청용 Summary](M1-2_REVIEW_SUMMARY_2026-10-02.md), [비교 결과](data/validation/FIRESTORE_CSV_COMPARISON.json).

## 최신 구현 범위 — 2026-10-01

GPT 검증: 첫 답변의 CSV 수치 일치·Usage 542토큰을 사용자 보고로 확인했다. 2026-10-02 제출용 GPT + Firestore 대화·Summary 저장과 서버 재시작 후 같은 ID 복원을 사용자 보고로 확인했다. 답변은 저장 Summary와 일치하며, 기존 CSV/Firestore 범위 차이·증빙 캡처는 남았다. 아래 날짜별 내용은 과거 개발 이력이다. [GPT 검증 기록](data/validation/GPT_CHAT_VERIFICATION.md).

AI 최종 결정: 제출·시연은 OpenAI `gpt-4o-mini` + 필수 Firestore, 반복 개발은 Mock·CSV·메모리. OpenRouter는 검토 이력이다. 제출 실행: `.\backend\scripts\start_submission.ps1`. Firestore 실패 시 fallback 없이 시작 중단/503, 실제 Chat은 프로세스 전체 분당 10회 제한. 질문·답변·Summary는 한 문서 쓰기로 저장한다. [GPT·Firestore 검증 순서](FIRESTORE_VERIFICATION.md).

2023~2025 경기 수집을 10개 구단 전체 정규시즌으로 확장했다(각 1,440개 팀 기록). 2026은 수집 기준일까지 완료 경기 1,360개 팀 기록이다. 투수는 2023~2026 각 시즌·팀별 IP 상위 3명, 총 120개의 시즌별 기록이다.

경기·투수를 `data/games`, `data/pitchers`의 시즌별 CSV로 분리 보관하고 `DATA_PATHS`, `PITCHER_DATA_PATHS`로 조회한다. 예측은 두 투수의 해당 시즌·팀 통계가 모두 있을 때만 팀 80%·투수 20%를 적용한다. 미선택·한쪽 누락은 팀 성적만 사용한다. 과거 시즌 최종 통계는 경기별 사전 예측 검증에 사용할 수 없다.

실제 네트워크 수집과 로컬 API 검증을 완료했다. Firestore 시즌 데이터의 최신성 확인·배포는 남았다. 서버 재시작 후 저장 유지는 사용자 보고로 통과했다. 개발 실행은 `.\backend\scripts\start_local.ps1`. 상세 수집 건수·출처는 [시즌 데이터 기록](data/SEASON_DATA.md)을 참고한다. 아래 날짜별 작업·이전 범위 설명은 개발 이력이다.

## 1. 프로젝트 목표

KBO 경기 데이터를 Firestore에 저장하고, FastAPI로 분석·요약한 뒤 GPT의 Context에 주입하여 사용자의 자연어 질문에 데이터 기반으로 답하는 AI Assistant를 만든다.

장기적으로는 2026년 이후 새 시즌 데이터를 추가하여 매년 사용할 수 있는 서비스로 확장한다.

## 2. M1-1 인계 자료

M1-1 자료 위치:

```text
M1-1_summary/
```

주요 파일:

```text
M1-1_summary/collect_games.py
M1-1_summary/preprocess_games.py
M1-1_summary/analysis.py
M1-1_summary/forecast.py
M1-1_summary/data/raw/game_results_raw.csv
M1-1_summary/data/processed/game_results.csv
M1-1_summary/data/processed/season_summary.csv
M1-1_summary/data/processed/monthly_summary.csv
M1-1_summary/data/processed/rolling_win_rate.csv
M1-1_summary/data/processed/player_stats.csv
```

M1-1 현재 결과:

- 대상 팀: KIA, 삼성
- 기간: 2023~2025 KBO 정규시즌
- 원본 데이터: 968행
- 완료 경기 분석 데이터: 864행
- 시즌별·월별·최근 10경기 승률 분석 완료
- 선수 기록 분석 완료
- 2025년 기준선 예측 검증 및 2026년 기준선 예측 완료
- README, REPORT, 그래프 작성 완료

주의: M1-1의 2026년 예측 파일은 실제 2026년 경기 결과가 아니라 2023~2025년 데이터를 이용한 기준선 예측이다.

## 3. M1-2 데이터 범위 결정

### 기본 범위

- 2023~2025: 완료 시즌 데이터
- 2026: 진행 중 시즌 데이터로 별도 표시
- 2027 이후: 동일한 데이터 구조로 시즌 데이터 추가
- 대상 팀: 최종 목표는 KBO 10개 구단

M1-1의 KIA·삼성 데이터는 M1-2 1단계의 개발·검증용으로 사용한다. 10개
구단 데이터 수집은 핵심 서비스 검증이 끝난 뒤 별도 단계로 진행한다.

진행 중 시즌은 “현재까지 완료된 경기 기준”임을 화면과 AI 응답에 표시한다.

### 장기 사용을 위한 원칙

- 연도를 코드에 하드코딩하지 않는다.
- 모든 경기와 통계에 `season`을 저장한다.
- 완료·예정·취소 상태를 `status`로 구분한다.
- 새 시즌은 데이터 수집·검증·적재만으로 추가할 수 있게 구성한다.

### 2027년 이후 데이터 운영 정책

- CSV는 수집 결과·백업·검증용으로 유지한다.
- Firestore를 서비스의 기준 데이터 저장소로 사용한다.
- 새 시즌 데이터는 기존 데이터를 삭제하지 않고 Firestore에 누적한다.
- 재실행해도 중복되지 않도록 `{game_id}_{team_code}`를 문서 ID로 사용한다.
- `DATA_PATH`는 로컬 테스트나 다른 CSV를 임시로 읽을 때 사용한다.
- 운영 환경에서는 새 CSV를 교체하는 것보다 초기 적재·증분 적재 방식으로
  데이터를 추가한다.
- 새 CSV도 `date, season, team, opponent, runs_for, runs_against,
  result, game_id` 등 데이터 계약을 유지한다.
- `status`가 없는 processed CSV는 완료 데이터로 취급하고, raw CSV는
  `completed`, `scheduled`, `cancelled`, `postponed`를 명시한다.

## 4. 확정 데이터 구조

M1-2의 `data` 컬렉션 문서 1건은 경기 전체가 아니라 **특정 팀 관점의
경기 기록 1건**으로 저장한다. 기존 M1-1 CSV를 바로 적재하고 미션의
`date/value/memo` 요구사항을 함께 만족하기 위한 결정이다.

```text
id = {game_id}_{team_code}
date
season
team_code
team
opponent_code
opponent
home_away
runs_for
runs_against
run_diff
value = run_diff
result
status
stadium
game_id
memo
source_url
updated_at
```

팀명은 화면 표시용으로 사용하고, 내부 식별과 문서 ID에는 정규화된
팀 코드를 사용한다. CRUD는 팀별 경기 기록 1건을 기준으로 하며, 동일
경기의 상대 팀 기록 불일치 가능성은 검증 단계에서 확인한다.

실제 경기 원본을 별도로 정규화할 필요가 생기면 후속 단계에서 다음
구조를 추가할 수 있다.

```text
game_id
date
season
away_team
home_team
away_score
home_score
stadium
status
source_url
```

`status` 허용값은 `completed`, `scheduled`, `cancelled`, `postponed`로
정한다. `completed`가 아닌 기록은 승률·득실차·최근 경기 계산에서
제외한다. 2026 실제 경기 데이터와 M1-1의 2026 기준선 예측 데이터는
서로 다른 데이터이며 같은 통계에 섞지 않는다.

추후 투수 분석을 위해 다음 데이터를 추가할 수 있다.

```text
game_id
season
date
team
pitcher
role
is_expected_starter
era
whip
innings
strikeouts
```

## 5. M1-2 필수 기능 진행 상태

```text
M1-1 데이터 인계 확인       ✅
10개 구단 데이터 확장       ⬜
2026 진행 시즌 데이터 수집  ⬜
프로젝트 폴더 구성           🔄
FastAPI 기본 실행            ✅
Firestore 연결               ✅
Data CRUD API                ✅ (Firestore 저장 검증 완료)
Summary API                  🔄 (Firestore 데이터 재검증 필요)
Conversation API              ✅ (Firestore 생성·목록·불러오기·삭제 검증 완료)
GPT Chat API                 🔄 (구현 완료, OpenAI 키 검증 필요)
Context Injection            🔄 (구현 완료, 실제 호출 검증 필요)
프론트엔드 Chat 화면          ⬜
프론트엔드 Summary 화면       ⬜
프론트엔드 Data CRUD 화면     ⬜
프론트엔드 Conversation 화면  ⬜
Render 배포                  ⬜
Vercel 배포                  ⬜
README 및 스크린샷            ⬜
```

범례:

- ✅ 완료
- 🔄 진행 중
- ⬜ 미착수
- 🟡 선택·보너스

## 6. 선택 기능

```text
구단별 최근 경기 그래프       🟡
CSV/JSON 다운로드             🟡
간단한 승리확률 예측           🟡
`POST /api/predictions`        🟡
사용자 투수 선택            🟡
투수 통계가 있을 때 예측 반영   🟡
예상 선발 자동 수집             🟡
Dark Mode                     🟡
Function Calling / MCP        🟡
```

필수 기능을 먼저 완성한 뒤 선택 기능을 진행한다. 승부 예측은 결과를 단정하지 않고 확률과 데이터 기준 시점을 함께 표시한다.

## 7. 목표 API

```text
POST   /api/data
GET    /api/data
PUT    /api/data/{id}
DELETE /api/data/{id}
GET    /api/data/summary

POST   /api/conversations
GET    /api/conversations
GET    /api/conversations/{id}
DELETE /api/conversations/{id}

POST   /api/chat

POST   /api/predictions        # 필수 기능 완료 후 추가
```

채팅 요청은 질문과 선택적 `conversation_id`, `season`, `team`, `last_n` 등의
범위를 받을 수 있도록 설계한다. 예측 API는 백엔드가 계산한 확률과
`as_of`, `method`, `limitations`를 반환하며, GPT는 계산 결과를 설명한다.

사용자는 팀·시즌별 목록에서 투수 이름·ID를 선택할 수 있다. 양쪽 통계가
모두 있을 때 시즌 통계를 예측에 반영하며, 미선택·한쪽 누락 시 팀 성적
기준선으로 계산한다. 예상 선발 자동 수집·선발 등판별 분석은 후속 기능이다.

## 8. 기술 및 보안 원칙

- Backend: Python 3.10+, FastAPI, Pydantic, Uvicorn
- Database: Firebase Firestore
- AI: OpenAI GPT API
- Frontend: HTML, CSS, Vanilla JavaScript
- 배포: Render(Backend), Vercel(Frontend)
- API 키와 Firebase 서비스 계정 정보는 환경 변수로만 관리한다.
- `.env`, 서비스 계정 JSON, API 키는 GitHub에 올리지 않는다.
- GPT가 주입된 데이터에 없는 사실을 단정하지 않도록 시스템 프롬프트에 한계와 데이터 기준 시점을 포함한다.

## 9. 개발 순서

1. M1-1 KIA·삼성 데이터로 FastAPI·Firestore·CRUD·Chat을 먼저 검증
2. 10개 구단 수집기로 데이터 범위 확장
3. `/api/predictions` 추가
4. 사용자가 투수 이름·ID를 선택하는 기능 추가
5. 투수 통계가 있을 때만 예측에 반영
6. 예상 선발 자동 수집은 후속 단계로 진행
7. 로컬 통합 테스트
8. Render·Vercel 배포 및 CORS 확인
9. README·스크린샷·제출 체크리스트 정리

## 10. 검증 기준

- 10개 구단의 팀·시즌별 경기 수 확인
- 완료·예정·취소 경기 분리 확인
- 경기 중복 및 필수값 누락 확인
- M1-1 KIA·삼성 결과와 재집계 결과 비교
- Summary API 수치와 원본 데이터 직접 대조
- CRUD 각 API의 성공·실패 응답 확인
- Chat 응답에 실제 Summary가 반영되는지 확인
- 예측 응답에 `as_of`, 계산 방식, 제한사항이 포함되는지 확인
- 투수 통계가 없을 때 예측에서 자동 제외되는지 확인
- 데이터가 없는 시즌·팀 질문에 한계를 안내하는지 확인
- 배포 환경에서 CORS와 환경 변수 동작 확인

## 11. 작업 기록

### 2026-09-20

- M1-1 프로젝트 코드와 CSV 전체 파일을 확인했다.
- M1-1은 KIA·삼성 2023~2025 분석 결과가 완료된 상태임을 확인했다.
- M1-2 실제 구현 파일(`backend`, `frontend`)은 아직 생성되지 않은 상태임을 확인했다.
- 10개 구단 및 2026 진행 시즌 확장 방향을 결정했다.
- 장기적으로 2027년 이후에도 재사용 가능한 구조가 필요함을 확인했다.
- 본 Summary 파일을 생성했다.
- `backend/` 기본 패키지, FastAPI 진입점, requirements, 환경 변수 예시를 생성했다.
- 미션 필수 기능과 10개 구단·승부 예측 확장 기능을 분리했다.
- 팀별 경기 기록 1건 구조, `value/run_diff`, `memo` 매핑을 확정했다.
- 실제 경기 데이터와 예측 데이터를 분리하기로 했다.

## 12. 알려진 문제와 해결 기록

### CSV 0건 조회 문제 — 2026-09-20

M1-1의 `data/processed/game_results.csv`는 이미 완료 경기만 남긴
가공 CSV라 `status` 컬럼이 없다. 로더가 `status == "completed"`인
행만 읽도록 되어 있으면 864행이 모두 제외되어 `/api/data`가
`count: 0`을 반환한다.

해결: 가공 CSV에서 `status`가 없거나 빈 값이면 완료 경기로 처리하고,
원본 CSV에서 상태값이 있을 때만 완료 여부를 필터링하도록 수정했다.

검증 완료: Swagger `GET /api/data?limit=1000`에서 `count: 864`를
확인했다.

검증 완료: Swagger `POST /api/data`로 테스트 경기 1건을 추가하고
`count: 865`를 확인했다. 현재 저장소는 Firestore 연결 전이라 메모리
저장 방식이다.

검증 완료: `GET /api/data/summary?team=KIA&season=2024`에서 144경기,
87승·55패·2무, 승률 0.6127을 확인했다. M1-1 시즌 집계와 일치한다.

Firebase 프로젝트와 Cloud Firestore Standard 데이터베이스를 생성했다.

검증 완료: Firebase Admin SDK 연결 후 Firestore `data` 컬렉션에서
864건을 조회했다. 테스트 데이터 추가 후 서버를 재시작해도 데이터가
유지되어 Firestore 영구 저장을 확인했다.

검증 완료: `PUT /api/data/{id}`로 테스트 데이터의 memo를 수정하고
수정된 내용을 재조회했다.

검증 완료: `GET /api/data/summary?team=KIA&season=2024`에서 144경기,
87승·55패·2무, 승률 0.6127을 확인했다. M1-1 공식 집계와 일치한다.

### 실행 위치 — 2026-09-20

`backend.main`은 패키지 기준 import를 사용하므로 프로젝트 루트에서
다음 명령으로 실행한다.

```powershell
uvicorn backend.main:app --reload
```

`backend` 폴더 안에서 `uvicorn main:app --reload`로 실행하지 않는다.

### 문서 인코딩

문서는 UTF-8로 저장한다. PowerShell에서 한글이 깨져 보이면 파일
내용이 아니라 콘솔 인코딩 문제일 수 있다.

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp 65001
```

### 아직 구현하지 않은 기능

현재 구현은 health check, Firestore 우선 Data CRUD, Summary API,
Conversation API다. Firebase 인증이 없는 로컬 환경에서는 테스트 편의를
위해 일부 저장소가 메모리 모드로 동작한다.

다음 기능은 아직 구현 전이다.

- `POST /api/chat`
- OpenAI Context Injection

## 13. 현재 구현 상태 (2026-09-30)

- 기준선 Prediction API와 투수 통계 반영을 구현했다.
- `GET /api/pitchers`는 시즌·팀·이름·`player_id` 검색을 지원한다.
- Fancy 화면은 팀과 시즌을 기준으로 투수를 선택하고 `player_id`를 전송한다.
- 투수 통계가 모두 있으면 20% 가중하고, 없으면 팀 성적 기준으로 fallback한다.
- 예측 응답의 기준일은 `team_a`, `team_b`별로 표시한다.
- 이름과 `player_id`가 다르면 요청을 거부한다.
- 투수 데이터 범위는 2026 KBO 정규시즌 팀별 IP 상위 3명, 총 30명의 시즌 요약 통계다. `G`는 경기 출장 수다. 2026-10-01 공식 페이지 스냅샷을 수집했으며 자동 예상 선발 명단은 아니다.
- `as_of`는 공식 기록 기준일, `updated_at`은 프로젝트 반영 시각이다. `IP`의 ⅓·⅔는 각각 0.3333·0.6667로 변환했다.

## 14. 현재 다음 작업

1. Firestore 기반 Summary API와 Conversation CRUD를 Swagger로 검증
2. OpenAI 키를 설정하고 Chat API와 Context Injection 검증
3. 이후 10개 구단 데이터 수집기로 확장

작업이 끝날 때마다 이 파일의 “진행 상태”, “작업 기록”, “현재 다음 작업”을 갱신한다.

개발 과정을 시간순으로 보고 싶다면 [M1-2_DEVELOPMENT_LOG.md](M1-2_DEVELOPMENT_LOG.md)를 확인한다.
## 확장 기능 로드맵 — 기본 화면 완성 후 진행

기본 서비스 화면과 미션 필수 기능을 먼저 완성한 뒤 아래 기능을 추가한다.

1. 사용자가 경기별 예상 선발투수를 선택
2. 투수 통계가 있을 때만 기준선 예측에 반영
3. 통계가 없으면 팀 성적만으로 분석했다고 안내
4. 전날 완료 경기 자동 수집 및 Firestore 저장
5. 사이트 접속·새로고침 시 누락된 날짜만 동기화
6. `game_id` 기준 중복 저장 방지
7. 이후 예상 선발투수 자동 수집

10개 구단 수집기:
- `backend/scripts/collect_10_teams.py`에서 기존 M1-1 KBO 수집 로직을 재사용한다.
- 대상 팀은 KIA, 삼성, LG, 두산, SSG, KT, 롯데, 한화, NC, 키움이다.
- 수집 후 팀별 건수, 시즌별 건수, 중복 `game_id/team`, 팀 누락 여부를 검증한다.
- 전체 정규시즌 수집 시 완료 경기 수 144건 기준을 적용하고, 부분 기간·진행 중 시즌에는 고정 경기 수를 강제하지 않는다.
- 같은 `game_id`의 두 팀 기록이 서로 반대 팀·홈원정·득점/실점인지 검증한다.

실제 소규모 수집 검증:
- 2025년 3~5월 10개 구단 수집 성공
- `M1-1_summary/data/raw/game_results_10teams_2025_03_05.csv` 생성
- 634개 팀 관점 행, 317개 경기 ID, 10개 구단 모두 확인
- 양 팀 기록·점수·홈원정·상태 검증 통과

자동 동기화는 브라우저가 KBO 사이트를 직접 호출하지 않고 백엔드 수집기가 담당한다. 예상 선발 상태는 `unknown`, `probable`, `confirmed`, `changed`로 구분한다.

2026 실제 경기 데이터:
- `M1-1_summary/data/raw/game_results_10teams_2026.csv`로 기준선 예측 파일과 분리한다.
- 2026년 3~9월 10개 구단 일정 1,506행을 수집했다.
- 완료 경기 1,340행만 Firestore에 적재하고 예정·미완료 행은 제외한다.

승부 예측 1차:
- `POST /api/predictions` 구현
- 시즌·최근 경기 승률 기반 기준선 확률 반환
- `pitcher_a`, `pitcher_b` 입력 필드는 지원하지만 투수 통계가 연결되기 전까지 예측에는 미반영

투수 통계 연결 전 작업 순서:
1. 2026 완료 경기 1,340건의 Firestore 적재 또는 로컬 CSV 테스트 확정
2. `POST /api/predictions`의 2026 팀 비교 검증
3. 투수 통계 데이터 구조와 출처 확정
4. 투수 통계 CSV 또는 Firestore 컬렉션 생성
5. 투수 검색 API 또는 내부 조회 로직 추가
6. 통계가 있을 때만 예측에 반영
7. 통계가 없을 때 팀 성적 기준으로 fallback
8. 응답에 `as_of`, 데이터 건수, 투수 반영 여부 추가

투수 통계 저장 준비:
- `data/raw/pitcher_stats_template.csv`에 표준 컬럼을 정의했다.
- 실제 값이 없는 상태에서 임의의 투수 통계를 생성하지 않는다.
- `PITCHER_DATA_PATH` 환경변수로 실제 CSV 경로를 지정한다.
- `GET /api/pitchers` 조회 API를 추가했다. 실제 CSV가 비어 있으면 `count: 0`으로 반환한다.
- `player_id` 검색 필터와 `invalid_count`, `duplicate_count` 진단 필드를 추가했다.

PredictionRequest에 `pitcher_a_id`, `pitcher_b_id`를 추가하고, 응답에 `pitcher_stats_applied`, `pitcher_stats_as_of`, `pitcher_data_count`를 추가했다. 현재는 통계가 조회되어도 실제 확률 보정 전 단계이므로 `pitcher_stats_applied=false`로 반환한다.

## 최신 상태 (2026-10-01)

위의 투수 통계 미반영 설명은 초기 구현 기록이다. 현재는 양쪽 선택 투수 통계가 있으면 팀 성적 80% + 투수 지표 20%를 반영한다. 투수 선택은 선택 사항이며 미선택·한쪽 누락 시 기존 팀 성적 기준선 예측을 반환한다.

`collect_pitcher_stats.py`로 공식 정규시즌 팀별 IP 내림차순 첫 페이지 283행을 수집했고, `build_pitcher_stats.py`로 팀별 상위 3명, 총 30명을 생성했다. 공식 URL·ID·이닝 변환·중복·결측을 검증했으며, API 전체 30명/팀별 3명/투수 ID 조회와 예측 반영·fallback·422 오류 테스트가 통과했다. 실제 AI 연결과 배포 검증은 별도 남은 작업이다.
