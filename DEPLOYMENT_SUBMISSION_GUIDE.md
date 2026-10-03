# 배포·제출 마무리 체크리스트

## 현재 상태

업데이트: 실제 격리 DB 재실행 ce45a854d4b5의 8개 PASS, Render/Vercel 배포 및 연결 확인. 실제 서버 충돌 재시도는 관측되지 않았으므로 별도 한계로 유지한다. 현재는 과제 Comment에 따른 문서·모바일 보완 및 최종 캡처 단계다.

배포 주소는 README에 명시했다. 사용자 보고로 Firestore 연결·실제 GPT 답변을 확인했고, 에이전트는 공개 config.js·health·CORS를 확인했다. 다음은 모바일 목록 보완 배포 → 기존 대화/가상 CRUD/Swagger/모바일 캡처 → README 증빙 연결이다. [제출 증빙](SUBMISSION_EVIDENCE.md). 이번 캡처는 새 GPT 호출 없이 진행한다.

## 1. 실제 보호 테스트 — 완료 범위와 재실행 안내

[격리 가이드](ISOLATED_FIRESTORE_TEST_GUIDE.md)의 같은 프로젝트/테스트 JSON으로 재실행한다. 모든 8개 결과와 operation 재시도 수를 확인한다. 부분 실패의 counts는 확인된 처리 건수이며, 응답 불확실 커밋을 포함한 실제 DB 변경 총수를 보장하지 않는다. 전체 롤백을 주장하지 않는다.

잠금 순서 설명은 삭제/일반 수정/추가 경로의 marker→record 보완에 한정한다. 자동 갱신·누락 보충의 get_all 경로까지 모든 잠금 순서가 통일됐다고 주장하지 않는다. 동시 수동 수정/적재 테스트는 적재 함수와의 경합이지 자동 갱신의 모든 경합 검증이 아니다.

## 2. Render 백엔드 설정 — 배포 완료

프로젝트 루트를 기준으로 배포한다. CSV와 재사용 M1-1 수집기 폴더도 함께 배포해야 한다.

- Build Command: `pip install -r backend/requirements.txt`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`
- 운영용 서비스 계정 JSON을 Render Secret File로 등록하고 `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-service-account.json`처럼 실제 파일 위치를 설정한다. 테스트 프로젝트 JSON을 운영 배포에 쓰지 않는다.
- 비밀 키/서비스 계정은 Git·Vercel·스크린샷에 올리지 않는다.

Render 환경변수:

```env
APP_ENV=production
DEMO_ACCESS_KEY=별도생성한24자이상랜덤시연키
AI_PROVIDER=openai
OPENAI_API_KEY=본인키
OPENAI_MODEL=gpt-4o-mini
OPENAI_MOCK_MODE=false
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-service-account.json
LOCAL_CSV_MODE=false
REQUIRE_FIRESTORE=true
AUTO_SYNC_ENABLED=true
CHAT_REQUESTS_PER_MINUTE=10
ALLOWED_ORIGINS=https://실제프로젝트.vercel.app
```

시즌 CSV 경로는 코드가 `data/games`, `data/pitchers`에서 기본 탐색한다. 별도 설정한다면 실제 파일명에 맞춘 `DATA_PATHS`/`PITCHER_DATA_PATHS`를 사용한다. Windows 로컬 JSON 경로를 Render에 복사하지 않는다.

production에서 시연 키가 없거나 짧은 키·메모리 fallback·와일드카드/HTTP CORS 설정이면 시작을 중단한다. 서버 키 생성 예시: 로컬에서 `python -c "import secrets; print(secrets.token_urlsafe(32))"`. 생성값은 비밀로 보관하고 Render에만 설정한다. 문서에는 실제 값을 적지 않는다.

## 3. Vercel 프론트엔드 준비

프로젝트 Root Directory는 저장소 루트. `vercel.json`은 `node frontend/build_config.cjs`로 명시적 정적 파일만 `dist`에 복사하고 공개 설정을 생성한다.

Vercel 환경변수:

```env
API_BASE_URL=https://실제백엔드.onrender.com
```

공개 HTTPS origin만 허용한다. localhost/경로/쿼리/자격증명이 들어간 URL은 빌드에서 거부한다. OpenAI 키·서비스 계정 JSON·`DEMO_ACCESS_KEY`는 Vercel 설정/소스에 넣지 않는다. URL 변경 후 다시 빌드한다. 현재 API_BASE_URL은 `https://m1-2-kbo-data-ai-assistant.onrender.com`, Render CORS는 `https://m1-2kbo-data-ai-assistant.vercel.app`이다. GitHub 계정 연결·실제 배포·CORS 검증은 완료했다.

## 4. 평가자 접근

평가자에게 URL과 시연 키를 비공개 제출 채널로 전달한다. 화면 상단의 “시연 접근 키” 입력 → 연결. 키는 sessionStorage에 보관하며 페이지 소스/배포 설정에 하드코딩하지 않는다. Swagger `/docs`는 Authorize에서 `X-Demo-Key`를 입력한다. health·문서 자체는 공개다.

공유 키를 가진 사용자는 같은 데이터와 대화를 조회/수정/삭제할 수 있다. 실제 민감한 대화를 올리지 않는다. CORS/분당 제한은 인증을 대체하지 않으며 이 시연 보호도 회원별 권한·비용 상한을 제공하지 않는다. 프론트엔드에는 첫 접속 서버 시작 지연 안내를 표시한다.

## 5. 배포 후 필수 검증·캡처

- [x] 실제 프론트엔드·백엔드·Swagger URL을 README에 기록
- [ ] 무키/잘못된 키 API는 차단, 유효 시연 키로 접근
- [ ] 키/서비스 계정 내용이 프론트엔드 산출물·캡처에 없는지 확인
- [x] 질문 + 저장 GPT 답변 + 선택 데이터 Summary가 함께 보이는 캡처 (새 생성 없음)
- [x] 가상 사용자 데이터 추가/삭제 동작 캡처(공식 원본 수정/삭제 없음)
- [x] 이전 대화 불러오기 + 당시 Summary 캡처(추가 GPT 질문 없음)
- [ ] Render `/docs` 접속 및 실제 Firestore 영구 저장 확인
- [x] 작은 화면 목록·저장 Chat·Summary·관리 입력 폼 배치 확인/캡처
- [ ] 실제 휴대폰 또는 작은 화면에서 새 질문·CRUD 전송 최종 수동 확인
- [ ] 자동 갱신 화면은 별도 증빙으로 첨부 — Chat 캡처를 대신하지 않음
- [ ] 첫 접속 지연 안내·GPT 비용/데이터 기준일/예측 한계 확인

실제 GPT 호출은 배포 확인 시 최소 횟수로 진행하고 Usage 증빙을 확보한다. 최종 URL이나 API 키가 없는 상태를 배포 완료로 표시하지 않는다.

구성 확인에 사용한 공식 자료: [Render FastAPI](https://render.com/docs/deploy-fastapi), [Render 환경변수·Secret Files](https://render.com/docs/configure-environment-variables), [Vercel 프로젝트 설정](https://vercel.com/docs/project-configuration).
