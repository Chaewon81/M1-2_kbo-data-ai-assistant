"""Persistent deletion markers shared by CRUD and future automatic synchronization."""
from datetime import datetime, timezone
import random
import time
from google.api_core.exceptions import Aborted
from google.cloud import firestore

DELETION_COLLECTION = 'data_deletions'


class DeletedRecordError(ValueError):
    pass


class ManualRecordError(ValueError):
    pass


def transactionally(client, operation, on_retry=None):
    # Installed SDK retries Aborted at COMMIT, but an Aborted during a read/
    # operation escapes its retry loop. Restart the WHOLE operation in a fresh
    # transaction so tombstones, manual flags and scores are read again.
    # Only definite Aborted is retried here, never an uncertain timeout/write.
    for attempt in range(3):
        try:
            return firestore.transactional(operation)(client.transaction(max_attempts=3))
        except Aborted:
            if attempt == 2:
                raise
            if on_retry is not None:
                on_retry({'kind': 'operation_aborted', 'next_attempt': attempt + 2})
            time.sleep(random.uniform(0.05, 0.15) * (2 ** attempt))


def deletion_marker(item_id, data):
    return {'record_id': item_id, 'game_id': data.get('game_id'), 'team': data.get('team'),
            'season': data.get('season'), 'date': data.get('date'),
            'deleted_at': datetime.now(timezone.utc).isoformat(), 'reason': 'user_deleted'}


def delete_with_marker(client, item_id):
    reference = client.collection('data').document(item_id)
    marker = client.collection(DELETION_COLLECTION).document(item_id)

    def operation(transaction):
        # Same marker-before-record lock order as update/create avoids one known
        # deadlock pattern. Reading the marker also fences concurrent creation.
        marker.get(transaction=transaction, timeout=10, retry=None)
        snapshot = reference.get(transaction=transaction, timeout=10, retry=None)
        if not snapshot.exists:
            return False
        # Marker and deletion commit atomically. A concurrent sync reading the marker
        # must retry and skip this record; data-only existence checks are insufficient.
        transaction.set(marker, deletion_marker(item_id, snapshot.to_dict()))
        transaction.delete(reference)
        return True

    return transactionally(client, operation)


def create_unless_deleted(client, item_id, data):
    reference = client.collection('data').document(item_id)
    marker = client.collection(DELETION_COLLECTION).document(item_id)

    def operation(transaction):
        if marker.get(transaction=transaction, timeout=10, retry=None).exists:
            raise DeletedRecordError('사용자가 삭제한 기록입니다. 자동/일반 추가로 복원하지 않습니다.')
        current = reference.get(transaction=transaction, timeout=10, retry=None)
        if current.exists and current.to_dict().get('is_manual') is True:
            raise ManualRecordError('수동 수정된 기록입니다. 적재/일반 추가로 덮어쓰지 않습니다. 수정 API를 사용하세요.')
        transaction.set(reference, data, merge=True)

    transactionally(client, operation)


def update_unless_deleted(client, item_id, transform):
    reference = client.collection('data').document(item_id)
    marker = client.collection(DELETION_COLLECTION).document(item_id)

    def operation(transaction):
        if marker.get(transaction=transaction, timeout=10, retry=None).exists:
            return None
        current = reference.get(transaction=transaction, timeout=10, retry=None)
        if not current.exists:
            return None
        # Derive scores from THIS attempt's snapshot, including on SDK conflict retry.
        changed = transform(current.to_dict())
        transaction.update(reference, changed)
        return changed

    return transactionally(client, operation)


def create_pair_unless_deleted(client, pair, apply=False):
    references = [client.collection('data').document(item_id) for item_id, _ in pair]
    markers = [client.collection(DELETION_COLLECTION).document(item_id) for item_id, _ in pair]

    def operation(transaction=None):
        refs = [*references, *markers]
        snapshots = list(client.get_all(refs, transaction=transaction, timeout=10, retry=None))
        by_path = {snapshot.reference.path: snapshot for snapshot in snapshots}
        if set(by_path) != {reference.path for reference in refs}:
            raise RuntimeError('Incomplete read; no writes allowed.')
        if any(by_path[reference.path].exists for reference in markers):
            return {'status': 'skipped_deleted_pair',
                    'deleted_ids': [reference.id for reference in markers if by_path[reference.path].exists]}
        if any(by_path[reference.path].exists for reference in references):
            return {'status': 'skipped_existing_pair',
                    'existing_ids': [reference.id for reference in references if by_path[reference.path].exists]}
        if not apply:
            return {'status': 'would_create_pair'}
        for reference, (_, data) in zip(references, pair):
            transaction.create(reference, data)
        return {'status': 'created_pair'}

    # Reads of all data/marker documents are in the SAME transaction as the creates.
    # Concurrent marker creation invalidates the transaction's prior absent read.
    return transactionally(client, operation) if apply else operation()
