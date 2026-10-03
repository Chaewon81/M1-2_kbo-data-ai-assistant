from __future__ import annotations

import csv
from pathlib import Path

from backend.config import settings
from backend.models.schemas import DataCreate, DataRecord, DataUpdate
from backend.services.firebase_service import get_firestore_client, firestore_required, StorageUnavailableError
from backend.services.deletion_service import DeletedRecordError, ManualRecordError, deletion_marker, delete_with_marker, create_unless_deleted, update_unless_deleted


class DataStore:
    """개발 1단계용 저장소. Firestore 연결 전에는 메모리에서 동작한다."""

    def __init__(self) -> None:
        self._items: dict[str, DataRecord] = {}
        self._deletions: dict[str, dict] = {}
        self._db = None
        try:
            self._db = get_firestore_client()
        except Exception:
            if firestore_required():
                raise StorageUnavailableError("Firestore 필수 모드에서 연결에 실패했습니다. CSV·메모리로 전환하지 않습니다.")
            # Firebase 연결 전 로컬 개발을 위해 CSV 메모리 저장소로 fallback한다.
            self.load_csv()

    @staticmethod
    def item_id(item: DataRecord) -> str:
        return f"{item.game_id}_{item.team}"

    @staticmethod
    def with_id(item: DataRecord, item_id: str) -> DataRecord:
        return item.model_copy(update={"id": item_id})

    def load_csv(self) -> None:
        for source in settings.data_paths or (settings.data_path,):
            self._load_csv_file(source)

    def _load_csv_file(self, source: str) -> None:
        path = Path(source)
        if not path.is_absolute():
            # 실행 위치가 프로젝트 루트 또는 다른 폴더여도 같은 CSV를 찾는다.
            path = Path(__file__).resolve().parents[2] / path
        if not path.exists():
            return
        with path.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                # processed CSV는 이미 완료 경기만 남긴 파일이라 status 컬럼이 없다.
                # raw CSV를 사용할 때만 status로 완료 여부를 필터링한다.
                if row.get("status") not in (None, "", "completed"):
                    continue
                runs_for = int(row["runs_for"])
                runs_against = int(row["runs_against"])
                item = DataRecord(
                    date=row["date"],
                    season=int(row["season"]),
                    team=row["team"],
                    opponent=row["opponent"],
                    home_away=row["home_away"],
                    runs_for=runs_for,
                    runs_against=runs_against,
                    result=row["result"],
                    run_diff=runs_for - runs_against,
                    value=runs_for - runs_against,
                    status="completed",
                    stadium=row.get("stadium", ""),
                    game_id=row["game_id"],
                    memo=f"{row['team']} {runs_for}:{runs_against} {row['opponent']}",
                    source_url=row.get("source_url", ""),
                )
                # 파일 간 같은 경기·팀은 1건만 유지한다. 나중 경로의 기록이 우선한다.
                if self.item_id(item) not in self._deletions:
                    self._items[self.item_id(item)] = item

    def list(self, team: str | None = None, season: int | None = None, limit: int = 100) -> list[DataRecord]:
        if self._db is not None:
            from google.cloud.firestore_v1.base_query import FieldFilter
            query = self._db.collection("data")
            # Single equality uses built-in indexes; narrow reads before Python filters.
            # Prefer team (~4 seasons) to season (~10 teams), without adding another index requirement.
            if team:
                query = query.where(filter=FieldFilter('team', '==', team))
            elif season:
                query = query.where(filter=FieldFilter('season', '==', season))
            items = [self.with_id(DataRecord.model_validate(doc.to_dict()), doc.id) for doc in query.stream()]
            if team:
                items = [item for item in items if item.team == team]
            if season:
                items = [item for item in items if item.season == season]
            items.sort(key=lambda item: (item.date, item.game_id, item.team), reverse=True)
            return [self.with_id(item, self.item_id(item)) for item in items[:limit]]
        items = list(self._items.values())
        if team:
            items = [item for item in items if item.team == team]
        if season:
            items = [item for item in items if item.season == season]
        items.sort(key=lambda item: (item.date, item.game_id, item.team), reverse=True)
        return [self.with_id(item, self.item_id(item)) for item in items[:limit]]

    def get(self, item_id: str) -> DataRecord | None:
        if self._db is not None:
            snapshot = self._db.collection("data").document(item_id).get()
            return self.with_id(DataRecord.model_validate(snapshot.to_dict()), snapshot.id) if snapshot.exists else None
        item = self._items.get(item_id)
        return self.with_id(item, item_id) if item else None

    def create(self, item: DataCreate) -> DataRecord:
        record = DataRecord.model_validate(item)
        if record.game_id.startswith("ui-"):
            record = record.model_copy(update={"is_manual": True})
        if self._db is not None:
            create_unless_deleted(self._db, self.item_id(record), record.model_dump(mode="json"))
            return self.with_id(record, self.item_id(record))
        if self.item_id(record) in self._deletions:
            raise DeletedRecordError('사용자가 삭제한 기록입니다. 일반 추가로 복원하지 않습니다.')
        existing = self._items.get(self.item_id(record))
        if existing is not None and existing.is_manual:
            raise ManualRecordError('수동 수정된 기록입니다. 일반 추가로 덮어쓰지 않습니다. 수정 API를 사용하세요.')
        self._items[self.item_id(record)] = record
        return self.with_id(record, self.item_id(record))

    def update(self, item_id: str, update: DataUpdate) -> DataRecord | None:
        update_values = update.model_dump(exclude_unset=True)
        # Public PUT is a user modification, never an authorization to unlock protection.
        # Official synchronization must use a separate protected service, not this route.
        update_values["is_manual"] = True

        def transform(current):
            changed = {**current, **update_values}
            if "runs_for" in update_values or "runs_against" in update_values:
                runs_for, runs_against = changed.get('runs_for'), changed.get('runs_against')
                if runs_for is None or runs_against is None:
                    changed.update(run_diff=None, value=None, result=None)
                else:
                    difference = runs_for - runs_against
                    changed.update(run_diff=difference, value=difference,
                                   result='W' if difference > 0 else 'L' if difference < 0 else 'D')
            return DataRecord.model_validate(changed).model_dump(mode='json')

        if self._db is not None:
            changed = update_unless_deleted(self._db, item_id, transform)
            return self.with_id(DataRecord.model_validate(changed), item_id) if changed is not None else None
        if item_id in self._deletions:
            return None
        current = self._items.get(item_id)
        if current is None:
            return None
        changed = DataRecord.model_validate(transform(current.model_dump(mode='json')))
        self._items[item_id] = changed
        return self.with_id(changed, item_id)

    def delete(self, item_id: str) -> bool:
        if self._db is not None:
            return delete_with_marker(self._db, item_id)
        current = self._items.get(item_id)
        if current is None:
            return False
        self._deletions[item_id] = deletion_marker(item_id, current.model_dump(mode='json'))
        del self._items[item_id]
        return True


store = DataStore()
