"""Unit tests for team advisory (mocked PokeAPI)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from team_advisory import team_advisory_report
from team_intent import TeamIntent, draft_team_from_intent


def _core_garchomp(**kwargs):
    return {
        "name": "garchomp",
        "types": ["dragon", "ground"],
        "stats": {"speed": 102},
        "abilities": [{"name": "rough-skin", "is_hidden": False}],
    }


def _core_flutter(**kwargs):
    return {
        "name": "flutter-mane",
        "types": ["ghost", "fairy"],
        "stats": {"speed": 135},
        "abilities": [{"name": "Protosynthesis", "is_hidden": False}],
    }


def _core_greninja(**kwargs):
    return {
        "name": "greninja",
        "types": ["water", "dark"],
        "stats": {"speed": 122},
        "abilities": [{"name": "protean", "is_hidden": True}],
    }


def fake_stats_lookup(name: str, **kwargs):
    n = name.lower().replace(" ", "-")
    if "garchomp" in n:
        return _core_garchomp(**kwargs)
    if "flutter" in n:
        return _core_flutter(**kwargs)
    if "greninja" in n:
        return _core_greninja(**kwargs)
    if "rattata" in n:
        return {"name": "rattata", "types": ["normal"], "stats": {"speed": 72}, "abilities": []}
    return {"name": n, "types": ["normal"], "stats": {"speed": 60}, "abilities": []}


class TeamAdvisoryTests(unittest.TestCase):
    @patch("team_advisory.get_base_stats_types_abilities", side_effect=fake_stats_lookup)
    @patch("team_advisory.attack_multiplier")
    def test_threat_stab_lane_fairy_vs_garchomp(self, mock_mult, _mock_stats):
        mock_mult.side_effect = lambda atk, defs, **kw: (
            2.0 if atk == "fairy" and "dragon" in defs else 0.5
        )

        intent = TeamIntent.from_dict(
            {
                "must_include": [{"species": "Garchomp", "moves": ["Earthquake"]}],
                "meta_threats": ["Flutter Mane"],
            }
        )
        team = draft_team_from_intent(intent, None)
        report = team_advisory_report(intent, team=team, partial_team=None, force_refresh=False)

        codes = [w["code"] for w in report["warnings"]]
        self.assertIn("threat_stab_lane", codes)

    @patch("team_advisory.get_move_battle_metadata")
    @patch("team_advisory.get_base_stats_types_abilities", side_effect=fake_stats_lookup)
    @patch("team_advisory.attack_multiplier", return_value=1.0)
    def test_armor_tail_blocks_fake_out_priority(self, _mult, _stats, mock_move):
        mock_move.return_value = {"name": "fake-out", "priority": 3, "type": "normal", "damage_class": "physical"}

        intent = TeamIntent.from_dict(
            {
                "must_include": [{"species": "Garchomp", "moves": ["Fake Out"]}],
                "assume_field_opponent": {"assume_armor_tail_active": True},
            }
        )
        team = draft_team_from_intent(intent, None)
        report = team_advisory_report(intent, team=team, partial_team=None, force_refresh=False)

        codes = [w["code"] for w in report["warnings"]]
        self.assertIn("armor_tail_priority", codes)

    @patch("team_advisory.get_base_stats_types_abilities", side_effect=fake_stats_lookup)
    @patch("team_advisory.attack_multiplier")
    def test_speed_threat_combo(self, mock_mult, _mock_stats):
        mock_mult.side_effect = lambda atk, defs, **kw: (
            2.0 if atk == "dark" and "dragon" in defs else 1.0
        )

        intent = TeamIntent.from_dict(
            {
                "must_include": [{"species": "Garchomp"}],
                "meta_threats": ["Greninja"],
                "speed_margin": 20,
            }
        )
        team = draft_team_from_intent(intent, None)
        report = team_advisory_report(intent, team=team, partial_team=None, force_refresh=False)

        codes = [w["code"] for w in report["warnings"]]
        self.assertIn("speed_threat_combo", codes)

    def test_empty_must_include_info(self):
        intent = TeamIntent.from_dict({"must_include": []})
        team = draft_team_from_intent(intent, None)
        report = team_advisory_report(intent, team=team, partial_team=None, force_refresh=False)
        self.assertTrue(any(w["code"] == "empty_intent" for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
