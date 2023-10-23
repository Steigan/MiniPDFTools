# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import configparser
import io
import os
import re
import shutil
import subprocess
import sys
from itertools import groupby

import fitz
import xlsxwriter
from PIL import Image as PILImage
from PIL import ImageDraw
from PIL import ImageOps
from PySide2.QtCore import QSettings
from PySide2.QtCore import Qt
from PySide2.QtCore import QUrl
from PySide2.QtCore import Slot
from PySide2.QtWidgets import QAbstractSpinBox
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
from mainwindow_ui import Ui_MainWindow
from params import FileFormat
from params import PageMode
from params import PageRotation
from params import SaveParams
from saveasdlg import SaveAsDialog
from siapdfview import SiaPdfView
from siapdfview import ZoomSelector
from tableanalize import parse_page_tables


ABOUT_TEXT = """
Mini PDF Tools - мини набор инструментов для просмотра и обработки файлов PDF.
Версия от 23.10.2023 (c) 2023 Игорь Степаненков

Используемые пакеты и библиотеки:
PySide2 (c) 2022 The Qt Company Ltd.
PyMuPDF (c) 2023 Artifex Software, Inc.
Pillow - PIL fork by Alex Clark and Contributors
XlsxWriter (c) 2013-2023 John McNamara
PyZBar (c) 2022 Lawrence Hudson
PyTesseract for Google's Tesseract-OCR Engine (c) 2022 Samuel Hoffstaetter
Paomedia Small & Flat Icons
"""


class MyQSpinBox(QSpinBox):
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
        self._zoom_selector = ZoomSelector(self)
        self._page_selector = MyQSpinBox(self)
        self._msg_box = QMessageBox(self)
        self._current_filename = ''
        self._real_file = False
        self._title = ''
        self._valid_extensions = [
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
            self._tesseract_cmd = config.get("Settings", "tesseract_cmd", fallback="")
            self._pdfviewer_cmd = config.get("Settings", "pdfviewer_cmd", fallback="")
            self._xlseditor_cmd = config.get("Settings", "xlseditor_cmd", fallback="")
        except configparser.Error:
            self._tesseract_cmd = ""
            self._pdfviewer_cmd = ""
            self._xlseditor_cmd = ""

        self.ui.setupUi(self)

        self.setMinimumSize(500, 400)

        self.statusBar().showMessage('')
        self.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.setGeometry(30, 40, 200, 20)
        # self.statusBar().showMessage('Процесс')
        # self.progressBar.setValue(50)
        self.progress_bar.setVisible(False)

        self._zoom_selector.setMaximumWidth(150)
        # Вставляем zoomSelector перед actionZoom_In
        self.ui.mainToolBar.insertWidget(self.ui.actionZoom_In, self._zoom_selector)

        # Вставляем pageSelector перед actionForward
        self.ui.mainToolBar.insertWidget(self.ui.actionNext_Page, self._page_selector)
        self._page_selector.setEnabled(False)
        self._page_selector.valueChanged.connect(self.page_selected)
        self._page_selector.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._page_selector.setSuffix(' из 0')
        self._page_selector.setMinimumWidth(70)
        # noinspection PyTypeChecker
        self._page_selector.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.pdf_view = SiaPdfView(self)
        self.setCentralWidget(self.pdf_view)
        # self.centralWidget(). insertWidget(self.centralWidget(), self.pdfView)
        # self.centralWidget().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.centralWidget().setLayout(Qt.QLay)

        self.pdf_view.current_page_changed.connect(self.page_select)
        self.pdf_view.rect_selected.connect(self.rect_selected)
        self.pdf_view.zoom_factor_changed.connect(self._zoom_selector.set_zoom_factor)

        # self.m_zoomSelector.zoom_mode_changed.connect(self.pdfView.setZoomMode)
        self._zoom_selector.zoom_factor_changed.connect(self.pdf_view.set_zoom_factor)
        self._zoom_selector.reset()

        self.pdf_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pdf_view.customContextMenuRequested.connect(self.show_context_menu)
        self.pop_menu = QMenu(self)
        self.pop_menu.addAction(self.ui.actionCbdRectTextCopy)
        self.pop_menu.addAction(self.ui.actionCbdRectTextTrimCopy)
        self.pop_menu.addSeparator()
        self.pop_menu.addAction(self.ui.actionCbdRectImageCopy)
        self.pop_menu.addAction(self.ui.actionCbdPageImageCopy)
        self.pop_menu.addSeparator()
        if self._tesseract_cmd:
            self.pop_menu.addAction(self.ui.actionRectRecognizeText)
            self.pop_menu.addAction(self.ui.actionRectRecognizeTextTrim)
            self.pop_menu.addSeparator()
        else:
            self.ui.actionRectRecognizeText.setVisible(False)
            self.ui.actionRectRecognizeTextTrim.setVisible(False)
            self.ui.menuView.setSeparatorsCollapsible(True)
        self.pop_menu.addAction(self.ui.actionRectRecognizeQR)
        self.pop_menu.addSeparator()
        self.pop_menu.addAction(self.ui.actionCbdRectsInfoCopy)
        self.pop_menu.addAction(self.ui.actionCbdRectsAllInfoCopy)
        self.pop_menu.addSeparator()
        self.pop_menu.addAction(self.ui.actionRectMode)
        self.pop_menu.addSeparator()
        self.pop_menu.addAction(self.ui.actionSelectAll)
        self.pop_menu.addAction(self.ui.actionRemoveSelection)
        self.pop_menu.addAction(self.ui.actionRemoveAllSelections)
        # self.popMenu.addSeparator().setText("Alternate Shaders")
        # self.popMenu.addAction(QAction('Blinn', self))
        # self.popMenu.addAction(QAction('Phong', self))

        # self.ui.actionCbdPageImageCopy.connect(self.pdfView.copyPageImageToClipboard)
        # self.ui.actionCbdRectImageCopy.connect(self.pdfView.copyRectImageToClipboard)
        # self.ui.actionCbdRectImageCopy.connect(self.pdfView.copyRectTextToClipboard)

        self.setAcceptDrops(True)
        self.showMaximized()
        self.pdf_view.setFocus()
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
        self.ui.actionCbdRectsInfoCopy.setEnabled(self.pdf_view.selections_count > 0)
        fl = self.pdf_view.selections_all_count > 0
        self.ui.actionCbdRectsAllInfoCopy.setEnabled(fl)
        self.ui.actionRemoveAllSelections.setEnabled(fl)

    def show_context_menu(self, position):
        if self.pdf_view.current_page > -1:
            self.pop_menu.exec_(self.pdf_view.mapToGlobal(position))

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        url_list = event.mimeData().urls()
        if len(url_list) > 1:
            filelist = [
                url.toLocalFile()
                for url in url_list
                if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in self._valid_extensions
            ]
            if filelist:
                self.combine_files(filelist)
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
                self._real_file = True
                self._current_filename = doc_location.toLocalFile()
                self.pdf_view.open(self._current_filename)
                ok_fl = self.pdf_view.page_count > 0
            elif files_list:
                self._real_file = False
                self._current_filename = '*** Результат объединения файлов ***'
                self.pdf_view.combine(files_list)
                ok_fl = self.pdf_view.page_count > 0
            else:
                ok_fl = False
            document_title = "Mini PDF Tools"
            # self.setWindowFilePath(self.m_currentFileName)
            if ok_fl:
                self.setWindowTitle(document_title + ' - ' + self._current_filename)
                self._page_selector.setRange(1, self.pdf_view.page_count)
                self._page_selector.setSuffix(f' из {self.pdf_view.page_count}')
                self.page_selected(1)
                if self._real_file:
                    settings = QSettings('Steigan', 'Mini PDF Tools')
                    settings.setValue('lastfilename', self._current_filename)
            else:
                self.setWindowTitle(document_title)
                self._page_selector.setRange(0, 1)
                self._page_selector.setSuffix(' из 0')
                self._page_selector.setValue(0)

            self._page_selector.setEnabled(ok_fl)
            self._zoom_selector.setEnabled(ok_fl)
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
        self.ui.actionNext_Page.setEnabled(page < self.pdf_view.page_count)
        self.ui.actionEnd.setEnabled(page < self.pdf_view.page_count)
        if 0 < page <= self.pdf_view.page_count:
            self.pdf_view.goto_page(page - 1)

    @Slot(int)
    def page_select(self, val):
        self._page_selector.setValue(val + 1)

    def combine_files(self, filelist: list):
        dlg = CombineDialog(self, filelist, self._valid_extensions)
        if dlg.exec_():
            # noinspection PyTypeChecker
            self.open('', dlg.getFilelist())

    @Slot()
    def on_actionNew_triggered(self):  # pylint: disable=invalid-name
        self.combine_files([])
        # settings = QSettings('Steigan', 'Mini PDF Tools')
        # lastfn = settings.value('lastfilename', '')

        # directory = os.path.dirname(lastfn)
        # to_open, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы PDF",
        #                                         directory, "Поддерживаемые файлы (*.pdf *.png *.jpg *.jpeg)")
        # filelist = [fl for fl in to_open if os.path.splitext(fl)[1].lower() in ['.pdf', '.png', '.jpg', '.jpeg']]
        # if filelist:
        #     self.open('', filelist)

    @Slot()
    def on_actionOpen_triggered(self):  # pylint: disable=invalid-name
        settings = QSettings('Steigan', 'Mini PDF Tools')
        lastfn = settings.value('lastfilename', '')

        # QMessageBox.information(self, 'Info', lastfn)

        directory = os.path.dirname(lastfn)
        to_open, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл PDF",
            directory,
            f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in self._valid_extensions).strip()})",
        )
        # if to_open.isValid():
        if to_open:
            self.open(QUrl.fromLocalFile(to_open))

    @Slot()
    def on_actionClose_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.close()
        # noinspection PyTypeChecker
        self.open('')

    def check_new_file(self, outfile, ext, ind, overwrite_all):
        if ind < 10000:
            fn = f'{outfile}-%04i{ext}' % ind
        else:
            fn = f'{outfile}-{ind}{ext}'
        if not overwrite_all and os.path.exists(fn):
            self._msg_box.setText(f'Файл \'{fn}\' уже существует. Перезаписать поверх?')
            res = self._msg_box.exec()
            if (res == QMessageBox.StandardButton.No) or (res == QMessageBox.StandardButton.Cancel):
                fn = ''
            return fn, (res == QMessageBox.StandardButton.YesToAll), (res == QMessageBox.StandardButton.Cancel)
        else:
            return fn, overwrite_all, False

    def show_save_error_msg(self, e):
        m_msg_box = QMessageBox(self)
        m_msg_box.setIcon(QMessageBox.Icon.Warning)
        m_msg_box.setWindowTitle(self._title)
        m_msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        m_msg_box.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
        m_msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
        m_msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        m_msg_box.setText(f'Ошибка: {e}\n\nПродолжить процесс сохранения остальных файлов?')
        res = m_msg_box.exec()
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
            _, transform = page.get_image_bbox(docimg, transform=True)

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
            decocde_qr = decode(img, [ZBarSymbol.QRCODE])
            qr_txt = ''
            fio = []
            addr = []
            # Обходим все распознанные QR коды
            for qr_obj in decocde_qr:
                txt = qr_obj.data.decode('utf-8')
                # Это банковский QR код?
                if txt.startswith('ST00012|'):
                    if not qr_txt:
                        qr_txt = txt

                    # Расширяем границы QR (в исходных координатах изображения)
                    r = fitz.Rect(
                        qr_obj.rect.left,
                        qr_obj.rect.top,
                        qr_obj.rect.left + qr_obj.rect.width,
                        qr_obj.rect.top + qr_obj.rect.height,
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
                except (TypeError, ValueError):
                    fio = []
                # Выделяем ключевые слова из адреса
                try:
                    addr = [w for w in re.search(r'\|payerAddress=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
                except (TypeError, ValueError):
                    addr = []
                # print(fio, addr)

        # !!! page.rect.width - это ширина с учетом поворота страницы !!!
        hcenter = page.rect.width // 2
        vcenter = page.rect.height // 2
        # print(hcenter, vcenter)

        # Получаем список слов на странице с их координатами
        words = page.get_text("words")

        r_ls = r_period = r_kuda = r_kogo = None
        r_fio_addr = []
        # rFIO = []
        r_fio_grpd = []
        # rAddr = []
        r_addr_grpd = []

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
                r_fio_addr.append(r)
            if w[4] == 'КУДА:':
                r_kuda = fitz.Rect(w[:4])
            if w[4] == 'КОГО:':
                r_kogo = fitz.Rect(w[:4])
            if w[4] == 'л.с':
                r_ls = fitz.Rect(w[:4])
            if w[4] == 'период:':
                r_period = fitz.Rect(w[:4])

        if r_kuda and r_kogo:
            hght = r_kuda.y1 - r_kogo.y1 - 0
            lft = 100

            r_kuda.y0 = r_kuda.y1 - hght
            r_kuda.x1 = r_kuda.x0 - 1
            r_kuda.x0 = lft
            anon_rects.append([r_kuda, 'POST'])

            # rKogo.y0 = rKogo.y1 - hght
            # rKogo.x1 = rKogo.x0 - 1
            # rKogo.x1 = lft
            # anon_rects.append([rKogo, 'ОТПРАВИТЕЛЬ', True])

        if r_ls and r_period:
            r_ls.y0 = r_period.y1 + 1
            r_ls.x1 += 1
            r_ls.y1 += 1
            anon_rects.append([r_ls, 'IPU'])

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

        left_fio_ind = 1
        right_fio_ind = 1
        max_y = 1000
        if r_kogo:
            max_y = min(r_kogo.y0, r_kogo.y1)
        # print(max_y)
        r_fio_addr.sort(key=rectsort_x0_key)
        for grp, items in groupby(r_fio_addr, key=rectsort_x0_key):
            r = fitz.Rect(grp, 1000, 0, 0)
            for item in items:
                r.y0 = min(r.y0, item.y0, item.y1)
                r.y1 = max(r.y1, item.y0, item.y1)
                r.x1 = item.x1
            if r.x0 < vcenter:
                # print(r)
                if (r.y1 > hcenter) and (r.y0 < max_y):
                    if left_fio_ind == 1:
                        r_fio_grpd.append(r)
                        left_fio_ind = 2
                    elif left_fio_ind == 2:
                        r_addr_grpd.append(r)
                        left_fio_ind = 0
                else:
                    if right_fio_ind == 1:
                        r_fio_grpd.append(r)
                        right_fio_ind = 2
                    elif right_fio_ind == 2:
                        r_addr_grpd.append(r)
                        right_fio_ind = 0

        is_do_addr = False
        if len(r_fio_grpd) > 0:
            r = fitz.Rect(r_fio_grpd[0])
            if len(r_addr_grpd) > 0:
                r.y0 = min(r.y0, r_addr_grpd[0].y0)
                r.y1 = max(r.y1, r_addr_grpd[0].y1)
                is_do_addr = True
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'FIO'])

        if is_do_addr:
            # noinspection PyUnboundLocalVariable
            r.x0 = r_addr_grpd[0].x0
            r.x1 = r_addr_grpd[0].x1 + 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])
        elif len(r_addr_grpd) > 0:
            r = fitz.Rect(r_addr_grpd[0])
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])

        is_do_addr = False
        if len(r_fio_grpd) > 1:
            r = r_fio_grpd[1]
            if len(r_addr_grpd) > 1:
                r.y0 = min(r.y0, r_addr_grpd[1].y0)
                r.y1 = max(r.y1, r_addr_grpd[1].y1)
                is_do_addr = True
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'FIO', False])

        if is_do_addr:
            r.x0 = r_addr_grpd[1].x0
            r.x1 = r_addr_grpd[1].x1 + 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])
        elif len(r_addr_grpd) > 1:
            r = fitz.Rect(r_addr_grpd[1])
            r.y0 -= 20
            r.y1 += 20
            r.x1 += 1
            anon_rects.append([fitz.Rect(r), 'ADDR'])

        md_list = ['FIO', 'ADDR', 'POST', 'IPU', 'QR']
        chks_list = [p.censore_fio, p.censore_addr, p.censore_post, p.censore_ipu, p.censore_qr]

        if not p.setselectionsonly:
            # Растеризуем страницу и запихиваем изображение в PIL
            pix = page.get_pixmap(matrix=mat)
            pix.set_dpi(p.dpi, p.dpi)
            img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)

        for anon_rect in anon_rects:
            if chks_list[md_list.index(anon_rect[1])]:
                if p.setselectionsonly:
                    self.pdf_view.add_selection(pno, anon_rect[0])
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
                        img_small = crop_img.resize((crop_img.size[0] // pixelator, crop_img.size[1] // pixelator))
                        blur_image = img_small.resize(crop_img.size, PILImage.NEAREST)
                        img.paste(blur_image, r)
                    except Exception:
                        pass

        if not p.setselectionsonly:
            samples = img.tobytes()
            pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)
            return pix

    def saveas_process(self, p: SaveParams, censore: bool):  # noqa: ignore=C901
        if censore:
            self._title = 'Деперсонификация данных'
        else:
            self._title = 'Сохранить как'

        if p.pgmode == PageMode.PG_ALL:
            pageranges = [range(0, self.pdf_view.page_count)]
            approx_pgcount = self.pdf_view.page_count
        elif p.pgmode == PageMode.PG_CURRENT:
            pageranges = [range(self.pdf_view.current_page, self.pdf_view.current_page + 1)]
            approx_pgcount = 1
        else:
            approx_pgcount = 0
            pageranges = []
            for grp in re.findall('([0-9-]+),', p.pgrange + ','):
                subgrp = re.findall(r'(\d*)-*', grp)
                r_start = 0
                if not grp.startswith('-'):
                    r_start = max(r_start, int(subgrp[0]))
                r_end = self.pdf_view.page_count + 1
                if not grp.endswith('-'):
                    r_end = min(r_end, int(subgrp[-2]))
                if r_start > r_end:
                    # r_start, r_end = r_end, r_start
                    if r_end <= self.pdf_view.page_count and r_start > 0:
                        pageranges.append(range(r_start - 1, r_end - 2, -1))
                        approx_pgcount += r_start - r_end + 1  # Примерное количество из-за границ
                else:
                    if r_start <= self.pdf_view.page_count and r_end > 0:
                        pageranges.append(range(r_start - 1, r_end))
                        approx_pgcount += r_end - r_start + 1  # Примерное количество из-за границ
                # print(r_start, r_end)
            # print(pageranges)
            if not pageranges:
                QMessageBox.critical(self, self._title, "Не задан список страниц!")
                return

        if p.setselectionsonly:
            if self.pdf_view.selections_all_count > 0:
                self._msg_box.setIcon(QMessageBox.Icon.Question)
                self._msg_box.setWindowTitle(self._title)
                self._msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                self._msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                self._msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
                self._msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
                self._msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
                self._msg_box.setText('Документ уже содержит выделенные области. Очистить их?')
                res = self._msg_box.exec()
                if res == QMessageBox.StandardButton.Cancel:
                    return
                elif res == QMessageBox.StandardButton.Yes:
                    self.pdf_view.remove_selection(True)

            self.statusBar().showMessage('Поиск и выделение персональных данных...')
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()
            ind = 0
            doc = self.pdf_view.m_doc
            for pages in pageranges:
                for pno in pages:
                    if 0 <= pno < doc.page_count:
                        self.censore_page(doc=doc, pno=pno, p=p)
                        ind += 1
                        self.progress_bar.setValue(ind * 100 // approx_pgcount)
                        QApplication.processEvents()

            self.rect_selected(self.pdf_view.selected_rect > -1)
            return

        # outfile, _ = os.path.splitext(self.m_currentFileName)

        if p.format in [FileFormat.FMT_JPEG, FileFormat.FMT_PNG]:
            m_singles = True
        else:
            m_singles = p.singles

        if m_singles:
            ext_tp = [".pdf", ".jpg", ".png"][max(p.format.value - 1, 0)]
            outfile, _ = QFileDialog.getSaveFileName(
                self,
                self._title,
                os.path.dirname(self._current_filename),
                r'Серия файлов {имя}' + f'-XXXX{ext_tp} (*{ext_tp})',
                options=QFileDialog.Option.DontConfirmOverwrite,
            )

            outfile, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != ext_tp:
                ext = ext_tp
        else:
            outfile, _ = QFileDialog.getSaveFileName(
                self, self._title, os.path.dirname(self._current_filename), r'Файл PDF (*.pdf)'
            )
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != ".pdf":
                ext = ".pdf"
                outfile += ext

        if not outfile:
            return

        if outfile == self._current_filename:
            QMessageBox.critical(self, self._title, "Нельзя сохранять файл в самого себя!")
            return

        self.statusBar().showMessage('Сохранение файла/файлов...')
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.setDisabled(True)
        QApplication.processEvents()

        # doc = fitz.open(self.m_currentFileName)
        doc = self.pdf_view.m_doc

        zoom = p.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        if p.format in [FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG] and not m_singles:
            # noinspection PyUnresolvedReferences
            pdfout = fitz.open()
        ind = 0

        self._msg_box.setIcon(QMessageBox.Icon.Question)
        self._msg_box.setWindowTitle(self._title)
        self._msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.YesToAll
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        self._msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        self._msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
        self._msg_box.button(QMessageBox.StandardButton.YesToAll).setText('  Да для всех  ')
        self._msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
        self._msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

        # Эксклюзивный режим ...
        if (
            self._real_file
            and p.format == FileFormat.FMT_PDF
            and p.pgmode == PageMode.PG_ALL
            and (not m_singles)
            and doc.can_save_incrementally()
        ):
            # noinspection PyUnboundLocalVariable
            pdfout.close()
            # doc.close()
            # doc = None
            try:
                shutil.copyfile(self._current_filename, outfile)
            except Exception as e:
                QMessageBox.critical(
                    self, self._title, f"Ошибка: {e}\n\nПопробуйте сохранить файл как диапазон из всех страниц [1-]."
                )
                return

            # print('Эксклюзивный режим ...')
            # noinspection PyUnresolvedReferences
            doc = fitz.open(outfile)
            if doc.needs_pass:
                doc.authenticate(self.pdf_view.psw)
            for pno in range(approx_pgcount):
                # if p.rotation != PageRotation.rtNone:
                # Пытаемся повернуть страницу в соответствии с отображаемым на экране объектом
                doc[pno].set_rotation((self.pdf_view.m_doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)
                self.progress_bar.setValue(pno * 95 // approx_pgcount)
                QApplication.processEvents()
            try:
                doc.save(
                    outfile, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
                )  # , garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
            except Exception as e:
                QMessageBox.critical(self, self._title, f"Ошибка: {e}")
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

                        self.progress_bar.setValue(ind * 100 // approx_pgcount)
                        QApplication.processEvents()

                        old_rot = doc[pno].rotation
                        if p.rotation != PageRotation.RT_NONE:
                            doc[pno].set_rotation((doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)

                        try:
                            if p.format == FileFormat.FMT_PDF:
                                if m_singles:
                                    # noinspection PyUnresolvedReferences
                                    newdoc = fitz.open()
                                    newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

                                    fn, overwrite_all, abort = self.check_new_file(outfile, ext, ind, overwrite_all)
                                    if abort:
                                        raise FileNotFoundError('Файл для записи не определен')
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
                                            if self.show_save_error_msg(e) == QMessageBox.StandardButton.Cancel:
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
                                            for sel in self.pdf_view.selections_all
                                            if (sel.pno == -1 or sel.pno == pno)
                                        ]
                                        if len(sels) > 0:
                                            img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)
                                            page_r = fitz.Rect(0, 0, pix.width, pix.height)
                                            for sel in sels:
                                                r = (
                                                    self.pdf_view.get_selection_fitz_rect(pno, old_rot, sel)
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
                                                            img_small = crop_img.resize(
                                                                (
                                                                    crop_img.size[0] // pixelator,
                                                                    crop_img.size[1] // pixelator,
                                                                )
                                                            )
                                                            blur_image = img_small.resize(
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

                                if p.format == FileFormat.FMT_PDF_JPEG:
                                    temp = io.BytesIO()
                                    pix.pil_save(temp, format="jpeg", quality=p.quality)
                                    if m_singles:
                                        # noinspection PyUnresolvedReferences
                                        newdoc = fitz.open()
                                        opage = newdoc.new_page(width=page.rect.width, height=page.rect.height)
                                        opage.insert_image(opage.rect, stream=temp)

                                        fn, overwrite_all, abort = self.check_new_file(outfile, ext, ind, overwrite_all)
                                        if abort:
                                            raise FileNotFoundError('Файл для записи не определен')
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
                                                if self.show_save_error_msg(e) == QMessageBox.StandardButton.Cancel:
                                                    newdoc.close()
                                                    raise

                                        newdoc.close()
                                    else:
                                        opage = pdfout.new_page(width=page.rect.width, height=page.rect.height)
                                        opage.insert_image(opage.rect, stream=temp)
                                else:
                                    fn, overwrite_all, abort = self.check_new_file(outfile, ext, ind, overwrite_all)
                                    if abort:
                                        raise FileNotFoundError('Файл для записи не определен')
                                    if fn:
                                        try:
                                            if p.format == FileFormat.FMT_JPEG:
                                                pix.pil_save(fn, format="jpeg", quality=p.quality)
                                            else:
                                                pix.pil_save(fn, format="png")
                                        except Exception as e:
                                            if self.show_save_error_msg(e) == QMessageBox.StandardButton.Cancel:
                                                raise
                        except Exception:
                            # Вертаем поворот страницы взад
                            if p.rotation != PageRotation.RT_NONE:
                                doc[pno].set_rotation(old_rot)
                            return

                        if p.rotation != PageRotation.RT_NONE:
                            doc[pno].set_rotation(old_rot)

            if p.format in [FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG] and not m_singles:
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
                    QMessageBox.critical(self, self._title, f"Ошибка: {e}")
                    pdfout.close()
                    return
                pdfout.close()

        self.progress_bar.setValue(100)
        QApplication.processEvents()

        self.statusBar().showMessage('Готово!')
        if p.format in [FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG] and not m_singles:
            # if platform.system() == 'Windows':
            #     subprocess.Popen(('start', outfile), shell = True)
            if self._pdfviewer_cmd:
                subprocess.Popen((self._pdfviewer_cmd, outfile))
        QMessageBox.information(self, "Сохранение файла/файлов", "Готово!")

    def tableanalize_process(self, strong):
        self._title = "Экспорт табличных данных в XLSX"
        outfile, _ = QFileDialog.getSaveFileName(
            self, self._title, os.path.dirname(self._current_filename), r'Книга Excel "(*.xlsx)"'
        )
        if outfile:
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != '.xlsx':
                outfile += '.xlsx'

            self.statusBar().showMessage('Экспорт табличных данных в XLSX...')
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()

            try:
                if os.path.isfile(outfile):
                    os.remove(outfile)
                # doc = fitz.open(self.m_currentFileName)
                doc = self.pdf_view.m_doc
            except Exception as e:
                QMessageBox.critical(self, self._title, f"Ошибка: {e}")
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
            try:
                # for pno in range(len(doc)):
                for pno in enumerate(doc):
                    start_row += parse_page_tables(doc[pno], worksheet, start_row, cell_format, strong)
                    self.progress_bar.setValue(pno * 99 // pgcount)
                    QApplication.processEvents()

                workbook.close()
            except Exception as e:
                QMessageBox.critical(self, self._title, f"Ошибка: {e}")
                return

            self.progress_bar.setValue(100)
            QApplication.processEvents()
            if start_row > 0:
                if self._xlseditor_cmd:
                    subprocess.Popen((self._xlseditor_cmd, outfile))
                self.statusBar().showMessage('Готово!')
            else:
                QMessageBox.warning(self, self._title, "Табличные данные найти не удалось...")

    def exportpd_process(self, recognize_qr):
        self._title = "Экспорт данных в XLSX"
        outfile, _ = QFileDialog.getSaveFileName(
            self, self._title, os.path.dirname(self._current_filename), r'Книга Excel "(*.xlsx)"'
        )
        if outfile:
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != '.xlsx':
                outfile += '.xlsx'

            self.statusBar().showMessage('Экспорт данных в XLSX...')
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.setDisabled(True)
            QApplication.processEvents()

            try:
                if os.path.isfile(outfile):
                    os.remove(outfile)
                # doc = fitz.open(self.m_currentFileName)
                doc = self.pdf_view.m_doc
            except Exception as e:
                QMessageBox.critical(self, self._title, f"Ошибка: {e}")
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
            if recognize_qr:
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

                if recognize_qr:
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
                        decocde_qr = decode(img, [ZBarSymbol.QRCODE])
                        for qr_obj in decocde_qr:
                            txt += ('\n-------------------\n' if txt else '') + qr_obj.data.decode('utf-8')
                    worksheet_det.write_string(ii, 2, txt, cell_format)

                if np != old_np:
                    if old_np:
                        np_list.append((old_np, np_start_pg, current_page))

                    old_np = np
                    np_start_pg = current_page + 1

                self.progress_bar.setValue(current_page * 95 // pgcount)
                QApplication.processEvents()
                # self.progressBar.setValue(current_page * 95 / pgcount)

            if old_np:
                # noinspection PyUnboundLocalVariable
                np_list.append((old_np, np_start_pg, current_page + 1))

            # print(np_list)
            worksheet_det.freeze_panes(1, 0)
            if recognize_qr:
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

            fnm = os.path.basename(self._current_filename)
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
                QMessageBox.critical(self, self._title, f"Ошибка: {e}")
                return

            self.progress_bar.setValue(100)
            QApplication.processEvents()
            # if platform.system() == 'Windows':
            #     subprocess.Popen(('start', outfile), shell = True)
            if self._xlseditor_cmd:
                subprocess.Popen((self._xlseditor_cmd, outfile))
            self.statusBar().showMessage('Готово!')
            # QMessageBox.information(self, "Экспорт данных в XLSX", "Готово!")

    @Slot()
    def on_actionSaveAs_triggered(self):  # pylint: disable=invalid-name
        dlg = SaveAsDialog(self)
        if dlg.exec_():
            self.saveas_process(dlg.params(), False)

            self.progress_bar.setVisible(False)
            self.setDisabled(False)
            self.statusBar().showMessage('')
            QApplication.processEvents()

    @Slot()
    def on_actionCensore_triggered(self):  # pylint: disable=invalid-name
        dlg = CensoreDialog(self)
        if dlg.exec_():
            # Отключаем режим small_glyph_heights, т.к. с ним некорректно определяется положение "КУДА" и "ОТ КОГО"
            fitz.Tools().set_small_glyph_heights(False)

            dlg.params().format = dlg.params().format_censore
            self.saveas_process(dlg.params(), True)

            self.progress_bar.setVisible(False)
            self.setDisabled(False)
            self.statusBar().showMessage('')
            QApplication.processEvents()

            # Для наилучшего распознания текстового слоя...
            fitz.Tools().set_small_glyph_heights(True)

    @Slot()
    def on_actionTablesAnalizeStrong_triggered(self):  # pylint: disable=invalid-name
        self.tableanalize_process(True)
        self.progress_bar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionTablesAnalizeSimple_triggered(self):  # pylint: disable=invalid-name
        self.tableanalize_process(False)
        self.progress_bar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionPDexport_triggered(self):  # pylint: disable=invalid-name
        self.exportpd_process(False)
        self.progress_bar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionPDexportQR_triggered(self):  # pylint: disable=invalid-name
        self.exportpd_process(True)
        self.progress_bar.setVisible(False)
        self.setDisabled(False)
        self.statusBar().showMessage('')
        QApplication.processEvents()

    @Slot()
    def on_actionQuit_triggered(self):  # pylint: disable=invalid-name
        self.close()

    @Slot()
    def on_actionHome_triggered(self):  # pylint: disable=invalid-name
        if self.pdf_view.page_count > 0:
            self.page_select(0)

    @Slot()
    def on_actionEnd_triggered(self):  # pylint: disable=invalid-name
        if self.pdf_view.page_count > 0:
            self.page_select(self.pdf_view.page_count - 1)

    @Slot()
    def on_actionAbout_triggered(self):  # pylint: disable=invalid-name
        QMessageBox.about(self, "О программе Mini PDF Tools", ABOUT_TEXT)

    @Slot()
    def on_actionZoom_In_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.zoom_in()

    @Slot()
    def on_actionZoom_Out_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.zoom_out()

    @Slot()
    def on_actionZoom_Normal_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.set_zoom_factor(1.0)

    @Slot()
    def on_actionPrevious_Page_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.goto_prev_page()

    @Slot()
    def on_actionNext_Page_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.goto_next_page()

    @Slot()
    def on_actionCbdPageImageCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_page_image_to_clipboard()

    @Slot()
    def on_actionCbdRectImageCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_rect_image_to_clipboard()

    @Slot()
    def on_actionCbdRectTextCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_rect_text_to_clipboard()

    @Slot()
    def on_actionCbdRectTextTrimCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_rect_text_to_clipboard(True)

    @Slot()
    def on_actionRectRecognizeText_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, trim=False)

    @Slot()
    def on_actionRectRecognizeTextTrim_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, trim=True)

    @Slot()
    def on_actionRectRecognizeQR_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.recognize_qr_and_copy_to_clipboard()

    @Slot()
    def on_actionCbdRectsInfoCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_rects_info_to_clipboard(False)

    @Slot()
    def on_actionCbdRectsAllInfoCopy_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.copy_rects_info_to_clipboard(True)

    @Slot()
    def on_actionSelectAll_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.select_all()

    @Slot()
    def on_actionRemoveSelection_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.remove_selection()

    @Slot()
    def on_actionRemoveAllSelections_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.remove_selection(True)

    @Slot()
    def on_actionRectMode_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.switch_rect_mode()

    @Slot()
    def on_actionPageRotateLeft_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(1, False)

    @Slot()
    def on_actionPageRotateRight_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(2, False)

    @Slot()
    def on_actionPageRotate180_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(3, False)

    @Slot()
    def on_actionPagesRotateLeft_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(1, True)

    @Slot()
    def on_actionPagesRotateRight_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(2, True)

    @Slot()
    def on_actionPagesRotate180_triggered(self):  # pylint: disable=invalid-name
        self.pdf_view.rotate_pages(3, True)
