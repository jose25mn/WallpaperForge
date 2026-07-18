import React, { useState, useEffect, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight, Info, Monitor, Tv2, Zap, Download } from 'lucide-react'
import type { ImageInfo, Monitor as MonitorType } from '../types'
import { api } from '../api'

interface Props {
  image:           ImageInfo
  images:          ImageInfo[]
  monitors:        MonitorType[]
  applyingMonitor: string | null
  onClose:         () => void
  onApply:         (monitorName: string, imageId: string) => void
}

function monitorLabel(name: string) {
  return name.replace(/^[\\/.]+/, '') || name
}

function triggerDownload(url: string, filename: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

export default function PreviewModal({
  image, images, monitors, applyingMonitor, onClose, onApply,
}: Props) {
  const [current, setCurrent] = useState(() => images.findIndex(i => i.id === image.id))
  const [loaded,  setLoaded]  = useState(false)

  const img = images[current] ?? image

  const prev = useCallback(() => { setLoaded(false); setCurrent(c => (c - 1 + images.length) % images.length) }, [images.length])
  const next = useCallback(() => { setLoaded(false); setCurrent(c => (c + 1) % images.length) }, [images.length])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [prev, next, onClose])

  const handleDownload = (mon: MonitorType) => {
    const url      = `/api/download/${img.id}?width=${mon.width}&height=${mon.height}`
    const filename = `${img.filename.replace(/\.[^.]+$/, '')}_${mon.width}x${mon.height}.jpg`
    triggerDownload(url, filename)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="relative flex flex-col max-w-[92vw] max-h-[92vh]
                   bg-surface border border-border rounded-2xl overflow-hidden
                   shadow-2xl animate-scale-in"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border
                        bg-surface/90 flex-shrink-0">
          <div className="flex items-center gap-3">
            <Info size={14} className="text-muted" />
            <div>
              <p className="text-sm font-medium text-text leading-none">{img.filename}</p>
              <p className="text-xs text-muted mt-0.5">
                {img.resolution} · {img.megapixels} MP
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">{current + 1} / {images.length}</span>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg flex items-center justify-center
                         text-muted hover:text-text hover:bg-card transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Image ── */}
        <div className="relative flex-1 flex items-center justify-center
                        bg-bg overflow-hidden min-h-[340px]">
          {!loaded && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-10 h-10 border-2 border-border border-t-accent
                              rounded-full animate-spin" />
            </div>
          )}
          <img
            key={img.id}
            src={api.fullUrl(img.id)}
            alt={img.filename}
            onLoad={() => setLoaded(true)}
            className={`max-w-full max-h-[60vh] object-contain transition-opacity duration-200
                        ${loaded ? 'opacity-100' : 'opacity-0'}`}
          />

          {images.length > 1 && (
            <>
              <button
                onClick={prev}
                className="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full
                           bg-black/60 border border-border/50 flex items-center justify-center
                           text-text-dim hover:bg-black/80 hover:text-text transition-all backdrop-blur-sm"
              >
                <ChevronLeft size={20} />
              </button>
              <button
                onClick={next}
                className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full
                           bg-black/60 border border-border/50 flex items-center justify-center
                           text-text-dim hover:bg-black/80 hover:text-text transition-all backdrop-blur-sm"
              >
                <ChevronRight size={20} />
              </button>
            </>
          )}
        </div>

        {/* ── Monitor actions ── */}
        {monitors.length > 0 && (
          <div className="px-4 py-3 border-t border-border bg-card/50 flex-shrink-0">
            <p className="text-[10px] text-muted uppercase tracking-widest font-semibold mb-2">
              Aplicar / Baixar por monitor
            </p>
            <div className="flex flex-col gap-1.5">
              {monitors.map(mon => (
                <div
                  key={mon.name}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg
                             bg-surface border border-border/60 hover:border-border
                             transition-colors"
                >
                  {/* orientation icon */}
                  {mon.is_portrait ? (
                    <Tv2 size={15} className="text-purple-400 flex-shrink-0" />
                  ) : (
                    <Monitor size={15} className="text-sky-400 flex-shrink-0" />
                  )}

                  {/* name + resolution */}
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium text-text">
                      {monitorLabel(mon.name)}
                    </span>
                    <span className="text-xs text-muted ml-2">
                      {mon.width}×{mon.height}
                    </span>
                    <span className={`text-[10px] ml-2 px-1.5 py-0.5 rounded font-medium
                      ${mon.is_portrait
                        ? 'bg-purple-500/15 text-purple-400'
                        : 'bg-sky-500/15 text-sky-400'}`}>
                      {mon.is_portrait ? 'Retrato' : 'Paisagem'}
                    </span>
                  </div>

                  {/* Apply button */}
                  <button
                    onClick={() => onApply(mon.name, img.id)}
                    disabled={applyingMonitor === mon.name}
                    title={`Aplicar wallpaper em ${monitorLabel(mon.name)}`}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs
                               font-medium bg-accent/20 text-accent-bright border border-accent/30
                               hover:bg-accent/30 disabled:opacity-40 transition-colors flex-shrink-0"
                  >
                    {applyingMonitor === mon.name ? (
                      <div className="w-3 h-3 border border-accent-bright/40 border-t-accent-bright
                                      rounded-full animate-spin" />
                    ) : (
                      <Zap size={11} />
                    )}
                    Aplicar
                  </button>

                  {/* Download 4K button */}
                  <button
                    onClick={() => handleDownload(mon)}
                    title={`Baixar convertido para ${mon.width}×${mon.height}`}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs
                               font-medium bg-green-500/10 text-green-400 border border-green-500/25
                               hover:bg-green-500/20 transition-colors flex-shrink-0"
                  >
                    <Download size={11} />
                    {mon.width}×{mon.height}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Filmstrip ── */}
        {images.length > 1 && (
          <div className="flex gap-1.5 px-3 py-2 border-t border-border
                          bg-surface/90 overflow-x-auto flex-shrink-0">
            {images.map((img2, i) => (
              <button
                key={img2.id}
                onClick={() => { setLoaded(false); setCurrent(i) }}
                className={`flex-shrink-0 w-14 h-10 rounded overflow-hidden border-2
                            transition-all ${i === current
                              ? 'border-accent shadow-glow-sm'
                              : 'border-transparent opacity-50 hover:opacity-80'}`}
              >
                <img
                  src={api.thumbUrl(img2.id)}
                  alt=""
                  className="w-full h-full object-cover"
                />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
