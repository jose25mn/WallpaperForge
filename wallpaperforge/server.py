"""Backend FastAPI para a interface web do WallpaperForge.

Rotas:
  POST /api/scrape              → inicia coleta (retorna task_id)
  GET  /api/scrape/stream/{id}  → SSE de progresso da coleta
  GET  /api/images              → lista de imagens com metadados
  GET  /api/thumbs/{id}         → thumbnail JPEG (gerado e cacheado)
  GET  /api/full/{id}           → imagem redimensionada para preview
  GET  /api/monitors            → monitores detectados (com orientação)
  GET  /api/selection           → selection.json atual
  POST /api/selection           → salva seleção
  POST /api/process             → dispara pipeline
  POST /api/set-wallpaper       → aplica wallpaper direto no monitor
  GET  /                        → SPA React (dist/)
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Timer
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

log = logging.getLogger(__name__)

# ── Caminhos ──────────────────────────────────────────────────────────────────

WORK_DIR       = Path.cwd() / "work"
FILTERED_DIR   = WORK_DIR / "filtered"
RAW_DIR        = WORK_DIR / "raw"
SELECTION_JSON = WORK_DIR / "selection.json"
THUMB_CACHE    = WORK_DIR / ".thumbs"
FRONTEND_DIST  = Path(__file__).parent.parent / "frontend" / "dist"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
THUMB_W, THUMB_H = 280, 200

# ── Helpers ───────────────────────────────────────────────────────────────────

def _image_id(path: Path) -> str:
    return hashlib.md5(str(path.resolve()).encode()).hexdigest()[:14]


def _find_all_images() -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for d in (FILTERED_DIR, RAW_DIR):
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTS and f.is_file() and f not in seen:
                seen.add(f)
                result.append(f)
    return result


def _read_dims(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _make_thumb(path: Path) -> bytes:
    from PIL import Image
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = THUMB_CACHE / f"{_image_id(path)}.jpg"
    if cache_path.exists():
        return cache_path.read_bytes()

    with Image.open(path) as im:
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (10, 10, 20))
            bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[3])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85, optimize=True)
    data = buf.getvalue()
    cache_path.write_bytes(data)
    return data


# Mapa id → Path (reconstruído a cada requisição ao endpoint de lista)
_id_to_path: dict[str, Path] = {}

# ── Scrape tasks ──────────────────────────────────────────────────────────────

_scrape_executor   = ThreadPoolExecutor(max_workers=2)
_wallpaper_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wallpaper")
_scrape_tasks:      dict[str, asyncio.Queue] = {}   # task_id → asyncio.Queue

WALLPAPER_DIR = WORK_DIR / ".wallpapers"


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="WallpaperForge API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174",
                   "http://127.0.0.1:5173", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SelectionPayload(BaseModel):
    images:   list[str]
    monitors: list[str]


class ScrapeRequest(BaseModel):
    query:  str | None = None
    url:    str | None = None
    limit:  int = 300
    source: str = "ddg"   # "ddg" | "wallhaven"


class SetWallpaperRequest(BaseModel):
    image_id:     str
    monitor_name: str   # e.g. "\\.\DISPLAY1"


# ── Scrape ────────────────────────────────────────────────────────────────────

@app.post("/api/scrape")
async def start_scrape(req: ScrapeRequest) -> dict:
    """Inicia a coleta em background; retorna task_id para seguir via SSE."""
    if not req.query and not req.url:
        raise HTTPException(400, "Forneça 'query' ou 'url'.")

    task_id = uuid.uuid4().hex[:10]
    q: asyncio.Queue = asyncio.Queue()
    _scrape_tasks[task_id] = q

    loop = asyncio.get_event_loop()

    def _run() -> None:
        from wallpaperforge.scraper import run_scrape

        def _cb(msg: dict) -> None:
            loop.call_soon_threadsafe(q.put_nowait, msg)

        try:
            run_scrape(query=req.query, url=req.url, limit=req.limit, source=req.source, progress=_cb)
        except Exception as exc:
            loop.call_soon_threadsafe(q.put_nowait, {"step": "error", "message": str(exc)})
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)  # sentinela de fim

    loop.run_in_executor(_scrape_executor, _run)
    return {"task_id": task_id}


@app.get("/api/scrape/stream/{task_id}")
async def scrape_stream(task_id: str) -> StreamingResponse:
    """SSE: transmite o progresso da coleta em tempo real."""
    q = _scrape_tasks.get(task_id)
    if q is None:
        raise HTTPException(404, "Task não encontrada.")

    async def event_gen():
        try:
            while True:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                if msg is None:
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        finally:
            _scrape_tasks.pop(task_id, None)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Rotas API ─────────────────────────────────────────────────────────────────

@app.get("/api/images")
def list_images() -> list[dict]:
    global _id_to_path
    paths = _find_all_images()
    result = []
    _id_to_path = {}
    for p in paths:
        img_id = _image_id(p)
        _id_to_path[img_id] = p
        w, h = _read_dims(p)
        result.append({
            "id":         img_id,
            "filename":   p.name,
            "path":       str(p),
            "width":      w,
            "height":     h,
            "resolution": f"{w}x{h}" if w else "?",
            "megapixels": round(w * h / 1_000_000, 1) if w else 0,
            "source":     p.parent.name,
        })
    return result


@app.get("/api/thumbs/{img_id}")
def get_thumbnail(img_id: str) -> Response:
    # Tenta encontrar no cache primeiro (sem precisar recarregar a lista)
    cached = THUMB_CACHE / f"{img_id}.jpg"
    if cached.exists():
        return Response(cached.read_bytes(), media_type="image/jpeg")

    path = _id_to_path.get(img_id)
    if not path or not path.exists():
        raise HTTPException(404, "Imagem não encontrada")
    try:
        data = _make_thumb(path)
        return Response(data, media_type="image/jpeg")
    except Exception as exc:
        log.error("Erro ao gerar thumbnail para %s: %s", path, exc)
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/full/{img_id}")
def get_full_image(img_id: str) -> Response:
    path = _id_to_path.get(img_id)
    if not path:
        # Percorrer disco na ausência do mapa
        for p in _find_all_images():
            if _image_id(p) == img_id:
                path = p
                _id_to_path[img_id] = p
                break
    if not path or not path.exists():
        raise HTTPException(404, "Imagem não encontrada")
    try:
        from PIL import Image
        with Image.open(path) as im:
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((1600, 1000), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
        return Response(buf.getvalue(), media_type="image/jpeg")
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/monitors")
def list_monitors() -> list[dict]:
    from wallpaperforge.monitors import load_monitors
    return [m.to_dict() for m in load_monitors()]


@app.get("/api/selection")
def get_selection() -> dict:
    if not SELECTION_JSON.exists():
        return {"images": [], "monitors": []}
    try:
        return json.loads(SELECTION_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"images": [], "monitors": []}


@app.post("/api/selection")
def save_selection(payload: SelectionPayload) -> dict:
    SELECTION_JSON.parent.mkdir(parents=True, exist_ok=True)
    data = {"images": payload.images, "monitors": payload.monitors}
    SELECTION_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Seleção salva: %d imagens", len(payload.images))
    return {"ok": True, "count": len(payload.images)}


@app.post("/api/process")
def process_selection() -> dict:
    # Placeholder — integrar com pipeline completo
    return {"ok": True, "message": "Pipeline de processamento iniciado (stub)."}


@app.delete("/api/images")
def clear_images() -> dict:
    """Remove todas as imagens baixadas, thumbnails e seleção atual."""
    import shutil

    cleared = 0
    for directory in (FILTERED_DIR, RAW_DIR, THUMB_CACHE, WALLPAPER_DIR):
        if directory.exists():
            for f in directory.iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                        cleared += 1
                except Exception:
                    pass

    if SELECTION_JSON.exists():
        SELECTION_JSON.unlink(missing_ok=True)

    _id_to_path.clear()
    log.info("Galeria limpa: %d arquivo(s) removido(s).", cleared)
    return {"ok": True, "cleared": cleared}


@app.post("/api/set-wallpaper")
async def set_wallpaper_endpoint(req: SetWallpaperRequest) -> dict:
    """Recorta a imagem para as dimensões do monitor e aplica como wallpaper."""
    # Localiza a imagem
    path = _id_to_path.get(req.image_id)
    if not path:
        for p in _find_all_images():
            if _image_id(p) == req.image_id:
                path = p
                _id_to_path[req.image_id] = p
                break
    if not path or not path.exists():
        raise HTTPException(404, "Imagem não encontrada")

    # Localiza o monitor
    from wallpaperforge.monitors import load_monitors
    monitors = load_monitors()
    monitor  = next((m for m in monitors if m.name == req.monitor_name), None)
    if not monitor:
        raise HTTPException(404, f"Monitor '{req.monitor_name}' não encontrado")

    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    safe    = req.monitor_name.replace("\\", "").replace(".", "").replace("/", "")
    out     = WALLPAPER_DIR / f"{req.image_id}_{safe}_{monitor.width}x{monitor.height}.png"
    img_snap = path      # capture for lambda
    mon_snap = monitor   # capture for lambda

    def _worker() -> dict:
        from wallpaperforge.crop            import crop_image_for_monitor
        from wallpaperforge.wallpaper_setter import set_wallpaper

        result = crop_image_for_monitor(img_snap, mon_snap.width, mon_snap.height, out)
        if not result.success:
            return {"ok": False, "error": f"Recorte falhou: {result.reason}"}

        ok = set_wallpaper(out, mon_snap.x, mon_snap.y)
        if not ok:
            return {"ok": False, "error": "Falha ao definir o wallpaper no Windows"}

        return {"ok": True, "message": f"Wallpaper aplicado em {mon_snap.name}"}

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(_wallpaper_executor, _worker)

    if not result["ok"]:
        raise HTTPException(500, result["error"])
    return result


# ── Serve SPA React (produção) ────────────────────────────────────────────────

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def start_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
) -> None:
    import uvicorn

    if open_browser:
        Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    log.info("Iniciando servidor em http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
