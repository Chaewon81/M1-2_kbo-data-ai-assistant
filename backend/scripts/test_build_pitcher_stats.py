"""임시 CSV로 선정과 오류 거부를 검증한다. 운영 통계는 수정하지 않는다."""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from backend.scripts.build_pitcher_stats import FIELDS, TEAM_NAMES, build, parse_ip


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.csv"
        self.output = Path(self.temp.name) / "output.csv"
        self.rows = []
        for code, name in TEAM_NAMES.items():
            for index, innings in enumerate(("10", "20 1/3", "20⅔", "30")):
                self.rows.append(dict(zip(FIELDS, (
                    "2026", code, name, str(10000 + index), "TEST",
                    "5", innings, "2", "1.5", "1.1", "12",
                    f"https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx?playerId={10000 + index}",
                    "2026-10-01", "2026-10-01T12:00:00+09:00",
                ))))

    def run_build(self, **kwargs):
        with self.source.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        arguments = dict(season=2026, top_n=3, as_of="2026-10-01")
        arguments.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            build(self.source, self.output, **arguments)

    def test_top_three_and_fraction_conversion(self):
        self.assertAlmostEqual(parse_ip("⅓"), 1 / 3)
        self.assertAlmostEqual(parse_ip("⅔"), 2 / 3)
        with self.assertRaises(ValueError):
            parse_ip("1 1/0")
        self.run_build()
        with self.output.open(encoding="utf-8-sig", newline="") as fp:
            result = list(csv.DictReader(fp))
        self.assertEqual(len(result), 30)
        for code in TEAM_NAMES:
            team = [row for row in result if row["team_code"] == code]
            self.assertEqual([row["innings"] for row in team], ["30", "20.6667", "20.3333"])

    def test_invalid_values_do_not_overwrite_output(self):
        self.run_build()
        previous = self.output.read_bytes()
        cases = (("innings", "nan"), ("innings", "inf"), ("innings", "-1"),
                 ("era", "nan"), ("whip", "inf"), ("strikeouts", "-1"),
                 ("games_appeared", "bad"), ("earned_runs", ""),
                 ("player", "  "), ("player_id", "  "),
                 ("team_code", "LG"), ("source_url", "https://example.com/Record/Player/"))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                original = self.rows[0][field]
                self.rows[0][field] = value
                with self.assertRaises(ValueError):
                    self.run_build()
                self.assertEqual(self.output.read_bytes(), previous)
                self.rows[0][field] = original

    def test_duplicate_outside_top_three_rejected(self):
        self.rows.append(dict(self.rows[0]))
        with self.assertRaisesRegex(ValueError, "중복"):
            self.run_build()

    def test_zero_innings_without_era_excluded(self):
        row = dict(self.rows[0], player_id="99999", innings="0", era="-", whip="-",
                   source_url="https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx?playerId=99999")
        self.rows.append(row)
        self.run_build()

    def test_invalid_options(self):
        for kwargs in ({"top_n": 0}, {"top_n": -1}, {"as_of": "2026-02-31"},
                       {"updated_at": "invalid-date"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_build(**kwargs)


if __name__ == "__main__":
    unittest.main()
