# GPT + Firestore 제출용 검증

2026-10-02 사용자 실행·보고 기준으로 **서버 재시작 후 같은 대화·Summary 유지 PASS**. GPT 답변 수치도 저장 Summary와 일치한다. CSV·Firestore 재대조는 각각 1,360건, 누락·추가·필드 차이 0이다. 스크린샷 확보는 별도 남은 작업이다. [실행 기록](data/validation/GPT_CHAT_VERIFICATION.md). 아래는 재현용 절차다.

## 1. 준비

프로젝트 루트 `.env`에서 다음 항목을 확인한다. 기존 키는 유지하고 파일 전체를 덮어쓰지 않는다.

```env
AI_PROVIDER=openai
OPENAI_API_KEY=본인_키
OPENAI_MODEL=gpt-4o-mini
GOOGLE_APPLICATION_CREDENTIALS=D:/본인폴더/서비스계정.json
LOCAL_CSV_MODE=false
REQUIRE_FIRESTORE=true
OPENAI_MOCK_MODE=false
CHAT_REQUESTS_PER_MINUTE=10
```

경로는 실제 서비스 계정 JSON 위치로 바꾼다. 키·JSON 내용은 화면 캡처나 Git에 올리지 않는다. 개발 실행 후 같은 PowerShell 창에 남은 환경변수가 `.env`보다 우선할 수 있으므로 새 창에서 실행하는 것이 쉽다.

## 2. 제출용 서버 실행

이제 제출용 실행은 접속 시 경기 자동 갱신도 활성화한다. 저장·복원만 확인하려면 `start_submission.ps1 -DisableAutoSync`를 사용한다. 실제 자동 갱신은 [인덱스 생성 안내](AUTO_UPDATE_TEST_GUIDE.md)를 먼저 따른다.

기존 서버에서 `Ctrl + C`, 새 PowerShell에서 프로젝트 루트로 이동한 뒤 실행한다.

```powershell
.\backend\scripts\start_submission.ps1
```

- 개발: `start_local.ps1` → Mock + CSV·메모리. 재시작하면 수정·대화가 사라짐.
- GPT만 시험: `start_local.ps1 -AiMode gpt` → 실제 GPT + CSV·메모리. 영구 저장 검증 아님.
- 제출 검증: `start_submission.ps1` → 실제 GPT + 필수 Firestore. 연결 실패 시 시작 중단, 요청 중 장애는 503. 메모리 fallback 없음.
- 투수 통계는 이 모드에서도 시즌별 CSV에서 읽는다. 경기·대화는 Firestore에서 읽고 저장한다.

`/api/firebase/status`의 `connected: true`와 `/api/chat/status`의 `mode: real`, `provider: openai`, `storage_policy: firestore_required`를 확인한다. 상태 확인만으로 GPT 호출·저장 완료가 증명되지는 않는다.

## 3. 경기 데이터 확인·필요할 때만 적재

Swagger에서 `/api/data/summary?team=KIA&season=2026`을 먼저 조회한다. quota 오류가 있으면 반복 조회·적재를 멈추고 Firebase 콘솔 할당량을 확인한다.

새 시즌 데이터가 없을 때만 아래 명령으로 **시즌별로** 적재한다. 실행 전 기존 자료를 백업한다. 삭제 이력·수동 수정 표시가 있는 문서는 제외하고, 나머지 동일 ID는 CSV 값으로 갱신할 수 있다. 다른 ID의 오래된 중복·테스트 행은 자동 삭제하지 않는다. `DATA_PATHS`는 자동 순회하지 않으므로 `--input`을 명시한다.

```powershell
$env:LOCAL_CSV_MODE = 'false'
python -m backend.scripts.import_to_firestore --input data/games/game_results_2023.csv
python -m backend.scripts.import_to_firestore --input data/games/game_results_2024.csv
python -m backend.scripts.import_to_firestore --input data/games/game_results_2025.csv
python -m backend.scripts.import_to_firestore --input data/games/game_results_2026.csv
```

현재 파일 기준 완료 팀 기록은 각각 1440 / 1440 / 1440 / 1360건이다. 2026은 재수집하면 달라진다. 한 경기의 양 팀 기록이므로 실제 경기 수는 절반이다. 기존 DB에 다른 자료가 있으면 총건수는 이 합계와 다를 수 있다.

## 4. 영구 저장 확인 — 실제 GPT 질문은 한 번만

1. 프론트엔드에서 **새 대화** → KIA·2026·최근 10경기 → 질문 전송.
2. GPT 답변과 Summary를 확인하고 대화 ID를 기록한다. Swagger의 `GET /api/conversations`에서 ID를 찾을 수 있다.
3. `GET /api/conversations/{id}`에서 user·assistant 메시지와 `summary`를 확인한다.
4. 백엔드 `Ctrl + C` → 같은 `start_submission.ps1`로 다시 실행한다.
5. 같은 ID를 조회하고 화면 대화를 다시 연다. 기존 답변·Summary가 그대로이면 영구 저장 PASS. 새 질문은 보내지 않아도 된다.
6. 모델 화면·Usage(키 숨김)·재시작 전후 대화 화면을 캡처하고 검증 기록에 날짜·결과를 남긴다.

저장 실패 시 Chat은 503을 반환한다. GPT 호출 후 저장에 실패하면 GPT 비용은 이미 발생했을 수 있으므로 무조건 재전송하지 않는다. 한 번의 문서 쓰기로 메시지 2개와 Summary를 저장하지만, 동시 요청의 덮어쓰기 방지를 위한 Firestore 트랜잭션은 아직 없다.

## 요청 제한과 남은 배포 과제

실제 AI Chat은 서버 프로세스 전체 **1분당 10회** 제한(변경 가능), 초과 시 429·Retry-After를 반환한다. Mock은 제외한다. 재시작하면 제한이 초기화되며 여러 worker 사이에 공유되지 않는다. 비용 상한이나 사용자 인증을 대신하지 않는다.

공개 배포 전에는 인증·대화 접근 권한·CRUD 보호, 배포 도메인 CORS, Render/Vercel API URL 설정이 필요하다. 현재 Chat Context는 선택한 한 팀 Summary와 이번 질문이며 이전 메시지·투수·두 팀 예측 결과를 자동 전달하지 않는다.
