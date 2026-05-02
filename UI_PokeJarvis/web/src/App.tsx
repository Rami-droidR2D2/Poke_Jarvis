import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { apiFetch } from './api/client'
import './App.css'

type TabId =
  | 'lookup'
  | 'team-build'
  | 'coach'
  | 'analyze'
  | 'synergy'
  | 'weakness'

const TABS: { id: TabId; label: string }[] = [
  { id: 'lookup', label: 'Lookup' },
  { id: 'team-build', label: 'Team build' },
  { id: 'coach', label: 'Coach' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'synergy', label: 'Synergy' },
  { id: 'weakness', label: 'Weakness' },
]

const LEGENDARY_POLICIES = [
  'allow_all',
  'ban_legendary_and_mythical',
  'ban_mythical_only',
] as const

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function ResultPanel(props: {
  title: string
  data: unknown
  extra?: ReactNode
  filename: string
  hideRaw?: boolean
}) {
  const text = useMemo(() => prettyJson(props.data), [props.data])

  const copy = () => {
    void navigator.clipboard.writeText(text)
  }

  const download = () => {
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="result-panel">
      <div className="result-toolbar">
        <h3>{props.title}</h3>
        <button type="button" className="btn secondary" onClick={copy}>
          Copy JSON
        </button>
        <button type="button" className="btn secondary" onClick={download}>
          Download
        </button>
      </div>
      {props.extra}
      {!props.hideRaw ? <pre className="json-out">{text}</pre> : null}
    </section>
  )
}

function CoachWarnings({ report }: { report: Record<string, unknown> }) {
  const warnings = report.warnings as
    | { severity?: string; detail?: string; code?: string }[]
    | undefined
  const hard = warnings?.filter((w) => w.severity === 'warn') ?? []
  if (!hard.length) return null
  return (
    <div className="warn-banner" role="alert">
      <strong>Coach warnings</strong>
      <ul>
        {hard.map((w, i) => (
          <li key={i}>
            <code>{w.code ?? 'warn'}</code> {w.detail}
          </li>
        ))}
      </ul>
    </div>
  )
}

function AnalyzeSections({ result }: { result: Record<string, unknown> }) {
  const keys = [
    'preset',
    'calc_gen',
    'field',
    'damage_matrix',
    'weakness_team_a',
    'weakness_team_b',
    'rules_team_a',
    'rules_team_b',
  ] as const
  return (
    <div className="analyze-sections">
      {keys.map((k) => (
        <details key={k} open={k === 'damage_matrix'}>
          <summary>{k}</summary>
          <pre className="json-nested">{prettyJson(result[k])}</pre>
        </details>
      ))}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState<TabId>('lookup')
  const [presets, setPresets] = useState<string[]>([])
  const [archetypes, setArchetypes] = useState<string[]>([])
  const [metaErr, setMetaErr] = useState<string | null>(null)

  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<unknown>(null)
  const [analyzeMode, setAnalyzeMode] = useState(false)

  const [lookupName, setLookupName] = useState('Pikachu')
  const [lookupRefresh, setLookupRefresh] = useState(false)

  const [tbArchetype, setTbArchetype] = useState('rain')
  const [tbPreset, setTbPreset] = useState('gen9')
  const [tbVerifyMoves, setTbVerifyMoves] = useState(false)
  const [tbRefresh, setTbRefresh] = useState(false)
  const [tbLegendary, setTbLegendary] = useState<string>('allow_all')
  const [tbMega, setTbMega] = useState(false)

  const [coachIntentJson, setCoachIntentJson] = useState('{}')
  const [coachPartialJson, setCoachPartialJson] = useState('')
  const [coachRefresh, setCoachRefresh] = useState(false)

  const [teamAJson, setTeamAJson] = useState('')
  const [teamBJson, setTeamBJson] = useState('')
  const [anPreset, setAnPreset] = useState('gen9')
  const [anGen, setAnGen] = useState('')
  const [anWorkers, setAnWorkers] = useState(6)
  const [anMoveSlots, setAnMoveSlots] = useState('0,1')
  const [anFieldJson, setAnFieldJson] = useState('')
  const [anRefresh, setAnRefresh] = useState(false)
  const [anLegendary, setAnLegendary] = useState<string>('allow_all')
  const [anMega, setAnMega] = useState(false)

  const [synTeamJson, setSynTeamJson] = useState('')
  const [synOppJson, setSynOppJson] = useState('')

  const [wkSpecies, setWkSpecies] = useState('Landorus')
  const [wkRefresh, setWkRefresh] = useState(false)

  useEffect(() => {
    setAnalyzeMode(false)
  }, [tab])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [pr, ar] = await Promise.all([
          apiFetch<{ presets: string[] }>('/api/presets'),
          apiFetch<{ archetypes: string[] }>('/api/team/archetypes'),
        ])
        if (cancelled) return
        setPresets(pr.presets ?? [])
        setArchetypes(ar.archetypes ?? [])
        setMetaErr(null)
      } catch (e) {
        if (!cancelled) setMetaErr(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setErr(null)
      setLoading(true)
      setAnalyzeMode(false)
      try {
        await fn()
      } catch (e) {
        setResult(null)
        setErr(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  const loadCoachSample = async () => {
    const d = await apiFetch<{ sample: unknown }>('/api/samples/coach-intent')
    setCoachIntentJson(prettyJson(d.sample))
  }

  const loadTeamSampleAll = async () => {
    const d = await apiFetch<{ sample: unknown }>('/api/samples/team')
    const t = prettyJson(d.sample)
    setSynTeamJson(t)
    setTeamAJson(t)
    setTeamBJson(t)
  }

  const loadCoachPartialSample = async () => {
    const d = await apiFetch<{ sample: unknown }>('/api/samples/team')
    setCoachPartialJson(prettyJson(d.sample))
  }

  const submitLookup = () =>
    run(async () => {
      const d = await apiFetch<{ result: unknown }>('/api/lookup', {
        method: 'POST',
        body: JSON.stringify({ name: lookupName.trim(), refresh: lookupRefresh }),
      })
      setResult(d.result)
    })

  const submitTeamBuild = () =>
    run(async () => {
      const d = await apiFetch<{ result: unknown }>('/api/team/build', {
        method: 'POST',
        body: JSON.stringify({
          archetype: tbArchetype.trim(),
          preset: tbPreset,
          verify_moves: tbVerifyMoves,
          refresh: tbRefresh,
          legendary_policy: tbLegendary,
          mechanics_only_mega: tbMega,
        }),
      })
      setResult(d.result)
    })

  const submitCoach = () =>
    run(async () => {
      const intent = JSON.parse(coachIntentJson) as Record<string, unknown>
      let partial_team: Record<string, unknown> | undefined
      const pt = coachPartialJson.trim()
      if (pt) partial_team = JSON.parse(pt) as Record<string, unknown>
      const d = await apiFetch<{ result: unknown }>('/api/coach', {
        method: 'POST',
        body: JSON.stringify({
          intent,
          partial_team,
          refresh: coachRefresh,
        }),
      })
      setResult(d.result)
    })

  const submitAnalyze = () =>
    run(async () => {
      const team_a = JSON.parse(teamAJson) as Record<string, unknown>
      const team_b = JSON.parse(teamBJson) as Record<string, unknown>
      const genRaw = anGen.trim()
      const fieldRaw = anFieldJson.trim()
      const body: Record<string, unknown> = {
        team_a,
        team_b,
        preset: anPreset,
        workers: anWorkers,
        move_slots: anMoveSlots.trim() || '0,1',
        refresh: anRefresh,
        legendary_policy: anLegendary,
        mechanics_only_mega: anMega,
      }
      if (genRaw) body.gen = Number(genRaw)
      if (fieldRaw) body.field = JSON.parse(fieldRaw) as Record<string, unknown>
      const d = await apiFetch<{ result: Record<string, unknown> }>(
        '/api/analyze',
        { method: 'POST', body: JSON.stringify(body) },
      )
      setAnalyzeMode(true)
      setResult(d.result)
    })

  const submitSynergy = () =>
    run(async () => {
      const team = JSON.parse(synTeamJson) as Record<string, unknown>
      const oppRaw = synOppJson.trim()
      const body: Record<string, unknown> = { team }
      if (oppRaw) body.opponent_team = JSON.parse(oppRaw) as Record<string, unknown>
      const d = await apiFetch<{ result: unknown }>('/api/synergy', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setResult(d.result)
    })

  const submitWeakness = () =>
    run(async () => {
      const d = await apiFetch<{ result: unknown }>('/api/weakness', {
        method: 'POST',
        body: JSON.stringify({
          species: wkSpecies.trim(),
          refresh: wkRefresh,
        }),
      })
      setResult(d.result)
    })

  const presetSelect =
    presets.length > 0 ? (
      <select
        className="select"
        value={tbPreset}
        onChange={(e) => setTbPreset(e.target.value)}
      >
        {presets.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    ) : (
      <input
        className="input"
        value={tbPreset}
        onChange={(e) => setTbPreset(e.target.value)}
      />
    )

  return (
    <div className="app-root">
      <header className="header">
        <h1>PokeJarvis</h1>
        <p className="subtitle">
          Structured commands against your local{' '}
          <code>Project_PokeJarvis</code> engine (via API). Coach expects{' '}
          <strong>TeamIntent JSON</strong>, not natural language.
        </p>
        <p className="api-base">
          API: <code>{import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'}</code>
        </p>
        {metaErr && (
          <p className="meta-warn" role="alert">
            Could not load presets/archetypes: {metaErr}
          </p>
        )}
      </header>

      <nav className="tabs" aria-label="Tools">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="main">
        {tab === 'lookup' && (
          <section className="panel">
            <h2>Pokémon lookup</h2>
            <label className="field">
              Species name
              <input
                className="input"
                value={lookupName}
                onChange={(e) => setLookupName(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={lookupRefresh}
                onChange={(e) => setLookupRefresh(e.target.checked)}
              />
              Refresh caches
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitLookup()}
            >
              {loading ? 'Running…' : 'Run lookup'}
            </button>
          </section>
        )}

        {tab === 'team-build' && (
          <section className="panel">
            <h2>Archetype team build</h2>
            <label className="field">
              Archetype id
              <input
                className="input"
                list="arch-list"
                value={tbArchetype}
                onChange={(e) => setTbArchetype(e.target.value)}
              />
              <datalist id="arch-list">
                {archetypes.map((a) => (
                  <option key={a} value={a} />
                ))}
              </datalist>
            </label>
            <label className="field">
              Preset
              {presetSelect}
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={tbVerifyMoves}
                onChange={(e) => setTbVerifyMoves(e.target.checked)}
              />
              Verify moves
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={tbRefresh}
                onChange={(e) => setTbRefresh(e.target.checked)}
              />
              Refresh caches
            </label>
            <label className="field">
              Legendary policy
              <select
                className="select"
                value={tbLegendary}
                onChange={(e) => setTbLegendary(e.target.value)}
              >
                {LEGENDARY_POLICIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={tbMega}
                onChange={(e) => setTbMega(e.target.checked)}
              />
              Mechanics-only mega (validation)
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitTeamBuild()}
            >
              {loading ? 'Running…' : 'Build team'}
            </button>
          </section>
        )}

        {tab === 'coach' && (
          <section className="panel">
            <h2>Team coach (TeamIntent JSON)</h2>
            <div className="row-actions">
              <button
                type="button"
                className="btn secondary"
                onClick={() => void loadCoachSample()}
              >
                Load sample intent
              </button>
              <button
                type="button"
                className="btn secondary"
                onClick={() => void loadCoachPartialSample()}
              >
                Load sample partial team
              </button>
            </div>
            <label className="field">
              Intent JSON
              <textarea
                className="textarea"
                spellCheck={false}
                rows={14}
                value={coachIntentJson}
                onChange={(e) => setCoachIntentJson(e.target.value)}
              />
            </label>
            <label className="field">
              Partial team JSON (optional, 6 slots — overlays{' '}
              <code>must_include</code>)
              <textarea
                className="textarea"
                spellCheck={false}
                rows={8}
                placeholder="Paste full team JSON or leave empty"
                value={coachPartialJson}
                onChange={(e) => setCoachPartialJson(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={coachRefresh}
                onChange={(e) => setCoachRefresh(e.target.checked)}
              />
              Refresh caches
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitCoach()}
            >
              {loading ? 'Running…' : 'Run coach'}
            </button>
          </section>
        )}

        {tab === 'analyze' && (
          <section className="panel">
            <h2>Matchup analyze (damage matrix)</h2>
            <p className="hint">
              Requires Node.js and <code>npm install</code> in Project_PokeJarvis.
              Large requests may take a while.
            </p>
            <div className="row-actions">
              <button
                type="button"
                className="btn secondary"
                onClick={() => void loadTeamSampleAll()}
              >
                Load sample team into A &amp; B
              </button>
            </div>
            <label className="field">
              Team A JSON (6 slots)
              <textarea
                className="textarea"
                spellCheck={false}
                rows={10}
                value={teamAJson}
                onChange={(e) => setTeamAJson(e.target.value)}
              />
            </label>
            <label className="field">
              Team B JSON (6 slots)
              <textarea
                className="textarea"
                spellCheck={false}
                rows={10}
                value={teamBJson}
                onChange={(e) => setTeamBJson(e.target.value)}
              />
            </label>
            <div className="grid2">
              <label className="field">
                Preset
                <select
                  className="select"
                  value={anPreset}
                  onChange={(e) => setAnPreset(e.target.value)}
                >
                  {(presets.length ? presets : ['gen9']).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Calc gen override (optional)
                <input
                  className="input"
                  placeholder="e.g. 9"
                  value={anGen}
                  onChange={(e) => setAnGen(e.target.value)}
                />
              </label>
              <label className="field">
                Workers
                <input
                  type="number"
                  className="input"
                  min={1}
                  max={32}
                  value={anWorkers}
                  onChange={(e) => setAnWorkers(Number(e.target.value))}
                />
              </label>
              <label className="field">
                Move slot indices (comma)
                <input
                  className="input"
                  value={anMoveSlots}
                  onChange={(e) => setAnMoveSlots(e.target.value)}
                />
              </label>
            </div>
            <label className="field">
              Field JSON override (optional, merged over preset)
              <textarea
                className="textarea"
                spellCheck={false}
                rows={4}
                placeholder='{"weather":"Rain"}'
                value={anFieldJson}
                onChange={(e) => setAnFieldJson(e.target.value)}
              />
            </label>
            <label className="field">
              Legendary policy
              <select
                className="select"
                value={anLegendary}
                onChange={(e) => setAnLegendary(e.target.value)}
              >
                {LEGENDARY_POLICIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={anRefresh}
                onChange={(e) => setAnRefresh(e.target.checked)}
              />
              Refresh caches
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={anMega}
                onChange={(e) => setAnMega(e.target.checked)}
              />
              Mechanics-only mega (validation)
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitAnalyze()}
            >
              {loading ? 'Running damage matrix…' : 'Run analyze'}
            </button>
          </section>
        )}

        {tab === 'synergy' && (
          <section className="panel">
            <h2>Synergy</h2>
            <div className="row-actions">
              <button
                type="button"
                className="btn secondary"
                onClick={() => void loadTeamSampleAll()}
              >
                Load sample team
              </button>
            </div>
            <label className="field">
              Team JSON
              <textarea
                className="textarea"
                spellCheck={false}
                rows={12}
                value={synTeamJson}
                onChange={(e) => setSynTeamJson(e.target.value)}
              />
            </label>
            <label className="field">
              Opponent team JSON (optional)
              <textarea
                className="textarea"
                spellCheck={false}
                rows={8}
                value={synOppJson}
                onChange={(e) => setSynOppJson(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitSynergy()}
            >
              {loading ? 'Running…' : 'Run synergy'}
            </button>
          </section>
        )}

        {tab === 'weakness' && (
          <section className="panel">
            <h2>Type-chart weakness profile</h2>
            <label className="field">
              Species
              <input
                className="input"
                value={wkSpecies}
                onChange={(e) => setWkSpecies(e.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={wkRefresh}
                onChange={(e) => setWkRefresh(e.target.checked)}
              />
              Refresh caches
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={loading}
              onClick={() => void submitWeakness()}
            >
              {loading ? 'Running…' : 'Run weakness'}
            </button>
          </section>
        )}

        {err && (
          <div className="error-banner" role="alert">
            {err}
          </div>
        )}

        {result !== null &&
        tab === 'analyze' &&
        analyzeMode &&
        typeof result === 'object' &&
        result !== null ? (
          <ResultPanel
            title="Result"
            data={result}
            filename="pokejarvis-analyze.json"
            hideRaw
            extra={
              <AnalyzeSections result={result as Record<string, unknown>} />
            }
          />
        ) : result !== null ? (
          <ResultPanel
            title="Result"
            data={result}
            filename="pokejarvis-result.json"
            extra={
              tab === 'coach' &&
              typeof result === 'object' &&
              result !== null ? (
                <CoachWarnings report={result as Record<string, unknown>} />
              ) : undefined
            }
          />
        ) : null}
      </main>
    </div>
  )
}
