from fastapi import APIRouter, HTTPException, Query, status

from backend.models.schemas import (
    ConversationCreate,
    ConversationListResponse,
    ConversationRecord,
    ConversationSummary,
)
from backend.services.conversation_store import conversation_store


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRecord, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate) -> ConversationRecord:
    return conversation_store.create(payload)


@router.get("", response_model=ConversationListResponse)
def list_conversations(limit: int = Query(default=50, ge=1, le=100)) -> ConversationListResponse:
    items = conversation_store.list(limit=limit)
    return ConversationListResponse(count=len(items), items=items)


@router.get("/{conversation_id}", response_model=ConversationRecord)
def get_conversation(conversation_id: str) -> ConversationRecord:
    item = conversation_store.get(conversation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return item


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, str]:
    if not conversation_store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"status": "deleted", "id": conversation_id}
