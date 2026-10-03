# GPT 연결 — 초보자용 순서

실제 GPT 응답·Usage 542토큰을 사용자 보고로 확인했고, 2026-10-02 GPT + Firestore 서버 재시작 후 동일 대화·Summary 유지도 사용자 보고로 확인했다. 아래는 **GPT + 로컬 CSV** 안내다. 제출용 재현 절차는 [FIRESTORE_VERIFICATION.md](FIRESTORE_VERIFICATION.md)를 따른다.

결정: 과제 제출·시연에는 OpenAI `gpt-4o-mini`, 반복 개발에는 Mock을 사용한다.

1. [OpenAI Billing](https://platform.openai.com/settings/organization/billing/overview)에서 크레딧을 준비한다. 결제는 본인이 직접 진행하고 자동 충전은 꺼둔다.
2. [OpenAI API 키](https://platform.openai.com/api-keys)에서 키를 준비한다. 기존 키가 유효하면 새로 만들 필요는 없다. 키를 채팅에 보내지 않는다.
3. 프로젝트 루트의 `.env`를 편집한다. 파일이 없다면 `backend/.env.example`을 참고해 만든다. 기존 `.env`가 있으면 덮어쓰지 말고 아래 항목만 수정한다.

```env
AI_PROVIDER=openai
OPENAI_API_KEY=본인_키로_교체
OPENAI_MODEL=gpt-4o-mini
OPENAI_MOCK_MODE=false
```

4. 기존 백엔드 창에서 `Ctrl + C`, 프로젝트 루트에서 실행한다.

```powershell
.\backend\scripts\start_local.ps1 -AiMode gpt
```

5. `http://127.0.0.1:8000/api/chat/status`에서 `mode: real`, `provider: openai`, `model: gpt-4o-mini`, `configured: true`인지 확인한다. 이는 설정 확인이지 성공 호출 증빙은 아니다.
6. 프론트엔드 `http://127.0.0.1:5500`에서 `Ctrl + F5`. KIA·2026·최근 10경기를 선택하고 “최근 경기 흐름을 Summary 숫자로 설명해줘.”라고 질문한다.
7. 실제 AI 응답 표시, 답변 숫자와 Summary 일치, 대화 저장·다시 열기를 확인한다. [Usage](https://platform.openai.com/usage)에서 호출과 실제 비용을 확인하고 질문·답변·Summary가 보이는 화면을 캡처한다.

오류: 503은 키·권한 설정, 429는 요청 제한 또는 크레딧/할당량 부족, 504는 AI 대기 시간 초과. 오류 메시지에 따라 확인한다. 키나 서비스 계정 전체 내용은 공유하지 않는다.

비용 없이 개발하려면 `.\backend\scripts\start_local.ps1`로 실행한다. 두 명령 모두 로컬 CSV·메모리 모드라 재시작하면 대화·수정이 사라진다. Firestore와 배포 테스트는 별도로 진행한다. Chat의 현재 Context는 팀 Summary이며, 투수·예측 Context 및 이전 메시지 전달은 후속 작업이다.
