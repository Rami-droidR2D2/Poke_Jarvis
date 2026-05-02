---
name: pokejarvis-team-coach
description: >-
  Convert natural-language Pokémon team constraints into TeamIntent JSON and run
  pokejarvis_cli coach for advisory warnings (threat typings, Armor Tail vs priority,
  speed heuristics). Use when the user asks to plan or sanity-check a team before building.
---

# PokeJarvis team coach (NL → JSON → `coach`)

When the user describes **restrictions** ("no legendaries", "I want rain + Barraskewda") or **worries** ("weak to Flutter Mane?", "Fake Out into Armor Tail?"), produce **valid `TeamIntent` JSON** matching `COACH.md` in the repo root, write it to a temp path or `examples/` only if the user agrees, then run:

```bash
python3 pokejarvis_cli.py coach <intent.json> [--partial-team-json TEAM.json] [--strict-rules]
```

From the project repository root (directory containing `pokejarvis_cli.py`).

## TeamIntent checklist

- **`preset_id`**: default `gen9` unless the user specifies another preset (`gen7_sm`, `gen8_ss`, `legends_za`).
- **`must_include`**: each entry **must** include `"species"`. Optional: `moves`, `ability`, `item`, `evs`, etc. (same keys as team slot JSON).
- **`meta_threats`**: species names the user cites as scary—e.g. Flutter Mane, Meowscarada, Greninja, Farigiraf.
- **`assume_field_opponent`**: if they mention **Armor Tail** or **Farigiraf**, set `"assume_armor_tail_active": true` and/or `"lead_species": "Farigiraf"`.
- **`avoid_species` / `avoid_types`**: soft bans from prose ("no fairies" → `avoid_types: ["fairy"]`).
- **`legendary_policy`**: map phrases like "ban legends" → `ban_legendary_and_mythical`, "no mythicals" → `ban_mythical_only`.

## Interpreting coach output

Explain **`warnings[].detail`** in plain language. Clarify limits: type-chart STAB lanes only, no damage sim; Speed compare uses **base Speed** and **`speed_margin`** unless they merge a full EV’d team via **`--partial-team-json`**.

## API shortcut

Alternatively call **`Jarvis_engine.team_advisory_report`** with **`draft_team_from_intent(load_team_intent(path))`** inside Python tools—same logic as the CLI.
