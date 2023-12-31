# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'censore.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

import resources_rc

class Ui_CensoreDialog(object):
    def setupUi(self, CensoreDialog):
        if not CensoreDialog.objectName():
            CensoreDialog.setObjectName(u"CensoreDialog")
        CensoreDialog.resize(620, 401)
        icon = QIcon()
        icon.addFile(u":/icons/images/Paomedia-Small-N-Flat-Floppy.svg", QSize(), QIcon.Normal, QIcon.Off)
        CensoreDialog.setWindowIcon(icon)
        CensoreDialog.setModal(True)
        self.verticalLayout = QVBoxLayout(CensoreDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.grpCensoreItems = QGroupBox(CensoreDialog)
        self.grpCensoreItems.setObjectName(u"grpCensoreItems")
        self.horizontalLayout = QHBoxLayout(self.grpCensoreItems)
        self.horizontalLayout.setSpacing(25)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.chkFIO = QCheckBox(self.grpCensoreItems)
        self.chkFIO.setObjectName(u"chkFIO")
        self.chkFIO.setChecked(True)

        self.horizontalLayout.addWidget(self.chkFIO, 0, Qt.AlignHCenter)

        self.chkAddr = QCheckBox(self.grpCensoreItems)
        self.chkAddr.setObjectName(u"chkAddr")
        self.chkAddr.setChecked(True)

        self.horizontalLayout.addWidget(self.chkAddr, 0, Qt.AlignHCenter)

        self.chkPost = QCheckBox(self.grpCensoreItems)
        self.chkPost.setObjectName(u"chkPost")
        self.chkPost.setChecked(True)

        self.horizontalLayout.addWidget(self.chkPost, 0, Qt.AlignHCenter)

        self.chkIPU = QCheckBox(self.grpCensoreItems)
        self.chkIPU.setObjectName(u"chkIPU")
        self.chkIPU.setChecked(True)

        self.horizontalLayout.addWidget(self.chkIPU, 0, Qt.AlignHCenter)

        self.chkQR = QCheckBox(self.grpCensoreItems)
        self.chkQR.setObjectName(u"chkQR")
        self.chkQR.setChecked(True)

        self.horizontalLayout.addWidget(self.chkQR, 0, Qt.AlignHCenter)

        self.horizontalLayout.setStretch(0, 3)
        self.horizontalLayout.setStretch(1, 5)
        self.horizontalLayout.setStretch(2, 4)
        self.horizontalLayout.setStretch(3, 4)
        self.horizontalLayout.setStretch(4, 3)

        self.verticalLayout.addWidget(self.grpCensoreItems)

        self.grpFormat = QGroupBox(CensoreDialog)
        self.grpFormat.setObjectName(u"grpFormat")
        self.grpFormat.setMaximumSize(QSize(16777215, 80))
        self.verticalLayout_3 = QVBoxLayout(self.grpFormat)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.horizontalLayout1 = QHBoxLayout()
        self.horizontalLayout1.setSpacing(15)
        self.horizontalLayout1.setObjectName(u"horizontalLayout1")
        self.rbtPDFjpeg = QRadioButton(self.grpFormat)
        self.rbtPDFjpeg.setObjectName(u"rbtPDFjpeg")

        self.horizontalLayout1.addWidget(self.rbtPDFjpeg, 0, Qt.AlignLeft)

        self.rbtJPEG = QRadioButton(self.grpFormat)
        self.rbtJPEG.setObjectName(u"rbtJPEG")

        self.horizontalLayout1.addWidget(self.rbtJPEG, 0, Qt.AlignHCenter)

        self.rbtPNG = QRadioButton(self.grpFormat)
        self.rbtPNG.setObjectName(u"rbtPNG")
        self.rbtPNG.setChecked(True)

        self.horizontalLayout1.addWidget(self.rbtPNG, 0, Qt.AlignRight)


        self.verticalLayout_3.addLayout(self.horizontalLayout1)


        self.verticalLayout.addWidget(self.grpFormat)

        self.grpPages = QGroupBox(CensoreDialog)
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

        self.grpJPEG = QGroupBox(CensoreDialog)
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
        self.horizontalLayout_2 = QHBoxLayout(self.wgSlider)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.SliderQuality = QSlider(self.wgSlider)
        self.SliderQuality.setObjectName(u"SliderQuality")
        self.SliderQuality.setMinimum(30)
        self.SliderQuality.setMaximum(100)
        self.SliderQuality.setSingleStep(5)
        self.SliderQuality.setValue(100)
        self.SliderQuality.setOrientation(Qt.Horizontal)

        self.horizontalLayout_2.addWidget(self.SliderQuality)

        self.lblQualityVal = QLabel(self.wgSlider)
        self.lblQualityVal.setObjectName(u"lblQualityVal")
        self.lblQualityVal.setAlignment(Qt.AlignCenter)
        self.lblQualityVal.setMargin(3)

        self.horizontalLayout_2.addWidget(self.lblQualityVal)


        self.formLayout1.setWidget(0, QFormLayout.FieldRole, self.wgSlider)

        self.lblQuality = QLabel(self.grpJPEG)
        self.lblQuality.setObjectName(u"lblQuality")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lblQuality.sizePolicy().hasHeightForWidth())
        self.lblQuality.setSizePolicy(sizePolicy)

        self.formLayout1.setWidget(0, QFormLayout.LabelRole, self.lblQuality)


        self.horizontalLayout_3.addLayout(self.formLayout1)

        self.horizontalLayout_3.setStretch(0, 1)
        self.horizontalLayout_3.setStretch(1, 1)

        self.verticalLayout.addWidget(self.grpJPEG)

        self.grpCensore = QGroupBox(CensoreDialog)
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

        self.buttonBox = QDialogButtonBox(CensoreDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok|QDialogButtonBox.Save)
        self.buttonBox.setCenterButtons(False)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(CensoreDialog)
        self.buttonBox.accepted.connect(CensoreDialog.accept)
        self.buttonBox.rejected.connect(CensoreDialog.reject)
        self.SliderQuality.valueChanged.connect(self.lblQualityVal.setNum)

        QMetaObject.connectSlotsByName(CensoreDialog)
    # setupUi

    def retranslateUi(self, CensoreDialog):
        CensoreDialog.setWindowTitle(QCoreApplication.translate("CensoreDialog", u"\u0414\u0435\u043f\u0435\u0440\u0441\u043e\u043d\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f \u0434\u0430\u043d\u043d\u044b\u0445 \u0432 \u043f\u043b\u0430\u0442\u0435\u0436\u043d\u043e\u043c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0435 \u041a\u0422\u041a", None))
        self.grpCensoreItems.setTitle(QCoreApplication.translate("CensoreDialog", u"\u0414\u0435\u043f\u0435\u0440\u0441\u043e\u043d\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f \u0434\u0430\u043d\u043d\u044b\u0445", None))
        self.chkFIO.setText(QCoreApplication.translate("CensoreDialog", u"\u0424\u0418\u041e", None))
        self.chkAddr.setText(QCoreApplication.translate("CensoreDialog", u"\u0410\u0434\u0440\u0435\u0441 \u043f\u043e\u043c\u0435\u0449\u0435\u043d\u0438\u044f", None))
        self.chkPost.setText(QCoreApplication.translate("CensoreDialog", u"\u0410\u0434\u0440\u0435\u0441 \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0438", None))
        self.chkIPU.setText(QCoreApplication.translate("CensoreDialog", u"\u0428\u0430\u043f\u043a\u0430 \u0418\u041f\u0423", None))
        self.chkQR.setText(QCoreApplication.translate("CensoreDialog", u"QR \u043a\u043e\u0434", None))
        self.grpFormat.setTitle(QCoreApplication.translate("CensoreDialog", u"\u0424\u043e\u0440\u043c\u0430\u0442 \u043d\u043e\u0432\u043e\u0433\u043e \u0444\u0430\u0439\u043b\u0430/\u0444\u0430\u0439\u043b\u043e\u0432", None))
        self.rbtPDFjpeg.setText(QCoreApplication.translate("CensoreDialog", u"\u0424\u0430\u0439\u043b PDF \u0438\u0437 JPEG \u043a\u0430\u0440\u0442\u0438\u043d\u043e\u043a", None))
        self.rbtJPEG.setText(QCoreApplication.translate("CensoreDialog", u"JPEG \u0444\u0430\u0439\u043b\u044b", None))
        self.rbtPNG.setText(QCoreApplication.translate("CensoreDialog", u"PNG \u0444\u0430\u0439\u043b\u044b", None))
        self.grpPages.setTitle(QCoreApplication.translate("CensoreDialog", u"\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.rbtPgAll.setText(QCoreApplication.translate("CensoreDialog", u"\u0412\u0441\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.rbtPgCurr.setText(QCoreApplication.translate("CensoreDialog", u"\u0422\u043e\u043b\u044c\u043a\u043e \u0442\u0435\u043a\u0443\u0449\u0443\u044e \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443", None))
        self.rbtPgRange.setText(QCoreApplication.translate("CensoreDialog", u"\u0423\u043a\u0430\u0437\u0430\u043d\u043d\u044b\u0435 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b", None))
        self.lblPg.setText(QCoreApplication.translate("CensoreDialog", u"\u0421\u043f\u0438\u0441\u043e\u043a \u0441\u0442\u0440\u0430\u043d\u0438\u0446 (\u043f\u0440\u0438\u043c\u0435\u0440\u044b: 2-6,8,5,5,5,-10,7-):", None))
        self.chkSingles.setText(QCoreApplication.translate("CensoreDialog", u"\u041a\u0430\u0436\u0434\u0443\u044e \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0432 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e\u043c \u0444\u0430\u0439\u043b\u0435 PDF", None))
        self.grpJPEG.setTitle(QCoreApplication.translate("CensoreDialog", u"\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u0433\u0440\u0430\u0444\u0438\u043a\u0438", None))
        self.lblDPI.setText(QCoreApplication.translate("CensoreDialog", u"\u0420\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 DPI:", None))
        self.cmbDPI.setItemText(0, QCoreApplication.translate("CensoreDialog", u"100", None))
        self.cmbDPI.setItemText(1, QCoreApplication.translate("CensoreDialog", u"150", None))
        self.cmbDPI.setItemText(2, QCoreApplication.translate("CensoreDialog", u"200", None))
        self.cmbDPI.setItemText(3, QCoreApplication.translate("CensoreDialog", u"300", None))
        self.cmbDPI.setItemText(4, QCoreApplication.translate("CensoreDialog", u"600", None))

        self.lblQualityVal.setText(QCoreApplication.translate("CensoreDialog", u"100", None))
        self.lblQuality.setText(QCoreApplication.translate("CensoreDialog", u"\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e:", None))
        self.grpCensore.setTitle(QCoreApplication.translate("CensoreDialog", u"\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 / \u043a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u0430\u044f \u0442\u0430\u0439\u043d\u0430", None))
        self.cmbCensore.setItemText(0, QCoreApplication.translate("CensoreDialog", u"\u0411\u0435\u0437 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f", None))
        self.cmbCensore.setItemText(1, QCoreApplication.translate("CensoreDialog", u"\u0420\u0430\u0437\u043c\u044b\u0442\u044c \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e", None))
        self.cmbCensore.setItemText(2, QCoreApplication.translate("CensoreDialog", u"\u0417\u0430\u043a\u0440\u0430\u0441\u0438\u0442\u044c \u0431\u0435\u043b\u044b\u043c \u0446\u0432\u0435\u0442\u043e\u043c \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e", None))

    # retranslateUi

