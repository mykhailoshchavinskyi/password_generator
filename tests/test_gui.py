import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from passgen.core import Case, Config  # noqa: E402
from passgen.gui.main_window import MainWindow  # noqa: E402
from passgen.settings import AppSettings  # noqa: E402


@pytest.fixture
def window(qtbot):
    saved = []
    w = MainWindow(AppSettings(), save=saved.append)
    w.saved = saved
    qtbot.addWidget(w)
    w.show()
    return w


def test_starts_with_phrase(window):
    assert window.phrase is not None
    assert len(window.phrase.segments) == 3
    assert window.copy_button.isEnabled()
    assert "біт" in window.strength_label.text()
    assert window.meter.value() > 70


def test_new_button_changes_phrase(window, qtbot):
    seen = {window.phrase.text}
    for _ in range(5):
        qtbot.mouseClick(window.new_button, Qt.MouseButton.LeftButton)
        seen.add(window.phrase.text)
    assert len(seen) > 1


def test_settings_change_regenerates_and_saves(window, qtbot):
    window.words_slider.setValue(4)
    window.maxlen_slider.setValue(40)
    window.separator_edit.setText("-")
    window.case_combo.setCurrentIndex(window.case_combo.findData(Case.UPPER.value))
    assert len(window.phrase.segments) == 4
    assert window.phrase.text.count("-") == 3
    assert window.settings.config == Config(words=4, max_len=40, separator="-", case=Case.UPPER)
    qtbot.waitUntil(lambda: bool(window.saved), timeout=2000)
    assert window.saved[-1].config.words == 4


def test_maxlen_minimum_follows_words(window):
    window.words_slider.setValue(5)
    # 5 · (3 + 2 + 1) + 4 роздільники = 34
    assert window.maxlen_slider.minimum() == 34
    assert window.maxlen_slider.value() >= 34
    assert window.phrase is not None


def test_range_spinboxes_stay_consistent(window):
    window.digits_min.setValue(5)
    assert window.digits_max.value() == 5
    window.symbols_max.setValue(0)
    assert window.symbols_min.value() == 0


def test_invalid_symbols_show_error(window):
    window.symbol_set_edit.setText("!a")
    assert window.phrase is None
    assert not window.copy_button.isEnabled()
    assert not window.config_error.isHidden()
    assert "Недопустимі" in window.config_error.text()
    window.symbol_set_edit.setText("!?")
    assert window.phrase is not None
    assert window.config_error.isHidden()


def test_copy_and_auto_clear(window, qtbot):
    window.clear_spin.setValue(1)
    window.copy()
    clipboard = QGuiApplication.clipboard()
    assert clipboard.text() == window.phrase.text
    assert "очиститься" in window.clipboard_note.text()
    qtbot.waitUntil(lambda: clipboard.text() == "", timeout=3000)


def test_auto_clear_keeps_foreign_clipboard(window, qtbot):
    window.clear_spin.setValue(1)
    window.copy()
    QGuiApplication.clipboard().setText("моє")
    qtbot.wait(1500)
    assert QGuiApplication.clipboard().text() == "моє"


def test_close_clears_pending_clipboard(window):
    window.copy()
    window.close()
    assert QGuiApplication.clipboard().text() == ""


def test_reset_defaults(window):
    window.words_slider.setValue(2)
    window.clear_spin.setValue(0)
    window.reset_defaults()
    assert window.words_slider.value() == 3
    assert window.maxlen_slider.value() == 26
    assert window.settings.clipboard_clear_seconds == 30


def test_settings_panel_toggle(window):
    window.toggle.setChecked(False)
    assert window.panel.isHidden()
    assert window.settings.settings_open is False
    window.toggle.setChecked(True)
    assert not window.panel.isHidden()


def test_restores_saved_settings(qtbot):
    s = AppSettings(config=Config(words=2, max_len=20, separator="."), clipboard_clear_seconds=0)
    w = MainWindow(s)
    qtbot.addWidget(w)
    assert w.words_slider.value() == 2
    assert w.maxlen_slider.value() == 20
    assert w.phrase.text.count(".") == 1
    assert "вимкнено" in w.clipboard_note.text()


def test_missing_custom_wordlist_falls_back(qtbot, tmp_path):
    w = MainWindow(AppSettings(wordlist_path=str(tmp_path / "gone.txt")))
    qtbot.addWidget(w)
    assert w.settings.wordlist_path is None
    assert "Вбудований" in w.wordlist_label.text()


def test_about_shows_author_and_email(window, qtbot):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    text = window.about_text()
    assert "Автор: mykhailoshchavinskyi" in text
    assert 'href="mailto:mykhailo.shchavinskyi@gmail.com"' in text

    seen = []

    def close_box():
        box = QApplication.activeModalWidget()
        if isinstance(box, QMessageBox):
            seen.append(box.text())
            box.accept()

    QTimer.singleShot(100, close_box)
    window._about()
    assert seen and "mykhailo.shchavinskyi@gmail.com" in seen[0]
