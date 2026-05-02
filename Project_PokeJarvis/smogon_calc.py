"""Run official Smogon damage math via calc_bridge.js (@smogon/calc)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

def _project_root() -> Path:
    env = os.environ.get("POKEJARVIS_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent


_PROJECT_ROOT = _project_root()
_BRIDGE_SCRIPT = _PROJECT_ROOT / "calc_bridge.js"
# Fallback when PATH lacks nvm (e.g. GUI apps, some notebooks).
_NODE_FALLBACK = Path("/Users/ramisherif/.nvm/versions/node/v24.14.1/bin/node")


class SmogonCalcError(RuntimeError):
    """calc_bridge.js failed or returned an error payload."""


def _resolve_node_binary() -> str:
    explicit = os.environ.get("SMOGON_CALC_NODE")
    if explicit:
        return explicit
    found = shutil.which("node")
    if found:
        return found
    if _NODE_FALLBACK.is_file():
        return str(_NODE_FALLBACK)
    raise FileNotFoundError(
        "Node.js was not found on PATH. Install Node.js, run `npm install` in the project root, "
        "or set SMOGON_CALC_NODE to the full path of the node executable."
    )


def run_smogon_calc(payload: dict[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    """
    Execute @smogon/calc through calc_bridge.js (payload JSON passed as ``argv[2]``).

    ``payload`` matches calc_bridge.js: gen/generation, attacker, defender, move, optional field.
    Returns the parsed JSON object from stdout (includes ok, damage, range, desc, ...).
    """
    if not _BRIDGE_SCRIPT.is_file():
        raise FileNotFoundError(f"Missing bridge script: {_BRIDGE_SCRIPT}")

    node = _resolve_node_binary()
    data = json.dumps(payload, separators=(",", ":"))
    proc = subprocess.run(
        [node, str(_BRIDGE_SCRIPT), data],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(_PROJECT_ROOT),
        check=False,
    )

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    if proc.returncode != 0:
        msg = _parse_bridge_error(err) or err or out or f"exit {proc.returncode}"
        raise SmogonCalcError(msg)

    if not out:
        raise SmogonCalcError(err or "calc_bridge.js produced no stdout")

    try:
        result: dict[str, Any] = json.loads(out)
    except json.JSONDecodeError as e:
        raise SmogonCalcError(f"Invalid JSON from calc_bridge.js: {e}\n{out[:500]}") from e

    if not result.get("ok"):
        raise SmogonCalcError(json.dumps(result))
    return result


def _parse_bridge_error(stderr: str) -> str | None:
    if not stderr:
        return None
    line = stderr.splitlines()[-1]
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return stderr
    if isinstance(obj, dict) and obj.get("message"):
        return str(obj["message"])
    return line
