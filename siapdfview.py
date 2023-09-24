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
from PySide2.QtCore import QPoint  # QDir, QStandardPaths,
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
from PySide2.QtWidgets import QComboBox
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
from PySide2.QtWidgets import QWidget
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol


def InfoMsgBox(parent, title: str, text: str):
    m_MsgBox = QMessageBox(parent)
    m_MsgBox.setIcon(QMessageBox.Icon.Information)
    m_MsgBox.setWindowTitle(title)
    m_MsgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
    m_MsgBox.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
    m_MsgBox.setDefaultButton(QMessageBox.StandardButton.Ok)
    m_MsgBox.setText(text)
    m_MsgBox.exec()


class selectionRect:
    """Класс для хранения данных о выделенных областях"""

    def __init__(self, pno=-1):
        self.pno = pno
        self.r = QRect(0, 0, 0, 0)
        self.rF = QRectF(0.0, 0.0, 0.0, 0.0)
        self.enabled = True
        # self.selected = False

    def getRect(self):
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

    def update_rF(self, scr_w: int, scr_h: int, eth_w: int, eth_h: int):
        """Пересчитать "эталлонный" QRect в соответствии с указанным масштабом и
        текущими экранными размерами выделенной области

        Args:
            scr_w (int): экранная ширина страницы
            scr_h (int): экранная высота страницы
            eth_w (int): ширина эталлоной страницы
            eth_h (int): высота эталлоной страницы
        """
        self.normalize()
        self.rF.setX(self.r.x() * eth_w / scr_w)
        self.rF.setY(self.r.y() * eth_h / scr_h)
        self.rF.setWidth((self.r.width() + 1) * eth_w / scr_w)
        self.rF.setHeight((self.r.height() + 1) * eth_h / scr_h)

        # print(self.r, scr_w, scr_h, self.rF, eth_w, eth_h)

    def update_r(self, scr_w: int, scr_h: int, eth_w: int, eth_h: int, check_size=False):
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
            # self.rF = self.rF.intersected(QRectF(0, 0, eth_w, eth_h))
            # if not QRectF(0, 0, eth_w, eth_h).contains(self.rF):
            #     return False
            self.enabled = QRectF(0, 0, eth_w, eth_h).contains(self.rF)

        self.r.setX(round(self.rF.x() * scr_w / eth_w))
        self.r.setY(round(self.rF.y() * scr_h / eth_h))
        self.r.setWidth(round((self.rF.x() + self.rF.width()) * scr_w / eth_w) - self.r.x() - 1)
        self.r.setHeight(round((self.rF.y() + self.rF.height()) * scr_h / eth_h) - self.r.y() - 1)
        return True

    def getScaledRect(self, new_w: int, new_h: int, eth_w: int, eth_h: int):
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
        m_r.setX(round(self.rF.x() * new_w / eth_w))
        m_r.setY(round(self.rF.y() * new_h / eth_h))
        m_r.setWidth(round(self.rF.width() * new_w / eth_w))
        m_r.setHeight(round(self.rF.height() * new_h / eth_h))
        return m_r

    def setX1Y1X2Y2(self, pt1: QPoint, pt2: QPoint):
        """Установить параметры экранного QRect исходя их координат двух переданных точек
        ("эталонный" QRect не пересчитывается)

        Args:
            pt1 (QPoint): точка первого угла прямоугольной области
            pt2 (QPoint): точка второго (диагонально противоположного) угла прямоугольной области
        """
        self.r.setRect(pt1.x(), pt1.y(), pt2.x() - pt1.x(), pt2.y() - pt1.y())

    def x1(self):
        """Получить координату X первого угла экранного QRect

        Returns:
            int: координата X
        """
        return self.r.x()

    def y1(self):
        """Получить координату Y первого угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.r.y()

    def x2(self):
        """Получить координату X второго угла экранного QRect

        Returns:
            int: координата X
        """
        return self.r.x() + self.r.width()

    def y2(self):
        """Получить координату Y второго угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.r.y() + self.r.height()

    def isNull(self):
        """Проверить выделенную область на соответствие минимальному размеру

        Returns:
            bool: признак соответствия минимально допустимому размеру
        """
        return abs(self.rF.width()) < 15 or abs(self.rF.height()) < 15

    def dirRect(self, pt: QPoint):
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
            return 0
        r = self.r
        xc = (self.x1() + self.x2()) // 2
        yc = (self.y1() + self.y2()) // 2
        offs = 4
        if r.x() - offs < pt.x() < r.x() + offs:  # левая сторона
            if r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
                return 1
            elif r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
                return 7
            elif yc - offs < pt.y() < yc + offs:  # середина по вертикали
                return 4
        elif r.right() - offs + 1 < pt.x() < r.right() + offs + 1:  # правая сторона
            if r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
                return 3
            elif r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
                return 9
            elif yc - offs < pt.y() < yc + offs:  # середина по вертикали
                return 6
        elif r.y() - offs < pt.y() < r.y() + offs:  # верхняя сторона
            if xc - offs < pt.x() < xc + offs:  # середина по горизонтали
                return 2
        elif r.bottom() - offs + 1 < pt.y() < r.bottom() + offs + 1:  # нижняя сторона
            if xc - offs < pt.x() < xc + offs:  # середина по горизонтали
                return 8

        if r.contains(pt):
            return 5
        return 0

    def adjustPosition(self, w: int, h: int):
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

    def shiftX(self, offs: int, shft: bool, w: int, h: int):
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
            self.adjustPosition(w, h)
        return self

    def shiftY(self, offs: int, shft, w: int, h: int):
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
            self.adjustPosition(w, h)
        return self


# noinspection PyUnresolvedReferences
class zoomSlider(QSlider):
    """Виджет слайдера для выбора масштаба просмотра страницы"""

    zoomSliderDoubleClicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event):
        self.zoomSliderDoubleClicked.emit()


# noinspection PyUnresolvedReferences
class zoomSelector(QWidget):
    """Виджет выбора масштаба просмотра страницы (на основе слайдера)"""

    zoomFactorChanged = Signal(float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedWidth(190)

        self.passemit = False

        self.horizontalLayout = QHBoxLayout(self)
        self.horizontalLayout.setSpacing(5)
        self.horizontalLayout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.Slider = zoomSlider(self)
        self.Slider.setFixedWidth(120)
        self.Slider.setMinimum(20)
        self.Slider.setMaximum(300)
        self.Slider.setValue(100)
        # self.Slider.setTickInterval(100)
        # self.Slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.Slider.setOrientation(Qt.Horizontal)

        # self.lblValue = QLabel(self)
        self.lblValue = QLineEdit(self)
        self.lblValue.setFixedWidth(45)
        self.lblValue.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.lblValue.setText("100%")
        self.lblValue.setReadOnly(True)
        self.horizontalLayout.addWidget(self.Slider)
        self.horizontalLayout.addWidget(self.lblValue)

        self.Slider.valueChanged.connect(self.valueChanged)
        self.Slider.zoomSliderDoubleClicked.connect(self.reset)
        self.lblValue.setEnabled(False)
        self.Slider.setEnabled(False)

    @Slot(float)
    def setZoomFactor(self, zoomFactor: float):
        self.passemit = True
        self.Slider.setValue(int(zoomFactor * 100))

    @Slot()
    def reset(self):
        self.Slider.setValue(100)
        self.valueChanged(100)

    @Slot(int)
    def valueChanged(self, value):
        self.lblValue.setText(f"{value}%")
        if not self.passemit:
            self.zoomFactorChanged.emit(value / 100.0)
        self.passemit = False

    @Slot(bool)
    def setDisabled(self, fl: bool):
        self.setEnabled(not fl)

    @Slot(bool)
    def setEnabled(self, fl: bool):
        self.lblValue.setEnabled(fl)
        self.Slider.setEnabled(fl)


# noinspection PyUnresolvedReferences
class zoomSelectorCB(QComboBox):
    """Виджет выбора масштаба просмотра страницы (на основе комбобокса)"""

    zoomFactorChanged = Signal(float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setEditable(True)

        # self.addItem("По ширине страницы")
        # self.addItem("Страница целиком")
        self.addItem("20%")
        self.addItem("40%")
        self.addItem("60%")
        self.addItem("80%")
        self.addItem("100%")
        self.addItem("120%")
        self.addItem("150%")
        self.addItem("200%")
        self.addItem("250%")
        self.addItem("300%")

        self.currentTextChanged.connect(self.on_current_text_changed)
        # self.lineEdit().editingFinished.connect(self._editing_finished)
        self.setEnabled(False)
        self.lineEdit().setReadOnly(True)
        # self.setEditable(False)

    @Slot(float)
    def setZoomFactor(self, zoomFactor):
        percent = int(zoomFactor * 100)
        self.setCurrentText(f"{percent}%")

    @Slot()
    def reset(self):
        self.setCurrentIndex(4)  # 100%

    @Slot(str)
    def on_current_text_changed(self, text):
        # if text == "По ширине страницы":
        #     self.zoom_mode_changed.emit(QPdfView.ZoomMode.FitToWidth)
        # elif text == "Страница целиком":
        #     self.zoom_mode_changed.emit(QPdfView.ZoomMode.FitInView)
        # elif text.endswith("%"):
        if text.endswith("%"):
            # factor = 1.0
            zoom_level = int(text[:-1])
            factor = zoom_level / 100.0
            # self.zoom_mode_changed.emit(QPdfView.ZoomMode.Custom)
            self.zoomFactorChanged.emit(factor)

    @Slot()
    def _editing_finished(self):
        self.on_current_text_changed(self.lineEdit().text())


# noinspection PyBroadException,PyUnresolvedReferences
class siaPdfView(QScrollArea):
    """Виджет-основная прокручиваемая область просмотра"""

    currentPageChanged = Signal(int)
    zoomFactorChanged = Signal(float)
    rectSelected = Signal(bool)
    scrollRequested = Signal(QPoint, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._psw = ''
        self._current_page = -1
        self._scale_factor = 1.0
        self._dpi = 300

        ppi = 96
        self.dpi = ppi * 3
        zoom = self.dpi / 72
        self._matrix = fitz.Matrix(zoom, zoom)

        self._scr_w = 0
        self._scr_h = 0
        self._eth_w = 0
        self._eth_h = 0

        self.selectionPoint1 = QPoint(0, 0)
        self.selectionPoint2 = QPoint(0, 0)
        self.movePoint = QPoint(0, 0)

        self.selectedRect = -1
        self.selectionsMax = 10000
        self.selections = []
        self.selections_all = []

        self.move_mode = 0
        # self.mousePos = QPoint(0, 0)

        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self.setFrameStyle(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._container = containerWidget(self)
        self._container.setBackgroundRole(QPalette.ColorRole.Dark)
        self._container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._container.setFixedSize(50, 50)
        self._container.move(0, 0)

        self._pageimage = pageWidget(self._container, self)
        self._pageimage.setBackgroundRole(QPalette.ColorRole.Base)
        self._pageimage.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._pageimage.setScaledContents(True)

        self._container.setWidget(self._pageimage)
        self.setWidget(self._container)

        self._container.setMouseTracking(True)
        self._pageimage.setMouseTracking(True)
        self._container.setVisible(False)

        self.scrollRequested.connect(self.scrollPointToPoint)

    def combine(self, filelist: list):
        m_MsgBox = QMessageBox(self)
        m_MsgBox.setIcon(QMessageBox.Icon.Question)
        m_MsgBox.setWindowTitle("Ошибка открытия файла")
        m_MsgBox.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.YesToAll | QMessageBox.StandardButton.Cancel
        )
        m_MsgBox.setDefaultButton(QMessageBox.StandardButton.Yes)
        m_MsgBox.button(QMessageBox.StandardButton.Yes).setText('  Пропустить  ')
        m_MsgBox.button(QMessageBox.StandardButton.YesToAll).setText('  Пропустить все  ')
        m_MsgBox.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

        skipAll = False

        self.close()
        self._doc = fitz.Document()
        for filename in filelist:
            try:
                doc = fitz.Document(filename)
                if not doc.is_pdf:
                    pdfbytes = doc.convert_to_pdf()
                    doc.close()
                    doc = fitz.open("pdf", pdfbytes)
                #     doc.close()
                #     continue
                if doc.needs_pass:
                    self._decrypt_doc(filename, doc)
            except Exception as e:
                if skipAll:
                    continue
                # QMessageBox.critical(self, "Ошибка открытия файла", f"Ошибка: {e}\nФайл: {filename}")
                m_MsgBox.setText(f'Ошибка: {e}\nФайл: {filename}')
                res = m_MsgBox.exec()
                if res == QMessageBox.StandardButton.Cancel:
                    self.close()
                    return
                elif res == QMessageBox.StandardButton.YesToAll:
                    skipAll = True
                continue
            if not doc.is_encrypted:
                self._doc.insert_pdf(doc, from_page=0, to_page=len(doc) - 1)
            doc.close()
        if len(self._doc):
            self._scale_factor = 1.0
            self._show_page(0)
            self._container.setVisible(True)
            self.zoomFactorChanged.emit(self._scale_factor)
        else:
            self.close()

    def open(self, filename: str):
        self.close()
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
            self._scale_factor = 1.0
            self._show_page(0)
            self._container.setVisible(True)
            self.zoomFactorChanged.emit(self._scale_factor)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка открытия файла", f"Ошибка: {e}\nФайл: {filename}")
            self.close()

    def _decrypt_doc(self, filename: str, doc: fitz.Document):
        m_InputDlg = QInputDialog(self)
        m_InputDlg.setWindowTitle("Введите пароль")
        m_InputDlg.setLabelText(f"Для открытия файла '{filename}' требуется пароль!\nВведите пароль:")
        m_InputDlg.setOkButtonText('ОК')
        m_InputDlg.setCancelButtonText('Отмена')
        m_InputDlg.setInputMode(QInputDialog.InputMode.TextInput)
        m_InputDlg.setTextEchoMode(QLineEdit.Password)
        while True:
            m_InputDlg.setTextValue('')
            # pw, res = m_InputDlg.getText(self,)
            res = m_InputDlg.exec_()
            if res == QDialog.DialogCode.Accepted:
                self._psw = m_InputDlg.textValue()
                doc.authenticate(self._psw)
            else:
                return
            if not doc.is_encrypted:
                return
            m_InputDlg.setLabelText(
                f"Пароль открытия файла '{filename}' не верный!\nВведите правильный, либо нажмите 'Отмена':"
            )

    def close(self):
        if self._doc is not None:
            self._doc.close()
            self._doc = None
            self._current_page = -1
            self._container.setVisible(False)
            self._container.setFixedSize(50, 50)
            self._container.move(0, 0)
            self.selections = []
            self.selections_all = []
            self.selectedRect = -1
            self.rectSelected.emit(False)

    def currentPage(self):
        return self._current_page

    def selectionsCount(self):
        return len(self.selections)

    def selectionsAllCount(self):
        return len(self.selections_all)

    def pageCount(self):
        try:
            return self._doc.page_count
        except Exception:
            return 0

    def goToPage(self, pno: int):
        self._show_page(pno)

    def goToNextPage(self):
        if self._current_page < self._doc.page_count - 1:
            self._show_page(self._current_page + 1)

    def goToPrevPage(self):
        if self._current_page > 0:
            self._show_page(self._current_page - 1)

    def zoomIn(self):
        self._scale_image(1.25)

    def zoomOut(self):
        self._scale_image(0.8)

    @Slot(float)
    def setZoomFactor(self, factor):
        self._scale_image(1, None, factor)

    @Slot()
    def copyPageImageToClipboard(self):
        if self._current_page > -1:
            img = self._pageimage.pixmap().toImage()
            dpm = self._dpi / 0.0254
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
            QGuiApplication.clipboard().setImage(img)

    @Slot()
    def copyRectImageToClipboard(self):
        if self._current_page > -1 and self.selectedRect > -1:
            img = self._pageimage.pixmap().toImage()
            dpm = self._dpi / 0.0254
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
            r = self.selections[self.selectedRect].getScaledRect(1, 1, 1, 1)
            QGuiApplication.clipboard().setImage(img.copy(r))

    @Slot()
    def copyRectTextToClipboard(self, trim: bool = False):
        if self._current_page > -1 and self.selectedRect > -1:
            r = self.selections[self.selectedRect].rF
            rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
            rc = rc / self._matrix
            rc = rc / self._doc[self._current_page].rotation_matrix
            recttext = self._doc[self._current_page].get_text("text", clip=rc).rstrip()
            if trim:
                recttext = re.sub(r'\s+', ' ', recttext)
            if not recttext:
                InfoMsgBox(self, 'Копирование текста', 'В выделенном участке отсутствует текст в текстовом слое.')
            else:
                QGuiApplication.clipboard().setText(recttext)

    @Slot()
    def recognizeAndCopyToClipboard(self, tesseract_cmd: str, trim: bool):
        if self._current_page > -1 and self.selectedRect > -1:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            img = self._pageimage.pixmap().toImage()
            r = self.selections[self.selectedRect].getScaledRect(1, 1, 1, 1)
            img = ImageQt.fromqimage(img.copy(r))
            recttext = pytesseract.image_to_string(img, lang='rus+eng')
            if trim:
                recttext = re.sub(r'\s+', ' ', recttext)
            if not recttext:
                InfoMsgBox(self, 'Распознание текста', 'В выделенном участке не удалось распознать текст.')
            else:
                QGuiApplication.clipboard().setText(recttext)

    @Slot()
    def recognizeQRAndCopyToClipboard(self):
        if self._current_page > -1 and self.selectedRect > -1:
            img = self._pageimage.pixmap().toImage()
            r = self.selections[self.selectedRect].getScaledRect(1, 1, 1, 1)
            img = ImageQt.fromqimage(img.copy(r))
            decocdeQR = decode(img, [ZBarSymbol.QRCODE])
            if not decocdeQR:
                img = ImageOps.invert(img)
                decocdeQR = decode(img, [ZBarSymbol.QRCODE])
            if not decocdeQR:
                InfoMsgBox(self, 'Распознание QR-кодов', 'Данные не распознаны.')
            else:
                txt = ''
                for QRobj in decocdeQR:
                    txt += ('\n-------------------\n' if txt else '') + QRobj.data.decode('utf-8')

                QGuiApplication.clipboard().setText(txt)

    @Slot(bool)
    def copyRectsInfoToClipboard(self, fl_all: bool = False):
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
                if self.selectedRect > -1:
                    selected = self.selections[self.selectedRect]
                else:
                    selected = None

                # selssort_key = lambda r: (r.pno, r.rF.y(), r.rF.x())
                def selssort_key(x):
                    return x.pno, x.rF.y(), x.rF.x()

                sels.sort(key=selssort_key)
                pno = self._current_page
                for i, s in enumerate(sels):
                    r = s.rF
                    rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                    rc = rc / self._matrix
                    if fl_all:
                        pno = max(s.pno, 0)
                    # rc = rc / self._doc[pno].rotation_matrix

                    recttext += f"{i + 1}{'*' if s is selected else ''}, {pno + 1}{'**' if s.pno == -1 else ''}"
                    if fl_all:
                        recttext += f", {self._doc[pno].rotation}"
                    recttext += f": ({round(rc.x0, 2)}, {round(rc.y0, 2)}, {round(rc.x1, 2)}, {round(rc.y1, 2)})\n"

            QGuiApplication.clipboard().setText(recttext)
            InfoMsgBox(self, 'Информация о выделенных участках', recttext)

    @Slot()
    def switchRectMode(self):
        if self._current_page > -1 and self.selectedRect > -1:
            r = self.selections[self.selectedRect]
            if r.pno == -1:
                r.pno = self._current_page
            else:
                r.pno = -1
            self._pageimage.update()

    def pagesRotate(self, n_dir: int, fl_all: bool):
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
                        r = sel.rF
                        rc = fitz.Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
                        rc = (rc / src_rot_mat) * dst_rot_mat
                        r.setRect(rc.x0, rc.y0, rc.x1 - rc.x0, rc.y1 - rc.y0)
                pno += 1

            pno = self._current_page
            self._current_page = -1
            self._show_page(pno)

    def addSelection(self, pno, r):
        sel = selectionRect(pno)
        rot_r = (r * self._doc[pno].rotation_matrix) * self._matrix
        rot_r.normalize()
        sel.rF.setCoords(rot_r.x0, rot_r.y0, rot_r.x1, rot_r.y1)
        self.selections_all.append(sel)
        if pno == self._current_page:
            sel.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h)
            self.selections.append(sel)
            self._pageimage.update()

    def getSelectionFitzRect(self, pno, old_rot, sel: selectionRect):
        cur_rot = self._doc[pno].rotation
        if cur_rot != old_rot:
            self._doc[pno].set_rotation(old_rot)
        r = fitz.Rect(sel.rF.x(), sel.rF.y(), sel.rF.x() + sel.rF.width(), sel.rF.y() + sel.rF.height())
        r = (r / self._matrix) / self._doc[pno].rotation_matrix
        if cur_rot != old_rot:
            self._doc[pno].set_rotation(cur_rot)
        return r

    @Slot(bool)
    def selectAll(self):
        if self._current_page > -1:
            max_rect = QRectF(0, 0, self._eth_w, self._eth_h)
            for sel in self.selections:
                if sel.rF == max_rect:
                    self.selectedRect = self.selections.index(sel)
                    break
            else:
                self.selectedRect = len(self.selections)
                new_sel = selectionRect(self._current_page)
                new_sel.rF = max_rect
                new_sel.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h)

                self.selections.append(new_sel)
                self.selections_all.append(new_sel)

            self._pageimage.update()
            self.rectSelected.emit(True)

    @Slot(bool)
    def removeSelection(self, removeAll=False):
        if removeAll:
            self.selections.clear()
            self.selections_all.clear()
        else:
            if self._current_page > -1:
                if self.selectedRect > -1:
                    ind = self.selections_all.index(self.selections[self.selectedRect])
                    self.selections_all.pop(ind)
                    self.selections.pop(self.selectedRect)
        self.selectedRect = -1
        self._pageimage.update()
        self.rectSelected.emit(False)

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

        if key in [Qt.Key.Key_PageUp, Qt.Key.Key_PageDown]:
            return

        # print(key)
        if key in [Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space]:
            if len(self.selections):
                if shft:
                    if self.selectedRect == 0:
                        self.selectedRect = len(self.selections)
                    self.selectedRect -= 1
                else:
                    self.selectedRect += 1
                    if self.selectedRect == len(self.selections):
                        self.selectedRect = 0
                self.rectSelected.emit(True)
                p_pt = self._pageimage.mapToParent(self.selections[self.selectedRect].r.topLeft())
                self.ensureVisible(p_pt.x(), p_pt.y(), 50, 50)

        if self.selectedRect == -1:
            # self.parent().keyPressEvent(event)
            # self._pageimage.update()
            super().keyPressEvent(event)
            return

        flUpdate = True
        flUpdateRf = True
        dx = dy = 0
        # if key == Qt.Key.Key_...:
        #     self.selections.pop(self.selectedRect)
        #     self.selectedRect = -1
        #     flUpdateRf = False
        #     self.rectSelected.emit(False)
        if alt:
            flUpdate = False
            if key == Qt.Key.Key_Left:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Right:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
            elif key == Qt.Key.Key_Up:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 10)
            elif key == Qt.Key.Key_Down:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 10)
        else:
            if key in [Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space]:
                pass
            elif key == Qt.Key.Key_Left:
                dx = (
                    -self.selections[self.selectedRect]
                    .shiftX(-1 if ctrl else -10, shft, self._pageimage.width(), self._pageimage.height())
                    .x2()
                )
            elif key == Qt.Key.Key_Right:
                if shft:
                    dx = (
                        self.selections[self.selectedRect]
                        .shiftX(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .x2()
                    )
                else:
                    dx = (
                        self.selections[self.selectedRect]
                        .shiftX(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .x1()
                    )
            elif key == Qt.Key.Key_Up:
                dy = (
                    -self.selections[self.selectedRect]
                    .shiftY(-1 if ctrl else -10, shft, self._pageimage.width(), self._pageimage.height())
                    .y2()
                )
            elif key == Qt.Key.Key_Down:
                if shft:
                    dy = (
                        self.selections[self.selectedRect]
                        .shiftY(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .y2()
                    )
                else:
                    dy = (
                        self.selections[self.selectedRect]
                        .shiftY(1 if ctrl else 10, shft, self._pageimage.width(), self._pageimage.height())
                        .y1()
                    )
            # elif key == Qt.Key_D:
            #     self.one_line_down()
            else:
                flUpdate = False
                flUpdateRf = False
                super().keyPressEvent(event)
                # self.parent().keyPressEvent(event)

            if dx or dy:
                vp_topLeft = self._container.mapFromParent(QPoint(0, 0))
                vp_x_min = vp_topLeft.x() + 20
                vp_y_min = vp_topLeft.y() + 20
                vp_x_max = vp_topLeft.x() + self.viewport().width() - 21
                vp_y_max = vp_topLeft.y() + self.viewport().height() - 21
                if dx > vp_x_max or (dx < 0 and -dx < vp_x_min):
                    self.ensureVisible(abs(dx), vp_y_min, 20, 0)
                elif dy > vp_y_max or (dy < 0 and -dy < vp_y_min):
                    self.ensureVisible(vp_x_min, abs(dy), 0, 20)

            if flUpdateRf:
                self.selections[self.selectedRect].update_rF(self._scr_w, self._scr_h, self._eth_w, self._eth_h)

            # print(self._pageimage.mapToParent(self._pageimage.selections[self._pageimage.selectedRect].getRect().topLeft()))
            # p_pt = self.mapTo(self.scroll_wg, pt)
            # self.move(self.x() - dx, self.y() - dy)
            # self.parent_wg.scrollContentsBy(dx, dy)

        if flUpdate:
            self._pageimage.update()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._pageimage.update()

    @Slot(QPoint, QPoint)
    def scrollPointToPoint(self, src_pt: QPoint, dest_pt: QPoint):
        """Попытаться прокрутить рабочую область так, чтобы точка из системы координат изображения src_pt
           оказалась в точке dest_pt системы координат области

        Args:
            src_pt (QPoint): точка из системы координат изображения
            dest_pt (QPoint): точка в системе координат рабочей области
        """
        # Переводим точку src_pt в систему координат рабочей области
        src_pt = self._container.mapToParent(self._pageimage.mapToParent(src_pt))

        # print('srcPoint на экране после изм. масшт. и оторисовки:', src_pt)
        # print(dest_pt.x(), src_pt.x(), (src_pt - dest_pt).x())

        # Тупо сдвигаем содержимое рабочей области на разницу в координатах
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + src_pt.x() - dest_pt.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + src_pt.y() - dest_pt.y())

    def _set_sizes(self):
        ww = max(self.viewport().width(), self._pageimage.width() + 20)
        hh = max(self.viewport().height(), self._pageimage.height() + 20)
        self._container.setFixedHeight(hh)
        self._container.setFixedWidth(ww)
        # self._pageimage.move((ww - self._pageimage.width()) // 2,
        #                     (hh - self._pageimage.height()) // 2)
        self._pageimage.move((ww - self._pageimage.width()) // 2, 10)

    def _set_image(self, new_image):
        self._pageimage.setPixmap(QPixmap.fromImage(new_image))
        # self._scale_factor = 1.0
        new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
        self._pageimage.resize(new_size)
        self._set_sizes()
        self._scr_w = new_size.width()
        self._scr_h = new_size.height()

    def _show_page(self, pno):
        if self._current_page != pno:
            # print(self._doc[pno].rect.width, self._doc[pno].rect.height)
            self._current_page = pno
            pix = self._doc[pno].get_pixmap(alpha=False, matrix=self._matrix, colorspace=fitz.csRGB)

            new_image = QImage(pix.samples_mv, pix.width, pix.height, pix.width * 3, QImage.Format_RGB888)

            # chk_rects = (self._eth_w > pix.width or self._eth_h > pix.height)
            self._eth_w = pix.width
            self._eth_h = pix.height
            if new_image.isNull():
                pass
            else:
                self._set_image(new_image)

            # if self.selectedRect > -1 and self.selections[self.selectedRect].pno > -1:
            self.selectedRect = -1
            self.selections = [sel for sel in self.selections_all if (sel.pno == -1 or sel.pno == pno)]

            # if chk_rects:
            i = len(self.selections)
            while i > 0:
                i -= 1
                r = self.selections[i]
                # Если не вмещается в страницу, дизейблим...
                r.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h, True)
                # Если не вмещается в страницу, то не показываем...
                # if not r.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h, True):
                #     self.selections.pop(i)
                # if r.isNull():
                #     self.selections.pop(i)
                #     ind = self.selections_all.index(r)
                #     self.selections_all.pop(ind)
                #     # if self.selectedRect == i:
                #     #     self.selectedRect = -1
                #     # self.rectSelected.emit(self.selectedRect > -1)

            self.rectSelected.emit(False)
            self.currentPageChanged.emit(pno)

    def _normal_size(self):
        self._scale_factor = 1.0
        new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
        self._pageimage.resize(new_size)
        self._scr_w = new_size.width()
        self._scr_h = new_size.height()
        for r in self._pageimage.selections:
            r.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h)
        self._set_sizes()

    def _scale_image(self, factor, wheelMousePos=None, newscale=1.0):
        if factor != 1:
            newscale = self._scale_factor * factor

        if newscale < 0.2:
            newscale = 0.2
        elif newscale > 3.0:
            newscale = 3.0
        elif 0.95 < newscale < 1.1:
            newscale = 1.0

        # if (factor < 1 and self._scale_factor > 0.1) or \
        #     (factor > 1 and self._scale_factor < 3.3) or \
        #     (factor == 1):

        if self._scale_factor != newscale:
            factor = newscale / self._scale_factor
            self._scale_factor = newscale

            if wheelMousePos is None:
                destPoint = QPoint(0, 0)
            else:
                destPoint = wheelMousePos
                # destPoint = QPoint(self.viewport().width() // 2,
                #                      self.viewport().height() // 2)

            # destPoint - это "якорная" точка относительно левого верхнего угла всего виджета
            # print('--------------------------------------------------')
            # print('destPoint на экране:', destPoint)
            # srcPoint - это "якорная" точка относительно левого верхнего угла страницы документа
            srcPoint = self._pageimage.mapFromParent(self._container.mapFromParent(destPoint))
            # print('srcPoint на листе до изм. масшт.:', srcPoint)
            # приводим srcPoint к новому масштабу
            # srcPoint = srcPoint * factor
            srcPoint.setX(srcPoint.x() * factor)
            srcPoint.setY(srcPoint.y() * factor)
            # print('Коэфф. масштабирования:', factor)
            # print('srcPoint на листе после изм. масшт.:', srcPoint)

            new_size = self._scale_factor / 3 * self._pageimage.pixmap().size()
            self._pageimage.resize(new_size)
            self._scr_w = new_size.width()
            self._scr_h = new_size.height()

            # self._zoom_in_act.setEnabled(self._scale_factor < 3.0)
            # self._zoom_out_act.setEnabled(self._scale_factor > 0.2)
            self._set_sizes()

            for r in self.selections:
                r.update_r(self._scr_w, self._scr_h, self._eth_w, self._eth_h)

            # self.update()
            # self.scrollPointToPoint(srcPoint, destPoint)
            self.zoomFactorChanged.emit(self._scale_factor)
            self.scrollRequested.emit(srcPoint, destPoint)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._current_page != -1:
            self._set_sizes()

    def setSelectionPoint(self, pt: QPoint, nm: int):
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
        # pt.toPointF
        if nm > 10:
            r = self.selections[self.selectedRect]
            if nm in [11, 13, 17, 19]:
                if nm == 19:
                    self.selectionPoint1 = QPoint(r.x1(), r.y1())
                elif nm == 17:
                    self.selectionPoint1 = QPoint(r.x2(), r.y1())
                elif nm == 13:
                    self.selectionPoint1 = QPoint(r.x1(), r.y2())
                elif nm == 11:
                    self.selectionPoint1 = QPoint(r.x2(), r.y2())
                nm = 2
            if nm == 18 or nm == 16:
                self.selectionPoint1 = QPoint(r.x1(), r.y1())
                self.selectionPoint2 = QPoint(r.x2(), r.y2())
                nm = self.move_mode + 2
            elif nm == 12 or nm == 14:
                self.selectionPoint1 = QPoint(r.x2(), r.y2())
                self.selectionPoint2 = QPoint(r.x1(), r.y1())
                nm = self.move_mode + 2
        # pt = self._pageimage.mapFromParent(pt)
        pt.setX(min(max(pt.x(), 0), self._pageimage.width() - 1))
        pt.setY(min(max(pt.y(), 0), self._pageimage.height() - 1))
        if nm in [1, 2, 5, 6]:
            if nm == 1:
                self.selectionPoint1 = pt
                self.selectionPoint2 = pt
            else:
                if nm == 2:
                    self.selectionPoint2 = pt
                elif nm == 5:
                    self.selectionPoint2.setX(pt.x())
                elif nm == 6:
                    self.selectionPoint2.setY(pt.y())
                p_pt = self._pageimage.mapToParent(pt)
                self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)
            self.selections[self.selectedRect].setX1Y1X2Y2(self.selectionPoint1, self.selectionPoint2)
        else:
            if nm == 3:
                self.movePoint = pt
            else:
                dx = pt.x() - self.movePoint.x()
                dy = pt.y() - self.movePoint.y()
                r = self.selections[self.selectedRect]
                r.getRect().adjust(dx, dy, dx, dy)
                # self.selections[self.selectedRect].getRect().adjust(dx, dy, dx, dy)

                dx, dy = r.adjustPosition(self._pageimage.width(), self._pageimage.height())

                p_pt = self._pageimage.mapToParent(pt)
                if dx or dy:
                    pt.setX(pt.x() - dx)
                    pt.setY(pt.y() - dy)

                self.movePoint = pt
                self.ensureVisible(p_pt.x(), p_pt.y(), 10, 10)

        self._pageimage.update()


# noinspection PyProtectedMember,PyUnresolvedReferences
class containerWidget(QWidget):
    """Виджет-контейнер для размещения внутри него страницы документа,
    обеспечения отступов между страницей документа и основной областью просмотра.
    """

    zoomIn = Signal(bool)
    zoomOut = Signal(bool)

    def __init__(self, parent: siaPdfView = None):
        super().__init__(parent)
        self.parent_wg = parent
        self.child_wg = None
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def setWidget(self, childWidget):
        self.child_wg = childWidget

    def mousePressEvent(self, event: QMouseEvent):
        pt = self.child_wg.mapFromParent(event.pos())
        if event.button() in [Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton]:
            if self.parent_wg.selectedRect >= 0:
                r = self.parent_wg.selections[self.parent_wg.selectedRect]
                dirRect = r.dirRect(pt)
                if event.button() == Qt.MouseButton.LeftButton or dirRect == 0:
                    if dirRect == 5:
                        self.parent_wg.move_mode = 2
                        self.parent_wg.setSelectionPoint(pt, 3)
                    # elif dirRect in [1, 3, 7, 9]:
                    elif 0 < dirRect < 10:
                        if dirRect == 4 or dirRect == 6:
                            self.parent_wg.move_mode = 3
                        elif dirRect == 2 or dirRect == 8:
                            self.parent_wg.move_mode = 4
                        else:
                            self.parent_wg.move_mode = 1

                        self.parent_wg.setSelectionPoint(pt, 10 + dirRect)
                        # noinspection PyTypeChecker
                        self.setCursor(Qt.CursorShape.CrossCursor)
                    else:
                        self.parent_wg.selectedRect = -1
                        self.parent_wg.rectSelected.emit(False)
                        self.child_wg.update()

            if self.parent_wg.selectedRect == -1:
                for i, r in enumerate(self.parent_wg.selections):
                    dirRect = r.dirRect(pt)
                    if dirRect == 5:
                        self.parent_wg.selectedRect = i
                        self.parent_wg.rectSelected.emit(True)
                        if event.button() == Qt.MouseButton.RightButton:
                            self.child_wg.update()
                        else:
                            self.parent_wg.move_mode = 2
                            # noinspection PyTypeChecker
                            self.setCursor(Qt.CursorShape.SizeAllCursor)
                            self.parent_wg.setSelectionPoint(pt, 3)
                        break

        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_wg.selectedRect == -1:
                if len(self.parent_wg.selections_all) < self.parent_wg.selectionsMax:
                    self.parent_wg.selectedRect = len(self.parent_wg.selections)
                    newsel = selectionRect(
                        -1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else self.parent_wg._current_page
                    )
                    self.parent_wg.selections.append(newsel)
                    self.parent_wg.selections_all.append(newsel)
                    self.parent_wg.move_mode = 1
                    self.parent_wg.setSelectionPoint(pt, 1)
                    # noinspection PyTypeChecker
                    self.setCursor(Qt.CursorShape.CrossCursor)
                    self.parent_wg.rectSelected.emit(True)
                else:
                    self.child_wg.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # self.parent_wg.mousePos = self.mapToParent(event.pos())
        pt = self.child_wg.mapFromParent(event.pos())
        # print(self.mapToParent(event.pos()), event.pos(), pt)
        if self.parent_wg.move_mode == 0:
            fl = 0
            for i, r in enumerate(self.parent_wg.selections):
                dirRect = r.dirRect(pt)
                if i == self.parent_wg.selectedRect:
                    if dirRect == 5:
                        fl = 2
                        break
                    elif dirRect in [1, 9]:
                        fl = 3
                        break
                    elif dirRect in [3, 7]:
                        fl = 4
                        break
                    elif dirRect in [2, 8]:
                        fl = 5
                        break
                    elif dirRect in [4, 6]:
                        fl = 6
                        break
                else:
                    if dirRect == 5:
                        fl = 1

            if fl == 1:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            elif fl == 2:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif fl == 3:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif fl == 4:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif fl == 5:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif fl == 6:
                # noinspection PyTypeChecker
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.unsetCursor()
        elif self.parent_wg.move_mode == 1:  # двигаем угол
            self.parent_wg.setSelectionPoint(pt, 2)
        elif self.parent_wg.move_mode == 2:  # двигаем всю область
            self.parent_wg.setSelectionPoint(pt, 4)
        elif self.parent_wg.move_mode == 3:  # двигаем вертикальные стороны
            self.parent_wg.setSelectionPoint(pt, 5)
        elif self.parent_wg.move_mode == 4:  # двигаем горизонтальные стороны
            self.parent_wg.setSelectionPoint(pt, 6)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_wg.move_mode in [1, 3, 4]:
                self.unsetCursor()
                self.parent_wg.selections[self.parent_wg.selectedRect].update_rF(
                    self.parent_wg._scr_w, self.parent_wg._scr_h, self.parent_wg._eth_w, self.parent_wg._eth_h
                )
                if self.parent_wg.selections[self.parent_wg.selectedRect].isNull():
                    ind = self.parent_wg.selections_all.index(self.parent_wg.selections[self.parent_wg.selectedRect])
                    self.parent_wg.selections_all.pop(ind)
                    self.parent_wg.selections.pop(self.parent_wg.selectedRect)
                    self.parent_wg.selectedRect = -1
                    self.child_wg.update()
                    self.parent_wg.rectSelected.emit(False)
            elif self.parent_wg.move_mode == 2:
                self.parent_wg.selections[self.parent_wg.selectedRect].update_rF(
                    self.parent_wg._scr_w, self.parent_wg._scr_h, self.parent_wg._eth_w, self.parent_wg._eth_h
                )
                # print('Ok', self.parent_wg.selections[self.parent_wg.selectedRect].r,
                #       self.parent_wg.selections[self.parent_wg.selectedRect].rF)
            self.parent_wg.move_mode = 0
        super().mouseReleaseEvent(event)

    def wheelEvent(self, wheelEvent: QWheelEvent):
        if wheelEvent.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # self.parent_wg.mousePos = self.mapToParent(wheelEvent.pos())
            # print(wheelEvent.pos(), self.parent_wg.mousePos)
            """
            Точка wheelEvent.pos() - это положение курсора относительно левого верхнего угла контейнера containerWidget
            (этот угол может находиться за пределами видимости)
            Точка self.mapToParent(wheelEvent.pos()) - это положение курсора относительно левого верхнего угла
            всего виджета siaPdfView
            """
            val = wheelEvent.angleDelta().y()
            if val > 0:
                self.parent_wg._scale_image(1.25, self.mapToParent(wheelEvent.pos()))
            elif val < 0:
                self.parent_wg._scale_image(0.8, self.mapToParent(wheelEvent.pos()))
        elif wheelEvent.modifiers() == Qt.KeyboardModifier.NoModifier:
            # print(wheelEvent.angleDelta().y())
            val = wheelEvent.angleDelta().y()
            if val > 0:
                self.parent_wg.goToPrevPage()
            elif val < 0:
                self.parent_wg.goToNextPage()
        else:
            self.parent().wheelEvent(wheelEvent)


class pageWidget(QLabel):
    """Виджет для отображения страницы файла PDF"""

    def __init__(self, parent: containerWidget = None, scrollWidget: siaPdfView = None):
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
                    painter.drawRect(r.getRect())
                    if i == self.scroll_wg.selectedRect:
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
                    painter.drawRect(r.getRect())
            painter.end()

        # with QPainter(self) as painter:
        #     srcPoint = QPoint(self.scroll_wg.viewport().width() // 2,
        #          self.scroll_wg.viewport().height() // 2)
        #     srcPoint = self.mapFromParent(self.parent_wg.mapFromParent(srcPoint))
        #     painter.setPen(Qt.PenStyle.SolidLine)
        #     painter.setPen(QColor.fromRgb(0,0,255,255))
        #     painter.drawLine(srcPoint.x() - 30, srcPoint.y(), srcPoint.x() + 30, srcPoint.y())
        #     painter.drawLine(srcPoint.x(), srcPoint.y() - 30, srcPoint.x(), srcPoint.y() + 30)
