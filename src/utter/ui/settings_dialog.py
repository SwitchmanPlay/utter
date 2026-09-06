"""Settings dialog: General / Hotkeys / Audio / Models."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utter.hotkeys import HotkeyParseError, qt_to_pynput
from utter.models.download import DownloadCancelled, delete_model, dir_size_mb, download_model
from utter.models.registry import MODELS, ModelSpec, is_installed
from utter.settings import Settings
from utter.tts.speaker import list_output_devices


# --------------------------------------------------------------------------- download worker


class _DownloadWorker(QObject):
    progress = Signal(int, int)
    done = Signal(str)  # model id
    failed = Signal(str, str)  # model id, message

    def __init__(self, spec: ModelSpec):
        super().__init__()
        self.spec = spec
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            download_model(self.spec, progress=self.progress.emit, cancel=self.cancel)
            self.done.emit(self.spec.id)
        except DownloadCancelled:
            self.failed.emit(self.spec.id, "cancelled")
        except Exception as exc:
            self.failed.emit(self.spec.id, f"{type(exc).__name__}: {exc}")


class ModelRow(QFrame):
    changed = Signal()
    preview = Signal(str)  # model id

    def __init__(self, spec: ModelSpec, parent=None):
        super().__init__(parent, objectName="card")
        self.spec = spec
        self._thread: QThread | None = None
        self._worker: _DownloadWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        top = QHBoxLayout()
        name = QLabel(f"<b>{spec.name}</b>" + ("  ⭐" if spec.recommended else ""))
        name.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(name, 1)
        self.size_label = QLabel(objectName="muted")
        top.addWidget(self.size_label)
        lay.addLayout(top)

        langs = ", ".join(spec.languages[:8]) + ("…" if len(spec.languages) > 8 else "")
        meta = QLabel(f"{spec.blurb}<br><span style='color:#8b90a0'>{langs}  ·  {spec.license}</span>")
        meta.setWordWrap(True)
        meta.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(meta)

        bottom = QHBoxLayout()
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(6)
        self.bar.hide()
        self.btn = QPushButton()
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setToolTip("Speak a short sample with this model")
        bottom.addWidget(self.bar, 1)
        bottom.addWidget(self.btn_preview)
        bottom.addWidget(self.btn)
        lay.addLayout(bottom)

        self.btn.clicked.connect(self._clicked)
        self.btn_preview.clicked.connect(lambda: self.preview.emit(self.spec.id))
        self.refresh()

    def refresh(self) -> None:
        installed = is_installed(self.spec)
        self.btn_preview.setEnabled(installed)
        if installed:
            self.btn.setText("Remove")
            self.btn.setObjectName("danger")
            self.size_label.setText(f"{dir_size_mb(self.spec.install_dir):.0f} MB on disk")
        else:
            self.btn.setText("Download")
            self.btn.setObjectName("primary")
            self.size_label.setText(f"~{self.spec.size_mb} MB")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

    def _clicked(self) -> None:
        if self._thread is not None:
            if self._worker:
                self._worker.cancel.set()
            return
        if is_installed(self.spec):
            if (
                QMessageBox.question(self, "Remove model", f"Delete {self.spec.name} from disk?")
                == QMessageBox.StandardButton.Yes
            ):
                delete_model(self.spec)
                self.refresh()
                self.changed.emit()
            return
        self._start_download()

    def _start_download(self) -> None:
        self._worker = _DownloadWorker(self.spec)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self.bar.setRange(0, 0)
        self.bar.show()
        self.btn.setText("Cancel")
        self.btn.setObjectName("")
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(done * 100 / total))
            self.size_label.setText(f"{done / 1048576:.0f} / {total / 1048576:.0f} MB")
        else:
            self.size_label.setText(f"{done / 1048576:.0f} MB…")

    def _finish_thread(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None
        self.bar.hide()

    def _on_done(self, _id: str) -> None:
        self._finish_thread()
        self.refresh()
        self.changed.emit()

    def _on_failed(self, _id: str, msg: str) -> None:
        self._finish_thread()
        self.refresh()
        if msg != "cancelled":
            QMessageBox.warning(self, "Download failed", msg)


# --------------------------------------------------------------------------- dialog


class SettingsDialog(QDialog):
    models_changed = Signal()
    preview_model = Signal(str)
    applied = Signal()

    def __init__(self, settings: Settings, parent=None, tab: str = "general"):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Utter — Settings")
        self.setMinimumSize(620, 520)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._general_tab(), "General")
        self.tabs.addTab(self._hotkeys_tab(), "Hotkeys")
        self.tabs.addTab(self._audio_tab(), "Audio")
        self.tabs.addTab(self._models_tab(), "Models")
        idx = {"general": 0, "hotkeys": 1, "audio": 2, "models": 3}.get(tab, 0)
        self.tabs.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)

        lay = QVBoxLayout(self)
        lay.addWidget(self.tabs, 1)
        lay.addWidget(buttons)

    # ---- tabs ------------------------------------------------------------
    def _general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        s = self.settings
        self.cb_autostart = QCheckBox("Launch Utter when I sign in to Windows")
        self.cb_autostart.setChecked(s.launch_at_login)
        self.cb_start_min = QCheckBox("Start minimized to the tray")
        self.cb_start_min.setChecked(s.start_minimized)
        self.cb_close_tray = QCheckBox("Closing the window keeps Utter running in the tray")
        self.cb_close_tray.setChecked(s.close_to_tray)
        self.cb_overlay = QCheckBox("Show the mini player near the cursor while speaking")
        self.cb_overlay.setChecked(s.show_overlay)
        self.cb_markdown = QCheckBox("Strip Markdown (##, **, `code`, links) before reading")
        self.cb_markdown.setChecked(s.strip_markdown)
        self.cb_numbers = QCheckBox("Read numbers, dates, prices and % as words in the sentence's language")
        self.cb_numbers.setChecked(s.verbalize_numbers)
        self.cb_numbers.setToolTip(
            "Turns “1 000 €”, “12.05.2026”, “3.5 %” or “10:30” into words before synthesis so the model\n"
            "cannot guess the wrong language for bare digits. Supports English, German, Ukrainian, Russian."
        )
        self.cmb_urls = QComboBox()
        for code, label in (("link", "say “link”"), ("skip", "skip them"), ("verbatim", "read them out")):
            self.cmb_urls.addItem(label, code)
        self.cmb_urls.setCurrentIndex(max(0, self.cmb_urls.findData(s.read_urls_as)))
        for cb in (
            self.cb_autostart, self.cb_start_min, self.cb_close_tray, self.cb_overlay,
            self.cb_markdown, self.cb_numbers,
        ):
            form.addRow(cb)
        form.addRow("URLs in text:", self.cmb_urls)

        self.sp_threads = QSpinBox()
        self.sp_threads.setRange(1, 16)
        self.sp_threads.setValue(s.num_threads)
        self.sp_threads.setToolTip("CPU threads for synthesis. 2–4 is plenty; more can make the UI stutter.")
        form.addRow("CPU threads:", self.sp_threads)

        self.sp_steps = QSpinBox()
        self.sp_steps.setRange(2, 32)
        self.sp_steps.setValue(s.num_steps)
        self.sp_steps.setToolTip(
            "Supertonic and Pocket TTS only. Fewer steps = faster, more = slightly higher quality. Default 8."
        )
        form.addRow("Quality steps:", self.sp_steps)
        return w

    def _hotkeys_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        hint = QLabel(
            "Global — they work in every app. Click a field and press the new combination. "
            "Leave empty to disable.",
            objectName="muted",
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        hk = self.settings.hotkeys
        self.hk_edits: dict[str, QKeySequenceEdit] = {}
        for attr, label in (
            ("read_selection", "Read selected text"),
            ("read_clipboard", "Read clipboard"),
            ("pause_resume", "Pause / resume"),
            ("stop", "Stop"),
            ("show_window", "Show / hide Utter"),
        ):
            edit = QKeySequenceEdit(QKeySequence(getattr(hk, attr)))
            if hasattr(edit, "setMaximumSequenceLength"):  # Qt >= 6.5
                edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True) if hasattr(edit, "setClearButtonEnabled") else None
            self.hk_edits[attr] = edit
            form.addRow(label + ":", edit)
        return w

    def _audio_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        self.cmb_device = QComboBox()
        self.cmb_device.addItem("System default", "")
        for name in list_output_devices():
            self.cmb_device.addItem(name, name)
        idx = self.cmb_device.findData(self.settings.output_device)
        self.cmb_device.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Output device:", self.cmb_device)

        row = QHBoxLayout()
        self.sl_volume = QSlider(Qt.Orientation.Horizontal)
        self.sl_volume.setRange(0, 150)
        self.sl_volume.setValue(int(round(self.settings.volume * 100)))
        self.lbl_volume = QLabel(f"{self.sl_volume.value()} %", objectName="muted")
        self.sl_volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v} %"))
        row.addWidget(self.sl_volume, 1)
        row.addWidget(self.lbl_volume)
        form.addRow("Volume:", row)

        # Voice cloning (Pocket TTS): optional reference WAV.
        ref_row = QHBoxLayout()
        self.ed_reference = QLineEdit(self.settings.reference_audio)
        self.ed_reference.setPlaceholderText("Optional: WAV of a voice to clone (Pocket TTS only)")
        self.ed_reference.setToolTip(
            "5–15 seconds of clean speech, 16-bit mono WAV. Leave empty to use the voice picked in the main window."
        )
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._pick_reference)
        btn_clear = QPushButton("Clear", objectName="flat")
        btn_clear.clicked.connect(lambda: self.ed_reference.setText(""))
        ref_row.addWidget(self.ed_reference, 1)
        ref_row.addWidget(btn_browse)
        ref_row.addWidget(btn_clear)
        form.addRow("Clone voice from:", ref_row)
        return w

    def _pick_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a reference voice", "", "WAV audio (*.wav)")
        if path:
            self.ed_reference.setText(path)

    def _models_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(objectName="root")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        intro = QLabel(
            "Models are downloaded once into your app-data folder and run 100% offline. "
            "Supertonic 3 is the recommended default for mixed English / German / Ukrainian / Russian.",
            objectName="muted",
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.model_rows: list[ModelRow] = []
        for spec in MODELS:
            row = ModelRow(spec)
            row.changed.connect(self.models_changed.emit)
            row.preview.connect(self.preview_model.emit)
            self.model_rows.append(row)
            lay.addWidget(row)
        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    # ---- apply -----------------------------------------------------------
    def _collect(self) -> str | None:
        """Write UI values into self.settings. Returns an error message or None."""
        s = self.settings
        s.launch_at_login = self.cb_autostart.isChecked()
        s.start_minimized = self.cb_start_min.isChecked()
        s.close_to_tray = self.cb_close_tray.isChecked()
        s.show_overlay = self.cb_overlay.isChecked()
        s.strip_markdown = self.cb_markdown.isChecked()
        s.verbalize_numbers = self.cb_numbers.isChecked()
        s.reference_audio = self.ed_reference.text().strip()
        s.read_urls_as = self.cmb_urls.currentData()
        s.num_threads = self.sp_threads.value()
        s.num_steps = self.sp_steps.value()
        s.output_device = self.cmb_device.currentData() or ""
        s.volume = self.sl_volume.value() / 100.0

        seen: dict[str, str] = {}
        for attr, edit in self.hk_edits.items():
            text = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
            if text:
                try:
                    py = qt_to_pynput(text)
                except HotkeyParseError as exc:
                    return f"Hotkey for “{attr.replace('_', ' ')}”: {exc}"
                if py in seen:
                    return f"“{text}” is assigned twice ({seen[py]} and {attr.replace('_', ' ')})."
                seen[py] = attr.replace("_", " ")
            setattr(s.hotkeys, attr, text)
        return None

    def _apply(self) -> bool:
        err = self._collect()
        if err:
            QMessageBox.warning(self, "Settings", err)
            return False
        self.settings.save()
        self.applied.emit()
        return True

    def _ok(self) -> None:
        if self._apply():
            self.accept()
