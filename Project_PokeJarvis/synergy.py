"""Heuristic synergy hints for doubles-oriented Gen 9 teams."""

from __future__ import annotations

from typing import Any

from data_engine import get_base_stats_types_abilities
from team_models import Team, move_slot_display
from type_effectiveness import defending_type_weaknesses


def _types_for(species: str) -> list[str]:
    return list(get_base_stats_types_abilities(species)["types"])


def analyze_synergy(
    team: Team,
    *,
    opponent_type_pairs: list[list[str]] | None = None,
) -> dict[str, Any]:
    """
    Produce bullet strings plus structured signals for agents/UI.

    ``opponent_type_pairs`` is optional list of opposing Pokémon typings (each 1–2 types).
    """
    hints: list[str] = []
    builds = team.slots

    abils = [(b.ability or "").replace(" ", "-").lower() for b in builds]

    if any("drizzle" in a for a in abils) and any("swift-swim" in a for a in abils):
        hints.append("Weather: Drizzle + Swift Swim enables doubled Speed Water attackers under Rain.")

    if any("drought" in a for a in abils) and any("chlorophyll" in a for a in abils):
        hints.append("Weather: Drought + Chlorophyll creates fast Grass attackers in Sun.")

    if any("drought" in a for a in abils) and any("Protosynthesis" in (b.ability or "") for b in builds):
        hints.append("Sun supports Paradox Protosynthesis users—Booster Energy or prolonged Sun helps.")

    if sum("Intimidate" in (b.ability or "") for b in builds) >= 1:
        hints.append("Intimidate user present—helps blunt opposing Attack-heavy leads.")

    if sum("Prankster" in (b.ability or "") for b in builds) >= 1:
        hints.append("Prankster utility supports priority Tailwind / Thunder Wave setups.")

    if sum("Regenerator" in (b.ability or "") for b in builds) >= 1:
        hints.append("Regenerator pivot improves successive Fake Out / redirection lanes.")

    fake_out_users = sum(
        1
        for b in builds
        if any(move_slot_display(m).strip().lower() == "fake out" for m in b.moves)
    )
    if fake_out_users >= 2:
        hints.append("Multiple Fake Out users—strong opener pressure but avoid stacking redundant disruption.")

    profs = [defending_type_weaknesses(_types_for(b.species)) for b in builds]
    type_sets = [set(_types_for(b.species)) for b in builds]
    overlap_weak: dict[str, int] = {}
    for i in range(len(builds)):
        wi = set(profs[i].get("weakness") or []) | set(profs[i].get("quad_weakness") or [])
        for j in range(i + 1, len(builds)):
            wj = set(profs[j].get("weakness") or []) | set(profs[j].get("quad_weakness") or [])
            shared = wi & wj
            for st in shared:
                overlap_weak[st] = overlap_weak.get(st, 0) + 1
    if overlap_weak:
        worst = sorted(overlap_weak.items(), key=lambda x: (-x[1], x[0]))[:5]
        for atk_type, cnt in worst:
            if cnt >= 2:
                hints.append(
                    f"Typing overlap: several Pokémon share vulnerabilities to {atk_type.upper()} moves "
                    f"(pairs flagged ≈ {cnt}); diversify pivots or redirection."
                )
                break

    stab_overlap_penalty = 0
    for i in range(len(type_sets)):
        for j in range(i + 1, len(type_sets)):
            if type_sets[i] == type_sets[j]:
                stab_overlap_penalty += 1
    if stab_overlap_penalty:
        hints.append("Repeated typings detected—consider complementary typings for sequential pressures.")

    if opponent_type_pairs:
        threatening = []
        for opp_types in opponent_type_pairs:
            for b in builds:
                wt = defending_type_weaknesses([t.lower() for t in opp_types])
                your_types = _types_for(b.species)
                best_eff = max(wt["multipliers_by_attack_type"].get(yt, 1.0) for yt in your_types)
                if best_eff >= 2:
                    threatening.append((b.species, opp_types))
                    break
        if threatening:
            hint_txt = ", ".join(f"{s} vs {ot}" for s, ot in threatening[:3])
            hints.append(f"Opponent typings expose STAB lanes vs {hint_txt}")

    score = max(0, 100 - 10 * stab_overlap_penalty + 5 * min(fake_out_users, 2))
    return {
        "team_name": team.name,
        "archetype": team.archetype,
        "hints": hints,
        "score_heuristic": score,
        "meta": {
            "fake_out_users": fake_out_users,
            "stab_overlap_pairs": stab_overlap_penalty,
        },
    }
