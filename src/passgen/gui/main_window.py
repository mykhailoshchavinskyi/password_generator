"""Головне вікно: одна фраза, шкала стійкості, налаштування, що згортаються."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from passgen import __version__
from passgen.core import (
    DIGITS_RANGE,
    MAX_LEN_RANGE,
    SEPARATOR_MAX,
    SYMBOLS_RANGE,
    WORDS_RANGE,
    Case,
    Config,
    ConfigError,
    Generator,
    Passphrase,
    strength_label,
)
from passgen.gui import theme
from passgen.gui.clipboard import ClipboardGuard
from passgen.settings import CLIPBOARD_CLEAR_RANGE, AppSettings
from passgen.wordlist import WordlistError, builtin_words, load_file

# HEAD веде на гілку за замовчуванням, хоч би як вона називалася
GUIDE_URL = (
    "https://github.com/mykhailoshchavinskyi/password_generator/blob/HEAD/docs/user-guide.md"
)
CASE_LABELS = {Case.CAPITALIZE: "Слово", Case.LOWER: "слово", Case.UPPER: "СЛОВО"}
ZWSP = "\u200b"  # дозволяє переносити довгу фразу; у буфер обміну не потрапляє


class PhraseLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings | None = None,
        save: Callable[[AppSettings], None] | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings or AppSettings()
        self._save = save
        self._words = builtin_words()
        self._generator: Generator | None = None
        self.phrase: Passphrase | None = None
        self._loading = False

        self._save_timer = QTimer(self, singleShot=True, interval=400)
        self._save_timer.timeout.connect(self._persist)
        self.clipboard = ClipboardGuard(self)
        self.clipboard.remaining_changed.connect(self._update_clipboard_note)

        self.setWindowTitle("Passgen")
        self._build_ui()
        self._build_menu()
        self._init_wordlist(self.settings.wordlist_path)
        self._apply_settings_to_widgets()
        self._set_settings_open(self.settings.settings_open)
        self._apply_always_on_top()
        self._update_clipboard_note(0)
        self.regenerate()

    # ---------- побудова інтерфейсу ----------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSizeF(max(mono.pointSizeF(), 10) * 1.6)
        mono.setWeight(QFont.Weight.DemiBold)
        self.phrase_label = PhraseLabel()
        self.phrase_label.setObjectName("phrase")
        self.phrase_label.setFont(mono)
        self.phrase_label.setTextFormat(Qt.TextFormat.RichText)
        self.phrase_label.setWordWrap(True)
        self.phrase_label.setMinimumHeight(int(mono.pointSizeF() * 4.2))
        self.phrase_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.phrase_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.phrase_label.setToolTip("Клік — скопіювати")
        self.phrase_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.phrase_label.clicked.connect(self.copy)
        root.addWidget(self.phrase_label)

        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setTextVisible(False)
        self.meter.setFixedHeight(6)
        root.addWidget(self.meter)

        info = QHBoxLayout()
        self.strength_label = QLabel()
        self.length_label = QLabel()
        self.length_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        info.addWidget(self.strength_label)
        info.addStretch()
        info.addWidget(self.length_label)
        root.addLayout(info)

        buttons = QHBoxLayout()
        self.new_button = QPushButton("↻ Нова")
        self.new_button.setToolTip("Згенерувати нову фразу (Ctrl+R)")
        self.new_button.clicked.connect(self.regenerate)
        self.copy_button = QPushButton("Копіювати")
        self.copy_button.setToolTip("Скопіювати фразу (Ctrl+Shift+C)")
        self.copy_button.setDefault(True)
        self.copy_button.clicked.connect(self.copy)
        for b in (self.new_button, self.copy_button):
            b.setMinimumHeight(34)
            buttons.addWidget(b, 1)
        root.addLayout(buttons)

        self.clipboard_note = QLabel()
        self.clipboard_note.setObjectName("note")
        root.addWidget(self.clipboard_note)

        self.toggle = QToolButton()
        self.toggle.setText("Налаштування")
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self.toggle.toggled.connect(self._set_settings_open)
        root.addWidget(self.toggle)

        self.panel = QWidget()
        root.addWidget(self.panel)
        self._build_settings(self.panel)

        self.setCentralWidget(central)
        self.setMinimumWidth(440)

    def _build_settings(self, panel: QWidget) -> None:
        form = QFormLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.words_slider, words_row = self._slider_row(*WORDS_RANGE)
        form.addRow("Кількість слів", words_row)
        self.maxlen_slider, maxlen_row = self._slider_row(*MAX_LEN_RANGE)
        form.addRow("Максимальна довжина", maxlen_row)

        self.digits_min, self.digits_max, digits_row = self._range_row(*DIGITS_RANGE)
        form.addRow("Цифр у частині", digits_row)
        self.symbols_min, self.symbols_max, symbols_row = self._range_row(*SYMBOLS_RANGE)
        form.addRow("Символів у частині", symbols_row)

        self.symbol_set_edit = QLineEdit()
        self.symbol_set_edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.symbol_set_edit.setToolTip("Які спецсимволи використовувати")
        form.addRow("Спецсимволи", self.symbol_set_edit)

        self.separator_edit = QLineEdit()
        self.separator_edit.setMaxLength(SEPARATOR_MAX)
        self.separator_edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.separator_edit.setPlaceholderText("без роздільника")
        form.addRow("Роздільник", self.separator_edit)

        self.case_combo = QComboBox()
        for case, label in CASE_LABELS.items():
            self.case_combo.addItem(label, case.value)
        form.addRow("Регістр слів", self.case_combo)

        self.wordlist_label = QLabel()
        self.wordlist_label.setWordWrap(True)
        pick = QPushButton("Обрати файл…")
        pick.clicked.connect(self._pick_wordlist)
        self.builtin_button = QPushButton("Вбудований")
        self.builtin_button.setToolTip("Повернутися до вбудованого словника")
        self.builtin_button.clicked.connect(lambda: self._set_wordlist(None))
        dict_buttons = QHBoxLayout()
        dict_buttons.addWidget(pick)
        dict_buttons.addWidget(self.builtin_button)
        dict_buttons.addStretch()
        dict_box = QVBoxLayout()
        dict_box.setSpacing(4)
        dict_box.addWidget(self.wordlist_label)
        dict_box.addLayout(dict_buttons)
        form.addRow("Словник", dict_box)

        self.clear_spin = QSpinBox()
        self.clear_spin.setRange(*CLIPBOARD_CLEAR_RANGE)
        self.clear_spin.setSuffix(" с")
        self.clear_spin.setSpecialValueText("не очищати")
        form.addRow("Очищати буфер через", self.clear_spin)

        self.on_top_check = QCheckBox("Поверх усіх вікон")
        form.addRow("", self.on_top_check)

        self.config_error = QLabel()
        self.config_error.setObjectName("error")
        self.config_error.setWordWrap(True)
        self.config_error.hide()
        form.addRow(self.config_error)

        reset = QPushButton("Скинути до стандартних")
        reset.clicked.connect(self.reset_defaults)
        form.addRow("", reset)

        for w in (
            self.words_slider,
            self.maxlen_slider,
            self.digits_min,
            self.digits_max,
            self.symbols_min,
            self.symbols_max,
        ):
            w.valueChanged.connect(self._on_config_changed)
        self.symbol_set_edit.textChanged.connect(self._on_config_changed)
        self.separator_edit.textChanged.connect(self._on_config_changed)
        self.case_combo.currentIndexChanged.connect(self._on_config_changed)
        self.clear_spin.valueChanged.connect(self._on_app_option_changed)
        self.on_top_check.toggled.connect(self._on_app_option_changed)

    def _slider_row(self, lo: int, hi: int) -> tuple[QSlider, QWidget]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        value = QLabel()
        value.setMinimumWidth(28)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setText(str(slider.value()))
        slider.valueChanged.connect(lambda v: value.setText(str(v)))
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(slider, 1)
        lay.addWidget(value)
        return slider, row

    def _range_row(self, lo: int, hi: int) -> tuple[QSpinBox, QSpinBox, QWidget]:
        a, b = QSpinBox(), QSpinBox()
        for s in (a, b):
            s.setRange(lo, hi)
        a.setToolTip("від")
        b.setToolTip("до")
        # мінімум не може перевищити максимум: тягнемо інше поле за собою
        a.valueChanged.connect(lambda v: b.setValue(v) if v > b.value() else None)
        b.valueChanged.connect(lambda v: a.setValue(v) if v < a.value() else None)
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("від"))
        lay.addWidget(a)
        lay.addWidget(QLabel("до"))
        lay.addWidget(b)
        lay.addStretch()
        return a, b, row

    def _build_menu(self) -> None:
        new_act = QAction("Нова фраза", self)
        new_act.setShortcuts([QKeySequence("Ctrl+R"), QKeySequence(Qt.Key.Key_F5)])
        new_act.triggered.connect(self.regenerate)
        copy_act = QAction("Копіювати фразу", self)
        copy_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_act.triggered.connect(self.copy)
        quit_act = QAction("Вихід", self)
        # StandardKey.Quit на Windows порожній, тому Ctrl+Q задаємо явно
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu = self.menuBar().addMenu("&Фраза")
        file_menu.addActions([new_act, copy_act])
        file_menu.addSeparator()
        file_menu.addAction(quit_act)

        guide = QAction("Посібник користувача", self)
        guide.setShortcut(QKeySequence.StandardKey.HelpContents)
        guide.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(GUIDE_URL)))
        about = QAction("Про програму", self)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        about.triggered.connect(self._about)
        help_menu = self.menuBar().addMenu("&Довідка")
        help_menu.addActions([guide, about])

    # ---------- налаштування ----------

    def _apply_settings_to_widgets(self) -> None:
        self._loading = True
        c = self.settings.config
        self.words_slider.setValue(c.words)
        self.digits_min.setValue(c.digits_min)
        self.digits_max.setValue(c.digits_max)
        self.digits_min.setValue(c.digits_min)
        self.symbols_min.setValue(c.symbols_min)
        self.symbols_max.setValue(c.symbols_max)
        self.symbols_min.setValue(c.symbols_min)
        self.symbol_set_edit.setText(c.symbol_set)
        self.separator_edit.setText(c.separator)
        self.case_combo.setCurrentIndex(self.case_combo.findData(c.case.value))
        self.clear_spin.setValue(self.settings.clipboard_clear_seconds)
        self.on_top_check.setChecked(self.settings.always_on_top)
        self._loading = False
        self._update_maxlen_minimum()
        self.maxlen_slider.setValue(c.max_len)

    def _config_from_widgets(self) -> Config:
        return Config(
            words=self.words_slider.value(),
            max_len=self.maxlen_slider.value(),
            digits_min=self.digits_min.value(),
            digits_max=self.digits_max.value(),
            symbols_min=self.symbols_min.value(),
            symbols_max=self.symbols_max.value(),
            symbol_set=self.symbol_set_edit.text(),
            separator=self.separator_edit.text(),
            case=Case(self.case_combo.currentData()),
            unique_words=self.settings.config.unique_words,
        )

    def _update_maxlen_minimum(self) -> None:
        """Повзунок довжини не дозволяє вибрати значення, менше за мінімально можливе."""
        probe = replace(self._config_from_widgets(), max_len=MAX_LEN_RANGE[1])
        try:
            minimum = Generator(probe, self._words).min_length
        except ConfigError:
            return
        self.maxlen_slider.setMinimum(min(minimum, MAX_LEN_RANGE[1]))

    def _on_config_changed(self) -> None:
        if self._loading:
            return
        self._update_maxlen_minimum()
        self.regenerate()

    def _on_app_option_changed(self) -> None:
        if self._loading:
            return
        self.settings.clipboard_clear_seconds = self.clear_spin.value()
        self.settings.always_on_top = self.on_top_check.isChecked()
        self._apply_always_on_top()
        self._update_clipboard_note(0)
        self._schedule_save()

    def reset_defaults(self) -> None:
        open_ = self.settings.settings_open
        self.settings = AppSettings(settings_open=open_)
        self._set_wordlist(None, regenerate=False)
        self._apply_settings_to_widgets()
        self._apply_always_on_top()
        self.regenerate()

    def _set_settings_open(self, open_: bool) -> None:
        self.toggle.blockSignals(True)
        self.toggle.setChecked(open_)
        self.toggle.blockSignals(False)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if open_ else Qt.ArrowType.RightArrow)
        self.panel.setVisible(open_)
        if self.settings.settings_open != open_:
            self.settings.settings_open = open_
            self._schedule_save()
        QTimer.singleShot(0, self._fit_height)

    def _fit_height(self) -> None:
        self.centralWidget().layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def _apply_always_on_top(self) -> None:
        on = self.settings.always_on_top
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != on:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
            if self.isVisible():
                self.show()

    def _schedule_save(self) -> None:
        if self._save:
            self._save_timer.start()

    def _persist(self) -> None:
        if self._save:
            self._save(self.settings)

    # ---------- словник ----------

    def _pick_wordlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл словника", str(Path.home()), "Текстові файли (*.txt);;Усі файли (*)"
        )
        if path:
            self._set_wordlist(path)

    def _set_wordlist(self, path: str | None, regenerate: bool = True) -> None:
        if path:
            try:
                words = load_file(path)
            except WordlistError as e:
                QMessageBox.warning(self, "Словник", str(e))
                return
        else:
            words = builtin_words()
        self._apply_wordlist(words, path)
        self.settings.wordlist_path = path
        self._schedule_save()
        if regenerate:
            self._update_maxlen_minimum()
            self.regenerate()

    def _init_wordlist(self, path: str | None) -> None:
        """Під час запуску: якщо збережений словник недоступний, тихо беремо вбудований."""
        words = None
        if path:
            try:
                words = load_file(path)
            except WordlistError:
                path = self.settings.wordlist_path = None
        self._apply_wordlist(words or builtin_words(), path)

    def _apply_wordlist(self, words: tuple[str, ...], path: str | None) -> None:
        self._words = words
        name = Path(path).name if path else "Вбудований"
        self.wordlist_label.setText(f"{name}, {len(words)} слів")
        self.wordlist_label.setToolTip(path or "")
        self.builtin_button.setEnabled(bool(path))

    # ---------- генерація і копіювання ----------

    def regenerate(self) -> None:
        config = self._config_from_widgets()
        try:
            self._generator = Generator(config, self._words)
            self.phrase = self._generator.generate()
        except ConfigError as e:
            self._generator = None
            self.phrase = None
            self._show_error(str(e))
            return
        self.config_error.hide()
        if config != self.settings.config:
            self.settings.config = config
            self._schedule_save()
        self._render()

    def _show_error(self, message: str) -> None:
        colors = theme.current()
        self.phrase_label.setText(
            f'<span style="color:{colors.bad}; font-size:11pt">Неможливо згенерувати фразу</span>'
        )
        self.config_error.setText(message)
        self.config_error.setStyleSheet(f"color: {colors.bad};")
        self.config_error.show()
        self.meter.setValue(0)
        self.strength_label.setText("")
        self.length_label.setText("")
        self.copy_button.setEnabled(False)
        self.new_button.setEnabled(False)

    def _render(self) -> None:
        assert self.phrase and self._generator
        colors = theme.current()
        kind_color = {
            "word": colors.word,
            "digits": colors.digits,
            "symbols": colors.symbols,
            "separator": colors.separator,
        }
        pieces = []
        for kind, text in self.phrase.tokens():
            span = f'<span style="color:{kind_color[kind]}">{html.escape(text)}</span>'
            pieces.append(span + (ZWSP if kind == "separator" else ""))
        self.phrase_label.setText("".join(pieces))
        self.phrase_label.setAccessibleName(self.phrase.text)

        bits = self._generator.entropy_bits()
        color = theme.strength_color(bits, colors)
        self.meter.setValue(min(100, round(bits)))
        self.meter.setStyleSheet(
            f"QProgressBar {{ border: none; border-radius: 3px; background: {colors.separator}; }}"
            f"QProgressBar::chunk {{ border-radius: 3px; background: {color}; }}"
        )
        self.strength_label.setText(f"{strength_label(bits)} · <b>{bits:.1f} біт</b>")
        self.strength_label.setToolTip(
            "Стійкість генератора: скільки біт ентропії, якщо зловмисник знає всі правила.\n"
            f"Ця фраза: {self.phrase.bits:.1f} біт, якщо відомий навіть її точний шаблон."
        )
        self.length_label.setText(f"<b>{len(self.phrase)}</b> символів")
        self.copy_button.setEnabled(True)
        self.new_button.setEnabled(True)

    def copy(self) -> None:
        if not self.phrase:
            return
        self.clipboard.copy(self.phrase.text, self.settings.clipboard_clear_seconds)

    def _update_clipboard_note(self, remaining: int) -> None:
        secs = self.settings.clipboard_clear_seconds
        if remaining > 0:
            text = f"Скопійовано. Буфер обміну очиститься через {remaining} с."
        elif secs > 0:
            text = f"Буфер обміну очищається через {secs} с після копіювання."
        else:
            text = "Автоочищення буфера обміну вимкнено."
        self.clipboard_note.setText(text)
        self.clipboard_note.setStyleSheet(f"color: {theme.current().muted};")

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "Про програму",
            f"<b>Passgen {__version__}</b><br>Генератор парольних фраз.<br><br>"
            "Фраза рівномірно вибирається серед усіх, що відповідають налаштуванням, "
            "за допомогою криптографічно стійкого генератора випадкових чисел. "
            "Паролі ніде не зберігаються і не передаються.",
        )

    # ---------- події вікна ----------

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().changeEvent(event)
        palette_events = (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange)
        if event.type() in palette_events and self.phrase:
            self._render()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.clipboard.pending:
            self.clipboard.clear_now()
        self._save_timer.stop()
        self._persist()
        super().closeEvent(event)
