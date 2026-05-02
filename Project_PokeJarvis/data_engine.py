"""Fetch and cache Pokémon data from PokeAPI (https://pokeapi.co/)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://pokeapi.co/api/v2"
CACHE_DIR = Path(__file__).resolve().parent / ".poke_cache"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PokeJarvis/1.0 (competitive assistant; +local)"})

# Be polite to the public API
_MIN_REQUEST_INTERVAL = 0.35
_last_request_at: float = 0.0


def _throttle() -> None:
    global _last_request_at
    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _slug(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    return s


# PokeAPI `/pokemon/{name}` uses disambiguated slugs for multi-form species (404 on bare name).
_POKEAPI_POKEMON_SLUG_ALIASES: dict[str, str] = {
    "thundurus": "thundurus-incarnate",
    "landorus": "landorus-incarnate",
    "tornadus": "tornadus-incarnate",
}


def _pokeapi_resource_slug(name: str) -> str:
    base = _slug(name)
    return _POKEAPI_POKEMON_SLUG_ALIASES.get(base, base)


def _cache_file(key: str) -> Path:
    safe = re.sub(r"[^a-z0-9._-]+", "_", key)
    return CACHE_DIR / f"{safe}.json"


def _read_cache(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(path: Path, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def fetch_json(url: str, cache_key: str, *, force_refresh: bool = False) -> Any:
    path = _cache_file(cache_key)
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached
    _throttle()
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    _write_cache(path, data)
    return data


def get_generation_version_groups(gen_num: int, *, force_refresh: bool = False) -> set[str]:
    """PokeAPI ``version_group`` names that belong to a main-series generation number."""
    data = fetch_json(
        f"{BASE_URL}/generation/{gen_num}/",
        f"generation_{gen_num}",
        force_refresh=force_refresh,
    )
    return {vg["name"] for vg in data.get("version_groups", [])}


def get_generation_9_version_groups(*, force_refresh: bool = False) -> set[str]:
    return get_generation_version_groups(9, force_refresh=force_refresh)


def get_pokemon_payload(name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    slug = _pokeapi_resource_slug(name)
    url = f"{BASE_URL}/pokemon/{slug}"
    data = fetch_json(url, f"pokemon_{slug}", force_refresh=force_refresh)
    if not isinstance(data, dict):
        raise TypeError("Unexpected Pokémon payload")
    return data


def get_base_stats_types_abilities(name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Return base stats, types, and abilities for a Pokémon by name."""
    p = get_pokemon_payload(name, force_refresh=force_refresh)
    stats: dict[str, int] = {}
    for row in p.get("stats", []):
        stat = row.get("stat") or {}
        sname = stat.get("name")
        if sname:
            stats[sname] = int(row.get("base_stat", 0))
    types = []
    for t in sorted(p.get("types", []), key=lambda x: x.get("slot", 0)):
        tn = (t.get("type") or {}).get("name")
        if tn:
            types.append(tn)
    abilities = []
    for a in p.get("abilities", []):
        an = (a.get("ability") or {}).get("name")
        if an:
            abilities.append({"name": an, "is_hidden": bool(a.get("is_hidden", False))})
    return {
        "id": p.get("id"),
        "name": p.get("name", _slug(name)),
        "stats": stats,
        "types": types,
        "abilities": abilities,
    }


def get_moves_for_generation(
    name: str, generation: int, *, force_refresh: bool = False
) -> list[dict[str, Any]]:
    """
    Moves learnable in ``generation`` (via any version group mapped to that generation).
    """
    p = get_pokemon_payload(name, force_refresh=force_refresh)
    groups = get_generation_version_groups(generation, force_refresh=force_refresh)
    by_move: dict[str, dict[str, Any]] = {}

    for m in p.get("moves", []):
        move = m.get("move") or {}
        mname = move.get("name")
        if not mname:
            continue
        contexts: list[dict[str, Any]] = []
        for vgd in m.get("version_group_details", []):
            vg = (vgd.get("version_group") or {}).get("name")
            if vg not in groups:
                continue
            method = (vgd.get("move_learn_method") or {}).get("name")
            contexts.append(
                {
                    "version_group": vg,
                    "method": method,
                    "level_learned_at": vgd.get("level_learned_at"),
                }
            )
        if not contexts:
            continue
        if mname not in by_move:
            by_move[mname] = {"name": mname, "contexts": []}
        by_move[mname]["contexts"].extend(contexts)

    return sorted(by_move.values(), key=lambda x: x["name"])


def get_move_battle_metadata(move_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """
    PokeAPI ``move`` resource: priority bracket, type, and damage class.

    ``priority`` > 0 indicates increased-priority moves (heuristic for Armor Tail checks).
    """
    slug = _slug(move_name)
    url = f"{BASE_URL}/move/{slug}"
    data = fetch_json(url, f"move_{slug}", force_refresh=force_refresh)
    if not isinstance(data, dict):
        raise TypeError("Unexpected move payload")
    return {
        "name": data.get("name", slug),
        "priority": int(data.get("priority") or 0),
        "type": ((data.get("type") or {}) if isinstance(data.get("type"), dict) else {}).get("name"),
        "damage_class": (
            (data.get("damage_class") or {}) if isinstance(data.get("damage_class"), dict) else {}
        ).get("name"),
    }


def get_moves_gen9(name: str, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """
    Moves this Pokémon can learn in Generation 9 (any Gen 9 version group),
    deduplicated by move name. Each entry includes learn contexts for Gen 9.
    """
    return get_moves_for_generation(name, 9, force_refresh=force_refresh)


def get_species_classification(display_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """
    Legendary / mythical flags from cached ``pokemon-species`` (shared across forms).
    """
    p = get_pokemon_payload(display_name, force_refresh=force_refresh)
    species_meta = p.get("species") or {}
    url = species_meta.get("url")
    if not url or not isinstance(url, str):
        raise ValueError(f"No species URL on Pokémon payload for {display_name!r}")
    slug = str(species_meta.get("name") or "")
    tail = url.rstrip("/").split("/")[-1]
    cache_key = f"pokemon_species_{slug or tail}"
    data = fetch_json(url, cache_key, force_refresh=force_refresh)
    if not isinstance(data, dict):
        raise TypeError("Unexpected pokemon-species payload")
    return {
        "name": data.get("name"),
        "id": data.get("id"),
        "is_legendary": bool(data.get("is_legendary")),
        "is_mythical": bool(data.get("is_mythical")),
        "is_baby": bool(data.get("is_baby")),
    }


def clear_cache() -> None:
    """Remove all cached JSON files."""
    if CACHE_DIR.is_dir():
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass


def smogon_damage_calc(payload: dict[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    """
    Run Smogon's official ``@smogon/calc`` logic via ``calc_bridge.js`` (requires Node.js
    and ``npm install`` in the project root). See ``smogon_calc.run_smogon_calc`` for details.
    """
    from smogon_calc import run_smogon_calc

    return run_smogon_calc(payload, timeout=timeout)
