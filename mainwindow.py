"""
Этот файл содержит класс основного окна приложения
"""

import logging
import os
import subprocess
import sys

import fitz
from PySide2.QtCore import Qt
from PySide2.QtCore import QUrl
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

        # Имя текущего файла
        self.current_filename = ''
        # Это настоящий файл (иначе - виртуальный, новый)
        self.is_real_file = False
        # Заголовок для дежурного объекта для вывода сообщений
        self.title = ''

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
        self.pdf_view.rect_selected.connect(self.process_rect_selection)

        # Привязываем обработчик изменения значения зум-фактора и номера страницы в панели инструментов
        self.ui.zoom_selector.zoom_factor_changed.connect(self.pdf_view.set_zoom_factor)
        self.ui.page_selector.valueChanged.connect(self._change_page)

        # Обработчики выбора пункто меню <Создать> и <Выход>
        self.ui.actionNew.triggered.connect(lambda: self.show_combine_files_dialog([]))
        self.ui.actionQuit.triggered.connect(self.close)

        self.ui.actionHome.triggered.connect(self.pdf_view.goto_home)
        self.ui.actionPrevious_Page.triggered.connect(self.pdf_view.goto_prev_page)
        self.ui.actionNext_Page.triggered.connect(self.pdf_view.goto_next_page)
        self.ui.actionEnd.triggered.connect(self.pdf_view.goto_end)

        self.ui.actionZoom_In.triggered.connect(self.pdf_view.zoom_in)
        self.ui.actionZoom_Out.triggered.connect(self.pdf_view.zoom_out)
        self.ui.actionZoom_Normal.triggered.connect(lambda: self.pdf_view.set_zoom_factor(1.0))

        self.ui.actionCbdPageImageCopy.triggered.connect(self.pdf_view.copy_page_image_to_clipboard)
        self.ui.actionCbdRectImageCopy.triggered.connect(self.pdf_view.copy_rect_image_to_clipboard)
        self.ui.actionCbdRectTextCopy.triggered.connect(self.pdf_view.copy_rect_text_to_clipboard)
        self.ui.actionCbdRectTextTrimCopy.triggered.connect(lambda: self.pdf_view.copy_rect_text_to_clipboard(True))
        self.ui.actionRectRecognizeText.triggered.connect(
            lambda: self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, trim=False)
        )
        self.ui.actionRectRecognizeTextTrim.triggered.connect(
            lambda: self.pdf_view.recognize_and_copy_to_clipboard(self._tesseract_cmd, trim=True)
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

    def process_rect_selection(self, selected: bool):
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

    # TODO: упростить
    def open_or_combine_files(self, doc_location, files_list=None):
        """Открыть файл или объединить несколько файлов в один и открыть его"""

        if doc_location == '' or doc_location.isLocalFile():
            if doc_location:
                self.is_real_file = True
                self.current_filename = doc_location.toLocalFile()
                self.pdf_view.open(self.current_filename)
                is_file_opened = self.pdf_view.page_count > 0
            elif files_list is not None:
                self.is_real_file = False
                self.current_filename = '*** Результат объединения файлов ***'
                self.pdf_view.combine(files_list)
                is_file_opened = self.pdf_view.page_count > 0
            else:
                is_file_opened = False

            if is_file_opened:
                self.setWindowTitle(const.APP_TITLE + ' - ' + self.current_filename)
                self.ui.page_selector.setRange(1, self.pdf_view.page_count)
                self.ui.page_selector.setSuffix(f' из {self.pdf_view.page_count}')
                self._change_page(1)
                if self.is_real_file:
                    params.set_lastfilename(self.current_filename)
            else:
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
            self.ui.actionRemoveAllSelections.setEnabled(False)
        else:
            message = f"{doc_location} не является локальным файлом"
            print(message, file=sys.stderr)
            QMessageBox.critical(self, "Открыть не удалось", message)

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
            # noinspection PyTypeChecker
            self.open_or_combine_files('', dlg.get_filelist())

    def _export_pd_process(self, recognize_qr: bool):
        """Экспорт рееста ПД в XLSX"""

        self.title = 'Экспорт рееста ПД в XLSX'

        # Получаем от пользователя имя нового файла
        outfile = self._get_savefilename(
            os.path.dirname(self.current_filename), r'Книга Excel "(*.xlsx)"', '.xlsx', True
        )
        # Имя файла не выбрано
        if not outfile:
            return

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self.title + '...')

        # Запускаем парсинг таблиц на всех страницах документа
        try:
            res = export_pd(
                self.pdf_view.doc, outfile, self.current_filename, recognize_qr, self._progress_status_refresh
            )
        except Exception as e:
            self._show_error_message(e)
            return

        # Отключаем прогресс-бар и разблокируем интерфейс
        self._progress_status_final(res, command=self._xlseditor_cmd, arg=outfile)

    def _tableanalize_process(self, strong: bool):
        """Анализ и разбор табличных данных на всех страницах файла PDF и сохранение их в файл XLSX"""

        self.title = 'Экспорт табличных данных в XLSX'

        # Получаем от пользователя имя нового файла
        outfile = self._get_savefilename(
            os.path.dirname(self.current_filename), r'Книга Excel "(*.xlsx)"', '.xlsx', True
        )
        # Имя файла не выбрано
        if not outfile:
            return

        # Включаем прогресс-бар и блокируем интерфейс
        self._progress_status_start(self.title + '...')

        # Запускаем парсинг таблиц на всех страницах документа
        try:
            rows_count = parse_tables(self.pdf_view.doc, outfile, strong, self._progress_status_refresh)
        except Exception as e:
            self._show_error_message(e)
            return

        # Отключаем прогресс-бар и разблокируем интерфейс
        self._progress_status_final(
            rows_count > 0,
            command=self._xlseditor_cmd,
            arg=outfile,
            fault_message='Табличные данные найти не удалось...',
        )

    def _get_savefilename(self, file_dir: str, file_filter: str, file_ext: str, file_delete: bool = False) -> str:
        """Диалог выбора имени файла для сохранения"""
        outfile, _ = QFileDialog.getSaveFileName(self, self.title, file_dir, file_filter)
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
                subprocess.Popen((command, arg))  # pylint: disable=consider-using-with
            if success_message:
                QMessageBox.information(self, self.title, success_message)
        else:
            if fault_message:
                QMessageBox.warning(self, self.title, fault_message)
            self.statusBar().showMessage('')

    def _show_error_message(self, e: BaseException):
        """Вывод сообщения об ошибке"""
        logger.error('', exc_info=True)
        QMessageBox.critical(self, self.title, f"Ошибка: {e}")

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
        # Если больше одной, то обрабатываем список
        if len(url_list) > 1:
            # Собираем список подходящих файлов из полученного списка ссылок
            filelist = [
                url.toLocalFile()
                for url in url_list
                if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in const.VALID_EXTENSIONS
            ]
            # Если список файлов непустой, запускаем интерфейс объединения файлов
            if filelist:
                self.show_combine_files_dialog(filelist)
        else:
            # Если это правильная ссылка, запускаем открытие файла
            to_open = url_list[0]
            if to_open.isValid():
                self.open_or_combine_files(to_open)

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
        to_open, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл PDF",
            directory,
            f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in const.VALID_EXTENSIONS).strip()})",
        )
        if to_open:
            self.open_or_combine_files(QUrl.fromLocalFile(to_open))

    @Slot()
    def on_actionClose_triggered(self):  # pylint: disable=invalid-name
        """Обработчик выбора пункта меню <Закрыть>"""
        self.pdf_view.close()
        # noinspection PyTypeChecker
        self.open_or_combine_files('')

    @Slot()
    def on_actionSaveAs_triggered(self):  # pylint: disable=invalid-name
        dlg = SaveAsDialog(self)
        if dlg.exec_():
            saveas_process(self, dlg.params, False)
            self._progress_status_turnoff()

    @Slot()
    def on_actionCensore_triggered(self):  # pylint: disable=invalid-name
        dlg = CensoreDialog(self)
        if dlg.exec_():
            # Отключаем режим small_glyph_heights, т.к. с ним некорректно определяется положение "КУДА" и "ОТ КОГО"
            fitz.Tools().set_small_glyph_heights(False)

            dlg.params.format = dlg.params.format_censore
            saveas_process(self, dlg.params, True)
            self._progress_status_turnoff()

            # Для наилучшего распознания текстового слоя...
            fitz.Tools().set_small_glyph_heights(True)

    @Slot()
    def on_actionTablesAnalizeStrong_triggered(self):  # pylint: disable=invalid-name
        self._tableanalize_process(True)
        self._progress_status_turnoff()

    @Slot()
    def on_actionTablesAnalizeSimple_triggered(self):  # pylint: disable=invalid-name
        self._tableanalize_process(False)
        self._progress_status_turnoff()

    @Slot()
    def on_actionPDexport_triggered(self):  # pylint: disable=invalid-name
        self._export_pd_process(False)
        self._progress_status_turnoff()

    @Slot()
    def on_actionPDexportQR_triggered(self):  # pylint: disable=invalid-name
        self._export_pd_process(True)
        self._progress_status_turnoff()
