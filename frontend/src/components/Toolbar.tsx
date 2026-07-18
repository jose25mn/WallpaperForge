import React from 'react'
import { LayoutGrid, SortAsc, CheckSquare, Square, Zap } from 'lucide-react'
import type { SortKey } from '../types'

interface Props {
  total:          number
  selectedCount:  number
  sortKey:        SortKey
  onSortChange:   (k: SortKey) => void
  onSelectAll:    () => void
  onSelectNone:   () => void
}

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'name',       label: 'Nome' },
  { value: 'resolution', label: 'Resolução' },
  { value: 'aspect',     label: 'Aspect ratio' },
  { value: 'source',     label: 'Fonte' },
]

export default function Toolbar({
  total, selectedCount, sortKey, onSortChange, onSelectAll, onSelectNone,
}: Props) {
  return (
    <header className="flex items-center gap-4 px-5 py-3 border-b border-border
                        bg-surface/80 backdrop-blur-sm flex-shrink-0 z-10">

      {/* Logo */}
      <div className="flex items-center gap-2 mr-2">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-purple-600
                        flex items-center justify-center shadow-glow-sm">
          <Zap size={14} className="text-white" />
        </div>
        <span className="font-bold text-text text-sm tracking-wide">WallpaperForge</span>
      </div>

      <div className="w-px h-5 bg-border" />

      {/* Gallery count */}
      <div className="flex items-center gap-1.5">
        <LayoutGrid size={14} className="text-muted" />
        <span className="text-text-dim text-xs">
          <span className="text-accent-bright font-semibold">{total}</span> imagens
        </span>
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2 ml-4">
        <SortAsc size={14} className="text-muted" />
        <span className="text-text-dim text-xs">Ordenar:</span>
        <div className="flex gap-1">
          {SORT_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => onSortChange(opt.value)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
                ${sortKey === opt.value
                  ? 'bg-accent text-white shadow-glow-sm'
                  : 'text-text-dim hover:text-text hover:bg-card'
                }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1" />

      {/* Selection actions */}
      <div className="flex items-center gap-2">
        {selectedCount > 0 && (
          <span className="text-xs text-accent-bright font-semibold
                           bg-accent/10 border border-accent/30 px-2.5 py-1 rounded-full">
            {selectedCount} selecionada{selectedCount !== 1 ? 's' : ''}
          </span>
        )}
        <button
          onClick={onSelectAll}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs
                     text-text-dim hover:text-text hover:bg-card transition-colors"
        >
          <CheckSquare size={13} />
          Todas
        </button>
        <button
          onClick={onSelectNone}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs
                     text-text-dim hover:text-text hover:bg-card transition-colors"
        >
          <Square size={13} />
          Nenhuma
        </button>
      </div>
    </header>
  )
}
