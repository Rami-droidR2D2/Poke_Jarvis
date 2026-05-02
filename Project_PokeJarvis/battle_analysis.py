"""Batch damage calculations and defensive typing profiles."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from data_engine import get_base_stats_types_abilities
from smogon_calc import SmogonCalcError, run_smogon_calc
from team_models import PokemonBuild, Team, move_payload_for_bridge, move_slot_display
from type_effectiveness import defending_type_weaknesses

logger = logging.getLogger(__name__)


def _move_sort_key(mv: Any) -> str:
    if isinstance(mv, str):
        return mv
    return json.dumps(mv, sort_keys=True)


def weakness_profile_for_species(species: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Typing weaknesses for a species using Pokédex types + type chart."""
    core = get_base_stats_types_abilities(species, force_refresh=force_refresh)
    prof = defending_type_weaknesses(core["types"], force_refresh=force_refresh)
    prof["species"] = core["name"]
    prof["species_types"] = core["types"]
    return prof


def weakness_profile_for_build(build: PokemonBuild, *, force_refresh: bool = False) -> dict[str, Any]:
    return weakness_profile_for_species(build.species, force_refresh=force_refresh)


def damage_matrix(
    attackers: Team,
    defenders: Team,
    *,
    gen: int = 9,
    field: dict[str, Any] | None = None,
    offensive_moves_by_slot: dict[int, list[Any]] | None = None,
    move_slot_indices: tuple[int, ...] = (0, 1),
    timeout: float = 45.0,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    """
    Run Smogon calc for each attacker slot × defender slot × selected moves.

    Move selection: ``offensive_moves_by_slot[i]`` if provided (strings or move objects);
    else attacker slot ``moves`` at indices ``move_slot_indices``.

    Rows with ``ok: false`` usually mean immunity, full mitigate, or non-damaging moves.
    """
    cells: list[tuple[int, int, Any]] = []
    for i, atk in enumerate(attackers.slots):
        move_slots: list[Any]
        if offensive_moves_by_slot and i in offensive_moves_by_slot:
            move_slots = list(offensive_moves_by_slot[i])
        else:
            m = atk.moves
            move_slots = [m[idx] for idx in move_slot_indices if idx < len(m)]
        if not move_slots:
            logger.warning("Skipping attacker slot %s (%s): no moves", i, atk.species)
            continue
        for j, _dfe in enumerate(defenders.slots):
            for ms in move_slots:
                cells.append((i, j, ms))

    results: list[dict[str, Any]] = []

    def _one(cell: tuple[int, int, Any]) -> dict[str, Any]:
        i, j, mslot = cell
        atk = attackers.slots[i]
        dfn = defenders.slots[j]
        mv_payload = move_payload_for_bridge(mslot)
        mv_label = move_slot_display(mslot)
        payload: dict[str, Any] = {
            "gen": gen,
            "attacker": atk.to_smogon_side_dict(),
            "defender": dfn.to_smogon_side_dict(),
            "move": mv_payload,
        }
        if field is not None:
            payload["field"] = field
        try:
            out = run_smogon_calc(payload, timeout=timeout)
            row: dict[str, Any] = {
                "attacker_slot": i,
                "defender_slot": j,
                "attacker_species": atk.species,
                "defender_species": dfn.species,
                "move": mv_label,
                "ok": True,
                "damage": out.get("damage"),
                "range": out.get("range"),
                "desc": out.get("desc"),
                "raw": out,
            }
            if isinstance(mslot, dict):
                row["calc_move"] = mv_payload
            return row
        except (SmogonCalcError, FileNotFoundError, OSError) as e:
            return {
                "attacker_slot": i,
                "defender_slot": j,
                "attacker_species": atk.species,
                "defender_species": dfn.species,
                "move": mv_label,
                "ok": False,
                "error": str(e),
            }

    if max_workers <= 1:
        for c in cells:
            results.append(_one(c))
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_one, c): c for c in cells}
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(
        key=lambda r: (r["attacker_slot"], r["defender_slot"], _move_sort_key(r.get("move")))
    )
    return results


def team_weakness_bundle(team: Team, *, force_refresh: bool = False) -> dict[str, Any]:
    """Per-slot weakness_profile plus team-level merged vulnerability hints."""
    profiles = []
    for idx, slot in enumerate(team.slots):
        w = weakness_profile_for_build(slot, force_refresh=force_refresh)
        w["slot"] = idx
        profiles.append(w)
    all_weak = set()
    all_quad = set()
    all_imm = set()
    for p in profiles:
        all_weak.update(p.get("weakness") or [])
        all_quad.update(p.get("quad_weakness") or [])
        all_imm.update(p.get("immunity") or [])
    return {
        "team_name": team.name,
        "archetype": team.archetype,
        "slots": profiles,
        "team_attack_types_covering_weakness": sorted(all_weak | all_quad),
        "team_immunities_aggregate": sorted(all_imm),
    }
