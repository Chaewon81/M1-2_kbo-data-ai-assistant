# 제출 증빙 기록

## 범위와 판정

배포: [프론트엔드](https://m1-2kbo-data-ai-assistant.vercel.app/) · [API](https://m1-2-kbo-data-ai-assistant.onrender.com) · [Swagger](https://m1-2-kbo-data-ai-assistant.onrender.com/docs).

2026-10-03 에이전트 읽기 검사에서 health 200·공개 프론트엔드 config.js의 정확한 Render 주소·접근 키 없는 API 401을 확인했다. 사용자 보고로 배포 Firestore 연결 및 실제 GPT 답변 확인. 로컬 사용자 보고로 Usage 542토큰·서버 재시작 후 대화/요약 복원 확인. 그 증거를 새로운 배포 전체 검증으로 과장하지 않는다.

| 요구 사항 | 캡처/검증 | 상태 |
|---|---|---|
| 배포 홈·Swagger 접속 | 실제 배포 화면 촬영 | 준비 중 |
| 질문·GPT 답변·Summary | 기존 저장 대화 조회, 새 GPT 호출 없음 | 준비 중 |
| 대화 불러오기 | 실제 목록에서 선택·당시 Summary 확인 | 준비 중 |
| 데이터 추가·저장·삭제 | 2099-01-01 가상 사용자 기록만 생성/조회/삭제 | 준비 중 |
| 모바일 주요 기능 | 390px 실제 브라우저, 목록·Chat·Summary·폼 확인 | 준비 중 |

캡처 도구는 로컬 `.env`의 시연 키를 자식 프로세스 환경으로만 전달하며 CLI/보고서에 키를 출력하지 않는다. Playwright는 `.tools/capture`에만 설치하고 공개 업로드에서 제외한다. 접속 시 자동 sync POST는 실제 저장 상태 GET으로 대체하여 캡처 중 경기 갱신 쓰기를 하지 않는다. 이 캡처는 자동 갱신 새 실행의 증빙이 아니다. CRUD 가상 기록은 현재 시즌 통계에서 분리된 2099년 기록이며 완료 후 삭제하고 삭제 보호 이력은 남는다. 공식 경기·기존 대화는 변경하지 않는다.

Firestore 저장은 연결 상태·실제 API 추가/재조회와 운영 필수 Firestore 모드로 확인한다. Firebase 콘솔 화면이나 서버 재시작 확인과는 구분한다. 새로운 GPT 비용 없이 기존 답변을 불러오는 캡처이므로 당시 AI 생성의 사용자 확인과 함께 해석한다.

## 재실행

```powershell
python backend/scripts/capture_submission.py --mode public
python backend/scripts/capture_submission.py --mode authenticated
# 가상 기록 추가·삭제를 포함할 때만:
python backend/scripts/capture_submission.py --mode crud
```

Chrome 설치 및 임시 Playwright 도구가 필요하다. 인증 캡처는 루트 `.env`에 `DEMO_ACCESS_KEY`가 있어야 하며 키를 채팅/스크린샷/README에 보내지 않는다. 필수 캡처가 촬영된 뒤 아래에 실제 파일·시각·검증 범위를 기록한다.
