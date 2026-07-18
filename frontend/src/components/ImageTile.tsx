import React, { useState } from 'react'
import { Check, ZoomIn } from 'lucide-react'
import type { ImageInfo } from '../types'
import { api } from '../api'

interface Props {
  image:       ImageInfo
  selected:    boolean
  onToggle:    (id: string) => void
  onPreview:   (image: ImageInfo) => void
  onHover:     (image: ImageInfo | null) => void
}

export default function ImageTile({ image, selected, onToggle, onPreview, onHover }: Props) {
  const [loaded, setLoaded] = useState(false)

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    onToggle(image.id)
  }

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    onPreview(image)
  }

  return (
    <div
      className={`tile ${selected ? 'selected' : ''}`}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => onHover(image)}
      onMouseLeave={() => onHover(null)}
      title={`${image.filename}\n${image.resolution}\nDuplo-clique: preview`}
    >
      {/* Thumbnail */}
      <div className="relative overflow-hidden bg-card" style={{ aspectRatio: '16/9' }}>
        {/* Skeleton */}
        {!loaded && (
          <div className="absolute inset-0 bg-gradient-to-br from-card to-surface
                          animate-pulse" />
        )}
        <img
          src={api.thumbUrl(image.id)}
          alt={image.filename}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          className={`w-full h-full object-cover transition-opacity duration-300
                      ${loaded ? 'opacity-100' : 'opacity-0'}`}
        />

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 hover:bg-black/20 transition-colors" />

        {/* Zoom icon on hover */}
        <div className="absolute bottom-2 left-2 opacity-0 group-hover:opacity-100
                        transition-opacity bg-black/60 rounded-md px-1.5 py-0.5
                        flex items-center gap-1 pointer-events-none">
          <ZoomIn size={11} className="text-white/80" />
          <span className="text-white/80 text-[10px]">preview</span>
        </div>

        {/* Check indicator */}
        <div className="tile-check">
          {selected && <Check size={12} className="text-white" strokeWidth={3} />}
        </div>

        {/* Selected gradient overlay */}
        {selected && (
          <div className="absolute inset-0 bg-accent/8 pointer-events-none" />
        )}
      </div>

      {/* Footer */}
      <div className="tile-footer">
        <div className="tile-name">{image.filename}</div>
        <div className="tile-res">{image.resolution} · {image.megapixels} MP</div>
      </div>
    </div>
  )
}
