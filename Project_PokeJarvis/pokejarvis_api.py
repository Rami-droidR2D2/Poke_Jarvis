"""HTTP API for PokeJarvis (damage matrix / analyze)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from battle_analysis import damage_matrix, team_weakness_bundle
from battle_presets import UnknownPresetError, list_presets, merge_field_json, resolve_preset
from team_constraints import LegendaryPolicy, validate_team_rules
from team_models import Team

app = FastAPI(title="PokeJarvis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _team_from_body(raw: Union[Dict[str, Any], str]) -> Team:
    if isinstance(raw, str):
        return Team.from_dict(json.loads(raw))
    return Team.from_dict(raw)


class AnalyzeBody(BaseModel):
    team_a: Union[Dict[str, Any], str]
    team_b: Union[Dict[str, Any], str]
    preset: str = "gen9"
    gen: Optional[int] = None
    field: Union[Dict[str, Any], None] = None
    workers: int = Field(default=6, ge=1, le=32)
    move_slots: str = "0,1"
    legendary_policy: LegendaryPolicy = "allow_all"
    mechanics_only_mega: bool = False
    refresh: bool = False


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/presets")
def presets() -> Dict[str, List[str]]:
    return {"presets": list_presets()}


@app.post("/analyze")
def analyze(body: AnalyzeBody) -> Dict[str, Any]:
    try:
        preset_obj = resolve_preset(body.preset)
    except UnknownPresetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        ta = _team_from_body(body.team_a)
        tb = _team_from_body(body.team_b)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid team JSON: {e}") from e

    calc_gen = body.gen if body.gen is not None else preset_obj.calc_gen
    field_merged = merge_field_json(preset_obj, None, body.field)

    move_slot_indices: Tuple[int, ...]
    try:
        move_slot_indices = tuple(int(x.strip()) for x in body.move_slots.split(",") if x.strip() != "")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid move_slots: {e}") from e

    matrix = damage_matrix(
        ta,
        tb,
        gen=calc_gen,
        field=field_merged,
        max_workers=body.workers,
        move_slot_indices=move_slot_indices,
    )
    bundle_a = team_weakness_bundle(ta, force_refresh=body.refresh)
    bundle_b = team_weakness_bundle(tb, force_refresh=body.refresh)

    vr_a = validate_team_rules(
        ta,
        preset_obj,
        legendary_policy=body.legendary_policy,
        mechanics_only_mega=body.mechanics_only_mega,
        force_refresh=body.refresh,
    )
    vr_b = validate_team_rules(
        tb,
        preset_obj,
        legendary_policy=body.legendary_policy,
        mechanics_only_mega=body.mechanics_only_mega,
        force_refresh=body.refresh,
    )

    return {
        "preset": preset_obj.id,
        "calc_gen": calc_gen,
        "field": field_merged,
        "damage_matrix": matrix,
        "weakness_team_a": bundle_a,
        "weakness_team_b": bundle_b,
        "rules_team_a": vr_a,
        "rules_team_b": vr_b,
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "pokejarvis",
        "docs": "/docs",
        "analyze": "POST /analyze",
    }

