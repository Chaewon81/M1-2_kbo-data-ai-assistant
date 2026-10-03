# KBO Data AI Assistant

KBO 경기 데이터를 기반으로 팀 경기력 Summary, 대화형 Chat, 기준선 승부 예측, 사용자가 선택한 투수의 시즌 통계를 제공하는 M1-2 프로젝트입니다.

## 현재 기능

GPT 검증: 사용자 보고로 실제 답변·Usage 542토큰 및 서버 재시작 후 Firestore 대화·Summary 유지를 확인했습니다. **2026-10-02 자동 갱신 전** CSV/Firestore 비교는 각각 1,360개 팀 기록, 누락·추가·비교 필드 차이 0이었습니다. 이후 DB 자동 갱신과는 구분하며 현재 DB 건수로 단정하지 않습니다. 모델·Usage 캡처는 별도 제출 증빙입니다. [검증 결과](data/validation/GPT_CHAT_VERIFICATION.md).

최종 AI는 과제 요구에 맞춰 OpenAI `gpt-4o-mini`를 직접 사용합니다. 반복 개발은 Mock, 제출 검증은 GPT + 필수 Firestore를 사용합니다. OpenRouter는 검토했던 무료 대안입니다. [AI 제공업체·과제 정합성](AI_PROVIDER_AND_MISSION.md), [GPT·Firestore 검증 순서](FIRESTORE_VERIFICATION.md).

- 10개 구단 경기 데이터 조회·추가·수정·삭제
- 삭제/수동 수정 보호: Firestore `data_deletions`와 현재 문서를 트랜잭션에서 확인한다. 일반 추가 충돌은 409, 삭제된 기록 수정은 404, 적재는 삭제·수동 기록을 제외한다. 누락 보충·자동 갱신은 양 팀을 함께 보호한다. 실제 경합 검증은 남았다.
- 접속·새로고침 자동 갱신 구현. 2026-10-03 사용자 화면 확인 기준 실제 갱신 성공·현재 Summary 반영·즉시 재새로고침 시 성공 시각 유지·저장 대화 Summary 보존 확인. 실제 보호 경합·실패 통합 검증은 남았다. [검증 안내](AUTO_UPDATE_TEST_GUIDE.md).
- 일반 수정(PUT)은 `is_manual=true`를 서버에서 강제한다. false/null을 보내도 보호를 해제하지 않으며 관리자 보호 해제 기능은 아직 없다.
- 시즌·팀·최근 경기 수 Summary
- Chat API와 대화 저장·불러오기
- 팀 성적 기반 기준선 승부 예측
- 사용자 선택 투수의 시즌 통계 및 `player_id` 기반 조회
- 양쪽 투수 통계가 있으면 20% 가중, 없으면 팀 성적 기준 fallback
- OpenAI Mock 모드
- OpenAI GPT 직접 연결 (사용자 보고 실제 응답 확인), OpenRouter 대안 검토 이력 보존

## 로컬 실행

기술 스택: Python/FastAPI·Pydantic, Firebase Admin/Firestore, OpenAI SDK, Vanilla HTML/CSS/JavaScript. 배포 대상은 Render 백엔드와 Vercel 정적 프론트엔드입니다.

실제 배포 URL: **아직 미확보**. 프론트엔드 URL·백엔드 URL·Swagger URL은 배포 검증 후 등록하며 로컬 주소나 예시 주소를 제출 URL로 사용하지 않습니다. [배포·제출 체크리스트](DEPLOYMENT_SUBMISSION_GUIDE.md).

배포용 최소 설정: Render `APP_ENV=production`, `DEMO_ACCESS_KEY`(24자 이상), `OPENAI_API_KEY`, `AI_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o-mini`, `OPENAI_MOCK_MODE=false`, `GOOGLE_APPLICATION_CREDENTIALS`, `LOCAL_CSV_MODE=false`, `REQUIRE_FIRESTORE=true`, `ALLOWED_ORIGINS`(실제 Vercel HTTPS 주소), `AUTO_SYNC_ENABLED=true`. Vercel에는 공개 값 `API_BASE_URL`(실제 Render HTTPS 주소)만 등록합니다. 빌드가 공개 `config.js`를 생성하며 API 키·서비스 계정·시연 키를 넣지 않습니다.

공개 배포 API는 `X-Demo-Key`를 서버에서 검사합니다. 시연 접근 키는 평가자에게 별도로 전달하고 화면 상단에서 입력합니다. Swagger는 Authorize로 입력합니다. 이 공유 키는 회원별 접근 권한이나 GPT 비용 상한을 대신하지 않습니다. 로컬 기본 설정은 기존처럼 접근 키 없이 동작합니다.

프로젝트 루트에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
.\backend\scripts\start_local.ps1
```

Swagger 문서: `http://127.0.0.1:8000/docs`

프론트엔드:

```powershell
cd frontend
python -m http.server 5500
```

화면: `http://127.0.0.1:5500`

## AI 연결 설정

### Mock 모드

API 비용 없이 Chat 흐름을 테스트할 때 사용합니다.

```env
OPENAI_MOCK_MODE=true
```

### OpenAI GPT — 최종 제출·시연 경로

```env
AI_PROVIDER=openai
OPENAI_API_KEY=본인_API_키
OPENAI_MODEL=gpt-4o-mini
OPENAI_MOCK_MODE=false
```

OpenAI API는 API 키와 사용 가능한 크레딧이 필요합니다. 키는 프론트엔드에 넣지 말고 백엔드 환경변수로만 관리합니다.

프로젝트 루트 `.env`에 위 설정을 등록한 후 기존 서버를 `Ctrl + C`로 종료하고 실행합니다.

```powershell
.\backend\scripts\start_local.ps1 -AiMode gpt
```

이 옵션은 GPT + 로컬 CSV·메모리 테스트입니다. 인자 없는 실행은 Mock입니다. **제출용 영구 저장 검증**은 `.\backend\scripts\start_submission.ps1`로 실행합니다. `GOOGLE_APPLICATION_CREDENTIALS`에 서비스 계정 JSON 경로가 필요하며, Firestore 실패 시 시작 중단 또는 503을 반환하고 메모리로 전환하지 않습니다. 시즌별 `--input` 적재·재시작 검증 순서는 [FIRESTORE_VERIFICATION.md](FIRESTORE_VERIFICATION.md)를 참고합니다. 실제 Chat은 프로세스 전체 분당 10회 제한이며 인증·비용 상한을 대신하지 않습니다.

### 과거 대안 검토 — OpenRouter (제출 경로 아님)

OpenAI SDK 호환 방식으로 무료 모델을 사용할 수 있습니다.

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=본인_OpenRouter_키
OPENROUTER_MODEL=openrouter/free
OPENAI_MOCK_MODE=false
```

OpenRouter 무료 플랜은 무료 모델과 API 접근을 제공하지만 요청 제한과 모델별 가용성 변동이 있습니다. 현재 무료 모델과 제한은 [OpenRouter 요금표](https://openrouter.ai/pricing)와 [무료 모델 목록](https://openrouter.ai/collections/free-models/)에서 확인합니다.

`.env`를 수정한 뒤에는 서버를 재시작해야 합니다.

### 과거 OpenRouter 테스트 안내 — 현재는 GPT_SETUP.md 사용

프로젝트 루트의 `.env`에 위 OpenRouter 설정을 넣습니다. API 키는 [OpenRouter 키 관리](https://openrouter.ai/settings/keys)에서 발급하며 채팅·프론트엔드·Git에 넣지 않습니다.

```powershell
# 실행 중인 백엔드에서 Ctrl + C 후, 프로젝트 루트에서:
.\backend\scripts\start_local.ps1 -AiMode configured
```

인자 없이 실행하면 기존 Mock 모드입니다. `-AiMode configured`는 실제 AI를 호출하지만 저장소는 여전히 로컬 CSV·메모리입니다. `.env`에 `AI_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL=openrouter/free`를 설정해야 합니다.

`GET /api/chat/status`에서 `mode: real`, `configured: true`를 확인합니다. 이것은 설정 존재 확인이지 실제 연결 성공 증명이 아닙니다. 화면에서 KIA·2026·최근 10경기를 선택하고 질문을 보내 실제 답변·Summary·대화 저장을 확인합니다. 응답 `model`이 `mock`이 아니고 화면에 '실제 AI 응답'이 표시되어야 합니다. 실제 응답의 숫자가 Summary와 일치하는지도 확인합니다.

AI 요청은 45초 타임아웃·자동 재시도 0회·최대 출력 500토큰입니다. 무료 요청 한도와 크레딧 오류를 구분해 안내하며, AI 요청 실패 시 새 빈 대화를 만들지 않습니다. 무료 모델 가용성·한도 때문에 실패할 수 있습니다. 현재 Chat Context는 팀 Summary이며 투수 통계·예측 결과 및 이전 메시지 전달은 후속 작업입니다.

## 데이터 경로

```env
DATA_PATHS=data/games/game_results_2023.csv;data/games/game_results_2024.csv;data/games/game_results_2025.csv;data/games/game_results_2026.csv
PITCHER_DATA_PATHS=data/pitchers/pitcher_stats_2023.csv;data/pitchers/pitcher_stats_2024.csv;data/pitchers/pitcher_stats_2025.csv;data/pitchers/pitcher_stats_2026.csv
LOCAL_CSV_MODE=true
```

`start_local.ps1`은 시즌별 파일을 자동 연결하고 로컬 CSV·Mock 모드로 실행합니다. 기존 서버는 먼저 `Ctrl + C`로 종료합니다. Firestore 모드로 전환할 때는 `LOCAL_CSV_MODE=false`로 바꾸고 서비스 계정 경로를 설정합니다. 로컬 CRUD·대화는 서버 메모리에만 저장됩니다.

## 주요 API

- `GET /api/data`
- `GET /api/data/summary`
- `POST /api/chat`
- `GET /api/conversations`
- `POST /api/predictions`
- `GET /api/pitchers`
- `GET /api/firebase/status`

### 투수 통계 확장

여러 시즌 경기 CSV는 파일을 분리 보관하고 `DATA_PATHS`에 세미콜론으로 경로를 연결하여 함께 읽습니다. `DATA_PATHS`가 설정되면 단일 파일용 `DATA_PATH`보다 우선합니다. 같은 `game_id/team`은 1건만 유지하며 뒤의 파일이 우선합니다. 예시는 `backend/.env.example`에 있습니다. 이 설정은 로컬 CSV 모드용이며 Firestore 연결 시에는 시즌별 별도 적재가 필요합니다.

2023~2025는 10개 구단 전체 정규시즌을 확보했습니다(각 1,440개 팀 기록 = 720경기, 팀별 144개). 2026은 2026-10-01 수집 시점의 완료 경기 1,360개 팀 기록 = 680경기입니다. 시즌별 `data/games/game_results_YYYY.csv`로 보관하며 기존 M1-1 파일은 검증 이력으로 보존하고 새 파일과 합치지 않습니다.

실제 KBO 네트워크 수집과 로컬 API 테스트를 별도로 수행했습니다. 경기 공식 ID·양 팀 기록·더블헤더 유지, 40개 시즌·팀 조합 조회, 투수 반영·fallback·이름/ID 불일치 422를 검증했습니다. 상세 범위는 [시즌 데이터 기록](data/SEASON_DATA.md)에 있습니다.

`data/pitchers/pitcher_stats_YYYY.csv`에는 2023~2026 각 시즌·팀별 IP 상위 3명씩 총 120개의 **시즌별 기록**이 있습니다(고유 선수 120명이 아님). `PITCHER_DATA_PATHS`로 복수 파일을 읽고, 기존 단일 `PITCHER_DATA_PATH`도 지원합니다. 선택한 두 투수의 해당 시즌·해당 팀 통계가 모두 있을 때만 팀 성적 80% + 투수 지표 20%를 적용합니다. 미선택·한쪽 누락이면 팀 성적만 사용합니다.

공식 기록을 다시 수집하고 최종 CSV를 생성하려면 프로젝트 루트에서 실행합니다. 기준일은 실제 수집한 공식 페이지 스냅샷 날짜에 맞춥니다.

```powershell
python backend\scripts\collect_pitcher_stats.py --season 2026 --as-of 2026-10-01
```

수집된 원본으로 선정만 다시 실행하려면:

```powershell
python backend\scripts\build_pitcher_stats.py `
  --input data\raw\pitcher_stats_source_2026.csv `
  --output data\pitchers\pitcher_stats_2026.csv `
  --season 2026 --top-n 3 --as-of 2026-10-01
```

스크립트는 IP 기준 내림차순으로 팀별 3명을 선택하며, 동률은 `player_id` 문자열 오름차순으로 처리합니다. IP 0 제외, 팀 코드 통일, 숫자·필수값·중복·팀별 인원을 검증합니다. `⅓`와 `⅔`는 각각 `0.3333`, `0.6667`로 변환합니다. 수집기는 팀별 IP 내림차순 첫 페이지(최대 30명)를 저장하므로 원본은 전체 투수 명단을 의미하지 않습니다. `as_of`는 공식 페이지 스냅샷 날짜이며, 사이트의 경기 반영 지연까지 보장하지 않습니다. `updated_at`은 실제 CSV 생성 시각입니다.

## 주의사항

- 승부 예측은 과거 데이터 기반 기준선이며 실제 결과를 보장하지 않습니다.
- 과거 시즌 최종 통계는 시즌 비교용입니다. 경기 이후 정보가 포함되므로 경기별 사전 예측 검증에는 사용할 수 없습니다. 그런 검증에는 해당 경기 이전 통계가 필요합니다.
- 선택한 투수 통계가 없는 경우 예측에는 투수 지표가 반영되지 않습니다.
- 현재 투수 데이터는 팀별 이닝 상위 3명의 정규시즌 요약이며, 실제 예상 선발 자동 수집이나 선발 등판별 분석은 지원하지 않습니다.
- OpenRouter는 무료 대안으로 검토했지만 최종 제출 경로는 OpenAI GPT입니다. OpenRouter 무료 모델을 GPT 사용 증빙으로 표시하지 않습니다.
- 실제 배포 시 API 키는 Render 등 백엔드 환경변수에만 등록합니다.

## 개발 기록

공식 기록 대조 결과와 미확인 범위: [KBO 데이터 검증 보고서](data/validation/KBO_VALIDATION_REPORT.md).

- [M1-2_PROJECT_SUMMARY.md](M1-2_PROJECT_SUMMARY.md)
- [M1-2_DEVELOPMENT_LOG.md](M1-2_DEVELOPMENT_LOG.md)
- [M1-2_CURRENT_STATUS.md](M1-2_CURRENT_STATUS.md)
- [M1-2_MISSION_ANSWERS.md](M1-2_MISSION_ANSWERS.md)
- [AI_Study.md](AI_Study.md)
