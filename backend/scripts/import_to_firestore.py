from __future__ import annotations

import csv
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.services.firebase_service import get_firestore_client
from backend.services.deletion_service import create_unless_deleted, DeletedRecordError, ManualRecordError


def source_path(input_path: str | None = None) -> Path:
    path = Path(input_path) if input_path else Path(settings.data_path)
    return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path


def row_to_document(row: dict[str, str]) -> tuple[str, dict]:
    runs_for = int(row["runs_for"])
    runs_against = int(row["runs_against"])
    game_id = row["game_id"]
    team = row["team"]
    document_id = f"{game_id}_{team}"
    return document_id, {
        "game_id": game_id,
        "date": row["date"],
        "season": int(row["season"]),
        "team": team,
        "opponent": row["opponent"],
        "home_away": row["home_away"],
        "runs_for": runs_for,
        "runs_against": runs_against,
        "run_diff": runs_for - runs_against,
        "value": runs_for - runs_against,
        "result": row["result"],
        "status": row.get("status") or "completed",
        "stadium": row.get("stadium", ""),
        "memo": f"{team} {runs_for}:{runs_against} {row['opponent']}",
        "source_url": row.get("source_url", ""),
        "is_manual": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV 경기 데이터를 Firestore에 적재")
    parser.add_argument("--input", help="적재할 CSV 경로 (기본값: DATA_PATH)")
    args = parser.parse_args()
    path = source_path(args.input)
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")

    client = get_firestore_client()
    imported = 0
    skipped_deleted = 0
    skipped_manual = 0
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        for row in rows:
            if row.get("status") not in (None, "", "completed"):
                continue
            document_id, document = row_to_document(row)
            try:
                create_unless_deleted(client, document_id, document)
            except DeletedRecordError:
                skipped_deleted += 1
                continue
            except ManualRecordError:
                skipped_manual += 1
                continue
            imported += 1

    print(f"Firestore data 적재 완료: {imported}건")
    print(f"삭제 이력 보호로 제외: {skipped_deleted}건")
    print(f"수동 수정 보호로 제외: {skipped_manual}건")
    print("문서 ID 기준: {game_id}_{team}")


if __name__ == "__main__":
    main()
