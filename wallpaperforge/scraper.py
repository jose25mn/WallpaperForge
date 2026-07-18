"""Coleta de imagens — estágio 2.

Fontes suportadas:
  ddg       → DuckDuckGo Images (ddgs, com retry automático)
  wallhaven → Wallhaven API v1 (sem chave, SFW, ótima para wallpapers)
  url       → gallery-dl (Pinterest, DeviantArt, Wallhaven, etc.)

Download concorrente httpx, retry/backoff.  Salvo em work/raw/ + manifest.json.
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

WORK_DIR = Path.cwd() / "work"
RAW_DIR  = WORK_DIR / "raw"
MANIFEST = RAW_DIR / "manifest.json"

SUPPORTED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_MAP        = {"image/jpeg": ".jpg", "image/png": ".png",
                  "image/webp": ".webp", "image/gif": ".gif"}
USER_AGENT = (
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
    h = _url_hash(url)
    if h in manifest:
        existing = Path(manifest[h]["path"])
        if existing.exists():
            return existing

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
                time.sleep(0.5 * (2 ** attempt))
            else:
                log.debug("Falha ao baixar %s: %s", url, exc)
    return None


# ── DuckDuckGo Images ──────────────────────────────────────────────────────────

def _collect_ddg(query: str, limit: int) -> list[str]:
    """Coleta URLs via DuckDuckGo Images (ddgs). Retorna lista de URLs."""
    try:
        from ddgs import DDGS  # pacote novo (substituto de duckduckgo-search)
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        except ImportError:
            log.error("ddgs não instalado. Execute: pip install ddgs")
            return []

    urls: list[str] = []
    attempts = 0
    max_attempts = 3

    while attempts < max_attempts and len(urls) < limit:
        try:
            with DDGS() as ddgs:
                for r in ddgs.images(query, max_results=limit):
                    url = r.get("image", "")
                    if url:
                        urls.append(url)
            break
        except Exception as exc:
            attempts += 1
            msg = str(exc)
            if "Ratelimit" in msg or "429" in msg or "403" in msg:
                if attempts < max_attempts:
                    wait = 3 * attempts
                    log.warning("DDG ratelimit (tentativa %d/%d); aguardando %ds…", attempts, max_attempts, wait)
                    time.sleep(wait)
                else:
                    log.error("DDG bloqueado após %d tentativas. Use 'Wallhaven' como fonte.", max_attempts)
            else:
                log.error("Erro DDG: %s", exc)
                break

    log.info("DDG: %d URLs para '%s'", len(urls), query)
    return urls


# ── Wallhaven API ──────────────────────────────────────────────────────────────

_WALLHAVEN_URL = "https://wallhaven.cc/api/v1/search"

def _collect_wallhaven(query: str, limit: int, progress: ProgressCb) -> list[str]:
    """
    Coleta URLs diretas de imagens via Wallhaven API v1.

    Sem API key → apenas conteúdo SFW.
    """
    urls: list[str] = []
    page     = 1
    per_page = 24

    with httpx.Client(headers=HEADERS, verify=False, timeout=10) as client:
        while len(urls) < limit:
            try:
                resp = client.get(
                    _WALLHAVEN_URL,
                    params={
                        "q":          query,
                        "categories": "111",   # geral + anime + pessoas
                        "purity":     "100",   # SFW
                        "sorting":    "relevance",
                        "page":       page,
                    },
                )
                if resp.status_code != 200:
                    log.warning("Wallhaven API status %d na página %d", resp.status_code, page)
                    break

                body  = resp.json()
                items = body.get("data", [])
                if not items:
                    break

                for item in items:
                    path = item.get("path")
                    if path:
                        urls.append(path)
                    if len(urls) >= limit:
                        break

                meta      = body.get("meta", {})
                last_page = meta.get("last_page", 1)
                progress({
                    "step":    "collecting",
                    "message": f"Wallhaven: {len(urls)} URLs (página {page}/{last_page})…",
                    "done":    len(urls),
                    "total":   min(limit, meta.get("total", limit)),
                })

                if page >= last_page:
                    break
                page += 1

            except Exception as exc:
                log.error("Wallhaven API erro: %s", exc)
                break

    log.info("Wallhaven: %d URLs para '%s'", len(urls), query)
    return urls[:limit]


# ── gallery-dl ─────────────────────────────────────────────────────────────────

def _collect_gallery_dl(url: str, out_dir: Path, progress: ProgressCb) -> int:
    try:
        result = subprocess.run(
            ["gallery-dl", "--directory", str(out_dir), url],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            log.warning("gallery-dl saiu %d: %s", result.returncode, result.stderr[:200])
        count = sum(1 for f in out_dir.iterdir()
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        progress({"step": "gallery-dl", "message": f"gallery-dl: {count} arquivo(s)", "done": count, "total": count})
        return count
    except FileNotFoundError:
        progress({"step": "error", "message": "gallery-dl não encontrado. Instale: pip install gallery-dl"})
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
                if future.result():
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
    query:    str | None = None,
    url:      str | None = None,
    limit:    int = 300,
    source:   str = "ddg",   # "ddg" | "wallhaven" | (ignorado se url fornecida)
    progress: ProgressCb = lambda _: None,
) -> int:
    """
    Executa a coleta e retorna o número de arquivos baixados.

    Args:
        query:   Palavra-chave (DDG ou Wallhaven).
        url:     URL de galeria/board para gallery-dl.
        limit:   Máximo de imagens.
        source:  "ddg" ou "wallhaven" (ignorado quando url é fornecida).
        progress: Callback de progresso.
    """
    if not query and not url:
        log.error("Forneça query ou url.")
        return 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()

    # ── URL → gallery-dl ──────────────────────────────────────────────────────
    if url:
        progress({"step": "collecting", "message": f"gallery-dl: {url}", "done": 0, "total": 1})
        return _collect_gallery_dl(url, RAW_DIR, progress)

    # ── Palavra-chave → coleta de URLs ────────────────────────────────────────
    if source == "wallhaven":
        progress({"step": "collecting", "message": f"Buscando '{query}' no Wallhaven…", "done": 0, "total": limit})
        urls = _collect_wallhaven(query, limit, progress)
        source_name = "Wallhaven"
    else:
        progress({"step": "collecting", "message": f"Buscando '{query}' no DuckDuckGo…", "done": 0, "total": limit})
        urls = _collect_ddg(query, limit)
        source_name = "DuckDuckGo"

    if not urls:
        progress({"step": "error", "message": f"Nenhuma imagem encontrada em {source_name}. Tente outro termo ou fonte."})
        return 0

    progress({"step": "downloading", "message": f"{len(urls)} URLs encontradas. Iniciando download…", "done": 0, "total": len(urls)})
    count = _download_batch(urls, RAW_DIR, manifest, progress)
    progress({"step": "done", "message": f"Concluído: {count}/{len(urls)} imagens baixadas.", "done": count, "total": len(urls)})
    log.info("Scrape (%s) concluído: %d/%d em %s", source_name, count, len(urls), RAW_DIR)
    return count


# ── CLI handler ────────────────────────────────────────────────────────────────

def cmd_scrape(
    query:  str | None = None,
    url:    str | None = None,
    limit:  int = 300,
    source: str = "ddg",
) -> None:
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

        def cb(msg: dict) -> None:
            prog.update(task_id,
                        completed=msg.get("done", 0),
                        total=max(msg.get("total", limit), 1),
                        description=msg.get("message", ""))

        count = run_scrape(query=query, url=url, limit=limit, source=source, progress=cb)

    console.print(f"[bold green]✓[/] {count} imagem(ns) em [cyan]{RAW_DIR}[/]")
