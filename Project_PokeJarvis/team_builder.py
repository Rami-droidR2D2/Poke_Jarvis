"""Load curated archetype teams (Rain, Sun, …) and optional learnset checks."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from battle_presets import BattlePreset, resolve_preset
from data_engine import get_moves_for_generation
from team_models import Team, move_slot_display

logger = logging.getLogger(__name__)

_ARCH_ROOT = Path(__file__).resolve().parent / "archetypes"


def list_archetypes() -> list[str]:
    if not _ARCH_ROOT.is_dir():
        return []
    return sorted(p.stem for p in _ARCH_ROOT.glob("*.json"))


def _slug_move(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def verify_team_moves(team: Team, preset: BattlePreset, *, force_refresh: bool = False) -> list[str]:
    """Return human-readable issues when a listed move is absent from PokeAPI learnsets for preset gen."""
    issues: list[str] = []
    gen = preset.learnset_generation
    for idx, slot in enumerate(team.slots):
        pool = {
            _slug_move(m["name"])
            for m in get_moves_for_generation(slot.species, gen, force_refresh=force_refresh)
        }
        for mv in slot.moves:
            label = _slug_move(move_slot_display(mv))
            if label not in pool:
                issues.append(
                    f"slot {idx} ({slot.species}): move '{move_slot_display(mv)}' "
                    f"not found in Gen {gen} learnset (PokeAPI)"
                )
    return issues


def load_archetype_bundle(
    archetype_id: str,
    *,
    preset_id: str = "gen9",
    verify_moves: bool = False,
    force_refresh: bool = False,
) -> tuple[Team, dict[str, Any] | None, BattlePreset]:
    """
    Load ``archetypes/<id>.json``.

    Returns ``(team, recommended_field, preset)``.
    """
    preset = resolve_preset(preset_id)
    path = _ARCH_ROOT / f"{archetype_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No archetype file: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    field = raw.get("recommended_field")
    aid = raw.get("id") or archetype_id
    team = Team.from_dict(
        {
            "name": raw.get("name") or aid.title(),
            "archetype": aid,
            "slots": raw["slots"],
        }
    )
    if verify_moves:
        problems = verify_team_moves(team, preset, force_refresh=force_refresh)
        for p in problems:
            logger.warning("Archetype %s: %s", archetype_id, p)
    return team, field if isinstance(field, dict) else None, preset


def build_team(
    archetype_id: str,
    *,
    preset_id: str = "gen9",
    verify_moves: bool = False,
    force_refresh: bool = False,
) -> tuple[Team, dict[str, Any] | None, BattlePreset]:
    """Alias for :func:`load_archetype_bundle`."""
    return load_archetype_bundle(
        archetype_id,
        preset_id=preset_id,
        verify_moves=verify_moves,
        force_refresh=force_refresh,
    )
