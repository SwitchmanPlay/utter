"""Application wiring: settings + speaker + hotkeys + windows + tray."""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from utter import APP_ID, APP_NAME, __version__
from utter.hotkeys import HotkeyManager, send_copy
from utter.models.registry import ModelSpec, default_model, get_model, installed_models
from utter.paths import app_data_dir, log_file, resource_path
from utter.settings import Settings
from utter.tts import speaker as spk
from utter.tts.engine import EngineCache
from utter.ui.main_window import MainWindow
from utter.ui.overlay import Overlay
from utter.ui.settings_dialog import SettingsDialog
from utter.ui.theme import QSS
from utter.ui.tray import Tray

log = logging.getLogger("utter")

SINGLE_INSTANCE_KEY = f"{APP_ID}-single-instance"
PREVIEW_TEXT = {
    "en": "Hi, this is Utter. I turn any text on your screen into speech, fully offline.",
    "de": "Hallo, hier ist Utter. Ich lese dir jeden Text vor, komplett offline.",
    "uk": "Привіт, це Utter. Я озвучую будь-який текст повністю офлайн.",
    "ru": "Привет, это Utter. Я озвучиваю любой текст полностью офлайн.",
}


class _HotkeyBridge(QObject):
    """pynput fires callbacks on its own thread; this hops them onto the Qt thread."""

    fired = Signal(str)


class UtterApp(QObject):
    _wav_done = Signal(str)  # emitted from the worker thread, delivered on the Qt thread
    _wav_failed = Signal(str)

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings.load()
        self.engines = EngineCache()
        self.speaker = spk.Speaker(self.engines, parent=self)
        self.icon = _load_icon()
        self.window = MainWindow(self.settings, self.speaker, self.icon)
        self.overlay = Overlay()
        self.tray = Tray(self.icon, parent=self)
        self.hotkeys = HotkeyManager()
        self._bridge = _HotkeyBridge()
        self._settings_dialog: SettingsDialog | None = None
        self._saved_clip: str | None = None
        self._wire()
        self.apply_hotkeys()
        self._apply_autostart()

        tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        if tray_ok:
            self.tray.show()
        if not (self.settings.start_minimized and tray_ok):
            self.window.show()

        spec = self.current_model()
        if spec is not None:
            QTimer.singleShot(300, lambda: self.speaker.preload(spec, self.settings))
        else:
            QTimer.singleShot(400, self._first_run)

    # ---- wiring ----------------------------------------------------------
    def _wire(self) -> None:
        w, t, o, s = self.window, self.tray, self.overlay, self.speaker
        w.speak_requested.connect(self.speak)
        w.read_clipboard_requested.connect(self.read_clipboard)
        w.pause_requested.connect(s.toggle_pause)
        w.stop_requested.connect(s.stop)
        w.save_wav_requested.connect(self.save_wav)
        w.settings_changed.connect(self._on_ui_settings_changed)
        w.open_settings_requested.connect(self.open_settings)
        w.quit_requested.connect(self.quit)

        t.show_window.connect(self.toggle_window)
        t.read_clipboard.connect(self.read_clipboard)
        t.pause_resume.connect(s.toggle_pause)
        t.stop.connect(s.stop)
        t.open_settings.connect(lambda: self.open_settings("general"))
        t.quit.connect(self.quit)

        o.pause_clicked.connect(s.toggle_pause)
        o.stop_clicked.connect(s.stop)
        o.open_clicked.connect(self.window.show_and_raise)

        s.state_changed.connect(t.on_state)
        s.state_changed.connect(o.on_state)
        s.progress.connect(o.on_progress)
        s.error.connect(self._on_error)

        self._bridge.fired.connect(self._on_hotkey)
        self._wav_done.connect(lambda p: self.window.set_status(f"Saved {os.path.basename(p)}"))
        self._wav_failed.connect(self.window.show_error)
        self.qapp.aboutToQuit.connect(self._shutdown)

    # ---- helpers ----------------------------------------------------------
    def current_model(self) -> ModelSpec | None:
        spec = get_model(self.settings.model_id)
        if spec is not None and spec in installed_models():
            return spec
        inst = installed_models()
        if inst:
            self.settings.model_id = inst[0].id
            return inst[0]
        return None

    def _first_run(self) -> None:
        self.window.show_and_raise()
        rec = default_model()
        box = QMessageBox(self.window)
        box.setWindowTitle(f"Welcome to {APP_NAME}")
        box.setText(
            f"<b>No voice model installed yet.</b><br><br>"
            f"Recommended: <b>{rec.name}</b> (~{rec.size_mb} MB, one-time download). "
            "It speaks English, German, Ukrainian, Russian and 27 more languages, fully offline."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Open).setText("Open model manager")
        if box.exec() == QMessageBox.StandardButton.Open:
            self.open_settings("models")

    # ---- speaking ---------------------------------------------------------
    def speak(self, text: str) -> None:
        spec = self.current_model()
        if spec is None:
            self._first_run()
            return
        if not self.speaker.speak(text, spec, self.settings):
            self.window.set_status("Nothing to read.")
            return
        if self.settings.show_overlay and not self.window.isActiveWindow():
            self.overlay.show_near_cursor()

    def read_clipboard(self) -> None:
        text = self.qapp.clipboard().text()
        if not text.strip():
            self.tray.notify(APP_NAME, "Clipboard has no text.")
            return
        self.speak(text)

    def read_selection(self) -> None:
        """Hotkey flow: copy the foreground selection, read it, restore the clipboard."""
        clip = self.qapp.clipboard()
        self._saved_clip = clip.text()
        clip.clear()
        try:
            send_copy()
        except Exception as exc:
            log.warning("send_copy failed: %s", exc)
            self.read_clipboard()
            return
        QTimer.singleShot(180, self._after_copy)

    def _after_copy(self) -> None:
        clip = self.qapp.clipboard()
        text = clip.text()
        saved = self._saved_clip
        self._saved_clip = None
        if not text.strip():
            # Nothing was selected -> fall back to what was in the clipboard before
            if saved:
                clip.setText(saved)
                self.speak(saved)
            else:
                self.tray.notify(APP_NAME, "Select some text first, then press the hotkey.")
            return
        if saved is not None:
            QTimer.singleShot(250, lambda: clip.setText(saved))
        self.speak(text)

    def preview_model(self, model_id: str) -> None:
        spec = get_model(model_id)
        if spec is None:
            return
        lang = self.settings.language if self.settings.language in PREVIEW_TEXT else "en"
        if lang not in spec.languages:
            lang = spec.languages[0] if spec.languages[0] in PREVIEW_TEXT else "en"
        text = PREVIEW_TEXT.get(lang, PREVIEW_TEXT["en"])
        s = Settings.from_dict(self.settings.to_dict())
        s.model_id = spec.id
        s.speaker_id = min(self.settings.speaker_id, spec.num_speakers - 1)
        s.language = lang
        self.speaker.speak(text, spec, s)

    def save_wav(self, text: str, path: str) -> None:
        spec = self.current_model()
        if spec is None:
            self._first_run()
            return
        s = self.settings

        def work():
            try:
                import numpy as np

                from utter.tts.engine import Audio
                from utter.tts.speaker import write_wav
                from utter.tts.text import chunk_text, clean_text, detect_language

                eng = self.engines.get(spec, s.num_threads)
                eng.load()
                parts = []
                sr = 0
                for chunk in chunk_text(clean_text(text, strip_markdown=s.strip_markdown, urls=s.read_urls_as)):
                    lang = s.language if s.language != "auto" else detect_language(chunk).code
                    if spec.supports_lang_tag and lang not in spec.languages:
                        lang = "en"
                    a = eng.synthesize(chunk, speaker_id=s.speaker_id, speed=s.speed, lang=lang, num_steps=s.num_steps)
                    sr = a.sample_rate
                    parts.append(a.samples)
                    parts.append(np.zeros(int(sr * 0.12), dtype=np.float32))
                if not parts:
                    raise RuntimeError("nothing to synthesize")
                write_wav(path, Audio(np.concatenate(parts), sr))
                self._wav_done.emit(path)
            except Exception as exc:
                log.exception("save_wav failed")
                self._wav_failed.emit(str(exc))

        self.window.set_status("Rendering WAV…")
        threading.Thread(target=work, name="utter-wav", daemon=True).start()

    # ---- hotkeys ----------------------------------------------------------
    def apply_hotkeys(self) -> None:
        hk = self.settings.hotkeys
        bindings = {
            hk.read_selection: lambda: self._bridge.fired.emit("read_selection"),
            hk.read_clipboard: lambda: self._bridge.fired.emit("read_clipboard"),
            hk.pause_resume: lambda: self._bridge.fired.emit("pause_resume"),
            hk.stop: lambda: self._bridge.fired.emit("stop"),
            hk.show_window: lambda: self._bridge.fired.emit("show_window"),
        }
        self.hotkeys.start({k: v for k, v in bindings.items() if k})
        if self.hotkeys.failed:
            msg = "; ".join(f"{k}: {v}" for k, v in self.hotkeys.failed.items())
            log.warning("hotkeys failed: %s", msg)
            self.window.set_status(f"Some hotkeys could not be registered: {msg}")

    def _on_hotkey(self, name: str) -> None:
        log.debug("hotkey %s", name)
        if name == "read_selection":
            self.read_selection()
        elif name == "read_clipboard":
            self.read_clipboard()
        elif name == "pause_resume":
            if self.speaker.busy:
                self.speaker.toggle_pause()
        elif name == "stop":
            self.speaker.stop()
            self.overlay.hide()
        elif name == "show_window":
            self.toggle_window()

    # ---- windows ----------------------------------------------------------
    def toggle_window(self) -> None:
        if self.window.isVisible() and self.window.isActiveWindow():
            self.window.hide()
        else:
            self.window.show_and_raise()

    def open_settings(self, tab: str = "general") -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog(self.settings, parent=self.window, tab=tab)
        dlg.models_changed.connect(self._on_models_changed)
        dlg.preview_model.connect(self.preview_model)
        dlg.applied.connect(self._on_settings_applied)
        dlg.finished.connect(self._settings_closed)
        self._settings_dialog = dlg
        self.window.show_and_raise()
        dlg.show()

    def _settings_closed(self, _result: int) -> None:
        self._settings_dialog = None

    def _on_models_changed(self) -> None:
        self.engines.clear()
        self.window.refresh_models()
        self.settings.save()

    def _on_settings_applied(self) -> None:
        self.apply_hotkeys()
        self._apply_autostart()
        self.window.refresh_models()

    def _on_ui_settings_changed(self) -> None:
        self.settings.save()
        spec = self.current_model()
        if spec is not None and not self.speaker.busy:
            self.speaker.preload(spec, self.settings)

    def _on_error(self, message: str) -> None:
        self.overlay.hide()
        if not self.window.isVisible():
            self.tray.notify(f"{APP_NAME} — error", message)

    # ---- lifecycle ---------------------------------------------------------
    def _apply_autostart(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE
            )
            if self.settings.launch_at_login:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    cmd = f'"{sys.executable}" -m utter'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as exc:  # pragma: no cover
            log.warning("autostart registry update failed: %s", exc)

    def quit(self) -> None:
        self.window.force_quit()
        self.qapp.quit()

    def _shutdown(self) -> None:
        self.window.persist()
        self.settings.save()
        self.speaker.stop()
        self.hotkeys.stop()
        self.tray.hide()


# --------------------------------------------------------------------------- bootstrap


def _load_icon() -> QIcon:
    for name in ("icon.ico", "icon.png", "icon.svg"):
        p = resource_path("assets", name)
        if p.exists():
            return QIcon(str(p))
    return QIcon()


def _setup_logging() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if os.environ.get("UTTER_DEBUG") else logging.INFO)
    fh = RotatingFileHandler(log_file(), maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stderr is not None:  # windowed PyInstaller builds have no stderr
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def _single_instance_or_wake() -> QLocalServer | None:
    """Return a QLocalServer if we are the first instance; else wake the other one and return None."""
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return None
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)  # stale socket from a crash
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE_KEY)
    return server


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _setup_logging()
    log.info("%s %s starting", APP_NAME, __version__)

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(argv)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationDisplayName(APP_NAME)
    qapp.setApplicationVersion(__version__)
    qapp.setOrganizationName(APP_NAME)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setStyle("Fusion")
    qapp.setStyleSheet(QSS)

    server = _single_instance_or_wake()
    if server is None:
        log.info("another instance is running; asked it to show itself")
        return 0

    app = UtterApp(qapp)
    qapp.setWindowIcon(app.icon)

    def _incoming():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(lambda: (conn.readAll(), app.window.show_and_raise()))

    server.newConnection.connect(_incoming)

    if "--speak-clipboard" in argv:
        QTimer.singleShot(500, app.read_clipboard)

    return qapp.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
