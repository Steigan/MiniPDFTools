"""
Виджеты для просмотра PDF-файла
-------------------------------
Комплект виджетов для просмотра PDF-файла с возможностью выделения областей,
их копирования в буфер и т.п.

Заметки
=======
* Версия от 05.04.2023 (c) 2023 **Igor Stepanenkov**

Зависимости
===========
* PySide2
* PyMuPDF
"""

import re

import fitz
import pytesseract
from PIL import ImageOps
from PIL import ImageQt
from PySide2.QtCore import QPoint
from PySide2.QtCore import QRect
from PySide2.QtCore import QRectF
from PySide2.QtCore import Qt
from PySide2.QtCore import Signal
from PySide2.QtCore import Slot
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


# Участки выделенной области
DIR_OUT = 0
DIR_NW = 1
DIR_N = 2
DIR_NE = 3
DIR_W = 4
DIR_IN = 5
DIR_E = 6
DIR_SW = 7
DIR_S = 8
DIR_SE = 9

# Режимы перетаскивания выделенной области или ее участка мышью
MODE_MOVE_NONE = 0
MODE_MOVE_CORNER = 1
MODE_MOVE_ALL = 2
MODE_MOVE_VERT_BORDER = 3
MODE_MOVE_HOR_BORDER = 4


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


class SelectionRect:
    """Класс для хранения данных о выделенных областях"""

    def __init__(self, pno: int = -1):
        self.pno = pno
        self.r = QRect(0, 0, 0, 0)
        self.r_f = QRectF(0.0, 0.0, 0.0, 0.0)
        self.enabled = True

    def get_rect(self) -> QRect:
        """Получить экранный QRect выделенной области

        Returns:
            QRect: выделенная область
        """
        return self.r

    def normalize(self):
        """Нормализовать экранные размеры выделенной области"""
        # Косяк в PySide2
        # self.r = self.r.normalized()
        # x1, y1, x2, y2 = self.r.getCoords()

        doit = False
        x1 = self.x1()
        x2 = self.x2()
        y1 = self.y1()
        y2 = self.y2()

        if x2 < x1:
            x1, x2 = x2, x1
            doit = True

        if y2 < y1:
            y1, y2 = y2, y1
            doit = True

        if doit:
            self.r.setRect(x1, y1, x2 - x1, y2 - y1)

    def update_r_f(self, scr_w: int, scr_h: int, eth_w: int, eth_h: int):
        """Пересчитать "эталлонный" QRect в соответствии с указанным масштабом и
        текущими экранными размерами выделенной области

        Args:
            scr_w (int): экранная ширина страницы
            scr_h (int): экранная высота страницы
            eth_w (int): ширина эталлоной страницы
            eth_h (int): высота эталлоной страницы
        """
        self.normalize()
        self.r_f.setX(self.r.x() * eth_w / scr_w)
        self.r_f.setY(self.r.y() * eth_h / scr_h)
        self.r_f.setWidth((self.r.width() + 1) * eth_w / scr_w)
        self.r_f.setHeight((self.r.height() + 1) * eth_h / scr_h)

    def update_r(
        self, scr_w: int, scr_h: int, eth_w: int, eth_h: int, check_size=False
    ):  # pylint: disable=too-many-arguments
        """Пересчитать экранный QRect в соответствии с указанным масштабом и
        "эталлонными" размерами выделенной области

        Args:
            scr_w (int): экранная ширина страницы
            scr_h (int): экранная высота страницы
            eth_w (int): ширина эталлоной страницы
            eth_h (int): высота эталлоной страницы
            check_size (int): проверить размеры области на вместиомость на странице
        """
        if check_size:
            self.enabled = QRectF(0, 0, eth_w, eth_h).contains(self.r_f)

        self.r.setX(round(self.r_f.x() * scr_w / eth_w))
        self.r.setY(round(self.r_f.y() * scr_h / eth_h))
        self.r.setWidth(round((self.r_f.x() + self.r_f.width()) * scr_w / eth_w) - self.r.x() - 1)
        self.r.setHeight(round((self.r_f.y() + self.r_f.height()) * scr_h / eth_h) - self.r.y() - 1)

    def get_scaled_rect(self, new_w: int, new_h: int, eth_w: int, eth_h: int) -> QRect:
        """Сформировать QRect в соответствии с указанным масштабом и "эталлонными"
        размерами выделенной области

        Args:
            new_w (int): новая ширина страницы
            new_h (int): новая высота страницы
            eth_w (int): ширина эталлоной страницы
            eth_h (int): высота эталлоной страницы

        Returns:
            QRect: масштабированная прямоугольная область
        """
        m_r = QRect()
        m_r.setX(round(self.r_f.x() * new_w / eth_w))
        m_r.setY(round(self.r_f.y() * new_h / eth_h))
        m_r.setWidth(round(self.r_f.width() * new_w / eth_w))
        m_r.setHeight(round(self.r_f.height() * new_h / eth_h))
        return m_r

    def set_x1y1_x2y2(self, pt1: QPoint, pt2: QPoint):
        """Установить параметры экранного QRect исходя их координат двух переданных точек
        ("эталонный" QRect не пересчитывается)

        Args:
            pt1 (QPoint): точка первого угла прямоугольной области
            pt2 (QPoint): точка второго (диагонально противоположного) угла прямоугольной области
        """
        self.r.setRect(pt1.x(), pt1.y(), pt2.x() - pt1.x(), pt2.y() - pt1.y())

    def x1(self) -> int:
        """Получить координату X первого угла экранного QRect

        Returns:
            int: координата X
        """
        return self.r.x()

    def y1(self) -> int:
        """Получить координату Y первого угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.r.y()

    def x2(self) -> int:
        """Получить координату X второго угла экранного QRect

        Returns:
            int: координата X
        """
        return self.r.x() + self.r.width()

    def y2(self) -> int:
        """Получить координату Y второго угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.r.y() + self.r.height()

    def is_null(self) -> bool:
        """Проверить выделенную область на соответствие минимальному размеру

        Returns:
            bool: признак соответствия минимально допустимому размеру
        """
        return abs(self.r_f.width()) < 15 or abs(self.r_f.height()) < 15

    def dir_rect(self, pt: QPoint) -> int:
        """Получить номер угла выделенной области, находящийся в зоне "досягаемости"
        указанной точки (1, 3, 7, 9), или идентификатор иного участка области/экрана
        (5 - внутри области, 0 - за пределами области или область disabled)

        1 - 2 - 3

        4 - 5 - 6

        7 - 8 - 9

        Args:
            pt (QPoint): точка (например, положение указателя мыши)

        Returns:
            int: идентификатор угла выделенной области или иного участка области/экрана
        """
        # self.normalize()
        if not self.enabled:
            return DIR_OUT
        r = self.r
        xc = (self.x1() + self.x2()) // 2
        yc = (self.y1() + self.y2()) // 2
        offs = 4
        if r.x() - offs < pt.x() < r.x() + offs:  # левая сторона
            if r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
                return DIR_NW
            if r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
                return DIR_SW
            if yc - offs < pt.y() < yc + offs:  # середина по вертикали
                return DIR_W
        elif r.right() - offs + 1 < pt.x() < r.right() + offs + 1:  # правая сторона
            if r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
                return DIR_NE
            if r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
                return DIR_SE
            if yc - offs < pt.y() < yc + offs:  # середина по вертикали
                return DIR_E
        elif r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
            if xc - offs < pt.x() < xc + offs:  # середина по горизонтали
                return DIR_N
        elif r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
            if xc - offs < pt.x() < xc + offs:  # середина по горизонтали
                return DIR_S

        if r.contains(pt):
            return DIR_IN
        return DIR_OUT

    def adjust_position(self, w: int, h: int):
        """Проверить, укладывается ли выделенная область в размеры страницы, и сдвинуть ее
        обратно на страницу, если область вышла за края

        Args:
            w (int): ширина страницы
            h (int): высота страницы

        Returns:
            int, int: смещения по X и Y из-за перемещения области обратно на страницу
        """
        dx = min(self.x1(), self.x2(), 0)
        if not dx:
            dx = max(self.x1() - (w - 1), self.x2() - (w - 1), 0)
        dy = min(self.y1(), self.y2(), 0)
        if not dy:
            dy = max(self.y1() - (h - 1), self.y2() - (h - 1), 0)
        if dx or dy:
            self.r.adjust(-dx, -dy, -dx, -dy)
        return dx, dy

    def shift_x(self, offs: int, shft: bool, w: int, h: int):
        """Сдвинуть выделенную область или изменить ее размер по горизонтали на указанное число пикселей
        в пределах страницы

        Args:
            offs (int): количество пикселей
            shft (bool): признак изменения размера области, иначе - перемещение
            w (int): ширина страницы
            h (int): высота страницы

        Returns:
            SelectionRect: этот объект
        """
        self.normalize()
        if shft:
            if self.r.width() + offs > 10:
                self.r.setWidth(min(self.r.width() + offs, w - self.x1() - 1))
        else:
            self.r.moveLeft(self.r.left() + offs)
            self.adjust_position(w, h)
        return self

    def shift_y(self, offs: int, shft, w: int, h: int):
        """Сдвинуть выделенную область или изменить ее размер по вертикали на указанное число пикселей
        в пределах страницы

        Args:
            offs (int): количество пикселей
            shft (bool): признак изменения размера области, иначе - перемещение
            w (int): ширина страницы
            h (int): высота страницы

        Returns:
            SelectionRect: этот объект
        """
        self.normalize()
        if shft:
            if self.r.height() + offs > 10:
                self.r.setHeight(min(self.r.height() + offs, h - self.y1() - 1))
        else:
            self.r.moveTop(self.r.top() + offs)
            self.adjust_position(w, h)
        return self


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
        # Отфильтровываем PgUp и PgDn
        if not event.key() in (16777238, 16777239):
            super().keyPressEvent(event)


# noinspection PyUnresolvedReferences
class ZoomSlider(QSlider):
    """Виджет слайдера для выбора масштаба просмотра страницы"""

    zoomSliderDoubleClicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event: QMouseEvent):  # pylint: disable=unused-argument
        self.zoomSliderDoubleClicked.emit()


# noinspection PyUnresolvedReferences
class ZoomSelector(QWidget):
    """Виджет выбора масштаба просмотра страницы (на основе слайдера)"""

    zoom_factor_changed = Signal(float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedWidth(190)

        self.passemit = False

        self.horizontal_layout = QHBoxLayout(self)
        self.horizontal_layout.setSpacing(5)
        self.horizontal_layout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.slider = ZoomSlider(self)
        self.slider.setFixedWidth(120)
        self.slider.setMinimum(20)
        self.slider.setMaximum(300)
        self.slider.setValue(100)
        self.slider.setOrientation(Qt.Horizontal)

        self.lbl_value = QLineEdit(self)
        self.lbl_value.setFixedWidth(45)
        self.lbl_value.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.lbl_value.setText("100%")
        self.lbl_value.setReadOnly(True)
        self.horizontal_layout.addWidget(self.slider)
        self.horizontal_layout.addWidget(self.lbl_value)

        self.slider.valueChanged.connect(self.value_changed)
        self.slider.zoomSliderDoubleClicked.connect(self.reset)
        self.lbl_value.setEnabled(False)
        self.slider.setEnabled(False)

    def set_zoom_factor(self, zoom_factor: float):
        self.passemit = True
        self.slider.setValue(int(zoom_factor * 100))

    def reset(self):
        self.slider.setValue(100)
        self.value_changed(100)

    def value_changed(self, value):
        self.lbl_value.setText(f"{value}%")
        if not self.passemit:
            self.zoom_factor_changed.emit(value / 100.0)
        self.passemit = False

    def setDisabled(self, fl: bool):
        self.setEnabled(not fl)

    def setEnabled(self, fl: bool):
        self.lbl_value.setEnabled(fl)
        self.slider.setEnabled(fl)


###########################################################################
# Основные виджеты
###########################################################################


# noinspection PyBroadException,PyUnresolvedReferences
class SiaPdfView(QScrollArea):
    """Виджет-основная прокручиваемая область просмотра"""

    current_page_changed = Signal(int)
    zoom_factor_changed = Signal(float)
    rect_selected = Signal(bool)
    scroll_requested = Signal(QPoint, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._current_filename = ''  # Имя текущего файла
        self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
        self._current_page = -1
        self._psw = ''
        self._scale_factor = 1.0
        self._dpi = 300

        ppi = 96
        self.dpi = ppi * 3
        zoom = self.dpi / 72
        self._matrix = fitz.Matrix(zoom, zoom)

        self.scr_w = 0
        self.scr_h = 0
        self.eth_w = 0
        self.eth_h = 0

        self.selection_point1 = QPoint(0, 0)
        self.selection_point2 = QPoint(0, 0)
        self.move_point = QPoint(0, 0)

        self.selected_rect = -1
        self.selections_max = 10000
        self.selections = []
        self.selections_all = []

        self.move_mode = 0

        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self.setFrameStyle(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._container = ContainerWidget(self)
        self._container.setBackgroundRole(QPalette.ColorRole.Dark)
        self._container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._container.setFixedSize(50, 50)
        self._container.move(0, 0)

        self._pageimage = PageWidget(self._container, self)
        self._pageimage.setBackgroundRole(QPalette.ColorRole.Base)
        self._pageimage.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._pageimage.setScaledContents(True)

        self._container.set_widget(self._pageimage)
        self.setWidget(self._container)

        self._container.setMouseTracking(True)
        self._pageimage.setMouseTracking(True)
        self._container.setVisible(False)

        self.scroll_requested.connect(self.scroll_point_to_point)

    def combine(self, filelist: list):
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

        skip_all = False

        self.close()
        self._current_filename = ''  # Имя текущего файла
        self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)

        self._doc = fitz.Document()
        for filename in filelist:
            try:
                doc = fitz.Document(filename)
                if not doc.is_pdf:
                    pdfbytes = doc.convert_to_pdf()
                    doc.close()
                    doc = fitz.open("pdf", pdfbytes)

                if doc.needs_pass:
                    self._decrypt_doc(filename, doc)
            except Exception as e:
                if skip_all:
                    continue

                m_msg_box.setText(f'Ошибка: {e}\nФайл: {filename}')
                res = m_msg_box.exec()
                if res == QMessageBox.StandardButton.Cancel:
                    self.close()
                    return

                if res == QMessageBox.StandardButton.YesToAll:
                    skip_all = True
                continue
            if not doc.is_encrypted:
                self._doc.insert_pdf(doc, from_page=0, to_page=len(doc) - 1)
            doc.close()

        if len(self._doc):
            self._current_filename = '*** Результат объединения файлов ***'  # Имя текущего файла
            self._scale_factor = 1.0
            self._show_page(0)
            self._container.setVisible(True)
            self.zoom_factor_changed.emit(self._scale_factor)
        else:
            self.close()

    def open(self, filename: str):
        self.close()
        self._current_filename = ''  # Имя текущего файла
        self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
        try:
            self._doc = fitz.Document(filename)
            if not self._doc.is_pdf:
                pdfbytes = self._doc.convert_to_pdf()
                self._doc.close()
                self._doc = fitz.open("pdf", pdfbytes)
                # self.close()
                # return
            if self._doc.needs_pass:
                self._decrypt_doc(filename, self._doc)
            if self._doc.is_encrypted:
                self.close()
                return

            self._current_filename = filename  # Имя текущего файла
            self._is_real_file = True  # Это настоящий файл (или виртуальный/новый)
            self._scale_factor = 1.0
            self._show_page(0)
            self._container.setVisible(True)
            self.zoom_factor_changed.emit(self._scale_factor)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка открытия файла", f"Ошибка: {e}\nФайл: {filename}")
            self.close()

    def _decrypt_doc(self, filename: str, doc: fitz.Document):
        m_input_dlg = QInputDialog(self)
        m_input_dlg.setWindowTitle("Введите пароль")
        m_input_dlg.setLabelText(f"Для открытия файла '{filename}' требуется пароль!\nВведите пароль:")
        m_input_dlg.setOkButtonText('ОК')
        m_input_dlg.setCancelButtonText('Отмена')
        m_input_dlg.setInputMode(QInputDialog.InputMode.TextInput)
        m_input_dlg.setTextEchoMode(QLineEdit.Password)
        while True:
            m_input_dlg.setTextValue('')
            res = m_input_dlg.exec_()
            if res == QDialog.DialogCode.Accepted:
                self._psw = m_input_dlg.textValue()
                doc.authenticate(self._psw)
            else:
                return
            if not doc.is_encrypted:
                return
            m_input_dlg.setLabelText(
                f"Пароль открытия файла '{filename}' не верный!\nВведите правильный, либо нажмите 'Отмена':"
            )

    def close(self):
        if self._doc is not None:
            self._doc.close()
            self._doc = None
            self._current_filename = ''  # Имя текущего файла
            self._is_real_file = False  # Это настоящий файл (или виртуальный/новый)
            self._current_page = -1
            self._container.setVisible(False)
            self._container.setFixedSize(50, 50)
            self._container.move(0, 0)
            self.selections = []
            self.selections_all = []
            self.selected_rect = -1
            self.rect_selected.emit(False)

    @property
    def doc(self):
        return self._doc

    @property
    def current_filename(self):
        return self._current_filename

    @property
    def is_real_file(self):
        return self._is_real_file

    @property
    def current_page(self):
        return self._current_page

    @property
    def psw(self):
        return self._psw

    @property
    def selections_count(self):
        return len(self.selections)

    @property
    def selections_all_count(self):
        return len(self.selections_all)

    @property
    def page_count(self):
        if self._doc is None:
            return 0
        return self._doc.page_count

    def goto_page(self, pno: int):
        self._show_page(pno)

    def goto_next_page(self):
        if self._current_page < self._doc.page_count - 1:
            self._show_page(self._current_page + 1)

    def goto_prev_page(self):
        if self._current_page > 0:
            self._show_page(self._current_page - 1)

    def goto_home(self):
        if self.page_count > 0:
            self._show_page(0)

    def goto_end(self):
        if self.page_count > 0:
            self._show_page(self._doc.page_count - 1)

    def zoom_in(self):
        self.scale_image(1.25)

    def zoom_out(self):
        self.scale_image(0.8)

    @Slot(float)
    def set_zoom_factor(self, factor):
        self.scale_image(1, None, factor)

    @Slot()
    def copy_page_image_to_clipboard(self):
        if self._current_page > -1:
            img = self._pageimage.pixmap().toImage()
            dpm = self._dpi / 0.0254
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
            QGuiApplication.clipboard().setImage(img)

    @Slot()
    def copy_rect_image_to_clipboard(self):
        if self._current_page > -1 and self.selected_rect > -1:
            img = self._pageimage.pixmap().toImage()
            dpm = self._dpi / 0.0254
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
            r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
            QGuiApplication.clipboard().setImage(img.copy(r))

    @Slot()
    def copy_rect_text_to_clipboard(self, trim: bool = False):
        if self._current_page > -1 and self.selected_rect > -1:
            r = self.selections[self.selected_rect].r_f
            rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
            rc = rc / self._matrix
            rc = rc / self._doc[self._current_page].rotation_matrix
            recttext = self._doc[self._current_page].get_text("text", clip=rc).rstrip()
            if trim:
                recttext = re.sub(r'\s+', ' ', recttext)
            if not recttext:
                show_info_msg_box(
                    self, 'Копирование текста', 'В выделенном участке отсутствует текст в текстовом слое.'
                )
            else:
                QGuiApplication.clipboard().setText(recttext)

    @Slot()
    def recognize_and_copy_to_clipboard(self, tesseract_cmd: str, trim: bool):
        if self._current_page > -1 and self.selected_rect > -1:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            img = self._pageimage.pixmap().toImage()
            r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
            img = ImageQt.fromqimage(img.copy(r))
            recttext = pytesseract.image_to_string(img, lang='rus+eng')
            if trim:
                recttext = re.sub(r'\s+', ' ', recttext)
            if not recttext:
                show_info_msg_box(self, 'Распознание текста', 'В выделенном участке не удалось распознать текст.')
            else:
                QGuiApplication.clipboard().setText(recttext)

    @Slot()
    def recognize_qr_and_copy_to_clipboard(self):
        if self._current_page > -1 and self.selected_rect > -1:
            img = self._pageimage.pixmap().toImage()
            r = self.selections[self.selected_rect].get_scaled_rect(1, 1, 1, 1)
            img = ImageQt.fromqimage(img.copy(r))
            decocde_qr = decode(img, [ZBarSymbol.QRCODE])
            if not decocde_qr:
                img = ImageOps.invert(img)
                decocde_qr = decode(img, [ZBarSymbol.QRCODE])
            if not decocde_qr:
                show_info_msg_box(self, 'Распознание QR-кодов', 'Данные не распознаны.')
            else:
                txt = ''
                for qr_obj in decocde_qr:
                    txt += ('\n-------------------\n' if txt else '') + qr_obj.data.decode('utf-8')

                QGuiApplication.clipboard().setText(txt)

    @Slot(bool)
    def copy_rects_info_to_clipboard(self, fl_all: bool = False):
        if self._current_page > -1:
            if fl_all:
                sels = self.selections_all.copy()
                recttext = "№ п/п, страница, вращение: область\n"
            else:
                sels = self.selections.copy()
                recttext = f"Угол вращения исходной страницы: {self._doc[self._current_page].rotation}\n"
                recttext += "№ п/п, страница: область\n"

            if len(sels) == 0:
                recttext = "Нет выделенных участков!"
            else:
                if self.selected_rect > -1:
                    selected = self.selections[self.selected_rect]
                else:
                    selected = None

                def selssort_key(x):
                    return x.pno, x.r_f.y(), x.r_f.x()

                sels.sort(key=selssort_key)
                pno = self._current_page
                for i, s in enumerate(sels):
                    r = s.r_f
                    rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                    rc = rc / self._matrix
                    if fl_all:
                        pno = max(s.pno, 0)

                    recttext += f"{i + 1}{'*' if s is selected else ''}, {pno + 1}{'**' if s.pno == -1 else ''}"
                    if fl_all:
                        recttext += f", {self._doc[pno].rotation}"
                    recttext += f": ({round(rc.x0, 2)}, {round(rc.y0, 2)}, {round(rc.x1, 2)}, {round(rc.y1, 2)})\n"

            QGuiApplication.clipboard().setText(recttext)
            show_info_msg_box(self, 'Информация о выделенных участках', recttext)

    @Slot()
    def switch_rect_mode(self):
        if self._current_page > -1 and self.selected_rect > -1:
            r = self.selections[self.selected_rect]
            if r.pno == -1:
                r.pno = self._current_page
            else:
                r.pno = -1
            self._pageimage.update()

    def rotate_pages(self, n_dir: int, fl_all: bool):
        if self._current_page > -1:
            if fl_all:
                pno = 0
                pno_end = len(self._doc)
            else:
                pno = self._current_page
                pno_end = pno + 1

            while pno < pno_end:
                src_rot_mat = self._doc[pno].rotation_matrix * self._matrix
                self._doc[pno].set_rotation((self._doc[pno].rotation + (0, 270, 90, 180)[n_dir]) % 360)
                dst_rot_mat = self._doc[pno].rotation_matrix * self._matrix
                for sel in self.selections_all:
                    # sel = selectionRect()
                    if sel.pno == pno or (sel.pno == -1 and (pno == self._current_page or fl_all)):
                        r = sel.r_f
                        rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                        rc = (rc / src_rot_mat) * dst_rot_mat
                        r.setRect(rc.x0, rc.y0, rc.x1 - rc.x0, rc.y1 - rc.y0)
                pno += 1

            pno = self._current_page
            self._current_page = -1
            self._show_page(pno)

    def add_selection(self, pno, r):
        sel = SelectionRect(pno)
        rot_r = (r * self._doc[pno].rotation_matrix) * self._matrix
        rot_r.normalize()
        sel.r_f.setCoords(rot_r.x0, rot_r.y0, rot_r.x1, rot_r.y1)
        self.selections_all.append(sel)
        if pno == self._current_page:
            sel.update_r(self.scr_w, self.scr_h, self.eth_w, self.eth_h)
            self.selections.append(sel)
            self._pageimage.update()

    def get_selection_fitz_rect(self, pno, old_rot, sel: SelectionRect):
        cur_rot = self._doc[pno].rotation
        if cur_rot != old_rot:
            self._doc[pno].set_rotation(old_rot)
        r = fitz.Rect(sel.r_f.x(), sel.r_f.y(), sel.r_f.x() + sel.r_f.width(), sel.r_f.y() + sel.r_f.height())
        r = (r / self._matrix) / self._doc[pno].rotation_matrix
        if cur_rot != old_rot:
            self._doc[pno].set_rotation(cur_rot)
        return r

    @Slot(bool)
    def select_all(self):
        if self._current_page > -1:
            max_rect = QRectF(0, 0, self.eth_w, self.eth_h)
            for sel in self.selections:
                if sel.r_f == max_rect:
                    self.selected_rect = self.selections.index(sel)
                    break
            else:
                self.selected_rect = len(self.selections)
                new_sel = SelectionRect(self._current_page)
                new_sel.r_f = max_rect
                new_sel.update_r(self.scr_w, self.scr_h, self.eth_w, self.eth_h)

                self.selections.append(new_sel)
                self.selections_all.append(new_sel)

            self._pageimage.update()
            self.rect_selected.emit(True)

    @Slot(bool)
    def remove_selection(self, remove_all=False):
        if remove_all:
            self.selections.clear()
            self.selections_all.clear()
        else:
            if self._current_page > -1:
                if self.selected_rect > -1:
                    ind = self.selections_all.index(self.selections[self.selected_rect])
                    self.selections_all.pop(ind)
                    self.selections.pop(self.selected_rect)
        self.selected_rect = -1
        self._pageimage.update()
        self.rect_selected.emit(False)

    def wheelEvent(self, wheelEvent: QWheelEvent):
        if (wheelEvent.modifiers() & Qt.KeyboardModifier.AltModifier) or (
            wheelEvent.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            super().wheelEvent(wheelEvent)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shft = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        alt = event.modifiers() & Qt.KeyboardModifier.AltModifier

        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            return

        if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space):
            if self.selections:
                if shft:
                    if self.selected_rect == 0:
                        self.selected_rect = len(self.selections)
                    self.selected_rect -= 1
                else:
                    self.selected_rect += 1
                    if self.selected_rect == len(self.selections):
                        self.selected_rect = 0
                self.rect_selected.emit(True)
                p_pt = self._pageimage.mapToParent(self.selections[self.selected_rect].r.topLeft())
                self.ensureVisible(p_pt.x(), p_pt.y(), 50, 50)

        if self.selected_rect == -1:
            super().keyPressEvent(event)
            return

        fl_update = True
        fl_update_r_f = True
        dx = dy = 0
        if alt:
            fl_update = False
            if key == Qt.Key.Key_Left:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Right:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
            elif key == Qt.Key.Key_Up:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Down:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 10)
        else:
            if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space):
                pass
            elif key == Qt.Key.Key_Left:
                dx = (
                    -self.selections[self.selected_rect]
                    .shift_x(-1 if ctrl else -10, shft, self._pageimage.width(), self._pageimage.height())
                    .x2()
                )
            elif key == Qt.Key.Key_Right:
                if shft:
                    dx = (
                        self.selections[self.selected_rect]
                        .shift_x(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .x2()
                    )
                else:
                    dx = (
                        self.selections[self.selected_rect]
                        .shift_x(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .x1()
                    )
            elif key == Qt.Key.Key_Up:
                dy = (
                    -self.selections[self.selected_rect]
                    .shift_y(-1 if ctrl else -10, shft, self._pageimage.width(), self._pageimage.height())
                    .y2()
                )
            elif key == Qt.Key.Key_Down:
                if shft:
                    dy = (
                        self.selections[self.selected_rect]
                        .shift_y(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .y2()
                    )
                else:
                    dy = (
                        self.selections[self.selected_rect]
                        .shift_y(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .y1()
                    )

            else:
                fl_update = False
                fl_update_r_f = False
                super().keyPressEvent(event)
                # self.parent().keyPressEvent(event)

            if dx or dy:
                vp_top_left = self._container.mapFromParent(QPoint(0, 0))
                vp_x_min = vp_top_left.x() + 20
                vp_y_min = vp_top_left.y() + 20
                vp_x_max = vp_top_left.x() + self.viewport().width() - 21
                vp_y_max = vp_top_left.y() + self.viewport().height() - 21
                if dx > vp_x_max or (dx < 0 and -dx < vp_x_min):
                    self.ensureVisible(abs(dx), vp_y_min, 20, 0)
                elif dy > vp_y_max or (dy < 0 and -dy < vp_y_min):
                    self.ensureVisible(vp_x_min, abs(dy), 0, 20)

            if fl_update_r_f:
                self.selections[self.selected_rect].update_r_f(self.scr_w, self.scr_h, self.eth_w, self.eth_h)

        if fl_update:
            self._pageimage.update()

    def scroll_contents_by(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._pageimage.update()

    @Slot(QPoint, QPoint)
    def scroll_point_to_point(self, src_pt: QPoint, dest_pt: QPoint):
        """Попытаться прокрутить рабочую область так, чтобы точка из системы координат изображения src_pt
           оказалась в точке dest_pt системы координат области

        Args:
            src_pt (QPoint): точка из системы координат изображения
            dest_pt (QPoint): точка в системе координат рабочей области
        """
        # Переводим точку src_pt в систему координат рабочей области
        src_pt = self._container.mapToParent(self._pageimage.mapToParent(src_pt))

        # Тупо сдвигаем содержимое рабочей области на разницу в координатах
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + src_pt.x() - dest_pt.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + src_pt.y() - dest_pt.y())

    def _set_sizes(self):
        ww = max(self.viewport().width(), self._pageimage.width() + 20)
        hh = max(self.viewport().height(), self._pageimage.height() + 20)
        self._container.setFixedHeight(hh)
        self._container.setFixedWidth(ww)
        self._pageimage.move((ww - self._pageimage.width()) // 2, 10)

    def _set_image(self, new_image):
        self._pageimage.setPixmap(QPixmap.fromImage(new_image))
        new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
        self._pageimage.resize(new_size)
        self._set_sizes()
        self.scr_w = new_size.width()
        self.scr_h = new_size.height()

    def _show_page(self, pno):
        if self._current_page != pno:
            self._current_page = pno
            pix = self._doc[pno].get_pixmap(alpha=False, matrix=self._matrix, colorspace=fitz.csRGB)

            new_image = QImage(pix.samples_mv, pix.width, pix.height, pix.width * 3, QImage.Format_RGB888)

            self.eth_w = pix.width
            self.eth_h = pix.height
            if new_image.isNull():
                pass
            else:
                self._set_image(new_image)

            self.selected_rect = -1
            self.selections = [sel for sel in self.selections_all if (sel.pno == -1 or sel.pno == pno)]

            i = len(self.selections)
            while i > 0:
                i -= 1
                r = self.selections[i]
                # Если не вмещается в страницу, дизейблим...
                r.update_r(self.scr_w, self.scr_h, self.eth_w, self.eth_h, True)

            self.rect_selected.emit(False)
            self.current_page_changed.emit(pno)

    def _normal_size(self):
        self._scale_factor = 1.0
        new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
        self._pageimage.resize(new_size)
        self.scr_w = new_size.width()
        self.scr_h = new_size.height()
        for r in self._pageimage.selections:
            r.update_r(self.scr_w, self.scr_h, self.eth_w, self.eth_h)
        self._set_sizes()

    def scale_image(self, factor, wheel_mouse_pos=None, newscale=1.0):
        if factor != 1:
            newscale = self._scale_factor * factor

        if newscale < 0.2:
            newscale = 0.2
        elif newscale > 3.0:
            newscale = 3.0
        elif 0.95 < newscale < 1.1:
            newscale = 1.0

        if self._scale_factor != newscale:
            factor = newscale / self._scale_factor
            self._scale_factor = newscale

            if wheel_mouse_pos is None:
                dest_point = QPoint(0, 0)
            else:
                dest_point = wheel_mouse_pos

            # destPoint - это "якорная" точка относительно левого верхнего угла всего виджета
            # srcPoint - это "якорная" точка относительно левого верхнего угла страницы документа
            src_point = self._pageimage.mapFromParent(self._container.mapFromParent(dest_point))
            # приводим srcPoint к новому масштабу
            src_point.setX(src_point.x() * factor)
            src_point.setY(src_point.y() * factor)

            new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
            self._pageimage.resize(new_size)
            self.scr_w = new_size.width()
            self.scr_h = new_size.height()

            self._set_sizes()

            for r in self.selections:
                r.update_r(self.scr_w, self.scr_h, self.eth_w, self.eth_h)

            self.zoom_factor_changed.emit(self._scale_factor)
            self.scroll_requested.emit(src_point, dest_point)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._current_page != -1:
            self._set_sizes()

    def set_selection_point(self, pt: QPoint, nm: int):
        """Установить координаты текущей выделенной области в соответствии
        с идентификатором действия

        1 - начало выделения области, оба угла устанавливаются в точку pt

        2 - перемещение второго угла в точку pt

        3 - начало перемещения всей выделенной области, фиксация pt как "точки зацепа"

        4 - перемещение всей выделенной области на дельту (pt - "точки зацепа"), фиксация pt как новой "точки зацепа"

        5 - перемещение вертикальной стороны в точку положение pt.x()

        6 - перемещение горизонтальной стороны в точку положение pt.y()

        11 - 19 - начало изменения размеров выделенной области за угол/сторону = (nm-10)

        Args:
            pt (QPoint): полощение указателя мыши
            nm (int): идентификатор действия
        """

        if nm > 10:
            r = self.selections[self.selected_rect]
            if nm in (11, 13, 17, 19):
                if nm == 19:
                    self.selection_point1 = QPoint(r.x1(), r.y1())
                elif nm == 17:
                    self.selection_point1 = QPoint(r.x2(), r.y1())
                elif nm == 13:
                    self.selection_point1 = QPoint(r.x1(), r.y2())
                elif nm == 11:
                    self.selection_point1 = QPoint(r.x2(), r.y2())
                nm = 2
            if nm == 18 or nm == 16:
                self.selection_point1 = QPoint(r.x1(), r.y1())
                self.selection_point2 = QPoint(r.x2(), r.y2())
                nm = self.move_mode + 2
            elif nm == 12 or nm == 14:
                self.selection_point1 = QPoint(r.x2(), r.y2())
                self.selection_point2 = QPoint(r.x1(), r.y1())
                nm = self.move_mode + 2

        pt.setX(min(max(pt.x(), 0), self._pageimage.width() - 1))
        pt.setY(min(max(pt.y(), 0), self._pageimage.height() - 1))
        if nm in (1, 2, 5, 6):
            if nm == 1:
                self.selection_point1 = pt
                self.selection_point2 = pt
            else:
                if nm == 2:
                    self.selection_point2 = pt
                elif nm == 5:
                    self.selection_point2.setX(pt.x())
                elif nm == 6:
                    self.selection_point2.setY(pt.y())
                p_pt = self._pageimage.mapToParent(pt)
                self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)
            self.selections[self.selected_rect].set_x1y1_x2y2(self.selection_point1, self.selection_point2)
        else:
            if nm == 3:
                self.move_point = pt
            else:
                dx = pt.x() - self.move_point.x()
                dy = pt.y() - self.move_point.y()
                r = self.selections[self.selected_rect]
                r.get_rect().adjust(dx, dy, dx, dy)

                dx, dy = r.adjust_position(self._pageimage.width(), self._pageimage.height())

                p_pt = self._pageimage.mapToParent(pt)
                if dx or dy:
                    pt.setX(pt.x() - dx)
                    pt.setY(pt.y() - dy)

                self.move_point = pt
                self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)

        self._pageimage.update()


# noinspection PyProtectedMember,PyUnresolvedReferences
class ContainerWidget(QWidget):
    """Виджет-контейнер для размещения внутри него страницы документа,
    обеспечения отступов между страницей документа и основной областью просмотра.
    """

    zoom_in = Signal(bool)
    zoom_out = Signal(bool)

    def __init__(self, parent: SiaPdfView = None):
        super().__init__(parent)
        self.parent_wg = parent
        self.child_wg = None
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_widget(self, child_widget):
        self.child_wg = child_widget

    def mousePressEvent(self, event: QMouseEvent):
        pt = self.child_wg.mapFromParent(event.pos())
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if self.parent_wg.selected_rect >= 0:
                r = self.parent_wg.selections[self.parent_wg.selected_rect]
                dir_rect = r.dir_rect(pt)
                if event.button() == Qt.MouseButton.LeftButton or dir_rect == 0:
                    if dir_rect == DIR_IN:
                        self.parent_wg.move_mode = MODE_MOVE_ALL
                        self.parent_wg.set_selection_point(pt, 3)

                    elif dir_rect == DIR_OUT:
                        self.parent_wg.selected_rect = -1
                        self.parent_wg.rect_selected.emit(False)
                        self.child_wg.update()

                    else:
                        if dir_rect in (DIR_W, DIR_E):
                            self.parent_wg.move_mode = MODE_MOVE_VERT_BORDER
                        elif dir_rect in (DIR_N, DIR_S):
                            self.parent_wg.move_mode = MODE_MOVE_HOR_BORDER
                        else:
                            self.parent_wg.move_mode = MODE_MOVE_CORNER

                        self.parent_wg.set_selection_point(pt, 10 + dir_rect)

                        self.setCursor(Qt.CursorShape.CrossCursor)

            if self.parent_wg.selected_rect == -1:
                for i, r in enumerate(self.parent_wg.selections):
                    dir_rect = r.dir_rect(pt)
                    if dir_rect == DIR_IN:
                        self.parent_wg.selected_rect = i
                        self.parent_wg.rect_selected.emit(True)
                        if event.button() == Qt.MouseButton.RightButton:
                            self.child_wg.update()
                        else:
                            self.parent_wg.move_mode = MODE_MOVE_ALL
                            # noinspection PyTypeChecker
                            self.setCursor(Qt.CursorShape.SizeAllCursor)
                            self.parent_wg.set_selection_point(pt, 3)
                        break

        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_wg.selected_rect == -1:
                if len(self.parent_wg.selections_all) < self.parent_wg.selections_max:
                    self.parent_wg.selected_rect = len(self.parent_wg.selections)
                    newsel = SelectionRect(
                        -1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else self.parent_wg.current_page
                    )
                    self.parent_wg.selections.append(newsel)
                    self.parent_wg.selections_all.append(newsel)
                    self.parent_wg.move_mode = MODE_MOVE_CORNER
                    self.parent_wg.set_selection_point(pt, 1)
                    # noinspection PyTypeChecker
                    self.setCursor(Qt.CursorShape.CrossCursor)
                    self.parent_wg.rect_selected.emit(True)
                else:
                    self.child_wg.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Получаем координаты указателя мыши
        pt = self.child_wg.mapFromParent(event.pos())

        # Не находимся в режиме перемещения или изменения размера выделенной области?
        if self.parent_wg.move_mode == MODE_MOVE_NONE:
            # По умолчанию такое вот значение
            cursor_shape = Qt.CursorShape.BlankCursor

            # Перебираем все выделенные области
            for i, r in enumerate(self.parent_wg.selections):
                # Определяем местоположение указателя мыши по отношению к этой выделенной области
                dir_rect = r.dir_rect(pt)

                # Если указательза пределами выделенной области, то пропускаем итерацию
                if dir_rect == DIR_OUT:
                    continue

                # Это активная выделенная область?
                if i == self.parent_wg.selected_rect:
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

            if cursor_shape == Qt.CursorShape.BlankCursor:
                self.unsetCursor()
            else:
                self.setCursor(cursor_shape)
        elif self.parent_wg.move_mode == MODE_MOVE_CORNER:  # двигаем угол
            self.parent_wg.set_selection_point(pt, 2)
        elif self.parent_wg.move_mode == MODE_MOVE_ALL:  # двигаем всю область
            self.parent_wg.set_selection_point(pt, 4)
        elif self.parent_wg.move_mode == MODE_MOVE_VERT_BORDER:  # двигаем вертикальные стороны
            self.parent_wg.set_selection_point(pt, 5)
        elif self.parent_wg.move_mode == MODE_MOVE_HOR_BORDER:  # двигаем горизонтальные стороны
            self.parent_wg.set_selection_point(pt, 6)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_wg.move_mode in (MODE_MOVE_CORNER, MODE_MOVE_VERT_BORDER, MODE_MOVE_HOR_BORDER):
                self.unsetCursor()
                self.parent_wg.selections[self.parent_wg.selected_rect].update_r_f(
                    self.parent_wg.scr_w, self.parent_wg.scr_h, self.parent_wg.eth_w, self.parent_wg.eth_h
                )
                if self.parent_wg.selections[self.parent_wg.selected_rect].is_null():
                    ind = self.parent_wg.selections_all.index(self.parent_wg.selections[self.parent_wg.selected_rect])
                    self.parent_wg.selections_all.pop(ind)
                    self.parent_wg.selections.pop(self.parent_wg.selected_rect)
                    self.parent_wg.selected_rect = -1
                    self.child_wg.update()
                    self.parent_wg.rect_selected.emit(False)

            elif self.parent_wg.move_mode == MODE_MOVE_ALL:
                self.parent_wg.selections[self.parent_wg.selected_rect].update_r_f(
                    self.parent_wg.scr_w, self.parent_wg.scr_h, self.parent_wg.eth_w, self.parent_wg.eth_h
                )
            self.parent_wg.move_mode = MODE_MOVE_NONE
        super().mouseReleaseEvent(event)

    def wheelEvent(self, wheelEvent: QWheelEvent):
        if wheelEvent.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Точка wheelEvent.pos() - это положение курсора относительно левого верхнего угла контейнера
            # containerWidget (этот угол может находиться за пределами видимости)
            # Точка self.mapToParent(wheelEvent.pos()) - это положение курсора относительно левого верхнего угла
            # всего виджета siaPdfView

            val = wheelEvent.angleDelta().y()
            if val > 0:
                self.parent_wg.scale_image(1.25, self.mapToParent(wheelEvent.pos()))
            elif val < 0:
                self.parent_wg.scale_image(0.8, self.mapToParent(wheelEvent.pos()))
        elif wheelEvent.modifiers() == Qt.KeyboardModifier.NoModifier:
            val = wheelEvent.angleDelta().y()
            if val > 0:
                self.parent_wg.goto_prev_page()
            elif val < 0:
                self.parent_wg.goto_next_page()
        else:
            self.parent().wheelEvent(wheelEvent)


class PageWidget(QLabel):  # pylint: disable=too-many-instance-attributes
    """Виджет для отображения страницы файла PDF"""

    def __init__(self, parent: ContainerWidget = None, scrollWidget: SiaPdfView = None):
        super().__init__(parent)
        self.parent_wg = parent
        self.scroll_wg = scrollWidget

        self.pen = QPen()
        self.pen.setWidth(1)
        self.pen.setStyle(Qt.PenStyle.DashLine)
        self.pen.setColor(QColor.fromRgb(255, 0, 0, 255))

        self.pen_dis = QPen()
        self.pen_dis.setWidth(1)
        self.pen_dis.setStyle(Qt.PenStyle.SolidLine)
        self.pen_dis.setColor(QColor.fromRgb(128, 128, 128, 255))

        self.pen2 = QPen()
        self.pen2.setWidth(1)
        self.pen2.setStyle(Qt.PenStyle.SolidLine)
        self.pen2.setColor(QColor.fromRgb(255, 0, 0, 255))

        self.fill = QBrush()
        self.fill.setStyle(Qt.BrushStyle.SolidPattern)
        self.fill.setColor(QColor.fromRgb(255, 255, 0, 64))

        self.fill_all = QBrush()
        self.fill_all.setStyle(Qt.BrushStyle.SolidPattern)
        self.fill_all.setColor(QColor.fromRgb(0, 255, 0, 64))

        self.fill_dis = QBrush()
        self.fill_dis.setStyle(Qt.BrushStyle.BDiagPattern)
        self.fill_dis.setColor(QColor.fromRgb(0, 0, 0, 64))

        self.fill2 = QBrush()
        self.fill2.setStyle(Qt.BrushStyle.SolidPattern)
        # self.fill2.setColor(QColor.fromRgb(255,0,0,255))
        self.fill2.setColor(QColor.fromRgb(255, 255, 255, 255))

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        if len(self.scroll_wg.selections):
            painter = QPainter()
            painter.begin(self)
            for i, r in enumerate(self.scroll_wg.selections):
                if r.enabled:
                    painter.setPen(self.pen)
                    if r.pno == -1:
                        painter.setBrush(self.fill_all)
                    else:
                        painter.setBrush(self.fill)
                    painter.drawRect(r.get_rect())
                    if i == self.scroll_wg.selected_rect:
                        # painter.setPen(Qt.PenStyle.NoPen)
                        painter.setPen(self.pen2)
                        painter.setBrush(self.fill2)
                        painter.drawRect(r.x1() - 3, r.y1() - 3, 6, 6)
                        painter.drawRect(r.x2() - 3, r.y1() - 3, 6, 6)
                        painter.drawRect(r.x1() - 3, r.y2() - 3, 6, 6)
                        painter.drawRect(r.x2() - 3, r.y2() - 3, 6, 6)

                        xc = (r.x1() + r.x2()) // 2
                        yc = (r.y1() + r.y2()) // 2
                        painter.drawRect(xc - 3, r.y1() - 3, 6, 6)
                        painter.drawRect(r.x1() - 3, yc - 3, 6, 6)
                        painter.drawRect(r.x2() - 3, yc - 3, 6, 6)
                        painter.drawRect(xc - 3, r.y2() - 3, 6, 6)
                else:
                    painter.setPen(self.pen_dis)
                    painter.setBrush(self.fill_dis)
                    painter.drawRect(r.get_rect())
            painter.end()

        # with QPainter(self) as painter:
        #     srcPoint = QPoint(self.scroll_wg.viewport().width() // 2,
        #          self.scroll_wg.viewport().height() // 2)
        #     srcPoint = self.mapFromParent(self.parent_wg.mapFromParent(srcPoint))
        #     painter.setPen(Qt.PenStyle.SolidLine)
        #     painter.setPen(QColor.fromRgb(0,0,255,255))
        #     painter.drawLine(srcPoint.x() - 30, srcPoint.y(), srcPoint.x() + 30, srcPoint.y())
        #     painter.drawLine(srcPoint.x(), srcPoint.y() - 30, srcPoint.x(), srcPoint.y() + 30)
