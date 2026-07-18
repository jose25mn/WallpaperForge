"""Interface gráfica de seleção de imagens (PySide6).

Estágio 4: grade de thumbnails com lazy loading em background thread,
seleção múltipla (Shift+clique, Ctrl+A), preview, filtros por monitor
e persistência em work/selection.json.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    Qt, QRunnable, QThreadPool, QObject, Signal, QSize,
    QTimer, QPoint,
)
from PySide6.QtGui import (
    QPixmap, QImage, QColor, QIcon, QKeySequence, QShortcut,
    QPainter, QPen, QFont,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QSplitter,
    QDialog, QSizePolicy, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QAbstractItemView,
)

log = logging.getLogger(__name__)

# ── Caminhos ──────────────────────────────────────────────────────────────────

WORK_DIR       = Path.cwd() / "work"
FILTERED_DIR   = WORK_DIR / "filtered"
RAW_DIR        = WORK_DIR / "raw"
SELECTION_JSON = WORK_DIR / "selection.json"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
THUMB_SIZE     = QSize(220, 160)

# ── Tema ──────────────────────────────────────────────────────────────────────

DARK_CSS = """
QMainWindow, QWidget { background-color:#1a1a2e; color:#e0e0e0; }

QListWidget {
    background-color:#12122a;
    border:none; outline:none;
}
QListWidget::item {
    background-color:#0f3460;
    border:2px solid transparent;
    border-radius:6px;
    color:#b0b0c8;
}
QListWidget::item:selected {
    background-color:#1a3a5c;
    border:2px solid #4fc3f7;
    color:#ffffff;
}
QListWidget::item:hover:!selected {
    border:2px solid #2a5a8c;
    background-color:#1a2a50;
}

QPushButton {
    background-color:#0f3460; color:#e0e0e0;
    border:1px solid #2a5a8c; border-radius:6px;
    padding:8px 16px; font-size:13px;
}
QPushButton:hover { background-color:#1a4a7a; border-color:#4fc3f7; }

QPushButton#process_btn {
    background-color:#1a6b3c; border-color:#2da868;
    font-weight:bold; font-size:14px; padding:10px;
}
QPushButton#process_btn:hover { background-color:#2a8a50; }

QPushButton#preview_nav {
    background-color:#0f3460; color:#e0e0e0;
    border:1px solid #2a5a8c; border-radius:4px;
    padding:6px 14px; font-size:12px;
}

QComboBox {
    background-color:#0f3460; color:#e0e0e0;
    border:1px solid #2a5a8c; border-radius:4px;
    padding:4px 8px; min-height:26px;
}
QComboBox QAbstractItemView {
    background-color:#0f3460; color:#e0e0e0;
    selection-background-color:#1a4a7a; border:none;
}

QCheckBox { color:#e0e0e0; spacing:6px; }
QCheckBox::indicator { width:14px; height:14px; border-radius:3px;
                        border:2px solid #2a5a8c; background:#0f3460; }
QCheckBox::indicator:checked { background:#4fc3f7; border-color:#4fc3f7; }

QGroupBox {
    border:1px solid #2a5a8c; border-radius:6px;
    margin-top:8px; padding-top:6px;
    color:#7a9cc0; font-size:11px;
}
QGroupBox::title {
    subcontrol-origin:margin; left:8px; padding:0 4px;
}

QSplitter::handle { background-color:#2a5a8c; width:2px; }

QScrollBar:vertical {
    background:#0f1a30; width:8px; border-radius:4px;
}
QScrollBar::handle:vertical {
    background:#2a5a8c; border-radius:4px; min-height:20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""

# ── Modelo de dados ───────────────────────────────────────────────────────────

@dataclass
class ImageInfo:
    path: Path
    width: int  = 0
    height: int = 0
    source: str = ""

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width else "?"

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000


def _read_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _find_images(dirs: list[Path]) -> list[ImageInfo]:
    images: list[ImageInfo] = []
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTS and f.is_file():
                w, h = _read_dimensions(f)
                images.append(ImageInfo(path=f, width=w, height=h))
    return images


# ── Carregamento de thumbnails em background thread ───────────────────────────

class _ThumbSignals(QObject):
    loaded = Signal(Path, QPixmap)


class _ThumbTask(QRunnable):
    def __init__(self, path: Path, size: QSize, signals: _ThumbSignals) -> None:
        super().__init__()
        self._path, self._size, self._signals = path, size, signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            from PIL import Image
            with Image.open(self._path) as im:
                im.thumbnail((self._size.width(), self._size.height()), Image.LANCZOS)
                if im.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", im.size, (15, 33, 62))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                elif im.mode != "RGB":
                    im = im.convert("RGB")
                raw    = im.tobytes("raw", "RGB")
                qi     = QImage(raw, im.width, im.height, im.width * 3,
                                QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qi.copy())   # deep copy antes de sair da thread
        except Exception:
            pixmap = QPixmap(self._size)
            pixmap.fill(QColor(15, 33, 62))
        self._signals.loaded.emit(self._path, pixmap)


# ── Grade de imagens ──────────────────────────────────────────────────────────

class ImageGridWidget(QListWidget):
    """Grade lazy de thumbnails. Seleção: clique, Shift+clique, Ctrl+A."""

    hover_changed   = Signal(object)   # ImageInfo | None
    selection_count = Signal(int)

    def __init__(self, images: list[ImageInfo], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images           = list(images)
        self._path_to_item:    dict[Path, QListWidgetItem] = {}
        self._thumb_signals    = _ThumbSignals()

        # A conexão atravessa threads → Qt usa QueuedConnection automaticamente
        self._thumb_signals.loaded.connect(self._on_thumb_ready)

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(THUMB_SIZE)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(8)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)

        self.itemSelectionChanged.connect(
            lambda: self.selection_count.emit(len(self.selectedItems()))
        )
        self._populate()

    # ── Construção ────────────────────────────────────────────────────────────

    def _populate(self) -> None:
        self.clear()
        self._path_to_item.clear()

        placeholder = QPixmap(THUMB_SIZE)
        placeholder.fill(QColor(15, 33, 62))
        ph_icon = QIcon(placeholder)
        pool    = QThreadPool.globalInstance()

        for info in self._images:
            item = QListWidgetItem(ph_icon, info.path.stem[:26])
            item.setData(Qt.ItemDataRole.UserRole, info)
            item.setSizeHint(QSize(THUMB_SIZE.width() + 20, THUMB_SIZE.height() + 40))
            item.setToolTip(f"{info.path.name}\n{info.resolution}")
            self.addItem(item)
            self._path_to_item[info.path] = item

            pool.start(_ThumbTask(info.path, THUMB_SIZE, self._thumb_signals))

    def _on_thumb_ready(self, path: Path, pixmap: QPixmap) -> None:
        item = self._path_to_item.get(path)
        if item:
            item.setIcon(QIcon(pixmap))

    # ── Seleção ───────────────────────────────────────────────────────────────

    def select_all(self) -> None:
        self.selectAll()

    def select_none(self) -> None:
        self.clearSelection()

    def get_selected(self) -> list[ImageInfo]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self.selectedItems()]

    # ── Hover ─────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        item = self.itemAt(event.pos())
        self.hover_changed.emit(
            item.data(Qt.ItemDataRole.UserRole) if item else None
        )

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.hover_changed.emit(None)

    # ── Duplo clique → preview ────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item:
            info = item.data(Qt.ItemDataRole.UserRole)
            PreviewDialog(info, self._images, self.window()).exec()

    # ── Ordenação ─────────────────────────────────────────────────────────────

    def sort_images(self, key: str) -> None:
        selected_paths = {i.path for i in self.get_selected()}

        if key == "resolution":
            self._images.sort(key=lambda i: i.width * i.height, reverse=True)
        elif key == "aspect":
            self._images.sort(key=lambda i: i.aspect_ratio, reverse=True)
        elif key == "source":
            self._images.sort(key=lambda i: i.source)
        else:
            self._images.sort(key=lambda i: i.path.name)

        self._populate()

        # Restaurar seleção prévia
        for i in range(self.count()):
            it = self.item(i)
            info = it.data(Qt.ItemDataRole.UserRole)
            if info.path in selected_paths:
                it.setSelected(True)


# ── Preview ───────────────────────────────────────────────────────────────────

class PreviewDialog(QDialog):
    """Preview em tela cheia com navegação ← / →."""

    def __init__(
        self,
        info: ImageInfo,
        all_images: list[ImageInfo],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._images  = all_images
        self._current = all_images.index(info) if info in all_images else 0

        self.setWindowTitle("Preview")
        self.setModal(True)
        self.resize(1280, 800)
        self.setStyleSheet("background-color:#0d0d1a; color:#e0e0e0;")

        self._img_lbl  = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setMinimumSize(900, 650)
        self._img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._info_lbl = QLabel()
        self._info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_lbl.setStyleSheet("color:#888; font-size:11px; padding:4px;")

        def _nav_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName("preview_nav")
            b.setStyleSheet("""
                QPushButton#preview_nav {
                    background:#0f3460; color:#e0e0e0;
                    border:1px solid #2a5a8c; border-radius:4px;
                    padding:6px 18px; font-size:13px;
                }
                QPushButton#preview_nav:hover { background:#1a4a7a; }
            """)
            return b

        prev_btn  = _nav_btn("← Anterior")
        next_btn  = _nav_btn("Próxima →")
        close_btn = _nav_btn("✕ Fechar")

        prev_btn.clicked.connect(self._prev)
        next_btn.clicked.connect(self._next)
        close_btn.clicked.connect(self.accept)

        nav = QHBoxLayout()
        nav.addWidget(prev_btn)
        nav.addStretch()
        nav.addWidget(self._info_lbl)
        nav.addStretch()
        nav.addWidget(next_btn)
        nav.addSpacing(16)
        nav.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._img_lbl, 1)
        root.addLayout(nav)

        QShortcut(QKeySequence(Qt.Key.Key_Left),  self, self._prev)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._next)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.accept)

        self._load()

    def _load(self) -> None:
        info = self._images[self._current]
        try:
            from PIL import Image
            avail_w = max(self._img_lbl.width(),  900) - 16
            avail_h = max(self._img_lbl.height(), 640) - 16
            with Image.open(info.path) as im:
                if im.mode != "RGB":
                    im = im.convert("RGB")
                im.thumbnail((avail_w, avail_h), Image.LANCZOS)
                raw = im.tobytes("raw", "RGB")
                qi  = QImage(raw, im.width, im.height, im.width * 3,
                             QImage.Format.Format_RGB888)
                px  = QPixmap.fromImage(qi.copy())
        except Exception:
            px = QPixmap(900, 640)
            px.fill(QColor(20, 40, 80))
        self._img_lbl.setPixmap(px)
        self._info_lbl.setText(
            f"{info.path.name}   ·   {info.resolution}   "
            f"({self._current + 1} / {len(self._images)})"
        )

    def _prev(self) -> None:
        self._current = (self._current - 1) % len(self._images)
        self._load()

    def _next(self) -> None:
        self._current = (self._current + 1) % len(self._images)
        self._load()


# ── Barra lateral ─────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    sort_changed    = Signal(str)
    select_all_req  = Signal()
    select_none_req = Signal()
    process_req     = Signal()
    save_exit_req   = Signal()

    def __init__(self, monitors: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._monitors = monitors
        self.setFixedWidth(270)
        self.setStyleSheet("background-color:#12122a;")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 14, 12, 14)

        # ── Estatísticas ──────────────────────────────────────────────────────
        stats = QGroupBox("Estatísticas")
        sg    = QVBoxLayout(stats)
        sg.setSpacing(4)
        self._total_lbl = self._stat_row(sg, "Total")
        self._sel_lbl   = self._stat_row(sg, "Selecionadas")

        hover_title = QLabel("Sob o cursor:")
        hover_title.setStyleSheet("color:#555; font-size:10px; margin-top:4px;")
        self._hover_lbl = QLabel("—")
        self._hover_lbl.setWordWrap(True)
        self._hover_lbl.setStyleSheet("color:#7a9cc0; font-size:10px; padding:2px 0;")
        sg.addWidget(hover_title)
        sg.addWidget(self._hover_lbl)
        root.addWidget(stats)

        # ── Ordenação ─────────────────────────────────────────────────────────
        sort_grp = QGroupBox("Ordenar por")
        sl       = QVBoxLayout(sort_grp)
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Nome", "Resolução (maior primeiro)",
                                   "Aspect Ratio", "Fonte"])
        self._sort_combo.currentIndexChanged.connect(self._emit_sort)
        sl.addWidget(self._sort_combo)
        root.addWidget(sort_grp)

        # ── Monitores ─────────────────────────────────────────────────────────
        mon_grp = QGroupBox("Exportar para")
        ml      = QVBoxLayout(mon_grp)
        self._mon_checks: list[QCheckBox] = []
        if monitors:
            for m in monitors:
                tag = " ★" if m.is_primary else ""
                label = f"{m.name.lstrip('\\\\.')} — {m.width}×{m.height}{tag}"
                cb = QCheckBox(label)
                cb.setChecked(True)
                ml.addWidget(cb)
                self._mon_checks.append(cb)
        else:
            ml.addWidget(QLabel("Nenhum monitor detectado.",
                                styleSheet="color:#666; font-size:11px;"))
        root.addWidget(mon_grp)

        # ── Seleção rápida ────────────────────────────────────────────────────
        sel_grp = QGroupBox("Seleção rápida")
        sel_row = QHBoxLayout(sel_grp)
        btn_all  = QPushButton("Todos")
        btn_none = QPushButton("Nenhum")
        btn_all.clicked.connect(self.select_all_req)
        btn_none.clicked.connect(self.select_none_req)
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        root.addWidget(sel_grp)

        root.addStretch()

        # ── Atalhos ───────────────────────────────────────────────────────────
        hint = QLabel("Shift+clique: intervalo   Ctrl+A: tudo")
        hint.setStyleSheet("color:#444; font-size:9px;")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        # ── Botões principais ─────────────────────────────────────────────────
        self._process_btn = QPushButton("▶  Processar selecionadas")
        self._process_btn.setObjectName("process_btn")
        self._process_btn.setMinimumHeight(46)
        self._process_btn.clicked.connect(self.process_req)
        root.addWidget(self._process_btn)

        save_btn = QPushButton("💾  Salvar seleção e sair")
        save_btn.clicked.connect(self.save_exit_req)
        root.addWidget(save_btn)

    @staticmethod
    def _stat_row(parent_layout: QVBoxLayout, label: str) -> QLabel:
        row = QHBoxLayout()
        lbl = QLabel(label + ":")
        lbl.setStyleSheet("color:#888; font-size:11px;")
        val = QLabel("0")
        val.setStyleSheet("color:#4fc3f7; font-size:18px; font-weight:bold;")
        row.addWidget(lbl)
        row.addWidget(val)
        row.addStretch()
        parent_layout.addLayout(row)
        return val

    def update_stats(self, total: int, selected: int) -> None:
        self._total_lbl.setText(str(total))
        self._sel_lbl.setText(str(selected))

    def update_hover(self, info: ImageInfo | None) -> None:
        if info:
            self._hover_lbl.setText(f"{info.path.name}\n{info.resolution}")
        else:
            self._hover_lbl.setText("—")

    def get_selected_monitors(self) -> list:
        return [m for m, cb in zip(self._monitors, self._mon_checks) if cb.isChecked()]

    def _emit_sort(self, index: int) -> None:
        keys = ["name", "resolution", "aspect", "source"]
        self.sort_changed.emit(keys[index])


# ── Janela principal ──────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, images: list[ImageInfo]) -> None:
        super().__init__()
        self._images = images
        self._result: dict | None = None

        self.setWindowTitle(f"WallpaperForge  —  {len(images)} imagem(ns)")
        self.setMinimumSize(1050, 680)
        self.resize(1440, 880)
        self.setStyleSheet(DARK_CSS)

        from wallpaperforge.monitors import load_monitors
        monitors = load_monitors()

        # ── Widgets principais ────────────────────────────────────────────────
        self._grid    = ImageGridWidget(images)
        self._sidebar = Sidebar(monitors)

        self._grid.hover_changed.connect(self._sidebar.update_hover)
        self._grid.selection_count.connect(
            lambda n: self._sidebar.update_stats(len(images), n)
        )
        self._sidebar.sort_changed.connect(self._grid.sort_images)
        self._sidebar.select_all_req.connect(self._grid.select_all)
        self._sidebar.select_none_req.connect(self._grid.select_none)
        self._sidebar.process_req.connect(self._on_process)
        self._sidebar.save_exit_req.connect(self._on_save_exit)
        self._sidebar.update_stats(len(images), 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._grid)
        splitter.addWidget(self._sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self.setCentralWidget(splitter)

        # ── Atalhos globais ───────────────────────────────────────────────────
        QShortcut(QKeySequence.StandardKey.SelectAll, self, self._grid.select_all)
        QShortcut(QKeySequence(Qt.Key.Key_Escape),    self, self._grid.select_none)

        # ── Estado vazio ──────────────────────────────────────────────────────
        if not images:
            empty = QLabel(
                "Nenhuma imagem encontrada em work/filtered/ ou work/raw/\n\n"
                "Execute primeiro:\n"
                "  python -m wallpaperforge scrape --query 'nome da obra'",
                alignment=Qt.AlignmentFlag.AlignCenter,
            )
            empty.setStyleSheet("color:#445; font-size:14px; padding:60px;")
            self.setCentralWidget(empty)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_process(self) -> None:
        selected = self._grid.get_selected()
        if not selected:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem selecionada.")
            return
        monitors = self._sidebar.get_selected_monitors()
        self._result = self._persist(selected, monitors)
        self.close()

    def _on_save_exit(self) -> None:
        selected = self._grid.get_selected()
        monitors = self._sidebar.get_selected_monitors()
        self._persist(selected, monitors)
        QMessageBox.information(
            self, "Salvo",
            f"Seleção salva em work/selection.json\n{len(selected)} imagem(ns).",
        )
        self.close()

    def _persist(self, selected: list[ImageInfo], monitors: list) -> dict:
        SELECTION_JSON.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "images":   [str(i.path) for i in selected],
            "monitors": [m.name for m in monitors],
        }
        SELECTION_JSON.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("Seleção persistida: %d imagem(ns) → %s", len(selected), SELECTION_JSON)
        return payload

    def get_result(self) -> dict | None:
        return self._result


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_select(no_ui: bool = False) -> dict | None:
    """Abre a interface de seleção ou processa em modo headless (--no-ui)."""
    images = _find_images([FILTERED_DIR, RAW_DIR])

    if not images:
        log.warning(
            "Nenhuma imagem em %s ou %s — execute 'scrape' primeiro.",
            FILTERED_DIR, RAW_DIR,
        )

    if no_ui:
        log.info("Modo headless: selecionando todas as %d imagens.", len(images))
        from wallpaperforge.monitors import load_monitors
        monitors = load_monitors()
        payload  = {
            "images":   [str(i.path) for i in images],
            "monitors": [m.name for m in monitors],
        }
        SELECTION_JSON.parent.mkdir(parents=True, exist_ok=True)
        SELECTION_JSON.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return payload

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(images)
    win.show()
    app.exec()
    return win.get_result()
