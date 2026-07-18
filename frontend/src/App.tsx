import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import Toolbar      from './components/Toolbar'
import ImageGrid    from './components/ImageGrid'
import Sidebar      from './components/Sidebar'
import PreviewModal from './components/PreviewModal'
import { api }      from './api'
import type { ImageInfo, Monitor, SortKey } from './types'
import type { SearchMode } from './components/SearchBar'
import type { ScrapeState } from './components/ScrapeProgress'

export default function App() {
  const [images,      setImages]      = useState<ImageInfo[]>([])
  const [monitors,    setMonitors]    = useState<Monitor[]>([])
  const [selected,    setSelected]    = useState<Set<string>>(new Set())
  const [selMonitors, setSelMonitors] = useState<Set<string>>(new Set())
  const [preview,     setPreview]     = useState<ImageInfo | null>(null)
  const [hovered,     setHovered]     = useState<ImageInfo | null>(null)
  const [sortKey,     setSortKey]     = useState<SortKey>('name')
  const [loading,     setLoading]     = useState(true)
  const [searching,       setSearching]       = useState(false)
  const [processing,      setProcessing]      = useState(false)
  const [clearing,        setClearing]        = useState(false)
  const [applyingMonitor, setApplyingMonitor] = useState<string | null>(null)
  const [scrapeState,     setScrapeState]     = useState<ScrapeState | null>(null)
  const [toast,           setToast]           = useState<string | null>(null)
  const evtSourceRef = useRef<EventSource | null>(null)

  // ── Carregamento inicial ─────────────────────────────────────────────────

  useEffect(() => {
    Promise.all([api.getImages(), api.getMonitors()])
      .then(([imgs, mons]) => {
        setImages(imgs)
        setMonitors(mons)
        setSelMonitors(new Set(mons.map(m => m.name)))
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  const refreshImages = useCallback(() => {
    api.getImages().then(setImages).catch(console.error)
  }, [])

  // ── Ordenação ────────────────────────────────────────────────────────────

  const sorted = useMemo(() => {
    const arr = [...images]
    if (sortKey === 'resolution') arr.sort((a, b) => (b.width * b.height) - (a.width * a.height))
    else if (sortKey === 'aspect') arr.sort((a, b) => (b.width / (b.height || 1)) - (a.width / (a.height || 1)))
    else if (sortKey === 'source') arr.sort((a, b) => a.source.localeCompare(b.source))
    else arr.sort((a, b) => a.filename.localeCompare(b.filename))
    return arr
  }, [images, sortKey])

  // ── Seleção ──────────────────────────────────────────────────────────────

  const toggle     = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])
  const selectAll  = useCallback(() => setSelected(new Set(images.map(i => i.id))), [images])
  const selectNone = useCallback(() => setSelected(new Set()), [])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'a' && !preview) {
        e.preventDefault(); selectAll()
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [selectAll, preview])

  // ── Busca / Scrape ────────────────────────────────────────────────────────

  const handleSearch = useCallback(async (value: string, mode: SearchMode, limit: number) => {
    // Fechar SSE anterior se ainda aberta
    evtSourceRef.current?.close()

    setSearching(true)
    setScrapeState({ step: 'init', message: 'Iniciando busca…', done: 0, total: limit })

    try {
      const body = mode === 'url'
        ? { url: value,  limit }
        : { query: value, limit, source: mode }  // "ddg" | "wallhaven"

      const { task_id } = await api.startScrape(body)

      const sse = new EventSource(`/api/scrape/stream/${task_id}`)
      evtSourceRef.current = sse

      sse.onmessage = (evt) => {
        const data = JSON.parse(evt.data)

        if (data.heartbeat) return

        if (data.done) {
          sse.close()
          setSearching(false)
          setScrapeState(prev => prev
            ? { ...prev, finished: true, step: 'done',
                message: prev.message.includes('Concluído') ? prev.message : 'Busca concluída!' }
            : null
          )
          // Atualizar grade com as novas imagens
          refreshImages()
          setTimeout(() => setScrapeState(null), 4000)
          return
        }

        if (data.step === 'error') {
          sse.close()
          setSearching(false)
          setScrapeState({ step: 'error', message: data.message, done: 0, total: 0, error: true })
          setTimeout(() => setScrapeState(null), 6000)
          return
        }

        setScrapeState({
          step:    data.step    ?? 'downloading',
          message: data.message ?? '',
          done:    data.done    ?? 0,
          total:   data.total   ?? limit,
          success: data.success,
        })
      }

      sse.onerror = () => {
        sse.close()
        setSearching(false)
        setScrapeState(prev => prev && !prev.finished
          ? { ...prev, error: true, step: 'error', message: 'Conexão com o servidor perdida.' }
          : null
        )
      }
    } catch (err) {
      setSearching(false)
      setScrapeState({ step: 'error', message: 'Erro ao iniciar a busca.', done: 0, total: 0, error: true })
    }
  }, [refreshImages])

  // ── Process / Save ────────────────────────────────────────────────────────

  const handleProcess = async () => {
    if (selected.size === 0) return
    setProcessing(true)
    try {
      const imgs = images.filter(i => selected.has(i.id)).map(i => i.path)
      const mons = monitors.filter(m => selMonitors.has(m.name)).map(m => m.name)
      await api.saveSelection({ images: imgs, monitors: mons })
      await api.process()
      showToast(`✓ ${imgs.length} imagem(ns) enfileiradas para processamento!`)
    } catch { showToast('Erro ao processar.') }
    finally   { setProcessing(false) }
  }

  const handleClear = async () => {
    if (!window.confirm('Remover todas as imagens baixadas? Esta ação não pode ser desfeita.')) return
    setClearing(true)
    try {
      const result = await api.clearImages()
      setImages([])
      setSelected(new Set())
      showToast(`🗑 Galeria limpa — ${result.cleared} arquivo(s) removido(s)`)
    } catch {
      showToast('Erro ao limpar a galeria.')
    } finally {
      setClearing(false)
    }
  }

  const handleApplyWallpaper = async (monitorName: string, imageId: string) => {
    setApplyingMonitor(monitorName)
    try {
      const result = await api.setWallpaper({ image_id: imageId, monitor_name: monitorName })
      showToast(`✓ ${result.message}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido'
      showToast(`Erro ao aplicar wallpaper: ${msg}`)
    } finally {
      setApplyingMonitor(null)
    }
  }

  const handleSaveExit = async () => {
    const imgs = images.filter(i => selected.has(i.id)).map(i => i.path)
    const mons = monitors.filter(m => selMonitors.has(m.name)).map(m => m.name)
    await api.saveSelection({ images: imgs, monitors: mons })
    showToast(`💾 Seleção salva: ${imgs.length} imagem(ns)`)
  }

  const showToast = (msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3500)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-screen overflow-hidden">

      <Toolbar
        total={images.length}
        selectedCount={selected.size}
        sortKey={sortKey}
        searching={searching}
        clearing={clearing}
        onSortChange={setSortKey}
        onSelectAll={selectAll}
        onSelectNone={selectNone}
        onSearch={handleSearch}
        onClear={handleClear}
      />

      <div className="flex flex-1 overflow-hidden">
        <ImageGrid
          images={sorted}
          selected={selected}
          loading={loading}
          searching={searching}
          scrapeState={scrapeState}
          onToggle={toggle}
          onPreview={setPreview}
          onHover={setHovered}
        />

        <Sidebar
          total={images.length}
          selectedImageIds={Array.from(selected)}
          hovered={hovered}
          monitors={monitors}
          selectedMonitors={selMonitors}
          processing={processing}
          applyingMonitor={applyingMonitor}
          onMonitorToggle={name => {
            setSelMonitors(prev => {
              const next = new Set(prev)
              next.has(name) ? next.delete(name) : next.add(name)
              return next
            })
          }}
          onSelectAll={selectAll}
          onSelectNone={selectNone}
          onProcess={handleProcess}
          onSaveExit={handleSaveExit}
          onApplyWallpaper={handleApplyWallpaper}
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
