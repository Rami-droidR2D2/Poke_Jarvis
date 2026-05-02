"""Unified Pokémon lookup for agents and CLI (stats, types, abilities, Gen 9 moves)."""

from __future__ import annotations

from typing import Any

from data_engine import get_base_stats_types_abilities, get_moves_gen9


def get_pokemon_summary(name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """
    Single structured payload: core Pokédex fields plus Gen 9 legal moves (names + contexts).

    Intended as the main entry point for \"give me data about Pokémon X\" requests.
    """
    core = get_base_stats_types_abilities(name, force_refresh=force_refresh)
    moves = get_moves_gen9(core["name"], force_refresh=force_refresh)
    move_names = [m["name"] for m in moves]
    return {
        "id": core.get("id"),
        "name": core["name"],
        "stats": core["stats"],
        "types": core["types"],
        "abilities": core["abilities"],
        "moves_gen9": moves,
        "move_names_gen9": move_names,
    }
