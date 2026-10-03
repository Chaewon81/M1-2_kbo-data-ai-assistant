# M1-2 AI Agent 개발 — Project Summary

## 자동 갱신 현재 상태 (2026-10-03)

접속·새로고침 시 `/api/sync`로 한국 시간 어제까지의 완료 경기를 백그라운드 갱신한다. 최근 7일 중첩 조회·현재 시즌 주기적 전체 대조, Firestore 공유 lease, 경기별 트랜잭션으로 중복 실행·삭제·수동 수정 보호를 적용한다. 저장된 대화 Summary는 유지하고 최신 Summary는 별도로 조회한다. GPT 자동 재호출과 투수 CSV 자동 갱신은 하지 않는다.

색인 생성·읽기 전용 미리보기·첫 실제 갱신 success를 확인했다. 사용자 화면 기준 현재 Summary 갱신·저장 대화 Summary 유지·즉시 새로고침 시 성공 시각 유지도 확인했다. 별도 테스트 프로젝트 첫 실행은 앞 3개 PASS 후 동시 수정/삭제 Aborted로 실패했으며, 보완 후 실제 재실행은 대기 중이다. [검증 안내](AUTO_UPDATE_TEST_GUIDE.md), [격리 테스트](ISOLATED_FIRESTORE_TEST_GUIDE.md).

### 제출 배포 설정·접근 보호

프론트엔드는 Vercel의 공개 `API_BASE_URL`을 빌드 단계에서 `config.js`로 반영한다. 백엔드 비밀 키는 포함하지 않는다. Render production 모드는 긴 시연 접근 키·필수 Firestore·명시적 HTTPS CORS 주소를 요구한다. 모든 `/api` 라우터는 서버에서 `X-Demo-Key`를 검사하며, 화면 입력/Swagger Authorize로 평가자가 접속한다. 공유 시연 키는 회원별 권한·비용 상한이 아니다. 실제 배포·최종 화면 캡처는 아직 대기다.

## AI 요구사항·대체 사용 구분 (2026-10-01)

미션 원문에 맞춰 최종 AI는 OpenAI `gpt-4o-mini` 직접 사용으로 확정한다. Mock은 개발 테스트, OpenRouter는 대안 검토 이력이다. 사용자 보고로 실제 GPT 응답 및 2026-10-02 서버 재시작 후 Firestore 대화·Summary 유지까지 확인했다. 이전 호출 Usage 542토큰과 이번 복원 검증을 구분한다. 모델·Usage 캡처 및 최신성 보완은 남았다. [오늘 검토 Summary](M1-2_REVIEW_SUMMARY_2026-10-02.md), [제출 검증 절차](FIRESTORE_VERIFICATION.md).

### 제출 실행·저장소 정책

개발은 `start_local.ps1`(Mock·CSV·메모리), 제출 검증은 `start_submission.ps1`(GPT·Firestore 필수)로 구분한다. `REQUIRE_FIRESTORE=true`에서는 시작 시 DB 조회 실패 시 중단하고, 요청 중 저장소 장애는 503을 반환한다. 메모리 fallback은 개발 모드에서만 허용한다. 질문·답변·Summary는 한 대화 문서 쓰기로 저장하며, 서버 재시작 후 복원까지 확인해야 통합 완료로 표시한다. 경기 적재는 시즌별 `--input`을 지정하며 투수 통계는 시즌별 CSV 조회를 유지한다.

실제 Chat은 `CHAT_REQUESTS_PER_MINUTE`(기본 10)로 프로세스 전체 분당 요청을 제한한다. Mock은 제외, 초과 시 429이다. 다중 worker 공유·사용자 인증·영구 비용 상한은 지원하지 않으므로 공개 배포 전 별도 보호가 필요하다.

## 1. 과제명

**M1-2 AI Agent 개발: 나만의 AI 비서 구축**

---

## 2. 과제 핵심 목표

시계열 데이터를 데이터베이스에 저장하고 분석한 뒤,
그 분석 결과를 GPT의 시스템 프롬프트에 주입하여
**내 데이터를 이해하고 답변하는 AI 웹서비스**를 만드는 것이 목표다.

단순한 ChatGPT 웹페이지가 아니라 아래 흐름을 구현해야 한다.

```text
시계열 데이터
    ↓
Firestore 저장
    ↓
FastAPI 분석 / 요약
    ↓
데이터 Summary 생성
    ↓
GPT System Prompt에 Context Injection
    ↓
사용자 질문
    ↓
데이터 기반 AI 답변
```

---

# 3. 현재 프로젝트 방향

## 주제

### KBO 10개 구단 데이터 분석 AI 비서

M1-1에서 분석한 야구 데이터를 기반으로 M1-2에서는 분석 범위를 확장하여
사용자가 KBO 구단 데이터에 대해 자연어로 질문할 수 있는 AI 서비스를 만든다.

예:

* 특정 구단의 최근 경기 흐름
* 시즌별 성적 비교
* 두 구단 비교
* 최근 상승/하락 추세
* 최고/최저 기록
* 월별 경기 흐름
* 최근 5경기 / 10경기 분석

---

# 4. M1-1과 M1-2의 관계

두 과제는 별도 프로젝트이지만 연결해서 진행한다.

## M1-1

```text
데이터 수집
→ 데이터 정제
→ 시계열 분석
→ 그래프
→ 인사이트 도출
```

## M1-2

```text
M1-1 최종 데이터
→ Firestore 저장
→ FastAPI
→ Summary API
→ GPT Context Injection
→ AI Chat
→ 웹서비스
```

M1-1 완료 후 생성된 **최종 CSV 또는 분석용 데이터를 M1-2에서 재사용한다.**

따라서 M1-2를 먼저 본격 개발하지 않고
**M1-1을 완료한 뒤 시작하는 것이 현재 계획이다.**

---

# 5. 데이터 범위 예정

최종 데이터 범위는 M1-1 완료 결과에 맞춘다.

기본 분석 데이터:

```text
2023
2024
2025
```

2026 시즌 데이터는 M1-1에서 최종 결정한 방식에 맞춰 사용한다.

가능한 방법:

```text
2023~2025 : 완료된 시즌
2026      : 시즌 진행 중 데이터 / 별도 표시
```

M1-2에서는 필요할 경우 2026 데이터를 포함하여
현재 시즌 흐름 질문도 가능하게 확장할 수 있다.

---

# 6. 데이터 구조 예정

과제 기본 구조:

```text
date
value
memo
```

야구 서비스에서는 추가 컬럼 사용 가능.

예:

```text
date
season
team
opponent
runs_for
runs_against
run_diff
result
memo
```

예시:

```json
{
  "date": "2025-04-05",
  "season": 2025,
  "team": "KIA",
  "opponent": "Samsung",
  "runs_for": 7,
  "runs_against": 4,
  "run_diff": 3,
  "result": "W",
  "memo": "KIA 7:4 Samsung"
}
```

`value`가 반드시 필요하다면 `run_diff`를 value로 사용할 수 있다.

```text
value = 득점 - 실점
```

예:

```text
7 : 4 → +3
2 : 6 → -4
```

---

# 7. 최종 서비스 구조

```text
사용자
  ↓
Frontend
HTML / CSS / JavaScript
  ↓
Vercel
  ↓
FastAPI Backend
  ↓
Render
  ├── Firestore
  ├── Data API
  ├── Summary API
  ├── Conversation API
  └── Chat API
          ↓
      OpenAI GPT API
```

---

# 8. 필수 기능

## 8-1. 데이터 기반 AI 채팅

사용자가 자연어로 질문한다.

예:

```text
"최근 KIA 경기 흐름이 어때?"

"2024년 KIA와 삼성 비교해줘."

"최근 10경기 성적이 좋아진 팀은?"

"올해 삼성 경기 흐름을 설명해줘."
```

FastAPI가 Firestore 데이터를 분석한 Summary를 불러와
GPT 시스템 프롬프트에 넣는다.

---

# 9. 핵심 개념 — Context Injection

이번 과제에서 가장 중요한 개념.

예:

```text
당신은 KBO 데이터 분석 AI 비서입니다.

[사용자 데이터 요약]

기간: 2023~2025
총 데이터: 2,000개

KIA
- 평균 득실차: +0.72
- 최근 10경기: 상승

Samsung
- 평균 득실차: +0.31
- 최근 10경기: 유지

위 데이터에 기반하여 답변하세요.
```

사용자가

```text
"요즘 KIA 분위기가 어때?"
```

라고 물으면 GPT가 일반적인 인터넷 지식이 아니라
**현재 Firestore 데이터 Summary를 기반으로 답변하게 한다.**

---

# 10. 필수 API

## Data API

```text
POST   /api/data
GET    /api/data
PUT    /api/data/{id}
DELETE /api/data/{id}
```

---

## Summary API

```text
GET /api/data/summary
```

예상 응답:

```json
{
  "period": "2023-04-01 ~ 2025-10-01",
  "count": 2000,
  "teams": {
    "KIA": {
      "games": 216,
      "average_run_diff": 0.72,
      "max_run_diff": 11,
      "min_run_diff": -9,
      "trend": "상승"
    }
  }
}
```

---

# 11. Conversation API

필수:

```text
POST   /api/conversations
GET    /api/conversations
DELETE /api/conversations/{id}
```

대화 불러오기 기능도 필요하다.

추천:

```text
GET /api/conversations/{id}
```

---

# 12. Chat API

```text
POST /api/chat
```

동작 순서:

```text
사용자 질문
    ↓
Summary 조회
    ↓
System Prompt 생성
    ↓
GPT API 호출
    ↓
AI 답변
    ↓
대화 Firestore 저장
    ↓
Frontend 반환
```

---

# 13. Firestore 컬렉션

최소 구조:

```text
data
conversations
```

예:

```text
Firestore

data/
   document1
   document2
   document3

conversations/
   conversation1
   conversation2
```

---

# 14. FastAPI 프로젝트 구조 예정

```text
M1-2/
│
├── backend/
│   ├── main.py
│   │
│   ├── routers/
│   │   ├── data.py
│   │   ├── conversations.py
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── firebase_service.py
│   │   ├── data_service.py
│   │   ├── summary_service.py
│   │   └── chat_service.py
│   │
│   ├── models/
│   │   └── schemas.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── data/
│   └── kbo_games.csv
│
├── .gitignore
├── README.md
└── SUMMARY.md
```

---

# 15. 사용 기술

## Backend

```text
Python 3.10+
FastAPI
Uvicorn
Pydantic
firebase-admin
python-dotenv
openai
```

## Frontend

```text
HTML
CSS
Vanilla JavaScript
```

Framework 사용 금지.

React / Vue 등 사용하지 않는다.

## Database

```text
Firebase Firestore
```

## AI

```text
OpenAI GPT API
```

## Deploy

```text
Backend  → Render
Frontend → Vercel
```

---

# 16. 환경 변수

예:

```env
OPENAI_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
LOCAL_CSV_MODE=false
REQUIRE_FIRESTORE=true
CHAT_REQUESTS_PER_MINUTE=10
ALLOWED_ORIGINS=
API_BASE_URL=
```

중요:

```text
.env
Firebase Service Account JSON
API Key
```

는 GitHub에 올리지 않는다.

`.gitignore` 필수.

---

# 17. Frontend 화면 구성 예정

한 페이지 Dashboard 형태를 우선 고려한다.

```text
┌─────────────────────────────────────┐
│ ⚾ KBO AI Assistant                 │
├───────────────────┬─────────────────┤
│ 📊 데이터 요약     │ 🤖 AI Chat      │
│                   │                 │
│ 기간               │ 사용자 질문     │
│ 경기 수            │                 │
│ 최근 추세          │ AI 답변          │
│                   │                 │
├───────────────────┼─────────────────┤
│ 📝 데이터 관리     │ 💬 이전 대화     │
│                   │                 │
│ 날짜               │ Conversation 1  │
│ 값                 │ Conversation 2  │
│ Memo              │ Conversation 3  │
│                   │                 │
└───────────────────┴─────────────────┘
```

필수 화면:

```text
1. AI Chat
2. Data Summary
3. Data CRUD
4. Conversation History
```

---

# 18. 데이터 관리 UI

필수:

```text
새 데이터 추가
데이터 목록 표시
```

그리고 수정 / 삭제 중 최소 1개가 화면에서 실제 동작해야 한다.

가능하면 둘 다 구현한다.

---

# 19. 대화 기록 UI

화면에 이전 대화 목록 표시.

예:

```text
2026-09-01 KIA 분석
2026-09-02 Samsung 비교
2026-09-03 최근 경기 분석
```

클릭 시 이전 대화를 다시 표시한다.

---

# 20. Summary 화면

예:

```text
분석 기간
2023-04-01 ~ 2025-10-01

총 데이터
2,160건

KIA
최근 추세 ↑

Samsung
최근 추세 →

...
```

---

# 21. 개발 순서

과제 완성이 최우선이므로 아래 순서를 유지한다.

## STEP 1

M1-1 완료

```text
최종 CSV 확보
컬럼 확정
데이터 검증
```

---

## STEP 2

M1-2 프로젝트 폴더 생성

```text
backend
frontend
data
```

---

## STEP 3

Python 가상환경

Windows PowerShell 기준:

```powershell
python -m venv .venv
```

활성화:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## STEP 4

FastAPI 최소 실행

```text
main.py
```

작성 후:

```powershell
uvicorn backend.main:app --reload
```

확인:

```text
/
```

그리고

```text
/docs
```

Swagger UI 확인.

---

## STEP 5

Firebase 연결

처음에는 CRUD를 만들지 않고

```text
FastAPI ↔ Firebase
```

연결 성공 여부만 확인한다.

---

## STEP 6

Data CRUD

순서:

```text
POST
→ GET
→ PUT
→ DELETE
```

한 기능씩 테스트.

---

## STEP 7

Summary API

```text
GET /api/data/summary
```

구현.

최소:

```text
기간
count
average
max
min
trend
```

야구 데이터에 맞게 팀별 통계 추가 가능.

---

## STEP 8

Conversation API

```text
대화 저장
목록 조회
특정 대화 조회
삭제
```

---

## STEP 9

OpenAI API 연결

처음에는 아주 간단한 질문으로 연결 테스트.

과거 OpenAI API 사용 시 `429 insufficient_quota` 문제가 있었으므로
프로젝트 초기에 API Key 및 Billing 상태를 확인한다.

테스트 시:

```text
작은 prompt
짧은 output
적은 요청 횟수
```

사용.

---

## STEP 10

Context Injection

Summary 결과를 시스템 프롬프트에 삽입.

이 단계가 이번 과제의 핵심이다.

---

## STEP 11

Frontend 제작

순서:

```text
Summary
→ Data
→ Chat
→ Conversation
```

---

## STEP 12

Render 배포

Backend 배포.

확인:

```text
https://xxxx.onrender.com/docs
```

Swagger가 외부에서 보여야 한다.

---

## STEP 13

Vercel 배포

Frontend 배포.

Frontend에서 Render Backend URL 사용.

---

## STEP 14

CORS 확인

Vercel 주소에서 Render API 호출 가능하도록 설정.

---

## STEP 15

README 작성

---

# 22. README 필수 내용

```text
서비스 소개
기술 스택
프로젝트 구조
데이터 설명
Backend 실행 방법
Frontend 실행 방법
환경 변수
Firebase 설정
배포 URL
Swagger URL
스크린샷
```

스크린샷 필수:

```text
1. 데이터 Summary가 보이는 AI Chat
2. Data CRUD 동작
3. Conversation 불러오기
```

---

# 23. 배포 URL

최종 제출 시 README에:

```text
Frontend:
https://xxxxx.vercel.app

Backend:
https://xxxxx.onrender.com

Swagger:
https://xxxxx.onrender.com/docs
```

---

# 24. 보너스 기능

필수 기능 완료 후에만 진행한다.

우선순위:

## 1순위 — 그래프

추천.

예:

```text
구단별 최근 경기 추세
월별 승률
득실차 변화
```

프론트에서 그래프 1개 구현.

---

## 2순위 — CSV / JSON 다운로드

현재 데이터를 파일로 다운로드.

---

## 3순위 — Dark Mode

간단한 UI 보너스.

---

## 후순위

```text
Function Calling
MCP
GPT Actions
```

기능이 복잡하므로 필수 과제 완료 후 여유가 있을 때만 진행한다.

---

# 25. 과제에서 설명할 수 있어야 할 핵심 개념

## 시계열 데이터

날짜 순서에 따라 변화하는 데이터를 분석하는 것.

---

## FastAPI Router / Service 구조

```text
Router
→ API 요청/응답 담당

Service
→ 실제 데이터 처리 / 분석 / DB / GPT 기능 담당
```

기능을 분리해 유지보수하기 쉽게 한다.

---

## Pydantic

API로 들어오는 값을 검증한다.

예:

```text
date 누락
value가 숫자가 아님
필수 항목 없음
```

등을 방지.

---

## Firestore

클라우드 NoSQL DB.

이번 프로젝트에서는:

```text
data
conversations
```

저장.

---

## Context Injection

내 데이터 Summary를 GPT의 System Prompt에 삽입하여
GPT가 해당 데이터를 기반으로 답하게 하는 방식.

---

## CORS

Frontend와 Backend의 주소가 다르기 때문에
허용할 Frontend 주소를 Backend에서 설정해야 한다.

---

## 환경 변수

API Key와 Firebase 인증 정보 등을
코드에 직접 넣지 않고 별도로 관리한다.

---

# 26. 과제 필수 체크리스트

## 개발 환경

* [ ] Python 3.10+
* [ ] venv
* [ ] FastAPI
* [ ] uvicorn
* [ ] firebase-admin
* [ ] openai
* [ ] python-dotenv

## 데이터

* [ ] 시계열 데이터 선정
* [ ] 데이터 100개 이상
* [ ] Summary 생성 가능

## FastAPI

* [ ] FastAPI 실행
* [ ] CORS
* [ ] `/docs`

## Firestore

* [ ] Firebase 프로젝트
* [ ] Firestore 생성
* [ ] 서비스 계정
* [ ] 환경변수 관리
* [ ] data collection
* [ ] conversations collection

## Data API

* [ ] POST /api/data
* [ ] GET /api/data
* [ ] PUT /api/data/{id}
* [ ] DELETE /api/data/{id}
* [ ] GET /api/data/summary

## Conversation

* [ ] POST /api/conversations
* [ ] GET /api/conversations
* [ ] GET /api/conversations/{id}
* [ ] DELETE /api/conversations/{id}

## AI

* [ ] POST /api/chat
* [ ] Summary 조회
* [ ] System Prompt Injection
* [ ] GPT 호출
* [ ] 대화 자동 저장

## Frontend

* [ ] Chat UI
* [ ] Loading 표시
* [ ] Summary 표시
* [ ] Data 목록
* [ ] Data 추가
* [ ] 수정 또는 삭제
* [ ] Conversation 목록
* [ ] Conversation 불러오기

## 배포

* [ ] Backend → Render
* [ ] Swagger 접속
* [ ] Frontend → Vercel
* [ ] CORS
* [ ] API URL 환경설정

## README

* [ ] 서비스 소개
* [ ] 기술 스택
* [ ] 배포 URL
* [ ] 로컬 실행 방법
* [ ] 환경 변수
* [ ] Chat 스크린샷
* [ ] CRUD 스크린샷
* [ ] Conversation 스크린샷

---

# 27. 개발 원칙

이번 프로젝트의 최우선 목표:

> **과제 요구사항을 빠짐없이 만족하는 완성된 서비스를 만드는 것**

따라서 작업 중에는 기능을 아래처럼 구분한다.

```text
✅ 필수
🟡 선택
⭐ 보너스
```

필수 기능이 완료되기 전에는 불필요한 기능을 추가하지 않는다.

---

# 28. Codex 작업 원칙

Codex에게 한 번에 전체 서비스를 만들라고 하지 않는다.

권장:

```text
1. 현재 단계 설명
2. 필요한 파일만 수정
3. 실행
4. 오류 확인
5. 수정
6. Git commit
7. 다음 단계
```

예:

```text
지금은 STEP 4 FastAPI 기본 실행 단계다.
Firebase나 GPT 기능은 아직 구현하지 말고,
FastAPI 서버와 /docs가 정상 실행되는 최소 코드만 만들어라.
```

이런 방식으로 작은 단계로 진행한다.

---

# 29. Git Commit 예시

```text
Initialize FastAPI backend

Connect Firebase Firestore

Implement data CRUD API

Add data summary endpoint

Implement conversation API

Connect OpenAI chat API

Inject data summary into GPT context

Build frontend chat UI

Add data management interface

Add conversation history

Deploy backend to Render

Deploy frontend to Vercel

Complete README documentation
```

---

# 30. 현재 진행 상태

```text
과제 요구사항 확인       ✅
주제 방향 결정           ✅
M1-1과 연계 계획         ✅
10개 구단 확장 방향      ✅
프로젝트 구조 설계       ✅

M1-1 완료                ✅ 별도 프로젝트 완료

M1-2 실제 개발            ⬜
FastAPI                   ⬜
Firebase                  ⬜
CRUD                      ⬜
Summary                   ⬜
Conversation              ⬜
GPT                       ⬜
Context Injection         ⬜
Frontend                  ⬜
Render                    ⬜
Vercel                    ⬜
README                    ⬜
```

---

# 31. M1-2 시작 조건

M1-1 완료 후 아래 정보를 가져온다.

```text
최종 CSV 파일
컬럼 설명
분석 기간
팀 목록
전처리 방법
결측치 처리
주요 분석 지표
주요 분석 결과
```

그 후 M1-2 개발을 시작한다.

---

# 32. M1-1 → M1-2 인계 시 확인

M1-1 완료 직후 아래를 결정한다.

```text
1. M1-2에서 사용할 최종 CSV
2. Firestore에 넣을 컬럼
3. value 정의
4. Summary에서 사용할 지표
5. 2026 시즌 포함 여부
6. 10개 구단 전체 적용 여부
```

현재 방향은:

```text
M1-1 분석 결과를 기반으로
M1-2에서 KBO 10개 구단 AI 데이터 비서로 확장
```

---

# 33. 최종 목표 서비스

**KBO 데이터 기반 AI Assistant**

사용자는 데이터를 직접 확인하지 않아도 자연어로 질문한다.

예:

```text
"2025년 KIA 경기 흐름을 설명해줘."

"삼성과 KIA의 최근 기록을 비교해줘."

"최근 10경기에서 좋아진 팀은?"

"이 팀의 가장 좋았던 시기는 언제야?"
```

AI는 Firestore의 실제 데이터를 분석한 Summary에 근거하여 답한다.

이것이 이번 M1-2 과제에서 구현할
**'내 데이터를 이해하는 AI 비서'**의 최종 형태다.

---

# 34. M1-2 확정 범위 및 구현 기준

이 문서는 초안의 세부 표현보다 아래 확정 기준을 우선한다.

## 34-1. 미션 필수 기능과 확장 기능 분리

M1-2 미션의 필수 기능은 다음 네 가지다.

1. 데이터 기반 AI 채팅
2. 데이터 관리 CRUD
3. 대화 저장·목록 조회·불러오기
4. 배포 및 문서화

KBO 10개 구단 확장, 승부 예측, 사용자 투수 선택, 투수 통계
반영, 예상 선발 자동 수집은 서비스 확장 기능이다. 필수 기능을
완료한 뒤 순서대로 진행한다.

## 34-2. 단계별 개발 순서

```text
1. M1-1 KIA·삼성 데이터로 FastAPI·Firestore·CRUD·Chat 검증
2. 10개 구단 수집기로 데이터 범위 확장
3. /api/predictions 추가
4. 사용자가 투수 이름·ID를 선택하는 기능 추가
5. 투수 통계가 있을 때만 예측에 반영
6. 예상 선발 자동 수집은 후속 단계
```

M1-1의 KIA·삼성 2023~2025 데이터는 1단계의 개발·검증 데이터로
사용한다. 현재 M1-2의 최종 확장 목표는 KBO 10개 구단이며, 2026년
실제 경기는 진행 중 데이터로 별도 표시한다. M1-1의 2026년 기준선
예측 파일은 실제 경기 데이터와 섞지 않는다.

## 34-3. Firestore `data` 문서 기준

`data` 컬렉션의 문서 1건은 경기 전체가 아니라 특정 팀 관점의 경기
기록 1건이다. 기존 M1-1 CSV와 미션의 `date/value/memo` 구조를 함께
수용하기 위한 결정이다.

```json
{
  "id": "20250902HTHH0_KIA",
  "game_id": "20250902HTHH0",
  "date": "2025-09-02",
  "season": 2025,
  "team_code": "KIA",
  "team": "KIA",
  "opponent_code": "HH",
  "opponent": "한화",
  "home_away": "away",
  "runs_for": 3,
  "runs_against": 1,
  "run_diff": 2,
  "value": 2,
  "result": "W",
  "status": "completed",
  "memo": "KIA 3:1 한화",
  "source_url": "...",
  "updated_at": "..."
}
```

`value`는 해당 팀 기준 `run_diff`이고, `memo`는 사람이 읽을 수 있는
경기 요약이다. 내부 식별자는 정규화된 팀 코드를 포함한
`{game_id}_{team_code}`를 사용한다.

`status` 허용값은 `completed`, `scheduled`, `cancelled`, `postponed`다.
`completed`가 아닌 데이터는 승률·득실차·최근 경기 Summary에서
제외한다. CRUD는 팀별 경기 기록 1건을 기준으로 한다.

## 34-4. 예측 기능 기준

승부 예측은 필수 Chat API와 분리하여 다음 API로 추가한다.

```text
POST /api/predictions
```

예측 결과는 처음에는 Firestore에 저장하지 않고 백엔드에서 계산하여
응답한다. 응답에는 `as_of`, `method`, 팀별 확률, `limitations`를
포함한다. `as_of`는 고정 날짜가 아니라 서버 계산 시각이다.

사용자는 팀·시즌별 목록에서 투수를 선택할 수 있다. 투수 선택은 선택 사항이다.
현재 목록은 2023~2026 KBO 정규시즌의 시즌·팀별 IP 상위 3명, 총 120개의 시즌별 기록이다. 같은 선수가 여러 시즌에 포함될 수 있다.
양쪽 투수의 해당 시즌·해당 팀 통계가 모두 있을 때 팀 성적 80% + 선택한 투수 지표 20%로 계산한다.
미선택 또는 한쪽 통계 누락 시 팀 성적 기준으로 계산한다.
예상 선발 자동 수집과 선발 등판별 분석은 후속 기능이다.

경기는 2023~2025 10개 구단 전체 정규시즌, 2026 수집 시점까지 완료 경기로 관리한다.
경기는 `data/games/game_results_YYYY.csv`, 투수는 `data/pitchers/pitcher_stats_YYYY.csv`로 분리 보관한다.
복수 파일 조회는 각각 `DATA_PATHS`, `PITCHER_DATA_PATHS`로 설정하며 선택 시즌·팀으로 필터링한다.
과거 시즌 최종 통계는 시즌 비교에만 사용한다. 경기 이후 정보가 포함되므로 경기별 사전 예측 검증에는 해당 경기 이전 통계가 별도로 필요하다.

```text
사용자 선택 투수 이름·player_id
→ 저장된 투수 통계 조회
→ 양쪽 통계가 있으면 시즌 통계를 예측 계산에 반영
→ 미선택·통계 누락이면 팀 성적으로 계산하고 안내
```

## 34-5. Summary와 Chat 범위

전체 구단·전체 시즌 Summary를 한 번에 GPT에 주입하지 않는다. 질문
또는 프론트엔드 선택값에 따라 팀·시즌·기간·최근 N경기 범위를 먼저
정하고, 해당 범위의 Summary만 Context로 주입한다.

데이터가 없거나 범위가 불명확한 경우에는 추측하지 않고 부족한
데이터와 기준 시점을 안내한다.

## 34-6. 미션 정합성 체크

- 100개 이상 시계열 데이터: M1-1 완료 데이터 864행으로 충족
- `date/value/memo` CRUD: 팀별 경기 기록 구조로 충족
- Summary: 기간·개수·통계·추세를 제공
- Pydantic: 날짜·팀·점수·상태·질문·범위 검증
- Firestore: `data`, `conversations` 컬렉션 사용
- Context Injection: Summary를 시스템 프롬프트에 주입
- 대화 불러오기: `GET /api/conversations/{id}` 구현
- 배포: Render Backend, Vercel Frontend
- 보안: API 키·서비스 계정 정보 환경 변수 관리


