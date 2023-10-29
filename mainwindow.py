"""
Этот файл содержит класс основного окна приложения
"""

import logging
import os
import platform
import subprocess

import fitz
from PySide2.QtCore import Qt
from PySide2.QtCore import Slot
from PySide2.QtGui import QCloseEvent
from PySide2.QtGui import QDragEnterEvent
from PySide2.QtGui import QDropEvent
from PySide2.QtWidgets import QAbstractSpinBox
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWidgets import QMainWindow
from PySide2.QtWidgets import QMenu
from PySide2.QtWidgets import QMessageBox
from PySide2.QtWidgets import QProgressBar

import const
import params
from censoredlg import CensoreDialog
from censorepd import censore_page
from combinedlg import CombineDialog
from exportpd import export_pd
from mainwindow_ui import Ui_MainWindow
from saveasdlg import SaveAsDialog
from savepdf import saveas_process
from siapdfview import PageNumberSpinBox
from siapdfview import SiaPdfView
from siapdfview import ZoomSelector
from tableanalize import parse_tables


ABOUT_TEXT = """
Mini PDF Tools - мини набор инструментов для просмотра и обработки файлов PDF.
Версия от 27.10.2023 (c) 2023 Игорь Степаненков

Используемые пакеты и библиотеки:
PySide2 (c) 2022 The Qt Company Ltd.
PyMuPDF (c) 2023 Artifex Software, Inc.
Pillow - PIL fork by Alex Clark and Contributors
XlsxWriter (c) 2013-2023 John McNamara
PyZBar (c) 2022 Lawrence Hudson
PyTesseract for Google's Tesseract-OCR Engine (c) 2022 Samuel Hoffstaetter
Paomedia Small & Flat Icons
"""

DETACHED_PROCESS = 0x00000008


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler('log.log')
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)

logger.info('Запуск приложения...')


class MainWindow(QMainWindow):  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Главное окно программы"""

    def __init__(self, parent=None):
        # Инициализируем интерфейс на основе автокода QT
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Загружаем настройки для запуска внешних приложений
        self._tesseract_cmd, self._pdfviewer_cmd, self._xlseditor_cmd = params.get_apps_paths()

        # Добавляем элементы интерфейса для изменения масштаба и выбора номера страницы
        self.ui.zoom_selector = ZoomSelector(self)
        self.ui.zoom_selector.setMaximumWidth(150)
        self.ui.page_selector = PageNumberSpinBox(self)

        # Настраиваем панель состояния, выключаем ее видимость
        self.statusBar().showMessage('')
        self.ui.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.ui.progress_bar)
        self.ui.progress_bar.setGeometry(30, 40, 200, 20)
        self.ui.progress_bar.setVisible(False)

        # Вставляем zoomSelector перед actionZoom_In
        self.ui.mainToolBar.insertWidget(self.ui.actionZoom_In, self.ui.zoom_selector)

        # Вставляем pageSelector перед actionForward
        self.ui.mainToolBar.insertWidget(self.ui.actionNext_Page, self.ui.page_selector)
        self.ui.page_selector.setEnabled(False)
        self.ui.page_selector.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.ui.page_selector.setSuffix(' из 0')
        self.ui.page_selector.setMinimumWidth(70)
        self.ui.page_selector.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Создаем виджет для области просмотра документа
        self.pdf_view = SiaPdfView(self)
        self.setCentralWidget(self.pdf_view)

        # Создаем контекстное меню
        self.ui.pop_menu = self._setup_popup_menu()

        # Подключаем соединения между элементами интерфейса (привязываем обработчики событий)
        self._setup_qt_connections()

        # Сбрасываем значения в виджетах масштабирования на 100%
        self.ui.zoom_selector.reset()

        # Настраиваем политику контекстного меню для области просмотра документа
        self.pdf_view.setContextMenuPolicy(Qt.CustomContextMenu)

        # Включаем прием файлов с применением DragAndDrop
        self.setAcceptDrops(True)

        # Задаем минимальный размер окна
        self.setMinimumSize(500, 400)
        # Максимизируем окно
        self.showMaximized()
        # Устанавливаем фокус на область просмотра документа
        self.pdf_view.setFocus()

        # Для наилучшего распознания текстового слоя...
        fitz.Tools().set_small_glyph_heights(True)

        # Дежурный объект для вывода сообщений
        self.ui.msg_box = QMessageBox(self)

        # Заголовок для дежурного объекта для вывода сообщений
        self._title = ''

    def _setup_popup_menu(self) -> QMenu:
        """Создание контекстного меню"""

        # Создаем контекстное меню
        pop_menu = QMenu(self)
        pop_menu.addAction(self.ui.actionCbdRectTextCopy)
        pop_menu.addAction(self.ui.actionCbdRectTextTrimCopy)
        pop_menu.addSeparator()
        pop_menu.addAction(self.ui.actionCbdRectImageCopy)
        pop_menu.addAction(self.ui.actionCbdPageImageCopy)
        pop_menu.addSeparator()

        # Если указан путь к Tesseract OCR
        if self._tesseract_cmd:
            pop_menu.addAction(self.ui.actionRectRecognizeText)
            pop_menu.addAction(self.ui.actionRectRecognizeTextTrim)
            pop_menu.addSeparator()
        else:
            self.ui.actionRectRecognizeText.setVisible(False)
            self.ui.actionRectRecognizeTextTrim.setVisible(False)
            self.ui.menuView.setSeparatorsCollapsible(True)

        pop_menu.addAction(self.ui.actionRectRecognizeQR)
        pop_menu.addSeparator()
        pop_menu.addAction(self.ui.actionCbdRectsInfoCopy)
        pop_menu.addAction(self.ui.actionCbdRectsAllInfoCopy)
        pop_menu.addSeparator()
        pop_menu.addAction(self.ui.actionRectMode)
        pop_menu.addSeparator()
        pop_menu.addAction(self.ui.actionSelectAll)
        pop_menu.addAction(self.ui.actionRemoveSelection)
        pop_menu.addAction(self.ui.actionRemoveAllSelections)
        return pop_menu

    def _setup_qt_connections(self):
        """Подключение соединений между элементами интерфейса"""
        # Привязываем обработчики событий, поступивших от области просмотра документа
        self.pdf_view.current_page_changed.connect(self.ui.page_selector.change_page_number)
        self.pdf_view.zoom_factor_changed.connect(self.ui.zoom_selector.set_zoom_factor)
        self.pdf_view.rect_selected.connect(self._process_rect_selection)
        self.pdf_view.coords_text_emited.connect(self.statusBar().showMessage)

        # Привязываем обработчик изменения значения зум-фактора и номера страницы в панели инструментов
        self.ui.zoom_selector.zoom_factor_changed.connect(self.pdf_view.set_zoom_factor)
        self.ui.page_selector.valueChanged.connect(self._change_page)

        # Обработчики выбора пунктов меню
        self.ui.actionNew.triggered.connect(lambda: self.show_combine_files_dialog([]))
        self.ui.actionQuit.triggered.connect(self.close)

        self.ui.actionHome.triggered.connect(self.pdf_view.goto_home)
        self.ui.actionPrevious_Page.triggered.connect(self.pdf_view.goto_prev_page)
        self.ui.actionNext_Page.triggered.connect(self.pdf_view.goto_next_page)
        self.ui.actionEnd.triggered.connect(self.pdf_view.goto_end)

        self.ui.actionZoom_In.triggered.connect(self.pdf_view.zoom_in)
        self.ui.actionZoom_Out.triggered.connect(self.pdf_view.zoom_out)
        self.ui.actionZoom_Normal.triggered.connect(lambda: self.pdf_view.set_zoom_factor(1.0))

        self.ui.actionCbdPageImageCopy.triggered.connect(lambda: self.pdf_view.copy_page_image_to_clipboard(False))
        self.ui.actionCbdRectImageCopy.triggered.connect(lambda: self.pdf_view.copy_page_image_to_clipboard(True))

        self.ui.actionCbdRectTextCopy.triggered.connect(self.pdf_view.copy_rect_text_to_clipboard)
        self.ui.actionCbdRectTextTrimCopy.triggered.connect(lambda: self.pdf_view.copy_rect_text_to_clipboard(True))
        self.ui.actionRectRecognizeText.triggered.connect(
            lambda: self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, is_trim=False)
        )
        self.ui.actionRectRecognizeTextTrim.triggered.connect(
            lambda: self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, is_trim=True)
        )
        self.ui.actionRectRecognizeQR.triggered.connect(self.pdf_view.recognize_qr_and_copy_to_clipboard)

        self.ui.actionCbdRectsInfoCopy.triggered.connect(lambda: self.pdf_view.copy_rects_info_to_clipboard(False))
        self.ui.actionCbdRectsAllInfoCopy.triggered.connect(lambda: self.pdf_view.copy_rects_info_to_clipboard(True))

        self.ui.actionSelectAll.triggered.connect(self.pdf_view.select_all)
        self.ui.actionRemoveSelection.triggered.connect(self.pdf_view.remove_selection)
        self.ui.actionRemoveAllSelections.triggered.connect(lambda: self.pdf_view.remove_selection(True))

        self.ui.actionRectMode.triggered.connect(self.pdf_view.switch_rect_mode)

        self.ui.actionPageRotateLeft.triggered.connect(lambda: self.pdf_view.rotate_pages(1, False))
        self.ui.actionPageRotateRight.triggered.connect(lambda: self.pdf_view.rotate_pages(2, False))
        self.ui.actionPageRotate180.triggered.connect(lambda: self.pdf_view.rotate_pages(3, False))

        self.ui.actionPagesRotateLeft.triggered.connect(lambda: self.pdf_view.rotate_pages(1, True))
        self.ui.actionPagesRotateRight.triggered.connect(lambda: self.pdf_view.rotate_pages(2, True))
        self.ui.actionPagesRotate180.triggered.connect(lambda: self.pdf_view.rotate_pages(3, True))

        # Привязываем обработчик вывода контекстного меню для области просмотра документа
        self.pdf_view.customContextMenuRequested.connect(self._show_context_menu)

        self.ui.actionAbout.triggered.connect(
            lambda: QMessageBox.about(self, "О программе " + const.APP_TITLE, ABOUT_TEXT)
        )

    def _setup_controls(self):
        """Обновление доступности контролов и их значений в зависимости от открытого файла"""

        # Файл открыт?
        is_file_opened = self.pdf_view.page_count > 0
        if is_file_opened:
            # Файл открыт - меняем заголовок окна, диапазон страниц
            self.setWindowTitle(const.APP_TITLE + ' - ' + self.pdf_view.current_filename)
            self.ui.page_selector.setRange(1, self.pdf_view.page_count)
            self.ui.page_selector.setSuffix(f' из {self.pdf_view.page_count}')
            # Переходим на первую страницу
            self._change_page(1)
            # Запоминаем путь к реальному файлу PDF
            if self.pdf_view.is_real_file:
                params.set_lastfilename(self.pdf_view.current_filename)
        else:
            # Файл не открыт - гасим все
            self.setWindowTitle(const.APP_TITLE)
            self.ui.page_selector.setRange(0, 1)
            self.ui.page_selector.setSuffix(' из 0')
            self.ui.page_selector.setValue(0)

        # Переключаем доступность элементов интерфейса в зависимости от
        # наличия открытого файла
        for widget in (
            self.ui.page_selector,
            self.ui.zoom_selector,
            self.ui.actionZoom_In,
            self.ui.actionZoom_Out,
            self.ui.actionZoom_Normal,
            self.ui.actionSaveAs,
            self.ui.actionClose,
            self.ui.actionTablesAnalizeStrong,
            self.ui.actionTablesAnalizeSimple,
            self.ui.actionPDexport,
            self.ui.actionPDexportQR,
            self.ui.actionCensore,
            self.ui.actionCbdPageImageCopy,
            self.ui.actionSelectAll,
            self.ui.actionPageRotateLeft,
            self.ui.actionPageRotateRight,
            self.ui.actionPageRotate180,
            self.ui.actionPagesRotateLeft,
            self.ui.actionPagesRotateRight,
            self.ui.actionPagesRotate180,
        ):
            widget.setEnabled(is_file_opened)

        # Отключаем доступность пункта меню удаления всех выделений
        self.ui.actionRemoveAllSelections.setEnabled(False)

    def _process_rect_selection(self, selected: bool):
        """Обработчик изменения количества выделенных областей и наличия активного выделения"""

        # Переключаем доступность элементов интерфейса в зависимости от наличия активного выделения
        for widget in (
            (
                self.ui.actionCbdRectTextCopy,
                self.ui.actionCbdRectTextTrimCopy,
                self.ui.actionCbdRectImageCopy,
                self.ui.actionRemoveSelection,
                self.ui.actionRectMode,
                self.ui.actionRectRecognizeQR,
            )
            + (self.ui.actionRectRecognizeText, self.ui.actionRectRecognizeTextTrim)
            if self.ui.actionRectRecognizeText.isVisible()
            else ()
        ):
            widget.setEnabled(selected)

        # Переключаем доступность элементов интерфейса в зависимости от наличия выделений на текущей странице
        self.ui.actionCbdRectsInfoCopy.setEnabled(self.pdf_view.selections_count > 0)

        # Переключаем доступность элементов интерфейса в зависимости от наличия выделений во всем документе
        is_selections_exists = self.pdf_view.selections_all_count > 0
        for widget in (self.ui.actionCbdRectsAllInfoCopy, self.ui.actionRemoveAllSelections):
            widget.setEnabled(is_selections_exists)

    def _show_context_menu(self, position):
        """Вывод контекстного меню (если файл открыт)"""

        if self.pdf_view.current_page > -1:
            self.ui.pop_menu.exec_(self.pdf_view.mapToGlobal(position))

    def open_or_combine_files(self, files_list=None):
        """Открыть файл или объединить несколько файлов в один и открыть его,
        обновить интерфейс в зависимости от результата
        """
        if not files_list:  # если пусто
            pass
        elif isinstance(files_list, str):  # если строка
            self.pdf_view.open_file(files_list)
        elif isinstance(files_list, list):  # если список
            self.pdf_view.combine_files(files_list)

        # Обновляем значения и доступность контролов
        self._setup_controls()

    def _change_page(self, page):
        """Обработчик события смены номера страницы, полученного от панели инструментов"""

        # Переключаем доступность элементов интерфейса в зависимости от номера страницы
        self.ui.actionPrevious_Page.setEnabled(page > 1)
        self.ui.actionHome.setEnabled(page > 1)
        self.ui.actionNext_Page.setEnabled(page < self.pdf_view.page_count)
        self.ui.actionEnd.setEnabled(page < self.pdf_view.page_count)

        # Меняем страницу в области просмотра документа
        if 0 < page <= self.pdf_view.page_count:
            self.pdf_view.goto_page(page - 1)

    def show_combine_files_dialog(self, filelist: list):
        """Вывод диалога объединения файлов и запуск обработки результата"""
        dlg = CombineDialog(self, filelist)
        if dlg.exec_():
            self.open_or_combine_files(dlg.get_filelist())

    def _save_files_process(self, p: params.SaveParams, censore: bool):
        """Сохранение файла/файлов с деперсонификацией данных или без"""

        if censore:
            self._title = 'Сохранение файла/файлов с деперсонификацией данных'
        else:
            self._title = 'Сохранение файла/файлов'

        # Получаем список объектов range с номерами страниц
        page_ranges, ranges_page_count = p.get_pages_ranges(self.pdf_view.current_page, self.pdf_view.page_count)

        # Если ничего нет...
        if not ranges_page_count:
            QMessageBox.critical(self, self._title, 'Не задан список страниц!')
            return

        # Если сохраняем в графический формат, либо стоит галка "разбивать по страницам",
        # то нужно разбивать по отдельным файлам
        if p.format in (params.FileFormat.FMT_JPEG, params.FileFormat.FMT_PNG) or p.singles:
            # Определяем расширение файлов
            ext_tp = [".pdf", ".jpg", ".png"][max(p.format.value - 1, 0)]
            # Получаем от пользователя имя "тушки" новых файлов
            outfile = self._get_savefilename(
                os.path.dirname(self.pdf_view.current_filename),
                r'Серия файлов {имя}' + f'-XXXX{ext_tp} (*{ext_tp})',
                ext_tp,
                False,
            )
        else:
            # Определяем расширение файлов
            ext_tp = '.pdf'
            # Получаем от пользователя имя нового файла
            outfile = self._get_savefilename(
                os.path.dirname(self.pdf_view.current_filename), r'Файл PDF (*.pdf)', ext_tp, True
            )

            # Проверяем имя файла на совпадение с исходным
            if outfile == self.pdf_view.current_filename:
                QMessageBox.critical(self, self._title, 'Нельзя сохранять файл в самого себя!')
                return

        # Имя файла не выбрано
        if not outfile:
            return

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self._title + '...')

        # Запускаем основную функцию сохранения файла
        try:
            res = saveas_process(
                pdf_view=self.pdf_view,
                page_ranges=page_ranges,
                ranges_page_count=ranges_page_count,
                outfile=outfile,
                ext=ext_tp,
                param=p,
                censore=censore,
                progress_callback=self._progress_status_refresh,
                overwrite_msg_callback=self._show_file_overwrite_msg,
                show_error_msg_callback=self._show_error_message,
                show_save_error_msg_callback=self._show_save_error_msg,
            )
        except Exception as e:
            self._show_error_message(e)
            return

        # Выводим финальные сообщения
        self._progress_status_final(
            res,
            success_message='Готово!',
            command=self._pdfviewer_cmd
            if p.format in (params.FileFormat.FMT_PDF, params.FileFormat.FMT_PDF_JPEG) and not p.singles
            else '',
            arg=outfile,
        )

    def _censore_selections_process(self, p: params.SaveParams):
        """Выделение областей с персональными данными"""

        self._title = 'Выделение областей с персональными данными'

        # Получаем список объектов range с номерами страниц
        page_ranges, ranges_page_count = p.get_pages_ranges(self.pdf_view.current_page, self.pdf_view.page_count)

        # Если ничего нет...
        if not ranges_page_count:
            QMessageBox.critical(self, self._title, 'Не задан список страниц!')
            return

        # Удаляем дубликаты страниц
        pages_set = set()
        for page_range in page_ranges:
            pages_set.update(page_range)

        # Подсчитываем количество страниц
        ranges_page_count = len(pages_set)

        # Если выделенные участки уже есть, то предложим их сбросить
        if self.pdf_view.selections_all_count > 0:
            # Выводим сообщение с тремя вариантами ответа Да-Нет-Отмена
            res = self._show_yes_no_cancel_message('Документ уже содержит выделенные области. Очистить их?')
            if res == QMessageBox.StandardButton.Cancel:
                return
            if res == QMessageBox.StandardButton.Yes:
                # Сбрасываем все выделенные области
                self.pdf_view.remove_selection(True)

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self._title + '...')

        # Сохраняем старое количество выделений
        old_count = self.pdf_view.selections_all_count

        ind = 0
        # Обходим указанные пользователем страницы
        for pno in pages_set:
            # Запускаем обработку страницы
            censore_page(doc=self.pdf_view.doc, pno=pno, param=p, add_selection_callback=self.pdf_view.add_selection)
            ind += 1
            self._progress_status_refresh(ind * 100 // ranges_page_count)

        # Обновляем доступность элементов
        self._process_rect_selection(self.pdf_view.selected_rect > -1)

        # Подсчитываем количество новых выделений
        old_count = self.pdf_view.selections_all_count - old_count

        # Выводим финальные сообщения
        self._progress_status_final(
            old_count > 0,
            success_message=f'Выделено областей с персональными данными: {old_count}',
            fault_message='Области с персональными данными не найдены...',
        )

    def _export_pd_process(self, recognize_qr: bool):
        """Экспорт рееста ПД в XLSX"""

        self._title = 'Экспорт рееста ПД в XLSX'

        # Получаем от пользователя имя нового файла
        outfile = self._get_savefilename(
            os.path.dirname(self.pdf_view.current_filename), r'Книга Excel "(*.xlsx)"', '.xlsx', True
        )
        # Имя файла не выбрано
        if not outfile:
            return

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self._title + '...')

        # Запускаем парсинг таблиц на всех страницах документа
        try:
            res = export_pd(
                self.pdf_view.doc, outfile, self.pdf_view.current_filename, recognize_qr, self._progress_status_refresh
            )
        except Exception as e:
            self._show_error_message(e)
            return

        # Выводим финальные сообщения
        self._progress_status_final(res, command=self._xlseditor_cmd, arg=outfile)

    def _tableanalize_process(self, strong: bool):
        """Анализ и разбор табличных данных на всех страницах файла PDF и сохранение их в файл XLSX"""

        self._title = 'Экспорт табличных данных в XLSX'

        # Получаем от пользователя имя нового файла
        outfile = self._get_savefilename(
            os.path.dirname(self.pdf_view.current_filename), r'Книга Excel "(*.xlsx)"', '.xlsx', True
        )
        # Имя файла не выбрано
        if not outfile:
            return

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self._title + '...')

        # Запускаем парсинг таблиц на всех страницах документа
        try:
            rows_count = parse_tables(self.pdf_view.doc, outfile, strong, self._progress_status_refresh)
        except Exception as e:
            self._show_error_message(e)
            return

        # Выводим финальные сообщения
        self._progress_status_final(
            rows_count > 0,
            command=self._xlseditor_cmd,
            arg=outfile,
            fault_message='Табличные данные найти не удалось...',
        )

    def _get_savefilename(self, file_dir: str, file_filter: str, file_ext: str, file_delete: bool = False) -> str:
        """Диалог выбора имени файла для сохранения"""
        if file_delete:
            outfile, _ = QFileDialog.getSaveFileName(self, self._title, file_dir, file_filter)
        else:
            outfile, _ = QFileDialog.getSaveFileName(
                self, self._title, file_dir, file_filter, options=QFileDialog.Option.DontConfirmOverwrite
            )
        # Имя файла не выбрано
        if not outfile:
            return ''

        if file_ext:  # для debian/GNOME
            _, ext = os.path.splitext(outfile)
            if ext.lower() != file_ext:  # добавляем расширение, если его нет
                outfile += file_ext

        if file_delete:
            # Пытаемся удалить файл, если он существует
            if os.path.isfile(outfile):
                try:
                    os.remove(outfile)
                except PermissionError as e:
                    self._show_error_message(e)
                    return ''

        return outfile

    def _progress_status_refresh(self, procent: int):
        """Обновление прогресс-бара"""
        self.ui.progress_bar.setValue(procent)
        QApplication.processEvents()

    def _progress_status_turnoff(self):
        """Отключение прогресс-бара с разблокированием интерфейса"""
        self.ui.progress_bar.setVisible(False)
        self.setDisabled(False)
        # self.statusBar().showMessage('')
        QApplication.processEvents()

    def _progress_status_start(self, status_message: str = ''):
        """Включение прогресс-бара с блокированием интерфейса и вывод статус-сообщения"""
        self.statusBar().showMessage(status_message)
        self.ui.progress_bar.setValue(0)
        self.ui.progress_bar.setVisible(True)
        self.setDisabled(True)
        QApplication.processEvents()

    def _progress_status_final(
        self,
        is_success: bool = False,
        success_message: str = '',
        fault_message: str = '',
        command: str = '',
        arg: str = '',
    ):  # pylint: disable=too-many-arguments
        """Финальное сообщение закончившегося процесса"""

        if is_success:
            self.statusBar().showMessage('Готово!')
            if command:
                # Во всех вариантах запуска (проверялось под Windows) при дебаге дочерний процесс привязан
                # к этой программе. Поэтому он уничтожается после выхода из основного приложения.
                if platform.system() == 'Windows':
                    os.startfile(arg)
                else:
                    subprocess.Popen((command, arg))  # pylint: disable=consider-using-with
            if success_message:
                QMessageBox.information(self, self._title, success_message)
        else:
            if fault_message:
                QMessageBox.warning(self, self._title, fault_message)
            self.statusBar().showMessage('')

    def _show_error_message(self, e: BaseException):
        """Вывод сообщения об ошибке"""
        logger.error('', exc_info=True)
        QMessageBox.critical(self, self._title, f"Ошибка: {e}")

    def _show_yes_no_cancel_message(self, text: str) -> QMessageBox.StandardButton:
        """Вывод сообщения с тремя вариантами ответа Да-Нет-Отмена"""

        self.ui.msg_box.setIcon(QMessageBox.Icon.Question)
        self.ui.msg_box.setWindowTitle(self._title)
        self.ui.msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        self.ui.msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        self.ui.msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
        self.ui.msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
        self.ui.msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
        self.ui.msg_box.setText(text)

        # Возвращаем результат вывода сообщения с тремя вариантами ответа Да-Нет-Отмена
        return self.ui.msg_box.exec()

    def _show_file_overwrite_msg(self, fulename: str) -> QMessageBox.StandardButton:
        """Вывод сообщения о перезаписи файла с четырьмя вариантами ответа Да-Да для всех-Нет-Отмена

        Возвращает: соответствующий вариант QMessageBox.StandardButton
        """
        self.ui.msg_box.setIcon(QMessageBox.Icon.Question)
        self.ui.msg_box.setWindowTitle(self._title)
        self.ui.msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.YesToAll
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        self.ui.msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        self.ui.msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
        self.ui.msg_box.button(QMessageBox.StandardButton.YesToAll).setText('  Да для всех  ')
        self.ui.msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
        self.ui.msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

        self.ui.msg_box.setText(f'Файл \'{fulename}\' уже существует. Перезаписать поверх?')
        return self.ui.msg_box.exec()

    def _show_save_error_msg(self, e: BaseException) -> bool:
        """Вывод сообщения при ошибке сохранения одного файла из серии

        Возвращает True, если пользователь решил продолжать, False - прекратить
        (???может добавить третий вариант - повторить попытку???)
        """
        m_msg_box = QMessageBox(self)
        m_msg_box.setIcon(QMessageBox.Icon.Warning)
        m_msg_box.setWindowTitle(self._title)
        m_msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        m_msg_box.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
        m_msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
        m_msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        m_msg_box.setText(f'Ошибка: {e}\n\nПродолжить процесс сохранения остальных файлов?')
        return m_msg_box.exec() == QMessageBox.StandardButton.Yes

    ###########################################################################
    # Обработчики событий
    ###########################################################################

    def closeEvent(self, event: QCloseEvent):  # pylint: disable=unused-argument
        """Обработчик события Close"""
        logger.info('Выход из приложения...')

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработчик события DragEnter"""

        # Проверяем формат перетаскиваемого объекта
        if event.mimeData().hasFormat('text/uri-list'):
            # Подтверждаем готовность принять объект
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Обработчик события Drop"""

        # Получаем список ссылок
        url_list = event.mimeData().urls()

        # Собираем список подходящих файлов из полученного списка ссылок
        filelist = [
            url.toLocalFile()
            for url in url_list
            if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in const.VALID_EXTENSIONS
        ]

        if not filelist:  # Если список файлов пустой, то выводим сообщение...
            self.statusBar().showMessage('Данный формат файла/файлов не поддерживается!!!')
        elif len(filelist) > 1:  # Если больше одного, то запускаем интерфейс объединения файлов
            self.show_combine_files_dialog(filelist)
        else:  # Запускаем открытие файла
            self.open_or_combine_files(filelist[0])

        # Подтверждаем принятие объекта
        event.acceptProposedAction()

    ###########################################################################
    # Обработчики событий (Слоты QT)
    ###########################################################################

    @Slot()
    def on_actionOpen_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Открыть>"""
        lastfn = params.get_lastfilename()

        directory = os.path.dirname(lastfn)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл PDF",
            directory,
            f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in const.VALID_EXTENSIONS).strip()})",
        )
        if filename:
            self.open_or_combine_files(filename)

    @Slot()
    def on_actionSaveAs_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Сохранить как...>"""
        dlg = SaveAsDialog(self)
        if dlg.exec_():
            self._save_files_process(dlg.params, False)
            self._progress_status_turnoff()

    @Slot()
    def on_actionClose_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Закрыть>"""
        self.pdf_view.close_file()
        self._setup_controls()

    @Slot()
    def on_actionCensore_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Деперсонификация платежных документов КТК>"""
        dlg = CensoreDialog(self)
        if dlg.exec_():
            # Отключаем режим small_glyph_heights, т.к. с ним некорректно определяется положение "КУДА" и "ОТ КОГО"
            fitz.Tools().set_small_glyph_heights(False)

            dlg.params.format = dlg.params.format_censore

            if dlg.params.setselectionsonly:
                self._censore_selections_process(dlg.params)
            else:
                self._save_files_process(dlg.params, True)

            self._progress_status_turnoff()

            # Для наилучшего распознания текстового слоя...
            fitz.Tools().set_small_glyph_heights(True)

    @Slot()
    def on_actionTablesAnalizeStrong_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Поиск таблиц (по рамкам) и экспорт данных
        в XLSX - С учетом структуры найденных таблиц>
        """
        self._tableanalize_process(True)
        self._progress_status_turnoff()

    @Slot()
    def on_actionTablesAnalizeSimple_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Поиск таблиц (по рамкам) и экспорт данных
        в XLSX - Простая шинковка на строки и столбцы>
        """
        self._tableanalize_process(False)
        self._progress_status_turnoff()

    @Slot()
    def on_actionPDexport_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Экспорт реестра платежных документов КТК в XLSX без анализа QR кодов>"""
        self._export_pd_process(False)
        self._progress_status_turnoff()

    @Slot()
    def on_actionPDexportQR_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Экспорт реестра платежных документов КТК в XLSX с анализом QR кодов>"""
        self._export_pd_process(True)
        self._progress_status_turnoff()
