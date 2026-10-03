"""로컬 CSV로 투수 API와 예측 흐름을 검증한다. Firestore/AI 호출 없음."""
import os
import unittest
from unittest.mock import patch

from backend.scripts.build_pitcher_stats import TEAM_NAMES


class PitcherIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {
            "DATA_PATH": "M1-1_summary/data/raw/game_results_10teams_2026.csv",
            "PITCHER_DATA_PATH": "data/raw/pitcher_stats.csv",
            "OPENAI_MOCK_MODE": "true",
        }):
            with patch("backend.services.firebase_service.get_firestore_client", side_effect=RuntimeError("local test")):
                from backend.main import app
            cls.client = TestClient(app)

    def test_all_teams_and_player_ids(self):
        response = self.client.get("/api/pitchers", params={"season": 2026})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 30)
        self.assertEqual(data["invalid_count"], 0)
        self.assertEqual(data["duplicate_count"], 0)
        for code in TEAM_NAMES:
            team = self.client.get("/api/pitchers", params={"season": 2026, "team": code}).json()
            self.assertEqual(team["count"], 3)
            for row in team["items"]:
                individual = self.client.get("/api/pitchers", params={
                    "season": 2026, "team": code, "player_id": row["player_id"],
                }).json()
                self.assertEqual(individual["count"], 1)

    def test_predictions_with_optional_pitchers(self):
        request = dict(team_a="KIA", team_b="LG", season=2026, last_n=10)
        base = self.client.post("/api/predictions", json=request)
        self.assertEqual(base.status_code, 200)
        self.assertFalse(base.json()["pitcher_stats_applied"])
        applied = self.client.post("/api/predictions", json=dict(
            request, pitcher_a_id="77637", pitcher_b_id="55348",
        ))
        self.assertEqual(applied.status_code, 200)
        self.assertTrue(applied.json()["pitcher_stats_applied"])
        self.assertEqual(applied.json()["pitcher_stats_as_of"]["team_a"], "2026-10-01")
        partial = self.client.post("/api/predictions", json=dict(request, pitcher_a_id="77637"))
        self.assertEqual(partial.status_code, 200)
        self.assertFalse(partial.json()["pitcher_stats_applied"])
        mismatch = self.client.post("/api/predictions", json=dict(
            request, pitcher_a="INVALID", pitcher_a_id="77637",
        ))
        self.assertEqual(mismatch.status_code, 422)


if __name__ == "__main__":
    unittest.main()
