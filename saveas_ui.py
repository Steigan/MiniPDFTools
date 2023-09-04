# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'saveas.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

import resources_rc

class Ui_SaveAsDialog(object):
    def setupUi(self, SaveAsDialog):
        if not SaveAsDialog.objectName():
            SaveAsDialog.setObjectName(u"SaveAsDialog")
        SaveAsDialog.resize(694, 426)
        icon = QIcon()
        icon.addFile(u":/icons/images/Paomedia-Small-N-Flat-Floppy.svg", QSize(), QIcon.Normal, QIcon.Off)
        SaveAsDialog.setWindowIcon(icon)
        SaveAsDialog.setModal(True)
        self.verticalLayout = QVBoxLayout(SaveAsDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.grpFormat = QGroupBox(SaveAsDialog)
        self.grpFormat.setObjectName(u"grpFormat")
        self.grpFormat.setMaximumSize(QSize(16777215, 80))
        self.verticalLayout_3 = QVBoxLayout(self.grpFormat)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.horizontalLayout1 = QHBoxLayout()
        self.horizontalLayout1.setSpacing(15)
        self.horizontalLayout1.setObjectName(u"horizontalLayout1")
        self.rbtPDF = QRadioButton(self.grpFormat)
        self.rbtPDF.setObjectName(u"rbtPDF")

        self.horizontalLayout1.addWidget(self.rbtPDF)

        self.rbtPDFjpeg = QRadioButton(self.grpFormat)
        self.rbtPDFjpeg.setObjectName(u"rbtPDFjpeg")

        self.horizontalLayout1.addWidget(self.rbtPDFjpeg)

        self.rbtJPEG = QRadioButton(self.grpFormat)
        self.rbtJPEG.setObjectName(u"rbtJPEG")

        self.horizontalLayout1.addWidget(self.rbtJPEG)

        self.rbtPNG = QRadioButton(self.grpFormat)
        self.rbtPNG.setObjectName(u"rbtPNG")
        self.rbtPNG.setChecked(True)

        self.horizontalLayout1.addWidget(self.rbtPNG)


        self.verticalLayout_3.addLayout(self.horizontalLayout1)


        self.verticalLayout.addWidget(self.grpFormat)

        self.grpPages = QGroupBox(SaveAsDialog)
        self.grpPages.setObjectName(u"grpPages")
        self.verticalLayout_2 = QVBoxLayout(self.grpPages)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout2 = QHBoxLayout()
        self.horizontalLayout2.setSpacing(15)
        self.horizontalLayout2.setObjectName(u"horizontalLayout2")
        self.rbtPgAll = QRadioButton(self.grpPages)
        self.rbtPgAll.setObjectName(u"rbtPgAll")

        self.horizontalLayout2.addWidget(self.rbtPgAll)

        self.rbtPgCurr = QRadioButton(self.grpPages)
        self.rbtPgCurr.setObjectName(u"rbtPgCurr")

        self.horizontalLayout2.addWidget(self.rbtPgCurr)

        self.rbtPgRange = QRadioButton(self.grpPages)
        self.rbtPgRange.setObjectName(u"rbtPgRange")
        self.rbtPgRange.setChecked(True)

        self.horizontalLayout2.addWidget(self.rbtPgRange)

        self.horizontalLayout2.setStretch(0, 2)
        self.horizontalLayout2.setStretch(1, 3)

        self.verticalLayout_2.addLayout(self.horizontalLayout2)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.lblPg = QLabel(self.grpPages)
        self.lblPg.setObjectName(u"lblPg")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.lblPg)

        self.edtPages = QLineEdit(self.grpPages)
        self.edtPages.setObjectName(u"edtPages")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.edtPages)


        self.verticalLayout_2.addLayout(self.formLayout)

        self.chkSingles = QCheckBox(self.grpPages)
        self.chkSingles.setObjectName(u"chkSingles")

        self.verticalLayout_2.addWidget(self.chkSingles)


        self.verticalLayout.addWidget(self.grpPages)

        self.grpRotation = QGroupBox(SaveAsDialog)
        self.grpRotation.setObjectName(u"grpRotation")
        self.horizontalLayout_4 = QHBoxLayout(self.grpRotation)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.btnOriginal = QPushButton(self.grpRotation)
        self.btnOriginal.setObjectName(u"btnOriginal")
        icon1 = QIcon()
        icon1.addFile(u":/icons/images/Pictogrammers-Material-File-File-outline.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon1.addFile(u":/icons/images/Pictogrammers-Material-File-File-outline_on.svg", QSize(), QIcon.Normal, QIcon.On)
        self.btnOriginal.setIcon(icon1)
        self.btnOriginal.setIconSize(QSize(20, 20))
        self.btnOriginal.setCheckable(True)

        self.horizontalLayout_4.addWidget(self.btnOriginal)

        self.btnLeft = QPushButton(self.grpRotation)
        self.btnLeft.setObjectName(u"btnLeft")
        icon2 = QIcon()
        icon2.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-down-left-bold.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon2.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-down-left-bold_on.svg", QSize(), QIcon.Normal, QIcon.On)
        self.btnLeft.setIcon(icon2)
        self.btnLeft.setIconSize(QSize(20, 20))
        self.btnLeft.setCheckable(True)
        self.btnLeft.setChecked(True)

        self.horizontalLayout_4.addWidget(self.btnLeft)

        self.btnRight = QPushButton(self.grpRotation)
        self.btnRight.setObjectName(u"btnRight")
        icon3 = QIcon()
        icon3.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-down-right-bold.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon3.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-down-right-bold_on.svg", QSize(), QIcon.Normal, QIcon.On)
        self.btnRight.setIcon(icon3)
        self.btnRight.setIconSize(QSize(20, 20))
        self.btnRight.setCheckable(True)

        self.horizontalLayout_4.addWidget(self.btnRight)

        self.btn180dg = QPushButton(self.grpRotation)
        self.btn180dg.setObjectName(u"btn180dg")
        icon4 = QIcon()
        icon4.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-u-left-bottom-bold.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon4.addFile(u":/icons/images/Pictogrammers-Material-Arrow-Arrow-u-left-bottom-bold_on.svg", QSize(), QIcon.Normal, QIcon.On)
        self.btn180dg.setIcon(icon4)
        self.btn180dg.setIconSize(QSize(20, 20))
        self.btn180dg.setCheckable(True)

        self.horizontalLayout_4.addWidget(self.btn180dg)


        self.verticalLayout.addWidget(self.grpRotation)

        self.grpJPEG = QGroupBox(SaveAsDialog)
        self.grpJPEG.setObjectName(u"grpJPEG")
        self.horizontalLayout_3 = QHBoxLayout(self.grpJPEG)
        self.horizontalLayout_3.setSpacing(30)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.formLayout2 = QFormLayout()
        self.formLayout2.setObjectName(u"formLayout2")
        self.formLayout2.setFormAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.formLayout2.setHorizontalSpacing(6)
        self.lblDPI = QLabel(self.grpJPEG)
        self.lblDPI.setObjectName(u"lblDPI")

        self.formLayout2.setWidget(0, QFormLayout.LabelRole, self.lblDPI)

        self.cmbDPI = QComboBox(self.grpJPEG)
        self.cmbDPI.addItem("")
        self.cmbDPI.addItem("")
        self.cmbDPI.addItem("")
        self.cmbDPI.addItem("")
        self.cmbDPI.addItem("")
        self.cmbDPI.setObjectName(u"cmbDPI")

        self.formLayout2.setWidget(0, QFormLayout.FieldRole, self.cmbDPI)


        self.horizontalLayout_3.addLayout(self.formLayout2)

        self.formLayout1 = QFormLayout()
        self.formLayout1.setObjectName(u"formLayout1")
        self.formLayout1.setFormAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.formLayout1.setHorizontalSpacing(6)
        self.wgSlider = QWidget(self.grpJPEG)
        self.wgSlider.setObjectName(u"wgSlider")
        self.horizontalLayout = QHBoxLayout(self.wgSlider)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.SliderQuality = QSlider(self.wgSlider)
        self.SliderQuality.setObjectName(u"SliderQuality")
        self.SliderQuality.setMinimum(30)
        self.SliderQuality.setMaximum(100)
        self.SliderQuality.setSingleStep(5)
        self.SliderQuality.setValue(100)
        self.SliderQuality.setOrientation(Qt.Horizontal)

        self.horizontalLayout.addWidget(self.SliderQuality)

        self.lblQualityVal = QLabel(self.wgSlider)
        self.lblQualityVal.setObjectName(u"lblQualityVal")
        self.lblQualityVal.setAlignment(Qt.AlignCenter)
        self.lblQualityVal.setMargin(3)

        self.horizontalLayout.addWidget(self.lblQualityVal)


        self.formLayout1.setWidget(0, QFormLayout.FieldRole, self.wgSlider)

        self.lblQuality = QLabel(self.grpJPEG)
        self.lblQuality.setObjectName(u"lblQuality")

        self.formLayout1.setWidget(0, QFormLayout.LabelRole, self.lblQuality)


        self.horizontalLayout_3.addLayout(self.formLayout1)

        self.horizontalLayout_3.setStretch(0, 1)
        self.horizontalLayout_3.setStretch(1, 1)

        self.verticalLayout.addWidget(self.grpJPEG)

        self.grpCensore = QGroupBox(SaveAsDialog)
        self.grpCensore.setObjectName(u"grpCensore")
        self.verticalLayout_4 = QVBoxLayout(self.grpCensore)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.cmbCensore = QComboBox(self.grpCensore)
        self.cmbCensore.addItem("")
        self.cmbCensore.addItem("")
        self.cmbCensore.addItem("")
        self.cmbCensore.setObjectName(u"cmbCensore")

        self.verticalLayout_4.addWidget(self.cmbCensore)


        self.verticalLayout.addWidget(self.grpCensore)

        self.buttonBox = QDialogButtonBox(SaveAsDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Save)
        self.buttonBox.setCenterButtons(False)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(SaveAsDialog)
        self.buttonBox.accepted.connect(SaveAsDialog.accept)
        self.buttonBox.rejected.connect(SaveAsDialog.reject)
        self.SliderQuality.valueChanged.connect(self.lblQualityVal.setNum)

        QMetaObject.connectSlotsByName(SaveAsDialog)
    # setupUi

    def retranslateUi(self, SaveAsDialog):
        SaveAsDialog.setWindowTitle(QCoreApplication.translate("SaveAsDialog", u"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043a\u0430\u043a...", None))
        self.grpFormat.setTitle(QCoreApplication.translate("SaveAsDialog", u"\u0424\u043e\u0440\u043c\u0430\u0442 \u043d\u043e\u0432\u043e\u0433\u043e \u0444\u0430\u0439\u043b\u0430/\u0444\u0430\u0439\u043b\u043e\u0432", None))
        self.rbtPDF.setText(QCoreApplication.translate("SaveAsDialog", u"\u041a\u0430\u043a \u0443 \u0438\u0441\u0445\u043e\u0434\u043d\u043e\u0433\u043e \u0444\u0430\u0439\u043b\u0430 PDF", None))
        self.rbtPDFjpeg.setText(QCoreApplication.translate("SaveAsDialog", u"\u0424\u0430\u0439\u043b PDF \u0438\u0437 JPEG \u043a\u0430\u0440\u0442\u0438\u043d\u043e\u043a", None))
        self.rbtJPEG.setText(QCoreApplication.translate("SaveAsDialog", u"JPEG \u0444\u0430\u0439\u043b\u044b", None))
        self.rbtPNG.setText(QCoreApplication.translate("SaveAsDialog", u"PNG \u0444\u0430\u0439\u043b\u044b", None))
        self.grpPages.setTitle(QCoreApplication.translate("SaveAsDialog", u"\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.rbtPgAll.setText(QCoreApplication.translate("SaveAsDialog", u"\u0412\u0441\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.rbtPgCurr.setText(QCoreApplication.translate("SaveAsDialog", u"\u0422\u043e\u043b\u044c\u043a\u043e \u0442\u0435\u043a\u0443\u0449\u0443\u044e \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443", None))
        self.rbtPgRange.setText(QCoreApplication.translate("SaveAsDialog", u"\u0423\u043a\u0430\u0437\u0430\u043d\u043d\u044b\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.lblPg.setText(QCoreApplication.translate("SaveAsDialog", u"\u0421\u043f\u0438\u0441\u043e\u043a \u0441\u0442\u0440\u0430\u043d\u0438\u0446 (\u043f\u0440\u0438\u043c\u0435\u0440\u044b: 2-6,8,5,5,5,-10,7-):", None))
        self.chkSingles.setText(QCoreApplication.translate("SaveAsDialog", u"\u041a\u0430\u0436\u0434\u0443\u044e \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0432 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e\u043c \u0444\u0430\u0439\u043b\u0435 PDF", None))
        self.grpRotation.setTitle(QCoreApplication.translate("SaveAsDialog", u"\u041f\u043e\u0432\u043e\u0440\u043e\u0442 \u0441\u0442\u0440\u0430\u043d\u0438\u0446", None))
        self.btnOriginal.setText(QCoreApplication.translate("SaveAsDialog", u"\u041d\u0435 \u043c\u0435\u043d\u044f\u0442\u044c", None))
        self.btnLeft.setText(QCoreApplication.translate("SaveAsDialog", u"\u041f\u043e\u0432\u0435\u0440\u043d\u0443\u0442\u044c \u0432\u043b\u0435\u0432\u043e", None))
        self.btnRight.setText(QCoreApplication.translate("SaveAsDialog", u"\u041f\u043e\u0432\u0435\u0440\u043d\u0443\u0442\u044c \u0432\u043f\u0440\u0430\u0432\u043e", None))
        self.btn180dg.setText(QCoreApplication.translate("SaveAsDialog", u"\u041f\u0435\u0440\u0435\u0432\u0435\u0440\u043d\u0443\u0442\u044c \u043d\u0430 180\u00b0", None))
        self.grpJPEG.setTitle(QCoreApplication.translate("SaveAsDialog", u"\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u0433\u0440\u0430\u0444\u0438\u043a\u0438", None))
        self.lblDPI.setText(QCoreApplication.translate("SaveAsDialog", u"\u0420\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 DPI:", None))
        self.cmbDPI.setItemText(0, QCoreApplication.translate("SaveAsDialog", u"100", None))
        self.cmbDPI.setItemText(1, QCoreApplication.translate("SaveAsDialog", u"150", None))
        self.cmbDPI.setItemText(2, QCoreApplication.translate("SaveAsDialog", u"200", None))
        self.cmbDPI.setItemText(3, QCoreApplication.translate("SaveAsDialog", u"300", None))
        self.cmbDPI.setItemText(4, QCoreApplication.translate("SaveAsDialog", u"600", None))

        self.lblQualityVal.setText(QCoreApplication.translate("SaveAsDialog", u"100", None))
        self.lblQuality.setText(QCoreApplication.translate("SaveAsDialog", u"\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e:", None))
        self.grpCensore.setTitle(QCoreApplication.translate("SaveAsDialog", u"\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 / \u043a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u0430\u044f \u0442\u0430\u0439\u043d\u0430", None))
        self.cmbCensore.setItemText(0, QCoreApplication.translate("SaveAsDialog", u"\u0411\u0435\u0437 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f", None))
        self.cmbCensore.setItemText(1, QCoreApplication.translate("SaveAsDialog", u"\u0420\u0430\u0437\u043c\u044b\u0442\u044c \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e \u0432 \u0432\u044b\u0434\u0435\u043b\u0435\u043d\u043d\u044b\u0445 \u043e\u0431\u043b\u0430\u0441\u0442\u044f\u0445 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430", None))
        self.cmbCensore.setItemText(2, QCoreApplication.translate("SaveAsDialog", u"\u0417\u0430\u043a\u0440\u0430\u0441\u0438\u0442\u044c \u0431\u0435\u043b\u044b\u043c \u0446\u0432\u0435\u0442\u043e\u043c \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e \u0432 \u0432\u044b\u0434\u0435\u043b\u0435\u043d\u043d\u044b\u0445 \u043e\u0431\u043b\u0430\u0441\u0442\u044f\u0445 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430", None))

    # retranslateUi

