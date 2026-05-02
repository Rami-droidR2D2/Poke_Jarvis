const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

type PresetsResponse = { presets: string[] };

async function loadJson(path: string): Promise<unknown> {
  const r = await fetch(path);
  if (!r.ok) {
    throw new Error(`HTTP ${r.status} loading ${path}`);
  }
  return r.json() as unknown;
}

function parseTeams(rawA: string, rawB: string): { team_a: unknown; team_b: unknown } {
  let team_a: unknown;
  let team_b: unknown;
  try {
    team_a = JSON.parse(rawA);
  } catch (e) {
    throw new Error(`Team A: ${String(e)}`);
  }
  try {
    team_b = JSON.parse(rawB);
  } catch (e) {
    throw new Error(`Team B: ${String(e)}`);
  }
  return { team_a, team_b };
}

async function populatePresets(select: HTMLSelectElement) {
  select.innerHTML = "";
  try {
    const r = await fetch(`${API_BASE}/presets`);
    if (!r.ok) {
      throw new Error(await r.text());
    }
    const data = (await r.json()) as PresetsResponse;
    for (const p of data.presets) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      select.append(opt);
    }
    if (!data.presets.includes("gen9")) {
      const opt = document.createElement("option");
      opt.value = "gen9";
      opt.textContent = "gen9";
      select.append(opt);
      select.value = "gen9";
    } else {
      select.value = "gen9";
    }
  } catch {
    ["gen9", "gen7_sm", "gen8_ss", "legends_za"].forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      select.append(opt);
    });
    select.value = "gen9";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const presetSel = document.getElementById("preset") as HTMLSelectElement;
  const fieldTa = document.getElementById("field") as HTMLTextAreaElement;
  const taA = document.getElementById("teamA") as HTMLTextAreaElement;
  const taB = document.getElementById("teamB") as HTMLTextAreaElement;
  const btn = document.getElementById("analyze") as HTMLButtonElement;
  const statusEl = document.getElementById("status") as HTMLSpanElement;
  const outEl = document.getElementById("output") as HTMLPreElement;

  void populatePresets(presetSel);

  document.getElementById("loadRain")?.addEventListener("click", async () => {
    try {
      taA.value = JSON.stringify(await loadJson("/samples/rain.json"), null, 2);
      fieldTa.value = JSON.stringify({ weather: "Rain" });
      statusEl.textContent = "";
    } catch (e) {
      statusEl.textContent = String(e);
    }
  });

  document.getElementById("loadSun")?.addEventListener("click", async () => {
    try {
      taB.value = JSON.stringify(await loadJson("/samples/sun.json"), null, 2);
      statusEl.textContent = "";
    } catch (e) {
      statusEl.textContent = String(e);
    }
  });

  btn.addEventListener("click", async () => {
    outEl.textContent = "";
    let fieldParsed: Record<string, unknown> | undefined;
    const trimmed = fieldTa.value.trim();
    if (trimmed) {
      try {
        fieldParsed = JSON.parse(trimmed) as Record<string, unknown>;
      } catch (e) {
        statusEl.textContent = `Field JSON: ${String(e)}`;
        return;
      }
    }

    let teams;
    try {
      teams = parseTeams(taA.value, taB.value);
    } catch (e) {
      statusEl.textContent = String(e);
      return;
    }

    btn.disabled = true;
    statusEl.textContent = "Running…";

    try {
      const r = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...teams,
          preset: presetSel.value,
          field: fieldParsed,
          legendary_policy: "allow_all",
        }),
      });

      const text = await r.text();
      try {
        const json = JSON.parse(text) as unknown;
        outEl.textContent =
          typeof json === "object" && json !== null && "detail" in json && !r.ok
            ? JSON.stringify(json, null, 2)
            : JSON.stringify(json, null, 2);
      } catch {
        outEl.textContent = text;
      }

      if (!r.ok) {
        statusEl.textContent = `Error ${r.status}`;
      } else {
        statusEl.textContent = "Done.";
      }
    } catch (e) {
      statusEl.textContent = String(e);
      outEl.textContent = `${e}`;
    } finally {
      btn.disabled = false;
    }
  });
});
