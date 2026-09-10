"""Tiny always-on-top mini player that appears near the cursor while Utter speaks.

v3.0.0: the overlay can be dragged anywhere with the mouse. Dragging pins it in place;
the pinned position survives restarts (Settings.overlay_pos). With
`Settings.overlay_follow_cursor` on (default) a fresh read moves it back next to the cursor,
with it off it stays wherever it was last dropped.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from utter.tts import speaker as spk

_DRAG_THRESHOLD = 4  # px before a press turns into a drag


class Overlay(QWidget):
    pause_clicked = Signal()
    stop_clicked = Signal()
    open_clicked = Signal()
    moved = Signal(int, int)  # user dropped the overlay at (x, y)

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
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        self.frame = QFrame(self, objectName="overlay")
        lay = QHBoxLayout(self.frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color:#7c8cff; font-size:14px;")
        self.label = QLabel("Speaking…")
        self.label.setMinimumWidth(130)
        self.label.setToolTip("Drag to move the mini player")
        self.btn_pause = QPushButton("⏸", objectName="flat")
        self.btn_pause.setToolTip("Pause / resume")
        self.btn_stop = QPushButton("■", objectName="flat")
        self.btn_stop.setToolTip("Stop")
        self.btn_open = QPushButton("Open", objectName="flat")
        self.btn_open.setToolTip("Hide this mini player and open the text in the Utter window")
        for b in (self.btn_pause, self.btn_stop):
            b.setFixedSize(28, 28)
        self.btn_open.setFixedHeight(28)
        for b in (self.btn_pause, self.btn_stop, self.btn_open):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.dot)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.btn_pause)
        lay.addWidget(self.btn_stop)
        lay.addWidget(self.btn_open)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)

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

        self._press_pos: QPoint | None = None  # global cursor pos at press
        self._press_origin = QPoint()  # window top-left at press
        self._dragging = False
        self._pinned: QPoint | None = None
        self._follow_cursor = True

    # ---- placement API ---------------------------------------------------
    def set_follow_cursor(self, follow: bool) -> None:
        self._follow_cursor = bool(follow)

    def set_pinned_position(self, pos: tuple[int, int] | None) -> None:
        self._pinned = QPoint(int(pos[0]), int(pos[1])) if pos else None

    @property
    def pinned_position(self) -> tuple[int, int] | None:
        return (self._pinned.x(), self._pinned.y()) if self._pinned is not None else None

    def show_near_cursor(self) -> None:
        """Show the player. Next to the cursor by default, or at the pinned spot when set."""
        self._hide_timer.stop()
        self.frame.adjustSize()
        self.adjustSize()
        if self._pinned is not None and not self._follow_cursor:
            self.move(self._clamp_to_screen(self._pinned))
        elif self.isVisible() and not self._follow_cursor:
            pass  # already on screen, do not jump around under the user's hands
        else:
            pos = QCursor.pos()
            self.move(self._clamp_to_screen(QPoint(pos.x() + 16, pos.y() + 24), pos))
        self.show()
        self.raise_()

    def show_now(self) -> None:
        """Alias kept for callers that only want to make sure the player is visible."""
        self.show_near_cursor()

    def _clamp_to_screen(self, want: QPoint, anchor: QPoint | None = None) -> QPoint:
        screen = QGuiApplication.screenAt(anchor or want) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        w = max(self.width(), self.sizeHint().width())
        h = max(self.height(), self.sizeHint().height())
        x = min(max(want.x(), geo.left() + 8), geo.right() - w - 8)
        y = min(max(want.y(), geo.top() + 8), geo.bottom() - h - 8)
        return QPoint(x, y)

    # ---- drag to move ----------------------------------------------------
    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press_pos = ev.globalPosition().toPoint()
            self._press_origin = self.frameGeometry().topLeft()
            self._dragging = False
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._press_pos is None or not (ev.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(ev)
            return
        delta = ev.globalPosition().toPoint() - self._press_pos
        if not self._dragging and delta.manhattanLength() < _DRAG_THRESHOLD:
            return
        self._dragging = True
        self._hide_timer.stop()
        self.move(self._press_origin + delta)
        ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            was_drag = self._dragging
            self._press_pos = None
            self._dragging = False
            if was_drag:
                pos = self._clamp_to_screen(self.frameGeometry().topLeft())
                self.move(pos)
                self._pinned = QPoint(pos)
                self.moved.emit(pos.x(), pos.y())
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    # ---- state -----------------------------------------------------------
    def on_state(self, state: str) -> None:
        if state != spk.STATE_IDLE:
            self._hide_timer.stop()  # a new read may start during the "Done" fade
        if state == spk.STATE_LOADING:
            self.label.setText("Loading model…")
            self.btn_pause.setText("⏸")
            self.btn_pause.setEnabled(True)
            self._pulse.start()
        elif state == spk.STATE_SPEAKING:
            self.label.setText("Speaking…")
            self.btn_pause.setText("⏸")
            self.btn_pause.setEnabled(True)
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
            if self.isVisible():
                self._hide_timer.start(900)

    def on_progress(self, idx: int, total: int) -> None:
        if total > 1:
            self.label.setText(f"Speaking…  {idx}/{total}")

    def hideEvent(self, ev) -> None:  # noqa: N802 (Qt override)
        self._hide_timer.stop()
        self._pulse.stop()
        self._press_pos = None
        self._dragging = False
        super().hideEvent(ev)

    def _toggle_dot(self) -> None:
        self._set_dot(not self._dot_on)

    def _set_dot(self, on: bool) -> None:
        self._dot_on = on
        self.dot.setStyleSheet(f"color:{'#7c8cff' if on else '#3a3f57'}; font-size:14px;")
