# AI 제공업체와 과제 충족 상태

기준: 2026-10-01. 이 문서는 과제 요구사항과 실제 검증 상태를 구분한다.

최신 검증: 첫 GPT 답변의 CSV 수치 일치·Usage 542토큰 확인에 이어, 2026-10-02 사용자 보고로 제출용 서버 재시작 후 Firestore 대화·Summary 유지를 확인했다. 이번 답변은 저장 Summary와 일치했다. 실제 읽기 전용 비교에서는 DB에 CSV의 20개 팀 기록이 누락돼 있었으며, 최신성 보완·모델/Usage 캡처는 남았다. [검증 기록](data/validation/GPT_CHAT_VERIFICATION.md), [오늘 검토 Summary](M1-2_REVIEW_SUMMARY_2026-10-02.md).

최종 결정: 제출·시연에는 **OpenAI GPT-4o mini + 필수 Firestore**, 반복 개발에는 Mock·CSV·메모리를 사용한다. OpenRouter는 검토 이력이다. 제출 실행은 `.\backend\scripts\start_submission.ps1`. [영구 저장 검증 순서](FIRESTORE_VERIFICATION.md).

## 요구사항과 현재 선택

- 과제 원문은 OpenAI API 키 준비와 GPT API 호출을 요구한다.
- OpenAI 연결을 구현했고, 사용자 보고로 실제 응답과 Usage 542토큰을 확인했다.
- 개발 중 OpenRouter `openrouter/free` 옵션을 준비했지만, 과제 GPT 요구에 맞춰 최종 제출에는 OpenAI `gpt-4o-mini`를 선택했다. 해당 옵션은 검토 이력으로 보존한다.
- OpenRouter는 제공업체/모델 연결 서비스이고 OpenAI SDK는 호출 도구다. OpenAI SDK 사용만으로 GPT 모델 사용을 증명하지 않는다.
- `openrouter/free`는 GPT 사용 증빙이 아니므로 제출 경로로 사용하지 않는다. OpenAI GPT의 실제 호출 성공을 확인해 과제 증빙을 남긴다.
- 모의 제공업체 테스트와 사용자 GPT 실사용 확인을 구분한다. 2026-10-02 사용자 보고로 서버 재시작 후 Firestore 대화·Summary 유지를 확인했다. 실제 OpenRouter 응답은 미검증이며 필수 작업은 아니다.

## 설명할 때 사용할 답변

> 과제 요구에 맞춰 OpenAI GPT-4o mini를 직접 연결했습니다. 개발은 Mock, 제출 검증은 GPT와 필수 Firestore를 사용합니다. 무료 대안 OpenRouter도 검토했지만 제출 경로는 아닙니다. 사용자 테스트에서 실제 GPT 응답과 서버 재시작 후 대화·Summary 유지를 확인했습니다. 이전 GPT 호출의 Usage 542토큰도 보고받았습니다. 데이터 최신성 보완과 제출 캡처는 남아 있습니다.

실제 연결에 성공한 뒤에는 제공업체·요청 모델·응답 모델·확인 날짜·스크린샷을 남긴다. `configured: true` 또는 모의 테스트 성공은 실제 AI 호출 성공을 뜻하지 않는다. 제출 전 실제 검증 결과에 맞게 답변을 갱신한다.

현재 Chat 응답의 `model`은 요청 설정 모델명이다. `openrouter/free`가 반환되었다고 실제 선택된 모델이 GPT라는 뜻은 아니다. 라우터가 실제 선택한 모델을 증명하려면 제공업체 Activity 또는 원본 응답 등 추가 증빙이 필요하다.

## 과거 OpenRouter 검토 메모 — 현재 실행 안내가 아님

`Credit limit`은 이 API 키가 사용할 수 있는 **달러 기준 지출 상한**이다. 무료 요청 횟수 설정도 아니고 지급받는 크레딧도 아니다. 화면의 `Key limit`이 같은 비용 입력란을 뜻하는지는 단위/설명을 확인한다.

무료만 원한다면 비용 상한 입력에 0이 허용될 때 0을 설정해 유료 지출을 허용하지 않는 방향으로 시작한다. 다만 한도 0에서 무료 호출까지 허용되는지는 공식 문서만으로 확정하지 못했으므로 성공을 보장하지 않는다. 생성 또는 호출이 막히면 오류 메시지를 확인하고, 자동으로 무제한이나 유료 상한으로 바꾸지 않는다.

빈값/무제한은 비용 제한이 없다는 뜻이지 무료라는 뜻이 아니다. 카드 등록·크레딧 충전·자동 충전은 무료 테스트를 위해 진행하지 않는다. 모델 설정은 `OPENROUTER_MODEL=openrouter/free`를 유지한다. 무료 모델에도 별도 요청 횟수·가용성 제한이 있다.

공식 근거: [키 인증·지출 상한](https://openrouter.ai/docs/api_reference/authentication), [키 생성의 USD limit 정의](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key), [무료 요청 제한](https://openrouter.ai/docs/api_reference/limits), [무료 모델 라우터](https://openrouter.ai/openrouter/free).

## 제출 전 남은 확인

1. OpenAI 키·크레딧 준비 후 실제 GPT 응답·Summary 근거·대화 저장 확인 및 증빙.
2. Usage에서 실제 사용량 확인. 반복 개발은 Mock, 자동 충전은 끄고 공개 배포 전 요청 제한 준비.
3. Firestore 영구 저장·배포·제출 스크린샷 검증. 로컬 CSV·메모리 모드는 Firestore 검증을 대신하지 않음.
