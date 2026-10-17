"""PRIMETONE STEMS v0.3 — tabs, offline model manager, stem mixer."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QSlider,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from primetone_stems import paths
from primetone_stems.models import MODELS
from primetone_stems.worker import FetchWorker, SeparationWorker

try:
    from primetone_stems.player import StemPlayer
    PLAYER_ERROR = None
except Exception as exc:  # missing sounddevice/PortAudio/soundfile
    StemPlayer = None
    PLAYER_ERROR = str(exc)

APP_NAME = "PRIMETONE STEMS"
SUPPORTED = "Audio files (*.wav *.mp3 *.flac *.m4a *.ogg *.aiff *.aif);;All files (*)"

MODE_OPTIONS = [
    ("All stems", []),
    ("Vocals + instrumental (karaoke)", ["--two-stems", "vocals"]),
    ("Drums + everything else", ["--two-stems", "drums"]),
    ("Bass + everything else", ["--two-stems", "bass"]),
]
QUALITY_OPTIONS = [
    ("Fast", ["--shifts", "0"]),
    ("Standard", []),
    ("High (slower)", ["--shifts", "2"]),
]
DEVICE_OPTIONS = [
    ("Automatic", []),
    ("CPU", ["-d", "cpu"]),
    ("NVIDIA GPU (CUDA)", ["-d", "cuda"]),
    ("Apple GPU (MPS)", ["-d", "mps"]),
]
STEM_COLORS = {
    "vocals": "#f0c778", "drums": "#6ec1e4", "bass": "#9b8cff", "other": "#7fd4a0",
    "guitar": "#ff9e6b", "piano": "#e48ad8", "no_vocals": "#9aa0a6",
}

STYLE = """
QMainWindow, QWidget { background: #111214; color: #ececec; font-family: Inter, "Segoe UI", Arial, sans-serif; font-size: 13px; }
QLabel, QSlider { background: transparent; }
QLabel#brandTitle { font-size: 27px; font-weight: 800; letter-spacing: 1px; color: #f0c778; }
QLabel#subtitle { color: #92949a; font-size: 10px; letter-spacing: 1.3px; }
QLabel#status { color: #f0c778; border: 1px solid #594a2b; border-radius: 8px; padding: 7px 10px; font-weight: 700; }
QTabWidget::pane { border: 0; top: 8px; }
QTabBar::tab { background: transparent; color: #92949a; padding: 10px 24px; font-weight: 800; letter-spacing: 1.2px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #f0c778; border-bottom: 2px solid #f0c778; }
QTabBar::tab:hover { color: #ececec; }
QFrame#panel { background: #1b1c20; border: 1px solid #34353a; border-radius: 13px; }
QFrame#dropZone { background: #16171a; border: 2px dashed #4a4b52; border-radius: 14px; }
QFrame#dropZone:hover { border-color: #d6ad61; }
QLabel#dropTitle { font-size: 19px; font-weight: 700; }
QLabel#dim { color: #a0a1a6; font-size: 11px; }
QLabel#cardTitle { font-size: 15px; font-weight: 700; }
QLabel#sectionLabel { color: #f0c778; font-size: 11px; font-weight: 800; letter-spacing: 1.2px; }
QLineEdit, QComboBox, QTextEdit { background: #151619; border: 1px solid #3a3b40; border-radius: 7px; padding: 8px; selection-background-color: #80652e; }
QComboBox QAbstractItemView { background: #1b1c20; selection-background-color: #80652e; }
QPushButton { background: #2b2c31; border: 1px solid #44454b; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { border-color: #d6ad61; }
QPushButton:disabled { color: #777; background: #202125; }
QPushButton#primaryButton { background: #d5ad62; color: #16130d; border: 0; font-size: 14px; padding: 13px; font-weight: 800; }
QPushButton#primaryButton:hover { background: #e7c681; }
QPushButton#primaryButton:disabled { background: #5a4d31; color: #222; }
QPushButton#soloButton:checked { background: #d5ad62; color: #16130d; border-color: #d5ad62; }
QPushButton#muteButton:checked { background: #a8403f; color: #fff; border-color: #a8403f; }
QProgressBar { border: 1px solid #34353a; background: #1b1c20; border-radius: 5px; height: 12px; text-align: center; }
QProgressBar::chunk { background: #d5ad62; border-radius: 4px; }
QSlider::groove:horizontal { height: 6px; background: #34353a; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #d5ad62; border-radius: 3px; }
QSlider::handle:horizontal { background: #f0c778; width: 14px; margin: -5px 0; border-radius: 7px; }
"""


def default_output_dir() -> Path:
    return Path.home() / "Music" / "PRIMETONE STEMS"


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


class DropZone(QFrame):
    def __init__(self, on_click) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 28, 20, 28)
        self.title = QLabel("Drop an audio file here")
        self.title.setObjectName("dropTitle")
        self.hint = QLabel("or click to browse  •  WAV · MP3 · FLAC · M4A · OGG · AIFF")
        self.hint.setObjectName("dim")
        for w in (self.title, self.hint):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)

    def set_file(self, name: str) -> None:
        self.title.setText(name)
        self.hint.setText("Click to choose a different file")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._on_click()


class StemRow(QWidget):
    def __init__(self, name: str, player) -> None:
        super().__init__()
        color = STEM_COLORS.get(name, "#cfd2d8")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        label = QLabel(name.replace("_", " ").upper())
        label.setStyleSheet(f"color: {color}; font-weight: 800; letter-spacing: 1px;")
        label.setFixedWidth(100)
        solo, mute = QPushButton("S"), QPushButton("M")
        solo.setObjectName("soloButton")
        mute.setObjectName("muteButton")
        for b in (solo, mute):
            b.setCheckable(True)
            b.setFixedWidth(42)
        vol = QSlider(Qt.Orientation.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(100)
        vol.setStyleSheet(f"QSlider::sub-page:horizontal {{ background: {color}; border-radius: 3px; }}")
        pct = QLabel("100%")
        pct.setFixedWidth(44)
        solo.toggled.connect(lambda on, n=name: player.set_solo(n, on))
        mute.toggled.connect(lambda on, n=name: player.set_mute(n, on))

        def on_vol(v: int, n=name) -> None:
            player.set_gain(n, v / 100)
            pct.setText(f"{v}%")

        vol.valueChanged.connect(on_vol)
        for w in (label, solo, mute):
            lay.addWidget(w)
        lay.addWidget(vol, 1)
        lay.addWidget(pct)


class ModelCard(QFrame):
    def __init__(self, info: dict, on_fetch) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.info = info
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        text = QVBoxLayout()
        title = QLabel(info["label"])
        title.setObjectName("cardTitle")
        desc = QLabel(info["description"])
        desc.setObjectName("dim")
        desc.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(desc)
        self.status = QLabel()
        self.status.setFixedWidth(140)
        self.button = QPushButton()
        self.button.setFixedWidth(130)
        self.button.clicked.connect(lambda: on_fetch(info["id"]))
        lay.addLayout(text, 1)
        lay.addWidget(self.status)
        lay.addWidget(self.button)
        self.refresh()

    def refresh(self) -> None:
        ok = paths.is_installed(self.info["id"])
        self.status.setText("● INSTALLED" if ok else "○ NOT INSTALLED")
        self.status.setStyleSheet(f"color: {'#7fd4a0' if ok else '#e6a15a'}; font-weight: 800;")
        self.button.setText("Verify / Update" if ok else "Download")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(980, 860)
        self.setAcceptDrops(True)
        self.audio_path: Path | None = None
        self.stems_folder: Path | None = None
        self.worker: SeparationWorker | None = None
        self.fetch_worker: FetchWorker | None = None
        self.current_model = "htdemucs"
        self.player = StemPlayer() if StemPlayer else None
        self.seeking = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(26, 22, 26, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        subtitle = QLabel("AI MUSIC SEPARATION STUDIO  •  100% LOCAL")
        subtitle.setObjectName("subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.status = QLabel("READY")
        self.status.setObjectName("status")
        header.addWidget(self.status, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_separate_tab(), "SEPARATE")
        self.tabs.addTab(self._build_mixer_tab(), "MIXER")
        self.tabs.addTab(self._build_models_tab(), "MODELS")

        self.setStyleSheet(STYLE)
        if PLAYER_ERROR:
            self.log.append(f"Playback disabled: {PLAYER_ERROR}")
        self.refresh_model_combo()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    # ---- tab builders ----------------------------------------------------
    def _build_separate_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.drop = DropZone(self.choose_audio)
        lay.addWidget(self.drop)

        panel = QFrame()
        panel.setObjectName("panel")
        grid = QGridLayout(panel)
        grid.setContentsMargins(20, 16, 20, 16)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        self.output_edit = QLineEdit(str(default_output_dir()))
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_output)
        self.model_combo = QComboBox()
        self.mode_combo, self.quality_combo, self.device_combo = QComboBox(), QComboBox(), QComboBox()
        for combo, options in ((self.mode_combo, MODE_OPTIONS), (self.quality_combo, QUALITY_OPTIONS),
                               (self.device_combo, DEVICE_OPTIONS)):
            combo.addItems([name for name, _ in options])
        self.quality_combo.setCurrentIndex(1)
        rows = [("Output folder", self.output_edit, browse), ("Model", self.model_combo, None),
                ("Mode", self.mode_combo, None), ("Quality", self.quality_combo, None),
                ("Device", self.device_combo, None)]
        for r, (text, widget, extra) in enumerate(rows):
            grid.addWidget(QLabel(text), r, 0)
            grid.addWidget(widget, r, 1)
            if extra:
                grid.addWidget(extra, r, 2)
        lay.addWidget(panel)

        run_row = QHBoxLayout()
        self.start_btn = QPushButton("Separate stems")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self.start_separation)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_separation)
        run_row.addWidget(self.start_btn, 1)
        run_row.addWidget(self.cancel_btn)
        lay.addLayout(run_row)
        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        sec = QLabel("PROCESS LOG")
        sec.setObjectName("sectionLabel")
        lay.addWidget(sec)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Choose an audio file, then press Separate stems.")
        lay.addWidget(self.log, 1)
        return page

    def _build_mixer_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(20, 16, 20, 16)
        pl.setSpacing(12)
        top = QHBoxLayout()
        lbl = QLabel("STEMS")
        lbl.setObjectName("sectionLabel")
        top.addWidget(lbl)
        top.addStretch()
        self.load_btn = QPushButton("Load stems folder…")
        self.load_btn.clicked.connect(self.choose_stems_folder)
        self.open_btn = QPushButton("Open folder")
        self.open_btn.clicked.connect(self.open_stems_folder)
        self.export_btn = QPushButton("Export mix…")
        self.export_btn.clicked.connect(self.export_mix)
        for b in (self.load_btn, self.open_btn, self.export_btn):
            top.addWidget(b)
        pl.addLayout(top)
        self.mixer_hint = QLabel("Separate a song, or load a stems folder, to start mixing.\n"
                                 "S = solo, M = mute, sliders = volume. Export mix saves what you hear.")
        self.mixer_hint.setObjectName("dim")
        pl.addWidget(self.mixer_hint)
        self.rows_host = QVBoxLayout()
        self.rows_host.setSpacing(10)
        pl.addLayout(self.rows_host)
        transport = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderPressed.connect(lambda: setattr(self, "seeking", True))
        self.seek.sliderReleased.connect(self.on_seek_released)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setFixedWidth(90)
        transport.addWidget(self.play_btn)
        transport.addWidget(self.stop_btn)
        transport.addWidget(self.seek, 1)
        transport.addWidget(self.time_label)
        pl.addLayout(transport)
        lay.addWidget(panel)
        lay.addStretch(1)
        self.set_player_enabled(False)
        if self.player is None:
            self.load_btn.setEnabled(False)
        return page

    def _build_models_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        note = QLabel(
            f"Models are stored in: {paths.models_dir()}\n"
            "The app only goes online when you press Download / Verify. Verify checks the files and fetches "
            "anything missing. New model versions arrive with new app versions."
        )
        note.setObjectName("dim")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.cards: list[ModelCard] = []
        for info in MODELS:
            card = ModelCard(info, self.fetch_model)
            self.cards.append(card)
            lay.addWidget(card)
        row = QHBoxLayout()
        import_btn = QPushButton("Import model files (.th)…")
        import_btn.clicked.connect(self.import_models)
        folder_btn = QPushButton("Open models folder")
        folder_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.models_dir()))))
        self.models_cancel = QPushButton("Cancel download")
        self.models_cancel.setEnabled(False)
        self.models_cancel.clicked.connect(self.cancel_fetch)
        for b in (import_btn, folder_btn, self.models_cancel):
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.models_progress = QProgressBar()
        lay.addWidget(self.models_progress)
        self.models_status = QLabel("")
        self.models_status.setObjectName("dim")
        lay.addWidget(self.models_status)
        lay.addStretch(1)
        return page

    # ---- helpers -----------------------------------------------------------
    def refresh_model_combo(self) -> None:
        current = self.model_combo.currentData()
        self.model_combo.clear()
        for m in MODELS:
            tag = "" if paths.is_installed(m["id"]) else "  (not installed)"
            self.model_combo.addItem(m["label"] + tag, m["id"])
        idx = self.model_combo.findData(current) if current else 0
        self.model_combo.setCurrentIndex(max(idx, 0))

    def refresh_models_ui(self) -> None:
        for card in self.cards:
            card.refresh()
        self.refresh_model_combo()

    def busy(self) -> bool:
        running = any(w is not None and w.isRunning() for w in (self.worker, self.fetch_worker))
        if running:
            QMessageBox.information(self, APP_NAME, "Another task is still running. Wait for it to finish or cancel it.")
        return running

    # ---- input -------------------------------------------------------------
    def set_audio(self, path: Path) -> None:
        self.audio_path = path
        self.drop.set_file(path.name)
        self.log.append(f"Selected: {path}")

    def choose_audio(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Choose audio", str(Path.home()), SUPPORTED)
        if name:
            self.set_audio(Path(name))

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not urls:
            return
        p = Path(urls[0])
        if p.is_dir():
            self.load_stems(p)
        else:
            self.set_audio(p)

    # ---- separation ----------------------------------------------------------
    def start_separation(self) -> None:
        if self.busy():
            return
        if not self.audio_path or not self.audio_path.exists():
            QMessageBox.warning(self, APP_NAME, "Choose a valid audio file first.")
            return
        text = self.output_edit.text().strip()
        if not text:
            QMessageBox.warning(self, APP_NAME, "Choose an output folder.")
            return
        model = self.model_combo.currentData()
        if not paths.is_installed(model):
            answer = QMessageBox.question(
                self, APP_NAME,
                f"The model '{model}' isn't installed yet.\n\nDownload it now? (Internet needed, one time.)\n"
                "Choose No to cancel; you can also install or import it from the Models tab.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        extra = (MODE_OPTIONS[self.mode_combo.currentIndex()][1]
                 + QUALITY_OPTIONS[self.quality_combo.currentIndex()][1]
                 + DEVICE_OPTIONS[self.device_combo.currentIndex()][1])
        if self.player:
            self.player.stop()
            self.play_btn.setText("▶ Play")
        self.current_model = model
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status.setText("PROCESSING")
        self.progress.setValue(0)
        self.log.append("\n--- Starting separation ---")
        self.worker = SeparationWorker(self.audio_path, Path(text).expanduser(), model, extra)
        self.worker.log_line.connect(self.log.append)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.succeeded.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.start()

    def cancel_separation(self) -> None:
        if self.worker and self.worker.isRunning():
            self.status.setText("CANCELLING")
            self.worker.cancel()

    def _finish_run(self, status: str) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status.setText(status)

    def on_success(self, folder: str) -> None:
        self._finish_run("COMPLETE")
        paths.mark_installed(self.current_model)
        self.refresh_models_ui()
        self.log.append(f"\nFinished. Stems saved in: {folder}")
        self.load_stems(Path(folder))
        self.tabs.setCurrentIndex(1)

    def on_failure(self, message: str) -> None:
        self._finish_run("ERROR")
        self.log.append("\nERROR: " + message)
        QMessageBox.critical(self, APP_NAME, message)

    def on_cancelled(self) -> None:
        self._finish_run("CANCELLED")
        self.progress.setValue(0)
        self.log.append("\nSeparation cancelled.")

    # ---- models ----------------------------------------------------------------
    def fetch_model(self, model_id: str) -> None:
        if self.busy():
            return
        self.models_progress.setValue(0)
        self.models_status.setText(f"Working on {model_id}…")
        self.status.setText("DOWNLOADING")
        self.models_cancel.setEnabled(True)
        for card in self.cards:
            card.button.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.fetch_worker = FetchWorker(model_id)
        self.fetch_worker.log_line.connect(self.log.append)
        self.fetch_worker.progress.connect(self.models_progress.setValue)
        self.fetch_worker.done.connect(self.on_fetch_done)
        self.fetch_worker.failed.connect(self.on_fetch_failed)
        self.fetch_worker.cancelled.connect(lambda: self._fetch_finished("Cancelled."))
        self.fetch_worker.start()

    def cancel_fetch(self) -> None:
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.cancel()

    def _fetch_finished(self, message: str) -> None:
        for card in self.cards:
            card.button.setEnabled(True)
        self.models_cancel.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.status.setText("READY")
        self.models_status.setText(message)
        self.refresh_models_ui()

    def on_fetch_done(self, model_id: str) -> None:
        self._fetch_finished(f"'{model_id}' is ready for offline use.")

    def on_fetch_failed(self, message: str) -> None:
        self._fetch_finished("Failed. See the log on the Separate tab.")
        QMessageBox.warning(self, APP_NAME, message)

    def import_models(self) -> None:
        cache = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
        start = str(cache if cache.exists() else Path.home())
        files, _ = QFileDialog.getOpenFileNames(self, "Choose model files (.th)", start,
                                                "Model files (*.th);;All files (*)")
        if not files:
            return
        dest = paths.checkpoints_dir()
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, dest / Path(f).name)
        self.log.append(f"Imported {len(files)} model file(s) into {dest}")
        QMessageBox.information(
            self, APP_NAME,
            f"Copied {len(files)} file(s).\n\nNow press Verify / Download on the matching model. "
            "If all of its files are present, nothing is downloaded.")

    # ---- stems / playback ---------------------------------------------------------
    def set_player_enabled(self, on: bool) -> None:
        for w in (self.play_btn, self.stop_btn, self.seek, self.export_btn, self.open_btn):
            w.setEnabled(on)

    def choose_stems_folder(self) -> None:
        start = self.output_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder containing stem .wav files", start)
        if folder:
            self.load_stems(Path(folder))

    def load_stems(self, folder: Path) -> None:
        if not self.player:
            QMessageBox.warning(self, APP_NAME, f"Playback unavailable: {PLAYER_ERROR}")
            return
        try:
            self.player.load(folder)
        except Exception as exc:  # noqa: BLE001
            self.log.append(f"Could not load stems: {exc}")
            QMessageBox.warning(self, APP_NAME, f"Could not load stems:\n{exc}")
            return
        self.stems_folder = folder
        while self.rows_host.count():
            item = self.rows_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name in self.player.names:
            self.rows_host.addWidget(StemRow(name, self.player))
        self.mixer_hint.setVisible(False)
        self.seek.setRange(0, int(self.player.duration * 1000))
        self.seek.setValue(0)
        self.play_btn.setText("▶ Play")
        self.set_player_enabled(True)
        self.log.append(f"Loaded {len(self.player.names)} stems from {folder}")

    def toggle_play(self) -> None:
        if not self.player or not self.player.loaded:
            return
        try:
            if self.player.is_playing:
                self.player.pause()
                self.play_btn.setText("▶ Play")
            else:
                self.player.play()
                self.play_btn.setText("❚❚ Pause")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, f"Audio output error:\n{exc}")

    def stop_playback(self) -> None:
        if self.player:
            self.player.stop()
            self.play_btn.setText("▶ Play")

    def on_seek_released(self) -> None:
        self.seeking = False
        if self.player and self.player.loaded:
            self.player.seek(self.seek.value() / 1000)

    def tick(self) -> None:
        p = self.player
        if not p or not p.loaded:
            return
        if p.ended:
            p.stop()
            self.play_btn.setText("▶ Play")
        if not self.seeking:
            self.seek.setValue(int(p.position * 1000))
        self.time_label.setText(f"{fmt_time(p.position)} / {fmt_time(p.duration)}")

    def open_stems_folder(self) -> None:
        if self.stems_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.stems_folder)))

    def export_mix(self) -> None:
        if not self.player or not self.player.loaded:
            return
        default = str((self.stems_folder or Path.home()) / "mix.wav")
        path, _ = QFileDialog.getSaveFileName(self, "Export current mix", default, "WAV (*.wav)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.player.export_mix(path)
            self.log.append(f"Exported mix (current solo/mute/volume): {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, f"Export failed:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def closeEvent(self, event) -> None:  # noqa: N802
        for w in (self.worker, self.fetch_worker):
            if w and w.isRunning():
                w.cancel()
                w.wait(5000)
        if self.player:
            self.player.close()
        event.accept()


def main() -> None:
    paths.configure_env()
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle and (Path(bundle) / "bin").is_dir():
        os.environ["PATH"] = str(Path(bundle) / "bin") + os.pathsep + os.environ.get("PATH", "")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
