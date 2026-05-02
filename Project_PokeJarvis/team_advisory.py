"""Deterministic team advisory: meta threats, Armor Tail vs priority, coarse speed checks."""

from __future__ import annotations

from typing import Any

from battle_presets import resolve_preset
from data_engine import get_base_stats_types_abilities, get_move_battle_metadata
from team_constraints import validate_team_rules
from team_intent import TeamIntent, uses_placeholder_slots
from team_models import Team, move_slot_display
from type_effectiveness import attack_multiplier

# Minimal fallback when move API fails (slug form). Only moves with priority > 0 in cartridge logic.
_FALLBACK_INCREASED_PRIORITY_SLUGS = frozenset(
    {
        "fake-out",
        "extreme-speed",
        "quick-attack",
        "mach-punch",
        "bullet-punch",
        "ice-shard",
        "aqua-jet",
        "shadow-sneak",
        "vacuum-wave",
        "upper-hand",
        "sucker-punch",
        "accelerock",
        "water-shuriken",
    }
)


def _slug_move(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _species_display(name: str, core: dict[str, Any]) -> str:
    raw = core.get("name") or name
    return str(raw).replace("-", " ").title()


def _has_armor_tail_ability(species: str, *, force_refresh: bool) -> bool:
    core = get_base_stats_types_abilities(species, force_refresh=force_refresh)
    for a in core.get("abilities") or []:
        an = (a.get("name") or "").strip().lower()
        if an == "armor-tail":
            return True
    return False


def _armor_tail_active(intent: TeamIntent, *, force_refresh: bool) -> bool:
    afo = intent.assume_field_opponent
    if not afo:
        return False
    if afo.assume_armor_tail_active:
        return True
    if afo.lead_species:
        return _has_armor_tail_ability(afo.lead_species, force_refresh=force_refresh)
    return False


def _move_is_increased_priority(move_label: str, *, force_refresh: bool) -> bool:
    try:
        meta = get_move_battle_metadata(move_label, force_refresh=force_refresh)
        return int(meta.get("priority") or 0) > 0
    except Exception:
        slug = _slug_move(move_label)
        return slug in _FALLBACK_INCREASED_PRIORITY_SLUGS


def _filled_slot_count(intent: TeamIntent, partial_team: Team | None) -> int:
    if partial_team is not None:
        return 6
    return len(intent.must_include)


def team_advisory_report(
    intent: TeamIntent,
    *,
    team: Team,
    partial_team: Team | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Produce structured warnings from typings/STAB lanes, Armor Tail vs priority moves,
    and coarse base Speed gaps vs ``meta_threats``.

    Does not simulate damage, EV spreads, items, or field conditions beyond Armor Tail flag.
    """
    warnings: list[dict[str, Any]] = []
    filled = _filled_slot_count(intent, partial_team)
    placeholders = uses_placeholder_slots(intent, partial_team=partial_team)

    if filled == 0 and partial_team is None:
        warnings.append(
            {
                "code": "empty_intent",
                "severity": "info",
                "detail": "must_include is empty; add Pokémon stubs or pass --partial-team-json with a full team.",
            }
        )
        return {
            "ok": True,
            "severity": "ok",
            "warnings": warnings,
            "intent_echo": intent.to_dict(),
            "meta": {
                "filled_slots": 0,
                "placeholders_used": False,
                "speed_margin": intent.speed_margin,
                "max_team_base_speed": 0,
            },
            "rules_validation": None,
        }

    # Restrictions: avoid_species / avoid_types
    avoid_sp = {s.strip().lower().replace(" ", "-") for s in intent.avoid_species}
    avoid_ty = {t.strip().lower() for t in intent.avoid_types}

    for i in range(filled):
        slot = team.slots[i]
        sp_slug = _slug_move(slot.species)
        if sp_slug in avoid_sp:
            warnings.append(
                {
                    "code": "avoid_species",
                    "severity": "warn",
                    "slot": i,
                    "detail": f"Slot {i} ({slot.species}) appears on your avoid_species list.",
                }
            )
        try:
            core = get_base_stats_types_abilities(slot.species, force_refresh=force_refresh)
            stypes = [t.lower() for t in core.get("types") or []]
            if avoid_ty and avoid_ty.intersection(set(stypes)):
                hit = ", ".join(sorted(avoid_ty.intersection(set(stypes))))
                warnings.append(
                    {
                        "code": "avoid_type",
                        "severity": "info",
                        "slot": i,
                        "detail": f"Slot {i} ({slot.species}) has type(s) you listed to avoid: {hit}.",
                    }
                )
        except Exception as e:
            warnings.append(
                {
                    "code": "species_lookup",
                    "severity": "warn",
                    "slot": i,
                    "detail": f"Could not load typings for {slot.species!r}: {e}",
                }
            )

    # Threat lanes + speed
    team_base_spes: list[int] = []
    for i in range(filled):
        slot = team.slots[i]
        try:
            core = get_base_stats_types_abilities(slot.species, force_refresh=force_refresh)
            spe = int((core.get("stats") or {}).get("speed") or 0)
            team_base_spes.append(spe)
        except Exception:
            team_base_spes.append(0)

    max_team_spe = max(team_base_spes) if team_base_spes else 0

    for threat_raw in intent.meta_threats:
        try:
            tcore = get_base_stats_types_abilities(threat_raw, force_refresh=force_refresh)
        except Exception as e:
            warnings.append(
                {
                    "code": "threat_lookup",
                    "severity": "warn",
                    "detail": f"Could not load meta threat {threat_raw!r}: {e}",
                }
            )
            continue

        tlabel = _species_display(threat_raw, tcore)
        threat_types = [str(t).lower() for t in tcore.get("types") or []]
        threat_spe = int((tcore.get("stats") or {}).get("speed") or 0)

        for i in range(filled):
            slot = team.slots[i]
            try:
                score = get_base_stats_types_abilities(slot.species, force_refresh=force_refresh)
            except Exception:
                continue
            slot_types = [str(t).lower() for t in score.get("types") or []]
            slot_label = slot.species

            best_mult = 0.0
            best_types: list[str] = []
            for tt in threat_types:
                mult = attack_multiplier(tt, slot_types, force_refresh=force_refresh)
                if mult > best_mult:
                    best_mult = mult
                    best_types = [tt]
                elif mult == best_mult and mult > 0:
                    best_types.append(tt)

            if best_mult >= 2.0:
                stab_txt = "/".join(t.upper() for t in best_types)
                warnings.append(
                    {
                        "code": "threat_stab_lane",
                        "severity": "warn",
                        "slot": i,
                        "threat": threat_raw,
                        "detail": (
                            f"{tlabel}'s typings threaten slot {i} ({slot_label}) "
                            f"with ~{stab_txt} STAB coverage (~×{best_mult:g} type chart)."
                        ),
                    }
                )

            if threat_spe - max_team_spe >= intent.speed_margin and best_mult >= 2.0:
                warnings.append(
                    {
                        "code": "speed_threat_combo",
                        "severity": "warn",
                        "slot": i,
                        "threat": threat_raw,
                        "detail": (
                            f"{tlabel} has higher base Speed (+{threat_spe - max_team_spe} vs your team's "
                            f"max {max_team_spe}) and a ≥2× typing lane vs slot {i} ({slot_label})—risk "
                            f"of being outspeed and chunked (heuristic; ignores EVs/items)."
                        ),
                    }
                )

    # Armor Tail vs priority moves
    if _armor_tail_active(intent, force_refresh=force_refresh):
        for i in range(filled):
            slot = team.slots[i]
            for mi, mv in enumerate(slot.moves):
                label = move_slot_display(mv).strip()
                if not label:
                    continue
                if _move_is_increased_priority(label, force_refresh=force_refresh):
                    warnings.append(
                        {
                            "code": "armor_tail_priority",
                            "severity": "warn",
                            "slot": i,
                            "move_index": mi,
                            "detail": (
                                f"Slot {i} ({slot.species}) move {label!r} has increased priority; "
                                f"Armor Tail may block it (doubles heuristic)."
                            ),
                        }
                    )

    rules_val: dict[str, Any] | None = None
    if not placeholders:
        preset = resolve_preset(intent.preset_id)
        rules_val = validate_team_rules(
            team,
            preset,
            legendary_policy=intent.legendary_policy,
            mechanics_only_mega=intent.mechanics_only_mega,
            force_refresh=force_refresh,
        )
        if not rules_val["ok"]:
            warnings.append(
                {
                    "code": "preset_rules",
                    "severity": "warn",
                    "detail": f"Preset/rules validation failed ({len(rules_val['violations'])} violation(s)).",
                }
            )

    severe = sum(1 for w in warnings if w.get("severity") == "warn")
    return {
        "ok": severe == 0,
        "severity": "warn" if severe else "ok",
        "warnings": warnings,
        "intent_echo": intent.to_dict(),
        "meta": {
            "filled_slots": filled,
            "placeholders_used": placeholders,
            "speed_margin": intent.speed_margin,
            "max_team_base_speed": max_team_spe,
        },
        "rules_validation": rules_val,
    }
