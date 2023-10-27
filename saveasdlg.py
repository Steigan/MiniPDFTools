"""
Этот файл содержит класс диалога настройки параметров сохранения файла/файлов
"""

from PySide2.QtCore import QRegularExpression
from PySide2.QtCore import Slot
from PySide2.QtGui import QRegularExpressionValidator
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QDialogButtonBox

from params import CensoreMode
from params import FileFormat
from params import PageMode
from params import SaveParams
from saveas_ui import Ui_SaveAsDialog


class SaveAsDialog(QDialog):
    """Диалог настройки параметров сохранения файла/файлов"""

    def __init__(self, parent=None):
        # Инициализируем интерфейс на основе автокода QT
        super().__init__(parent)
        self.ui = Ui_SaveAsDialog()
        self.ui.setupUi(self)

        # Меняем надписи кнопок
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setText('Сохранить')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('Отмена')

        # Загружаем параметры сохранения файла/файлов
        self._current_params = SaveParams()

        # Настраиваем элементы интерфейса на основе загруженных параметров
        # -- формат выходного файла/файлов
        if self._current_params.format == FileFormat.FMT_PDF:
            self.ui.rbtPDF.setChecked(True)
        elif self._current_params.format == FileFormat.FMT_PDF_JPEG:
            self.ui.rbtPDFjpeg.setChecked(True)
        elif self._current_params.format == FileFormat.FMT_JPEG:
            self.ui.rbtJPEG.setChecked(True)
        else:
            self.ui.rbtPNG.setChecked(True)
        self._format_checked(self._current_params.format)

        # -- выбор страниц для сохранения
        if self._current_params.pgmode == PageMode.PG_ALL:
            self.ui.rbtPgAll.setChecked(True)
        elif self._current_params.pgmode == PageMode.PG_CURRENT:
            self.ui.rbtPgCurr.setChecked(True)
        else:
            self.ui.rbtPgRange.setChecked(True)
        self._pagemode_checked(self._current_params.pgmode)

        # -- диапазон страниц для сохранения
        self.ui.edtPages.setText(self._current_params.pgrange)
        self.ui.edtPages.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9,-]*')))
        # -- чекбокс "сохранять страницы в отдельные файлы"
        self.ui.chkSingles.setChecked(self._current_params.singles)

        # -- DPI и качество создаваемых файлов в графических форматах
        self.ui.cmbDPI.setCurrentText(str(self._current_params.dpi))
        self.ui.SliderQuality.setValue(self._current_params.quality)

        # -- порядок деперсонификации данных в выделенных областях
        self.ui.cmbCensore.setCurrentIndex(self._current_params.censore.value)

        # Уменьшаем размер диалогового окна до минимально необходимого
        self.resize(self.minimumSizeHint())

    @property
    def params(self):
        """Параметры сохранения файла/файлов, указанные пользователем"""
        return self._current_params

    def _update_other_params(self):
        """Обновить прочие параметры на основании значений элементов интерфейса
        (для элементов, не имеющих своего обработчика)
        """
        self._current_params.pgrange = self.ui.edtPages.text()
        self._current_params.singles = self.ui.chkSingles.isChecked()
        self._current_params.dpi = int(self.ui.cmbDPI.currentText())
        self._current_params.quality = self.ui.SliderQuality.value()
        self._current_params.censore = CensoreMode(self.ui.cmbCensore.currentIndex())

    def _format_checked(self, m_format: FileFormat):
        """Обработка выбора формата файла/файлов"""

        # Синхронизируем соответствующий параметр
        self._current_params.format = m_format

        # Переключаем доступность чекбокса "сохранять страницы в отдельные файлы"
        self.ui.chkSingles.setEnabled(
            m_format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG)
            and self._current_params.pgmode != PageMode.PG_CURRENT
        )

        # Переключаем доступность поля ввода DPI и "цензуры"
        is_dpi = m_format in (FileFormat.FMT_PDF_JPEG, FileFormat.FMT_JPEG, FileFormat.FMT_PNG)
        self.ui.lblDPI.setEnabled(is_dpi)
        self.ui.cmbDPI.setEnabled(is_dpi)
        self.ui.cmbCensore.setEnabled(is_dpi)

        # Переключаем доступность поля ввода качества изображения
        is_quality = m_format in (FileFormat.FMT_PDF_JPEG, FileFormat.FMT_JPEG)
        self.ui.lblQuality.setEnabled(is_quality)
        self.ui.SliderQuality.setEnabled(is_quality)
        self.ui.lblQualityVal.setEnabled(is_quality)

    def _pagemode_checked(self, m_pgmode: PageMode):
        """Обработка выбора формата файла/файлов"""

        # Синхронизируем соответствующий параметр
        self._current_params.pgmode = m_pgmode

        # Переключаем доступность поля ввода диапазона страниц
        is_range = m_pgmode == PageMode.PG_RANGE
        self.ui.lblPg.setEnabled(is_range)
        self.ui.edtPages.setEnabled(is_range)

        # Переключаем доступность чекбокса "сохранять страницы в отдельные файлы"
        self.ui.chkSingles.setEnabled(
            self._current_params.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG)
            and m_pgmode != PageMode.PG_CURRENT
        )

    ###########################################################################
    # Обработчики событий QT
    ###########################################################################

    @Slot()
    def on_SaveAsDialog_accepted(self):  # pylint: disable=invalid-name
        """Обработка нажатия кнопки <Сохранить>"""

        # Обновляем прочие параметры на основании значений элементов интерфейса
        self._update_other_params()
        # Сохраняем параметры в реестре
        self._current_params.save_params()
        # Закрываем окно диалога
        self.hide()

    @Slot()
    def on_rbtPDF_clicked(self):  # pylint: disable=invalid-name
        self._format_checked(FileFormat.FMT_PDF)

    @Slot()
    def on_rbtPDFjpeg_clicked(self):  # pylint: disable=invalid-name
        self._format_checked(FileFormat.FMT_PDF_JPEG)

    @Slot()
    def on_rbtJPEG_clicked(self):  # pylint: disable=invalid-name
        self._format_checked(FileFormat.FMT_JPEG)

    @Slot()
    def on_rbtPNG_clicked(self):  # pylint: disable=invalid-name
        self._format_checked(FileFormat.FMT_PNG)

    @Slot()
    def on_rbtPgAll_clicked(self):  # pylint: disable=invalid-name
        self._pagemode_checked(PageMode.PG_ALL)

    @Slot()
    def on_rbtPgCurr_clicked(self):  # pylint: disable=invalid-name
        self._pagemode_checked(PageMode.PG_CURRENT)

    @Slot()
    def on_rbtPgRange_clicked(self):  # pylint: disable=invalid-name
        self._pagemode_checked(PageMode.PG_RANGE)
