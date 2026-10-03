# GitHub 최초 업로드 사전 점검

대상: `https://github.com/Chaewon81/M1-2_kbo-data-ai-assistant`.

## 업로드 결과

사용자가 Public으로 진행하기로 선택했다. GitHub API에서 `private=false`, `can_push=true` 확인 후 업로드했다. 385개 파일, staged 텍스트 374개 비밀 검사 PASS, 발견 0건. 로컬과 원격 main 모두 커밋 `92f0f3994cf7f46b8c132eaa880afb584dd77634`이며 작업 트리는 clean이다.

## 검사 범위

업로드 후보 텍스트에서 알려진 로컬 비밀 값과 API 토큰/비공개 키/서비스 계정 JSON 패턴이 발견되지 않았다. 서비스 계정 파일은 Downloads의 외부 파일이며 업로드 대상이 아니다. 이미지·PDF 확인도 진행했다. 자동 검사는 모든 종류의 비밀을 보장하는 검사가 아니며 최종 staged 내용도 다시 검사한다.

**GitHub API 확인: private=false, can_push=true.** 사용자가 공개 저장소로 진행하기로 선택했다. 공개 범위는 바꾸지 않는다.

## 포함 범위

- backend: API·서비스·모델·실행/수집/검증 스크립트 및 빈 환경변수 예시
- frontend: HTML/CSS/JS·공개 API URL 빌드 설정 (키 없음)
- 시즌별 CSV·KBO 원본 스냅샷·비밀 없는 검증 결과
- README·PRD·미션 설명·개발/학습/재개 문서
- 직접 확인한 화면 캡처·분석 차트
- M1-1 참고 수집기·분석 코드·자료 (배포 수집기가 일부 재사용)
- .gitignore·vercel.json

최종 후보/staged 파일 수는 385개다. 검사기는 알려진 토큰·키·서비스 계정 형태와 작업 폴더에서 읽은 알려진 로컬 비밀 값을 검사했으며 발견 사항이 없었다. 자동 패턴 검사는 모든 가능한 비밀을 보장하지 않는다.

## 업로드 제외

- 실제 `.env`, `.env.*` (빈 `.env.example`만 포함)
- 서비스 계정 JSON·adminsdk 파일·비공개 키 인증서
- `.venv`, Python 캐시, 로컬 패키지·`.tools`
- KBO 쿠키 파일·HAR·로그·임시 빌드/배포 산출물
- 원칙적으로 JSON은 제외. vercel 설정과 검토한 검증 JSON 파일명만 명시적 예외 허용

이미지: picture의 Chat/갱신 캡처, validation의 메인/상태 화면, M1-1 분석 차트 6개를 직접 열어 확인했다. 과제 PDF는 7페이지 텍스트를 추출해 비밀 패턴/로컬 비밀 값 검사를 수행했다. PDF 모든 이미지에 대한 OCR 검사까지 완료한 것은 아니다.

## 다음 단계

GitHub에는 첫 커밋을 정상 업로드했다. 실제 Render/Vercel 배포, 서비스 URL, 배포 후 GPT·CRUD·이전 대화 화면 캡처는 별도 작업이다. 실제 키를 README나 프론트엔드 빌드에 넣지 않는다.
