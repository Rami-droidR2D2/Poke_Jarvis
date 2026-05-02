"""Team and Pokémon build models for damage matrix and Smogon calc payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _stat_key_for_smogon(key: str) -> str:
    k = key.strip().lower()
    mapping = {
        "hp": "hp",
        "attack": "atk",
        "defense": "def",
        "special-attack": "spa",
        "special-defense": "spd",
        "speed": "spe",
        "atk": "atk",
        "def": "def",
        "spa": "spa",
        "spd": "spd",
        "spe": "spe",
    }
    return mapping.get(k, k)


def normalize_move_slot(raw: Any) -> str | dict[str, Any]:
    """Accept move name string or ``{\"name\": \"...\", \"useZ\": true, \"useMax\": true}``."""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        out = dict(raw)
        if "name" not in out:
            raise ValueError(f"move object requires 'name' key, got {raw!r}")
        return out
    raise TypeError(f"move slot must be str or dict, got {type(raw).__name__}")


def move_slot_display(ms: str | dict[str, Any]) -> str:
    if isinstance(ms, str):
        return ms
    return str(ms.get("name", ""))


def move_payload_for_bridge(ms: str | dict[str, Any]) -> str | dict[str, Any]:
    """Payload fragment for ``calc_bridge.js`` ``move`` argument."""
    if isinstance(ms, str):
        return ms
    name = ms["name"]
    extra = {k: v for k, v in ms.items() if k != "name" and v is not None}
    return {"name": name, **extra}


@dataclass
class PokemonBuild:
    species: str
    level: int = 50
    ability: str | None = None
    item: str | None = None
    nature: str | None = None
    evs: dict[str, int] = field(default_factory=dict)
    ivs: dict[str, int] = field(default_factory=dict)
    moves: list[str | dict[str, Any]] = field(default_factory=list)
    tera_type: str | None = None
    is_dynamaxed: bool = False
    dynamax_level: int | None = None

    def to_smogon_side_dict(self) -> dict[str, Any]:
        """Payload fragment for ``attacker`` / ``defender`` in ``calc_bridge.js``."""
        d: dict[str, Any] = {"species": self.species, "level": self.level}
        if self.ability:
            d["ability"] = self.ability
        if self.item:
            d["item"] = self.item
        if self.nature:
            d["nature"] = self.nature
        if self.evs:
            evs_smogon: dict[str, int] = {}
            for k, v in self.evs.items():
                evs_smogon[_stat_key_for_smogon(k)] = int(v)
            d["evs"] = evs_smogon
        if self.ivs:
            ivs_smogon: dict[str, int] = {}
            for k, v in self.ivs.items():
                ivs_smogon[_stat_key_for_smogon(k)] = int(v)
            d["ivs"] = ivs_smogon
        if self.moves:
            # Smogon ``Pokemon`` expects move *names* here; Z/Max handled on ``Move`` payload.
            d["moves"] = [move_slot_display(m) for m in self.moves[:4]]
        if self.tera_type:
            d["teraType"] = self.tera_type
        if self.is_dynamaxed:
            d["isDynamaxed"] = True
            if self.dynamax_level is not None:
                d["dynamaxLevel"] = int(self.dynamax_level)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PokemonBuild:
        moves_raw = raw.get("moves") or []
        moves = [normalize_move_slot(m) for m in moves_raw]
        dl = raw.get("dynamax_level")
        if dl is None:
            dl = raw.get("dynamaxLevel")
        dynamax_level = int(dl) if dl is not None else None
        return cls(
            species=str(raw["species"]),
            level=int(raw.get("level", 50)),
            ability=raw.get("ability"),
            item=raw.get("item"),
            nature=raw.get("nature"),
            evs=dict(raw.get("evs") or {}),
            ivs=dict(raw.get("ivs") or {}),
            moves=moves,
            tera_type=raw.get("tera_type") or raw.get("teraType"),
            is_dynamaxed=bool(raw.get("is_dynamaxed") or raw.get("isDynamaxed")),
            dynamax_level=dynamax_level,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "level": self.level,
            "ability": self.ability,
            "item": self.item,
            "nature": self.nature,
            "evs": dict(self.evs),
            "ivs": dict(self.ivs),
            "moves": list(self.moves),
            "tera_type": self.tera_type,
            "is_dynamaxed": self.is_dynamaxed,
            "dynamax_level": self.dynamax_level,
        }


@dataclass
class Team:
    name: str = ""
    archetype: str | None = None
    slots: list[PokemonBuild] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.slots) != 6:
            raise ValueError(f"Team must have exactly 6 Pokémon builds, got {len(self.slots)}")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Team:
        slots_raw = raw.get("slots") or raw.get("pokemon") or []
        if len(slots_raw) != 6:
            raise ValueError("team JSON must contain exactly 6 slot entries")
        return cls(
            name=str(raw.get("name") or ""),
            archetype=raw.get("archetype"),
            slots=[PokemonBuild.from_dict(s) for s in slots_raw],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "slots": [s.to_dict() for s in self.slots],
        }


def team_from_json_str(s: str) -> Team:
    return Team.from_dict(json.loads(s))


def team_to_json_str(team: Team, *, indent: int | None = 2) -> str:
    return json.dumps(team.to_dict(), indent=indent, ensure_ascii=False)
