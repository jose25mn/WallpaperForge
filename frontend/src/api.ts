import type { ImageInfo, Monitor, Selection } from './types'

const BASE = ''   // same origin in production; proxied in dev

async function get<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url)
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${url} → ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  getImages:     () => get<ImageInfo[]>('/api/images'),
  getMonitors:   () => get<Monitor[]>('/api/monitors'),
  getSelection:  () => get<Selection>('/api/selection'),
  saveSelection: (data: Selection) => post<{ ok: boolean; count: number }>('/api/selection', data),
  process:       () => post<{ ok: boolean; message: string }>('/api/process', {}),

  thumbUrl: (id: string) => `/api/thumbs/${id}`,
  fullUrl:  (id: string) => `/api/full/${id}`,
}
