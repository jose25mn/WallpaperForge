import React, { useState, useEffect, useCallback, useMemo } from 'react'
import Toolbar     from './components/Toolbar'
import ImageGrid   from './components/ImageGrid'
import Sidebar     from './components/Sidebar'
import PreviewModal from './components/PreviewModal'
import { api }     from './api'
import type { ImageInfo, Monitor, SortKey } from './types'

export default function App() {
  const [images,     setImages]     = useState<ImageInfo[]>([])
  const [monitors,   setMonitors]   = useState<Monitor[]>([])
  const [selected,   setSelected]   = useState<Set<string>>(new Set())
  const [selMonitors, setSelMonitors] = useState<Set<string>>(new Set())
  const [preview,    setPreview]    = useState<ImageInfo | null>(null)
  const [hovered,    setHovered]    = useState<ImageInfo | null>(null)
  const [sortKey,    setSortKey]    = useState<SortKey>('name')
  const [loading,    setLoading]    = useState(true)
  const [processing, setProcessing] = useState(false)
  const [toast,      setToast]      = useState<string | null>(null)

  // ── Load data ─────────────────────────────────────────────────────────────

  useEffect(() => {
    Promise.all([api.getImages(), api.getMonitors()])
      .then(([imgs, mons]) => {
        setImages(imgs)
        setMonitors(mons)
        setSelMonitors(new Set(mons.map(m => m.name)))
      })
      .catch(err => console.error('Erro ao carregar dados:', err))
      .finally(() => setLoading(false))
  }, [])

  // ── Sorted images ─────────────────────────────────────────────────────────

  const sorted = useMemo(() => {
    const arr = [...images]
    if (sortKey === 'resolution') arr.sort((a, b) => (b.width * b.height) - (a.width * a.height))
    else if (sortKey === 'aspect') arr.sort((a, b) => (b.width / (b.height || 1)) - (a.width / (a.height || 1)))
    else if (sortKey === 'source') arr.sort((a, b) => a.source.localeCompare(b.source))
    else arr.sort((a, b) => a.filename.localeCompare(b.filename))
    return arr
  }, [images, sortKey])

  // ── Selection ─────────────────────────────────────────────────────────────

  const toggle = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const selectAll  = useCallback(() => setSelected(new Set(images.map(i => i.id))), [images])
  const selectNone = useCallback(() => setSelected(new Set()), [])

  // Ctrl+A
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'a' && !preview) {
        e.preventDefault()
        selectAll()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectAll, preview])

  // ── Monitor toggle ────────────────────────────────────────────────────────

  const toggleMonitor = useCallback((name: string) => {
    setSelMonitors(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }, [])

  // ── Process ───────────────────────────────────────────────────────────────

  const handleProcess = async () => {
    if (selected.size === 0) return
    setProcessing(true)
    try {
      const selImages   = images.filter(i => selected.has(i.id)).map(i => i.path)
      const selMonNames = monitors.filter(m => selMonitors.has(m.name)).map(m => m.name)
      await api.saveSelection({ images: selImages, monitors: selMonNames })
      await api.process()
      showToast(`✓ ${selImages.length} imagem(ns) enfileiradas para processamento!`)
    } catch (err) {
      showToast('Erro ao processar. Verifique o servidor.')
    } finally {
      setProcessing(false)
    }
  }

  const handleSaveExit = async () => {
    const selImages   = images.filter(i => selected.has(i.id)).map(i => i.path)
    const selMonNames = monitors.filter(m => selMonitors.has(m.name)).map(m => m.name)
    await api.saveSelection({ images: selImages, monitors: selMonNames })
    showToast(`💾 Seleção salva: ${selImages.length} imagem(ns)`)
  }

  // ── Toast ─────────────────────────────────────────────────────────────────

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Toolbar
        total={images.length}
        selectedCount={selected.size}
        sortKey={sortKey}
        onSortChange={setSortKey}
        onSelectAll={selectAll}
        onSelectNone={selectNone}
      />

      <div className="flex flex-1 overflow-hidden">
        <ImageGrid
          images={sorted}
          selected={selected}
          loading={loading}
          onToggle={toggle}
          onPreview={setPreview}
          onHover={setHovered}
        />

        <Sidebar
          total={images.length}
          selectedCount={selected.size}
          hovered={hovered}
          monitors={monitors}
          selectedMonitors={selMonitors}
          processing={processing}
          onMonitorToggle={toggleMonitor}
          onSelectAll={selectAll}
          onSelectNone={selectNone}
          onProcess={handleProcess}
          onSaveExit={handleSaveExit}
        />
      </div>

      {preview && (
        <PreviewModal
          image={preview}
          images={sorted}
          onClose={() => setPreview(null)}
        />
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
