from PySide2.QtWidgets import (QDialog, QFileDialog, QMessageBox, QDialogButtonBox)
from PySide2.QtCore import Signal, Slot, QSettings, QRegularExpression
from PySide2.QtGui import QRegularExpressionValidator
from saveas_ui import Ui_SaveAsDialog
import enum

class FileFormat(enum.IntEnum):
    fmtPDF = 0
    fmtPDFjpeg = 1
    fmtJPEG = 2
    fmtPNG = 3

class PageMode(enum.IntEnum):
    pgAll = 0
    pgCurrent = 1
    pgRange = 2

class PageRotation(enum.IntEnum):
    rtNone = 0
    rtLeft = 1
    rtRight = 2
    rt180 = 3

class SaveParams():
    def __init__(self):
        # self.format = FileFormat.fmtPDFjpeg
        # self.pgmode = PageMode.pgCurrent
        # self.pgrange = "1-10,1"
        # self.dpi = 300
        # self.quality = 80
        # self.singles = True

        settings = QSettings('Steigan', 'Mini PDF Tools')

        # self.format = settings.value('format', FileFormat.fmtPDF)
        # self.pgmode = settings.value('pgmode', PageMode.pgAll)
        try:
            self.format = FileFormat(int(settings.value('format', '0')))
            self.format_censore = FileFormat(int(settings.value('format_censore', '0')))
            self.pgmode = PageMode(int(settings.value('pgmode', '0')))
            # self.rotation = PageRotation(int(settings.value('rotation', '0')))
            self.rotation = PageRotation.rtNone
        except:
            self.format = FileFormat.fmtPDF
            self.format_censore = FileFormat.fmtPDFjpeg
            self.pgmode = PageMode.pgAll
            self.rotation = PageRotation.rtNone

        self.pgrange = settings.value('pgrange', "")
        self.dpi = settings.value('dpi', '300')
        self.quality = int(settings.value('quality', '75'))
        self.singles = self.valueToBool(settings.value('singles', False))

        self.censoreFIO = self.valueToBool(settings.value('censoreFIO', True))
        self.censoreAddr = self.valueToBool(settings.value('censoreAddr', True))
        self.censorePost = self.valueToBool(settings.value('censorePost', True))
        self.censoreIPU = self.valueToBool(settings.value('censoreIPU', True))
        self.censoreQR = self.valueToBool(settings.value('censoreQR', True))

        self.censore = 0
        # self.valueToBool(settings.value('censore', False))
        self.setselectionsonly = False
        
    # def load_params(self):
    #     pass

    def save_params(self):
        settings = QSettings('Steigan', 'Mini PDF Tools')
        settings.setValue('format', str(self.format.value))
        settings.setValue('format_censore', str(self.format_censore.value))
        settings.setValue('pgmode', str(self.pgmode.value))
        settings.setValue('rotation', str(self.rotation.value))
        settings.setValue('pgrange', self.pgrange)
        settings.setValue('dpi', self.dpi)
        settings.setValue('quality', str(self.quality))
        settings.setValue('singles', str(self.singles))

        settings.setValue('censoreFIO', str(self.censoreFIO))
        settings.setValue('censoreAddr', str(self.censoreAddr))
        settings.setValue('censorePost', str(self.censorePost))
        settings.setValue('censoreIPU', str(self.censoreIPU))
        settings.setValue('censoreQR', str(self.censoreQR))

        # settings.setValue('censore', str(self.censore))

    @staticmethod
    def valueToBool(value):
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

class SaveAsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_SaveAsDialog()
        self.ui.setupUi(self)

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save)

        self.m_currentParams = SaveParams()
        # self.m_currentParams.load_params()
        
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Save).setText('Сохранить')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('Отмена')
        
        if self.m_currentParams.format == FileFormat.fmtPDF:
            self.ui.rbtPDF.setChecked(True)
        elif self.m_currentParams.format == FileFormat.fmtPDFjpeg:
            self.ui.rbtPDFjpeg.setChecked(True)
        elif self.m_currentParams.format == FileFormat.fmtJPEG:
            self.ui.rbtJPEG.setChecked(True)
        else:
            self.ui.rbtPNG.setChecked(True)
        self.format_checked(self.m_currentParams.format)

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

        # self.ui.chkCensore.setChecked(self.m_currentParams.censore)
        self.ui.cmbCensore.setCurrentIndex(self.m_currentParams.censore)
        
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
        # self.m_currentParams.censore = self.ui.chkCensore.isChecked()
        self.m_currentParams.censore = self.ui.cmbCensore.currentIndex()

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
        self.m_currentParams.format = m_format

        fl_pdf = m_format in (FileFormat.fmtPDF, FileFormat.fmtPDFjpeg)
        self.ui.chkSingles.setEnabled(fl_pdf and self.m_currentParams.pgmode != PageMode.pgCurrent)
        # self.ui.btnOriginal.setEnabled(fl_pdf)
        # self.ui.btnLeft.setEnabled(fl_pdf)
        # self.ui.btnRight.setEnabled(fl_pdf)
        # self.ui.btn180dg.setEnabled(fl_pdf)

        fl_dpi = m_format in (FileFormat.fmtPDFjpeg, FileFormat.fmtJPEG, FileFormat.fmtPNG)
        self.ui.lblDPI.setEnabled(fl_dpi)
        self.ui.cmbDPI.setEnabled(fl_dpi)
        self.ui.cmbCensore.setEnabled(fl_dpi)

        fl_qual = m_format in (FileFormat.fmtPDFjpeg, FileFormat.fmtJPEG)
        self.ui.lblQuality.setEnabled(fl_qual)
        self.ui.SliderQuality.setEnabled(fl_qual)
        self.ui.lblQualityVal.setEnabled(fl_qual)

    @Slot()
    def on_rbtPDF_clicked(self):
        self.format_checked(FileFormat.fmtPDF)

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
        self.ui.chkSingles.setEnabled(self.m_currentParams.format in (FileFormat.fmtPDF, FileFormat.fmtPDFjpeg) \
            and m_pgmode != PageMode.pgCurrent)

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
