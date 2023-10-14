# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import configparser
import io
import os
import re

# import platform
import shutil
import subprocess

# import math
# import datetime
import sys
from itertools import groupby

import fitz
import xlsxwriter
from PIL import Image as PILImage
from PIL import ImageDraw
from PIL import ImageOps
from PySide2.QtCore import QSettings  # QModelIndex, QPoint, QStandardPaths,
from PySide2.QtCore import Qt
from PySide2.QtCore import QUrl
from PySide2.QtCore import Slot
from PySide2.QtWidgets import QAbstractSpinBox  # QSizePolicy, QDialog
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWidgets import QMainWindow
from PySide2.QtWidgets import QMenu
from PySide2.QtWidgets import QMessageBox
from PySide2.QtWidgets import QProgressBar
from PySide2.QtWidgets import QSpinBox
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol

from censoredlg import CensoreDialog
from combinedlg import CombineDialog

# from ui_mainwindow import Ui_MainWindow
from mainwindow_ui import Ui_MainWindow
from saveasdlg import FileFormat
from saveasdlg import PageMode
from saveasdlg import PageRotation
from saveasdlg import SaveAsDialog
from saveasdlg import SaveParams
from siapdfview import siaPdfView
from siapdfview import zoomSelector
from tableanalize import parse_page_tables


ABOUT_TEXT = """
Mini PDF Tools - мини набор инструментов для просмотра и обработки файлов PDF.
Версия от 06.09.2023 (c) 2023 Игорь Степаненков

Используемые пакеты и библиотеки:
PySide2 (c) 2022 The Qt Company Ltd.
PyMuPDF (c) 2023 Artifex Software, Inc.
Pillow - PIL fork by Alex Clark and Contributors
XlsxWriter (c) 2013-2023 John McNamara
PyZBar (c) 2022 Lawrence Hudson
PyTesseract for Google's Tesseract-OCR Engine (c) 2022 Samuel Hoffstaetter
Paomedia Small & Flat Icons
"""


class myQSpinBox(QSpinBox):
    def __init__(self, wg):
        # self.wg = wg
        super().__init__(wg)

    def keyPressEvent(self, e):
        # Отфильтровываем PgUp и PgDn
        if not e.key() in [16777238, 16777239]:
            super().keyPressEvent(e)


# noinspection PyBroadException,PyProtectedMember
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.m_zoomSelector = zoomSelector(self)
        self.m_pageSelector = myQSpinBox(self)
        self.m_MsgBox = QMessageBox(self)
        self.m_currentFileName = ''
        self.m_realFile = False
        self.m_title = ''
        self.m_validExtensions = [
            '.pdf',
            '.png',
            '.jpg',
            '.jpeg',
            '.tif',
            '.tiff',
            '.bmp',
            '.epub',
            '.xps',
            '.oxps',
            '.cbz',
            '.fb2',
        ]
        config = configparser.ConfigParser()
        config = configparser.ConfigParser()
        try:
            config.read(os.path.join(os.path.dirname(__file__), 'settings.ini'))
            self.m_tesseract_cmd = config.get("Settings", "tesseract_cmd", fallback="")
            self.m_pdfviewer_cmd = config.get("Settings", "pdfviewer_cmd", fallback="")
            self.m_xlseditor_cmd = config.get("Settings", "xlseditor_cmd", fallback="")
        except configparser.Error:
            self.m_tesseract_cmd = ""
            self.m_pdfviewer_cmd = ""
            self.m_xlseditor_cmd = ""

        self.ui.setupUi(self)

        self.setMinimumSize(500, 400)

        self.statusBar().showMessage('')
        self.progressBar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progressBar)
        self.progressBar.setGeometry(30, 40, 200, 20)
        # self.statusBar().showMessage('Процесс')
        # self.progressBar.setValue(50)
        self.progressBar.setVisible(False)

        self.m_zoomSelector.setMaximumWidth(150)
        # Вставляем zoomSelector перед actionZoom_In
        self.ui.mainToolBar.insertWidget(self.ui.actionZoom_In, self.m_zoomSelector)

        # Вставляем pageSelector перед actionForward
        self.ui.mainToolBar.insertWidget(self.ui.actionNext_Page, self.m_pageSelector)
        self.m_pageSelector.setEnabled(False)
        self.m_pageSelector.valueChanged.connect(self.page_selected)
        self.m_pageSelector.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.m_pageSelector.setSuffix(' из 0')
        self.m_pageSelector.setMinimumWidth(70)
        # noinspection PyTypeChecker
        self.m_pageSelector.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.pdfView = siaPdfView(self)
        self.setCentralWidget(self.pdfView)
        # self.centralWidget(). insertWidget(self.centralWidget(), self.pdfView)
        # self.centralWidget().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.centralWidget().setLayout(Qt.QLay)

        self.pdfView.currentPageChanged.connect(self.page_select)
        self.pdfView.rectSelected.connect(self.rect_selected)
        self.pdfView.zoomFactorChanged.connect(self.m_zoomSelector.setZoomFactor)

        # self.m_zoomSelector.zoom_mode_changed.connect(self.pdfView.setZoomMode)
        self.m_zoomSelector.zoomFactorChanged.connect(self.pdfView.setZoomFactor)
        self.m_zoomSelector.reset()

        self.pdfView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pdfView.customContextMenuRequested.connect(self.show_context_menu)
        self.popMenu = QMenu(self)
        self.popMenu.addAction(self.ui.actionCbdRectTextCopy)
        self.popMenu.addAction(self.ui.actionCbdRectTextTrimCopy)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.ui.actionCbdRectImageCopy)
        self.popMenu.addAction(self.ui.actionCbdPageImageCopy)
        self.popMenu.addSeparator()
        if self.m_tesseract_cmd:
            self.popMenu.addAction(self.ui.actionRectRecognizeText)
            self.popMenu.addAction(self.ui.actionRectRecognizeTextTrim)
            self.popMenu.addSeparator()
        else:
            self.ui.actionRectRecognizeText.setVisible(False)
            self.ui.actionRectRecognizeTextTrim.setVisible(False)
            self.ui.menuView.setSeparatorsCollapsible(True)
        self.popMenu.addAction(self.ui.actionRectRecognizeQR)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.ui.actionCbdRectsInfoCopy)
        self.popMenu.addAction(self.ui.actionCbdRectsAllInfoCopy)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.ui.actionRectMode)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.ui.actionSelectAll)
        self.popMenu.addAction(self.ui.actionRemoveSelection)
        self.popMenu.addAction(self.ui.actionRemoveAllSelections)
        # self.popMenu.addSeparator().setText("Alternate Shaders")
        # self.popMenu.addAction(QAction('Blinn', self))
        # self.popMenu.addAction(QAction('Phong', self))

        # self.ui.actionCbdPageImageCopy.connect(self.pdfView.copyPageImageToClipboard)
        # self.ui.actionCbdRectImageCopy.connect(self.pdfView.copyRectImageToClipboard)
        # self.ui.actionCbdRectImageCopy.connect(self.pdfView.copyRectTextToClipboard)

        self.setAcceptDrops(True)
        self.showMaximized()
        self.pdfView.setFocus()
        # Для наилучшего распознания текстового слоя...
        fitz.Tools().set_small_glyph_heights(True)

    @Slot(bool)
    def rect_selected(self, selected):
        self.ui.actionCbdRectTextCopy.setEnabled(selected)
        self.ui.actionCbdRectTextTrimCopy.setEnabled(selected)
        self.ui.actionCbdRectImageCopy.setEnabled(selected)
        self.ui.actionRemoveSelection.setEnabled(selected)
        self.ui.actionRectMode.setEnabled(selected)
        if self.ui.actionRectRecognizeText.isVisible():
            self.ui.actionRectRecognizeText.setEnabled(selected)
            self.ui.actionRectRecognizeTextTrim.setEnabled(selected)
        self.ui.actionRectRecognizeQR.setEnabled(selected)
        self.ui.actionCbdRectsInfoCopy.setEnabled(self.pdfView.selectionsCount() > 0)
        fl = self.pdfView.selectionsAllCount() > 0
        self.ui.actionCbdRectsAllInfoCopy.setEnabled(fl)
        self.ui.actionRemoveAllSelections.setEnabled(fl)

    def show_context_menu(self, position):
        if self.pdfView.currentPage() > -1:
            self.popMenu.exec_(self.pdfView.mapToGlobal(position))

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        # print(event.mimeData().text())
        url_list = event.mimeData().urls()
        # text = ""
        # for i in range(0, min(len(url_list), 32)):
        #     text += url_list[i].toString() + " "
        if len(url_list) > 1:
            filelist = [
                url.toLocalFile()
                for url in url_list
                if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in self.m_validExtensions
            ]
            if filelist:
                self.combineFiles(filelist)
                # self.open('', filelist)
        else:
            to_open = url_list[0]
            if to_open.isValid():
                self.open(to_open)
        event.acceptProposedAction()

    @Slot(QUrl)
    def open(self, doc_location, files_list=None):
        if files_list is None:
            files_list = []
        if doc_location == '' or doc_location.isLocalFile():
            if doc_location:
                self.m_realFile = True
                self.m_currentFileName = doc_location.toLocalFile()
                self.pdfView.open(self.m_currentFileName)
                ok_fl = self.pdfView.pageCount() > 0
            elif files_list:
                self.m_realFile = False
                self.m_currentFileName = '*** Результат объединения файлов ***'
                self.pdfView.combine(files_list)
                ok_fl = self.pdfView.pageCount() > 0
            else:
                ok_fl = False
            document_title = "Mini PDF Tools"
            # self.setWindowFilePath(self.m_currentFileName)
            if ok_fl:
                self.setWindowTitle(document_title + ' - ' + self.m_currentFileName)
                self.m_pageSelector.setRange(1, self.pdfView.pageCount())
                self.m_pageSelector.setSuffix(f' из {self.pdfView.pageCount()}')
                self.page_selected(1)
                if self.m_realFile:
                    settings = QSettings('Steigan', 'Mini PDF Tools')
                    settings.setValue('lastfilename', self.m_currentFileName)
            else:
                self.setWindowTitle(document_title)
                self.m_pageSelector.setRange(0, 1)
                self.m_pageSelector.setSuffix(' из 0')
                self.m_pageSelector.setValue(0)

            self.m_pageSelector.setEnabled(ok_fl)
            self.m_zoomSelector.setEnabled(ok_fl)
            self.ui.actionZoom_In.setEnabled(ok_fl)
            self.ui.actionZoom_Out.setEnabled(ok_fl)
            self.ui.actionZoom_Normal.setEnabled(ok_fl)
            self.ui.actionSaveAs.setEnabled(ok_fl)
            self.ui.actionClose.setEnabled(ok_fl)
            self.ui.actionTablesAnalizeStrong.setEnabled(ok_fl)
            self.ui.actionTablesAnalizeSimple.setEnabled(ok_fl)
            self.ui.actionPDexport.setEnabled(ok_fl)
            self.ui.actionPDexportQR.setEnabled(ok_fl)
            self.ui.actionCensore.setEnabled(ok_fl)
            self.ui.actionCbdPageImageCopy.setEnabled(ok_fl)
            self.ui.actionSelectAll.setEnabled(ok_fl)
            self.ui.actionRemoveAllSelections.setEnabled(False)

            self.ui.actionPageRotateLeft.setEnabled(ok_fl)
            self.ui.actionPageRotateRight.setEnabled(ok_fl)
            self.ui.actionPageRotate180.setEnabled(ok_fl)
            self.ui.actionPagesRotateLeft.setEnabled(ok_fl)
            self.ui.actionPagesRotateRight.setEnabled(ok_fl)
            self.ui.actionPagesRotate180.setEnabled(ok_fl)
        else:
            message = f"{doc_location} не является локальным файлом"
            print(message, file=sys.stderr)
            QMessageBox.critical(self, "Открыть не удалось", message)

    @Slot(int)
    def page_selected(self, page):
        # print(page)
        self.ui.actionPrevious_Page.setEnabled(page > 1)
        self.ui.actionHome.setEnabled(page > 1)
        self.ui.actionNext_Page.setEnabled(page < self.pdfView.pageCount())
        self.ui.actionEnd.setEnabled(page < self.pdfView.pageCount())
        if 0 < page <= self.pdfView.pageCount():
            self.pdfView.goToPage(page - 1)

    @Slot(int)
    def page_select(self, val):
        self.m_pageSelector.setValue(val + 1)

    def combineFiles(self, filelist: list):
        dlg = CombineDialog(self, filelist, self.m_validExtensions)
        if dlg.exec_():
            # noinspection PyTypeChecker
            self.open('', dlg.getFilelist())

    @Slot()
    def on_actionNew_triggered(self):
        self.combineFiles([])
        # settings = QSettings('Steigan', 'Mini PDF Tools')
        # lastfn = settings.value('lastfilename', '')

        # directory = os.path.dirname(lastfn)
        # to_open, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы PDF",
        #                                         directory, "Поддерживаемые файлы (*.pdf *.png *.jpg *.jpeg)")
        # filelist = [fl for fl in to_open if os.path.splitext(fl)[1].lower() in ['.pdf', '.png', '.jpg', '.jpeg']]
        # if filelist:
        #     self.open('', filelist)

    @Slot()
    def on_actionOpen_triggered(self):
        settings = QSettings('Steigan', 'Mini PDF Tools')
        lastfn = settings.value('lastfilename', '')

        # QMessageBox.information(self, 'Info', lastfn)

        directory = os.path.dirname(lastfn)
        to_open, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл PDF",
            directory,
            f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in self.m_validExtensions).strip()})",
        )
        # if to_open.isValid():
        if to_open:
            self.open(QUrl.fromLocalFile(to_open))

    @Slot()
    def on_actionClose_triggered(self):
        self.pdfView.close()
        # noinspection PyTypeChecker
        self.open('')

    def CheckNewFile(self, outfile, ext, ind, overwrite_all):
        if ind < 10000:
            fn = f'{outfile}-%04i{ext}' % ind
        else:
            fn = f'{outfile}-{ind}{ext}'
        if not overwrite_all and os.path.exists(fn):
            self.m_MsgBox.setText(f'Файл \'{fn}\' уже существует. Перезаписать поверх?')
            res = self.m_MsgBox.exec()
            if (res == QMessageBox.StandardButton.No) or (res == QMessageBox.StandardButton.Cancel):
                fn = ''
            return fn, (res == QMessageBox.StandardButton.YesToAll), (res == QMessageBox.StandardButton.Cancel)
        else:
            return fn, overwrite_all, False

    def SaveErrorMsg(self, e):
        m_MsgBox = QMessageBox(self)
        m_MsgBox.setIcon(QMessageBox.Icon.Warning)
        m_MsgBox.setWindowTitle(self.m_title)
        m_MsgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        m_MsgBox.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
        m_MsgBox.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
        m_MsgBox.setDefaultButton(QMessageBox.StandardButton.Ok)
        m_MsgBox.setText(f'Ошибка: {e}\n\nПродолжить процесс сохранения остальных файлов?')
        res = m_MsgBox.exec()
        return res

    def censore_page(self, doc, pno: int, p: SaveParams):  # noqa: ignore=C901
        """Деперсонификация одной страницы файла PDF

        Args:
            doc (fitz doc): документ PDF
            pno (int): индекс обрабатываемой страницы
            p (SaveParams): параметры сохранения файла

        Returns:
            (Pixmap): результат рендеринга и деперсонификации
        """

        zoom = p.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pixelator = p.dpi // 20
        page = doc[pno]
        anon_rects = []
        fio = []
        addr = []

        for docimg in doc.get_page_images(pno, full=True):
            # docimg[2] и docimg[3] - это ширина и высота изображения в исходных пикселях
            # shrink - матрица сжатия исходного изображения
            shrink = fitz.Matrix(1 / docimg[2], 0, 0, 1 / docimg[3], 0, 0)
            # imgrect = fitz.Rect(0, 0, docimg[2], docimg[3])

            # bbox - положение изображения в координатах PDF
            # transform - матрица для перевода координат внутри исходного изображения во
            #             "внешние" координаты страницы PDF
            bbox, transform = page.get_image_bbox(docimg, transform=True)

            # Выделяем изображение и запихиваем его в PIL

            # Перестало работать в версии PyMuPDF-1.22.0...
            # image = doc.extract_image(docimg[0])

            # Вариант для версии PyMuPDF-1.22.0...
            pix = fitz.Pixmap(doc, docimg[0])
            temp = io.BytesIO(pix.tobytes())

            img = PILImage.open(temp)

            # Левый верхний пиксель изображения черный??? Тогда инвертируем цвета
            if img.getpixel(xy=(0, 0)) == 0:
                img = ImageOps.invert(img)
            # Распознаем QR коды
            decocdeQR = decode(img, [ZBarSymbol.QRCODE])
            qr_txt = ''
            fio = []
            addr = []
            # Обходим все распознанные QR коды
            for QRobj in decocdeQR:
                txt = QRobj.data.decode('utf-8')
                # Это банковский QR код?
                if txt.startswith('ST00012|'):
                    if not qr_txt:
                        qr_txt = txt

                    # Расширяем границы QR (в исходных координатах изображения)
                    r = fitz.Rect(
                        QRobj.rect.left,
                        QRobj.rect.top,
                        QRobj.rect.left + QRobj.rect.width,
                        QRobj.rect.top + QRobj.rect.height,
                    ) + fitz.Rect(-3, -3, 4, 4)

                    # Переводим в координаты PDF
                    r = r * shrink * transform
                    # print(imgrect, QRobj.rect)

                    # Добавляем QR КОД в список скрываемых полей
                    anon_rects.append([r, 'QR'])

            # Хоть один банковский QR код найден?
            if qr_txt:
                # print(qr_txt)
                # Выделяем ключевые слова из ФИО
                try:
                    fio = [w for w in re.search(r'\|lastName=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
                except Exception:
                    fio = []
                # Выделяем ключевые слова из адреса
                try:
                    addr = [w for w in re.search(r'\|payerAddress=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
                except Exception:
                    addr = []
                # print(fio, addr)

        # !!! page.rect.width - это ширина с учетом поворота страницы !!!
        hcenter = page.rect.width // 2
        vcenter = page.rect.height // 2
        # print(hcenter, vcenter)

        # Получаем список слов на странице с их координатами
        words = page.get_text("words")

        rLS = rPeriod = rKuda = rKogo = None
        rFIOAddr = []
        # rFIO = []
        rFIO_grpd = []
        # rAddr = []
        rAddr_grpd = []

        # Обходим список слов на странице
        for w in words:
            # if w[4] in fio:
            #     r = fitz.Rect(w[:4])
            #     rFIO.append(r)
            # if w[4] in addr:
            #     r = fitz.Rect(w[:4])
            #     rAddr.append(r)
            if w[4] in fio or w[4] in addr:
                r = fitz.Rect(w[:4])
                rFIOAddr.append(r)
            if w[4] == 'КУДА:':
                rKuda = fitz.Rect(w[:4])
            if w[4] == 'КОГО:':
                rKogo = fitz.Rect(w[:4])
            if w[4] == 'л.с':
                rLS = fitz.Rect(w[:4])
            if w[4] == 'период:':
                rPeriod = fitz.Rect(w[:4])

        if rKuda and rKogo:
            hght = rKuda.y1 - rKogo.y1 - 0
            lft = 100

            rKuda.y0 = rKuda.y1 - hght
            rKuda.x1 = rKuda.x0 - 1
            rKuda.x0 = lft
            anon_rects.append([rKuda, 'POST'])

            # rKogo.y0 = rKogo.y1 - hght
            # rKogo.x1 = rKogo.x0 - 1
            # rKogo.x1 = lft
            # anon_rects.append([rKogo, 'ОТПРАВИТЕЛЬ', True])

        if rLS and rPeriod:
            rLS.y0 = rPeriod.y1 + 1
            rLS.x1 += 1
            rLS.y1 += 1
            anon_rects.append([rLS, 'IPU'])

        # rectsort_x0_key = lambda r: r.x0
        def rectsort_x0_key(x):
            return x.x0

        # rFIO.sort(key = rectsort_x0_key)
        # for grp, items in groupby(rFIO , key=rectsort_x0_key):
        #     r = fitz.Rect(grp,1000,0,0)
        #     for item in items:
        #         r.y0 = min(r.y0, item.y0, item.y1)
        #         r.y1 = max(r.y1, item.y0, item.y1)
        #         r.x1 = item.x1
        #     # print(r)
        #     rFIO_grpd.append(r)

        # rAddr.sort(key = rectsort_x0_key)
        # for grp, items in groupby(rAddr , key=rectsort_x0_key):
        #     r = fitz.Rect(grp,1000,0,0)
        #     for item in items:
        #         r.y0 = min(r.y0, item.y0, item.y1)
        #         r.y1 = max(r.y1, item.y0, item.y1)
        #         r.x1 = item.x1
        #     # print(r)
        #     rAddr_grpd.append(r)

        leftFioInd = 1
        rightFioInd = 1
        max_y = 1000
        if rKogo:
            max_y = min(rKogo.y0, rKogo.y1)
        # print(max_y)
        rFIOAddr.sort(key=rectsort_x0_key)
        for grp, items in groupby(rFIOAddr, key=rectsort_x0_key):
            r = fitz.Rect(grp, 1000, 0, 0)
            for item in items:
                r.y0 = min(r.y0, item.y0, item.y1)
                r.y1 = max(r.y1, item.y0, item.y1)
                r.x1 = item.x1
            if r.x0 < vcenter:
                # print(r)
                if (r.y1 > hcenter) and (r.y0 < max_y):
                    if leftFioInd == 1:
                        rFIO_grpd.append(r)
                        leftFioInd = 2
                    elif leftFioInd == 2:
                        rAddr_grpd.append(r)
                        leftFioInd = 0
                else:
                    if rightFioInd == 1:
                        rFIO_grpd.append(r)
                        rightFioInd = 2
                    elif rightFioInd == 2:
                        rAddr_grpd.append(r)
                        rightFioInd = 0

        flDoAddr = False
        if len(rFIO_grpd) > 0:
            r = fitz.Rect(rFIO_grpd[0])
            if len(rAddr_grpd) > 0:
                r.y0 = min(r.y0, rAddr_grpd[0].y0)
                r.y1 = max(r.y1, rAddr_grpd[0].y1)
                flDoAddr = True
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'FIO'])

        if flDoAddr:
            # noinspection PyUnboundLocalVariable
            r.x0 = rAddr_grpd[0].x0
            r.x1 = rAddr_grpd[0].x1 + 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])
        elif len(rAddr_grpd) > 0:
            r = fitz.Rect(rAddr_grpd[0])
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])

        flDoAddr = False
        if len(rFIO_grpd) > 1:
            r = rFIO_grpd[1]
            if len(rAddr_grpd) > 1:
                r.y0 = min(r.y0, rAddr_grpd[1].y0)
                r.y1 = max(r.y1, rAddr_grpd[1].y1)
                flDoAddr = True
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'FIO', False])

        if flDoAddr:
            r.x0 = rAddr_grpd[1].x0
            r.x1 = rAddr_grpd[1].x1 + 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])
        elif len(rAddr_grpd) > 1:
            r = fitz.Rect(rAddr_grpd[1])
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])

        md_list = ['FIO', 'ADDR', 'POST', 'IPU', 'QR']
        chks_list = [p.censoreFIO, p.censoreAddr, p.censorePost, p.censoreIPU, p.censoreQR]

        if not p.setselectionsonly:
            # Растеризуем страницу и запихиваем изображение в PIL
            pix = page.get_pixmap(matrix=mat)
            pix.set_dpi(p.dpi, p.dpi)
            img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)

        for anon_rect in anon_rects:
            if chks_list[md_list.index(anon_rect[1])]:
                if p.setselectionsonly:
                    self.pdfView.addSelection(pno, anon_rect[0])
                else:
                    # noinspection PyTypeChecker
                    r = anon_rect[0] * page.rotation_matrix * mat
                    try:
                        r.x0 = int(r.x0)
                        r.x1 = int(r.x1)
                        r.y0 = int(r.y0)
                        r.y1 = int(r.y1)
                        # noinspection PyUnboundLocalVariable
                        crop_img = img.crop(r)
                        # # Use GaussianBlur directly to blur the image 10 times.
                        # blur_image = crop_img.filter(ImageFilter.GaussianBlur(radius=10))
                        # blur_image = crop_img.filter(ImageFilter.BoxBlur(radius=10))
                        imgSmall = crop_img.resize((crop_img.size[0] // pixelator, crop_img.size[1] // pixelator))
                        blur_image = imgSmall.resize(crop_img.size, PILImage.NEAREST)
                        img.paste(blur_image, r)
                    except Exception:
                        pass

        if not p.setselectionsonly:
            samples = img.tobytes()
            pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)
            return pix

    def saveas_process(self, p: SaveParams, censore: bool):  # noqa: ignore=C901
        if censore:
            self.m_title = 'Деперсонификация данных'
        else:
            self.m_title = 'Сохранить как'

        if p.pgmode == PageMode.pgAll:
            pageranges = [range(0, self.pdfView.pageCount())]
            approx_pgcount = self.pdfView.pageCount()
        elif p.pgmode == PageMode.pgCurrent:
            pageranges = [range(self.pdfView.currentPage(), self.pdfView.currentPage() + 1)]
            approx_pgcount = 1
        else:
            approx_pgcount = 0
            pageranges = []
            for grp in re.findall('([0-9-]+),', p.pgrange + ','):
                subgrp = re.findall(r'(\d*)-*', grp)
                r_start = 0
                if not grp.startswith('-'):
                    r_start = max(r_start, int(subgrp[0]))
                r_end = self.pdfView.pageCount() + 1
                if not grp.endswith('-'):
                    r_end = min(r_end, int(subgrp[-2]))
                if r_start > r_end:
                    # r_start, r_end = r_end, r_start
                    if r_end <= self.pdfView.pageCount() and r_start > 0:
                        pageranges.append(range(r_start - 1, r_end - 2, -1))
                        approx_pgcount += r_start - r_end + 1  # Примерное количество из-за границ
                else:
                    if r_start <= self.pdfView.pageCount() and r_end > 0:
                        pageranges.append(range(r_start - 1, r_end))
                        approx_pgcount += r_end - r_start + 1  # Примерное количество из-за границ
                # print(r_start, r_end)
            # print(pageranges)
            if not len(pageranges):
                QMessageBox.critical(self, self.m_title, "Не задан список страниц!")
                return

        if p.setselectionsonly:
            if self.pdfView.selectionsAllCount() > 0:
                self.m_MsgBox.setIcon(QMessageBox.Icon.Question)
                self.m_MsgBox.setWindowTitle(self.m_title)
                self.m_MsgBox.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                self.m_MsgBox.setDefaultButton(QMessageBox.StandardButton.Yes)
                self.m_MsgBox.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
                self.m_MsgBox.button(QMessageBox.StandardButton.No).setText('  Нет  ')
                self.m_MsgBox.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
                self.m_MsgBox.setText('Документ уже содержит выделенные области. Очистить их?')
                res = self.m_MsgBox.exec()
                if res == QMessageBox.StandardButton.Cancel:
                    return
                elif res == QMessageBox.StandardButton.Yes:
                    self.pdfView.removeSelection(True)

            self.statusBar().showMessage('Поиск и выделение персональных данных...')
            self.progressBar.setValue(0)
            self.progressBar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()
            ind = 0
            doc = self.pdfView._doc
            for pages in pageranges:
                for pno in pages:
                    if 0 <= pno < doc.page_count:
                        self.censore_page(doc=doc, pno=pno, p=p)
                        ind += 1
                        self.progressBar.setValue(ind * 100 // approx_pgcount)
                        QApplication.processEvents()

            self.rect_selected(self.pdfView.selectedRect > -1)
            return

        # outfile, _ = os.path.splitext(self.m_currentFileName)

        if p.format in [FileFormat.fmtJPEG, FileFormat.fmtPNG]:
            m_singles = True
        else:
            m_singles = p.singles

        if m_singles:
            ext_tp = [".pdf", ".jpg", ".png"][max(p.format.value - 1, 0)]
            outfile, _ = QFileDialog.getSaveFileName(
                self,
                self.m_title,
                os.path.dirname(self.m_currentFileName),
                r'Серия файлов {имя}' + f'-XXXX{ext_tp} (*{ext_tp})',
                options=QFileDialog.Option.DontConfirmOverwrite,
            )

            outfile, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != ext_tp:
                ext = ext_tp
        else:
            outfile, _ = QFileDialog.getSaveFileName(
                self, self.m_title, os.path.dirname(self.m_currentFileName), r'Файл PDF (*.pdf)'
            )
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != ".pdf":
                ext = ".pdf"
                outfile += ext

        if not outfile:
            return

        if outfile == self.m_currentFileName:
            QMessageBox.critical(self, self.m_title, "Нельзя сохранять файл в самого себя!")
            return

        self.statusBar().showMessage('Сохранение файла/файлов...')
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.setDisabled(True)
        QApplication.processEvents()

        # doc = fitz.open(self.m_currentFileName)
        doc = self.pdfView._doc

        zoom = p.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        if p.format in [FileFormat.fmtPDF, FileFormat.fmtPDFjpeg] and not m_singles:
            # noinspection PyUnresolvedReferences
            pdfout = fitz.open()
        ind = 0

        self.m_MsgBox.setIcon(QMessageBox.Icon.Question)
        self.m_MsgBox.setWindowTitle(self.m_title)
        self.m_MsgBox.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.YesToAll
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        self.m_MsgBox.setDefaultButton(QMessageBox.StandardButton.Yes)
        self.m_MsgBox.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
        self.m_MsgBox.button(QMessageBox.StandardButton.YesToAll).setText('  Да для всех  ')
        self.m_MsgBox.button(QMessageBox.StandardButton.No).setText('  Нет  ')
        self.m_MsgBox.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

        # Эксклюзивный режим ...
        if (
            self.m_realFile
            and p.format == FileFormat.fmtPDF
            and p.pgmode == PageMode.pgAll
            and (not m_singles)
            and doc.can_save_incrementally()
        ):
            # noinspection PyUnboundLocalVariable
            pdfout.close()
            # doc.close()
            # doc = None
            try:
                shutil.copyfile(self.m_currentFileName, outfile)
            except Exception as e:
                QMessageBox.critical(
                    self, self.m_title, f"Ошибка: {e}\n\nПопробуйте сохранить файл как диапазон из всех страниц [1-]."
                )
                return

            # print('Эксклюзивный режим ...')
            # noinspection PyUnresolvedReferences
            doc = fitz.open(outfile)
            if doc.needs_pass:
                doc.authenticate(self.pdfView._psw)
            for pno in range(approx_pgcount):
                # if p.rotation != PageRotation.rtNone:
                # Пытаемся повернуть страницу в соответствии с отображаемым на экране объектом
                doc[pno].set_rotation((self.pdfView._doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)
                self.progressBar.setValue(pno * 95 // approx_pgcount)
                QApplication.processEvents()
            try:
                doc.save(
                    outfile, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
                )  # , garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
            except Exception as e:
                QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                doc.close()
                # shutil. copyfile(self.m_currentFileName, outfile)
                return
            doc.close()
        else:
            pixelator = p.dpi // 20
            overwrite_all = False
            for pages in pageranges:
                for pno in pages:
                    if 0 <= pno < doc.page_count:
                        ind += 1

                        self.progressBar.setValue(ind * 100 // approx_pgcount)
                        QApplication.processEvents()

                        old_rot = doc[pno].rotation
                        if p.rotation != PageRotation.rtNone:
                            doc[pno].set_rotation((doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)

                        try:
                            if p.format == FileFormat.fmtPDF:
                                if m_singles:
                                    # noinspection PyUnresolvedReferences
                                    newdoc = fitz.open()
                                    newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

                                    fn, overwrite_all, abort = self.CheckNewFile(outfile, ext, ind, overwrite_all)
                                    if abort:
                                        raise
                                    if fn:
                                        try:
                                            newdoc.save(
                                                fn,
                                                garbage=4,
                                                clean=True,
                                                deflate=True,
                                                deflate_images=True,
                                                deflate_fonts=True,
                                            )
                                        except Exception as e:
                                            if self.SaveErrorMsg(e) == QMessageBox.StandardButton.Cancel:
                                                newdoc.close()
                                                raise
                                    newdoc.close()
                                else:
                                    # noinspection PyUnboundLocalVariable
                                    pdfout.insert_pdf(doc, from_page=pno, to_page=pno)
                                    # pg = pdfout[pdfout.page_count - 1]
                                    # print(pg.rotation)
                                    # new_rotation = (0, 270, 90, 180)[p.rotation.value]
                                    # pg.set_rotation(new_rotation)

                            else:
                                page = doc[pno]
                                if censore:
                                    pix = self.censore_page(doc=doc, pno=pno, p=p)
                                else:
                                    # Растеризуем страницу и запихиваем изображение в PIL
                                    pix = page.get_pixmap(matrix=mat)
                                    pix.set_dpi(p.dpi, p.dpi)

                                    if p.censore:
                                        sels = [
                                            sel
                                            for sel in self.pdfView.selections_all
                                            if (sel.pno == -1 or sel.pno == pno)
                                        ]
                                        if len(sels) > 0:
                                            img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)
                                            page_r = fitz.Rect(0, 0, pix.width, pix.height)
                                            for sel in sels:
                                                r = (
                                                    self.pdfView.getSelectionFitzRect(pno, old_rot, sel)
                                                    * page.rotation_matrix
                                                    * mat
                                                )
                                                if page_r.contains(r):
                                                    # print(r)
                                                    try:
                                                        r.x0 = int(r.x0)
                                                        r.x1 = int(r.x1)
                                                        r.y0 = int(r.y0)
                                                        r.y1 = int(r.y1)
                                                        if p.censore == 1:
                                                            crop_img = img.crop(r)
                                                            imgSmall = crop_img.resize(
                                                                (
                                                                    crop_img.size[0] // pixelator,
                                                                    crop_img.size[1] // pixelator,
                                                                )
                                                            )
                                                            blur_image = imgSmall.resize(
                                                                crop_img.size, PILImage.NEAREST
                                                            )
                                                            img.paste(blur_image, r)
                                                        else:
                                                            draw = ImageDraw.Draw(img)
                                                            draw.rectangle(r, fill=(255, 255, 255, 0))
                                                    except Exception:
                                                        pass
                                            samples = img.tobytes()
                                            pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)

                                if p.format == FileFormat.fmtPDFjpeg:
                                    temp = io.BytesIO()
                                    pix.pil_save(temp, format="jpeg", quality=p.quality)
                                    if m_singles:
                                        # noinspection PyUnresolvedReferences
                                        newdoc = fitz.open()
                                        opage = newdoc.new_page(width=page.rect.width, height=page.rect.height)
                                        opage.insert_image(opage.rect, stream=temp)

                                        fn, overwrite_all, abort = self.CheckNewFile(outfile, ext, ind, overwrite_all)
                                        if abort:
                                            raise
                                        if fn:
                                            try:
                                                newdoc.save(
                                                    fn,
                                                    garbage=4,
                                                    clean=True,
                                                    deflate=True,
                                                    deflate_images=True,
                                                    deflate_fonts=True,
                                                    encryption=fitz.PDF_ENCRYPT_KEEP,
                                                )
                                            except Exception as e:
                                                if self.SaveErrorMsg(e) == QMessageBox.StandardButton.Cancel:
                                                    newdoc.close()
                                                    raise

                                        newdoc.close()
                                    else:
                                        opage = pdfout.new_page(width=page.rect.width, height=page.rect.height)
                                        opage.insert_image(opage.rect, stream=temp)
                                else:
                                    fn, overwrite_all, abort = self.CheckNewFile(outfile, ext, ind, overwrite_all)
                                    if abort:
                                        raise
                                    if fn:
                                        try:
                                            if p.format == FileFormat.fmtJPEG:
                                                pix.pil_save(fn, format="jpeg", quality=p.quality)
                                            else:
                                                pix.pil_save(fn, format="png")
                                        except Exception as e:
                                            if self.SaveErrorMsg(e) == QMessageBox.StandardButton.Cancel:
                                                raise
                        except Exception:
                            # Вертаем поворот страницы взад
                            if p.rotation != PageRotation.rtNone:
                                doc[pno].set_rotation(old_rot)
                            return

                        if p.rotation != PageRotation.rtNone:
                            doc[pno].set_rotation(old_rot)

            if p.format in [FileFormat.fmtPDF, FileFormat.fmtPDFjpeg] and not m_singles:
                try:
                    pdfout.save(
                        outfile,
                        garbage=4,
                        clean=True,
                        deflate=True,
                        deflate_images=True,
                        deflate_fonts=True,
                        encryption=fitz.PDF_ENCRYPT_KEEP,
                    )
                except Exception as e:
                    QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                    pdfout.close()
                    return
                pdfout.close()

        self.progressBar.setValue(100)
        QApplication.processEvents()

        self.statusBar().showMessage('Готово!')
        if p.format in [FileFormat.fmtPDF, FileFormat.fmtPDFjpeg] and not m_singles:
            # if platform.system() == 'Windows':
            #     subprocess.Popen(('start', outfile), shell = True)
            if self.m_pdfviewer_cmd:
                subprocess.Popen((self.m_pdfviewer_cmd, outfile))
        QMessageBox.information(self, "Сохранение файла/файлов", "Готово!")

    def tableanalize_process(self, strong):
        self.m_title = "Экспорт табличных данных в XLSX"
        outfile, _ = QFileDialog.getSaveFileName(
            self, self.m_title, os.path.dirname(self.m_currentFileName), r'Книга Excel "(*.xlsx)"'
        )
        if outfile:
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != '.xlsx':
                outfile += '.xlsx'

            self.statusBar().showMessage('Экспорт табличных данных в XLSX...')
            self.progressBar.setValue(0)
            self.progressBar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()

            try:
                if os.path.isfile(outfile):
                    os.remove(outfile)
                # doc = fitz.open(self.m_currentFileName)
                doc = self.pdfView._doc
            except Exception as e:
                QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                return

            workbook = xlsxwriter.Workbook(outfile)
            worksheet = workbook.add_worksheet()

            cell_format = workbook.add_format()
            cell_format.set_align('center')
            cell_format.set_align('vcenter')
            cell_format.set_text_wrap()
            cell_format.set_border(1)

            pgcount = len(doc)
            start_row = 0
            for pno in range(len(doc)):
                start_row += parse_page_tables(doc[pno], worksheet, start_row, cell_format, strong)
                self.progressBar.setValue(pno * 99 // pgcount)
                QApplication.processEvents()

            try:
                workbook.close()
            except Exception as e:
                QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                return

            self.progressBar.setValue(100)
            QApplication.processEvents()
            if start_row > 0:
                if self.m_xlseditor_cmd:
                    subprocess.Popen((self.m_xlseditor_cmd, outfile))
                self.statusBar().showMessage('Готово!')
            else:
                QMessageBox.warning(self, self.m_title, "Табличные данные найти не удалось...")

    def exportpd_process(self, recognizeQR):
        self.m_title = "Экспорт данных в XLSX"
        outfile, _ = QFileDialog.getSaveFileName(
            self, self.m_title, os.path.dirname(self.m_currentFileName), r'Книга Excel "(*.xlsx)"'
        )
        if outfile:
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != '.xlsx':
                outfile += '.xlsx'

            self.statusBar().showMessage('Экспорт данных в XLSX...')
            self.progressBar.setValue(0)
            self.progressBar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()

            try:
                if os.path.isfile(outfile):
                    os.remove(outfile)
                # doc = fitz.open(self.m_currentFileName)
                doc = self.pdfView._doc
            except Exception as e:
                QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                return

            workbook = xlsxwriter.Workbook(outfile)
            cell_format = workbook.add_format()
            cell_format.set_align('center')
            cell_format.set_align('vcenter')
            cell_format.set_text_wrap()
            cell_format.set_border(1)

            worksheet = workbook.add_worksheet('Свод')
            worksheet_det = workbook.add_worksheet('Детально')
            worksheet_det.set_column(0, 0, 10)
            worksheet_det.set_column(1, 1, 60)
            worksheet_det.write_row(0, 0, ("Страница файла PDF", "Адрес доставки"), cell_format)
            if recognizeQR:
                worksheet_det.set_column(2, 2, 110)
                worksheet_det.write_string(0, 2, "Информация из QR кода", cell_format)

            # Тест переноса дат в Эксель
            # worksheet_det.write_datetime(0, 3, datetime.date(2023, 6, 30), cell_format)
            # worksheet_det.write_datetime(0, 4, datetime.date(1900, 1, 1), cell_format)
            # worksheet_det.write_datetime(0, 4, datetime.date(1900, 2, 29), cell_format) - такая дата
            # есть только в Экселе и т.п. программах (наследство от Лотуса)

            pgcount = len(doc)

            np_list = []
            old_np = ""
            np_start_pg = 0
            ii = 0

            for current_page in range(pgcount):
                page = doc.load_page(current_page)
                page_text = page.get_text("text")

                ii += 1
                worksheet_det.write(ii, 0, ii, cell_format)

                # if ii == 1:
                #     print(page_text)

                res = re.compile(r'^КУДА: (.*)').search(page_text)
                if res is not None:
                    dest = res.group(1)
                else:
                    page_lines = page_text.splitlines()
                    if page_lines[-1] == 'Куда:':
                        dest = page_lines[-4]
                    else:
                        dest = '----'

                if dest == '----':
                    np = "ПД не распознан или в нем ошибка"
                    worksheet_det.write_string(ii, 1, np, cell_format)
                else:
                    worksheet_det.write_string(ii, 1, dest, cell_format)
                    np = re.compile(r'[^,]*').search(dest + ",").group(0)
                    np = np.replace('ё', 'е').replace('Ё', 'Е')

                if recognizeQR:
                    txt = ''
                    for docimg in doc.get_page_images(current_page):
                        # xref = docimg[0]
                        # width = docimg[2]
                        # height = docimg[3]
                        # if min(width, height) <= dimlimit:
                        #     continue

                        # Перестало работать в версии PyMuPDF-1.22.0...
                        # image = doc.extract_image(docimg[0])

                        # Вариант для версии PyMuPDF-1.22.0...
                        pix = fitz.Pixmap(doc, docimg[0])
                        temp = io.BytesIO(pix.tobytes())

                        img = PILImage.open(temp)

                        if img.getpixel(xy=(0, 0)) == 0:
                            img = ImageOps.invert(img)
                        decocdeQR = decode(img, [ZBarSymbol.QRCODE])
                        for QRobj in decocdeQR:
                            txt += ('\n-------------------\n' if txt else '') + QRobj.data.decode('utf-8')
                    worksheet_det.write_string(ii, 2, txt, cell_format)

                if np != old_np:
                    if old_np:
                        np_list.append((old_np, np_start_pg, current_page))

                    old_np = np
                    np_start_pg = current_page + 1

                self.progressBar.setValue(current_page * 95 // pgcount)
                QApplication.processEvents()
                # self.progressBar.setValue(current_page * 95 / pgcount)

            if old_np:
                # noinspection PyUnboundLocalVariable
                np_list.append((old_np, np_start_pg, current_page + 1))

            # print(np_list)
            worksheet_det.freeze_panes(1, 0)
            if recognizeQR:
                worksheet_det.autofilter(0, 0, pgcount, 2)
            else:
                worksheet_det.autofilter(0, 0, pgcount, 1)

            worksheet.set_column(0, 0, 7)
            worksheet.set_column(1, 1, 45)
            worksheet.set_column(2, 2, 20)
            worksheet.set_column(3, 3, 20)
            worksheet.set_column(4, 4, 45)

            worksheet.write_row(
                0, 0, ("№ п/п", "Населенный пункт", "Страницы файла PDF", "Кол-во страниц", "Файл PDF"), cell_format
            )

            fnm = os.path.basename(self.m_currentFileName)
            ii = 0
            for data in np_list:
                ii += 1
                worksheet.write(ii, 0, ii, cell_format)
                worksheet.write_string(ii, 1, data[0], cell_format)
                worksheet.write_string(ii, 2, f'{data[1]} - {data[2]}', cell_format)
                worksheet.write(ii, 3, data[2] - data[1] + 1, cell_format)
                worksheet.write_string(ii, 4, fnm, cell_format)

            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, ii, 3)

            # doc.close()
            try:
                workbook.close()
            except Exception as e:
                QMessageBox.critical(self, self.m_title, f"Ошибка: {e}")
                return

            self.progressBar.setValue(100)
            QApplication.processEvents()
            # if platform.system() == 'Windows':
            #     subprocess.Popen(('start', outfile), shell = True)
            if self.m_xlseditor_cmd:
                subprocess.Popen((self.m_xlseditor_cmd, outfile))
            self.statusBar().showMessage('Готово!')
            # QMessageBox.information(self, "Экспорт данных в XLSX", "Готово!")

    @Slot()
    def on_actionSaveAs_triggered(self):
        dlg = SaveAsDialog(self)
        if dlg.exec_():
            self.saveas_process(dlg.params(), False)

            self.progressBar.setVisible(False)
            self.setDisabled(False)
            self.statusBar().showMessage('')
            QApplication.processEvents()

    @Slot()
    def on_actionCensore_triggered(self):
        dlg = CensoreDialog(self)
        if dlg.exec_():
            # Отключаем режим small_glyph_heights, т.к. с ним некорректно определяется положение "КУДА" и "ОТ КОГО"
            fitz.Tools().set_small_glyph_heights(False)

            dlg.params().format = dlg.params().format_censore
            self.saveas_process(dlg.params(), True)

            self.progressBar.setVisible(False)
            self.setDisabled(False)
            self.statusBar().showMessage('')
            QApplication.processEvents()

            # Для наилучшего распознания текстового слоя...
            fitz.Tools().set_small_glyph_heights(True)

    @Slot()
    def on_actionTablesAnalizeStrong_triggered(self):
        self.tableanalize_process(True)
        self.progressBar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionTablesAnalizeSimple_triggered(self):
        self.tableanalize_process(False)
        self.progressBar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionPDexport_triggered(self):
        self.exportpd_process(False)
        self.progressBar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionPDexportQR_triggered(self):
        self.exportpd_process(True)
        self.progressBar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionQuit_triggered(self):
        self.close()

    @Slot()
    def on_actionHome_triggered(self):
        if self.pdfView.pageCount() > 0:
            self.page_select(0)

    @Slot()
    def on_actionEnd_triggered(self):
        if self.pdfView.pageCount() > 0:
            self.page_select(self.pdfView.pageCount() - 1)

    @Slot()
    def on_actionAbout_triggered(self):
        QMessageBox.about(self, "О программе Mini PDF Tools", ABOUT_TEXT)

    @Slot()
    def on_actionZoom_In_triggered(self):
        self.pdfView.zoomIn()

    @Slot()
    def on_actionZoom_Out_triggered(self):
        self.pdfView.zoomOut()

    @Slot()
    def on_actionZoom_Normal_triggered(self):
        self.pdfView.setZoomFactor(1.0)

    @Slot()
    def on_actionPrevious_Page_triggered(self):
        self.pdfView.goToPrevPage()

    @Slot()
    def on_actionNext_Page_triggered(self):
        self.pdfView.goToNextPage()

    @Slot()
    def on_actionCbdPageImageCopy_triggered(self):
        self.pdfView.copyPageImageToClipboard()

    @Slot()
    def on_actionCbdRectImageCopy_triggered(self):
        self.pdfView.copyRectImageToClipboard()

    @Slot()
    def on_actionCbdRectTextCopy_triggered(self):
        self.pdfView.copyRectTextToClipboard()

    @Slot()
    def on_actionCbdRectTextTrimCopy_triggered(self):
        self.pdfView.copyRectTextToClipboard(True)

    @Slot()
    def on_actionRectRecognizeText_triggered(self):
        self.pdfView.recognizeAndCopyToClipboard(self.m_tesseract_cmd, trim=False)

    @Slot()
    def on_actionRectRecognizeTextTrim_triggered(self):
        self.pdfView.recognizeAndCopyToClipboard(self.m_tesseract_cmd, trim=True)

    @Slot()
    def on_actionRectRecognizeQR_triggered(self):
        self.pdfView.recognizeQRAndCopyToClipboard()

    @Slot()
    def on_actionCbdRectsInfoCopy_triggered(self):
        self.pdfView.copyRectsInfoToClipboard(False)

    @Slot()
    def on_actionCbdRectsAllInfoCopy_triggered(self):
        self.pdfView.copyRectsInfoToClipboard(True)

    @Slot()
    def on_actionSelectAll_triggered(self):
        self.pdfView.selectAll()

    @Slot()
    def on_actionRemoveSelection_triggered(self):
        self.pdfView.removeSelection()

    @Slot()
    def on_actionRemoveAllSelections_triggered(self):
        self.pdfView.removeSelection(True)

    @Slot()
    def on_actionRectMode_triggered(self):
        self.pdfView.switchRectMode()

    @Slot()
    def on_actionPageRotateLeft_triggered(self):
        self.pdfView.pagesRotate(1, False)

    @Slot()
    def on_actionPageRotateRight_triggered(self):
        self.pdfView.pagesRotate(2, False)

    @Slot()
    def on_actionPageRotate180_triggered(self):
        self.pdfView.pagesRotate(3, False)

    @Slot()
    def on_actionPagesRotateLeft_triggered(self):
        self.pdfView.pagesRotate(1, True)

    @Slot()
    def on_actionPagesRotateRight_triggered(self):
        self.pdfView.pagesRotate(2, True)

    @Slot()
    def on_actionPagesRotate180_triggered(self):
        self.pdfView.pagesRotate(3, True)
