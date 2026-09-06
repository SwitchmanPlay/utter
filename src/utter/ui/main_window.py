"""Main window: text pad + voice controls."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from utter import APP_NAME, REPO_URL, __version__
from utter.models.registry import MODELS, ModelSpec, get_model, installed_models
from utter.settings import Settings
from utter.tts import speaker as spk

LANGUAGE_LABELS = {
    "auto": "Auto-detect",
    "en": "English",
    "de": "Deutsch",
    "uk": "Українська",
    "ru": "Русский",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pl": "Polski",
    "pt": "Português",
    "nl": "Nederlands",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
}


class MainWindow(QMainWindow):
    speak_requested = Signal(str)  # text from the pad
    read_clipboard_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    save_wav_requested = Signal(str, str)  # text, path
    settings_changed = Signal()  # model / voice / speed / language changed in the UI
    open_settings_requested = Signal(str)  # tab name
    quit_requested = Signal()

    def __init__(self, settings: Settings, speaker: spk.Speaker, icon: QIcon):
        super().__init__()
        self.settings = settings
        self.speaker = speaker
        self._force_quit = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(560, 460)
        self._build_menu()
        self._build_ui()
        self._restore_geometry()
        self._wire_speaker()
        self.refresh_models()

    # ---- construction ------------------------------------------------------
    def _build_menu(self) -> None:
        bar = self.menuBar()
        m_file = bar.addMenu("&File")
        a_open = QAction("Open text file…", self)
        a_open.setShortcut(QKeySequence.StandardKey.Open)
        a_open.triggered.connect(self._open_file)
        a_save = QAction("Save as WAV…", self)
        a_save.setShortcut(QKeySequence("Ctrl+S"))
        a_save.triggered.connect(self._save_wav)
        a_quit = QAction("Quit", self)
        a_quit.setShortcut(QKeySequence("Ctrl+Q"))
        a_quit.triggered.connect(self.quit_requested.emit)
        m_file.addActions([a_open, a_save])
        m_file.addSeparator()
        m_file.addAction(a_quit)

        m_tools = bar.addMenu("&Tools")
        a_models = QAction("Models…", self)
        a_models.triggered.connect(lambda: self.open_settings_requested.emit("models"))
        a_settings = QAction("Settings…", self)
        a_settings.setShortcut(QKeySequence("Ctrl+,"))
        a_settings.triggered.connect(lambda: self.open_settings_requested.emit("general"))
        m_tools.addActions([a_models, a_settings])

        m_help = bar.addMenu("&Help")
        a_about = QAction("About Utter", self)
        a_about.triggered.connect(self._about)
        a_repo = QAction("GitHub", self)
        a_repo.triggered.connect(self._open_repo)
        m_help.addActions([a_repo, a_about])

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 8)
        outer.setSpacing(10)

        # header row: title + model/voice/lang combos
        header = QHBoxLayout()
        title = QLabel(APP_NAME, objectName="title")
        header.addWidget(title)
        header.addStretch(1)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        self.model_combo.setToolTip("TTS model. Install more under Tools › Models.")
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(150)
        self.voice_combo.setToolTip("Voice / speaker")
        self.lang_combo = QComboBox()
        self.lang_combo.setToolTip("Language sent to the model. Auto = detect per sentence.")
        for code, label in LANGUAGE_LABELS.items():
            self.lang_combo.addItem(label, code)
        header.addWidget(self.model_combo)
        header.addWidget(self.voice_combo)
        header.addWidget(self.lang_combo)
        outer.addLayout(header)

        # text pad
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText(
            "Paste or type anything here and press Speak (F5).\n\n"
            f"Or select text in any app and press {self.settings.hotkeys.read_selection} — "
            "Utter reads it out without you switching windows."
        )
        self.text.setPlainText(self.settings.last_text)
        self.text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer.addWidget(self.text, 1)

        # speed row
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed", objectName="muted"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setSingleStep(5)
        self.speed_slider.setValue(int(round(self.settings.speed * 100)))
        self.speed_label = QLabel(f"{self.settings.speed:.2f}×", objectName="muted")
        self.speed_label.setMinimumWidth(48)
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        self.words_label = QLabel("", objectName="muted")
        speed_row.addSpacing(16)
        speed_row.addWidget(self.words_label)
        outer.addLayout(speed_row)

        # buttons
        btns = QHBoxLayout()
        self.btn_speak = QPushButton("▶  Speak", objectName="primary")
        self.btn_speak.setShortcut(QKeySequence("F5"))
        self.btn_speak.setToolTip("Speak the text above (F5)")
        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setEnabled(False)
        self.btn_stop = QPushButton("■  Stop", objectName="danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setShortcut(QKeySequence("Esc"))
        self.btn_clip = QPushButton("📋  Read clipboard")
        self.btn_clear = QPushButton("Clear", objectName="flat")
        btns.addWidget(self.btn_speak)
        btns.addWidget(self.btn_pause)
        btns.addWidget(self.btn_stop)
        btns.addSpacing(12)
        btns.addWidget(self.btn_clip)
        btns.addStretch(1)
        btns.addWidget(self.btn_clear)
        outer.addLayout(btns)

        # progress + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        outer.addWidget(self.progress)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("Ready", objectName="status")
        self.stats_label = QLabel("", objectName="status")
        self.status.addWidget(self.status_label, 1)
        self.status.addPermanentWidget(self.stats_label)

        # signals
        self.btn_speak.clicked.connect(self._speak_pad)
        self.btn_pause.clicked.connect(self.pause_requested.emit)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        self.btn_clip.clicked.connect(self.read_clipboard_requested.emit)
        self.btn_clear.clicked.connect(self.text.clear)
        self.text.textChanged.connect(self._update_word_count)
        self.speed_slider.valueChanged.connect(self._speed_changed)
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        self.voice_combo.currentIndexChanged.connect(self._voice_changed)
        self.lang_combo.currentIndexChanged.connect(self._lang_changed)
        self._update_word_count()

    def _wire_speaker(self) -> None:
        self.speaker.state_changed.connect(self._on_state)
        self.speaker.progress.connect(self._on_progress)
        self.speaker.stats.connect(self.stats_label.setText)
        self.speaker.error.connect(self.show_error)

    # ---- model / voice combos --------------------------------------------
    def refresh_models(self) -> None:
        """Rebuild the model combo from what is installed. Called after downloads."""
        self._syncing = True
        try:
            self.model_combo.clear()
            installed = installed_models()
            for m in installed:
                self.model_combo.addItem(m.name, m.id)
            if not installed:
                self.model_combo.addItem("No model installed — open Tools › Models", "")
                self.btn_speak.setEnabled(False)
                self.btn_clip.setEnabled(False)
            else:
                self.btn_speak.setEnabled(True)
                self.btn_clip.setEnabled(True)
                idx = self.model_combo.findData(self.settings.model_id)
                if idx < 0:
                    idx = 0
                    self.settings.model_id = installed[0].id
                self.model_combo.setCurrentIndex(idx)
            self._rebuild_voices()
            li = self.lang_combo.findData(self.settings.language)
            self.lang_combo.setCurrentIndex(li if li >= 0 else 0)
        finally:
            self._syncing = False

    def current_model(self) -> ModelSpec | None:
        return get_model(self.model_combo.currentData() or "")

    def _rebuild_voices(self) -> None:
        spec = self.current_model()
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        if spec:
            for i, name in enumerate(spec.voice_names()):
                self.voice_combo.addItem(name, i)
            sid = min(self.settings.speaker_id, max(spec.num_speakers - 1, 0))
            self.voice_combo.setCurrentIndex(sid)
            self.lang_combo.setEnabled(spec.supports_lang_tag)
            self.lang_combo.setToolTip(
                "Language sent to the model. Auto = detect per sentence."
                if spec.supports_lang_tag
                else f"This model is fixed to: {', '.join(spec.languages)}"
            )
        self.voice_combo.blockSignals(False)

    def _model_changed(self, _idx: int) -> None:
        if getattr(self, "_syncing", False):
            return
        spec = self.current_model()
        if spec is None:
            return
        self.settings.model_id = spec.id
        self.settings.speaker_id = 0
        self._rebuild_voices()
        self.settings_changed.emit()

    def _voice_changed(self, idx: int) -> None:
        if getattr(self, "_syncing", False) or idx < 0:
            return
        self.settings.speaker_id = int(self.voice_combo.currentData() or 0)
        self.settings_changed.emit()

    def _lang_changed(self, _idx: int) -> None:
        if getattr(self, "_syncing", False):
            return
        self.settings.language = self.lang_combo.currentData() or "auto"
        self.settings_changed.emit()

    def _speed_changed(self, value: int) -> None:
        self.settings.speed = value / 100.0
        self.speed_label.setText(f"{self.settings.speed:.2f}×")
        self.settings_changed.emit()

    # ---- actions --------------------------------------------------------
    def _speak_pad(self) -> None:
        text = self.text.toPlainText()
        cursor = self.text.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace("\u2029", "\n")
        if not text.strip():
            self.set_status("Nothing to read — type or paste some text first.")
            return
        self.speak_requested.emit(text)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open text file", "", "Text files (*.txt *.md);;All files (*)")
        if path:
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    self.text.setPlainText(fh.read())
            except OSError as exc:
                self.show_error(str(exc))

    def _save_wav(self) -> None:
        text = self.text.toPlainText().strip()
        if not text:
            self.set_status("Nothing to save — type or paste some text first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save speech as WAV", "utter.wav", "WAV audio (*.wav)")
        if path:
            self.save_wav_requested.emit(text, path)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br>"
            "Handy, but for text-to-speech. Fully offline, runs on your CPU.<br><br>"
            "Engines: Supertonic 3, Kokoro, Piper via sherpa-onnx.<br>"
            f"<a href='{REPO_URL}'>{REPO_URL}</a>",
        )

    def _open_repo(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(REPO_URL))

    # ---- state from speaker ----------------------------------------------
    def _on_state(self, state: str) -> None:
        speaking = state in (spk.STATE_SPEAKING, spk.STATE_PAUSED)
        self.btn_pause.setEnabled(speaking)
        self.btn_stop.setEnabled(speaking or state == spk.STATE_LOADING)
        self.btn_pause.setText("▶  Resume" if state == spk.STATE_PAUSED else "⏸  Pause")
        if state == spk.STATE_LOADING:
            self.set_status("Loading model…")
            self.progress.setRange(0, 0)  # busy indicator
        elif state == spk.STATE_SPEAKING:
            self.set_status("Speaking")
        elif state == spk.STATE_PAUSED:
            self.set_status("Paused")
        else:
            self.set_status("Ready")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    def _on_progress(self, idx: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(idx)
        self.set_status(f"Speaking  ·  {idx}/{total}")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def show_error(self, message: str) -> None:
        self.set_status("Error")
        QMessageBox.warning(self, APP_NAME, message)

    def _update_word_count(self) -> None:
        n = len(self.text.toPlainText().split())
        self.words_label.setText(f"{n} words" if n != 1 else "1 word")

    # ---- window lifecycle -------------------------------------------------
    def _restore_geometry(self) -> None:
        if self.settings.window_geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(self.settings.window_geometry.encode()))
                return
            except Exception:
                pass
        self.resize(720, 560)

    def persist(self) -> None:
        self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        self.settings.last_text = self.text.toPlainText()[:20000]

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.text.setFocus()

    def force_quit(self) -> None:
        self._force_quit = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.persist()
        if self.settings.close_to_tray and not self._force_quit:
            event.ignore()
            self.hide()
            return
        event.accept()
