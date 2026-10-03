"""실제 시즌별 CSV의 경기·투수·예측 API 통합 검증. 외부 서비스 쓰기 없음."""
import unittest
from collections import Counter, defaultdict
from dataclasses import replace
from unittest.mock import patch

from backend.config import settings, season_files
from backend.scripts.build_pitcher_stats import TEAM_NAMES


class SeasonDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        with patch('backend.services.firebase_service.get_firestore_client', side_effect=RuntimeError('local CSV test')):
            import backend.services.data_store as games
            import backend.services.pitcher_service as pitchers
            import backend.services.prediction_service as predictions
            from backend.routers import data, summary, pitchers as pitcher_router, predictions as prediction_router
        cfg = replace(settings,
            data_paths=season_files('data/games', 'game_results'),
            pitcher_data_paths=season_files('data/pitchers', 'pitcher_stats'))
        patchers = [patch.object(games, 'settings', cfg), patch.object(pitchers, 'settings', cfg)]
        for p in patchers:
            p.start()
            cls.addClassCleanup(p.stop)
        with patch.object(games, 'get_firestore_client', side_effect=RuntimeError('CSV test')):
            cls.store = games.DataStore()
        for module in (predictions, data, summary):
            p = patch.object(module, 'store', cls.store)
            p.start()
            cls.addClassCleanup(p.stop)
        app = FastAPI()
        for router in (summary.router, data.router, pitcher_router.router, prediction_router.router):
            app.include_router(router)
        cls.client = TestClient(app)

    def test_games_counts_ids_and_doubleheaders(self):
        items = self.store.list(limit=100000)
        self.assertEqual(len(items), len({x.id for x in items}))
        for year in (2023, 2024, 2025):
            counts = Counter(x.team for x in items if x.season == year)
            self.assertEqual(len(counts), 10)
            self.assertEqual(set(counts.values()), {144})
        pairs = defaultdict(list)
        day_games = defaultdict(set)
        for x in items:
            self.assertRegex(x.game_id, r'^\d{8}[A-Z]{4}\d$')
            self.assertEqual(x.date.strftime('%Y%m%d'), x.game_id[:8])
            pairs[x.game_id].append(x)
            day_games[(x.date, x.team)].add(x.game_id)
        self.assertTrue(any(len(ids) == 2 for ids in day_games.values()))
        self.assertTrue(all(len(pair) == 2 for pair in pairs.values()))

    def test_all_season_team_queries(self):
        total = self.client.get('/api/pitchers').json()
        self.assertEqual(total['count'], 120)
        self.assertEqual((total['invalid_count'], total['duplicate_count']), (0, 0))
        for year in (2023, 2024, 2025, 2026):
            for team in TEAM_NAMES.values():
                stats = self.client.get('/api/pitchers', params={'season': year, 'team': team}).json()
                self.assertEqual(stats['count'], 3)
                summary = self.client.get('/api/data/summary', params={'season': year, 'team': team}).json()
                self.assertEqual(summary['count'], 144) if year < 2026 else self.assertGreater(summary['count'], 0)

    def test_season_specific_prediction_and_fallback(self):
        for year in (2023, 2024, 2025, 2026):
            a = self.client.get('/api/pitchers', params={'season': year, 'team': 'KIA'}).json()['items'][0]
            b = self.client.get('/api/pitchers', params={'season': year, 'team': 'LG'}).json()['items'][0]
            request = dict(team_a='KIA', team_b='LG', season=year, last_n=10)
            applied = self.client.post('/api/predictions', json=dict(request,
                pitcher_a=a['player'], pitcher_a_id=a['player_id'], pitcher_b=b['player'], pitcher_b_id=b['player_id']))
            self.assertEqual(applied.status_code, 200)
            self.assertTrue(applied.json()['pitcher_stats_applied'])
            if year < 2026:
                self.assertTrue(any('사전 예측 검증' in text for text in applied.json()['limitations']))
            for extra in ({}, {'pitcher_a_id': a['player_id']}, {'pitcher_a_id': 'not-found', 'pitcher_b_id': b['player_id']}):
                response = self.client.post('/api/predictions', json=dict(request, **extra))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['pitcher_stats_applied'])
            wrong_team = self.client.post('/api/predictions', json=dict(request, pitcher_a=a['player'], pitcher_a_id=b['player_id']))
            self.assertEqual(wrong_team.status_code, 422)


if __name__ == '__main__':
    unittest.main()
