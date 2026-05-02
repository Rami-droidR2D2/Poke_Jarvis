"""Jarvis-facing integration: Pokédex, teams, batch damage (Smogon bridge), synergy."""

from __future__ import annotations

import logging
from typing import Any

from smogon_calc import SmogonCalcError, run_smogon_calc as _run_smogon_calc_raw

from battle_analysis import (
    damage_matrix,
    team_weakness_bundle,
    weakness_profile_for_build,
    weakness_profile_for_species,
)
from battle_presets import UnknownPresetError, list_presets, resolve_preset
from pokedex_service import get_pokemon_summary
from synergy import analyze_synergy
from team_builder import build_team, list_archetypes, verify_team_moves
from team_constraints import validate_team_rules
from team_advisory import team_advisory_report
from team_intent import TeamIntent, draft_team_from_intent, load_team_intent
from team_models import PokemonBuild, Team, team_from_json_str, team_to_json_str

logger = logging.getLogger(__name__)

__all__ = [
    "SmogonCalcError",
    "UnknownPresetError",
    "analyze_synergy",
    "build_team",
    "calc_damage",
    "configure_logging",
    "damage_calc",
    "damage_matrix",
    "get_pokemon_summary",
    "list_archetypes",
    "list_presets",
    "resolve_preset",
    "run_smogon_calc",
    "team_from_json_str",
    "team_to_json_str",
    "team_weakness_bundle",
    "validate_team_rules",
    "verify_team_moves",
    "weakness_profile_for_build",
    "weakness_profile_for_species",
    "PokemonBuild",
    "Team",
    "TeamIntent",
    "draft_team_from_intent",
    "load_team_intent",
    "team_advisory_report",
]


def configure_logging(*, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _invoke_bridge(payload: dict[str, Any], *, timeout: float, verbose: bool) -> dict[str, Any]:
    attacker = payload.get("attacker")
    defender = payload.get("defender")
    if verbose:
        logger.info("Running calc for %s vs %s", attacker, defender)
    result = _run_smogon_calc_raw(payload, timeout=timeout)
    if verbose:
        logger.info("Result ok=%s range=%s", result.get("ok"), result.get("range"))
    return result


def run_smogon_calc(payload: dict[str, Any], *, timeout: float = 30.0, verbose: bool = False) -> dict[str, Any]:
    """Run the Node calc bridge; set ``verbose=True`` for per-request logging."""
    return _invoke_bridge(payload, timeout=timeout, verbose=verbose)


def damage_calc(payload: dict[str, Any], *, timeout: float = 30.0, verbose: bool = False) -> dict[str, Any]:
    return _invoke_bridge(payload, timeout=timeout, verbose=verbose)


def calc_damage(
    *,
    gen: int,
    attacker: dict[str, Any],
    defender: dict[str, Any],
    move: str | dict[str, Any],
    field: dict[str, Any] | None = None,
    timeout: float = 30.0,
    verbose: bool = False,
) -> dict[str, Any]:
    """Single-move damage calc; ``verbose`` logs attacker/defender species and result summary."""
    payload: dict[str, Any] = {
        "gen": gen,
        "attacker": attacker,
        "defender": defender,
        "move": move,
    }
    if field is not None:
        payload["field"] = field
    return _invoke_bridge(payload, timeout=timeout, verbose=verbose)


if __name__ == "__main__":
    configure_logging(verbose=True)
    logger.info("Jarvis_engine demo calc (quiet bridge logs unless verbose)")
    calc_damage(
        gen=9,
        attacker={"species": "Gholdengo"},
        defender={"species": "Amoonguss"},
        move="Make It Rain",
        verbose=True,
    )
