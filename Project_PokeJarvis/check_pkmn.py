#!/usr/bin/env python3
"""CLI: look up a Pokémon and print a competitive-oriented summary."""

from __future__ import annotations

import argparse
import sys

import requests

from pokedex_service import get_pokemon_summary


STAT_ORDER = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
STAT_LABELS = {
    "hp": "HP",
    "attack": "Atk",
    "defense": "Def",
    "special-attack": "SpA",
    "special-defense": "SpD",
    "speed": "Spe",
}


def _format_abilities(abilities: list[dict]) -> str:
    parts = []
    for a in abilities:
        label = a["name"].replace("-", " ").title()
        if a.get("is_hidden"):
            label += " (Hidden)"
        parts.append(label)
    return ", ".join(parts) if parts else "—"


def _format_types(types: list[str]) -> str:
    return " / ".join(t.title() for t in types) if types else "—"


def _format_stat_line(stats: dict[str, int]) -> list[str]:
    lines = []
    total = 0
    for key in STAT_ORDER:
        val = stats.get(key, 0)
        total += val
        label = STAT_LABELS.get(key, key)
        lines.append(f"  {label:>3}  {val:>3}")
    lines.append(f"  {'BST':>3}  {total:>3}")
    return lines


def _summarize_move_contexts(move: dict) -> str:
    """Short hint: level / TM / egg / tutor counts per Gen 9 groups."""
    methods: set[str] = set()
    min_level: int | None = None
    for c in move.get("contexts", []):
        m = c.get("method")
        if m:
            methods.add(m)
        lvl = c.get("level_learned_at")
        if isinstance(lvl, int) and lvl > 0:
            min_level = lvl if min_level is None else min(min_level, lvl)
    bits = []
    if min_level is not None:
        bits.append(f"L{min_level}+")
    for m in sorted(methods):
        if m == "level-up":
            continue
        bits.append(m.replace("-", " "))
    return ", ".join(bits) if bits else "available"


def print_summary(name: str, *, refresh: bool = False) -> None:
    s = get_pokemon_summary(name, force_refresh=refresh)
    core = {
        "id": s["id"],
        "name": s["name"],
        "stats": s["stats"],
        "types": s["types"],
        "abilities": s["abilities"],
    }
    moves = s["moves_gen9"]

    display_name = core["name"].replace("-", " ").title()
    nid = core.get("id")
    id_str = f"{int(nid):03d}" if isinstance(nid, int) else "—"
    print()
    print(f"#{id_str}  {display_name}")
    print(f"Types:    {_format_types(core['types'])}")
    print(f"Abilities: {_format_abilities(core['abilities'])}")
    print("Base stats:")
    for line in _format_stat_line(core["stats"]):
        print(line)
    print()
    print(f"Gen 9 move pool: {len(moves)} moves (incl. all learn methods)")
    preview = moves[:24]
    for mv in preview:
        extra = _summarize_move_contexts(mv)
        print(f"  • {mv['name'].replace('-', ' '):<22}  ({extra})")
    if len(moves) > len(preview):
        print(f"  … and {len(moves) - len(preview)} more")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pokémon competitive snapshot (PokeAPI + local cache).")
    parser.add_argument("name", nargs="?", help="Pokémon name (e.g. Garchomp, flutter mane)")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache and refetch from the API")
    args = parser.parse_args()

    name = args.name
    if not name:
        try:
            name = input("Pokémon name: ").strip()
        except EOFError:
            print("No name provided.", file=sys.stderr)
            return 1
    if not name:
        print("No name provided.", file=sys.stderr)
        return 1

    try:
        print_summary(name, refresh=args.refresh)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print(f"Not found: '{name}'. Check spelling or try the official dex name.", file=sys.stderr)
        else:
            print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
