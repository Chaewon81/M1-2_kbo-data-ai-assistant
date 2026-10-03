# 누락 경기 안전 보충 — 2026-10-02

현재 상태: **CSV/Firestore 재비교 및 Summary 보존 검증 PASS**. 사용자 `--apply` 결과는 10경기 모두 이미 있어 건너뜀, 생성 0건이었다. 이후 양쪽 1360건, 누락·추가·비교 필드 차이·중복·문서 ID 불일치 0을 확인했다. 어떤 이전 실행이 누락분을 넣었는지는 확정하지 않는다. 아래 미리보기/검증 대기 내용은 이전 단계 기록이다.

## 기존 전체 적재 대신 이 스크립트를 사용하는 이유

`import_to_firestore.py`는 기존 비수동 데이터도 변경할 수 있으므로 이번 누락 보충에는 사용하지 않는다. 현재는 행별 트랜잭션에서 삭제 이력과 기존 `is_manual=true`를 확인하고 해당 행을 제외한다. 행별 적재이므로 경기 양쪽의 동시 변경까지 보장하지 않으며 자동 정정에는 별도 경기별 트랜잭션이 필요하다.

`repair_missing_games.py`는 비교 보고서의 누락 ID만 선택한다. CSV·양 팀 검증 후 하나의 트랜잭션에서 양 팀 문서와 삭제 이력 4개를 읽는다. 삭제 이력이 있으면 `skipped_deleted_pair`, 이미 문서가 있으면 `skipped_existing_pair`로 경기 전체를 건너뛴다. 모두 없을 때만 같은 트랜잭션에서 `create` 2건을 수행한다. 이전 배치 방식은 삭제 이력 쓰기와의 경합을 보호하기 위해 트랜잭션으로 변경했다.

읽기 이후 문서나 삭제 이력이 생기면 트랜잭션 재시도/충돌로 처리한다. 기존 문서는 변경하지 않는다. 경기별 원자성이며 10경기 전체 원자성은 아니다. 중간 오류·시간 초과 시 앞 경기만 반영됐을 수 있으므로 재비교한다. 실서비스의 동시 요청 경합 검증은 아직 필요하다.

## 프로젝트 루트에서 실행

경로·Firestore 인증은 기존 루트 `.env`/현재 PowerShell 설정을 사용한다. 로컬 모드가 아니라 `LOCAL_CSV_MODE=false`여야 한다. 키·JSON을 공유하지 않는다.

1. 쓰기 없는 미리보기(이미 에이전트가 한 번 실행함):

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.repair_missing_games
```

현재 결과: `mode=read_only_preview`, `candidate_games=10`, `candidate_records=20`, `created_records=0`, 10경기 모두 `would_create_pair`. 이 결과는 이후 실행까지 문서가 비어 있을 것을 보장하지 않으므로 실제 실행에서도 다시 읽는다.

2. **실제 DB 생성 — 사용자가 반영을 결정한 뒤 실행:**

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.repair_missing_games --apply
```

3. 바로 읽기 전용 재비교:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.compare_firestore_csv --season 2026
```

목표: CSV와 DB 각각 1360건, 누락·추가 ID·비교 필드 차이·중복·문서 ID 불일치 0. 수동 수정이나 동시 입력으로 차이가 생기면 강제로 덮어쓰지 말고 검토한다. `skipped_existing_pair`나 `failed_or_uncertain`이면 보충 완료로 표시하지 않고 재비교한다.

4. `/api/data/summary?team=KIA&season=2026&last_n=10` 조회. 현재 CSV 기준 09-12~09-30, 5승 5패, 승률 0.5 예상. 이 조회에는 GPT 비용이 없다.
5. 기존 대화 ID `8ef4e66d33f6495088aa41c86b24761b`를 다시 조회한다. 저장 Summary는 당시 09-10~09-26·6승 4패 그대로여야 한다. 최신 분석은 새 질문 1회로 확인할 수 있지만 자동 GPT 재호출은 하지 않는다.

## 검증과 범위

- 보충 로직 오프라인 테스트 7개 PASS, 비교 로직 테스트 3개 PASS.
- 실제 Firestore 미리보기 실행 PASS, 쓰기 0건. 결과: `data/validation/MISSING_GAMES_PREVIEW.json`.
- 이전 버전 `--apply`와 재비교는 사용자 실행으로 확인했고 모두 이미 있어 생성 0건이었다. 최신 삭제 보호 버전의 실제 DB 쓰기/동시 요청 검증은 아직 하지 않았다.
- 이 스크립트는 삭제 이력 보호가 있는 누락 보충용이다. 공식 정정·접속 시 자동 갱신 기능 자체는 아니다.
