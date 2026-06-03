import sys
import json
import re
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QListWidget, QListWidgetItem, QTextBrowser,
    QSplitter, QPushButton, QMessageBox, QTextEdit, QDialog,
    QRadioButton, QButtonGroup, QDialogButtonBox, QSpinBox, QFormLayout,
    QMenu
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QAction

# ==================== ВЕРСИЯ ====================
__version__ = "0.1.0"


def get_external_npa_path() -> Path:
    """Возвращает путь к папке NPA рядом с исполняемым файлом."""
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path.cwd()
    return base_dir / "NPA"


def get_builtin_npa_path() -> Path:
    """Возвращает путь к встроенной папке NPA (если была добавлена при сборке)."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return Path(base_path) / "NPA"


def resource_path(relative_path: str) -> str:
    """Возвращает путь к ресурсу: сначала ищет рядом с exe, потом внутри exe."""
    external_path = get_external_npa_path() / relative_path
    if external_path.exists():
        return str(external_path)

    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ==================== ДИАЛОГ С ИНСТРУКЦИЕЙ ====================
class InstructionDialog(QDialog):
    def __init__(self, parent=None, error_text: str = None):
        super().__init__(parent)
        self.setWindowTitle("Как добавить законы")
        self.setModal(True)
        self.setMinimumWidth(650)
        layout = QVBoxLayout(self)

        if error_text:
            error_label = QLabel(f"⚠️ {error_text}")
            error_label.setStyleSheet(
                "color: #ff6666; font-size: 14px; font-weight: bold; padding: 10px; background-color: #2a0000; border-radius: 5px;")
            layout.addWidget(error_label)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>📁 Добавление собственных кодексов</h2>
        <p>Чтобы приложение работало с вашими законами, создайте папку <b>NPA</b> рядом с программой и поместите в неё JSON-файлы.</p>
        
        <h3>📄 Пример структуры JSON-файла (koap.json):</h3>
        <pre style="background:#2d2d2d; padding:10px; border-radius:5px;">
{
  "codex_name": "КоАП",
  "sections": [
    {
      "section_name": "РАЗДЕЛ II. ОСОБЕННАЯ ЧАСТЬ",
      "chapters": [
        {
          "chapter_name": "Глава 9. Правонарушения в области дорожного движения",
          "articles": [
            {
              "article_number": "12.8",
              "disposition": "Управление транспортным средством в состоянии опьянения...",
              "penalty": "штраф 30000 рублей или лишение прав до 2 лет",
              "fine_amount": 30000
            }
          ]
        }
      ]
    }
  ]
}
        </pre>
        
        <h3>📌 Примечания:</h3>
        <ul>
        <li><b>codex_name</b> – название кодекса (отображается в интерфейсе)</li>
        <li><b>article_number</b> – номер статьи (может быть с точками, например "12.8.1")</li>
        <li><b>disposition</b> – описание правонарушения</li>
        <li><b>penalty</b> – текст санкции (поддерживаются альтернативы через " или ", диапазоны "от X до Y рублей")</li>
        <li><b>fine_amount</b> – необязательное поле; если не указано, сумма извлекается из penalty</li>
        </ul>
        
        <p>✅ После добавления файлов перезапустите программу.</p>
        <p><i>Приложение продолжит работу со встроенной базой (если она есть).</i></p>
        """)
        text.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #e0e0e0; border: none; padding: 10px; }")
        layout.addWidget(text)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


# ==================== ДИАЛОГИ ВЫБОРА НАКАЗАНИЯ ====================
class PenaltyChoiceDialog(QDialog):
    def __init__(self, penalties, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор наказания")
        self.setModal(True)
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Статья предусматривает несколько видов наказания. Выберите один:"))
        self.button_group = QButtonGroup(self)
        self.radio_buttons = []
        for i, (text, fine, is_range, min_fine, max_fine) in enumerate(penalties):
            if is_range:
                display_text = f"{text} (введите сумму от {min_fine:,} до {max_fine:,} руб.)"
            elif fine > 0:
                display_text = f"{text} (штраф {fine:,} руб.)"
            else:
                display_text = text
            rb = QRadioButton(display_text)
            layout.addWidget(rb)
            self.button_group.addButton(rb, i)
            self.radio_buttons.append(rb)
        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.penalties = penalties

    def get_selected_penalty(self):
        checked_id = self.button_group.checkedId()
        if checked_id >= 0:
            return checked_id, self.penalties[checked_id]
        return -1, None


class FineInputDialog(QDialog):
    def __init__(self, min_fine, max_fine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ввод суммы штрафа")
        self.setModal(True)
        self.setMinimumWidth(350)
        layout = QFormLayout(self)
        layout.addRow(QLabel(f"Введите сумму штрафа (от {min_fine:,} до {max_fine:,} руб.):"))
        self.spinbox = QSpinBox()
        self.spinbox.setRange(min_fine, max_fine)
        self.spinbox.setSingleStep(1000)
        self.spinbox.setValue(min_fine)
        self.spinbox.setGroupSeparatorShown(True)
        layout.addRow(self.spinbox)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_fine(self):
        return self.spinbox.value()


# ==================== ГЛАВНОЕ ОКНО ====================
class ModernNPAViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ГИБДД Helper — RMRP (v{__version__}) made by Bisquit & k4ktusss")
        self.resize(1400, 850)

        self.articles = []
        self.incriminated_articles = []
        self.current_article = None

        # Если нет внешней папки NPA, показываем инструкцию, но не выходим
        external_npa = get_external_npa_path()
        if not external_npa.exists():
            dlg = InstructionDialog(self, "Папка NPA не найдена рядом с программой.")
            dlg.exec()

        # Загружаем данные: сначала внешняя папка, если нет статей - встроенная
        if not self._load_data_from_external():
            if not self._load_data_from_builtin():
                dlg = InstructionDialog(self, "Не удалось загрузить ни одной статьи (ни из внешней, ни из встроенной папки NPA).")
                dlg.exec()
                sys.exit(1)

        self._init_ui()
        QTimer.singleShot(500, self._focus_search_bar)

    # ---------- ФОКУС И АКТИВАЦИЯ ОКНА ----------
    def _focus_search_bar(self):
        if hasattr(self, 'search_bar'):
            self.search_bar.setFocus()
            self.search_bar.selectAll()

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and self.isActiveWindow():
            self._focus_search_bar()
        super().changeEvent(event)

    # ---------- ПАРСИНГ ЧИСЕЛ И САНКЦИЙ ----------
    @staticmethod
    def _extract_numbers_from_text(text: str):
        numbers = []
        for match in re.finditer(r'\d[\d\s\.]*\d', text):
            clean = re.sub(r'[\s\.]', '', match.group())
            numbers.append(int(clean))
        for match in re.finditer(r'\b\d\b', text):
            numbers.append(int(match.group()))
        return numbers

    @classmethod
    def _extract_fine_from_penalty(cls, penalty_text: str) -> int:
        if not penalty_text:
            return 0
        if 'от' in penalty_text.lower() and 'до' in penalty_text.lower():
            numbers = cls._extract_numbers_from_text(penalty_text)
            if numbers:
                return numbers[0]
        numbers = cls._extract_numbers_from_text(penalty_text)
        return numbers[0] if numbers else 0

    def _parse_penalty_options(self, article):
        penalty_text = article.get('penalty', '')
        if not penalty_text:
            return [("Нет санкции", 0, False, 0, 0)]

        def process_part(part):
            part_lower = part.lower()
            if 'от' in part_lower and 'до' in part_lower:
                numbers = self._extract_numbers_from_text(part)
                if len(numbers) >= 2:
                    return (part.strip(), 0, True, numbers[0], numbers[1])
                rg = re.search(r'от\s+(\d[\d\s\.]+?)\s+до\s+(\d[\d\s\.]+?)\s+руб', part, re.IGNORECASE)
                if rg:
                    min_fine = int(re.sub(r'[\s\.]', '', rg.group(1)))
                    max_fine = int(re.sub(r'[\s\.]', '', rg.group(2)))
                    return (part.strip(), 0, True, min_fine, max_fine)
            numbers = self._extract_numbers_from_text(part)
            if numbers:
                return (part.strip(), numbers[0], False, 0, 0)
            if 'лишение' in part_lower:
                return (part.strip(), 0, False, 0, 0)
            return (part.strip(), 0, False, 0, 0)

        if ' или ' in penalty_text.lower():
            parts = re.split(r'\s+или\s+', penalty_text, flags=re.IGNORECASE)
            options = [process_part(p) for p in parts]
        else:
            options = [process_part(penalty_text)]

        unique = []
        seen = set()
        for opt in options:
            if opt[0] not in seen:
                seen.add(opt[0])
                unique.append(opt)
        return unique

    # ---------- ЗАГРУЗКА ДАННЫХ ----------
    def _load_data_from_path(self, npa_dir: Path) -> bool:
        """Загружает статьи из указанной папки. Возвращает True, если загружена хотя бы одна статья."""
        if not npa_dir.exists():
            return False

        json_files = list(npa_dir.glob("*.json"))
        if not json_files:
            return False

        articles_temp = []
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    codex_name = data.get("codex_name", json_file.stem)
                    for section in data.get("sections", []):
                        section_name = section.get("section_name", "")
                        for chapter in section.get("chapters", []):
                            chapter_name = chapter.get("chapter_name", "")
                            for art in chapter.get("articles", []):
                                if not art.get("disposition"):
                                    continue
                                penalty = art.get("penalty", "") or ""
                                fine_amount = art.get("fine_amount", 0)
                                if not fine_amount:
                                    fine_amount = self._extract_fine_from_penalty(penalty)
                                articles_temp.append({
                                    **art,
                                    "penalty": penalty,
                                    "fine_amount": fine_amount,
                                    "chapter": chapter_name,
                                    "section": section_name,
                                    "codex": codex_name
                                })
            except Exception as e:
                QMessageBox.warning(self, "Ошибка загрузки", f"Не удалось загрузить {json_file.name}:\n{e}")
                return False

        if articles_temp:
            self.articles = articles_temp
            return True
        return False

    def _load_data_from_external(self) -> bool:
        return self._load_data_from_path(get_external_npa_path())

    def _load_data_from_builtin(self) -> bool:
        return self._load_data_from_path(get_builtin_npa_path())

    # ---------- РАСЧЁТ НАКАЗАНИЙ ----------
    def _calculate_total_penalty(self):
        total_fine = 0
        has_disqualification = False
        breakdown = []
        for article in self.incriminated_articles:
            fine = article.get('selected_fine', 0)
            penalty_text = article.get('selected_penalty', '')
            if fine > 0:
                total_fine += fine
                breakdown.append(f"Ст.{article['article_number']}: {fine:,} руб.")
            if penalty_text and 'лишение прав' in penalty_text.lower():
                has_disqualification = True
                breakdown.append(f"Ст.{article['article_number']}: ЛИШЕНИЕ ПРАВ")
        return total_fine, has_disqualification, breakdown

    def _get_articles_summary(self) -> str:
        if not self.incriminated_articles:
            return "Нет инкриминированных статей"
        parts = [f"{art['article_number']} {art.get('codex', 'КоАП')}" for art in self.incriminated_articles]
        return ", ".join(parts)

    # ---------- ПОСТРОЕНИЕ ИНТЕРФЕЙСА ----------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Левая панель
        self.incriminated_panel = QWidget()
        self.incriminated_panel.setFixedWidth(350)
        self.incriminated_panel.setStyleSheet("QWidget { background-color: #1a1a1a; border-right: 1px solid #333; }")
        incriminated_layout = QVBoxLayout(self.incriminated_panel)
        incriminated_layout.setContentsMargins(10, 15, 10, 15)

        incriminated_title = QLabel("⚖️ Инкриминировано")
        incriminated_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        incriminated_title.setStyleSheet("color: #ff4444; padding: 5px;")
        incriminated_layout.addWidget(incriminated_title)

        self.incriminated_list = QListWidget()
        self.incriminated_list.setStyleSheet("""
            QListWidget { background-color: #1f1f1f; border: none; border-radius: 5px; padding: 5px; font-size: 12px; }
            QListWidget::item { padding: 8px; border-radius: 5px; margin: 2px; }
            QListWidget::item:selected { background-color: #ff4444; color: white; }
            QListWidget::item:hover { background-color: #2a2a2a; }
        """)
        self.incriminated_list.itemClicked.connect(self._show_incriminated_article)
        self.incriminated_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.incriminated_list.customContextMenuRequested.connect(self._show_incriminated_context_menu)
        incriminated_layout.addWidget(self.incriminated_list)

        self.clear_btn = QPushButton("🗑️ Очистить все")
        self.clear_btn.setStyleSheet("""
            QPushButton { background-color: #ff4444; color: white; border: none; border-radius: 5px; padding: 8px; font-size: 13px; font-weight: bold; margin-top: 5px; }
            QPushButton:hover { background-color: #cc0000; }
        """)
        self.clear_btn.clicked.connect(self._clear_incriminated)
        incriminated_layout.addWidget(self.clear_btn)

        self.total_label = QLabel("📊 Суммарное наказание:\n0 руб.")
        self.total_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.total_label.setStyleSheet(
            "QLabel { background-color: #0f0f0f; border-radius: 5px; padding: 10px; margin-top: 10px; color: #ffcc00; }")
        self.total_label.setWordWrap(True)
        incriminated_layout.addWidget(self.total_label)

        copy_label = QLabel("📋 Текст для вставки в игру:")
        copy_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        copy_label.setStyleSheet("color: #888; margin-top: 10px;")
        incriminated_layout.addWidget(copy_label)

        self.copy_text = QTextEdit()
        self.copy_text.setPlaceholderText("Здесь появится список инкриминированных статей...")
        self.copy_text.setMaximumHeight(120)
        self.copy_text.setStyleSheet("""
            QTextEdit { background-color: #0f0f0f; border: 1px solid #333; border-radius: 5px; padding: 8px; font-size: 12px; font-family: 'Consolas', monospace; color: #00ff9d; }
        """)
        self.copy_text.setReadOnly(True)
        incriminated_layout.addWidget(self.copy_text)

        self.copy_btn = QPushButton("📋 Копировать в буфер обмена")
        self.copy_btn.setStyleSheet("""
            QPushButton { background-color: #00b36b; color: white; border: none; border-radius: 5px; padding: 8px; font-size: 12px; font-weight: bold; margin-top: 5px; }
            QPushButton:hover { background-color: #009956; }
        """)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        incriminated_layout.addWidget(self.copy_btn)
        incriminated_layout.addStretch()

        # Центральная панель
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Левая часть центра
        left_center = QWidget()
        left_center.setMinimumWidth(300)
        left_center_layout = QVBoxLayout(left_center)
        left_center_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("📋 База НПА")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff9d;")
        left_center_layout.addWidget(title)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Поиск по статье, ключевому слову, кодексу...")
        self.search_bar.setMinimumHeight(48)
        self.search_bar.textChanged.connect(self._filter_list)
        left_center_layout.addWidget(self.search_bar)

        self.search_info = QLabel("")
        self.search_info.setStyleSheet("color: #888; font-size: 12px; padding: 5px;")
        left_center_layout.addWidget(self.search_info)

        self.article_list = QListWidget()
        self.article_list.setAlternatingRowColors(True)
        self.article_list.itemClicked.connect(self._show_article_details)
        self.article_list.installEventFilter(self)
        left_center_layout.addWidget(self.article_list)

        # Правая часть центра
        right_center = QWidget()
        right_center_layout = QVBoxLayout(right_center)
        right_center_layout.setContentsMargins(0, 0, 0, 0)
        right_center_layout.setSpacing(0)

        self.detail_view = QTextBrowser()
        self.detail_view.setOpenExternalLinks(False)
        self.detail_view.setStyleSheet(
            "QTextBrowser { background-color: #1e1e1e; color: #e0e0e0; border: none; padding: 20px; font-size: 15px; }")

        self.incriminate_btn = QPushButton("⚖️ Инкриминировать статью")
        self.incriminate_btn.setStyleSheet("""
            QPushButton { background-color: #00b36b; color: white; border: none; border-radius: 8px; padding: 12px; font-size: 14px; font-weight: bold; margin: 10px 20px; }
            QPushButton:hover { background-color: #009956; }
            QPushButton:disabled { background-color: #555; }
        """)
        self.incriminate_btn.clicked.connect(self._incriminate_current_article)
        self.incriminate_btn.setEnabled(False)

        right_center_layout.addWidget(self.detail_view)
        right_center_layout.addWidget(self.incriminate_btn)

        # Сплиттеры
        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        center_splitter.addWidget(left_center)
        center_splitter.addWidget(right_center)
        center_splitter.setSizes([450, 650])
        center_layout.addWidget(center_splitter)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.incriminated_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.setSizes([350, 1050])
        main_layout.addWidget(main_splitter)

        self._apply_modern_style()
        self._populate_article_list()

    def _apply_modern_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #0f0f0f; color: #e0e0e0; }
            QListWidget { background-color: #1a1a1a; border: none; border-radius: 8px; padding: 5px; }
            QListWidget::item { padding: 12px; border-radius: 6px; margin: 2px; }
            QListWidget::item:selected { background-color: #00b36b; color: white; }
            QListWidget::item:hover { background-color: #2a2a2a; }
            QLineEdit { background-color: #1f1f1f; border: 2px solid #333; border-radius: 8px; padding: 10px; font-size: 15px; }
            QLineEdit:focus { border: 2px solid #00ff9d; }
            QSplitter::handle { background-color: #333; }
        """)

    # ---------- РАБОТА СО СПИСКОМ СТАТЕЙ ----------
    def _populate_article_list(self):
        self.article_list.clear()
        for article in self.articles:
            item = QListWidgetItem()
            codex_prefix = f"[{article['codex']}] " if article.get('codex') else ""
            fine_info = f" 💰{article['fine_amount']:,} руб." if article.get('fine_amount', 0) > 0 else ""
            item.setText(f"{codex_prefix}Ст. {article['article_number']} — {article['disposition'][:70]}...{fine_info}")
            item.setData(Qt.ItemDataRole.UserRole, article)
            self.article_list.addItem(item)
        self._update_search_info()

    def _filter_list(self, text: str):
        text = text.lower()
        visible_count = 0
        for i in range(self.article_list.count()):
            item = self.article_list.item(i)
            article = item.data(Qt.ItemDataRole.UserRole)
            match = (text in article['article_number'].lower() or
                     text in article['disposition'].lower() or
                     text in article['penalty'].lower() or
                     text in article.get('codex', '').lower() or
                     text in article.get('section', '').lower() or
                     text in article.get('chapter', '').lower())
            item.setHidden(not match)
            if match:
                visible_count += 1
        self._update_search_info(visible_count)

    def _update_search_info(self, visible_count=None):
        if visible_count is None:
            self.search_info.setText(f"📚 Всего статей: {len(self.articles)}")
        else:
            self.search_info.setText(f"🔍 Найдено: {visible_count} из {len(self.articles)}")

    def _show_article_details(self, item):
        self.current_article = item.data(Qt.ItemDataRole.UserRole)
        if not self.current_article:
            self.incriminate_btn.setEnabled(False)
            return

        already = any(art['article_number'] == self.current_article['article_number'] for art in self.incriminated_articles)
        if already:
            self.incriminate_btn.setText("❌ Уже инкриминировано")
            self.incriminate_btn.setEnabled(False)
        else:
            self.incriminate_btn.setText("⚖️ Инкриминировать статью")
            self.incriminate_btn.setEnabled(True)

        penalty = self.current_article.get('penalty', 'Не указано') or 'Не указано'
        codex_info = f"<p><b>📕 Кодекс:</b> {self.current_article.get('codex', '—')}</p>"
        section_info = f"<p><b>📑 Раздел:</b> {self.current_article.get('section', '—')}</p>"
        chapter_info = f"<p><b>📖 Глава:</b> {self.current_article.get('chapter', '—')}</p>"
        fine_amount = self.current_article.get('fine_amount', 0)
        fine_info = f"<p style='color: #ffcc00;'><b>💰 Сумма штрафа:</b> {fine_amount:,} руб.</p>" if fine_amount > 0 else ""

        html = f"""
        <h2 style="color: #00ff9d;">Статья {self.current_article['article_number']}</h2>
        {codex_info}{section_info}{chapter_info}
        <hr style="border: 1px solid #333;">
        <h3>📝 Диспозиция</h3>
        <p style="line-height: 1.6;">{self.current_article['disposition']}</p>
        <h3 style="color: #ffd700; margin-top: 25px;">⚖️ Санкция</h3>
        <p style="color: #ffcc00; font-size: 16px; line-height: 1.6;">{penalty}</p>
        {fine_info}
        """
        self.detail_view.setHtml(html)

    # ---------- ИНКРИМИНИРОВАНИЕ ----------
    def _incriminate_current_article(self):
        if not self.current_article:
            return
        if any(art['article_number'] == self.current_article['article_number'] for art in self.incriminated_articles):
            QMessageBox.warning(self, "Предупреждение", f"Статья {self.current_article['article_number']} уже инкриминирована!")
            return

        options = self._parse_penalty_options(self.current_article)
        selected_penalty_text, selected_fine = self._select_penalty(options)
        if selected_penalty_text is None:
            return

        incriminated_copy = self.current_article.copy()
        incriminated_copy['selected_penalty'] = selected_penalty_text
        incriminated_copy['selected_fine'] = selected_fine
        self.incriminated_articles.append(incriminated_copy)
        self._update_incriminated_list()
        self.incriminate_btn.setText("❌ Уже инкриминировано")
        self.incriminate_btn.setEnabled(False)

    def _select_penalty(self, options):
        if len(options) == 1:
            text, fine, is_range, min_fine, max_fine = options[0]
            if is_range:
                dlg = FineInputDialog(min_fine, max_fine, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    return text, dlg.get_fine()
                return None, 0
            else:
                return text, fine
        else:
            dlg = PenaltyChoiceDialog(options, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None, 0
            idx, (text, fine, is_range, min_fine, max_fine) = dlg.get_selected_penalty()
            if idx < 0:
                return None, 0
            if is_range:
                fine_dlg = FineInputDialog(min_fine, max_fine, self)
                if fine_dlg.exec() == QDialog.DialogCode.Accepted:
                    return text, fine_dlg.get_fine()
                return None, 0
            else:
                return text, fine

    # ---------- РАБОТА СО СПИСКОМ ИНКРИМИНИРОВАННЫХ ----------
    def _update_incriminated_list(self):
        self.incriminated_list.clear()
        total_fine, has_disqual, breakdown = self._calculate_total_penalty()
        for i, art in enumerate(self.incriminated_articles, 1):
            item = QListWidgetItem()
            display = f"{i}. Ст. {art['article_number']}"
            fine = art.get('selected_fine', 0)
            penalty_txt = art.get('selected_penalty', '')
            if fine > 0:
                display += f"\n   💰 {fine:,} руб."
            elif penalty_txt and 'лишение прав' in penalty_txt.lower():
                display += "\n   ⚠️ Лишение прав"
            short_penalty = penalty_txt[:50] + "..." if len(penalty_txt) > 50 else penalty_txt
            if short_penalty:
                display += f"\n   📌 {short_penalty}"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, art)
            self.incriminated_list.addItem(item)

        total_text = f"📊 Суммарное наказание:\n{total_fine:,} руб." if total_fine > 0 else "📊 Суммарное наказание:\n0 руб."
        if has_disqual:
            total_text += "\n⚠️ Включая лишение прав"
        total_text = f"📋 Всего статей: {len(self.incriminated_articles)}\n\n" + total_text
        if breakdown and len(breakdown) <= 5:
            total_text += "\n\n📝 Детализация:\n" + "\n".join(breakdown[:5])
        self.total_label.setText(total_text)
        self.copy_text.setText(self._get_articles_summary())

    def _show_incriminated_article(self, item):
        article = item.data(Qt.ItemDataRole.UserRole)
        if not article:
            return
        penalty = article.get('selected_penalty', article.get('penalty', 'Не указано')) or 'Не указано'
        fine_amount = article.get('selected_fine', 0)
        fine_info = f"<p style='color: #ffcc00;'><b>💰 Сумма штрафа:</b> {fine_amount:,} руб.</p>" if fine_amount > 0 else ""
        html = f"""
        <h2 style="color: #ff4444;">⚖️ Инкриминировано: Статья {article['article_number']}</h2>
        <p><b>Выбранное наказание:</b> {penalty}</p>
        <hr style="border: 1px solid #333;">
        <h3>📝 Диспозиция</h3>
        <p style="line-height: 1.6;">{article['disposition']}</p>
        <h3 style="color: #ffd700; margin-top: 25px;">⚖️ Полная санкция (из НПА)</h3>
        <p style="color: #ffcc00; font-size: 16px; line-height: 1.6;">{article.get('penalty', 'Не указано')}</p>
        {fine_info}
        """
        self.detail_view.setHtml(html)
        self.incriminate_btn.setEnabled(False)
        self.incriminate_btn.setText("❌ Уже инкриминировано")

    def _show_incriminated_context_menu(self, position: QPoint):
        item = self.incriminated_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        delete_action = QAction("❌ Удалить статью", self)
        delete_action.triggered.connect(lambda: self._remove_incriminated_article(item))
        menu.addAction(delete_action)
        menu.exec(self.incriminated_list.mapToGlobal(position))

    def _remove_incriminated_article(self, item):
        article = item.data(Qt.ItemDataRole.UserRole)
        if not article:
            return
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить статью {article['article_number']} из списка?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.incriminated_articles.remove(article)
            self._update_incriminated_list()
            if self.current_article and self.current_article['article_number'] == article['article_number']:
                self._show_article_details(self.article_list.currentItem())

    def _clear_incriminated(self):
        if not self.incriminated_articles:
            return
        reply = QMessageBox.question(self, "Подтверждение", "Вы уверены, что хотите очистить весь список?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.incriminated_articles.clear()
            self._update_incriminated_list()
            if self.current_article:
                self._show_article_details(self.article_list.currentItem())

    # ---------- КОПИРОВАНИЕ ----------
    def _copy_to_clipboard(self):
        text = self.copy_text.toPlainText()
        if text and text != "Нет инкриминированных статей":
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Успех", "Текст скопирован в буфер обмена!")
        else:
            QMessageBox.warning(self, "Предупреждение", "Нет текста для копирования!")

    # ---------- СОБЫТИЯ КЛАВИАТУРЫ ----------
    def eventFilter(self, obj, event):
        if obj == self.article_list and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                current_item = self.article_list.currentItem()
                if current_item and self.incriminate_btn.isEnabled():
                    self._incriminate_current_article()
                    return True
        return super().eventFilter(obj, event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ModernNPAViewer()
    window.show()
    sys.exit(app.exec())