"""FastAPI surface for Project_PokeJarvis (imports engine via POKEJARVIS_ROOT)."""

import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from settings import settings

# Must run before any Project_PokeJarvis imports
_root = settings.resolved_root()
_root_s = str(_root)
if _root_s not in sys.path:
    sys.path.insert(0, _root_s)

from battle_presets import merge_field_json  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

from Jarvis_engine import (  # noqa: E402
    SmogonCalcError,
    Team,
    TeamIntent,
    UnknownPresetError,
    analyze_synergy,
    build_team,
    damage_matrix,
    draft_team_from_intent,
    get_pokemon_summary,
    list_archetypes,
    list_presets,
    resolve_preset,
    team_advisory_report,
    team_weakness_bundle,
    validate_team_rules,
    weakness_profile_for_species,
)

app = FastAPI(title="PokeJarvis UI API", version="0.1.0")


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Any, exc: HTTPException) -> JSONResponse:
    payload = exc.detail
    if isinstance(payload, dict):
        return JSONResponse(status_code=exc.status_code, content=payload)
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": str(payload)},
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(_request: Any, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": "Validation failed", "detail": exc.errors()},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _err(status: int, message: str, detail: Any = None) -> HTTPException:
    body: Dict[str, Any] = {"ok": False, "error": message}
    if detail is not None:
        body["detail"] = detail
    return HTTPException(status_code=status, detail=body)


class LookupBody(BaseModel):
    name: str = Field(..., min_length=1)
    refresh: bool = False


class TeamBuildBody(BaseModel):
    archetype: str = Field(..., min_length=1)
    preset: str = "gen9"
    verify_moves: bool = False
    refresh: bool = False
    legendary_policy: str = "allow_all"
    mechanics_only_mega: bool = False


class WeaknessBody(BaseModel):
    species: str = Field(..., min_length=1)
    refresh: bool = False


class SynergyBody(BaseModel):
    team: Dict[str, Any]
    opponent_team: Optional[Dict[str, Any]] = None


class CoachBody(BaseModel):
    intent: Dict[str, Any]
    partial_team: Optional[Dict[str, Any]] = None
    refresh: bool = False


class AnalyzeBody(BaseModel):
    team_a: Dict[str, Any]
    team_b: Dict[str, Any]
    preset: str = "gen9"
    gen: Optional[int] = None
    field: Optional[Dict[str, Any]] = None
    workers: int = 6
    move_slots: Union[List[int], str] = Field(default_factory=lambda: [0, 1])
    refresh: bool = False
    legendary_policy: str = "allow_all"
    mechanics_only_mega: bool = False


def _move_slot_tuple(move_slots: Union[List[int], str]) -> Tuple[int, ...]:
    if isinstance(move_slots, str):
        parts = [p.strip() for p in move_slots.split(",") if p.strip()]
        return tuple(int(x) for x in parts)
    if not move_slots:
        raise ValueError("move_slots must not be empty")
    return tuple(int(x) for x in move_slots)


SAMPLE_COACH_INTENT: Dict[str, Any] = {
    "preset_id": "gen9",
    "team_name": "Draft coach sample",
    "must_include": [
        {"species": "Garchomp", "level": 50, "moves": ["Earthquake", "Protect"]},
        {
            "species": "Incineroar",
            "level": 50,
            "moves": ["Fake Out", "Knock Off", "Flare Blitz", "Protect"],
        },
    ],
    "meta_threats": ["Flutter Mane", "Meowscarada"],
    "speed_margin": 20,
    "assume_field_opponent": {
        "lead_species": "Farigiraf",
        "assume_armor_tail_active": True,
    },
}

SAMPLE_TEAM: Dict[str, Any] = {
    "name": "Rain sample",
    "archetype": "rain",
    "slots": [
        {
            "species": "Pelipper",
            "level": 50,
            "ability": "Drizzle",
            "item": "Damp Rock",
            "nature": "Bold",
            "evs": {"hp": 252, "def": 252, "spd": 4},
            "ivs": {},
            "moves": ["Hurricane", "Weather Ball", "Tailwind", "Protect"],
        },
        {
            "species": "Barraskewda",
            "level": 50,
            "ability": "Swift Swim",
            "item": "Life Orb",
            "nature": "Adamant",
            "evs": {"atk": 252, "spe": 252, "spd": 4},
            "ivs": {},
            "moves": ["Liquidation", "Close Combat", "Ice Fang", "Protect"],
        },
        {
            "species": "Ferrothorn",
            "level": 50,
            "ability": "Iron Barbs",
            "item": "Leftovers",
            "nature": "Relaxed",
            "evs": {"hp": 252, "def": 252, "spd": 4},
            "ivs": {},
            "moves": ["Leech Seed", "Gyro Ball", "Body Press", "Protect"],
        },
        {
            "species": "Amoonguss",
            "level": 50,
            "ability": "Regenerator",
            "item": "Rocky Helmet",
            "nature": "Bold",
            "evs": {"hp": 252, "def": 252, "spd": 4},
            "ivs": {},
            "moves": ["Spore", "Sludge Bomb", "Pollen Puff", "Protect"],
        },
        {
            "species": "Thundurus",
            "level": 50,
            "ability": "Prankster",
            "item": "Safety Goggles",
            "nature": "Timid",
            "evs": {"spa": 252, "spe": 252, "hp": 4},
            "ivs": {},
            "moves": ["Wildbolt Storm", "Thunder Wave", "Rain Dance", "Protect"],
        },
        {
            "species": "Landorus",
            "level": 50,
            "ability": "Sheer Force",
            "item": "Life Orb",
            "nature": "Timid",
            "evs": {"spa": 252, "spe": 252, "hp": 4},
            "ivs": {},
            "moves": ["Earth Power", "Sludge Bomb", "Focus Blast", "Protect"],
        },
    ],
}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "pokejarvis_root": _root_s}


@app.get("/api/presets")
def api_presets() -> Dict[str, Any]:
    try:
        return {"ok": True, "presets": list_presets()}
    except Exception as e:  # noqa: BLE001
        raise _err(500, str(e)) from e


@app.get("/api/team/archetypes")
def api_team_archetypes() -> Dict[str, Any]:
    try:
        return {"ok": True, "archetypes": list_archetypes()}
    except Exception as e:  # noqa: BLE001
        raise _err(500, str(e)) from e


@app.get("/api/samples/coach-intent")
def sample_coach_intent() -> Dict[str, Any]:
    return {"ok": True, "sample": SAMPLE_COACH_INTENT}


@app.get("/api/samples/team")
def sample_team() -> Dict[str, Any]:
    return {"ok": True, "sample": SAMPLE_TEAM}


@app.post("/api/lookup")
def api_lookup(body: LookupBody) -> Dict[str, Any]:
    try:
        s = get_pokemon_summary(body.name, force_refresh=body.refresh)
        return {"ok": True, "result": s}
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e


@app.post("/api/team/build")
def api_team_build(body: TeamBuildBody) -> Dict[str, Any]:
    try:
        team, arch_field, preset_loaded = build_team(
            body.archetype,
            preset_id=body.preset,
            verify_moves=body.verify_moves,
            force_refresh=body.refresh,
        )
    except UnknownPresetError as e:
        raise _err(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e

    merged_field = merge_field_json(preset_loaded, arch_field, None)
    vr = validate_team_rules(
        team,
        preset_loaded,
        legendary_policy=body.legendary_policy,  # type: ignore[arg-type]
        mechanics_only_mega=body.mechanics_only_mega,
        force_refresh=body.refresh,
    )
    return {
        "ok": True,
        "result": {
            "team": team.to_dict(),
            "recommended_field": merged_field,
            "preset": preset_loaded.id,
            "rules_validation": vr,
        },
    }


@app.post("/api/weakness")
def api_weakness(body: WeaknessBody) -> Dict[str, Any]:
    try:
        w = weakness_profile_for_species(body.species, force_refresh=body.refresh)
        return {"ok": True, "result": w}
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e


@app.post("/api/synergy")
def api_synergy(body: SynergyBody) -> Dict[str, Any]:
    try:
        team = Team.from_dict(body.team)
    except Exception as e:  # noqa: BLE001
        raise _err(400, f"Invalid team: {e}") from e

    opp = None
    if body.opponent_team is not None:
        try:
            ot = Team.from_dict(body.opponent_team)
        except Exception as e:  # noqa: BLE001
            raise _err(400, f"Invalid opponent_team: {e}") from e
        opp = [get_pokemon_summary(s.species)["types"] for s in ot.slots]

    try:
        sym = analyze_synergy(team, opponent_type_pairs=opp)
        return {"ok": True, "result": sym}
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e


@app.post("/api/coach")
def api_coach(body: CoachBody) -> Dict[str, Any]:
    try:
        intent = TeamIntent.from_dict(body.intent)
    except Exception as e:  # noqa: BLE001
        raise _err(400, f"Invalid intent: {e}") from e

    partial = None
    if body.partial_team is not None:
        try:
            partial = Team.from_dict(body.partial_team)
        except Exception as e:  # noqa: BLE001
            raise _err(400, f"Invalid partial_team: {e}") from e

    try:
        team = draft_team_from_intent(intent, partial)
        report = team_advisory_report(
            intent,
            team=team,
            partial_team=partial,
            force_refresh=body.refresh,
        )
        return {"ok": True, "result": report}
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e


@app.post("/api/analyze")
def api_analyze(body: AnalyzeBody) -> Dict[str, Any]:
    try:
        preset_obj = resolve_preset(body.preset)
    except UnknownPresetError as e:
        raise _err(400, str(e)) from e

    try:
        ta = Team.from_dict(body.team_a)
        tb = Team.from_dict(body.team_b)
    except Exception as e:  # noqa: BLE001
        raise _err(400, f"Invalid team JSON: {e}") from e

    calc_gen = body.gen if body.gen is not None else preset_obj.calc_gen

    try:
        slots = _move_slot_tuple(body.move_slots)
    except ValueError as e:
        raise _err(400, str(e)) from e

    field_merged = merge_field_json(preset_obj, None, body.field)

    try:
        matrix = damage_matrix(
            ta,
            tb,
            gen=calc_gen,
            field=field_merged,
            max_workers=body.workers,
            move_slot_indices=slots,
        )
        bundle_a = team_weakness_bundle(ta, force_refresh=body.refresh)
        bundle_b = team_weakness_bundle(tb, force_refresh=body.refresh)
    except SmogonCalcError as e:
        raise _err(
            502,
            "Damage calculation failed (ensure Node.js and npm install in Project_PokeJarvis)",
            detail=str(e),
        ) from e
    except Exception as e:  # noqa: BLE001
        raise _err(400, str(e)) from e

    vr_a = validate_team_rules(
        ta,
        preset_obj,
        legendary_policy=body.legendary_policy,  # type: ignore[arg-type]
        mechanics_only_mega=body.mechanics_only_mega,
        force_refresh=body.refresh,
    )
    vr_b = validate_team_rules(
        tb,
        preset_obj,
        legendary_policy=body.legendary_policy,  # type: ignore[arg-type]
        mechanics_only_mega=body.mechanics_only_mega,
        force_refresh=body.refresh,
    )

    report = {
        "preset": preset_obj.id,
        "calc_gen": calc_gen,
        "field": field_merged,
        "damage_matrix": matrix,
        "weakness_team_a": bundle_a,
        "weakness_team_b": bundle_b,
        "rules_team_a": vr_a,
        "rules_team_b": vr_b,
    }
    return {"ok": True, "result": report}
