"""Team validation against battle presets and legendary/mythical policies."""

from __future__ import annotations

from typing import Any, Literal

from battle_presets import BattlePreset
from data_engine import get_species_classification
from team_models import Team, move_slot_display

LegendaryPolicy = Literal["allow_all", "ban_legendary_and_mythical", "ban_mythical_only"]


def _mega_like_species(species: str) -> bool:
    s = species.lower()
    return "-mega-" in s or s.endswith("-mega") or "-mega" in s


def validate_team_rules(
    team: Team,
    preset: BattlePreset,
    *,
    legendary_policy: LegendaryPolicy = "allow_all",
    mechanics_only_mega: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return ``{"ok": bool, "violations": [...]}`` with human-readable violation dicts.

    ``mechanics_only_mega``: disallow Z-Moves, Dynamax flags, Terastallize, and non-mega
    species/items patterns beyond Mega forms (heuristic: species name contains ``Mega``).
    """
    violations: list[dict[str, Any]] = []
    allowed = preset.allowed_mechanics

    for idx, slot in enumerate(team.slots):
        prefix = f"slot[{idx}] ({slot.species})"

        try:
            cls = get_species_classification(slot.species, force_refresh=force_refresh)
        except Exception as e:
            violations.append(
                {
                    "slot": idx,
                    "species": slot.species,
                    "rule": "species_classification",
                    "detail": str(e),
                }
            )
            cls = None

        if cls is not None:
            if legendary_policy == "ban_mythical_only" and cls["is_mythical"]:
                violations.append(
                    {
                        "slot": idx,
                        "species": slot.species,
                        "rule": "legendary_policy",
                        "detail": f"{prefix}: mythical Pokémon banned by policy.",
                    }
                )
            if legendary_policy == "ban_legendary_and_mythical" and (
                cls["is_mythical"] or cls["is_legendary"]
            ):
                violations.append(
                    {
                        "slot": idx,
                        "species": slot.species,
                        "rule": "legendary_policy",
                        "detail": f"{prefix}: legendary/mythical Pokémon banned by policy.",
                    }
                )

        if slot.is_dynamaxed and "dynamax" not in allowed:
            violations.append(
                {
                    "slot": idx,
                    "species": slot.species,
                    "rule": "mechanics",
                    "detail": f"{prefix}: Dynamax set but preset {preset.id!r} does not allow dynamax.",
                }
            )

        if slot.tera_type and "tera" not in allowed:
            violations.append(
                {
                    "slot": idx,
                    "species": slot.species,
                    "rule": "mechanics",
                    "detail": f"{prefix}: teraType set but preset {preset.id!r} does not allow tera.",
                }
            )

        inferred_mega = _mega_like_species(slot.species)
        if inferred_mega and "mega" not in allowed:
            violations.append(
                {
                    "slot": idx,
                    "species": slot.species,
                    "rule": "mechanics",
                    "detail": f"{prefix}: Mega species while preset {preset.id!r} disallows mega.",
                }
            )

        for mi, mslot in enumerate(slot.moves):
            if isinstance(mslot, dict):
                if mslot.get("useZ") and "z_move" not in allowed:
                    violations.append(
                        {
                            "slot": idx,
                            "species": slot.species,
                            "rule": "mechanics",
                            "detail": f"{prefix} move[{mi}] {move_slot_display(mslot)}: useZ without z_move in preset.",
                        }
                    )
                if mslot.get("useMax") and "dynamax" not in allowed:
                    violations.append(
                        {
                            "slot": idx,
                            "species": slot.species,
                            "rule": "mechanics",
                            "detail": f"{prefix} move[{mi}] {move_slot_display(mslot)}: useMax without dynamax in preset.",
                        }
                    )

        if mechanics_only_mega:
            if slot.is_dynamaxed or slot.dynamax_level is not None:
                violations.append(
                    {
                        "slot": idx,
                        "species": slot.species,
                        "rule": "mechanics_only_mega",
                        "detail": f"{prefix}: Dynamax fields present under mega-only rules.",
                    }
                )
            if slot.tera_type:
                violations.append(
                    {
                        "slot": idx,
                        "species": slot.species,
                        "rule": "mechanics_only_mega",
                        "detail": f"{prefix}: Terastallize disallowed under mega-only rules.",
                    }
                )
            for mi, mslot in enumerate(slot.moves):
                if isinstance(mslot, dict):
                    if mslot.get("useZ") or mslot.get("useMax"):
                        violations.append(
                            {
                                "slot": idx,
                                "species": slot.species,
                                "rule": "mechanics_only_mega",
                                "detail": f"{prefix} move[{mi}]: Z-Move/Max flags disallowed under mega-only rules.",
                            }
                        )
    return {"ok": len(violations) == 0, "violations": violations, "preset": preset.id}
