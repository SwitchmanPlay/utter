import pytest

from utter.hotkeys import HotkeyParseError, qt_to_pynput


@pytest.mark.parametrize(
    "qt, py",
    [
        ("Ctrl+Alt+R", "<ctrl>+<alt>+r"),
        ("Ctrl+Alt+Space", "<ctrl>+<alt>+<space>"),
        ("F5", "<f5>"),
        ("Shift+F12", "<shift>+<f12>"),
        ("Meta+U", "<cmd>+u"),
        ("Ctrl+Shift+Ins", "<ctrl>+<shift>+<insert>"),
        ("ctrl + alt + x", "<ctrl>+<alt>+x"),
        ("Ctrl+Alt+Ctrl+Y", "<ctrl>+<alt>+y"),
    ],
)
def test_conversion(qt, py):
    assert qt_to_pynput(qt) == py


@pytest.mark.parametrize("bad", ["", "   ", "Ctrl+Alt", "Ctrl+Foo", "A+B"])
def test_rejects(bad):
    with pytest.raises(HotkeyParseError):
        qt_to_pynput(bad)
