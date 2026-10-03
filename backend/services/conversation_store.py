from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.models.schemas import ConversationCreate, ConversationMessage, ConversationRecord
from backend.services.firebase_service import get_firestore_client, firestore_required, StorageUnavailableError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ConversationStore:
    """Firestore에 대화를 저장하고, Firebase 미연결 시 개발용 메모리를 사용한다."""

    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def _db(self):
        try:
            return get_firestore_client()
        except Exception as error:
            if firestore_required():
                raise StorageUnavailableError("Firestore 대화 저장소에 연결하지 못했습니다. 메모리로 전환하지 않습니다.") from error
            return None

    def save_exchange(self, conversation_id: str | None, user: str, answer: str, summary: dict) -> ConversationRecord:
        """두 메시지와 Summary를 같은 문서에 한 번에 저장한다."""
        now = now_utc()
        messages = [ConversationMessage(role="user", content=user, created_at=now),
                    ConversationMessage(role="assistant", content=answer, created_at=now)]
        if conversation_id is None:
            return self.create(ConversationCreate(title=user[:60], messages=messages, summary=summary))
        current = self.get(conversation_id)
        if current is None:
            raise ValueError("conversation not found")
        updated = current.model_copy(update={"messages": [*current.messages, *messages],
            "updated_at": now, "summary": summary,
            "title": user[:60] if current.title == "새 대화" else current.title})
        db = self._db()
        data = updated.model_dump(mode="json", exclude={"id"})
        if db is not None:
            self._collection(db).document(conversation_id).set(data)
        else:
            self._items[conversation_id] = data
        return updated

    @staticmethod
    def _collection(db):
        return db.collection("conversations")

    def create(self, payload: ConversationCreate) -> ConversationRecord:
        now = now_utc()
        conversation_id = uuid4().hex
        messages = [
            (message.model_copy(update={"created_at": message.created_at or now}))
            for message in payload.messages
        ]
        record = ConversationRecord(
            id=conversation_id,
            title=payload.title,
            created_at=now,
            updated_at=now,
            messages=messages,
            summary=payload.summary,
        )
        data = record.model_dump(mode="json")
        db = self._db()
        if db is not None:
            self._collection(db).document(conversation_id).set(data)
        else:
            self._items[conversation_id] = data
        return record

    def list(self, limit: int = 50) -> list[dict]:
        db = self._db()
        if db is not None:
            items = [{"id": doc.id, **doc.to_dict()} for doc in self._collection(db).stream()]
        else:
            items = [{"id": item_id, **value} for item_id, value in self._items.items()]
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return [
            {
                "id": item["id"],
                "title": item.get("title", "새 대화"),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            }
            for item in items[:limit]
        ]

    def get(self, conversation_id: str) -> ConversationRecord | None:
        db = self._db()
        if db is not None:
            snapshot = self._collection(db).document(conversation_id).get()
            if not snapshot.exists:
                return None
            data = {"id": snapshot.id, **snapshot.to_dict()}
        else:
            value = self._items.get(conversation_id)
            if value is None:
                return None
            data = {"id": conversation_id, **value}
        return ConversationRecord.model_validate(data)

    def append_message(self, conversation_id: str, message: ConversationMessage, summary: dict | None = None) -> ConversationRecord | None:
        current = self.get(conversation_id)
        if current is None:
            return None
        now = now_utc()
        updated_messages = [*current.messages, message.model_copy(update={"created_at": message.created_at or now})]
        title = current.title
        if title == "새 대화" and message.role == "user":
            title = message.content[:60]
        updated = current.model_copy(
            update={
                "title": title,
                "updated_at": now,
                "messages": updated_messages,
                "summary": summary if summary is not None else current.summary,
            }
        )
        data = updated.model_dump(mode="json", exclude={"id"})
        db = self._db()
        if db is not None:
            self._collection(db).document(conversation_id).set(data)
        else:
            self._items[conversation_id] = data
        return updated

    def delete(self, conversation_id: str) -> bool:
        db = self._db()
        if db is not None:
            reference = self._collection(db).document(conversation_id)
            if not reference.get().exists:
                return False
            reference.delete()
            return True
        return self._items.pop(conversation_id, None) is not None


conversation_store = ConversationStore()
