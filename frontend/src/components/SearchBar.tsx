import React, { useState } from 'react'
import { Search, Link, X, Loader2, Globe } from 'lucide-react'

export type SearchMode = 'ddg' | 'wallhaven' | 'url'

interface Props {
  onSearch:  (value: string, mode: SearchMode, limit: number) => void
  searching: boolean
}

const MODES: { key: SearchMode; label: string; icon: React.ReactNode; title: string }[] = [
  { key: 'ddg',       label: 'DDG',       icon: <Search size={10} />, title: 'DuckDuckGo Images' },
  { key: 'wallhaven', label: 'Wallhaven', icon: <Globe  size={10} />, title: 'Wallhaven (recomendado para wallpapers)' },
  { key: 'url',       label: 'URL',       icon: <Link   size={10} />, title: 'gallery-dl — colar URL de galeria' },
]

export default function SearchBar({ onSearch, searching }: Props) {
  const [mode,  setMode]  = useState<SearchMode>('wallhaven')
  const [value, setValue] = useState('')
  const [limit, setLimit] = useState(150)

  const canSearch = value.trim().length > 0 && !searching

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (canSearch) onSearch(value.trim(), mode, limit)
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 flex-1 max-w-2xl">

      {/* Mode toggle */}
      <div className="flex rounded-lg overflow-hidden border border-border flex-shrink-0">
        {MODES.map(m => (
          <button
            key={m.key}
            type="button"
            onClick={() => setMode(m.key)}
            title={m.title}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium transition-colors
              ${mode === m.key
                ? m.key === 'wallhaven'
                  ? 'bg-purple-600 text-white'
                  : 'bg-accent text-white'
                : 'bg-card text-muted hover:text-text'}`}
          >
            {m.icon}
            {m.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex-1 relative">
        <input
          type="text"
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder={
            mode === 'url'
              ? 'Colar URL (Wallhaven, DeviantArt, Pinterest…)'
              : mode === 'wallhaven'
                ? 'Buscar wallpapers (ex: cyberpunk city, anime landscape…)'
                : 'Buscar no DuckDuckGo (ex: Makoto Shinkai 4K…)'
          }
          disabled={searching}
          className="w-full bg-card border border-border rounded-lg pl-4 pr-8 py-2
                     text-sm text-text placeholder-muted
                     focus:outline-none focus:border-accent/60
                     disabled:opacity-50 transition-colors"
        />
        {value && !searching && (
          <button
            type="button"
            onClick={() => setValue('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2
                       text-muted hover:text-text transition-colors"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Limit selector (só para modos de busca por palavra-chave) */}
      {mode !== 'url' && (
        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          disabled={searching}
          className="bg-card border border-border rounded-lg px-2 py-2 text-xs
                     text-text-dim focus:outline-none focus:border-accent/60
                     disabled:opacity-50 transition-colors flex-shrink-0"
        >
          <option value={24}>24 imgs</option>
          <option value={50}>50 imgs</option>
          <option value={100}>100 imgs</option>
          <option value={150}>150 imgs</option>
          <option value={300}>300 imgs</option>
        </select>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSearch}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold
                    flex-shrink-0 transition-all
                    ${canSearch
                      ? mode === 'wallhaven'
                        ? 'bg-purple-600 hover:bg-purple-500 shadow-lg shadow-purple-900/30 text-white'
                        : 'btn-glow text-white'
                      : 'bg-card border border-border text-muted cursor-not-allowed'}`}
      >
        {searching
          ? <><Loader2 size={14} className="animate-spin" /> Buscando…</>
          : <><Search size={14} /> Buscar</>
        }
      </button>
    </form>
  )
}
