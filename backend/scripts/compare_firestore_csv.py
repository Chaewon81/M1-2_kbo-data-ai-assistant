"""Read-only season comparison. Never writes/deletes Firestore documents or calls AI."""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ('date', 'season', 'team', 'opponent', 'home_away', 'runs_for',
          'runs_against', 'result', 'run_diff', 'value', 'status', 'stadium')


def key(row):
    return f"{row['game_id']}_{row['team']}"


def compare(csv_rows, documents):
    expected = {key(row): row for row in csv_rows}
    actual = {doc_id: row for doc_id, row in documents}
    common = expected.keys() & actual.keys()
    changes = []
    for doc_id in sorted(common):
        changeset = {field: {'csv': expected[doc_id].get(field), 'firestore': actual[doc_id].get(field)}
                     for field in FIELDS if expected[doc_id].get(field) != actual[doc_id].get(field)}
        if changeset:
            changes.append({'id': doc_id, 'is_manual': actual[doc_id].get('is_manual', False), 'fields': changeset})
    keys = Counter(key(row) for _, row in documents if row.get('game_id') and row.get('team'))
    teams = sorted({row['team'] for row in csv_rows} | {row.get('team', '') for _, row in documents})
    summaries = []
    for team in teams:
        source = [row for row in csv_rows if row['team'] == team]
        db = [row for _, row in documents if row.get('team') == team and row.get('status', 'completed') == 'completed']
        summaries.append({'team': team, 'csv_count': len(source), 'firestore_completed_count': len(db),
                          'csv_latest_date': max((row['date'] for row in source), default=None),
                          'firestore_latest_date': max((row.get('date', '') for row in db), default=None)})
    missing_ids = sorted(expected.keys() - actual.keys())
    extra_ids = sorted(actual.keys() - expected.keys())
    return {'csv_count': len(csv_rows), 'firestore_count': len(documents),
            'csv_duplicate_keys': sorted(k for k, n in Counter(key(r) for r in csv_rows).items() if n > 1),
            'missing': [{'id': i, 'date': expected[i]['date'], 'team': expected[i]['team']} for i in missing_ids],
            'extra': [{'id': i, 'game_id': actual[i].get('game_id'), 'team': actual[i].get('team'),
                       'is_manual': actual[i].get('is_manual', False)} for i in extra_ids],
            'differences': changes, 'manual_ids': sorted(i for i, row in documents if row.get('is_manual') is True),
            'duplicate_game_team_keys': sorted(k for k, n in keys.items() if n > 1),
            'document_id_mismatches': [{'id': i, 'expected_id': key(row)} for i, row in documents
                                     if row.get('game_id') and row.get('team') and i != key(row)],
            'teams': summaries,
            'limitations': ['같은 날짜·팀의 다른 ID를 자동 통합하지 않음(더블헤더 보호)',
                            'CSV와의 비교이며 KBO 공식 페이지를 재수집한 검증은 아님',
                            'Firestore 쓰기·삭제 없음. is_manual 기록도 변경 없음']}


def main():
    parser = argparse.ArgumentParser(description='Read-only Firestore/CSV season audit')
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--input')
    parser.add_argument('--output', default='data/validation/FIRESTORE_CSV_COMPARISON.json')
    args = parser.parse_args()
    source = ROOT / (args.input or f'data/games/game_results_{args.season}.csv')
    from backend.scripts.import_to_firestore import row_to_document
    from backend.services.firebase_service import get_firestore_client
    from google.cloud.firestore_v1.base_query import FieldFilter
    with source.open(encoding='utf-8-sig', newline='') as file:
        rows = [row_to_document(row)[1] for row in csv.DictReader(file)
                if int(row['season']) == args.season and row.get('status', 'completed') == 'completed']
    client = get_firestore_client()
    query = client.collection('data').where(filter=FieldFilter('season', '==', args.season))
    documents = [(doc.id, doc.to_dict()) for doc in query.stream(timeout=30, retry=None)]
    report = compare(rows, documents)
    report.update({'checked_at': datetime.now(timezone.utc).isoformat(), 'season': args.season,
                   'source_csv': source.relative_to(ROOT).as_posix()})
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'season': args.season, 'csv_count': report['csv_count'],
                      'firestore_count': report['firestore_count'], 'missing': len(report['missing']),
                      'extra': len(report['extra']), 'differences': len(report['differences']),
                      'manual': len(report['manual_ids']), 'teams': report['teams']}, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Read-only audit failed ({type(error).__name__}). Check CSV, credentials, access, quota and network; no Firestore writes performed.') from None
