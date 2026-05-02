# Team coach (`coach` command)

Use a **TeamIntent** JSON file to capture recommendations and restrictions **before** locking a full team. The CLI runs deterministic checks (no embedded LLM):

```bash
python pokejarvis_cli.py coach examples/coach_intent_sample.json --refresh
python pokejarvis_cli.py coach my_intent.json --partial-team-json path/to/team.json
```

- **`--partial-team-json`**: full 6-slot team (same shape as other team JSON files). Entries in **`must_include`** overlay slots `0..N-1` by species/moves/etc.
- **`--strict-rules`**: exit status `1` when the advisory report has any **`severity: "warn"`** warning (or failed preset validation).

Natural-language commands are handled in Cursor via the **pokejarvis-team-coach** skill (NL → JSON → `coach`).

## TeamIntent fields

| Field | Meaning |
|-------|---------|
| `preset_id` | Passed to [`battle_presets.resolve_preset`](battle_presets.py) for rules validation when there are no placeholder slots. |
| `legendary_policy` | `allow_all` \| `ban_legendary_and_mythical` \| `ban_mythical_only` |
| `mechanics_only_mega` | Same as CLI flag; forwarded to [`team_constraints.validate_team_rules`](team_constraints.py). |
| `must_include` | List of partial Pokémon objects (`species` required). Fewer than six entries pad with `placeholder_species` (default `rattata`). |
| `avoid_species` / `avoid_types` | Soft bans; emit warnings if violated. |
| `meta_threats` | Species names to score STAB lanes and coarse Speed gaps against your filled slots. |
| `assume_field_opponent` | `{ "lead_species": "Farigiraf", "assume_armor_tail_active": true }` for Armor Tail vs priority-move checks. |
| `placeholder_species` | Neutral filler for unused slots (ignored for validation when placeholders are used). |
| `speed_margin` | Minimum base Speed gap (default `20`) to flag **`speed_threat_combo`** with a super-effective typing lane. |

## Limitations

- Typing/STAB warnings use the type chart only—not actual movesets, damage calcs, items, or Tailwind/Paralysis.
- **Armor Tail**: increased priority is inferred from PokeAPI move **`priority > 0`** (with a small offline fallback list if the move fetch fails).

## Python API

See **`team_advisory.team_advisory_report`**, **`team_intent.load_team_intent`**, **`team_intent.draft_team_from_intent`** (also exported from **`Jarvis_engine`**).
