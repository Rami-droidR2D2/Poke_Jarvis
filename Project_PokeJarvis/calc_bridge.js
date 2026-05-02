#!/usr/bin/env node
/**
 * argv JSON bridge for @smogon/calc (official Smogon damage calculator).
 *
 * Usage: node calc_bridge.js '<json-string>'
 *
 * Payload shape:
 * {
 *   "gen" | "generation": 9,
 *   "attacker": "Garchomp" | { "species" | "name": "Garchomp", "level": 100, ... },
 *   "defender": "Slowbro" | { ... },
 *   "move": "Earthquake" | { "name": "Earthquake", "isCrit": false, ... },
 *   "field": { ... }   // optional, passed to Field constructor
 * }
 *
 * Pokémon option passthrough (stripping species/name only): any extra keys on attacker/defender
 * are forwarded to the Smogon Pokemon constructor. Useful mechanics fields include:
 *   - isDynamaxed (boolean), dynamaxLevel (number)
 *   - teraType (string), ability, item, nature, level, evs, ivs, boosts, status, ...
 *
 * Move objects may include flags forwarded to the Move constructor after stripping name:
 *   - useZ (boolean) — Z-Move variant where applicable
 *   - useMax (boolean) — Max move / Dynamax move variant
 * Mega Evolution is represented by species id (e.g. "Charizard-Mega-X"), not a separate flag here.
 */

"use strict";

const { calculate, Generations, Pokemon, Move, Field } = require("@smogon/calc");

function fail(code, err) {
  process.stderr.write(`${JSON.stringify({ ok: false, ...err })}\n`);
  process.exit(code);
}

function buildPokemon(gen, raw, label) {
  if (!raw || typeof raw !== "object") {
    throw new Error(`Missing ${label} object`);
  }
  const species = raw.species != null ? raw.species : raw.name;
  if (species == null || species === "") {
    throw new Error(`${label} requires species or name`);
  }
  const { species: _sp, name: _nm, ...options } = raw;
  return new Pokemon(gen, String(species), options);
}

function buildMove(gen, raw) {
  if (raw == null || raw === "") {
    throw new Error("Missing move");
  }
  if (typeof raw === "string") {
    return new Move(gen, raw);
  }
  const { name, ...options } = raw;
  if (name == null || name === "") {
    throw new Error("move.name is required when move is an object");
  }
  return new Move(gen, String(name), options);
}

/** Accept shorthand `"Pikachu"` as well as `{ species: "Pikachu", ... }`. */
function normalizePokemonSlot(raw, label) {
  if (raw == null || raw === "") {
    throw new Error(`Missing ${label}`);
  }
  if (typeof raw === "string") {
    return { species: raw };
  }
  return raw;
}

function main() {
  const jsonStr = process.argv[2];
  if (jsonStr == null || jsonStr === "") {
    fail(1, {
      error: "missing_payload",
      message: "Provide the request JSON as argv[2] (single string).",
    });
  }

  let payload;
  try {
    payload = JSON.parse(jsonStr);
  } catch (e) {
    fail(1, { error: "invalid_json", message: e.message });
  }

  payload.attacker = normalizePokemonSlot(payload.attacker, "attacker");
  payload.defender = normalizePokemonSlot(payload.defender, "defender");

  const genNum = payload.gen ?? payload.generation ?? 9;
  let gen;
  try {
    gen = Generations.get(genNum);
  } catch (e) {
    fail(1, { error: "bad_generation", message: e.message || String(e) });
  }

  let attacker;
  let defender;
  let move;
  let field;
  try {
    attacker = buildPokemon(gen, payload.attacker, "attacker");
    defender = buildPokemon(gen, payload.defender, "defender");
    move = buildMove(gen, payload.move);
    field = payload.field != null ? new Field(payload.field) : new Field();
  } catch (e) {
    fail(1, { error: "build_failed", message: e.message || String(e) });
  }

  let result;
  try {
    result = calculate(gen, attacker, defender, move, field);
  } catch (e) {
    fail(2, { error: "calculate_failed", message: e.message || String(e) });
  }

  const out = {
    ok: true,
    gen: gen.num,
    damage: result.damage,
    range: result.range(),
    desc: result.desc(),
    fullDesc: result.fullDesc(),
    moveDesc: result.moveDesc(),
    kochance: result.kochance(true),
    recovery: result.recovery(),
    recoil: result.recoil(),
  };
  console.log(JSON.stringify(out));
}

try {
  main();
} catch (e) {
  fail(2, { error: "bridge_error", message: e.message || String(e) });
}
