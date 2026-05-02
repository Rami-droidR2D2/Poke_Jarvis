export function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
}

export async function apiFetch<T extends Record<string, unknown>>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (init?.body !== undefined && headers['Content-Type'] === undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${apiBase()}${path}`, { ...init, headers })
  let data: Record<string, unknown>
  try {
    data = (await res.json()) as Record<string, unknown>
  } catch {
    throw new Error(`HTTP ${res.status}: response was not JSON`)
  }

  if (!res.ok || data.ok === false) {
    const msg = String(data.error ?? `HTTP ${res.status}`)
    const detail = data.detail
    if (detail !== undefined && typeof detail === 'string') {
      throw new Error(`${msg}: ${detail}`)
    }
    throw new Error(msg)
  }

  return data as T
}
