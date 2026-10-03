"""Read official recent schedule + bounded DB latest-date query. NO sync/state writes."""
import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from backend.services.game_sync_service import collect_window, validated_pairs, GameSyncService, utcnow, KST
from backend.services.firebase_service import get_firestore_client


def main():
    parser = argparse.ArgumentParser(description='Read-only official collection smoke test')
    parser.add_argument('--as-of', type=date.fromisoformat, default=utcnow().astimezone(KST).date() - timedelta(days=1))
    args = parser.parse_args()
    start = args.as_of - timedelta(days=6)
    rows = collect_window(start, args.as_of, lambda: None)
    pairs = validated_pairs(rows, args.as_of.year)
    result = {'mode': 'read_only_preview', 'checked_at': utcnow().isoformat(), 'start': start.isoformat(),
              'cutoff': args.as_of.isoformat(), 'source_records': len(rows), 'source_games': len(pairs),
              'source_latest_date': max((row['date'] for row in rows), default=None),
              'validation': 'PASS', 'firestore_writes': 0, 'ai_calls': 0}
    try:
        result['db_latest_game_date'] = GameSyncService().latest_date(get_firestore_client())
        result['latest_query'] = 'PASS'
    except Exception as error:
        result.update(latest_query='FAILED', error_type=type(error).__name__)
        if type(error).__name__ == 'FailedPrecondition' and 'index' in str(error).lower():
            result['error_code'] = 'INDEX_REQUIRED'
            urls = re.findall(r'https://console\.firebase\.google\.com/[^\s]+', str(error))
            if urls:
                result['index_creation_url'] = urls[0]
    output = Path(__file__).resolve().parents[2] / 'data/validation/GAME_SYNC_PREVIEW.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Read-only preview failed ({type(error).__name__}). No game/state writes or AI calls.') from None
