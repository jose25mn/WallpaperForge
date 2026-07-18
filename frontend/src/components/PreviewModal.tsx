import React, { useState, useEffect, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight, Info } from 'lucide-react'
import type { ImageInfo } from '../types'
import { api } from '../api'

interface Props {
  image:   ImageInfo
  images:  ImageInfo[]
  onClose: () => void
}

export default function PreviewModal({ image, images, onClose }: Props) {
  const [current, setCurrent] = useState(() => images.findIndex(i => i.id === image.id))
  const [loaded,  setLoaded]  = useState(false)

  const img = images[current] ?? image

  const prev = useCallback(() => {
    setLoaded(false)
    setCurrent(c => (c - 1 + images.length) % images.length)
  }, [images.length])

  const next = useCallback(() => {
    setLoaded(false)
    setCurrent(c => (c + 1) % images.length)
  }, [images.length])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="relative flex flex-col max-w-[92vw] max-h-[92vh]
                   bg-surface border border-border rounded-2xl overflow-hidden
                   shadow-2xl animate-scale-in"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
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
            <span className="text-xs text-muted">
              {current + 1} / {images.length}
            </span>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg flex items-center justify-center
                         text-muted hover:text-text hover:bg-card transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Image */}
        <div className="relative flex-1 flex items-center justify-center
                        bg-bg overflow-hidden min-h-[400px]">
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
            className={`max-w-full max-h-[75vh] object-contain transition-opacity duration-200
                        ${loaded ? 'opacity-100' : 'opacity-0'}`}
          />

          {/* Nav arrows */}
          {images.length > 1 && (
            <>
              <button
                onClick={prev}
                className="absolute left-3 top-1/2 -translate-y-1/2
                           w-10 h-10 rounded-full bg-black/60 border border-border/50
                           flex items-center justify-center text-text-dim
                           hover:bg-black/80 hover:text-text transition-all
                           backdrop-blur-sm"
              >
                <ChevronLeft size={20} />
              </button>
              <button
                onClick={next}
                className="absolute right-3 top-1/2 -translate-y-1/2
                           w-10 h-10 rounded-full bg-black/60 border border-border/50
                           flex items-center justify-center text-text-dim
                           hover:bg-black/80 hover:text-text transition-all
                           backdrop-blur-sm"
              >
                <ChevronRight size={20} />
              </button>
            </>
          )}
        </div>

        {/* Filmstrip (thumbnail strip) */}
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
