import React from 'react'
import { CheckCircle, AlertCircle, Download } from 'lucide-react'

export interface ScrapeState {
  step:    string
  message: string
  done:    number
  total:   number
  success?: number
  finished?: boolean
  error?:    boolean
}

interface Props {
  state: ScrapeState
}

export default function ScrapeProgress({ state }: Props) {
  const pct = state.total > 0 ? Math.min((state.done / state.total) * 100, 100) : 0
  const isDownloading = state.step === 'downloading'
  const isDone        = state.finished || state.step === 'done'
  const isError       = state.error    || state.step === 'error'

  return (
    <div className={`flex items-center gap-3 px-5 py-2.5 border-b text-xs
                     transition-colors flex-shrink-0
                     ${isError  ? 'border-red-900/50 bg-red-950/30' :
                       isDone   ? 'border-green-900/50 bg-green-950/20' :
                                  'border-border bg-surface/60'}`}>

      {/* Ícone de estado */}
      <div className="flex-shrink-0">
        {isError ? (
          <AlertCircle size={15} className="text-red-400" />
        ) : isDone ? (
          <CheckCircle size={15} className="text-green-400" />
        ) : (
          <Download size={15} className="text-accent-bright animate-bounce" />
        )}
      </div>

      {/* Barra de progresso (só aparece durante download) */}
      {isDownloading && state.total > 0 && (
        <div className="w-36 h-1.5 bg-card rounded-full overflow-hidden flex-shrink-0">
          <div
            className="h-full bg-gradient-to-r from-accent to-purple-500
                       rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {/* Mensagem */}
      <span className={`flex-1 truncate
                        ${isError ? 'text-red-300' :
                          isDone  ? 'text-green-300' :
                                    'text-text-dim'}`}>
        {state.message}
      </span>

      {/* Contador */}
      {isDownloading && state.total > 0 && (
        <span className="text-muted flex-shrink-0 tabular-nums">
          {state.done}/{state.total}
        </span>
      )}
    </div>
  )
}
