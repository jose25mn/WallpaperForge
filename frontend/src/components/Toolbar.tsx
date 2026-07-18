import React from 'react'
import { LayoutGrid, SortAsc, CheckSquare, Square, Zap } from 'lucide-react'
import SearchBar, { SearchMode } from './SearchBar'
import type { SortKey } from '../types'

interface Props {
  total:         number
  selectedCount: number
  sortKey:       SortKey
  searching:     boolean
  onSortChange:  (k: SortKey) => void
  onSelectAll:   () => void
  onSelectNone:  () => void
  onSearch:      (value: string, mode: SearchMode, limit: number) => void
}

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'name',       label: 'Nome' },
  { value: 'resolution', label: 'Resolução' },
  { value: 'aspect',     label: 'Aspect' },
  { value: 'source',     label: 'Fonte' },
]

export default function Toolbar({
  total, selectedCount, sortKey, searching,
  onSortChange, onSelectAll, onSelectNone, onSearch,
}: Props) {
  return (
    <header className="flex items-center gap-3 px-4 py-2.5 border-b border-border
                        bg-surface/80 backdrop-blur-sm flex-shrink-0 z-10">

      {/* Logo */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-purple-600
                        flex items-center justify-center shadow-glow-sm flex-shrink-0">
          <Zap size={14} className="text-white" />
        </div>
        <span className="font-bold text-text text-sm tracking-wide hidden lg:block">
          WallpaperForge
        </span>
      </div>

      <div className="w-px h-5 bg-border flex-shrink-0" />

      {/* Search bar — ocupa o espaço central */}
      <SearchBar onSearch={onSearch} searching={searching} />

      <div className="w-px h-5 bg-border flex-shrink-0" />

      {/* Sort chips */}
      <div className="hidden xl:flex items-center gap-1 flex-shrink-0">
        <SortAsc size={13} className="text-muted mr-1" />
        {SORT_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => onSortChange(opt.value)}
            className={`px-2 py-1 rounded-md text-xs font-medium transition-all duration-150
              ${sortKey === opt.value
                ? 'bg-accent text-white shadow-glow-sm'
                : 'text-muted hover:text-text hover:bg-card'}`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="hidden xl:block w-px h-5 bg-border flex-shrink-0" />

      {/* Gallery count + selection actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <LayoutGrid size={13} className="text-muted" />
          <span className="text-text-dim text-xs tabular-nums">
            <span className="text-accent-bright font-semibold">{total}</span>
          </span>
        </div>

        {selectedCount > 0 && (
          <span className="text-xs text-accent-bright font-semibold
                           bg-accent/10 border border-accent/30 px-2 py-0.5 rounded-full">
            {selectedCount} ✓
          </span>
        )}

        <button
          onClick={onSelectAll}
          className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs
                     text-muted hover:text-text hover:bg-card transition-colors"
          title="Selecionar todas (Ctrl+A)"
        >
          <CheckSquare size={12} />
        </button>
        <button
          onClick={onSelectNone}
          className="flex items-center gap-1 px-2 py-1.5 rounded-md text-xs
                     text-muted hover:text-text hover:bg-card transition-colors"
          title="Desmarcar todas"
        >
          <Square size={12} />
        </button>
      </div>
    </header>
  )
}
