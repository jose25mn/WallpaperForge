import React from 'react'
import { ImageOff } from 'lucide-react'
import ImageTile from './ImageTile'
import type { ImageInfo } from '../types'

interface Props {
  images:    ImageInfo[]
  selected:  Set<string>
  loading:   boolean
  onToggle:  (id: string) => void
  onPreview: (image: ImageInfo) => void
  onHover:   (image: ImageInfo | null) => void
}

function Skeleton() {
  return (
    <div className="rounded-[10px] overflow-hidden bg-card border-2 border-transparent animate-pulse">
      <div className="bg-gradient-to-br from-card to-surface" style={{ aspectRatio: '16/9' }} />
      <div className="p-2.5 space-y-1.5">
        <div className="h-2.5 bg-border rounded w-3/4" />
        <div className="h-2 bg-border/60 rounded w-1/2" />
      </div>
    </div>
  )
}

export default function ImageGrid({
  images, selected, loading, onToggle, onPreview, onHover,
}: Props) {
  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-4">
        <div
          className="grid gap-3"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}
        >
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} />)}
        </div>
      </div>
    )
  }

  if (images.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-text-dim">
        <div className="w-20 h-20 rounded-2xl bg-card border border-border
                        flex items-center justify-center">
          <ImageOff size={36} className="text-muted" />
        </div>
        <div className="text-center">
          <p className="text-base font-medium text-text-dim">Nenhuma imagem encontrada</p>
          <p className="text-sm text-muted mt-1">
            Execute primeiro:
          </p>
          <code className="text-xs text-accent-bright bg-card border border-border
                           px-3 py-1.5 rounded-lg block mt-2 font-mono">
            python -m wallpaperforge scrape --query "nome da obra"
          </code>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 animate-fade-in">
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}
      >
        {images.map(img => (
          <ImageTile
            key={img.id}
            image={img}
            selected={selected.has(img.id)}
            onToggle={onToggle}
            onPreview={onPreview}
            onHover={onHover}
          />
        ))}
      </div>
    </div>
  )
}
