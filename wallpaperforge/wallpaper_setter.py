"""Set desktop wallpaper per monitor via IDesktopWallpaper COM (Windows 8+).

Uses raw ctypes COM vtable calls — no extra dependencies.
Falls back to SystemParametersInfoW (all monitors) when COM fails.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import sys
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

# ── GUID ──────────────────────────────────────────────────────────────────────

class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_uint8 * 8),
    ]


def _guid(s: str) -> _GUID:
    b = uuid.UUID(s).bytes_le
    g = _GUID()
    ctypes.memmove(ctypes.addressof(g), b, 16)
    return g


# ── IDesktopWallpaper ─────────────────────────────────────────────────────────

_CLSID_DW          = "{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}"
_IID_DW            = "{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}"
_CLSCTX_LOCAL_SRV  = 4   # out-of-process COM server (explorer.exe)
_COINIT_STA        = 0   # single-threaded apartment

# vtable indices (IUnknown: 0=QI, 1=AddRef, 2=Release)
_VT_RELEASE        = 2
_VT_SET_WALLPAPER  = 3   # (LPCWSTR monitorID, LPCWSTR wallpaper)
_VT_GET_PATH_AT    = 5   # (UINT index, LPWSTR* path)
_VT_GET_PATH_COUNT = 6   # (UINT* count)
_VT_GET_RECT       = 7   # (LPCWSTR monitorID, RECT* rect)


def _vtfn(obj_val: int, idx: int) -> int:
    """Return function address at vtable[idx] for COM interface pointer obj_val."""
    vptr = ctypes.cast(ctypes.c_void_p(obj_val), ctypes.POINTER(ctypes.c_void_p))[0]
    return ctypes.cast(ctypes.c_void_p(vptr), ctypes.POINTER(ctypes.c_void_p))[idx]


# ── COM lifecycle ─────────────────────────────────────────────────────────────

def _create_idw() -> tuple[ctypes.c_void_p | None, bool]:
    """
    Instantiate IDesktopWallpaper COM object.

    Returns (ptr, com_inited): if com_inited=True, caller must CoUninitialize().
    """
    if sys.platform != "win32":
        return None, False
    try:
        ole32     = ctypes.windll.ole32
        hr_init   = ole32.CoInitializeEx(None, _COINIT_STA)
        # S_OK=0 or S_FALSE=1 → both need matching CoUninitialize
        com_inited = hr_init in (0, 1)

        clsid = _guid(_CLSID_DW)
        iid   = _guid(_IID_DW)
        ptr   = ctypes.c_void_p()
        hr    = ole32.CoCreateInstance(
            ctypes.byref(clsid), None, _CLSCTX_LOCAL_SRV,
            ctypes.byref(iid), ctypes.byref(ptr),
        )
        if hr != 0 or not ptr.value:
            log.debug("CoCreateInstance IDesktopWallpaper 0x%08X", hr & 0xFFFFFFFF)
            if com_inited:
                ole32.CoUninitialize()
            return None, False
        return ptr, com_inited
    except Exception as exc:
        log.debug("_create_idw: %s", exc)
        return None, False


def _release_idw(ptr: ctypes.c_void_p | None, com_inited: bool) -> None:
    try:
        if ptr and ptr.value:
            RelFn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            RelFn(_vtfn(ptr.value, _VT_RELEASE))(ptr.value)
    except Exception:
        pass
    if com_inited:
        try:
            ctypes.windll.ole32.CoUninitialize()
        except Exception:
            pass


# ── IDesktopWallpaper operations ──────────────────────────────────────────────

def _idw_monitor_paths() -> list[tuple[str, wintypes.RECT]]:
    """Return [(device_path, RECT)] for all monitors from IDesktopWallpaper."""
    ptr, com_inited = _create_idw()
    if ptr is None:
        return []
    try:
        count = ctypes.c_uint(0)
        CountFn = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint),
        )
        hr = CountFn(_vtfn(ptr.value, _VT_GET_PATH_COUNT))(ptr.value, ctypes.byref(count))
        if hr != 0:
            return []

        PathFn = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
        )
        RectFn = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.c_wchar_p,
            ctypes.POINTER(wintypes.RECT),
        )
        get_path = PathFn(_vtfn(ptr.value, _VT_GET_PATH_AT))
        get_rect = RectFn(_vtfn(ptr.value, _VT_GET_RECT))
        ole32    = ctypes.windll.ole32

        results: list[tuple[str, wintypes.RECT]] = []
        for i in range(count.value):
            path_ptr = ctypes.c_void_p(0)
            hr = get_path(ptr.value, i, ctypes.byref(path_ptr))
            if hr != 0 or not path_ptr.value:
                continue
            path_str = ctypes.wstring_at(path_ptr.value)
            ole32.CoTaskMemFree(ctypes.c_void_p(path_ptr.value))

            rect = wintypes.RECT()
            if get_rect(ptr.value, path_str, ctypes.byref(rect)) == 0:
                results.append((path_str, rect))
        return results
    except Exception as exc:
        log.debug("_idw_monitor_paths: %s", exc)
        return []
    finally:
        _release_idw(ptr, com_inited)


def _idw_set(device_path: str | None, image_path: Path) -> bool:
    """Call IDesktopWallpaper::SetWallpaper. device_path=None = all monitors."""
    ptr, com_inited = _create_idw()
    if ptr is None:
        return False
    try:
        SetFn = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        )
        hr = SetFn(_vtfn(ptr.value, _VT_SET_WALLPAPER))(
            ptr.value, device_path, str(image_path.resolve()),
        )
        if hr != 0:
            log.debug("SetWallpaper 0x%08X", hr & 0xFFFFFFFF)
        return hr == 0
    except Exception as exc:
        log.debug("_idw_set: %s", exc)
        return False
    finally:
        _release_idw(ptr, com_inited)


def _spi_set(image_path: Path) -> bool:
    """Fallback: SystemParametersInfoW (all monitors, same image)."""
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0014, 0,                          # SPI_SETDESKWALLPAPER
            str(image_path.resolve()),
            0x0001 | 0x0002,                    # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        return bool(ok)
    except Exception as exc:
        log.error("SystemParametersInfoW: %s", exc)
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def find_device_path(monitor_x: int, monitor_y: int) -> str | None:
    """Find IDesktopWallpaper hardware device path by monitor top-left position."""
    try:
        for path, rect in _idw_monitor_paths():
            if rect.left == monitor_x and rect.top == monitor_y:
                return path
    except Exception as exc:
        log.debug("find_device_path: %s", exc)
    return None


def set_wallpaper(
    image_path: Path,
    monitor_x: int | None = None,
    monitor_y: int | None = None,
) -> bool:
    """
    Set desktop wallpaper.

    Args:
        image_path: Cropped image at the exact monitor resolution.
        monitor_x:  Monitor left position in virtual desktop. None = all monitors.
        monitor_y:  Monitor top  position in virtual desktop. None = all monitors.

    Returns True on success.
    """
    if not image_path.exists():
        log.error("Image not found: %s", image_path)
        return False
    if sys.platform != "win32":
        log.warning("set_wallpaper is Windows-only")
        return False

    device_path: str | None = None
    if monitor_x is not None and monitor_y is not None:
        device_path = find_device_path(monitor_x, monitor_y)
        if device_path is None:
            log.warning(
                "No device path for monitor (%d, %d); applying to all monitors.",
                monitor_x, monitor_y,
            )

    ok = _idw_set(device_path, image_path)
    if ok:
        log.info("Wallpaper set via COM: %s → %s", image_path.name, device_path or "all")
        return True

    log.info("IDesktopWallpaper failed; trying SystemParametersInfoW")
    return _spi_set(image_path)
