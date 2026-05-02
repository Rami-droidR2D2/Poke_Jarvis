"""Gen 9 type matchup chart (attack type vs defending type), cached via PokeAPI."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from data_engine import BASE_URL, fetch_json

_ALL_TYPE_IDS = range(1, 19)

_CHART: dict[str, dict[str, float]] | None = None


def build_attack_chart(*, force_refresh: bool = False) -> dict[str, dict[str, float]]:
    """attack_type -> defend_type -> multiplier."""
    global _CHART
    if _CHART is not None and not force_refresh:
        return _CHART
    chart: dict[str, dict[str, float]] = {}
    for tid in _ALL_TYPE_IDS:
        data = fetch_json(f"{BASE_URL}/type/{tid}/", f"type_{tid}", force_refresh=force_refresh)
        atk = data.get("name")
        if not atk:
            continue
        row: dict[str, float] = defaultdict(lambda: 1.0)
        rel = data.get("damage_relations") or {}
        for entry in rel.get("double_damage_to") or []:
            if isinstance(entry, dict) and entry.get("name"):
                row[str(entry["name"])] = 2.0
        for entry in rel.get("half_damage_to") or []:
            if isinstance(entry, dict) and entry.get("name"):
                row[str(entry["name"])] = 0.5
        for entry in rel.get("no_damage_to") or []:
            if isinstance(entry, dict) and entry.get("name"):
                row[str(entry["name"])] = 0.0
        chart[str(atk)] = dict(row)
    _CHART = chart
    return chart


def reload_type_chart_cache() -> None:
    """Invalidate cached chart (e.g. after ``clear_cache``)."""
    global _CHART
    _CHART = None


def attack_multiplier(move_type: str, defending_types: list[str], *, force_refresh: bool = False) -> float:
    """Combined multiplier when ``move_type`` attacks a Pokémon with ``defending_types``."""
    chart = build_attack_chart(force_refresh=force_refresh)
    mt = move_type.strip().lower()
    row = chart.get(mt)
    if row is None:
        return 1.0
    m = 1.0
    for dt in defending_types:
        d = (dt or "").strip().lower()
        m *= float(row.get(d, 1.0))
    return m


def defending_type_weaknesses(defending_types: list[str], *, force_refresh: bool = False) -> dict[str, Any]:
    """
    For each attacking type, multiplier vs this defender (dual-type product).
    Returns sorted lists: quad_weakness, weakness, resistance, immunity.
    """
    chart = build_attack_chart(force_refresh=force_refresh)
    dtypes = [(dt or "").strip().lower() for dt in defending_types]
    multipliers: dict[str, float] = {}
    for atk, row in chart.items():
        prod = 1.0
        for d in dtypes:
            prod *= float(row.get(d, 1.0))
        multipliers[atk] = prod

    quad = [t for t, m in multipliers.items() if m >= 4.0 - 1e-9]
    weak = [t for t, m in multipliers.items() if 2.0 <= m < 4.0]
    resist = [t for t, m in multipliers.items() if 0 < m < 1.0]
    immune = [t for t, m in multipliers.items() if m == 0]
    quad.sort()
    weak.sort()
    resist.sort()
    immune.sort()
    return {
        "defending_types": dtypes,
        "multipliers_by_attack_type": dict(sorted(multipliers.items(), key=lambda x: (-x[1], x[0]))),
        "quad_weakness": quad,
        "weakness": weak,
        "resistance": resist,
        "immunity": immune,
    }
