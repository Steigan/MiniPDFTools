from PySide2.QtCore import QRegularExpression
from PySide2.QtCore import Slot
from PySide2.QtGui import QRegularExpressionValidator
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QDialogButtonBox

from params import FileFormat
from params import PageMode
from params import PageRotation
from params import SaveParams
from saveas_ui import Ui_SaveAsDialog


class SaveAsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_SaveAsDialog()
        self.ui.setupUi(self)

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save)

        self.m_current_params = SaveParams()
        # self.m_currentParams.load_params()

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setText('Сохранить')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('Отмена')

        if self.m_current_params.format == FileFormat.FMT_PDF:
            self.ui.rbtPDF.setChecked(True)
        elif self.m_current_params.format == FileFormat.FMT_PDF_JPEG:
            self.ui.rbtPDFjpeg.setChecked(True)
        elif self.m_current_params.format == FileFormat.FMT_JPEG:
            self.ui.rbtJPEG.setChecked(True)
        else:
            self.ui.rbtPNG.setChecked(True)
        self.format_checked(self.m_current_params.format)

        if self.m_current_params.pgmode == PageMode.PG_ALL:
            self.ui.rbtPgAll.setChecked(True)
        elif self.m_current_params.pgmode == PageMode.PG_CURRENT:
            self.ui.rbtPgCurr.setChecked(True)
        else:
            self.ui.rbtPgRange.setChecked(True)
        self.pagemode_checked(self.m_current_params.pgmode)

        self.ui.edtPages.setText(self.m_current_params.pgrange)
        self.ui.edtPages.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9,-]*')))
        self.ui.chkSingles.setChecked(self.m_current_params.singles)

        self.rotation_checked(self.m_current_params.rotation)

        self.ui.cmbDPI.setCurrentText(str(self.m_current_params.dpi))
        self.ui.SliderQuality.setValue(self.m_current_params.quality)

        # self.ui.chkCensore.setChecked(self.m_currentParams.censore)
        self.ui.cmbCensore.setCurrentIndex(self.m_current_params.censore)

        self.resize(self.minimumSizeHint())

    ############################################
    # Свойство класса с выбранными параметрами
    def params(self):
        return self.m_current_params

    def update_params(self):
        self.m_current_params.pgrange = self.ui.edtPages.text()
        self.m_current_params.singles = self.ui.chkSingles.isChecked()
        self.m_current_params.dpi = int(self.ui.cmbDPI.currentText())
        self.m_current_params.quality = self.ui.SliderQuality.value()
        # self.m_currentParams.censore = self.ui.chkCensore.isChecked()
        self.m_current_params.censore = self.ui.cmbCensore.currentIndex()

    @Slot()
    def save(self):
        '''Обработка нажатия кнопки "Сохранить"'''
        self.update_params()
        self.m_current_params.save_params()
        # print(self.m_currentParams)
        self.hide()

    def format_checked(self, m_format):
        '''Обработка выбора формата файла/файлов'''
        self.m_current_params.format = m_format

        fl_pdf = m_format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG)
        self.ui.chkSingles.setEnabled(fl_pdf and self.m_current_params.pgmode != PageMode.PG_CURRENT)
        # self.ui.btnOriginal.setEnabled(fl_pdf)
        # self.ui.btnLeft.setEnabled(fl_pdf)
        # self.ui.btnRight.setEnabled(fl_pdf)
        # self.ui.btn180dg.setEnabled(fl_pdf)

        fl_dpi = m_format in (FileFormat.FMT_PDF_JPEG, FileFormat.FMT_JPEG, FileFormat.FMT_PNG)
        self.ui.lblDPI.setEnabled(fl_dpi)
        self.ui.cmbDPI.setEnabled(fl_dpi)
        self.ui.cmbCensore.setEnabled(fl_dpi)

        fl_qual = m_format in (FileFormat.FMT_PDF_JPEG, FileFormat.FMT_JPEG)
        self.ui.lblQuality.setEnabled(fl_qual)
        self.ui.SliderQuality.setEnabled(fl_qual)
        self.ui.lblQualityVal.setEnabled(fl_qual)

    @Slot()
    def on_rbtPDF_clicked(self):  # pylint: disable=invalid-name
        self.format_checked(FileFormat.FMT_PDF)

    @Slot()
    def on_rbtPDFjpeg_clicked(self):  # pylint: disable=invalid-name
        self.format_checked(FileFormat.FMT_PDF_JPEG)

    @Slot()
    def on_rbtJPEG_clicked(self):  # pylint: disable=invalid-name
        self.format_checked(FileFormat.FMT_JPEG)

    @Slot()
    def on_rbtPNG_clicked(self):  # pylint: disable=invalid-name
        self.format_checked(FileFormat.FMT_PNG)

    ############################################
    # Обработка выбора формата файла/файлов
    def pagemode_checked(self, m_pgmode):
        self.m_current_params.pgmode = m_pgmode

        fl_rng = m_pgmode == PageMode.PG_RANGE
        self.ui.lblPg.setEnabled(fl_rng)
        self.ui.edtPages.setEnabled(fl_rng)
        self.ui.chkSingles.setEnabled(
            self.m_current_params.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG)
            and m_pgmode != PageMode.PG_CURRENT
        )

    @Slot()
    def on_rbtPgAll_clicked(self):  # pylint: disable=invalid-name
        self.pagemode_checked(PageMode.PG_ALL)

    @Slot()
    def on_rbtPgCurr_clicked(self):  # pylint: disable=invalid-name
        self.pagemode_checked(PageMode.PG_CURRENT)

    @Slot()
    def on_rbtPgRange_clicked(self):  # pylint: disable=invalid-name
        self.pagemode_checked(PageMode.PG_RANGE)

    ############################################
    # Обработка выбора вращения страниц
    def rotation_checked(self, m_rotation):
        self.m_current_params.rotation = m_rotation
        self.ui.btnOriginal.setChecked(m_rotation == PageRotation.RT_NONE)
        self.ui.btnLeft.setChecked(m_rotation == PageRotation.RT_LEFT)
        self.ui.btnRight.setChecked(m_rotation == PageRotation.RT_RIGHT)
        self.ui.btn180dg.setChecked(m_rotation == PageRotation.RT_180)

    @Slot()
    def on_btnOriginal_clicked(self):  # pylint: disable=invalid-name
        self.rotation_checked(PageRotation.RT_NONE)

    @Slot()
    def on_btnLeft_clicked(self):  # pylint: disable=invalid-name
        self.rotation_checked(PageRotation.RT_LEFT)

    @Slot()
    def on_btnRight_clicked(self):  # pylint: disable=invalid-name
        self.rotation_checked(PageRotation.RT_RIGHT)

    @Slot()
    def on_btn180dg_clicked(self):  # pylint: disable=invalid-name
        self.rotation_checked(PageRotation.RT_180)
