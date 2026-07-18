"""Coleta de imagens — estágio 2.

Fontes suportadas:
  - DuckDuckGo Images (palavra-chave via ddgs)
  - gallery-dl (URL de board/tag — Pinterest, DeviantArt, Wallhaven, etc.)

Download concorrente com httpx (semáforo de 8 workers), retry/backoff,
User-Agent de browser real.  Tudo salvo em work/raw/ com manifest.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────

WORK_DIR   = Path.cwd() / "work"
RAW_DIR    = WORK_DIR / "raw"
MANIFEST   = RAW_DIR / "manifest.json"

SUPPORTED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_MAP        = {"image/jpeg": ".jpg", "image/png": ".png",
                  "image/webp": ".webp", "image/gif": ".gif"}
USER_AGENT     = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"}

ProgressCb = Callable[[dict], None]


# ── Manifest ───────────────────────────────────────────────────────────────────

def _load_manifest() -> dict[str, dict]:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(data: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:14]


def _ext_from_url(url: str, content_type: str) -> str:
    if content_type in EXT_MAP:
        return EXT_MAP[content_type]
    path_ext = Path(urlparse(url).path).suffix.lower()
    return path_ext if path_ext in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _download_one(
    url: str,
    client: httpx.Client,
    out_dir: Path,
    manifest: dict,
    *,
    retries: int = 3,
) -> Path | None:
    """Baixa uma URL e salva em out_dir. Retorna o Path ou None se falhou."""
    h = _url_hash(url)
    if h in manifest:
        existing = Path(manifest[h]["path"])
        if existing.exists():
            return existing   # já baixada, reusar

    for attempt in range(retries):
        try:
            resp = client.get(url, timeout=20, follow_redirects=True)
            if resp.status_code != 200:
                return None
            ct   = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            ext  = _ext_from_url(url, ct)
            path = out_dir / f"{h}{ext}"
            path.write_bytes(resp.content)
            manifest[h] = {"path": str(path), "url": url, "content_type": ct}
            return path
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(0.5 * (2 ** attempt))   # backoff exponencial
            else:
                log.debug("Falha ao baixar %s: %s", url, exc)
    return None


# ── DuckDuckGo Images ──────────────────────────────────────────────────────────

def _collect_ddg(query: str, limit: int) -> list[str]:
    """Coleta URLs de imagens via DuckDuckGo; retorna lista de URLs."""
    try:
        from duckduckgo_search import DDGS
        urls: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=limit):
                url = r.get("image", "")
                if url:
                    urls.append(url)
        log.info("DDG: %d URLs coletadas para '%s'", len(urls), query)
        return urls
    except Exception as exc:
        log.error("Erro DuckDuckGo: %s", exc)
        return []


# ── gallery-dl ─────────────────────────────────────────────────────────────────

def _collect_gallery_dl(url: str, out_dir: Path, progress: ProgressCb) -> int:
    """Usa gallery-dl (subprocess) para baixar imagens de uma URL de galeria."""
    try:
        result = subprocess.run(
            ["gallery-dl", "--directory", str(out_dir), url],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            log.warning("gallery-dl saiu com código %d: %s", result.returncode, result.stderr[:200])
        count = sum(1 for _ in out_dir.iterdir()
                    if _.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        progress({"step": "gallery-dl", "message": f"gallery-dl: {count} arquivo(s) baixado(s)", "done": count, "total": count})
        return count
    except FileNotFoundError:
        progress({"step": "error", "message": "gallery-dl não encontrado. Instale com: pip install gallery-dl"})
        log.error("gallery-dl não encontrado no PATH.")
        return 0
    except subprocess.TimeoutExpired:
        progress({"step": "error", "message": "gallery-dl excedeu o tempo limite."})
        return 0


# ── Download concorrente ───────────────────────────────────────────────────────

def _download_batch(
    urls: list[str],
    out_dir: Path,
    manifest: dict,
    progress: ProgressCb,
    *,
    workers: int = 8,
) -> int:
    """Baixa lista de URLs em paralelo. Retorna contagem de sucessos."""
    out_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    total   = len(urls)

    with httpx.Client(headers=HEADERS, verify=False) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_download_one, url, client, out_dir, manifest): url
                for url in urls
            }
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if result:
                    success += 1
                progress({
                    "step":    "downloading",
                    "done":    i,
                    "total":   total,
                    "success": success,
                    "message": f"Baixando {i}/{total} ({success} ok)",
                })

    _save_manifest(manifest)
    return success


# ── Ponto de entrada público ──────────────────────────────────────────────────

def run_scrape(
    *,
    query: str | None = None,
    url:   str | None = None,
    limit: int = 300,
    progress: ProgressCb = lambda _: None,
) -> int:
    """
    Executa a coleta de imagens e retorna o número de arquivos baixados.

    Args:
        query:    Palavra-chave para busca DuckDuckGo Images.
        url:      URL de board/tag/galeria para gallery-dl.
        limit:    Número máximo de imagens (só aplica ao DDG).
        progress: Callback chamado com dicts de progresso.
    """
    if not query and not url:
        log.error("Forneça --query ou --url.")
        return 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()

    # ── URL → gallery-dl ──────────────────────────────────────────────────────
    if url:
        progress({"step": "collecting", "message": f"Coletando via gallery-dl: {url}", "done": 0, "total": 1})
        return _collect_gallery_dl(url, RAW_DIR, progress)

    # ── Palavra-chave → DDG + download ───────────────────────────────────────
    progress({"step": "collecting", "message": f"Buscando '{query}' no DuckDuckGo…", "done": 0, "total": limit})
    urls = _collect_ddg(query, limit)

    if not urls:
        progress({"step": "error", "message": "Nenhuma imagem encontrada. Tente outro termo."})
        return 0

    progress({"step": "downloading", "message": f"{len(urls)} URLs encontradas. Iniciando download…", "done": 0, "total": len(urls)})
    count = _download_batch(urls, RAW_DIR, manifest, progress)
    progress({"step": "done", "message": f"Concluído: {count}/{len(urls)} imagens baixadas.", "done": count, "total": len(urls)})
    log.info("Scrape concluído: %d/%d imagens em %s", count, len(urls), RAW_DIR)
    return count


# ── CLI handler ────────────────────────────────────────────────────────────────

def cmd_scrape(
    query: str | None = None,
    url:   str | None = None,
    limit: int = 300,
) -> None:
    """Handler do subcomando `python -m wallpaperforge scrape`."""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as prog:
        task_id = prog.add_task("Coletando…", total=limit)

        def progress_cb(msg: dict) -> None:
            total = msg.get("total", limit)
            done  = msg.get("done", 0)
            text  = msg.get("message", "")
            prog.update(task_id, completed=done, total=max(total, 1), description=text)

        count = run_scrape(query=query, url=url, limit=limit, progress=progress_cb)

    console.print(f"[bold green]✓[/] {count} imagem(ns) salva(s) em [cyan]{RAW_DIR}[/]")
