"""Structured team-building constraints and draft team materialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from team_constraints import LegendaryPolicy
from team_models import PokemonBuild, Team


@dataclass
class AssumeFieldOpponent:
    """Optional opponent lead assumptions for advisory (e.g. Armor Tail)."""

    lead_species: str | None = None
    assume_armor_tail_active: bool = False


@dataclass
class TeamIntent:
    """
    Machine-readable recommendations/restrictions before final team build.

    ``must_include`` entries are partial slot dicts (``species`` required); remaining
    slots are padded with ``placeholder_species`` unless a full partial ``Team`` is merged.
    """

    preset_id: str = "gen9"
    legendary_policy: LegendaryPolicy = "allow_all"
    mechanics_only_mega: bool = False
    must_include: list[dict[str, Any]] = field(default_factory=list)
    avoid_species: list[str] = field(default_factory=list)
    avoid_types: list[str] = field(default_factory=list)
    meta_threats: list[str] = field(default_factory=list)
    assume_field_opponent: AssumeFieldOpponent | None = None
    placeholder_species: str = "rattata"
    speed_margin: int = 20
    team_name: str = "Draft"
    archetype: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TeamIntent:
        afo_raw = raw.get("assume_field_opponent") or raw.get("assumeFieldOpponent")
        afo: AssumeFieldOpponent | None = None
        if isinstance(afo_raw, dict):
            afo = AssumeFieldOpponent(
                lead_species=afo_raw.get("lead_species") or afo_raw.get("leadSpecies"),
                assume_armor_tail_active=bool(
                    afo_raw.get("assume_armor_tail_active")
                    or afo_raw.get("assumeArmorTailActive")
                ),
            )

        lp = raw.get("legendary_policy") or raw.get("legendaryPolicy") or "allow_all"
        if lp not in ("allow_all", "ban_legendary_and_mythical", "ban_mythical_only"):
            raise ValueError(f"invalid legendary_policy: {lp!r}")

        stubs = raw.get("must_include") or raw.get("mustInclude") or []
        if not isinstance(stubs, list):
            raise TypeError("must_include must be a list")
        out_stubs: list[dict[str, Any]] = []
        for i, s in enumerate(stubs):
            if not isinstance(s, dict):
                raise TypeError(f"must_include[{i}] must be an object")
            if not s.get("species"):
                raise ValueError(f"must_include[{i}] requires species")
            out_stubs.append(dict(s))

        def _str_list(key: str, alt: str | None = None) -> list[str]:
            v = raw.get(key) if alt is None else raw.get(key, raw.get(alt))
            if v is None:
                return []
            if not isinstance(v, list):
                raise TypeError(f"{key} must be a list of strings")
            return [str(x).strip() for x in v if str(x).strip()]

        return cls(
            preset_id=str(raw.get("preset_id") or raw.get("preset") or "gen9"),
            legendary_policy=lp,  # type: ignore[assignment]
            mechanics_only_mega=bool(raw.get("mechanics_only_mega") or raw.get("mechanicsOnlyMega")),
            must_include=out_stubs,
            avoid_species=_str_list("avoid_species", "avoidSpecies"),
            avoid_types=[t.strip().lower() for t in _str_list("avoid_types", "avoidTypes")],
            meta_threats=_str_list("meta_threats", "metaThreats"),
            assume_field_opponent=afo,
            placeholder_species=str(raw.get("placeholder_species") or raw.get("placeholderSpecies") or "rattata"),
            speed_margin=int(raw.get("speed_margin") or raw.get("speedMargin") or 20),
            team_name=str(raw.get("team_name") or raw.get("teamName") or "Draft"),
            archetype=raw.get("archetype"),
        )

    def to_dict(self) -> dict[str, Any]:
        afo_d: dict[str, Any] | None = None
        if self.assume_field_opponent:
            afo_d = {
                "lead_species": self.assume_field_opponent.lead_species,
                "assume_armor_tail_active": self.assume_field_opponent.assume_armor_tail_active,
            }
        return {
            "preset_id": self.preset_id,
            "legendary_policy": self.legendary_policy,
            "mechanics_only_mega": self.mechanics_only_mega,
            "must_include": list(self.must_include),
            "avoid_species": list(self.avoid_species),
            "avoid_types": list(self.avoid_types),
            "meta_threats": list(self.meta_threats),
            "assume_field_opponent": afo_d,
            "placeholder_species": self.placeholder_species,
            "speed_margin": self.speed_margin,
            "team_name": self.team_name,
            "archetype": self.archetype,
        }


def load_team_intent(path: str | Path) -> TeamIntent:
    """Load :class:`TeamIntent` from a JSON file."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return TeamIntent.from_dict(raw)


def uses_placeholder_slots(intent: TeamIntent, *, partial_team: Team | None) -> bool:
    """True when advisory team includes filler placeholders (not a full 6-species intent)."""
    if partial_team is not None:
        return False
    return len(intent.must_include) < 6


def merge_intent_overlay(partial: Team, intent: TeamIntent) -> Team:
    """Overlay ``intent.must_include`` stubs onto the first N slots of ``partial``."""
    slots_dict = [s.to_dict() for s in partial.slots]
    for i, stub in enumerate(intent.must_include):
        if i >= 6:
            break
        base = dict(slots_dict[i])
        for k, v in stub.items():
            if k == "moves" and v is not None:
                base["moves"] = v
            elif v is not None:
                base[k] = v
        slots_dict[i] = base
    return Team.from_dict(
        {
            "name": intent.team_name or partial.name,
            "archetype": intent.archetype if intent.archetype is not None else partial.archetype,
            "slots": slots_dict,
        }
    )


def draft_team_from_intent(intent: TeamIntent, partial_team: Team | None = None) -> Team:
    """
    Materialize a 6-slot :class:`Team` from intent, optionally merging over ``partial_team``.

    Placeholder slots (neutral filler) use ``intent.placeholder_species`` when fewer than
    six ``must_include`` entries and no partial team is provided.
    """
    if partial_team is not None:
        return merge_intent_overlay(partial_team, intent)

    slots: list[PokemonBuild] = []
    for stub in intent.must_include:
        slots.append(PokemonBuild.from_dict(dict(stub)))
    while len(slots) < 6:
        slots.append(PokemonBuild(species=intent.placeholder_species))
    return Team(
        name=intent.team_name,
        archetype=intent.archetype,
        slots=slots,
    )
