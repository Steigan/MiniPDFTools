from PySide2.QtCore import QRegularExpression
from PySide2.QtCore import Slot
from PySide2.QtGui import QRegularExpressionValidator
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QDialogButtonBox

from censore_ui import Ui_CensoreDialog
from saveasdlg import FileFormat
from saveasdlg import PageMode
from saveasdlg import PageRotation
from saveasdlg import SaveParams


class CensoreDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_CensoreDialog()
        self.ui.setupUi(self)

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.ok)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save)

        self.m_currentParams = SaveParams()
        # self.m_currentParams.load_params()

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('  Только выделить области  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setText('  Сохранить как новый файл  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('  Отмена  ')

        if self.m_currentParams.format_censore == FileFormat.fmtPDF:
            self.m_currentParams.format_censore = FileFormat.fmtPDFjpeg
        if self.m_currentParams.format_censore == FileFormat.fmtPDFjpeg:
            self.ui.rbtPDFjpeg.setChecked(True)
        elif self.m_currentParams.format_censore == FileFormat.fmtJPEG:
            self.ui.rbtJPEG.setChecked(True)
        else:
            self.ui.rbtPNG.setChecked(True)
        self.format_checked(self.m_currentParams.format_censore)

        if self.m_currentParams.pgmode == PageMode.pgAll:
            self.ui.rbtPgAll.setChecked(True)
        elif self.m_currentParams.pgmode == PageMode.pgCurrent:
            self.ui.rbtPgCurr.setChecked(True)
        else:
            self.ui.rbtPgRange.setChecked(True)
        self.pagemode_checked(self.m_currentParams.pgmode)

        self.ui.edtPages.setText(self.m_currentParams.pgrange)
        self.ui.edtPages.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9,-]*')))
        self.ui.chkSingles.setChecked(self.m_currentParams.singles)

        self.rotation_checked(self.m_currentParams.rotation)

        self.ui.cmbDPI.setCurrentText(str(self.m_currentParams.dpi))
        self.ui.SliderQuality.setValue(self.m_currentParams.quality)

        self.ui.chkFIO.setChecked(self.m_currentParams.censoreFIO)
        self.ui.chkAddr.setChecked(self.m_currentParams.censoreAddr)
        self.ui.chkPost.setChecked(self.m_currentParams.censorePost)
        self.ui.chkIPU.setChecked(self.m_currentParams.censoreIPU)
        self.ui.chkQR.setChecked(self.m_currentParams.censoreQR)

        self.resize(self.minimumSizeHint())

    ############################################
    # Свойство класса с выбранными параметрами
    def params(self):
        return self.m_currentParams

    def update_params(self):
        self.m_currentParams.pgrange = self.ui.edtPages.text()
        self.m_currentParams.singles = self.ui.chkSingles.isChecked()
        self.m_currentParams.dpi = int(self.ui.cmbDPI.currentText())
        self.m_currentParams.quality = self.ui.SliderQuality.value()

        self.m_currentParams.censoreFIO = self.ui.chkFIO.isChecked()
        self.m_currentParams.censoreAddr = self.ui.chkAddr.isChecked()
        self.m_currentParams.censorePost = self.ui.chkPost.isChecked()
        self.m_currentParams.censoreIPU = self.ui.chkIPU.isChecked()
        self.m_currentParams.censoreQR = self.ui.chkQR.isChecked()

    ############################################
    # Обработка нажатия кнопки "OK"
    @Slot()
    def ok(self):
        self.update_params()
        self.m_currentParams.save_params()
        self.m_currentParams.setselectionsonly = True
        self.hide()

    ############################################
    # Обработка нажатия кнопки "Сохранить"
    @Slot()
    def save(self):
        self.update_params()
        self.m_currentParams.save_params()
        # print(self.m_currentParams)
        self.hide()

    ############################################
    # Обработка выбора формата файла/файлов
    def format_checked(self, m_format):
        self.m_currentParams.format_censore = m_format

        fl_pdf = m_format in (FileFormat.fmtPDF, FileFormat.fmtPDFjpeg)
        self.ui.chkSingles.setEnabled(fl_pdf and self.m_currentParams.pgmode != PageMode.pgCurrent)

        fl_dpi = m_format in (FileFormat.fmtPDFjpeg, FileFormat.fmtJPEG, FileFormat.fmtPNG)
        self.ui.lblDPI.setEnabled(fl_dpi)
        self.ui.cmbDPI.setEnabled(fl_dpi)

        fl_qual = m_format in (FileFormat.fmtPDFjpeg, FileFormat.fmtJPEG)
        self.ui.lblQuality.setEnabled(fl_qual)
        self.ui.SliderQuality.setEnabled(fl_qual)
        self.ui.lblQualityVal.setEnabled(fl_qual)

    @Slot()
    def on_rbtPDFjpeg_clicked(self):
        self.format_checked(FileFormat.fmtPDFjpeg)

    @Slot()
    def on_rbtJPEG_clicked(self):
        self.format_checked(FileFormat.fmtJPEG)

    @Slot()
    def on_rbtPNG_clicked(self):
        self.format_checked(FileFormat.fmtPNG)

    ############################################
    # Обработка выбора формата файла/файлов
    def pagemode_checked(self, m_pgmode):
        self.m_currentParams.pgmode = m_pgmode

        fl_rng = m_pgmode == PageMode.pgRange
        self.ui.lblPg.setEnabled(fl_rng)
        self.ui.edtPages.setEnabled(fl_rng)
        self.ui.chkSingles.setEnabled(
            self.m_currentParams.format_censore in (FileFormat.fmtPDF, FileFormat.fmtPDFjpeg)
            and m_pgmode != PageMode.pgCurrent
        )

    @Slot()
    def on_rbtPgAll_clicked(self):
        self.pagemode_checked(PageMode.pgAll)

    @Slot()
    def on_rbtPgCurr_clicked(self):
        self.pagemode_checked(PageMode.pgCurrent)

    @Slot()
    def on_rbtPgRange_clicked(self):
        self.pagemode_checked(PageMode.pgRange)

    ############################################
    # Обработка выбора вращения страниц
    def rotation_checked(self, m_rotation):
        self.m_currentParams.rotation = m_rotation
        self.ui.btnOriginal.setChecked(m_rotation == PageRotation.rtNone)
        self.ui.btnLeft.setChecked(m_rotation == PageRotation.rtLeft)
        self.ui.btnRight.setChecked(m_rotation == PageRotation.rtRight)
        self.ui.btn180dg.setChecked(m_rotation == PageRotation.rt180)

    @Slot()
    def on_btnOriginal_clicked(self):
        self.rotation_checked(PageRotation.rtNone)

    @Slot()
    def on_btnLeft_clicked(self):
        self.rotation_checked(PageRotation.rtLeft)

    @Slot()
    def on_btnRight_clicked(self):
        self.rotation_checked(PageRotation.rtRight)

    @Slot()
    def on_btn180dg_clicked(self):
        self.rotation_checked(PageRotation.rt180)
