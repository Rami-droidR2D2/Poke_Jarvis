#!/usr/bin/env python3
"""PokeJarvis CLI: lookup, archetype teams, damage matrix, synergy."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from battle_analysis import damage_matrix, team_weakness_bundle, weakness_profile_for_species
from battle_presets import UnknownPresetError, list_presets, merge_field_json, resolve_preset
from pokedex_service import get_pokemon_summary
from synergy import analyze_synergy
from team_advisory import team_advisory_report
from team_builder import build_team, list_archetypes
from team_constraints import LegendaryPolicy, validate_team_rules
from team_intent import draft_team_from_intent, load_team_intent
from team_models import Team, team_from_json_str

_LOG = logging.getLogger("pokejarvis")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def cmd_lookup(args: argparse.Namespace) -> int:
    s = get_pokemon_summary(args.name, force_refresh=args.refresh)
    print(json.dumps(s, indent=2, ensure_ascii=False))
    return 0


def cmd_team_build(args: argparse.Namespace) -> int:
    try:
        team, arch_field, preset_loaded = build_team(
            args.archetype,
            preset_id=args.preset,
            verify_moves=args.verify_moves,
            force_refresh=args.refresh,
        )
    except UnknownPresetError as e:
        print(str(e), file=sys.stderr)
        return 2
    merged_field = merge_field_json(preset_loaded, arch_field, None)
    vr = validate_team_rules(
        team,
        preset_loaded,
        legendary_policy=args.legendary_policy,
        mechanics_only_mega=args.mechanics_only_mega,
        force_refresh=args.refresh,
    )
    out = {
        "team": team.to_dict(),
        "recommended_field": merged_field,
        "preset": preset_loaded.id,
        "rules_validation": vr,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if args.strict_rules and not vr["ok"]:
        return 1
    return 0


def cmd_team_list(_args: argparse.Namespace) -> int:
    for a in list_archetypes():
        print(a)
    return 0


def cmd_weakness(args: argparse.Namespace) -> int:
    w = weakness_profile_for_species(args.species, force_refresh=args.refresh)
    print(json.dumps(w, indent=2, ensure_ascii=False))
    return 0


def cmd_synergy(args: argparse.Namespace) -> int:
    raw = Path(args.team_json).read_text(encoding="utf-8")
    team = team_from_json_str(raw)
    opp = None
    if args.opponent_json:
        raw_o = Path(args.opponent_json).read_text(encoding="utf-8")
        ot = team_from_json_str(raw_o)
        opp = [get_pokemon_summary(s.species)["types"] for s in ot.slots]
    sym = analyze_synergy(team, opponent_type_pairs=opp)
    print(json.dumps(sym, indent=2, ensure_ascii=False))
    return 0


def cmd_coach(args: argparse.Namespace) -> int:
    try:
        intent = load_team_intent(args.intent)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        print(str(e), file=sys.stderr)
        return 2

    partial: Team | None = None
    if args.partial_team_json:
        partial = team_from_json_str(Path(args.partial_team_json).read_text(encoding="utf-8"))

    team = draft_team_from_intent(intent, partial)
    report = team_advisory_report(
        intent,
        team=team,
        partial_team=partial,
        force_refresh=args.refresh,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.strict_rules and not report.get("ok", False):
        return 1
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        preset_obj = resolve_preset(args.preset)
    except UnknownPresetError as e:
        print(str(e), file=sys.stderr)
        return 2

    ta = team_from_json_str(Path(args.team_a_json).read_text(encoding="utf-8"))
    tb = team_from_json_str(Path(args.team_b_json).read_text(encoding="utf-8"))
    calc_gen = args.gen if args.gen is not None else preset_obj.calc_gen

    field_user = None
    if args.field_json:
        field_user = json.loads(Path(args.field_json).read_text(encoding="utf-8"))
    field_merged = merge_field_json(preset_obj, None, field_user)

    matrix = damage_matrix(
        ta,
        tb,
        gen=calc_gen,
        field=field_merged,
        max_workers=args.workers,
        move_slot_indices=tuple(int(x) for x in args.move_slots.split(",")),
    )
    bundle_a = team_weakness_bundle(ta, force_refresh=args.refresh)
    bundle_b = team_weakness_bundle(tb, force_refresh=args.refresh)

    vr_a = validate_team_rules(
        ta,
        preset_obj,
        legendary_policy=args.legendary_policy,
        mechanics_only_mega=args.mechanics_only_mega,
        force_refresh=args.refresh,
    )
    vr_b = validate_team_rules(
        tb,
        preset_obj,
        legendary_policy=args.legendary_policy,
        mechanics_only_mega=args.mechanics_only_mega,
        force_refresh=args.refresh,
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
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.strict_rules and (not vr_a["ok"] or not vr_b["ok"]):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    preset_help = f"battle preset ({', '.join(list_presets())})"
    lp_choices: list[LegendaryPolicy] = [
        "allow_all",
        "ban_legendary_and_mythical",
        "ban_mythical_only",
    ]

    parser = argparse.ArgumentParser(description="PokeJarvis competitive toolkit")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--preset", default="gen9", metavar="ID", help=preset_help)
    common.add_argument(
        "--legendary-policy",
        choices=lp_choices,
        default="allow_all",
        help="restrict legendary/mythical Pokémon in rule validation",
    )
    common.add_argument(
        "--mechanics-only-mega",
        action="store_true",
        help="forbid Z/Max/Dynamax/Tera flags on Pokémon builds (validation)",
    )
    common.add_argument(
        "--strict-rules",
        action="store_true",
        help="exit with status 1 when validation/coach advisory fails (team-build / analyze / coach)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_l = sub.add_parser("lookup", parents=[common], help="full Pokémon summary (Gen 9 moves)")
    p_l.add_argument("name", help="species name")
    p_l.add_argument("--refresh", action="store_true")
    p_l.set_defaults(func=cmd_lookup)

    p_tb = sub.add_parser("team-build", parents=[common], help="load curated archetype team JSON")
    p_tb.add_argument("archetype", help="e.g. rain, sun")
    p_tb.add_argument("--verify-moves", action="store_true")
    p_tb.add_argument("--refresh", action="store_true", help="refresh PokeAPI caches for validation")
    p_tb.set_defaults(func=cmd_team_build)

    p_tl = sub.add_parser("team-list", parents=[common], help="list archetype ids")
    p_tl.set_defaults(func=cmd_team_list)

    p_w = sub.add_parser("weakness", parents=[common], help="type-chart weakness profile for species")
    p_w.add_argument("species")
    p_w.add_argument("--refresh", action="store_true")
    p_w.set_defaults(func=cmd_weakness)

    p_s = sub.add_parser("synergy", parents=[common], help="heuristic synergy hints for team JSON")
    p_s.add_argument("team_json", type=str)
    p_s.add_argument("--opponent-json", type=str, default=None)
    p_s.set_defaults(func=cmd_synergy)

    p_c = sub.add_parser(
        "coach",
        parents=[common],
        help="advisory warnings from TeamIntent JSON (threats, Armor Tail vs priority, speed heuristics)",
    )
    p_c.add_argument("intent", type=str, help="path to TeamIntent JSON file")
    p_c.add_argument(
        "--partial-team-json",
        type=str,
        default=None,
        help="full 6-slot team JSON; intent.must_include overlays first N slots",
    )
    p_c.add_argument("--refresh", action="store_true", help="refresh PokeAPI caches")
    p_c.set_defaults(func=cmd_coach)

    p_a = sub.add_parser("analyze", parents=[common], help="damage matrix + weakness bundles for two team JSON files")
    p_a.add_argument("team_a_json")
    p_a.add_argument("team_b_json")
    p_a.add_argument(
        "--gen",
        type=int,
        default=None,
        metavar="N",
        help="override @smogon/calc generation (default: preset calc_gen)",
    )
    p_a.add_argument("--field-json", type=str, default=None, help="calc Field JSON path (merged over preset defaults)")
    p_a.add_argument("--workers", type=int, default=6)
    p_a.add_argument("--move-slots", type=str, default="0,1", help="comma indices into each moves[]")
    p_a.add_argument("--refresh", action="store_true")
    p_a.set_defaults(func=cmd_analyze)

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
