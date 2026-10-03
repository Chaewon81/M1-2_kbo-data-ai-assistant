# GitHub 최초 업로드 사전 점검

대상: `https://github.com/Chaewon81/M1-2_kbo-data-ai-assistant`.

## 현재 판정

업로드 후보 텍스트에서 알려진 로컬 비밀 값과 API 토큰/비공개 키/서비스 계정 JSON 패턴이 발견되지 않았다. 서비스 계정 파일은 Downloads의 외부 파일이며 업로드 대상이 아니다. 이미지·PDF 확인도 진행했다. 자동 검사는 모든 종류의 비밀을 보장하는 검사가 아니며 최종 staged 내용도 다시 검사한다.

**GitHub API 확인: private=false, can_push=true.** 사용자가 공개 저장소로 진행하기로 선택했다. 공개 범위는 바꾸지 않는다.

## 업로드 예정

- backend: API·서비스·모델·실행/수집/검증 스크립트 및 빈 환경변수 예시
- frontend: HTML/CSS/JS·공개 API URL 빌드 설정 (키 없음)
- 시즌별 CSV·KBO 원본 스냅샷·비밀 없는 검증 결과
- README·PRD·미션 설명·개발/학습/재개 문서
- 직접 확인한 화면 캡처·분석 차트
- M1-1 참고 수집기·분석 코드·자료 (배포 수집기가 일부 재사용)
- .gitignore·vercel.json

원본 단계 후보 검사: 383개, 약 21.24MiB (추가 검사 도구/문서 전의 목록으로 최종 파일 수는 다시 집계한다). 변경 후 최종 목록·staged 비밀 검사·ignore 확인을 수행한다.

## 업로드 제외

- 실제 `.env`, `.env.*` (빈 `.env.example`만 포함)
- 서비스 계정 JSON·adminsdk 파일·비공개 키 인증서
- `.venv`, Python 캐시, 로컬 패키지·`.tools`
- KBO 쿠키 파일·HAR·로그·임시 빌드/배포 산출물
- 원칙적으로 JSON은 제외. vercel 설정과 검토한 검증 JSON 파일명만 명시적 예외 허용

이미지: picture의 Chat/갱신 캡처, validation의 메인/상태 화면, M1-1 분석 차트 6개를 직접 열어 확인했다. 과제 PDF는 7페이지 텍스트를 추출해 비밀 패턴/로컬 비밀 값 검사를 수행했다. PDF 모든 이미지에 대한 OCR 검사까지 완료한 것은 아니다.

## Git 상태와 다음 단계

기존 로컬 Git 저장소/커밋 이력은 없었다. main 저장소를 초기화하고 지정한 origin을 등록했다. 파일 소유권 표시가 없는 Windows 파일시스템의 Git 보호 때문에 이 작업 폴더에 한정한 명령별 safe.directory 설정을 사용한다. 전역 safe.directory는 변경하지 않았다.

원격 ls-remote는 비어 있었다. 기존 원격 커밋을 덮어쓰거나 force push하지 않는다. 인증 토큰은 Git credential helper에서 내부적으로 사용하며 출력·파일 저장하지 않는다.

다음: 파일 목록·ignore 재검증 → staging → staged 비밀 검사 → 첫 커밋 → origin main push → 로컬/원격 커밋 일치 확인. 업로드가 실제 완료된 뒤에만 완료로 표시한다.
