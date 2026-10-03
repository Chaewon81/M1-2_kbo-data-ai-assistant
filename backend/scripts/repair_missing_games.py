"""Fill only audited missing pairs. Default: read-only preview; --apply opts into writes."""
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from google.api_core.exceptions import AlreadyExists, Conflict
from backend.models.schemas import DataRecord
from backend.scripts.import_to_firestore import row_to_document
from backend.services.deletion_service import create_pair_unless_deleted

ROOT = Path(__file__).resolve().parents[2]
TEAMS = {'KIA', '삼성', 'LG', '두산', 'SSG', 'KT', '롯데', '한화', 'NC', '키움'}


def build_pairs(report, csv_rows, max_records=20):
    if any(report.get(field) for field in ('csv_duplicate_keys', 'extra', 'differences',
                                          'duplicate_game_team_keys', 'document_id_mismatches')):
        raise ValueError('Audit has conflicts; review before repair.')
    season = report['season']
    targets = {item['id'] for item in report['missing']}
    if len(targets) != len(report['missing']) or len(targets) > max_records:
        raise ValueError('Duplicate targets or missing-record limit exceeded.')
    documents = {}
    for row in csv_rows:
        if int(row['season']) != season or row.get('status', 'completed') != 'completed':
            continue
        doc_id, data = row_to_document(row)
        if doc_id not in targets:
            continue
        if doc_id in documents:
            raise ValueError('Duplicate target in CSV.')
        DataRecord.model_validate(data)
        if (data['team'] not in TEAMS or data['opponent'] not in TEAMS or
                data['team'] == data['opponent'] or date.fromisoformat(data['date']).year != season or
                not re.fullmatch(r'\d{8}[A-Z]{4}[0-2]', data['game_id']) or
                not data['game_id'].startswith(data['date'].replace('-', ''))):
            raise ValueError('Invalid official game identity.')
        expected = 'W' if data['runs_for'] > data['runs_against'] else 'L' if data['runs_for'] < data['runs_against'] else 'D'
        if data['result'] != expected:
            raise ValueError('Scores and result disagree.')
        documents[doc_id] = data
    if documents.keys() != targets:
        raise ValueError('Missing target not found in CSV.')
    grouped = defaultdict(list)
    for doc_id, data in documents.items():
        grouped[data['game_id']].append((doc_id, data))
    for pair in grouped.values():
        if len(pair) != 2:
            raise ValueError('Repair requires both audited missing team documents.')
        first, second = pair[0][1], pair[1][1]
        if (first['team'] != second['opponent'] or second['team'] != first['opponent'] or
                first['home_away'] == second['home_away'] or
                any(first[f] != second[f] for f in ('date', 'season', 'status', 'stadium')) or
                first['runs_for'] != second['runs_against'] or first['runs_against'] != second['runs_for']):
            raise ValueError('Invalid opposing game pair.')
    return [sorted(grouped[game_id]) for game_id in sorted(grouped)]


def repair_pair(client, pair, apply=False):
    try:
        return create_pair_unless_deleted(client, pair, apply)
    except (AlreadyExists, Conflict):
        # A concurrent document creation can still produce an existence conflict.
        return {'status': 'skipped_concurrent_create'}


def run(client, pairs, apply=False):
    results = []
    for pair in pairs:
        try:
            outcome = repair_pair(client, pair, apply)
        except Exception as error:
            results.append({'game_id': pair[0][1]['game_id'], 'ids': [i for i, _ in pair],
                            'status': 'failed_or_uncertain', 'error_type': type(error).__name__})
            break  # Some earlier pairs may already exist. Re-audit; never claim rollback.
        results.append({'game_id': pair[0][1]['game_id'], 'ids': [i for i, _ in pair], **outcome})
    return {'mode': 'apply' if apply else 'read_only_preview', 'candidate_games': len(pairs),
            'candidate_records': len(pairs) * 2, 'created_records': 2 * sum(r['status'] == 'created_pair' for r in results),
            'results': results,
            'needs_reaudit': apply or any(r['status'] != 'would_create_pair' for r in results)}


def main():
    parser = argparse.ArgumentParser(description='Create-only missing game repair (preview by default)')
    parser.add_argument('--report', default='data/validation/FIRESTORE_CSV_COMPARISON.json')
    parser.add_argument('--input')
    parser.add_argument('--max-records', type=int, default=20)
    parser.add_argument('--apply', action='store_true', help='Explicitly create absent pairs; otherwise read-only')
    parser.add_argument('--output', help='Separate preview/apply result file')
    args = parser.parse_args()
    if args.max_records < 1:
        raise ValueError('max-records must be >= 1')
    report = json.loads((ROOT / args.report).read_text(encoding='utf-8'))
    source = ROOT / (args.input or report['source_csv'])
    with source.open(encoding='utf-8-sig', newline='') as file:
        pairs = build_pairs(report, list(csv.DictReader(file)), args.max_records)
    from backend.services.firebase_service import get_firestore_client
    result = run(get_firestore_client(), pairs, args.apply)
    result.update({'checked_at': datetime.now(timezone.utc).isoformat(), 'season': report['season'],
                   'audit_report': args.report})
    output = ROOT / (args.output or f'data/validation/MISSING_GAMES_{"APPLY" if args.apply else "PREVIEW"}.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    if any(row['status'] == 'failed_or_uncertain' for row in result['results']):
        raise SystemExit('Repair interrupted; earlier pairs may be committed. Re-audit before retrying.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Repair stopped ({type(error).__name__}); inspect inputs/credentials/quota and re-audit. No existing documents are overwritten.') from None
