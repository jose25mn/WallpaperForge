import React from 'react'
import {
  Monitor, Layers, Image, Info, Play, Save,
  ChevronRight, Star,
} from 'lucide-react'
import type { ImageInfo, Monitor as MonitorType } from '../types'

interface Props {
  total:            number
  selectedCount:    number
  hovered:          ImageInfo | null
  monitors:         MonitorType[]
  selectedMonitors: Set<string>
  processing:       boolean
  onMonitorToggle:  (name: string) => void
  onSelectAll:      () => void
  onSelectNone:     () => void
  onProcess:        () => void
  onSaveExit:       () => void
}

function StatBox({ label, value, accent = false }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="flex-1 bg-card rounded-xl p-3 border border-border/50">
      <div className="text-xs text-muted font-medium uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold leading-none ${accent ? 'text-accent-bright' : 'text-text'}`}>
        {value}
      </div>
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-muted">{icon}</span>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</span>
      </div>
      {children}
    </div>
  )
}

export default function Sidebar({
  total, selectedCount, hovered, monitors, selectedMonitors,
  processing, onMonitorToggle, onSelectAll, onSelectNone, onProcess, onSaveExit,
}: Props) {
  return (
    <aside className="w-64 flex-shrink-0 flex flex-col border-l border-border
                      bg-surface overflow-y-auto">
      <div className="flex-1 p-4 space-y-5">

        {/* Stats */}
        <Section icon={<Layers size={13} />} title="Estatísticas">
          <div className="flex gap-2">
            <StatBox label="Total"        value={total} />
            <StatBox label="Selecionadas" value={selectedCount} accent />
          </div>
        </Section>

        <div className="sep" />

        {/* Hover info */}
        <Section icon={<Info size={13} />} title="Sob o cursor">
          {hovered ? (
            <div className="bg-card rounded-lg p-2.5 border border-border/50 space-y-1 animate-fade-in">
              <p className="text-xs text-text font-medium truncate" title={hovered.filename}>
                {hovered.filename}
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] text-accent-bright font-semibold">
                  {hovered.resolution}
                </span>
                <span className="text-[11px] text-muted">·</span>
                <span className="text-[11px] text-muted">{hovered.megapixels} MP</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted italic">Passe o mouse sobre uma imagem</p>
          )}
        </Section>

        <div className="sep" />

        {/* Monitors */}
        <Section icon={<Monitor size={13} />} title="Exportar para">
          <div className="space-y-1.5">
            {monitors.length === 0 ? (
              <p className="text-xs text-muted">Nenhum monitor detectado</p>
            ) : (
              monitors.map(m => (
                <label
                  key={m.name}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg
                             bg-card/50 border border-border/30 cursor-pointer
                             hover:border-border transition-colors group"
                >
                  <input
                    type="checkbox"
                    checked={selectedMonitors.has(m.name)}
                    onChange={() => onMonitorToggle(m.name)}
                    className="accent-indigo-500 w-3.5 h-3.5 flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-text-dim truncate font-medium">
                        {m.name.replace(/\\\\.\\/, '')}
                      </span>
                      {m.is_primary && (
                        <Star size={9} className="text-yellow-500 fill-yellow-500 flex-shrink-0" />
                      )}
                    </div>
                    <span className="text-[10px] text-muted">{m.width}×{m.height}</span>
                  </div>
                </label>
              ))
            )}
          </div>
        </Section>

        <div className="sep" />

        {/* Quick selection */}
        <Section icon={<Image size={13} />} title="Seleção rápida">
          <div className="flex gap-2">
            <button
              onClick={onSelectAll}
              className="flex-1 py-1.5 rounded-lg text-xs font-medium text-text-dim
                         border border-border hover:border-accent/40 hover:text-text
                         hover:bg-card transition-all"
            >
              Todas
            </button>
            <button
              onClick={onSelectNone}
              className="flex-1 py-1.5 rounded-lg text-xs font-medium text-text-dim
                         border border-border hover:border-border hover:text-text
                         hover:bg-card transition-all"
            >
              Nenhuma
            </button>
          </div>
          <p className="text-[10px] text-muted/70 text-center">
            Shift+clique · Ctrl+A
          </p>
        </Section>
      </div>

      {/* Action buttons */}
      <div className="p-4 space-y-2.5 border-t border-border flex-shrink-0">
        <button
          onClick={onProcess}
          disabled={selectedCount === 0 || processing}
          className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl
                      text-sm font-bold text-white transition-all
                      disabled:opacity-40 disabled:cursor-not-allowed
                      ${selectedCount > 0 && !processing ? 'btn-glow' : 'bg-card border border-border'}`}
        >
          {processing ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white
                              rounded-full animate-spin" />
              Processando…
            </>
          ) : (
            <>
              <Play size={14} fill="white" />
              Processar {selectedCount > 0 ? `(${selectedCount})` : ''}
            </>
          )}
        </button>

        <button
          onClick={onSaveExit}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                     text-xs font-medium text-text-dim border border-border
                     hover:text-text hover:border-border hover:bg-card
                     transition-all"
        >
          <Save size={13} />
          Salvar seleção e sair
        </button>
      </div>
    </aside>
  )
}
