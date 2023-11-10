"""
Виджеты для просмотра PDF-файла
-------------------------------
Комплект виджетов для просмотра PDF-файла с возможностью выделения областей,
их копирования в буфер и т.п.

root_widget (SiaPdfView: resizeEvent, keyPressEvent, wheelEvent)
   |
   ---> board_widget (BoardWidget: mousePressEvent, mouseMoveEvent, mouseReleaseEvent)
           |
           ---> page_widget (PageWidget: paintEvent)

Заметки
=======
* Версия от 10.11.2023 (c) 2023 **Igor Stepanenkov**

Зависимости
===========
* PySide2
* PyMuPDF
* Pillow
* pytesseract
* pyzbar
"""

import logging
import os
import re
from io import BytesIO

import fitz
import pytesseract
from PIL import Image
from PIL import ImageOps
from PySide2.QtCore import QBuffer
from PySide2.QtCore import QIODevice
from PySide2.QtCore import QPoint
from PySide2.QtCore import QRectF
from PySide2.QtCore import Qt
from PySide2.QtCore import Signal
from PySide2.QtGui import QBrush
from PySide2.QtGui import QColor
from PySide2.QtGui import QGuiApplication
from PySide2.QtGui import QImage
from PySide2.QtGui import QKeyEvent
from PySide2.QtGui import QMouseEvent
from PySide2.QtGui import QPainter
from PySide2.QtGui import QPaintEvent
from PySide2.QtGui import QPalette
from PySide2.QtGui import QPen
from PySide2.QtGui import QPixmap
from PySide2.QtGui import QResizeEvent
from PySide2.QtGui import QWheelEvent
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QFrame
from PySide2.QtWidgets import QHBoxLayout
from PySide2.QtWidgets import QInputDialog
from PySide2.QtWidgets import QLabel
from PySide2.QtWidgets import QLineEdit
from PySide2.QtWidgets import QMessageBox
from PySide2.QtWidgets import QScrollArea
from PySide2.QtWidgets import QSizePolicy
from PySide2.QtWidgets import QSlider
from PySide2.QtWidgets import QSpinBox
from PySide2.QtWidgets import QWidget
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol

from selection import DIR_E
from selection import DIR_IN
from selection import DIR_N
from selection import DIR_NE
from selection import DIR_NW
from selection import DIR_OUT
from selection import DIR_S
from selection import DIR_SE
from selection import DIR_SW
from selection import DIR_W
from selection import SelectionRect


# Режимы перетаскивания мышью выделенной области или ее участка
MODE_MOVE_NONE = 0  # Обычный режим просмотра - нет перетаскивания
MODE_MOVE_CORNER = 1  # Перемещаем угол области
MODE_MOVE_ALL = 2  # Перемещаем всю область
MODE_MOVE_VERT_BORDER = 3  # Перемещаем вертикальную сторону (лево или право)
MODE_MOVE_HOR_BORDER = 4  # Перемещаем горизонтальную сторону (верх или низ)

# Действия с выделенной областью (для метода set_selection_point)
ACT_FIX_FIRST_POINT = 1  # началось выделение области, оба угла фиксируются в точке нажатия мыши
ACT_MOVE_SECOND_POINT = 2  # первый угол зафиксирован ранее, второй угол перемещается в точку курсора мыши
ACT_FIX_ANCHOR_POINT = 3  # началось перемещение всей выделенной области, фиксируем положение мыши как "точку зацепа"
ACT_MOVE_ANCHOR_POINT = 4  # выделенная область перемещается на дельту = (положение мыши - "точки зацепа"),
#  фиксируем положение мыши как новую "точку зацепа"
ACT_RESIZE_X = 5  # перемещается вертикальная сторона в положение мыши, противоположная сторона зафиксирована
ACT_RESIZE_Y = 6  # перемещается горизонтальная сторона в положение мыши, противоположная сторона зафиксирована
ACT_MOVE_MARKER = 10  # 11 - 19 - началось изменение размера выделенной области за маркер (угол или сторону),
# идентификатор маркера = nm - ACT_MOVE_MARKER


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'log.log'))
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)


def show_info_msg_box(parent, title: str, text: str):
    """
    Функция выводит окно с информационным сообщением

    Args:
        parent: объект-родитель окна
        title (str): Заголовок окна с сообщением
        text (str): Текст сообщения
    """
    m_msg_box = QMessageBox(parent)
    m_msg_box.setIcon(QMessageBox.Icon.Information)
    m_msg_box.setWindowTitle(title)
    m_msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    m_msg_box.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
    m_msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
    m_msg_box.setText(text)
    m_msg_box.exec()


def fromqimage(im):
    """
    Замена для ImageQt.fromqimage из PIL
    """
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    # preserve alpha channel with png
    # otherwise ppm is more friendly with Image.open
    if im.hasAlphaChannel():
        im.save(buffer, "png")
    else:
        im.save(buffer, "ppm")

    b = BytesIO()
    b.write(buffer.data())
    buffer.close()
    b.seek(0)

    return Image.open(b)


###########################################################################
# Дополнительные виджеты для использования в панели инструментов
###########################################################################


class PageNumberSpinBox(QSpinBox):
    """Виджет для поля выбора номера страницы"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def change_page_number(self, page_number: int):
        """Изменить в поле ввода номер страницы"""
        self.setValue(page_number + 1)

    def keyPressEvent(self, event: QKeyEvent):
        """Обработчик нажатий клавиш"""
        # Игнорируем PgUp и PgDn, чтобы не было смешения со сменой страниц
        if not event.key() in (16777238, 16777239):
            super().keyPressEvent(event)


# noinspection PyUnresolvedReferences
class ZoomSlider(QSlider):
    """Виджет слайдера для выбора масштаба просмотра страницы"""

    zoomSliderDoubleClicked = Signal()  # Сигнал при двойном клике мыши

    def __init__(self, parent):
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event: QMouseEvent):  # pylint: disable=unused-argument
        """Обработчик двойного клика мыши"""
        # Эмитируем сигнал zoomSliderDoubleClicked
        self.zoomSliderDoubleClicked.emit()


# noinspection PyUnresolvedReferences
class ZoomSelector(QWidget):
    """Виджет выбора масштаба просмотра страницы (на основе слайдера)"""

    zoom_factor_changed = Signal(float)  # Сигнал при изменении выбранного масштаба

    def __init__(self, parent):
        super().__init__(parent)
        # Устанавливаем фиксированную ширину виджета
        self.setFixedWidth(190)

        # По умолчанию будем эмитировать zoom_factor_changed при изменении масштаба
        self.is_emit = True

        # Создаем и настраиваем горизонтальный layout
        self.horizontal_layout = QHBoxLayout(self)
        self.horizontal_layout.setSpacing(5)
        self.horizontal_layout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        # Создаем виджет ZoomSlider и настраиваем его
        self.slider = ZoomSlider(self)
        self.slider.setFixedWidth(120)
        self.slider.setMinimum(20)
        self.slider.setMaximum(300)
        self.slider.setValue(100)
        self.slider.setOrientation(Qt.Horizontal)

        # Создаем виджет QLineEdit и настраиваем его
        self.lbl_value = QLineEdit(self)
        self.lbl_value.setFixedWidth(45)
        self.lbl_value.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.lbl_value.setText("100%")
        self.lbl_value.setReadOnly(True)

        # Добавляем оба виджета в layout
        self.horizontal_layout.addWidget(self.slider)
        self.horizontal_layout.addWidget(self.lbl_value)

        # Соединяем сигнал слайдера valueChanged с соответствующим обработчиком
        self.slider.valueChanged.connect(self.value_changed)
        # Соединяем сигнал слайдера zoomSliderDoubleClicked с соответствующим обработчиком
        self.slider.zoomSliderDoubleClicked.connect(self.reset)
        # Включаем доступность элементов виджета
        self.lbl_value.setEnabled(False)
        self.slider.setEnabled(False)

    def set_zoom_factor(self, zoom_factor: float):
        """Установка масштаба извне"""
        # Отключаем эмитирование сигнала zoom_factor_changed на это изменение
        self.is_emit = False
        # Устанавливаем новое значение масштаба
        self.slider.setValue(int(zoom_factor * 100))

    def reset(self):
        """Сброс масштаба в 100%"""
        self.slider.setValue(100)
        # Устанавливаем новое значение масштаба
        self.value_changed(100)

    def value_changed(self, value):
        """Обработчик изменения значения масштаба"""
        # Меняем текст с масштабом в процентах
        self.lbl_value.setText(f"{value}%")
        # Если нужно эмитировать zoom_factor_changed, то делаем это
        if self.is_emit:
            self.zoom_factor_changed.emit(value / 100.0)
        # По умолчанию будем эмитировать zoom_factor_changed при дальнейших изменениях
        self.is_emit = True

    def setDisabled(self, is_disabled: bool):
        """Устанавливаем элементы виджета недоступными в зависимости от переданного флага"""
        self.setEnabled(not is_disabled)

    def setEnabled(self, is_enabled: bool):
        """Устанавливаем элементы виджета доступными в зависимости от переданного флага"""
        self.lbl_value.setEnabled(is_enabled)
        self.slider.setEnabled(is_enabled)


###########################################################################
# Основные виджеты
###########################################################################


# noinspection PyBroadException,PyUnresolvedReferences
class SiaPdfView(QScrollArea):
    """Виджет-основная прокручиваемая область просмотра"""

    current_page_changed = Signal(int)  # Сигнал при смене страницы
    zoom_factor_changed = Signal(float)  # Сигнал при изменении масштаба
    rect_selected = Signal(bool)  # Сигнал при изменении фокуса на выделенной области
    scroll_requested = Signal(QPoint, QPoint)  # Сигнал о необходимости прокрутки экрана при изменении масштаба
    coords_text_emited = Signal(str, int)  # Сигнал при изменении координат курсора при удерживаемом Alt/е

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None  # текущий документ PDF (объект fitz)
        self._current_filename = ''  # Имя текущего файла
        self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
        self._current_page = -1  # Текущая страница документа
        self._psw = ''  # Пароль к зашифрованному документу PDF
        self._scale_factor = 1.0  # Текущий масштаб страницы
        ppi = 96
        self._dpi = ppi * 3  # DPI, используемый для рендеринга страницы документа

        zoom = self._dpi / 72
        self._matrix = fitz.Matrix(zoom, zoom)  # Матрица для рендеринга страницы документа

        self.scr_w = 0  # Экранная ширина текущей страницы документа
        self.scr_h = 0  # Экранная высота текущей страницы документа
        self.ref_w = 0  # Эталонная ширина текущей страницы документа (для масштаба х3)
        self.ref_h = 0  # Эталонная высота текущей страницы документа (для масштаба х3)

        self.selection_point1 = QPoint(0, 0)  # Координаты первого угла выделяемой области
        self.selection_point2 = QPoint(0, 0)  # Координаты второго угла выделяемой области
        self.move_point = QPoint(0, 0)  # Координаты реперной точки при изменении масштаба страницы (пытаемся
        # сохранить положение страницы неподвижным в этой точке посме смены масштаба)

        self.selected_rect = -1  # Индекс текущей выделенной области
        self.selections_max = 10000  # Максимальное количество выделенных областей
        self.selections: list[SelectionRect] = []  # Список выделенных областей на текущей странице
        self.selections_all: list[SelectionRect] = []  # Общий список выделенных областей на всех страницах

        self.move_mode = MODE_MOVE_NONE  # Текущий режим передвижения курсора мыши

        # Настраиваем корневой виджет (серый фон, без рамки, постоянная видимость скроллбаров, "фокусируемость")
        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self.setFrameStyle(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Добавляем виджет-контейнер страницы "внутрь" корневого виджета (тоже серый фон, выкл. авторесайзинг,
        # маленький размер для начала, сдвигаем в левый верчний угол корневого виджета)
        self._board_widget = BoardWidget(self)
        self._board_widget.setBackgroundRole(QPalette.ColorRole.Dark)
        self._board_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._board_widget.setFixedSize(50, 50)
        self._board_widget.move(0, 0)

        # Устанавливаем виджет-контейнер страницы основным внутренним виджетом корневого виджета
        self.setWidget(self._board_widget)

        # Добавляем виджет страницы "внутрь" виджета-контейнера (базовый цвет фона, выкл. авторесайзинг,
        # вкл. автомасштабирование содержимого - т.е. размер изображения внутри будет подстраиваться
        # под размеры самого виджета)
        self._page_widget = PageWidget(self._board_widget, self)  # передаем и ссылку на корневой виджет
        self._page_widget.setBackgroundRole(QPalette.ColorRole.Base)
        self._page_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._page_widget.setScaledContents(True)
        # self._page_widget.setStyleSheet('border:1px solid grey')  -- съедает полезное пространство...

        # Передаем виджету-контейнеру ссылку на виджет страницы
        self._board_widget.set_page_widget(self._page_widget)

        # Включаем принудительный трекинг перемещения мыши для отлова события mouseMoveEvent внутри
        # виджета-контейнера и виджета страницы
        self._board_widget.setMouseTracking(True)
        self._page_widget.setMouseTracking(True)

        # Выключаем видимость виджета-контейнра
        self._board_widget.setVisible(False)

        # Связываем сигнал scroll_requested с методом-обработчиком
        self.scroll_requested.connect(self._scroll_point_to_point)

    def combine_files(self, filelist: list):
        """Скомбинировать документ"""

        # Заранее готовим объект сообщения об ошибке
        m_msg_box = QMessageBox(self)
        m_msg_box.setIcon(QMessageBox.Icon.Question)
        m_msg_box.setWindowTitle("Ошибка открытия файла")
        m_msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.YesToAll | QMessageBox.StandardButton.Cancel
        )
        m_msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        m_msg_box.button(QMessageBox.StandardButton.Yes).setText('  Пропустить  ')
        m_msg_box.button(QMessageBox.StandardButton.YesToAll).setText('  Пропустить все  ')
        m_msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

        # Пропустить все файлы с ошибками открытия
        is_skip_all = False

        # Закрываем предыдущий файл
        self.close_file()

        # Создаем основной объект fitz.Document
        self._doc = fitz.Document()

        # Обходим список файлов
        for filename in filelist:
            try:
                # Открываем файл
                doc = fitz.Document(filename)
                # Это не PDF?
                if not doc.is_pdf:
                    # Пытаемся сконвертировать в PDF
                    pdfbytes = doc.convert_to_pdf()
                    doc.close()
                    doc = fitz.open("pdf", pdfbytes)

                # Этот документ зашифрован?
                if doc.needs_pass:
                    # Запрашиваем пароль и пытаемся открыть документ
                    self._decrypt_doc(filename, doc)

            except Exception as e:
                # Если произошла ошибка, то записываем кляузу в логи
                logger.error(filename, exc_info=True)

                # Если ранее был выбран вариант пропускать все ошибки, то идем к следующему файлу
                if is_skip_all:
                    continue

                # Выводим сообщение об ошибке с тремя вариантами ответа Пропустить-Пропустить все-Отмена
                m_msg_box.setText(f'Ошибка: {e}\nФайл: {filename}')
                res = m_msg_box.exec()
                if res == QMessageBox.StandardButton.Cancel:
                    # Пользователь выбрал отмену
                    self.close_file()
                    return

                # Если пользователь выбрал <Пропустить все>, то далее будем пропускать все ошибкифайлу
                if res == QMessageBox.StandardButton.YesToAll:
                    is_skip_all = True
                continue

            # Если файл не зашифрован (либо пароль был снят), добавляем его в основной документ
            if not doc.is_encrypted:
                self._doc.insert_pdf(doc, from_page=0, to_page=len(doc) - 1)

            # Закрываем временный объект
            doc.close()

        if len(self._doc):
            self._current_filename = '*** Результат объединения файлов ***'  # Имя текущего файла
            self._scale_factor = 1.0  # Масштаб 100%
            self._show_page(0)  # Отображаем первую страницу
            self._board_widget.setVisible(True)  # Включаем виджет-контейнер
            self.zoom_factor_changed.emit(self._scale_factor)  # Эмит сигнала zoom_factor_changed
        else:
            # Закрываем и обнуляем объект
            self._doc.close()
            self._doc = None

    def open_file(self, filename: str):
        """Открыть документ"""

        # Закрываем предыдущий файл
        self.close_file()

        # Если имя файла не передано, то выходим
        if not filename:
            return

        try:
            # Создаем основной объект fitz.Document и открываем файл
            self._doc = fitz.Document(filename)
            self._is_real_file = True  # Это настоящий файл
            self._current_filename = filename  # Имя текущего файла

            # Это не PDF?
            if not self._doc.is_pdf:
                # Пытаемся сконвертировать в PDF
                pdfbytes = self._doc.convert_to_pdf()
                self._doc.close()
                self._current_filename = '*** Новый файл ****'  # Имя текущего файла
                self._is_real_file = False  # Это виртуальный/новый файл
                self._doc = fitz.open('pdf', pdfbytes)

            # Этот документ зашифрован?
            if self._doc.needs_pass:
                # Запрашиваем пароль и пытаемся открыть документ
                self._decrypt_doc(filename, self._doc)

            # Если файл так и остался зашифрован
            if self._doc.is_encrypted:
                # Закрываем и обнуляем объект
                self._doc.close()
                self._doc = None
                self._current_filename = ''  # Имя текущего файла
                self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
                return

            self._scale_factor = 1.0  # Масштаб 100%
            self._show_page(0)  # Отображаем первую страницу
            self._board_widget.setVisible(True)  # Включаем виджет-контейнер
            self.zoom_factor_changed.emit(self._scale_factor)  # Эмит сигнала zoom_factor_changed

        except Exception as e:
            # Если произошла ошибка, то записываем кляузу в логи и выводим сообщение
            logger.error(filename, exc_info=True)
            QMessageBox.critical(self, 'Ошибка открытия файла', f'Ошибка: {e}\nФайл: {filename}')
            # Закрываем и обнуляем объект
            self._doc.close()
            self._doc = None
            self._current_filename = ''  # Имя текущего файла
            self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)

    def _decrypt_doc(self, filename: str, doc: fitz.Document) -> bool:
        """Расшифровать документ"""

        # Диалог для запроса пародя
        m_input_dlg = QInputDialog(self)
        m_input_dlg.setWindowTitle('Введите пароль')
        m_input_dlg.setLabelText(f'Для открытия файла "{filename}" требуется пароль!\nВведите пароль:')
        m_input_dlg.setOkButtonText('ОК')
        m_input_dlg.setCancelButtonText('Отмена')
        m_input_dlg.setInputMode(QInputDialog.InputMode.TextInput)
        m_input_dlg.setTextEchoMode(QLineEdit.Password)
        while True:
            # Очищаем поле ввода пароля
            m_input_dlg.setTextValue('')

            # Выводим диалог
            res = m_input_dlg.exec_()

            if res == QDialog.DialogCode.Accepted:
                # Пользователь ввел прароль
                self._psw = m_input_dlg.textValue()
                # Пытаемся его применить
                doc.authenticate(self._psw)
            else:
                # Пользователь отказался - выходим с False
                return False

            # Если документ расшифрован, то выходим с True
            if not doc.is_encrypted:
                return True

            # Документ не расшифрован, поэтому меняем сообщение и повторяем цикл
            m_input_dlg.setLabelText(
                f'Пароль открытия файла "{filename}" не верный!\nВведите правильный, либо нажмите "Отмена":'
            )

    def close_file(self):
        """Закрыть документ"""
        if self._doc is not None:
            # Закрываем и обнуляем объект
            self._doc.close()
            self._doc = None

            # Сбрасываем переменные
            self._current_filename = ''  # Имя текущего файла
            self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
            self._current_page = -1  # Текущая страница
            self.selected_rect = -1  # Текущее выделение
            self.selections = []  # Список выделений на текущей странице
            self.selections_all = []  # Список всех выделений

            # Сбрасываем виджет-контейнер в исходное состояние
            self._board_widget.setVisible(False)
            self._board_widget.setFixedSize(50, 50)
            self._board_widget.move(0, 0)

            # Очищаем виджет страницы от старого изображения
            self._page_widget.clear()

            # Эмитируем сигнал rect_selected
            self.rect_selected.emit(False)
            QApplication.processEvents()

    @property
    def doc(self):
        """Текущий документ PyMuPDF"""
        return self._doc

    @property
    def current_filename(self):
        """Имя текущего файла"""
        return self._current_filename

    @property
    def is_real_file(self):
        """Это реальный файл"""
        return self._is_real_file

    @property
    def current_page(self):
        """Текущая страница"""
        return self._current_page

    @property
    def psw(self):
        """Пароль"""
        return self._psw

    @property
    def selections_count(self):
        """Количество выделенных областей на текущей странице"""
        return len(self.selections)

    @property
    def selections_all_count(self):
        """Количество выделенных областей на всех страницах документа"""
        return len(self.selections_all)

    @property
    def page_count(self):
        """Количество страниц документа"""
        if self._doc is None:
            return 0
        return self._doc.page_count

    def goto_page(self, pno: int):
        """Переход на указанную страницу"""
        self._show_page(pno)

    def goto_next_page(self):
        """Переход на следующую страницу"""
        if self._current_page < self._doc.page_count - 1:
            self._show_page(self._current_page + 1)

    def goto_prev_page(self):
        """Переход на предыдущую страницу"""
        if self._current_page > 0:
            self._show_page(self._current_page - 1)

    def goto_home(self):
        """Переход на первую страницу"""
        if self.page_count > 0:
            self._show_page(0)

    def goto_end(self):
        """Переход на последнюю страницу"""
        if self.page_count > 0:
            self._show_page(self._doc.page_count - 1)

    def zoom_in(self):
        """Увеличить масштаб"""
        self.scale_image(1.25)

    def zoom_out(self):
        """Уменьшить масштаб"""
        self.scale_image(0.8)

    def set_zoom_factor(self, factor):
        """Установить указанный масштаб"""
        self.scale_image(1, None, factor)

    def emit_coords_text(self, pt: QPoint):
        """Генерируем сигнал об изменении координат указателя мыши"""
        # Если курсор за пределами страницы, то ничего не делаем
        if not (0 <= pt.x() <= self._page_widget.width() and 0 <= pt.y() <= self._page_widget.height()):
            return
        # Корректируем их на _scale_factor
        x = pt.x() * self.ref_w / self.scr_w
        y = pt.y() * self.ref_h / self.scr_h
        # Превращаем координаты мыши в fitz.Rect
        rc = fitz.Rect(x, y, x, y)
        # Приводим к системе координат документа (с учетом поворота страницы)
        rc = rc / self._matrix
        # Эмитируем сигнал coords_text_emited
        self.coords_text_emited.emit(f'{round(rc.x0, 2)} : {round(rc.y0, 2)}', 0)

    def copy_page_image_to_clipboard(self, is_selection: bool = False):
        """Скопировать изображение всей страницы или из текущей выделенной области в буфер обмена"""
        # Если нет текущей страницы, то сразу выходим
        if self._current_page == -1:
            return

        # Если копируем выделение, а его нет, то тоже выходим
        if is_selection and self.selected_rect == -1:
            return

        # Берем всё изображение из виджета страницы
        img = self._page_widget.pixmap().toImage()
        # Устанавливаем соответствующий DPI/DPM
        dpm = self._dpi / 0.0254
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)

        if is_selection:
            # Если копируем выделенную область, то вырезаем ее из изображения страницы
            r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
            img = img.copy(r)

        # Запихиваем изображение в буфер обмена
        QGuiApplication.clipboard().setImage(img)

    def copy_rect_text_to_clipboard(self, is_trim: bool = False):
        """Скопировать текст из текстового слоя текущей выделенной области в буфер обмена.
        Если is_trim == True, то убираем из текста лишние "пробельные" символы
        """
        # Если нет текущей страницы или нет текущего выделения, то сразу выходим
        if self._current_page == -1 or self.selected_rect == -1:
            return

        # Получаем координаты выделения
        r = self.selections[self.selected_rect].rect_ref
        rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
        # Трансформируем их в систему координат документа
        rc = rc / self._matrix
        rc = rc / self._doc[self._current_page].rotation_matrix
        # Получаем текст
        recttext = self._doc[self._current_page].get_text("text", clip=rc).rstrip()
        # Если is_trim == True, то убираем из текста лишние "пробельные" символы
        if is_trim:
            recttext = re.sub(r'\s+', ' ', recttext)

        # Текст не найден?
        if not recttext:
            show_info_msg_box(self, 'Копирование текста', 'В выделенном участке отсутствует текст в текстовом слое.')
        else:
            # Запихиваем текст в буфер обмена
            QGuiApplication.clipboard().setText(recttext)

    def recognize_and_copy_to_clipboard(self, tesseract_cmd: str, is_trim: bool):
        """Распознать текст из текущей выделенной области и скопировать его в буфер обмена.
        Если is_trim == True, то убираем из текста лишние "пробельные" символы
        """
        # Если нет текущей страницы или нет текущего выделения, то сразу выходим
        if self._current_page == -1 or self.selected_rect == -1:
            return

        # Настраиваем pytesseract
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        # Берем всё изображение из виджета страницы
        img = self._page_widget.pixmap().toImage()
        # Получаем координаты выделения
        r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
        # Вырезаем выделенную область из изображения страницы
        img = fromqimage(img.copy(r))
        img = fromqimage(img.copy(r))
        # Распознаем
        recttext = pytesseract.image_to_string(img, lang='rus+eng')
        # Если is_trim == True, то убираем из текста лишние "пробельные" символы
        if is_trim:
            recttext = re.sub(r'\s+', ' ', recttext)

        # Текст не найден?
        if not recttext:
            show_info_msg_box(self, 'Распознание текста', 'В выделенном участке не удалось распознать текст.')
        else:
            # Запихиваем текст в буфер обмена
            QGuiApplication.clipboard().setText(recttext)

    def recognize_qr_and_copy_to_clipboard(self):
        """Распознать текст из текущей выделенной области и скопировать его в буфер обмена.
        Если is_trim == True, то убираем из текста лишние "пробельные" символы
        """
        # Если нет текущей страницы или нет текущего выделения, то сразу выходим
        if self._current_page == -1 or self.selected_rect == -1:
            return

        # Берем всё изображение из виджета страницы
        img = self._page_widget.pixmap().toImage()
        # Получаем координаты выделения
        r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
        # Вырезаем выделенную область из изображения страницы
        img = fromqimage(img.copy(r))
        img = fromqimage(img.copy(r))
        # Распознаем QR коды
        decocde_qr = decode(img, [ZBarSymbol.QRCODE])
        # Если коды не найдены, пробуем инвертировать изображение
        if not decocde_qr:
            img = ImageOps.invert(img)
            # Еще раз пытаемся распознать QR коды
            decocde_qr = decode(img, [ZBarSymbol.QRCODE])

        # Если коды так и не найдены, выводим сообщение
        if not decocde_qr:
            show_info_msg_box(self, 'Распознание QR-кодов', 'Данные не распознаны.')
        else:
            # Иначе собираем все найденные коды в один текст
            txt = ''
            for qr_obj in decocde_qr:
                txt += ('\n-------------------\n' if txt else '') + qr_obj.data.decode('utf-8')

            # Запихиваем текст в буфер обмена
            QGuiApplication.clipboard().setText(txt)

    def copy_rects_info_to_clipboard(self, is_all: bool = False):
        """Скопировать информацию о выделенных областях в буфер обмена.
        Если is_all == True, то информацию берем со всех страниц, иначе - только с текущей
        """
        # Если нет текущей страницы, то сразу выходим
        if self._current_page == -1:
            return

        if is_all:
            # Если информацию берем со всех страниц, то берем список всех выделений
            sels = self.selections_all.copy()
            recttext = '№ п/п, страница, вращение: область\n'
        else:
            # иначе берем список выделений на текущей странице
            sels = self.selections.copy()
            recttext = f'Угол вращения исходной страницы: {self._doc[self._current_page].rotation}\n'
            recttext += '№ п/п, страница: область\n'

        if len(sels) == 0:  # Список выделений пуст?
            recttext = 'Нет выделенных участков!'
        else:
            # Запоминаем объект с текущим выделением
            if self.selected_rect > -1:
                selected = self.selections[self.selected_rect]
            else:
                selected = None

            # Запоминаем номер текущей страницы
            pno = self._current_page

            # Сортируем список выделений
            sels.sort(key=lambda x: (x.pno, x.rect_ref.y(), x.rect_ref.x()))

            # Обходим все выделенные области
            for i, s in enumerate(sels):
                if is_all:
                    # Если собираем информацию со всех страниц, то меняем номер страницы
                    # Все глобальные выделения перечисляются только один раз - на первой странице
                    pno = max(s.pno, 0)

                # Получаем координаты области и переводим их в систему координат страницы
                # документа (с учетом ее поворота!!!)
                r = s.rect_ref
                rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                rc = rc / self._matrix

                # Дополняем текст с информацией о номере страницы и т.п.
                recttext += f"{i + 1}{'*' if s is selected else ''}, {pno + 1}{'**' if s.pno == -1 else ''}"

                if is_all:
                    # Если собираем информацию со всех страниц, то добавляем сведения о повороте страницы
                    recttext += f", {self._doc[pno].rotation}"

                # Дополняем текст с информацией о координатах
                recttext += f": ({round(rc.x0, 2)}, {round(rc.y0, 2)}, {round(rc.x1, 2)}, {round(rc.y1, 2)})\n"

        # Запихиваем текст в буфер обмена и выводим его в сообщении
        QGuiApplication.clipboard().setText(recttext)
        show_info_msg_box(self, 'Информация о выделенных участках', recttext)

    def get_selection_fitz_rect(self, sel: SelectionRect):
        """Трансформируем координаты выделения в координаты страницы pdf документа

        Args:
            sel (SelectionRect): выделение

        Returns:
            fitz rect: прямоугольная область fitz
        """
        return (
            fitz.Rect(
                sel.rect_ref.x(),
                sel.rect_ref.y(),
                sel.rect_ref.x() + sel.rect_ref.width(),
                sel.rect_ref.y() + sel.rect_ref.height(),
            )
            / self._matrix
        )

    def add_selection(self, pno: int, rect):
        """Добавить выделенную область

        Args:
            pno (int): номер страницы
            rect (_type_): прямоугольная область в экранной системе координат,
                           которая будет добавлена в качестве выделенной области
        """
        # Создаем новый объект SelectionRect
        sel = SelectionRect(pno)
        # Трансформируем экранные координаты в "эталонные"
        rotated_rect = (rect * self._doc[pno].rotation_matrix) * self._matrix
        # Нормализируем углы прямоугольника
        rotated_rect.normalize()
        # Устанавливаем "эталонные" координаты выделенной области
        sel.rect_ref.setCoords(rotated_rect.x0, rotated_rect.y0, rotated_rect.x1, rotated_rect.y1)
        # Добавляем объект в общий список выделений на всех страницах
        self.selections_all.append(sel)

        # Если добавляемое выделение не находится на текущей странице и не глобальное, то выходим
        if pno != self._current_page and pno != -1:
            return

        # Приводим "эталонные" координаты в экранные с проверкой на вместимость в страницу
        sel.update_rect(self.scr_w, self.scr_h, self.ref_w, self.ref_h)
        # Добавляем объект в список выделений текущей страницы
        self.selections.append(sel)
        # Обновляем экран
        self._page_widget.update()

    def switch_rect_mode(self):
        """Переключить признак глобальности выделения"""
        # Если нет текущей страницы или нет текущего выделения, то сразу выходим
        if self._current_page == -1 or self.selected_rect == -1:
            return

        # Меняем признак глобальности выделения
        self.selections[self.selected_rect].pno = (
            self._current_page if self.selections[self.selected_rect].pno == -1 else -1
        )

        # Обновляем экран
        self._page_widget.update()

    def rotate_pages(self, rotation_dir: int, is_all: bool):
        """Вращение страницы/всех страниц

        Args:
            rotation_dir (int): индекс значения переворота (0 - нет вращения,
                                1 - против часовой на 90, 2 - по часовой на 90,
                                3 - перевернуть на 180)
            is_all (bool): повернуть все страницы, иначе - только текущую
        """
        # Если нет текущей страницы, то сразу выходим
        if self._current_page == -1:
            return

        # Задаем индексы первой и последней страницы для переворота
        if is_all:
            pno = 0
            pno_end = len(self._doc) - 1
        else:
            pno = self._current_page
            pno_end = pno

        # Переворачиваем все страницы в цикле
        while pno <= pno_end:
            # Сохраняем матрицу рендеринга для старой ориентации страницы
            src_rot_mat = self._doc[pno].rotation_matrix * self._matrix
            # Поворачиваем страницу документа в объекте fitz
            self._doc[pno].set_rotation((self._doc[pno].rotation + (0, 270, 90, 180)[rotation_dir]) % 360)
            # Сохраняем матрицу рендеринга для новой ориентации страницы
            dst_rot_mat = self._doc[pno].rotation_matrix * self._matrix
            # В цикле трансформируем все выделения, которые были привязаны к странице, в т.ч. "глобальные"
            for sel in self.selections_all:
                # Глобальные выделения трансформируются только один раз - на текущей странице
                if sel.pno == pno or (sel.pno == -1 and pno == self._current_page):
                    # Получаем старые "эталонные" координаты выделения в fitz rect
                    r = sel.rect_ref
                    rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                    # Трансформируем координаты, применяя старую и новую матрицы
                    rc = (rc / src_rot_mat) * dst_rot_mat
                    # Сохраняем новые "эталонные" координаты выделения
                    r.setRect(rc.x0, rc.y0, rc.x1 - rc.x0, rc.y1 - rc.y0)
            # Индекс следующей страницы
            pno += 1

        # Обновляем отображение страницы
        self._show_page(self._current_page, True)

    def select_all(self):
        """Создать выделение всей страницы"""
        # Если нет текущей страницы, то сразу выходим
        if self._current_page == -1:
            return

        # Формируем прямоугольную область, соответствующую всей странице
        max_rect = QRectF(0, 0, self.ref_w, self.ref_h)
        # В цикле проверяем все уже выделенные области на текущей странице
        for sel in self.selections:
            # Если такая область уже выделена, то фокусируемся на ней и выходим из цикла
            if sel.rect_ref == max_rect:
                self.selected_rect = self.selections.index(sel)
                break
        else:
            # "Фокусируемся" на новой выделенной области
            self.selected_rect = len(self.selections)
            # Создаем объект для новой выделенной области
            new_sel = SelectionRect(self._current_page)
            # Устанавливаем ее "эталонные" координаты
            new_sel.rect_ref = max_rect
            # Пересчитываем "эталонные" координаты в экранные
            new_sel.update_rect(self.scr_w, self.scr_h, self.ref_w, self.ref_h)

            # Добавляем новое выделение в список выделений на текущей странице
            self.selections.append(new_sel)
            # Добавляем новое выделение в общий список выделений на всех страницах
            self.selections_all.append(new_sel)

        # Обновляем экран
        self._page_widget.update()
        # Эмитируем сигнал об изменении фокуса на выделенной области
        self.rect_selected.emit(True)

    def remove_selection(self, is_remove_all=False):
        """Снять текущую выделенную область / все выделенные области (на всех страницах!!!)

        Args:
            is_remove_all (bool, optional): Признак снятия всех выделений (на всех страницах!!!). Defaults to False.
        """
        # Если нет текущей страницы, то сразу выходим
        if self._current_page == -1:
            return

        # Если снимаем все выделения
        if is_remove_all:
            # то очищаем полностью оба списка выделенных областей
            self.selections.clear()
            self.selections_all.clear()
        else:
            # Если нет текущего выделения, то выходим
            if self.selected_rect == -1:
                return
            # Ищем индекс удаляемого выделения в общем списке выделенных областей
            ind = self.selections_all.index(self.selections[self.selected_rect])
            # Удаляем элемент списка в общем списке выделенных областей
            self.selections_all.pop(ind)
            # Удаляем элемент списка в списке выделенных областей текущей страницы
            self.selections.pop(self.selected_rect)

        # Снимаем фокус с выделенной области (если был)
        self.selected_rect = -1
        # Обновляем экран
        self._page_widget.update()
        # Эмитируем сигнал об изменении фокуса на выделенной области
        self.rect_selected.emit(True)

    def _scroll_point_to_point(self, src_pt: QPoint, dest_pt: QPoint):
        """Попытаться прокрутить содержимое корневого виджета так, чтобы точка из системы координат страницы src_pt
           оказалась в точке dest_pt системы координат корневого виджета

        Args:
            src_pt (QPoint): точка из системы координат страницы
            dest_pt (QPoint): точка в системе координат корневого виджета
        """
        # Переводим точку src_pt в систему координат корневого виджета
        src_pt = self._board_widget.mapToParent(self._page_widget.mapToParent(src_pt))

        # Тупо сдвигаем содержимое корневого виджета на разницу в координатах
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + src_pt.x() - dest_pt.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + src_pt.y() - dest_pt.y())

    def _set_sizes(self):
        """Изменяем размер виджета-контейнера страницы"""
        # Определяем размер виджета-контейнера страницы исходя из размера виджета страницы + 20px, а
        # если полученная высота или ширина меньше высоты или ширины вьюпорта корневого контейнера,
        # то соответствующие размеры берем от вьюпорта корневого контейнера
        ww = max(self.viewport().width(), self._page_widget.width() + 20)
        hh = max(self.viewport().height(), self._page_widget.height() + 20)
        # Записываем полученные значения в размеры виджета-контейнера страницы
        self._board_widget.setFixedHeight(hh)
        self._board_widget.setFixedWidth(ww)
        # Сдвигаем виджет страницы внутри виджета-контейнера по горизонтали так, чтобы слева от
        # страницы был margin минимум 10 px, а при мелких масштабах, чтобы страница была по центру вьюпорта
        self._page_widget.move((ww - self._page_widget.width()) // 2, 10)

    def _show_page(self, pno: int, is_force: bool = False):
        """Показать страницу документа

        Args:
            pno (int): индекс страницы
            is_force (bool, optional): перерисовать страницу в любом случае, иначе - только если
                                       она не была текущей. Defaults to False.
        """
        # Если индекс страницы совпадает с текущей и не стоит признак перерисовывать всегда, то выходим
        if self._current_page == pno and not is_force:
            return

        # Устанавливаем переданный индекс в качестве текущей страницы
        self._current_page = pno
        # Рендерим изображение
        pix = self._doc[pno].get_pixmap(alpha=False, matrix=self._matrix, colorspace=fitz.csRGB)

        # Переводим изображение в QImage
        new_image = QImage(pix.samples_mv, pix.width, pix.height, pix.width * 3, QImage.Format_RGB888)

        # Запоминаем "эталонные" размеры страницы текущей документа
        self.ref_w = pix.width
        self.ref_h = pix.height

        # Устанавливаем новое изображение страницы
        self._page_widget.setPixmap(QPixmap.fromImage(new_image))

        # Изменяем экранный размер отображения страницы исходя из установленного масштаба
        # при обычном отображении страницы выделенные области не пересчитываем, а если форс - то
        # обновляем и их экранные координаты
        self._update_size(is_force)

        # Дальнейшие действия не нужны для форс - режима
        if is_force:
            return

        # Сбрасываем фокус с выделенной области (если он был)
        self.selected_rect = -1
        # Перезаполняем список выделенных областей на текущей странице
        self.selections = [sel for sel in self.selections_all if sel.pno in (-1, pno)]

        # В цикле пересчитываем "эталонные" координаты выделенных областей в экранные
        for sel in self.selections:
            sel.update_rect(self.scr_w, self.scr_h, self.ref_w, self.ref_h)

        # Эмитируем сигнал об изменении фокуса на выделенной области
        self.rect_selected.emit(False)
        # Эмитируем сигнал об изменении страницы
        self.current_page_changed.emit(pno)

    def _update_size(self, is_update_selections: bool = True):
        """Обновляем экранный размер отображения страницы исходя из установленного масштаба

        Args:
            is_update_selections (bool, optional): обновить экранные размеры выделенных областей. Defaults to True.
        """
        # Определяем размеры отображения страницы на экране исходя из текущего масштаба
        new_size = self._scale_factor / 3 * self._page_widget.pixmap().size()
        # Устанавливаем размеры отображения страницы на экране
        self._page_widget.resize(new_size)
        # Изменяем размер виджета-контейнера страницы
        self._set_sizes()
        # Запоминаем экранные размеры страницы текущей документа
        self.scr_w = new_size.width()
        self.scr_h = new_size.height()

        # Выходим, если не надо обновлять экранные размеры выделенных областей
        if not is_update_selections:
            return

        # Обновляем экранные размеры выделенных областей исходя из "эталонных" значений
        for sel in self.selections:
            sel.update_rect(self.scr_w, self.scr_h, self.ref_w, self.ref_h)

    def scale_image(self, factor, wheel_mouse_pos=None, newscale=1.0):
        """Масштабировать изображение страницы

        Args:
            factor: множитель, который необходимо применить к текущему масштабу. Если 1, то устанавливаем 100%.
            wheel_mouse_pos (optional): позиция курсора мыши при прокручивании колесика. Defaults to None.
            newscale (float, optional): новый масштаб, если factor не равен 1. Defaults to 1.0.
        """
        # Если это не переход на 100%, то рассчитываем новый масштаб
        if factor != 1:
            newscale = self._scale_factor * factor

        # Если новый масштаб вылезает за допустимые рамки, то ограничиваем его
        if newscale < 0.2:
            newscale = 0.2
        elif newscale > 3.0:
            newscale = 3.0
        elif 0.95 < newscale < 1.1:  # близкие к единице значения округляем до 100%
            newscale = 1.0

        # Если масштаб не изменился - то выходим
        if self._scale_factor == newscale:
            return

        # Обратным счетом определяем множитель изменения масштаба
        factor = newscale / self._scale_factor
        # Сохраняем значение нового масштаба
        self._scale_factor = newscale

        # Если это не увеличение колесиком мышки, то реперную точку ставим в левый верхний угол корневого виджета
        if wheel_mouse_pos is None:
            dest_point = QPoint(0, 0)
        else:
            # иначе реперную точку ставим в позицию курсора относительно корневого виджета
            dest_point = wheel_mouse_pos

        # destPoint - это "якорная" точка относительно левого верхнего угла корневого виджета
        # srcPoint - это "якорная" точка относительно левого верхнего угла виджета страницы документа
        src_point = self._page_widget.mapFromParent(self._board_widget.mapFromParent(dest_point))
        # приводим srcPoint к новому масштабу (это будет координата, которую нужно подставить под курсор мыши)
        src_point.setX(src_point.x() * factor)
        src_point.setY(src_point.y() * factor)

        # Изменяем экранный размер отображения страницы исходя из установленного масштаба
        self._update_size()

        # Эмитируем сигнал об изменении масштаба
        self.zoom_factor_changed.emit(self._scale_factor)
        # Эмитируем сигнал о необходимости сдвинуть содержимое корневого виджета исходя из двух переданных координат
        self.scroll_requested.emit(src_point, dest_point)

    def set_selection_points(self, pt: QPoint, nm: int):
        """Установить координаты текущей выделенной области в соответствии с переданной координатой положения
        курсора мыши и идентификатором выполняемого действия (вызывается из mousePressEvent и mouseMoveEvent)

        ACT_FIX_FIRST_POINT - 1 - началось выделение области, оба угла фиксируются в точке нажатия мыши pt

        ACT_MOVE_SECOND_POINT - 2 - первый угол зафиксирован ранее, второй угол перемещается в точку pt

        ACT_FIX_ANCHOR_POINT - 3 - началось перемещение всей выделенной области, фиксируем pt как "точку зацепа"

        ACT_MOVE_ANCHOR_POINT - 4 - выделенная область перемещается на дельту = (pt - "точки зацепа"),
                                    pt фиксируем как новую "точку зацепа"

        ACT_RESIZE_X - 5 - перемещается вертикальная сторона в pt.x(), противоположная сторона зафиксирована

        ACT_RESIZE_Y - 6 - перемещается горизонтальная сторона в pt.y(), противоположная сторона зафиксирована

        > ACT_MOVE_MARKER - [11 - 19] - началось изменение размера выделенной области за маркер (угол или сторону),
                                        идентификатор маркера = nm - ACT_MOVE_MARKER

        Args:
            pt (QPoint): положение указателя мыши в системе координат виджета страницы документа
            nm (int): идентификатор действия
        """
        # Начали перемещать маркер?
        if nm > ACT_MOVE_MARKER:
            # Определяем какой именно маркер перемещается
            nm -= ACT_MOVE_MARKER
            # Сохраняем ссылку на объект с выделенной областью в переменную с коротким именем
            r = self.selections[self.selected_rect]

            # Перемещается один из угловых маркеров?
            if nm in (DIR_NW, DIR_NE, DIR_SW, DIR_SE):
                # Фиксируем в selection_point1 координаты противоположного угла
                if nm == DIR_NW:  # левый верхний угол
                    self.selection_point1 = QPoint(r.x2, r.y2)
                elif nm == DIR_NE:  # правый верхний угол
                    self.selection_point1 = QPoint(r.x1, r.y2)
                elif nm == DIR_SW:  # левый нижний угол
                    self.selection_point1 = QPoint(r.x2, r.y1)
                elif nm == DIR_SE:  # правый нижний угол
                    self.selection_point1 = QPoint(r.x1, r.y1)
                # Меняем действие на перемещение второго угла
                nm = ACT_MOVE_SECOND_POINT

            # Перемещается маркер, расположенный на середине верхней или левой стороны?
            elif nm in (DIR_N, DIR_W):
                # Фиксируем в selection_point1 координаты неподвижного правого нижнего угла,
                # а selection_point2 координаты перемещаемого левого верхнего угла
                self.selection_point1 = QPoint(r.x2, r.y2)
                self.selection_point2 = QPoint(r.x1, r.y1)
                # Меняем действие на ресайз по X или Y
                nm = ACT_RESIZE_X if nm == DIR_W else ACT_RESIZE_Y

            # Перемещается маркер, расположенный на середине нижней или правой стороны?
            elif nm in (DIR_E, DIR_S):
                # Фиксируем в selection_point1 координаты неподвижного левого верхнего угла,
                # а selection_point2 координаты перемещаемого правого нижнего угла
                self.selection_point1 = QPoint(r.x1, r.y1)
                self.selection_point2 = QPoint(r.x2, r.y2)
                # Меняем действие на ресайз по X или Y
                nm = ACT_RESIZE_X if nm == DIR_E else ACT_RESIZE_Y

        # Корректируем положение точки курсора мыши так, чтобы она находилась в пределах страницы
        pt.setX(min(max(pt.x(), 0), self._page_widget.width() - 1))
        pt.setY(min(max(pt.y(), 0), self._page_widget.height() - 1))

        # Если выделение только создается (ACT_FIX_FIRST_POINT) или уже ресайзится (остальные варианты), то...
        if nm in (ACT_FIX_FIRST_POINT, ACT_MOVE_SECOND_POINT, ACT_RESIZE_X, ACT_RESIZE_Y):
            if nm == ACT_FIX_FIRST_POINT:
                # Выделение только создается, поэтому оба угла области выделения фиксируем в точке курсора
                self.selection_point1 = pt
                self.selection_point2 = pt
            else:
                if nm == ACT_MOVE_SECOND_POINT:
                    # Угол selection_point1 уже был зафиксирован ранее, а сейчас меняем
                    # положение угла selection_point2
                    self.selection_point2 = pt
                elif nm == ACT_RESIZE_X:
                    # Угол selection_point1 уже был зафиксирован ранее, а сейчас меняем
                    # положение "противоположной" вертикальной стороны
                    self.selection_point2.setX(pt.x())
                elif nm == ACT_RESIZE_Y:
                    # Угол selection_point1 уже был зафиксирован ранее, а сейчас меняем
                    # положение "противоположной" горизонтальной стороны
                    self.selection_point2.setY(pt.y())

                # Переводим координаты точки из системы координат виджета страницы документа
                # в систему координат виджета-контейнера
                p_pt = self._page_widget.mapToParent(pt)
                # Пытаемся "прокрутить" содержимое корневого виджета, чтобы точка p_pt дочернего виджета была видна
                self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)

            # Обновляем координаты выделенной области в объекте из списка выделенных областей текущей страницы
            self.selections[self.selected_rect].set_x1y1_x2y2(self.selection_point1, self.selection_point2)
            # Обновляем экран
            self._page_widget.update()
            # С этими действиями все...
            return

        # Если началось перемещение всей выделенной области, фиксируем pt как "точку зацепа" и выходим
        if nm == ACT_FIX_ANCHOR_POINT:
            self.move_point = pt
            return

        # Остался последний вариант - ACT_MOVE_ANCHOR_POINT, если это вдруг не он, то выходим
        if nm != ACT_MOVE_ANCHOR_POINT:
            return

        # Определяем на какие дельты по x и y сдвинулись по сравнению с предыдущим положением
        dx = pt.x() - self.move_point.x()
        dy = pt.y() - self.move_point.y()

        # Смещаем экранные координаты текущего выделения в соответствии с дельтами смещения курсора мыши
        r = self.selections[self.selected_rect]
        r.rect.adjust(dx, dy, dx, dy)

        # Проверяем, укладывается ли теперь смещенная выделенная область в размеры страницы,
        # если нет - немного сдвигаем обратно, чтобы вернуть на страницу, и сохраняем эту дельту в dx и dy
        dx, dy = r.adjust_position(self._page_widget.width(), self._page_widget.height())

        # Переводим координаты точки из системы координат виджета страницы документа
        # в систему координат виджета-контейнера
        p_pt = self._page_widget.mapToParent(pt)

        # Выехали за пределы страницы?
        if dx or dy:
            # Если так, то корректируем положение новой "точки зацепа" на дельту "выезда" за пределы страницы
            pt.setX(pt.x() - dx)
            pt.setY(pt.y() - dy)

        # Фиксируем pt как новую "точку зацепа"
        self.move_point = pt

        # Пытаемся "прокрутить" содержимое корневого виджета, чтобы точка p_pt дочернего виджета была видна
        self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)

        # Обновляем экран
        self._page_widget.update()

    ###########################################################################
    # Обработчики событий
    ###########################################################################
    def resizeEvent(self, event: QResizeEvent):
        """Обработчик изменения размеров экрана"""
        super().resizeEvent(event)
        # Если есть открытый файл, то запускаем _set_sizes
        if self._current_page != -1:
            self._set_sizes()

    def keyPressEvent(self, event: QKeyEvent):
        """Обработчик нажатия клавиши клавиатуры"""
        key = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shft = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        alt = event.modifiers() & Qt.KeyboardModifier.AltModifier

        # Игнорируем нажатия PageUp и PageDown
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            return

        # Нажатие на Enter, Return, Space - смена фокуса между выделениями
        if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space):
            # есть выделения?
            if self.selections:
                # нажат Shift?
                if shft:
                    # перемещаем фокус на предыдущее выделение (по кругу)
                    if self.selected_rect <= 0:
                        self.selected_rect = len(self.selections)
                    self.selected_rect -= 1
                else:
                    # перемещаем фокус на следующее выделение (по кругу)
                    self.selected_rect += 1
                    if self.selected_rect == len(self.selections):
                        self.selected_rect = 0

                # Эмитируем сигнал rect_selected
                self.rect_selected.emit(True)

                # Смещаем изображение, чтобы был виден левый верхний угол фокусного выделения
                p_pt = self._page_widget.mapToParent(self.selections[self.selected_rect].rect.topLeft())
                self.ensureVisible(p_pt.x(), p_pt.y(), 50, 50)

                # Обновляем экран
                self._page_widget.update()

            # Выходим из обработки Key_Enter, Key_Return, Key_Space
            return

        # Если фокус не находится на выделении, то выполняем стандартные процедуры и выходим
        if self.selected_rect == -1:
            super().keyPressEvent(event)
            return

        # Нажата клавиша Alt?
        if alt:
            # прокручиваем содержимое виджета в зависимости от нажатой клавиши и выходим
            if key == Qt.Key.Key_Left:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Right:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
            elif key == Qt.Key.Key_Up:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Down:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 10)
            return

        ensure_visible_x = ensure_visible_y = 0  # координаты по X и Y, которые должны стать видны

        if key == Qt.Key.Key_Left:  # "влево" без и с Ctrl и Shift
            ensure_visible_x = (
                -self.selections[self.selected_rect]
                .shift_x(-1 if ctrl else -10, shft, self._page_widget.width(), self._page_widget.height())
                .x2
            )  # обеспечиваем видимость правой стороны

        elif key == Qt.Key.Key_Right:  # "вправо" без и с Ctrl и Shift
            if shft:
                ensure_visible_x = (
                    self.selections[self.selected_rect]
                    .shift_x(1 if ctrl else 10, shft, self._page_widget.width(), self._page_widget.height())
                    .x2
                )  # обеспечиваем видимость правой стороны
            else:
                ensure_visible_x = (
                    self.selections[self.selected_rect]
                    .shift_x(1 if ctrl else 10, shft, self._page_widget.width(), self._page_widget.height())
                    .x1
                )  # обеспечиваем видимость левой стороны

        elif key == Qt.Key.Key_Up:  # "вверх" без и с Ctrl и Shift
            ensure_visible_y = (
                -self.selections[self.selected_rect]
                .shift_y(-1 if ctrl else -10, shft, self._page_widget.width(), self._page_widget.height())
                .y2
            )  # обеспечиваем видимость нижней стороны

        elif key == Qt.Key.Key_Down:  # "вниз" без и с Ctrl и Shift
            if shft:
                ensure_visible_y = (
                    self.selections[self.selected_rect]
                    .shift_y(1 if ctrl else 10, shft, self._page_widget.width(), self._page_widget.height())
                    .y2
                )  # обеспечиваем видимость нижней стороны
            else:
                ensure_visible_y = (
                    self.selections[self.selected_rect]
                    .shift_y(1 if ctrl else 10, shft, self._page_widget.width(), self._page_widget.height())
                    .y1
                )  # обеспечиваем видимость верхней стороны

        else:  # все остальные клавиши обрабатываем в стандартном порядке
            super().keyPressEvent(event)
            return

        # Определяем границы вьюпорта
        vp_top_left = self._board_widget.mapFromParent(QPoint(0, 0))
        vp_x_min = vp_top_left.x() + 20
        vp_y_min = vp_top_left.y() + 20
        vp_x_max = vp_top_left.x() + self.viewport().width() - 21
        vp_y_max = vp_top_left.y() + self.viewport().height() - 21

        # Есть координата по X, которой необходимо обеспечить видимость?
        if ensure_visible_x and (
            ensure_visible_x > vp_x_max or (ensure_visible_x < 0 and -ensure_visible_x < vp_x_min)
        ):
            # обеспечиваем видимость по X
            self.ensureVisible(abs(ensure_visible_x), vp_y_min, 20, 0)

        # Есть координата по Y, которой необходимо обеспечить видимость?
        if ensure_visible_y and (
            ensure_visible_y > vp_y_max or (ensure_visible_y < 0 and -ensure_visible_y < vp_y_min)
        ):
            # обеспечиваем видимость по Y
            self.ensureVisible(vp_x_min, abs(ensure_visible_y), 0, 20)

        # Обновляем координаты выделения
        self.selections[self.selected_rect].update_rect_ref(self.scr_w, self.scr_h, self.ref_w, self.ref_h)

        # Обновляем экран
        self._page_widget.update()

    def wheelEvent(self, event: QWheelEvent):
        """Обработчик прокрутки колесика мыши"""

        # Alt переворачивает координату с Y на X
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            # Занчение угла прокрутки
            val = event.angleDelta().x()
            delta = 500
        else:
            # Занчение угла прокрутки
            val = event.angleDelta().y()
            delta = 50

        # Прокрутка с зажатым Ctrl/ом
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if val > 0:
                # Увеличиваем масштаб
                self.scale_image(1.25, event.pos())
            elif val < 0:
                # Уменьшаем масштаб
                self.scale_image(0.8, event.pos())
            return

        # Если прокрутка с зажатыми Shift, то прокручиваем страницу по горизонтали
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if val > 0:
                # Прокручивание страницы влево
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
            elif val < 0:
                # Прокручивание страницы вправо
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta)
            return

        # Прокрутка без зажатых кнопок или с Alt
        before = self.verticalScrollBar().value()
        if val > 0:
            # Прокручивание страницы вверх
            self.verticalScrollBar().setValue(before - delta)
            if before != self.verticalScrollBar().value() or self._current_page == 0:
                return
            # Перелистывание страницы назад
            self.goto_prev_page()
            # Перкручиваем на конец страницы
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        elif val < 0:
            # Прокручивание страницы вниз
            self.verticalScrollBar().setValue(before + delta)
            if before != self.verticalScrollBar().value() or self._current_page == self.page_count - 1:
                return
            # Перелистывание страницы вперед
            self.goto_next_page()
            # Перкручиваем на начало страницы
            self.verticalScrollBar().setValue(0)
        return


# noinspection PyProtectedMember,PyUnresolvedReferences
class BoardWidget(QWidget):
    """Виджет-контейнер для размещения внутри него страницы документа,
    обеспечения отступов между страницей документа и основной областью просмотра.
    """

    def __init__(self, parent: SiaPdfView = None):
        super().__init__(parent)
        self._root_widget = parent  # корневой виджет
        self._page_widget = None  # виджет страницы
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_page_widget(self, page_widget):
        """Установить ссылку на виджет страницы"""
        self._page_widget = page_widget

    ###########################################################################
    # Обработчики событий
    ###########################################################################
    def mousePressEvent(self, event: QMouseEvent):
        """Обработчик нажатия кнопки мыши"""

        # Если это не левая и не правая кнопка, то выполняем стандартную обработку и выходим
        # Правую кнопку обрабатываем потому, что перед открытием контекстного меню необходимо
        # сменить фокус на элемент под курсором мыши
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            super().mousePressEvent(event)
            return

        # Корневой виджет
        m_root_widget = self._root_widget

        # Определяем положение мыши в системе координат страницы документа
        pt = self._page_widget.mapFromParent(event.pos())

        # Есть фокус на выделении?
        if m_root_widget.selected_rect >= 0:
            # Получаем координаты выделения с фокусом
            r = m_root_widget.selections[m_root_widget.selected_rect]
            # Проверяем как соотносится положение мыши с выделенной областью
            dir_rect = r.get_dir_rect(pt)
            if event.button() == Qt.MouseButton.LeftButton and dir_rect == DIR_IN:  # левая кнопка внутри
                # Переходим в режим перемещения
                m_root_widget.move_mode = MODE_MOVE_ALL
                # "Захватываем" якорную точку
                m_root_widget.set_selection_points(pt, ACT_FIX_ANCHOR_POINT)

            elif dir_rect == DIR_OUT:  # левая или правая кнопка снаружи
                # Снимаем фокус с выделенной области
                m_root_widget.selected_rect = -1
                # Эмитируем сигнал rect_selected
                m_root_widget.rect_selected.emit(False)
                # Обновляем экран
                self._page_widget.update()

            elif event.button() == Qt.MouseButton.LeftButton:  # остальные варианты для левой кнопки
                # Переходим в режим изменения размера
                if dir_rect in (DIR_W, DIR_E):  # на середине вертикальных сторон
                    m_root_widget.move_mode = MODE_MOVE_VERT_BORDER
                elif dir_rect in (DIR_N, DIR_S):  # на середине горизонтальных сторон
                    m_root_widget.move_mode = MODE_MOVE_HOR_BORDER
                else:  # на углах
                    m_root_widget.move_mode = MODE_MOVE_CORNER

                # "Захватываем" передвигаемую точку
                m_root_widget.set_selection_points(pt, ACT_MOVE_MARKER + dir_rect)

                # Меняем форму курсора на крест
                self.setCursor(Qt.CursorShape.CrossCursor)

        # Нет (или не стало) фокуса на выделении?
        if m_root_widget.selected_rect == -1:
            # Перебираем все выделения на странице
            for i, r in enumerate(m_root_widget.selections):
                # Проверяем как соотносится положение мыши с выделенной областью
                dir_rect = r.get_dir_rect(pt)
                if dir_rect == DIR_IN:  # внутри
                    # Устанавливаем фокус на эту выделенную область
                    m_root_widget.selected_rect = i
                    # Эмитируем сигнал rect_selected
                    m_root_widget.rect_selected.emit(True)

                    # Если это правая кнопка, то обновляем экран с новым фокусом
                    if event.button() == Qt.MouseButton.RightButton:
                        self._page_widget.update()
                        break

                    # Переходим в режим перемещения
                    m_root_widget.move_mode = MODE_MOVE_ALL
                    # "Захватываем" якорную точку
                    m_root_widget.set_selection_points(pt, ACT_FIX_ANCHOR_POINT)
                    # Меняем форму курсора на крест
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    break

        # Если это правая кнопка, то выполняем стандартную обработку и выходим
        if event.button() == Qt.MouseButton.RightButton:
            super().mousePressEvent(event)
            return

        # Все еще нет фокуса на выделении?
        if m_root_widget.selected_rect == -1:
            # Если достигли максимума количества выделений, то выполняем стандартную обработку и выходим
            if len(m_root_widget.selections_all) >= m_root_widget.selections_max:
                super().mousePressEvent(event)

            # Устанавливаем фокус на новую выделенную область
            m_root_widget.selected_rect = len(m_root_widget.selections)
            # Создаем объект для новой выделенной области (с Ctrl - глобальное выделение)
            newsel = SelectionRect(
                -1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else m_root_widget.current_page
            )
            # Добавляем новую выделенную область в списки
            m_root_widget.selections.append(newsel)
            m_root_widget.selections_all.append(newsel)
            # Переходим в режим перемещения угла
            m_root_widget.move_mode = MODE_MOVE_CORNER
            # "Фиксируем" начальный угол нового выделения
            m_root_widget.set_selection_points(pt, ACT_FIX_FIRST_POINT)
            # Меняем форму курсора на крест
            self.setCursor(Qt.CursorShape.CrossCursor)
            # Эмитируем сигнал rect_selected
            m_root_widget.rect_selected.emit(True)

        # Выполняем стандартную обработку и выходим
        super().mousePressEvent(event)

    def set_cursor_shape(self, pt: QPoint):
        """Установка формы курсора мыши в зависимости от того, что под ним"""
        # По умолчанию такое вот значение
        cursor_shape = Qt.CursorShape.BlankCursor

        # Перебираем все выделенные области
        for i, r in enumerate(self._root_widget.selections):
            # Определяем местоположение указателя мыши по отношению к этой выделенной области
            dir_rect = r.get_dir_rect(pt)

            # Если указательза пределами выделенной области, то пропускаем итерацию
            if dir_rect == DIR_OUT:
                continue

            # Это активная выделенная область?
            if i == self._root_widget.selected_rect:
                # Выбираем вид курсора в зависимости от участка, где находится указатель мыши
                cursor_shape = (
                    Qt.CursorShape.SizeFDiagCursor,  # NW
                    Qt.CursorShape.SizeVerCursor,  # N
                    Qt.CursorShape.SizeBDiagCursor,  # NE
                    Qt.CursorShape.SizeHorCursor,  # W
                    Qt.CursorShape.SizeAllCursor,  # IN
                    Qt.CursorShape.SizeHorCursor,  # E
                    Qt.CursorShape.SizeBDiagCursor,  # SW
                    Qt.CursorShape.SizeVerCursor,  # S
                    Qt.CursorShape.SizeFDiagCursor,  # SE
                )[dir_rect - 1]

                # Прекращаем обход
                break

            # Если под указателем нашлась какая-нибудь неактивная выделенная область,
            # то меняем значение по умолчанию на PointingHandCursor
            if dir_rect == DIR_IN:
                cursor_shape = Qt.CursorShape.PointingHandCursor

        # Если ничего не подошло, то сбрасываем форму курсора
        if cursor_shape == Qt.CursorShape.BlankCursor:
            self.unsetCursor()
        else:
            # иначе устанавливаем найденный вариант
            self.setCursor(cursor_shape)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Обработчик перемещения мыши"""

        # Определяем положение мыши в системе координат страницы документа
        pt = self._page_widget.mapFromParent(event.pos())

        # Не находимся в режиме перемещения или изменения размера выделенной области?
        if self._root_widget.move_mode == MODE_MOVE_NONE:
            self.set_cursor_shape(pt)  # меняем форму курсора, если нужно
            # Если нажат Alt, то выводим координаты в системе координат документа (с учетом поворота страницы)
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                # Обрабатываем движение мыши с нажатым Alt
                self._root_widget.emit_coords_text(pt)

        elif self._root_widget.move_mode == MODE_MOVE_CORNER:  # двигаем угол
            self._root_widget.set_selection_points(pt, ACT_MOVE_SECOND_POINT)

        elif self._root_widget.move_mode == MODE_MOVE_ALL:  # двигаем всю область
            self._root_widget.set_selection_points(pt, ACT_MOVE_ANCHOR_POINT)

        elif self._root_widget.move_mode == MODE_MOVE_VERT_BORDER:  # двигаем вертикальные стороны
            self._root_widget.set_selection_points(pt, ACT_RESIZE_X)

        elif self._root_widget.move_mode == MODE_MOVE_HOR_BORDER:  # двигаем горизонтальные стороны
            self._root_widget.set_selection_points(pt, ACT_RESIZE_Y)

        # Вызываем обработчик родительского класса
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Обработчик отпускания кнопки мыши"""

        # Отпущена левая кнопка
        if event.button() == Qt.MouseButton.LeftButton:
            # Корневой объект
            root_widget = self._root_widget

            # Находились в режим перемещения угла или середины выделения (изменения размера)
            if root_widget.move_mode in (MODE_MOVE_CORNER, MODE_MOVE_VERT_BORDER, MODE_MOVE_HOR_BORDER):
                # Обновляем "эталонные" координаты выделенной области (исходя из новых экранных)
                root_widget.selections[root_widget.selected_rect].update_rect_ref(
                    root_widget.scr_w, root_widget.scr_h, root_widget.ref_w, root_widget.ref_h
                )
                # Если размер области слишком мал, то ликвидируем его
                if root_widget.selections[root_widget.selected_rect].is_null:
                    ind = root_widget.selections_all.index(root_widget.selections[root_widget.selected_rect])
                    # удаляем из общего списка
                    root_widget.selections_all.pop(ind)
                    # удаляем из списка выделений текущего окна
                    root_widget.selections.pop(root_widget.selected_rect)
                    # сбрасываем индекс
                    root_widget.selected_rect = -1
                    # обновляем экран
                    self._page_widget.update()
                    # эмитируем сигнал rect_selected
                    root_widget.rect_selected.emit(False)

            # Находимся в режим перемещения всего выделения
            elif root_widget.move_mode == MODE_MOVE_ALL:
                # Пересчитываем "эталонные" координаты выделения (исходя из новых экранных)
                root_widget.selections[root_widget.selected_rect].update_rect_ref(
                    root_widget.scr_w, root_widget.scr_h, root_widget.ref_w, root_widget.ref_h
                )

            # Сбрасываем режим перемещения
            root_widget.move_mode = MODE_MOVE_NONE
            # Обновляем форму курсора исходя из положения мыши в системе координат страницы документа
            self.set_cursor_shape(self._page_widget.mapFromParent(event.pos()))

        # Вызываем обработчик родительского класса
        super().mouseReleaseEvent(event)


class PageWidget(QLabel):  # pylint: disable=too-many-instance-attributes
    """Виджет для отображения страницы файла PDF"""

    def __init__(self, parent: BoardWidget = None, root_widget: SiaPdfView = None):
        super().__init__(parent)
        self._board_widget = parent  # виджет-контейнер страницы
        self._root_widget = root_widget  # корневой виджет

        # Стиль контура активных выделений
        self.pen = QPen()
        self.pen.setWidth(1)
        self.pen.setStyle(Qt.PenStyle.DashLine)  # пунктир
        self.pen.setColor(QColor.fromRgb(255, 0, 0, 255))  # красный

        # Стиль контура неактивных выделений
        self.pen_dis = QPen()
        self.pen_dis.setWidth(1)
        self.pen_dis.setStyle(Qt.PenStyle.SolidLine)  # сплошная линия
        self.pen_dis.setColor(QColor.fromRgb(128, 128, 128, 255))  # серый

        # Стиль контура маркеров
        self.pen2 = QPen()
        self.pen2.setWidth(1)
        self.pen2.setStyle(Qt.PenStyle.SolidLine)  # сплошная линия
        self.pen2.setColor(QColor.fromRgb(255, 0, 0, 255))  # красный

        # Стиль заливки простых активных выделений
        self.fill = QBrush()
        self.fill.setStyle(Qt.BrushStyle.SolidPattern)  # сплошная заливка
        self.fill.setColor(QColor.fromRgb(255, 255, 0, 64))  # желтый

        # Стиль заливки глобальных активных выделений
        self.fill_all = QBrush()
        self.fill_all.setStyle(Qt.BrushStyle.SolidPattern)  # сплошная заливка
        self.fill_all.setColor(QColor.fromRgb(0, 255, 0, 64))  # зеленый

        # Стиль заливки неактивных выделений
        self.fill_dis = QBrush()
        self.fill_dis.setStyle(Qt.BrushStyle.BDiagPattern)  # диагональная штриховка
        self.fill_dis.setColor(QColor.fromRgb(0, 0, 0, 64))  # черный

        # Стиль заливки маркеров
        self.fill2 = QBrush()
        self.fill2.setStyle(Qt.BrushStyle.SolidPattern)  # сплошная заливка
        # self.fill2.setColor(QColor.fromRgb(255,0,0,255))
        self.fill2.setColor(QColor.fromRgb(255, 255, 255, 255))  # белый

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event: QPaintEvent):
        """Обработчик события прорисовки виджета"""
        super().paintEvent(event)

        # Если на странице нет выделенных областей, то сразу выходим
        if not self._root_widget.selections:
            return

        # Инизиализируем QPainter
        painter = QPainter()
        painter.begin(self)
        # Обходим все выделенные области на странице
        for i, r in enumerate(self._root_widget.selections):
            # Если выделение не активно, выводим прямоугольник "неактивными" цветами
            if not r.enabled:
                painter.setPen(self.pen_dis)
                painter.setBrush(self.fill_dis)
                painter.drawRect(r.rect)
                continue

            # Если выделение активно, выводим цветами в зависимости от его "глобальности"
            painter.setPen(self.pen)
            if r.pno == -1:
                painter.setBrush(self.fill_all)
            else:
                painter.setBrush(self.fill)
            painter.drawRect(r.rect)

            # Если выделение активно и имеет фокус, выводим маркеры по углам и по центрам сторон
            if i == self._root_widget.selected_rect:
                # painter.setPen(Qt.PenStyle.NoPen)
                painter.setPen(self.pen2)
                painter.setBrush(self.fill2)

                #  Маркеры на углах
                painter.drawRect(r.x1 - 3, r.y1 - 3, 6, 6)
                painter.drawRect(r.x2 - 3, r.y1 - 3, 6, 6)
                painter.drawRect(r.x1 - 3, r.y2 - 3, 6, 6)
                painter.drawRect(r.x2 - 3, r.y2 - 3, 6, 6)

                xc = (r.x1 + r.x2) // 2
                yc = (r.y1 + r.y2) // 2
                #  Маркеры на серединах сторон
                painter.drawRect(xc - 3, r.y1 - 3, 6, 6)
                painter.drawRect(r.x1 - 3, yc - 3, 6, 6)
                painter.drawRect(r.x2 - 3, yc - 3, 6, 6)
                painter.drawRect(xc - 3, r.y2 - 3, 6, 6)

        # Финализируем QPainter
        painter.end()
