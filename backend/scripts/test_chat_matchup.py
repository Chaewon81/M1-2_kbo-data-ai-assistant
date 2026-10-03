"""Synthetic matchup regression tests. No DB writes or paid AI calls."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

with patch('backend.services.firebase_service.get_firestore_client', side_effect=RuntimeError('test')):
    from backend.services import chat_service as service
from backend.models.schemas import ChatRequest, DataRecord


def record(game_id, team='LG', opponent='KIA', score=(3, 1), season=2026, status='completed'):
    a, b = score
    return DataRecord(date=f'{season}-09-01', season=season, team=team, opponent=opponent,
                      home_away='home', runs_for=a, runs_against=b,
                      result='W' if a > b else 'L' if a < b else 'D', run_diff=a-b,
                      value=a-b, status=status, game_id=game_id)


class MatchupTests(unittest.TestCase):
    def request(self, message='LG 와 기아의 상대전적 확인해줘', team='삼성', last_n=1):
        return ChatRequest(message=message, team=team, season=2026, last_n=last_n)

    def summary(self, records, request=None):
        with patch.object(service, 'store') as store:
            store.list.return_value = records
            result = service.chat_service._summary(request or self.request())
            return result, store.list.call_args.kwargs

    def test_aliases_question_teams_override_selected_team(self):
        for message in ('LG 와 기아의 상대전적 확인해줘', 'lg와 kia 상대 전적', '엘지와 기아 맞대결'):
            self.assertEqual(service.chat_service._matchup(self.request(message)), ('LG', 'KIA'))

    def test_all_matchups_not_recent_team_games_and_no_double_count(self):
        rows = [record('g1'), record('g1'), record('g1', team='KIA', opponent='LG', score=(1,3)),
                record('g2', score=(1,4)), record('g3', score=(2,2)), record('other', opponent='삼성'),
                record('old', season=2025), record('future', status='scheduled')]
        summary, query = self.summary(rows)
        self.assertEqual(query['team'], 'LG')
        self.assertEqual(summary['count'], 3)
        self.assertIsNone(summary['filters']['last_n'])
        self.assertEqual(summary['head_to_head']['team_a_wins'], 1)
        self.assertEqual(summary['head_to_head']['team_b_wins'], 1)
        self.assertEqual(summary['head_to_head']['draws'], 1)
        self.assertEqual(summary['head_to_head']['team_a_win_rate'], .5)

    def test_doubleheader_distinct_ids_are_both_counted(self):
        summary, _ = self.summary([record('dh1'), record('dh2')])
        self.assertEqual(summary['count'], 2)

    def test_no_matchup_data(self):
        summary, _ = self.summary([record('other', opponent='삼성')])
        self.assertEqual(summary['count'], 0)
        self.assertIsNone(summary['head_to_head']['team_a_win_rate'])

    def test_one_opponent_uses_selected_team(self):
        request = self.request('LG와 상대전적은?', team='KIA')
        self.assertEqual(service.chat_service._matchup(request), ('KIA', 'LG'))

    def test_normal_single_team_summary_unchanged(self):
        request = self.request('LG 최근 경기력은?', team='LG')
        summary, _ = self.summary([record('g1'), record('g2')], request)
        self.assertNotIn('head_to_head', summary)
        self.assertEqual(summary['count'], 1)

    def test_context_sent_to_sdk_and_saved_with_summary(self):
        summary, _ = self.summary([record('g1')])
        sdk = MagicMock()
        sdk.__enter__.return_value = sdk
        sdk.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='LG 1승'))])
        cfg = replace(service.settings, ai_provider='openai', openai_mock_mode=False, openai_api_key='test')
        with patch.object(service, 'settings', cfg), patch.object(service.chat_service, '_summary', return_value=summary), \
             patch.object(service, 'conversation_store') as conversations, patch('openai.OpenAI', return_value=sdk):
            conversations.save_exchange.return_value = SimpleNamespace(id='test')
            result = service.chat_service.answer(self.request())
            self.assertIn('"head_to_head"', sdk.chat.completions.create.call_args.kwargs['messages'][0]['content'])
            self.assertEqual(conversations.save_exchange.call_args.args[3], summary)
            self.assertEqual(result.summary, summary)

    def test_all_draws_mock_does_not_crash(self):
        summary, _ = self.summary([record('draw', score=(1,1))])
        with patch.object(service, 'settings', replace(service.settings, openai_mock_mode=True)), \
             patch.object(service.chat_service, '_summary', return_value=summary), patch.object(service, 'conversation_store') as conversations:
            conversations.save_exchange.return_value = SimpleNamespace(id='test')
            self.assertIn('산정 불가', service.chat_service.answer(self.request()).answer)


if __name__ == '__main__':
    unittest.main()
