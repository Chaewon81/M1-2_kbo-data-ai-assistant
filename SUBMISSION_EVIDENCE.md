# 제출 증빙 기록

## 범위와 판정

배포: [프론트엔드](https://m1-2kbo-data-ai-assistant.vercel.app/) · [API](https://m1-2-kbo-data-ai-assistant.onrender.com) · [Swagger](https://m1-2-kbo-data-ai-assistant.onrender.com/docs).

2026-10-03 에이전트 읽기 검사에서 health 200·공개 프론트엔드 config.js의 정확한 Render 주소·접근 키 없는 API 401을 확인했다. 사용자 보고로 배포 Firestore 연결 및 실제 GPT 답변 확인. 로컬 사용자 보고로 Usage 542토큰·서버 재시작 후 대화/요약 복원 확인. 그 증거를 새로운 배포 전체 검증으로 과장하지 않는다.

| 요구 사항 | 캡처/검증 | 상태 |
|---|---|---|
| 배포 홈·Swagger 접속 | 실제 배포 화면 촬영 | PASS |
| 질문·GPT 답변·Summary | 기존 저장 대화 조회, 새 GPT 호출 없음 | PASS (저장 답변 조회) |
| 대화 불러오기 | 실제 목록에서 선택·당시 Summary 확인 | PASS |
| 데이터 추가·저장·삭제 | 2099-01-01 가상 사용자 기록만 생성/조회/삭제 | PASS (배포 화면/API) |
| 작은 화면 목록·요약·입력 폼 | Chrome 390px viewport, 목록 선택·요약 표시·입력 폼 너비 확인 | PASS (새 GPT 질문·모바일 CRUD 전송은 별도) |

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

## 실제 촬영 결과 (2026-10-03)

CRUD 촬영 완료: `2026-10-03T07:31:35.714Z` (KST 16:31:35). 인증 읽기 재촬영 완료: `2026-10-03T07:33:45.585Z` (KST 16:33:45). Chrome headless에서 실제 Vercel 화면·Render API를 사용했고 로컬 화면/임의 답변을 삽입하지 않았다. 질문과 전체 답변이 잘리지 않도록 **기존 채팅 스크롤 영역만 촬영용으로 펼쳤으며 내용은 변경하지 않았다.** 실제 모바일 기기가 아닌 390×844 작은 화면 viewport 검증이다.

- [배포 화면·대화 불러오기](picture/submission/03_CHAT_SUMMARY_RELOADED.png)
- [질문·답변·Summary 상세](picture/submission/04_CHAT_SUMMARY_DETAIL.png)
- [작은 화면 대화 목록·Chat·Summary·관리 폼](picture/submission/05_MOBILE_CONVERSATION.png)
- [가상 데이터 추가 결과](picture/submission/06_DATA_CREATED.png)
- [저장 기록 API 재조회](picture/submission/07_STORED_DATA_API.png)
- [가상 데이터 삭제 후 목록](picture/submission/08_DATA_DELETED.png)
- [배포 Swagger](picture/submission/09_DEPLOYED_SWAGGER.png)

확인한 저장 대화: “LG와 기아의 상대전적 확인해줘”, 2026-03-31~09-26, 완료 맞대결 12경기·LG 7승·KIA 5승·0무·LG 승률 0.5833. 화면의 GPT 답변과 저장 Summary 수치 일치. `/api/chat/status`는 real/openai, `/api/firebase/status`는 connected true를 캡처 도구가 확인했다. Chat 모델 표시는 현재 제공업체 설정이며 과거 메시지별 모델 이력이 저장된 것은 아니다. 기존 답변의 실제 GPT 사용 증빙은 사용자 보고/Usage와 함께 해석한다.

가상 기록 `ui-1791012665269-KIA_KIA` 추가 응답 201 → 별도 GET으로 date/score/is_manual 확인 → 화면 삭제 응답 성공·목록 제거 확인. Firestore 필수 운영 경로를 이용했으며 Firebase 콘솔 스크린샷이나 해당 기록의 서버 재시작 검증은 수행하지 않았다. 삭제한 가상 문서는 데이터 목록에서 제거됐고 삭제 보호 이력은 유지된다. 공식 경기·기존 대화 변경 없음.

두 실행 모두 새 GPT 호출 0. 각 접속의 sync POST 1회는 실제 상태 GET으로 대체했으므로 자동 갱신 재실행 증빙은 아니다. 추가/삭제는 데스크톱 화면에서 검증했으며 작은 화면에서는 목록 클릭·저장 대화/요약 표시·입력 폼의 viewport 내 배치를 확인했다. 새 모바일 GPT 질문/CRUD 전송, 실제 휴대폰 터치 조작은 별도 확인 항목이다.

에이전트가 위 7개 PNG를 직접 열어 질문/답변/요약·목록·가상 기록·Swagger 표시 및 비밀 키 노출 없음을 확인했다. 생산 환경 전체 장애/동시성/비용 상한 검증 완료를 의미하지 않는다.
