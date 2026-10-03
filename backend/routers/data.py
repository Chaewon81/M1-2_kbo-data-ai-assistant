from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from backend.models.schemas import DataCreate, DataListResponse, DataRecord, DataUpdate
from backend.services.data_store import store
from backend.services.deletion_service import DeletedRecordError, ManualRecordError


router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("", response_model=DataListResponse)
def list_data(
    team: str | None = None,
    season: int | None = Query(default=None, ge=1900, le=2100),
    limit: int = Query(default=100, ge=1, le=1000),
) -> DataListResponse:
    items = store.list(team=team, season=season, limit=limit)
    return DataListResponse(count=len(items), items=items)


@router.get("/{item_id}", response_model=DataRecord)
def get_data(item_id: str) -> DataRecord:
    item = store.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="data record not found")
    return item


@router.post("", response_model=DataRecord, status_code=201)
def create_data(item: DataCreate) -> DataRecord:
    try:
        return store.create(item)
    except (DeletedRecordError, ManualRecordError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{item_id}", response_model=DataRecord)
def update_data(item_id: str, update: DataUpdate) -> DataRecord:
    try:
        item = store.update(item_id, update)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="수정 후 경기 데이터가 유효하지 않습니다. 상태와 필수 점수를 확인하세요.") from error
    if item is None:
        raise HTTPException(status_code=404, detail="data record not found")
    return item


@router.delete("/{item_id}")
def delete_data(item_id: str) -> dict[str, str]:
    if not store.delete(item_id):
        raise HTTPException(status_code=404, detail="data record not found")
    return {"status": "deleted", "id": item_id}
