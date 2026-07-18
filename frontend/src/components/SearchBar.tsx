import React, { useState } from 'react'
import { Search, Link, X, Loader2, Globe, Layers } from 'lucide-react'

export type SearchMode = 'multi' | 'wallhaven' | 'bing' | 'ddg' | 'url'

interface ModeOption {
  key:   SearchMode
  label: string
  icon:  React.ReactNode
  title: string
  color: string
}

const MODES: ModeOption[] = [
  {
    key:   'multi',
    label: 'Multi',
    icon:  <Layers size={10} />,
    title: 'Todas as fontes: Wallhaven + Bing + Reddit + DDG (melhor para temas específicos)',
    color: 'bg-emerald-600 text-white',
  },
  {
    key:   'wallhaven',
    label: 'Wallhaven',
    icon:  <Globe size={10} />,
    title: 'Wallhaven — banco de wallpapers de alta qualidade',
    color: 'bg-purple-600 text-white',
  },
  {
    key:   'bing',
    label: 'Bing',
    icon:  <Search size={10} />,
    title: 'Bing Images — maior cobertura geral',
    color: 'bg-sky-600 text-white',
  },
  {
    key:   'ddg',
    label: 'DDG',
    icon:  <Search size={10} />,
    title: 'DuckDuckGo Images',
    color: 'bg-accent text-white',
  },
  {
    key:   'url',
    label: 'URL',
    icon:  <Link size={10} />,
    title: 'gallery-dl — colar URL de galeria (Wallhaven, Pinterest, DeviantArt…)',
    color: 'bg-accent text-white',
  },
]

const ACTIVE_COLORS: Record<SearchMode, string> = {
  multi:     'bg-emerald-600 text-white',
  wallhaven: 'bg-purple-600 text-white',
  bing:      'bg-sky-600 text-white',
  ddg:       'bg-accent text-white',
  url:       'bg-accent text-white',
}

interface Props {
  onSearch:  (value: string, mode: SearchMode, limit: number) => void
  searching: boolean
}

export default function SearchBar({ onSearch, searching }: Props) {
  const [mode,  setMode]  = useState<SearchMode>('multi')
  const [value, setValue] = useState('')
  const [limit, setLimit] = useState(150)

  const canSearch = value.trim().length > 0 && !searching
  const isUrlMode = mode === 'url'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (canSearch) onSearch(value.trim(), mode, limit)
  }

  const activeCls = ACTIVE_COLORS[mode]

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
            className={`flex items-center gap-1 px-2 py-1.5 text-[11px] font-medium transition-colors
              ${mode === m.key
                ? ACTIVE_COLORS[m.key]
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
            isUrlMode
              ? 'Colar URL (Wallhaven, Pinterest, DeviantArt…)'
              : mode === 'multi'
                ? 'Buscar em todas as fontes (ex: lord of the mysteries, cyberpunk 4k…)'
                : mode === 'wallhaven'
                  ? 'Buscar no Wallhaven (ex: anime landscape, dark fantasy…)'
                  : mode === 'bing'
                    ? 'Buscar no Bing Images (ex: makoto shinkai wallpaper 4k…)'
                    : 'Buscar no DuckDuckGo…'
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

      {/* Limit selector (só modos de keyword) */}
      {!isUrlMode && (
        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          disabled={searching}
          className="bg-card border border-border rounded-lg px-2 py-2 text-xs
                     text-text-dim focus:outline-none focus:border-accent/60
                     disabled:opacity-50 transition-colors flex-shrink-0"
        >
          <option value={24}>24</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
          <option value={150}>150</option>
          <option value={300}>300</option>
        </select>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSearch}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold
                    flex-shrink-0 transition-all
                    ${canSearch
                      ? `${activeCls} shadow-lg`
                      : 'bg-card border border-border text-muted cursor-not-allowed'}`}
      >
        {searching
          ? <><Loader2 size={14} className="animate-spin" /> Buscando…</>
          : <><Search size={14} /> Buscar</>}
      </button>
    </form>
  )
}
