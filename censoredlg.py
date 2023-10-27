"""
Этот файл содержит класс диалога настройки параметров деперсонификации документа
и настройки параметров сохранения файла/файлов
"""

from PySide2.QtCore import QRegularExpression
from PySide2.QtCore import Slot
from PySide2.QtGui import QRegularExpressionValidator
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QDialogButtonBox

from censore_ui import Ui_CensoreDialog
from params import CensoreMode
from params import FileFormat
from params import PageMode
from params import SaveParams


class CensoreDialog(QDialog):
    """Диалог настройки параметров деперсонификации и сохранения файла/файлов"""

    def __init__(self, parent=None):
        # Инициализируем интерфейс на основе автокода QT
        super().__init__(parent)
        self.ui = Ui_CensoreDialog()
        self.ui.setupUi(self)

        # Меняем надписи кнопок
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('  Только выделить области  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setText('  Сохранить как новый файл  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('  Отмена  ')

        # Подключаем обработчики нажатий кнопок
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self._select_areas)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._save_censored)

        # Загружаем параметры сохранения файла/файлов
        self._current_params = SaveParams()

        # Настраиваем элементы интерфейса на основе загруженных параметров
        # -- формат выходного файла/файлов
        if self._current_params.format_censore == FileFormat.FMT_PDF:
            self._current_params.format_censore = FileFormat.FMT_PDF_JPEG
        if self._current_params.format_censore == FileFormat.FMT_PDF_JPEG:
            self.ui.rbtPDFjpeg.setChecked(True)
        elif self._current_params.format_censore == FileFormat.FMT_JPEG:
            self.ui.rbtJPEG.setChecked(True)
        else:
            self.ui.rbtPNG.setChecked(True)
        self._format_checked(self._current_params.format_censore)

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
        self._current_params.censore = CensoreMode.CM_BLUR
        self.ui.cmbCensore.setCurrentIndex(self._current_params.censore.value)

        # -- элементы для деперсонификации данных в выделенных областях
        self.ui.chkFIO.setChecked(self._current_params.censore_fio)
        self.ui.chkAddr.setChecked(self._current_params.censore_addr)
        self.ui.chkPost.setChecked(self._current_params.censore_post)
        self.ui.chkIPU.setChecked(self._current_params.censore_ipu)
        self.ui.chkQR.setChecked(self._current_params.censore_qr)

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

        self._current_params.censore_fio = self.ui.chkFIO.isChecked()
        self._current_params.censore_addr = self.ui.chkAddr.isChecked()
        self._current_params.censore_post = self.ui.chkPost.isChecked()
        self._current_params.censore_ipu = self.ui.chkIPU.isChecked()
        self._current_params.censore_qr = self.ui.chkQR.isChecked()

    def _format_checked(self, m_format: FileFormat):
        """Обработка выбора формата файла/файлов"""

        # Синхронизируем соответствующий параметр
        self._current_params.format_censore = m_format

        # Переключаем доступность чекбокса "сохранять страницы в отдельные файлы"
        self.ui.chkSingles.setEnabled(
            m_format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG)
            and self._current_params.pgmode != PageMode.PG_CURRENT
        )

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
            self._current_params.format_censore == FileFormat.FMT_PDF_JPEG and m_pgmode != PageMode.PG_CURRENT
        )

    def _select_areas(self):
        """Обработка нажатия кнопки <Только выделить области> (<OK>)"""

        # Обновляем прочие параметры на основании значений элементов интерфейса
        self._update_other_params()
        # Сохраняем параметры в реестре
        self._current_params.save_params()
        # Устанавливаем флаг "Только выделить области"
        self._current_params.setselectionsonly = True
        # Закрываем окно диалога
        self.hide()

    def _save_censored(self):
        """Обработка нажатия кнопки <Сохранить как новый файл> (<Сохранить>)"""

        # Обновляем прочие параметры на основании значений элементов интерфейса
        self._update_other_params()
        # Сохраняем параметры в реестре
        self._current_params.save_params()
        # Закрываем окно диалога
        self.hide()

    ###########################################################################
    # Обработчики событий QT
    ###########################################################################

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

    @Slot(int)
    def on_cmbCensore_currentIndexChanged(self, newvalue: int):  # pylint: disable=invalid-name
        """Обработчик выбора нового элемента в комбобоксе cmbCensore"""
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setEnabled(newvalue > 0)
