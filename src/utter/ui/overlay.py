"""Tiny always-on-top mini player that appears near the cursor while Utter speaks."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from utter.tts import speaker as spk


class Overlay(QWidget):
    pause_clicked = Signal()
    stop_clicked = Signal()
    open_clicked = Signal()

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        frame = QFrame(self, objectName="overlay")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color:#7c8cff; font-size:14px;")
        self.label = QLabel("Speaking…")
        self.label.setMinimumWidth(130)
        self.btn_pause = QPushButton("⏸", objectName="flat")
        self.btn_pause.setToolTip("Pause / resume")
        self.btn_stop = QPushButton("■", objectName="flat")
        self.btn_stop.setToolTip("Stop")
        self.btn_open = QPushButton("↗", objectName="flat")
        self.btn_open.setToolTip("Open Utter")
        for b in (self.btn_pause, self.btn_stop, self.btn_open):
            b.setFixedSize(28, 28)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.dot)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.btn_pause)
        lay.addWidget(self.btn_stop)
        lay.addWidget(self.btn_open)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_open.clicked.connect(self.open_clicked.emit)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._pulse = QTimer(self)
        self._pulse.setInterval(600)
        self._pulse.timeout.connect(self._toggle_dot)
        self._dot_on = True

    # ---- API -------------------------------------------------------------
    def show_near_cursor(self) -> None:
        self.adjustSize()
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(pos.x() + 16, geo.left() + 8), geo.right() - self.width() - 8)
        y = min(max(pos.y() + 24, geo.top() + 8), geo.bottom() - self.height() - 8)
        self.move(QPoint(x, y))
        self._hide_timer.stop()
        self.show()

    def on_state(self, state: str) -> None:
        if state == spk.STATE_LOADING:
            self.label.setText("Loading model…")
            self.btn_pause.setText("⏸")
            self._pulse.start()
        elif state == spk.STATE_SPEAKING:
            self.label.setText("Speaking…")
            self.btn_pause.setText("⏸")
            self._pulse.start()
        elif state == spk.STATE_PAUSED:
            self.label.setText("Paused")
            self.btn_pause.setText("▶")
            self._pulse.stop()
            self._set_dot(True)
        else:
            self._pulse.stop()
            self._set_dot(True)
            self.label.setText("Done")
            self._hide_timer.start(900)

    def on_progress(self, idx: int, total: int) -> None:
        if total > 1:
            self.label.setText(f"Speaking…  {idx}/{total}")

    def _toggle_dot(self) -> None:
        self._set_dot(not self._dot_on)

    def _set_dot(self, on: bool) -> None:
        self._dot_on = on
        self.dot.setStyleSheet(f"color:{'#7c8cff' if on else '#3a3f57'}; font-size:14px;")
