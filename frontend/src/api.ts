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
  startScrape:   (data: { query?: string; url?: string; limit: number }) =>
                   post<{ task_id: string }>('/api/scrape', data),
  setWallpaper:  (data: { image_id: string; monitor_name: string }) =>
                   post<{ ok: boolean; message: string }>('/api/set-wallpaper', data),

  thumbUrl: (id: string) => `/api/thumbs/${id}`,
  fullUrl:  (id: string) => `/api/full/${id}`,
}
