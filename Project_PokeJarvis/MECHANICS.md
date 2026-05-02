# Battle presets and damage mechanics

PokeJarvis selects a **preset** (`battle_presets.resolve_preset`) that fixes:

- **`calc_gen`** — generation passed to `@smogon/calc` via `calc_bridge.js`.
- **`allowed_mechanics`** — used by `team_constraints.validate_team_rules` (mega species names, Z/Max flags, Dynamax, Terastallize).
- **`learnset_generation`** — PokeAPI learnset checks in `team_builder.verify_team_moves`.

Preset ids: `gen9`, `gen7_sm`, `gen8_ss`, `legends_za` (Z-A–oriented alias until Smogon ships a dedicated generation).

## Team JSON

Per-slot mechanics supported on Pokémon builds:

- **`is_dynamaxed`**, **`dynamax_level`** → bridge `isDynamaxed`, `dynamaxLevel`.
- **`tera_type`** → bridge `teraType`.
- **Moves**: each slot may be a string or `{ "name": "...", "useZ": true, "useMax": true }` (flags optional) for calculator fidelity.

Mega forms use the mega **species** name (e.g. `Charizard-Mega-X`), consistent with `@smogon/calc`.

## Upgrading data for new games (e.g. Legends Z-A)

There is **no hand-maintained dex overlay**. When official data lands:

1. Bump **`@smogon/calc`** in `package.json` / `npm update`.
2. Refresh or clear PokeJarvis caches if species or learnsets fail (see project cache docs).
3. Adjust **`legends_za`** in `battle_presets.py` when Smogon documents the correct generation.

Unknown species will fail at calculation time with a clear bridge error until upstream packages include them.

## CLI

Global flags (repeat on each subcommand; place after the command name, e.g. `team-build rain --preset gen7_sm`):

- **`--preset`** — preset id (default `gen9`).
- **`--legendary-policy`** — `allow_all` | `ban_legendary_and_mythical` | `ban_mythical_only`.
- **`--mechanics-only-mega`** — forbid Z/Max/Dynamax/Tera flags on builds.
- **`--strict-rules`** — non-zero exit when team-build, analyze, or **coach** advisory fails validation expectations (`coach`: any warning with severity `warn`).

`analyze` uses the preset’s **`calc_gen`** unless **`--gen`** is set; **`--field-json`** merges over preset defaults.

## Team coach (intent + warnings)

See **`COACH.md`** for **`TeamIntent`** JSON and the **`coach`** subcommand (meta-threat typings, Armor Tail vs priority moves, coarse Speed checks).
