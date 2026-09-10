"""System tray icon and menu."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from utter import APP_NAME
from utter.tts import speaker as spk


class Tray(QSystemTrayIcon):
    show_window = Signal()
    read_clipboard = Signal()
    pause_resume = Signal()
    stop = Signal()
    open_settings = Signal()
    quit = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip(f"{APP_NAME} — ready")
        menu = QMenu()
        self.a_show = QAction("Open Utter", menu)
        self.a_clip = QAction("Read clipboard", menu)
        self.a_pause = QAction("Pause", menu)
        self.a_pause.setEnabled(False)
        self.a_stop = QAction("Stop", menu)
        self.a_stop.setEnabled(False)
        self.a_settings = QAction("Settings…", menu)
        self.a_quit = QAction("Quit", menu)
        menu.addAction(self.a_show)
        menu.addSeparator()
        menu.addAction(self.a_clip)
        menu.addAction(self.a_pause)
        menu.addAction(self.a_stop)
        menu.addSeparator()
        menu.addAction(self.a_settings)
        menu.addSeparator()
        menu.addAction(self.a_quit)
        self.setContextMenu(menu)
        self._menu = menu  # keep alive

        self.a_show.triggered.connect(self.show_window.emit)
        self.a_clip.triggered.connect(self.read_clipboard.emit)
        self.a_pause.triggered.connect(self.pause_resume.emit)
        self.a_stop.triggered.connect(self.stop.emit)
        self.a_settings.triggered.connect(self.open_settings.emit)
        self.a_quit.triggered.connect(self.quit.emit)
        self.activated.connect(self._activated)

    def _activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window.emit()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.read_clipboard.emit()

    def on_state(self, state: str) -> None:
        active = state in (spk.STATE_SPEAKING, spk.STATE_PAUSED)
        self.a_pause.setEnabled(active)
        self.a_stop.setEnabled(active or state == spk.STATE_LOADING)
        self.a_pause.setText("Resume" if state == spk.STATE_PAUSED else "Pause")
        label = {
            spk.STATE_LOADING: "loading model…",
            spk.STATE_SPEAKING: "speaking",
            spk.STATE_PAUSED: "paused",
        }.get(state, "ready")
        self.setToolTip(f"{APP_NAME} — {label}")

    def notify(self, title: str, body: str, msecs: int = 4000) -> None:
        if self.supportsMessages():
            self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, msecs)
