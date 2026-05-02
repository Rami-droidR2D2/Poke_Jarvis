"""Selectable battle rulesets: calc generation, allowed mechanics, learnset verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet


class UnknownPresetError(ValueError):
    """Raised when ``preset_id`` is not registered."""


Mechanic = str  # mega | z_move | dynamax | tera


@dataclass(frozen=True)
class BattlePreset:
    """Maps user-facing preset id to ``@smogon/calc`` generation and constraints."""

    id: str
    calc_gen: int
    allowed_mechanics: FrozenSet[str]
    learnset_generation: int
    description: str = ""
    default_field: dict[str, Any] | None = None


_PRESETS: dict[str, BattlePreset] = {
    "gen9": BattlePreset(
        id="gen9",
        calc_gen=9,
        allowed_mechanics=frozenset({"tera"}),
        learnset_generation=9,
        description="Gen IX SV-style (Terastallize where applicable).",
    ),
    "gen7_sm": BattlePreset(
        id="gen7_sm",
        calc_gen=7,
        allowed_mechanics=frozenset({"mega", "z_move"}),
        learnset_generation=7,
        description="Gen VII Sun/Moon—Mega Evolution and Z-Moves; no Dynamax.",
    ),
    "gen8_ss": BattlePreset(
        id="gen8_ss",
        calc_gen=8,
        allowed_mechanics=frozenset({"dynamax"}),
        learnset_generation=8,
        description="Gen VIII Sword/Shield—Dynamax / Max moves.",
    ),
    "legends_za": BattlePreset(
        id="legends_za",
        calc_gen=9,
        allowed_mechanics=frozenset({"mega", "tera"}),
        learnset_generation=9,
        description=(
            "Alias for Legends: Z-A–oriented teams until @smogon/calc publishes a dedicated "
            "generation—uses Gen 9 damage math with mega + tera allowed in validation flags."
        ),
    ),
}


def list_presets() -> list[str]:
    return sorted(_PRESETS.keys())


def resolve_preset(preset_id: str) -> BattlePreset:
    key = (preset_id or "gen9").strip().lower()
    p = _PRESETS.get(key)
    if p is None:
        raise UnknownPresetError(
            f"Unknown preset {preset_id!r}. Choose one of: {', '.join(list_presets())}"
        )
    return p


def merge_field_json(
    preset: BattlePreset,
    archetype_field: dict[str, Any] | None,
    user_field: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Later keys win (user overrides archetype overrides preset defaults)."""
    out: dict[str, Any] = {}
    if preset.default_field:
        out.update(preset.default_field)
    if archetype_field:
        out.update(archetype_field)
    if user_field:
        out.update(user_field)
    return out if out else None
