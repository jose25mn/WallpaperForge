import React from 'react'
import { Zap, CheckCircle, AlertCircle } from 'lucide-react'
import type { ScrapeState } from './ScrapeProgress'

interface Props {
  state:     ScrapeState
  hasImages: boolean
}

export default function SearchOverlay({ state, hasImages }: Props) {
  const pct          = state.total > 0 ? Math.min((state.done / state.total) * 100, 100) : 0
  const isDownload   = state.step === 'downloading'
  const isDone       = state.finished || state.step === 'done'
  const isError      = state.error    || state.step === 'error'
  const isCollecting = !isDownload && !isDone && !isError

  const stepLabel = isError      ? 'Erro na busca'
                  : isDone       ? 'Concluído!'
                  : isDownload   ? 'Baixando imagens…'
                                 : 'Coletando imagens…'

  return (
    <div
      className={`absolute inset-0 z-20 flex flex-col items-center justify-center gap-6
                  transition-all duration-300
                  ${hasImages ? 'bg-bg/85 backdrop-blur-md' : 'bg-bg'}`}
    >
      {/* Icon */}
      {isError ? (
        <AlertCircle size={52} className="text-red-400" />
      ) : isDone ? (
        <CheckCircle size={52} className="text-green-400 animate-scale-in" />
      ) : (
        <div className="relative flex items-center justify-center w-24 h-24">
          {/* Outer ping rings */}
          <div className="absolute inset-0 rounded-2xl bg-accent/20 animate-ping"
               style={{ animationDuration: '1.6s' }} />
          <div className="absolute inset-2 rounded-2xl bg-purple-500/15 animate-ping"
               style={{ animationDuration: '1.6s', animationDelay: '0.3s' }} />
          {/* Icon box */}
          <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-accent to-purple-600
                          flex items-center justify-center shadow-glow-lg">
            <Zap size={40} className="text-white drop-shadow" />
          </div>
        </div>
      )}

      {/* Labels */}
      <div className="flex flex-col items-center gap-2 text-center px-6 max-w-sm">
        <span className={`text-sm font-semibold tracking-widest uppercase
          ${isError ? 'text-red-400' : isDone ? 'text-green-400' : 'text-accent-bright'}`}>
          {stepLabel}
        </span>
        <span className="text-xs text-text-dim leading-relaxed">
          {state.message}
        </span>
      </div>

      {/* Progress bar (only during download or done) */}
      {(isDownload || isDone) && state.total > 0 && (
        <div className="flex flex-col items-center gap-2.5">
          <div className="w-72 h-2 bg-card rounded-full overflow-hidden border border-border/60">
            <div
              className={`h-full rounded-full transition-all duration-500
                          ${isDone
                            ? 'bg-green-500'
                            : 'bg-gradient-to-r from-accent to-purple-500'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs text-muted tabular-nums">
            {state.success ?? state.done} / {state.total} imagens
          </span>
        </div>
      )}

      {/* Collecting bounce dots */}
      {isCollecting && (
        <div className="flex gap-2">
          {[0, 1, 2, 3].map(i => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-accent animate-bounce"
              style={{ animationDelay: `${i * 0.12}s` }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
