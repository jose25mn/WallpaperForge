"""Coleta de imagens — estágio 2.

Fontes suportadas:
  wallhaven → Wallhaven API v1 (SFW, ótima para wallpapers)
  bing       → Bing Images HTML scraping (maior cobertura geral)
  reddit     → Reddit JSON público (fan art, community wallpapers)
  ddg        → DuckDuckGo Images (ddgs)
  multi      → Todas as fontes combinadas (recomendado para temas nichados)
  url        → gallery-dl (colar URL de galeria/board)

Download concorrente httpx, retry/backoff.  Salvo em work/raw/ + manifest.json.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import logging
import re
import subprocess
import sys
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

# ── Reddit subreddits para busca de wallpapers/fan art ────────────────────────
REDDIT_SUBS = [
    "wallpaper", "wallpapers", "WidescreenWallpaper",
    "ImaginaryLandscapes", "ImaginaryCharacters", "AnimeWallpaper",
    "Art", "DigitalArt", "DarkFantasy",
]


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


def _merge_unique(base: list[str], *extra: list[str]) -> list[str]:
    """Merge URL lists deduplicating by value."""
    seen = set(base)
    result = list(base)
    for lst in extra:
        for u in lst:
            if u not in seen:
                seen.add(u)
                result.append(u)
    return result


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


# ── Wallhaven API ──────────────────────────────────────────────────────────────

def _collect_wallhaven(query: str, limit: int, progress: ProgressCb) -> list[str]:
    """Wallhaven API v1 — sem chave, SFW, paginada."""
    urls: list[str] = []
    page = 1

    with httpx.Client(headers=HEADERS, verify=False, timeout=10) as client:
        while len(urls) < limit:
            try:
                resp = client.get(
                    "https://wallhaven.cc/api/v1/search",
                    params={"q": query, "categories": "111", "purity": "100",
                            "sorting": "relevance", "page": page},
                )
                if resp.status_code == 429:
                    log.warning("Wallhaven ratelimit (pág %d)", page)
                    break
                if resp.status_code != 200:
                    break

                body  = resp.json()
                items = body.get("data", [])
                if not items:
                    break

                for item in items:
                    if (p := item.get("path")):
                        urls.append(p)
                    if len(urls) >= limit:
                        break

                meta = body.get("meta", {})
                progress({"step": "collecting",
                          "message": f"Wallhaven: {len(urls)} URLs (pág {page}/{meta.get('last_page', '?')})…",
                          "done": len(urls), "total": limit})

                if page >= meta.get("last_page", 1):
                    break
                page += 1

            except Exception as exc:
                log.error("Wallhaven: %s", exc)
                break

    log.info("Wallhaven: %d URLs para '%s'", len(urls), query)
    return urls[:limit]


# ── Bing Images ────────────────────────────────────────────────────────────────

def _collect_bing(query: str, limit: int, progress: ProgressCb) -> list[str]:
    """
    Bing Images HTML scraping — maior cobertura, sem API key.

    Extrai blobs JSON da classe 'iusc' para obter URLs diretas das imagens.
    """
    urls: list[str] = []
    offset    = 0
    page_size = 35

    # Adiciona contexto de wallpaper para resultados melhores
    search_q = f"{query} wallpaper 4k"

    bing_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    with httpx.Client(headers=bing_headers, verify=False, timeout=15) as client:
        while len(urls) < limit:
            try:
                resp = client.get(
                    "https://www.bing.com/images/search",
                    params={"q": search_q, "first": offset, "count": page_size,
                            "form": "HDRSC2", "tsc": "ImageBasicHover"},
                )
                if resp.status_code != 200:
                    log.debug("Bing status %d", resp.status_code)
                    break

                found = 0

                # Formato 1: m=&quot;{...}&quot; (entidades HTML)
                for m in re.finditer(r'm=&quot;(\{[^&]+\})&quot;', resp.text):
                    try:
                        data = json.loads(html_mod.unescape(m.group(1)))
                        if (u := data.get("murl", "")) and u.startswith("http"):
                            urls.append(u)
                            found += 1
                    except Exception:
                        pass

                # Formato 2: m="{...}" direto
                if not found:
                    for m in re.finditer(r'class="iusc"[^>]+?m="(\{.+?\})"', resp.text, re.DOTALL):
                        try:
                            data = json.loads(html_mod.unescape(m.group(1)))
                            if (u := data.get("murl", "")) and u.startswith("http"):
                                urls.append(u)
                                found += 1
                        except Exception:
                            pass

                if not found:
                    break

                progress({"step": "collecting",
                          "message": f"Bing: {len(urls)} URLs…",
                          "done": min(len(urls), limit), "total": limit})

                offset += page_size
                time.sleep(0.25)

            except Exception as exc:
                log.error("Bing: %s", exc)
                break

    result = list(dict.fromkeys(urls))[:limit]   # dedup
    log.info("Bing: %d URLs para '%s'", len(result), query)
    return result


# ── Reddit ─────────────────────────────────────────────────────────────────────

def _collect_reddit(query: str, limit: int, progress: ProgressCb) -> list[str]:
    """
    Reddit public JSON API — posts de topo de todos os tempos.

    Busca em múltiplos subreddits; extrai URLs diretas de imagens e previews.
    """
    urls: list[str] = []
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

    reddit_headers = {
        "User-Agent": "WallpaperForge/1.0",
        "Accept": "application/json",
    }

    with httpx.Client(headers=reddit_headers, verify=False, timeout=15) as client:
        for sub in REDDIT_SUBS:
            if len(urls) >= limit:
                break
            try:
                resp = client.get(
                    f"https://www.reddit.com/r/{sub}/search.json",
                    params={"q": query, "restrict_sr": "true",
                            "sort": "top", "t": "all", "limit": 50},
                )
                if resp.status_code != 200:
                    time.sleep(0.5)
                    continue

                posts = resp.json().get("data", {}).get("children", [])
                for post in posts:
                    pd = post.get("data", {})

                    # URL direta de imagem
                    url = pd.get("url", "")
                    if url and Path(urlparse(url).path).suffix.lower() in IMAGE_EXTS:
                        urls.append(url)

                    # Preview de alta resolução
                    for img in pd.get("preview", {}).get("images", []):
                        src = img.get("source", {})
                        src_url = src.get("url", "").replace("&amp;", "&")
                        if src_url and src.get("width", 0) >= 1000:
                            urls.append(src_url)
                            break

                progress({"step": "collecting",
                          "message": f"Reddit r/{sub}: {len(urls)} URLs…",
                          "done": min(len(urls), limit), "total": limit})
                time.sleep(0.3)

            except Exception as exc:
                log.debug("Reddit r/%s: %s", sub, exc)
                time.sleep(0.5)

    result = list(dict.fromkeys(urls))[:limit]   # dedup
    log.info("Reddit: %d URLs para '%s'", len(result), query)
    return result


# ── DuckDuckGo Images ──────────────────────────────────────────────────────────

def _collect_ddg(query: str, limit: int) -> list[str]:
    """DuckDuckGo Images via ddgs com retry em ratelimit."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        except ImportError:
            log.error("ddgs não instalado. Execute: pip install ddgs")
            return []

    urls: list[str] = []
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                for r in ddgs.images(query, max_results=limit):
                    if (u := r.get("image", "")):
                        urls.append(u)
            break
        except Exception as exc:
            msg = str(exc)
            if "Ratelimit" in msg or "403" in msg or "429" in msg:
                if attempt < 2:
                    wait = 3 * (attempt + 1)
                    log.warning("DDG ratelimit; aguardando %ds…", wait)
                    time.sleep(wait)
                else:
                    log.error("DDG bloqueado após 3 tentativas.")
            else:
                log.error("DDG: %s", exc)
                break

    log.info("DDG: %d URLs para '%s'", len(urls), query)
    return urls


# ── gallery-dl ─────────────────────────────────────────────────────────────────

def _gallery_dl_exe() -> str:
    """Retorna o gallery-dl do venv atual, ou via PATH."""
    scripts = Path(sys.executable).parent
    for name in ("gallery-dl.exe", "gallery-dl"):
        if (c := scripts / name).exists():
            return str(c)
    return "gallery-dl"


def _collect_gallery_dl(url: str, out_dir: Path, progress: ProgressCb) -> int:
    exe = _gallery_dl_exe()
    try:
        result = subprocess.run(
            [exe, "--directory", str(out_dir), url],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            log.warning("gallery-dl saiu %d: %s", result.returncode, result.stderr[:200])
        count = sum(1 for f in out_dir.iterdir()
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        progress({"step": "gallery-dl", "message": f"gallery-dl: {count} arquivo(s)",
                  "done": count, "total": count})
        return count
    except FileNotFoundError:
        progress({"step": "error",
                  "message": f"gallery-dl não encontrado ({exe}). Execute: pip install gallery-dl"})
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
                progress({"step": "downloading", "done": i, "total": total,
                          "success": success, "message": f"Baixando {i}/{total} ({success} ok)"})

    _save_manifest(manifest)
    return success


# ── Ponto de entrada público ──────────────────────────────────────────────────

def run_scrape(
    *,
    query:    str | None = None,
    url:      str | None = None,
    limit:    int = 300,
    source:   str = "multi",
    progress: ProgressCb = lambda _: None,
) -> int:
    """
    Executa a coleta e retorna o número de arquivos baixados.

    source:
      "multi"     → Wallhaven + Bing + Reddit + DDG (recomendado)
      "wallhaven" → só Wallhaven
      "bing"      → só Bing Images
      "reddit"    → só Reddit
      "ddg"       → só DuckDuckGo
      (ignorado quando url é fornecida → gallery-dl)
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

    # ── Coleta por palavra-chave ──────────────────────────────────────────────

    urls: list[str] = []

    if source == "multi":
        # ─ Wallhaven ─────────────────────────────────────────────────────────
        progress({"step": "collecting", "message": "Wallhaven…", "done": 0, "total": limit})
        wh = _collect_wallhaven(query, limit, progress)
        urls = _merge_unique(urls, wh)
        progress({"step": "collecting",
                  "message": f"Wallhaven: {len(wh)} — total {len(urls)}",
                  "done": len(urls), "total": limit})

        # ─ Bing ───────────────────────────────────────────────────────────────
        progress({"step": "collecting", "message": "Bing Images…", "done": len(urls), "total": limit})
        bing = _collect_bing(query, limit, progress)
        urls = _merge_unique(urls, bing)
        progress({"step": "collecting",
                  "message": f"Bing: {len(bing)} — total {len(urls)}",
                  "done": len(urls), "total": limit})

        # ─ Reddit ─────────────────────────────────────────────────────────────
        reddit_limit = max(50, limit // 3)
        progress({"step": "collecting", "message": "Reddit…", "done": len(urls), "total": limit})
        rdt = _collect_reddit(query, reddit_limit, progress)
        urls = _merge_unique(urls, rdt)
        progress({"step": "collecting",
                  "message": f"Reddit: {len(rdt)} — total {len(urls)}",
                  "done": len(urls), "total": limit})

        # ─ DDG se ainda faltam imagens ────────────────────────────────────────
        if len(urls) < limit // 3:
            progress({"step": "collecting",
                      "message": f"Poucos resultados ({len(urls)}). Tentando DuckDuckGo…",
                      "done": len(urls), "total": limit})
            ddg = _collect_ddg(query, limit)
            urls = _merge_unique(urls, ddg)

        urls = urls[:limit]
        source_name = f"Multi ({len(urls)} URLs)"

    elif source == "wallhaven":
        progress({"step": "collecting", "message": f"Wallhaven: '{query}'…", "done": 0, "total": limit})
        urls = _collect_wallhaven(query, limit, progress)
        # fallback DDG
        if len(urls) < 12:
            progress({"step": "collecting",
                      "message": f"Wallhaven: {len(urls)} resultado(s). Complementando com DDG…",
                      "done": len(urls), "total": limit})
            urls = _merge_unique(urls, _collect_ddg(query, limit - len(urls)))
        source_name = "Wallhaven"

    elif source == "bing":
        progress({"step": "collecting", "message": f"Bing: '{query}'…", "done": 0, "total": limit})
        urls = _collect_bing(query, limit, progress)
        source_name = "Bing"

    elif source == "reddit":
        progress({"step": "collecting", "message": f"Reddit: '{query}'…", "done": 0, "total": limit})
        urls = _collect_reddit(query, limit, progress)
        source_name = "Reddit"

    else:  # ddg
        progress({"step": "collecting", "message": f"DuckDuckGo: '{query}'…", "done": 0, "total": limit})
        urls = _collect_ddg(query, limit)
        source_name = "DuckDuckGo"
        # fallback Wallhaven
        if len(urls) < 12:
            progress({"step": "collecting",
                      "message": f"DDG: {len(urls)} resultado(s). Complementando com Wallhaven…",
                      "done": len(urls), "total": limit})
            urls = _merge_unique(urls, _collect_wallhaven(query, limit - len(urls), progress))

    if not urls:
        progress({"step": "error",
                  "message": f"Nenhuma imagem encontrada para '{query}'. Tente outro termo ou modo Multi."})
        return 0

    progress({"step": "downloading",
              "message": f"{len(urls)} URLs ({source_name}). Iniciando download…",
              "done": 0, "total": len(urls)})
    count = _download_batch(urls, RAW_DIR, manifest, progress)
    progress({"step": "done",
              "message": f"Concluído: {count}/{len(urls)} imagens baixadas via {source_name}.",
              "done": count, "total": len(urls)})
    log.info("Scrape (%s): %d/%d em %s", source_name, count, len(urls), RAW_DIR)
    return count


# ── CLI handler ────────────────────────────────────────────────────────────────

def cmd_scrape(
    query:  str | None = None,
    url:    str | None = None,
    limit:  int = 300,
    source: str = "multi",
) -> None:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

    console = Console()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=console, transient=True) as prog:
        tid = prog.add_task("Coletando…", total=limit)

        def cb(msg: dict) -> None:
            prog.update(tid, completed=msg.get("done", 0),
                        total=max(msg.get("total", limit), 1),
                        description=msg.get("message", ""))

        count = run_scrape(query=query, url=url, limit=limit, source=source, progress=cb)

    console.print(f"[bold green]✓[/] {count} imagem(ns) em [cyan]{RAW_DIR}[/]")
