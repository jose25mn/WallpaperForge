"""Detecção de monitores físicos.

Caminho principal : Win32 EnumDisplayMonitors + GetDpiForMonitor
Fallback          : screeninfo

SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE) é chamado antes de
qualquer medição para que as coordenadas retornadas sejam pixels físicos,
não pixels lógicos escalados pelo Windows.

Fluxo de dados:
  detect_monitors()  →  salva config/monitors.json  →  retorna list[MonitorInfo]
  load_monitors()    →  lê do cache ou chama detect_monitors()
  cmd_list_monitors()→  CLI: imprime tabela e sai
"""

from __future__ import annotations

import ctypes
import dataclasses
import json
import logging
import sys
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

log = logging.getLogger(__name__)
console = Console()

# ── Caminhos ──────────────────────────────────────────────────────────────────

CONFIG_DIR   = Path.cwd() / "config"
MONITORS_JSON = CONFIG_DIR / "monitors.json"

# ── DPI awareness ─────────────────────────────────────────────────────────────

_DPI_AWARENESS_SET = False


def _ensure_dpi_awareness() -> None:
    """Chama SetProcessDpiAwareness(2) uma única vez.

    Com PROCESS_PER_MONITOR_DPI_AWARE=2 as coordenadas Win32 correspondem
    a pixels físicos, não a pixels virtuais ajustados pela escala do Windows.
    """
    global _DPI_AWARENESS_SET
    if _DPI_AWARENESS_SET or sys.platform != "win32":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2  (Windows 8.1+, shcore.dll)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        log.debug("SetProcessDpiAwareness(2) ok")
    except (AttributeError, OSError):
        try:
            # Fallback Windows Vista/7
            ctypes.windll.user32.SetProcessDPIAware()
            log.debug("SetProcessDPIAware() ok (legacy)")
        except (AttributeError, OSError):
            log.warning(
                "Não foi possível definir DPI awareness; "
                "a resolução detectada pode estar escalada."
            )
    _DPI_AWARENESS_SET = True


# ── Modelo de dados ───────────────────────────────────────────────────────────

@dataclass
class MonitorInfo:
    """Informações físicas de um monitor."""

    name: str
    width: int            # pixels físicos (horizontal)
    height: int           # pixels físicos (vertical)
    x: int                # origem X no desktop virtual
    y: int                # origem Y no desktop virtual
    is_primary: bool
    dpi_x: int   = 96
    dpi_y: int   = 96
    scale_factor: float = 1.0   # ex.: 1.25 para 125 %
    manual: bool = False        # True se adicionado à mão no monitors.json

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def is_portrait(self) -> bool:
        return self.height > self.width

    @property
    def orientation(self) -> str:
        return "portrait" if self.is_portrait else "landscape"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["resolution"]  = self.resolution
        d["is_portrait"] = self.is_portrait
        d["orientation"] = self.orientation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MonitorInfo":
        valid = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})


# ── Structs Win32 ─────────────────────────────────────────────────────────────

_CCHDEVICENAME   = 32
_MONITORINFOF_PRIMARY = 0x00000001
_MDT_EFFECTIVE_DPI    = 0   # DPI efetivo (inclui scaling do Windows)


class _MONITORINFOEXW(ctypes.Structure):
    """MONITORINFOEXW: MONITORINFO + szDevice[CCHDEVICENAME]."""

    _fields_ = [
        ("cbSize",    wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork",    wintypes.RECT),
        ("dwFlags",   wintypes.DWORD),
        ("szDevice",  ctypes.c_wchar * _CCHDEVICENAME),
    ]


# ── Helpers Win32 ─────────────────────────────────────────────────────────────

def _get_dpi_for_monitor(hmonitor: int) -> tuple[int, int]:
    """Retorna (dpi_x, dpi_y); padrão (96, 96) em caso de falha."""
    dpi_x = ctypes.c_uint(96)
    dpi_y = ctypes.c_uint(96)
    try:
        hr = ctypes.windll.shcore.GetDpiForMonitor(
            hmonitor,
            _MDT_EFFECTIVE_DPI,
            ctypes.byref(dpi_x),
            ctypes.byref(dpi_y),
        )
        if hr != 0:  # S_OK = 0
            log.debug("GetDpiForMonitor HRESULT=0x%08X para handle %s", hr, hmonitor)
            return 96, 96
    except (AttributeError, OSError) as exc:
        log.debug("GetDpiForMonitor indisponível: %s", exc)
    return int(dpi_x.value), int(dpi_y.value)


# ── Enumeradores ──────────────────────────────────────────────────────────────

def _enum_via_win32() -> list[MonitorInfo]:
    """Enumera monitores usando a API Win32 (método primário no Windows)."""
    user32   = ctypes.windll.user32
    monitors: list[MonitorInfo] = []
    index    = 0

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_size_t,                   # HMONITOR
        ctypes.c_size_t,                   # HDC
        ctypes.POINTER(wintypes.RECT),     # LPRECT (ignorado — usamos GetMonitorInfoW)
        ctypes.c_ssize_t,                  # LPARAM
    )

    def _callback(hmonitor: int, _hdc: int, _lprect, _lparam: int) -> bool:
        nonlocal index

        info = _MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(_MONITORINFOEXW)

        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            log.warning("GetMonitorInfoW falhou para handle %s", hmonitor)
            return True

        rect       = info.rcMonitor
        w          = rect.right  - rect.left
        h          = rect.bottom - rect.top
        is_primary = bool(info.dwFlags & _MONITORINFOF_PRIMARY)
        name       = info.szDevice.strip() or f"DISPLAY{index + 1}"

        dpi_x, dpi_y = _get_dpi_for_monitor(hmonitor)
        scale        = round(dpi_x / 96.0, 4)

        monitors.append(MonitorInfo(
            name=name,
            width=w,
            height=h,
            x=rect.left,
            y=rect.top,
            is_primary=is_primary,
            dpi_x=dpi_x,
            dpi_y=dpi_y,
            scale_factor=scale,
        ))
        index += 1
        return True

    cb = MonitorEnumProc(_callback)
    user32.EnumDisplayMonitors(None, None, cb, 0)
    return monitors


def _enum_via_screeninfo() -> list[MonitorInfo]:
    """Fallback usando a lib screeninfo (cross-platform)."""
    try:
        import screeninfo  # type: ignore[import-untyped]

        result: list[MonitorInfo] = []
        for idx, m in enumerate(screeninfo.get_monitors()):
            result.append(MonitorInfo(
                name=getattr(m, "name", None) or f"Monitor{idx + 1}",
                width=m.width,
                height=m.height,
                x=m.x,
                y=m.y,
                is_primary=bool(getattr(m, "is_primary", idx == 0)),
                dpi_x=96,
                dpi_y=96,
                scale_factor=1.0,
            ))
        return result
    except Exception as exc:
        log.debug("screeninfo falhou: %s", exc)
        return []


# ── API pública ───────────────────────────────────────────────────────────────

def detect_monitors() -> list[MonitorInfo]:
    """Detecta monitores físicos, persiste em monitors.json e retorna a lista.

    Prioridade de detecção:
      1. Win32 (Windows) — dados de DPI mais precisos
      2. screeninfo      — fallback / não-Windows
    Entradas manuais no monitors.json são preservadas e anexadas ao final.
    """
    _ensure_dpi_awareness()

    monitors: list[MonitorInfo] = []

    if sys.platform == "win32":
        monitors = _enum_via_win32()
        if monitors:
            log.info("Win32: %d monitor(es) detectado(s).", len(monitors))
        else:
            log.warning("Win32 retornou 0 monitores; tentando screeninfo.")

    if not monitors:
        monitors = _enum_via_screeninfo()
        if monitors:
            log.info("screeninfo: %d monitor(es) detectado(s).", len(monitors))
        else:
            log.error(
                "Nenhum monitor detectado. "
                "Verifique os drivers de vídeo ou adicione entradas manuais em %s.",
                MONITORS_JSON,
            )

    monitors = _merge_manual_entries(monitors)
    _save_monitors_json(monitors)
    return monitors


def load_monitors() -> list[MonitorInfo]:
    """Carrega monitores do cache (monitors.json) ou executa detect_monitors().

    Permite que o usuário edite o arquivo à mão para adicionar monitores
    sem refazer a detecção automática.
    """
    if not MONITORS_JSON.exists():
        return detect_monitors()
    try:
        data     = json.loads(MONITORS_JSON.read_text(encoding="utf-8"))
        monitors = [MonitorInfo.from_dict(e) for e in data]
        log.debug("Cache: %d monitor(es) carregado(s) de %s.", len(monitors), MONITORS_JSON)
        return monitors
    except (json.JSONDecodeError, OSError, TypeError, KeyError) as exc:
        log.warning("monitors.json inválido (%s); re-detectando.", exc)
        return detect_monitors()


# ── Persistência ──────────────────────────────────────────────────────────────

def _merge_manual_entries(detected: list[MonitorInfo]) -> list[MonitorInfo]:
    """Lê monitors.json e anexa entradas com manual=true à lista detectada."""
    if not MONITORS_JSON.exists():
        return detected
    try:
        existing = json.loads(MONITORS_JSON.read_text(encoding="utf-8"))
        manual   = [MonitorInfo.from_dict(e) for e in existing if e.get("manual")]
        if manual:
            log.info("%d entrada(s) manual/manuais carregada(s) de monitors.json.", len(manual))
        return detected + manual
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Não foi possível ler entradas manuais de %s: %s", MONITORS_JSON, exc)
        return detected


def _save_monitors_json(monitors: list[MonitorInfo]) -> None:
    """Salva monitores em config/monitors.json.

    Entradas manuais pré-existentes são preservadas; apenas as detectadas
    automaticamente são atualizadas.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Preservar entradas manuais existentes
    manual_entries: list[dict] = []
    if MONITORS_JSON.exists():
        try:
            existing      = json.loads(MONITORS_JSON.read_text(encoding="utf-8"))
            manual_entries = [e for e in existing if e.get("manual")]
        except (json.JSONDecodeError, OSError):
            pass

    auto_entries = [m.to_dict() for m in monitors if not m.manual]
    payload      = auto_entries + manual_entries

    MONITORS_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.debug("monitors.json salvo em %s.", MONITORS_JSON)


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_list_monitors() -> None:
    """Handler do subcomando `python -m wallpaperforge monitors`."""
    monitors = detect_monitors()

    table = Table(
        title="[bold]Monitores Detectados[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("#",           style="dim",    width=3,  justify="right")
    table.add_column("Nome",        min_width=18)
    table.add_column("Resolução",   justify="right", min_width=12)
    table.add_column("Posição",     justify="right", min_width=11)
    table.add_column("DPI",         justify="right", width=9)
    table.add_column("Escala",      justify="right", width=7)
    table.add_column("Orientação",  justify="center", width=10)
    table.add_column("Primário",    justify="center", width=9)
    table.add_column("Manual",      justify="center", width=7)

    for i, m in enumerate(monitors, 1):
        orient = "[magenta]Retrato[/magenta]" if m.is_portrait else "[cyan]Paisagem[/cyan]"
        table.add_row(
            str(i),
            m.name,
            f"[green]{m.resolution}[/green]" if m.is_primary else m.resolution,
            f"({m.x}, {m.y})",
            f"{m.dpi_x}x{m.dpi_y}",
            f"{m.scale_factor * 100:.0f}%",
            orient,
            "[bold green]✓[/bold green]" if m.is_primary else "",
            "[yellow]✓[/yellow]"         if m.manual    else "",
        )

    console.print()
    console.print(table)
    console.print(f"\n[bold]Total:[/] {len(monitors)} monitor(es)")
    console.print(f"[dim]Config: {MONITORS_JSON}[/dim]\n")
