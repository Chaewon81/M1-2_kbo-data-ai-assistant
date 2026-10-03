# AI 개발 공부 노트

## 자동 갱신과 인덱스 (2026-10-02)

- 자동 갱신: 기존 데이터를 먼저 보여주고 서버가 어제까지 완료 경기를 뒤에서 가져온다. GPT는 다시 호출하지 않는다. Firestore 사용량은 발생한다.
- 인덱스: DB의 검색 목차. 이번에는 `status`와 `date`를 함께 찾는 복합 인덱스가 필요하다.
- 저장된 대화 Summary는 당시 결과이고, 최신 Summary는 별도로 표시한다.
- 실제 갱신 완료 검증은 인덱스 생성 후 진행한다. [따라 하기](AUTO_UPDATE_TEST_GUIDE.md).

이 파일은 M1-2를 진행하며 새롭게 배운 내용을 짧게 정리하는 개인 학습 노트다.

## 오늘 배운 것: GPT 연결과 영구 저장은 별개

추가 학습 — 삭제 이력: 데이터를 지우면서 “사용자가 삭제했다”는 표시도 따로 남긴다. 수집기가 같은 기록을 다시 가져와도 복원하지 않기 위해서다. 이 표시를 tombstone이라고 부른다. 트랜잭션은 삭제와 이력 저장을 함께 성공하거나 함께 실패하도록 묶는 방법이다.

- `start_local.ps1`: Mock + CSV·메모리, 비용 없이 개발. 재시작하면 대화가 사라진다.
- `start_local.ps1 -AiMode gpt`: 실제 GPT지만 저장은 메모리다.
- `start_submission.ps1`: 실제 GPT + Firestore, 연결 실패 시 중단한다.
- `.env`의 `GOOGLE_APPLICATION_CREDENTIALS`: 서비스 계정 JSON의 **파일 경로**다. JSON 내용을 붙여넣는 칸이 아니다.
- 영구 저장 테스트: 질문 → 대화 ID 기록 → 서버 종료·재실행 → 같은 대화와 Summary 조회. 다시 질문할 필요는 없다.
- 503: 서버/저장소를 사용할 수 없음. 429: 요청 한도 초과 등, 잠시 기다린다.
- 새 PowerShell 창에서도 프로젝트 루트에서 실행한다. 구체적인 순서는 [GPT·Firestore 검증](FIRESTORE_VERIFICATION.md).

## 1. 가상환경(venv)

프로젝트마다 필요한 Python 패키지를 따로 관리하는 공간이다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

활성화되면 PowerShell 앞에 `(.venv)`가 표시된다.

종료:

```powershell
deactivate
```

## 2. pip와 requirements.txt

`pip`는 Python 패키지를 설치하는 도구다.

```powershell
python -m pip install -r backend\requirements.txt
```

`requirements.txt`에는 프로젝트에 필요한 패키지 목록을 적는다.

## 3. FastAPI

Python으로 API 서버를 만드는 framework다. API는 프론트엔드가 백엔드에 데이터를 요청하는 통로다.

```text
GET /api/data       데이터 조회
POST /api/chat      AI 질문 전송
```

## 4. Uvicorn

FastAPI 서버를 실행하는 프로그램이다. 내 컴퓨터에서 테스트할 때 사용한다.

```powershell
uvicorn backend.main:app --reload
```

실행 주소:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

`/docs`에서는 Swagger API 테스트 화면을 볼 수 있다.

## 5. 배포 도구 역할

```text
Uvicorn  : 내 컴퓨터에서 FastAPI 실행
Render   : FastAPI 백엔드 인터넷 배포
Vercel   : HTML/CSS/JavaScript 프론트엔드 배포
```

이번 프로젝트의 연결:

```text
브라우저 → Vercel Frontend → Render FastAPI → Firestore/OpenAI
```

## 6. Firestore

Firebase에서 제공하는 클라우드 데이터베이스다.

```text
data            경기 데이터
conversations   대화 기록
```

## 6-1. Firebase와 Firestore의 차이

```text
Firebase  : 앱 개발에 필요한 여러 기능을 제공하는 Google 플랫폼
Firestore : Firebase 안에 포함된 클라우드 NoSQL 데이터베이스
```

Firebase에는 인증, 파일 저장, 호스팅, 분석 등 여러 기능이 있고,
Firestore는 그중 데이터를 저장하고 조회하는 기능이다.

이번 프로젝트의 구조:

```text
Firebase 프로젝트
└─ Cloud Firestore
   ├─ data            경기 데이터
   └─ conversations   AI 대화 기록
```

Firestore는 표 형태의 SQL 데이터베이스와 달리 컬렉션과 문서로
데이터를 저장한다.

```text
컬렉션(collection) → 문서(document) → 필드(field)
```

예:

```text
data → 20250902HTHH0_KIA → team, date, result, run_diff
```

이번 프로젝트에서는 FastAPI가 Firebase Admin SDK를 이용해 Firestore에
접근한다. 프론트엔드가 Firestore 키를 직접 가지지 않도록 한다.

## 7. GPT Context Injection

데이터 Summary를 GPT의 시스템 프롬프트에 넣어 데이터 기반 답변을 하게 하는 방식이다.

```text
Firestore 데이터
→ Summary API
→ 시스템 프롬프트에 삽입
→ GPT 답변
```

## 8. 환경 변수

API 키나 서비스 계정 정보를 코드에 직접 쓰지 않고 별도로 관리한다.

```text
OPENAI_API_KEY
FIREBASE_SERVICE_ACCOUNT_JSON
ALLOWED_ORIGINS
API_BASE_URL
```

`.env`와 인증 파일은 GitHub에 올리지 않는다.

## 9. 현재 프로젝트 개발 순서

```text
M1-1 CSV 확인
→ FastAPI 실행
→ Firestore 연결
→ CRUD
→ Summary API
→ Conversation API
→ Chat + Context Injection
→ Frontend
→ Render/Vercel 배포
```

## 10. 새로 배운 내용 기록 형식

```text
### 날짜 — 개념

한 줄 설명:

이번 프로젝트에서 어디에 사용하는가:

기억할 명령어 또는 예시:
```

## 11. OpenAI API 키와 크레딧

- API 키는 [OpenAI API keys](https://platform.openai.com/api-keys)에서 만든다.
- ChatGPT 구독과 API 사용 크레딧은 별도다.
- 키가 있어도 API 크레딧이 없으면 `429 insufficient_quota`가 발생한다.
- 키는 코드나 GitHub에 직접 적지 않고 `OPENAI_API_KEY` 환경변수로 사용한다.
- 개발 중에는 `OPENAI_MOCK_MODE=true`로 비용 없이 Chat 흐름을 확인할 수 있다.

## 12. 다음에 Chat 테스트하는 순서

### 1) 서버 실행

프로젝트 루트에서 실행한다.

```powershell
.\.venv\Scripts\Activate.ps1
$env:OPENAI_MOCK_MODE="true"
uvicorn backend.main:app --reload
```

`OPENAI_MOCK_MODE=true`는 실제 OpenAI 호출 없이 테스트하는 설정이다.

### 2) Firestore 연결 확인

브라우저에서 다음 주소를 연다.

```text
http://127.0.0.1:8000/api/firebase/status
```

다음처럼 나오면 연결 성공이다.

```json
{"connected": true, "database": "firestore"}
```

### 3) Swagger에서 Chat 실행

1. `http://127.0.0.1:8000/docs` 접속
2. `POST /api/chat` 선택
3. **Try it out** 클릭
4. 아래 JSON 입력

```json
{
  "message": "KIA의 최근 경기 흐름을 알려줘",
  "team": "KIA",
  "season": 2024,
  "last_n": 5
}
```

5. **Execute** 클릭

성공하면 응답에 다음 항목이 포함된다.

- `answer`: 개발용 Mock 답변
- `conversation_id`: 자동 생성된 대화 ID
- `summary`: 질문 조건에 맞는 경기 요약
- `model`: `mock`

### 4) 대화 저장 확인

Swagger에서 `GET /api/conversations`를 실행한다. 방금 만든 대화가 목록에 있으면 Chat 결과가 Firestore에 저장된 것이다.

실제 GPT를 사용할 때는 서버를 다시 시작하면서 다음처럼 설정한다.

```powershell
$env:OPENAI_MOCK_MODE="false"
$env:OPENAI_API_KEY="발급받은_API_키"
uvicorn backend.main:app --reload
```

단, API 크레딧이 없으면 `429 insufficient_quota`가 발생하므로 먼저 Mock 모드로 전체 흐름을 확인한다.

## 13. 프론트엔드 실행과 테스트

현재 실행 스크립트는 2023~2026 경기·투수 CSV를 함께 읽고 Mock 모드로 실행한다. 가상환경이 이미 준비되어 있다면 활성화 명령을 따로 실행할 필요가 없다. 기존 백엔드는 먼저 `Ctrl + C`로 종료한다.

PowerShell 창 2개를 사용한다. 백엔드가 이미 켜져 있으면 그대로 두고, 새 PowerShell 창에서 프론트엔드만 실행하면 된다.

```powershell
# PowerShell 1 — 프로젝트 루트
cd "D:\AI\Codyssey\project\M1_AI응용\M1-2_"
.\backend\scripts\start_local.ps1

# PowerShell 2 — frontend 폴더
cd "D:\AI\Codyssey\project\M1_AI응용\M1-2_\frontend"
python -m http.server 5500
```

브라우저에서 `http://127.0.0.1:5500`을 연다.

- `8000/docs`: Swagger API 테스트 화면 / `5500`: 사용자가 보는 서비스 화면
- 서버를 실행한 두 창은 사용 중에 계속 열어둔다. 종료는 각 창에서 `Ctrl + C`.
- 폴더 목록만 나오면 실행 위치가 잘못된 것이다. `frontend` 폴더에서 서버를 실행한다.
- `Failed to fetch`가 나오면 백엔드가 켜져 있는지 `http://127.0.0.1:8000/health`에서 확인한다.
- 이전 화면이 보이면 `Ctrl + F5`로 새로고침한다.
- `DATA_PATHS`는 여러 CSV를 함께 읽는 설정이다. 세미콜론(`;`)으로 구분하며 `DATA_PATH`보다 우선한다. Firestore 연결 시에는 Firestore에 해당 시즌 경기 데이터가 있어야 한다.

확인 순서:

1. Chat 질문을 보내고 Summary 카드가 바뀌는지 확인
2. 왼쪽 최근 대화에 새 대화가 나타나는지 확인
3. 경기 데이터 관리에서 테스트 기록을 추가
4. 목록에 새 기록이 나타나는지 확인
5. 필요하면 삭제 버튼으로 테스트 기록 삭제

Swagger(`/docs`)는 API 개발자 테스트용이고, `frontend/index.html`은 사용자가 보는 서비스 화면이다.

## 14. 저장된 대화 불러오기 테스트

1. 프론트엔드에서 질문을 한 번 보낸다.
2. 왼쪽 `최근 대화` 목록에 항목이 생기는지 확인한다.
3. 대화 항목을 클릭한다.
4. 이전 질문과 Mock 답변이 화면에 다시 나타나면 성공이다.

대화 목록은 Firestore에서 가져오고, 클릭한 대화의 메시지는 `GET /api/conversations/{id}`로 조회한다.

경기 데이터 표의 `수정` 버튼은 득점·실점·메모·상태를 `PUT /api/data/{id}`로 저장한다. 득점이나 실점이 바뀌면 백엔드가 득실차·승패·`value`를 자동으로 다시 계산한다. 상태는 `completed`, `scheduled`, `cancelled`, `postponed` 중 하나를 입력한다.

데이터 표의 출처 배지는 원본 KBO 수집 기록과 사용자가 추가·수정한 기록을 구분한다. 사용자가 추가한 기록은 `is_manual=true`, 기존 수집 기록은 `is_manual=false`로 관리한다.

API의 각 경기 응답에는 Firestore 문서 ID인 `id`가 포함된다. `scheduled`, `cancelled`, `postponed` 상태는 아직 점수와 결과가 없을 수 있으므로 점수 필드가 `null`이어도 허용한다. `completed`일 때는 점수와 결과가 필수다.

## 15. 이후 추가할 확장 기능

기본 화면을 완성한 뒤 다음 순서로 확장한다.

- 사용자가 경기의 예상 선발투수 선택
- 투수 통계가 있을 때만 예측에 반영
- 전날 완료 경기만 자동 수집
- 새로고침 시 마지막 수집일 이후 데이터만 동기화
- `game_id`로 중복 저장 방지
- 나중에 예상 선발투수 자동 수집

이 기능들은 현재 필수 기능이 아니므로 기본 Chat·Summary·CRUD·대화 기능을 먼저 안정화한다.

## 16. 10개 구단 수집기

기존 M1-1 수집기를 재사용하는 별도 스크립트다.

```powershell
.\.venv\Scripts\Activate.ps1
python backend\scripts\collect_10_teams.py --years 2025 --months 3 4 5
```

스크립트는 수집 후 팀별 건수, 완료 경기 수, 시즌별 건수, 중복 기록, 누락 구단을 확인한다. 검증이 실패하면 CSV를 저장하지 않는다.

전체 정규시즌을 수집할 때는 완료 경기 144건 기준을 검사하지만, 3~5월처럼 일부 기간을 수집할 때는 144건을 강제하지 않는다. 같은 `game_id`의 양 팀 기록이 서로 반대 팀·홈원정·득점/실점인지도 검사한다.

2025년 3~5월 실제 테스트 결과는 634행(317경기), 10개 구단 모두 포함으로 검증되었다. KBO 응답에 `game_id`가 없는 경기에는 양 팀이 공유하는 날짜·팀 조합 임시 키를 사용한다.

2026년 실제 경기 결과는 `game_results_10teams_2026.csv`에 따로 저장한다. 2026년 3~9월 수집 결과는 1,506행이며, 완료 경기 1,340행만 Firestore에 적재한다. 2026 기준선 예측 CSV와 섞지 않는다.

## 17. 오늘 작업 마무리 메모

- Firestore에서 `429 Quota exceeded`가 발생하면 CSV 모드로 테스트한다.
- CSV 모드 실행:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = $null
$env:DATA_PATH = "M1-1_summary/data/raw/game_results_10teams_2026.csv"
$env:OPENAI_MOCK_MODE = "true"
uvicorn backend.main:app --reload
```

- 프론트엔드 `Failed to fetch`는 백엔드 `http://127.0.0.1:8000/health`가 열리는지 먼저 확인한다.
- API 주소에서 JSON이 보이는 것은 정상이며, 사용자 화면은 `http://127.0.0.1:5500`이다.

## 18. 투수 선택과 player_id

- 화면에서 팀·시즌을 선택하면 해당 팀 투수 목록을 조회한다.
- 투수를 선택하면 이름은 표시용, `player_id`는 실제 조회용으로 사용한다.
- 이름과 ID가 일치하지 않으면 백엔드가 요청을 거부한다.
- 투수 통계가 양쪽 모두 있으면 팀 성적 80%와 투수 지표 20%를 조합한다.
- 통계가 없으면 기존 팀 성적 기준선으로 fallback한다.
- `pitcher_stats_as_of`는 팀별 기준일을 따로 표시한다.

## 19. OpenAI Chat 연결 확인

- 프로젝트 루트에 `.env` 파일을 만들고 `OPENAI_API_KEY`를 저장한다.
- `OPENAI_MOCK_MODE=false`로 설정하면 실제 OpenAI API를 호출한다.
- 환경변수는 서버 시작 시 읽으므로 `.env`를 수정한 뒤 uvicorn을 재시작한다.
- API 키가 없으면 연결 설정 오류, 크레딧이 없으면 429 quota 오류가 발생한다.
- API 키는 프론트엔드에 넣지 않고 백엔드 환경변수로만 관리한다.

## 20. 기준선 승부 예측 API

Swagger의 `POST /api/predictions`에서 두 팀의 최근 경기 승률을 비교할 수 있다.

```json
{
  "team_a": "KIA",
  "team_b": "LG",
  "season": 2026,
  "last_n": 10,
  "pitcher_a": "",
  "pitcher_b": ""
}
```

현재 확률은 과거 경기 기반 기준선이다. 양쪽 선택 투수의 시즌 통계가 있으면 20% 반영하고, 미선택·한쪽 누락 시 팀 성적으로 계산한다.

프론트엔드의 `오늘의 기준선 승부 예측` 영역에서 두 팀과 최근 경기 수를 정하고, 투수 이름은 선택 사항으로 고른다.

투수 통계 조회 API는 다음과 같다.

```text
GET /api/pitchers?season=2026&team=KIA&name=투수이름
```

선수 ID를 알고 있으면 이름보다 안전하게 검색할 수 있다.

```text
GET /api/pitchers?season=2026&player_id=12345
```

응답의 `invalid_count`, `duplicate_count`로 CSV에 잘못된 행이나 중복 행이 있었는지 확인한다.

예측 요청에는 투수 이름과 함께 `pitcher_a_id`, `pitcher_b_id`를 보낼 수 있다. 응답의 `pitcher_stats_applied`, `pitcher_stats_as_of`, `pitcher_data_count`로 실제 통계 사용 여부를 확인한다. 현재는 양쪽 투수 통계가 있을 때 확률 보정에 반영한다.

현재 실제 투수 CSV가 비어 있으면 `{ "count": 0, "items": [] }`를 반환한다. 임의의 통계로 예측하지 않는 안전한 fallback이다.

투수 통계는 바로 예측에 섞지 않고, 먼저 2026 데이터 저장·예측 검증을 끝낸다. 이후 통계가 존재할 때만 반영하고, 없으면 팀 성적 기준으로 fallback한다.

### 2026-10-01: 투수 데이터 수집과 확인

현재는 공식 KBO 정규시즌 기록에서 팀별 이닝 상위 3명, 총 30명을 연결했다. 위의 '조회 준비만 완료' 설명은 과거 기록이다.

- 전체 확인: `http://127.0.0.1:8000/api/pitchers?season=2026` → `count: 30`
- 팀별 확인: `http://127.0.0.1:8000/api/pitchers?season=2026&team=KIA` → `count: 3`
- 투수는 선택 사항이다. 양쪽 모두 선택하면 시즌 통계를 반영하고, 선택하지 않으면 팀 성적으로 예측한다.
- `as_of`는 공식 페이지를 확인한 날짜, `updated_at`은 CSV를 생성한 시각이다.

다시 수집하는 명령(프로젝트 루트 PowerShell, 날짜는 수집일에 맞춰 변경):

```powershell
python backend\scripts\collect_pitcher_stats.py --season 2026 --as-of 2026-10-01
```

파일 반영 후 백엔드를 재시작하고 프론트엔드를 `Ctrl + F5`로 새로고침한다. 2026 시즌과 팀을 선택하면 투수 후보 3명이 표시된다.

### 여러 시즌 파일을 분리해서 함께 조회하기

2023~2025 과거 시즌과 2026 현재 시즌 파일은 따로 보관하되, `DATA_PATHS`로 함께 읽는다. 한 파일만 지정하면 다른 시즌은 조회되지 않는다. 파일 간 중복 경기는 `game_id + team`으로 한 번만 저장하고, 뒤에 지정한 파일의 기록이 우선한다. 실제 결과만 사용하며 forecast 파일은 넣지 않는다.

위 설명은 초기 통합 방식이다. 2026-10-01 현재는 2023~2025 모두 10개 팀 전체 정규시즌을 확보했고, 2026 완료 기록과 함께 `data/games`의 시즌별 CSV로 조회한다. 기존 파일은 이력용으로 보존하며 새 파일과 합치지 않는다.

### 현재 시즌별 조회 확인 방법

### 실제 AI 켜는 법 — OpenAI GPT (최종 결정)

첫 테스트 결과: KIA·2026·최근 10경기 GPT 답변이 CSV와 일치했다. 5승 5패·50%, 평균 득실차 0.7, 최근 5경기 40%로 하락. 다음은 저장된 대화를 다시 눌러 답변·Summary가 남는지 확인한다. 아래 미검증 안내는 연결 전 상태다. 자세한 증빙 범위는 `data/validation/GPT_CHAT_VERIFICATION.md`에 기록했다.

과제 요구에 맞춰 GPT-4o mini를 직접 사용한다. 개발 테스트는 Mock이다. OpenRouter는 무료 대안으로 검토했지만 최종 제출 경로는 아니다. 실제 GPT 응답 검증은 키·크레딧 준비 후 해야 하며 아직 완료가 아니다.

크레딧 충전은 본인이 직접 하고 자동 충전은 꺼둔다. OpenAI Usage에서 실제 비용을 확인한다. API 비용은 ChatGPT 구독과 별도다. 설정만 등록했다고 실제 GPT 연결에 성공한 것은 아니다. [GPT 연결 순서](GPT_SETUP.md).

1. OpenAI Billing에서 크레딧을 준비하고 `https://platform.openai.com/api-keys`에서 API 키를 준비한다. 기존 키가 유효하면 그대로 사용한다. 키는 채팅에 보내지 않는다.
2. 프로젝트 루트의 `.env`에 아래를 적는다. 이 파일은 Git에 올리지 않는다.

```env
AI_PROVIDER=openai
OPENAI_API_KEY=본인_키로_교체
OPENAI_MODEL=gpt-4o-mini
OPENAI_MOCK_MODE=false
```

3. 기존 백엔드는 `Ctrl + C`, 다시 실행은 `.\backend\scripts\start_local.ps1 -AiMode gpt`.
4. 프론트엔드 `Ctrl + F5` → KIA·2026·최근 10경기 → '최근 경기 흐름을 Summary 숫자로 설명해줘.'
5. 답변 후 '실제 AI 응답' 표시, Summary 숫자 일치, 대화 저장·다시 열기를 확인한다.

`/api/chat/status`에서 `provider: openai`, `model: gpt-4o-mini`, `configured: true`를 확인한다. 키가 있다는 뜻이지 연결 성공이라는 뜻은 아니다. 실제 질문이 성공해야 연결 확인이다. `429`는 요청 한도/크레딧/할당량, `504`는 대기 시간 초과다. 기본 명령 `.\backend\scripts\start_local.ps1`은 계속 Mock이다. 두 실행 모두 로컬 CSV·메모리 저장이라 재시작하면 수정·대화가 사라진다.

과거 OpenRouter 키 한도 검토는 `AI_PROVIDER_AND_MISSION.md`의 이력 메모로 보존한다. 현재 설정/제출 안내로 사용하지 않는다.

### 시즌별 조회 메모

데이터 검증은 '형식·중복 검사'와 'KBO 공식 기록 대조'가 다르다. 오류 개수 0만으로 공식 기록과 같다고 말할 수 없다. `python -m backend.scripts.audit_kbo_data --official`로 공식 집계·투수 지표를 대조하고 `data/validation`에 결과와 당시 HTML을 남긴다. 쉬운 결과 설명은 `data/validation/KBO_VALIDATION_REPORT.md`를 본다.

`start_local.ps1`은 경기용 `DATA_PATHS`와 투수용 `PITCHER_DATA_PATHS`를 각각 연결한다. 2023~2026 투수 기록은 시즌마다 30개, 전체 120개다. 같은 선수가 여러 시즌에 있으면 별도 기록이다.

Swagger에서 `GET /api/pitchers`에 `season=2025`, `team=KIA`를 넣으면 `count: 3`이다. `GET /api/data/summary`에 같은 조건을 넣고 `last_n`은 비우면 `count: 144`이다. 화면에서도 2025·KIA를 선택하면 투수 목록 3명이 나와야 한다.

투수는 안 골라도 예측할 수 있다. 양쪽의 해당 시즌·팀 통계가 모두 있으면 팀 80% + 투수 20%, 한쪽만 있으면 팀 성적만 사용한다. 과거 시즌 최종 성적에는 당시 경기 이후 정보도 있어, 그 경기 전에 했을 예측의 정확도를 검증하는 데 사용하면 안 된다.

## 배포 플랫폼: Render와 Vercel

- Render는 FastAPI 백엔드 서버를 인터넷에 올려 실행한다. 이 프로젝트에서는 GPT 호출과 Firestore 연결을 담당한다.
- Vercel은 HTML·CSS·JavaScript 프론트엔드를 웹 페이지로 제공한다.
- 프론트엔드는 Vercel 주소로 열고, 필요한 API 요청은 Render 백엔드 주소로 보낸다.
- Render 무료 서버는 15분 동안 요청이 없으면 잠들 수 있다. 다음 요청이 오면 자동으로 깨어나며 첫 접속은 약 1분 걸릴 수 있다. 사용자가 서버를 직접 깨우지는 않는다.
- API 주소는 프론트엔드 공개 설정으로 연결하고, OpenAI 키·Firestore 서비스 계정·시연 접근 키는 백엔드(Render)에만 둔다.
