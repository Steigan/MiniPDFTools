# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'combine.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

import resources_rc

class Ui_CombineDialog(object):
    def setupUi(self, CombineDialog):
        if not CombineDialog.objectName():
            CombineDialog.setObjectName(u"CombineDialog")
        CombineDialog.resize(618, 414)
        self.verticalLayout = QVBoxLayout(CombineDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.grpFilelist = QGroupBox(CombineDialog)
        self.grpFilelist.setObjectName(u"grpFilelist")
        self.horizontalLayout = QHBoxLayout(self.grpFilelist)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.lstFiles = QListWidget(self.grpFilelist)
        self.lstFiles.setObjectName(u"lstFiles")

        self.horizontalLayout.addWidget(self.lstFiles)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.btnAdd = QPushButton(self.grpFilelist)
        self.btnAdd.setObjectName(u"btnAdd")
        icon = QIcon()
        icon.addFile(u":/icons/images/plus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btnAdd.setIcon(icon)

        self.verticalLayout_2.addWidget(self.btnAdd)

        self.btnRemove = QPushButton(self.grpFilelist)
        self.btnRemove.setObjectName(u"btnRemove")
        self.btnRemove.setEnabled(False)
        icon1 = QIcon()
        icon1.addFile(u":/icons/images/minus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btnRemove.setIcon(icon1)

        self.verticalLayout_2.addWidget(self.btnRemove)

        self.verticalSpacer_2 = QSpacerItem(20, 5, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_2)

        self.btnSort = QPushButton(self.grpFilelist)
        self.btnSort.setObjectName(u"btnSort")
        icon2 = QIcon()
        icon2.addFile(u":/icons/images/alphabetical_sorting_az.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btnSort.setIcon(icon2)

        self.verticalLayout_2.addWidget(self.btnSort)

        self.verticalSpacer_3 = QSpacerItem(20, 5, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_3)

        self.btnUp = QPushButton(self.grpFilelist)
        self.btnUp.setObjectName(u"btnUp")
        self.btnUp.setEnabled(False)
        icon3 = QIcon()
        icon3.addFile(u":/icons/images/Paomedia-Small-N-Flat-Sign-up.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btnUp.setIcon(icon3)

        self.verticalLayout_2.addWidget(self.btnUp)

        self.btnDown = QPushButton(self.grpFilelist)
        self.btnDown.setObjectName(u"btnDown")
        self.btnDown.setEnabled(False)
        icon4 = QIcon()
        icon4.addFile(u":/icons/images/Paomedia-Small-N-Flat-Sign-down.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btnDown.setIcon(icon4)

        self.verticalLayout_2.addWidget(self.btnDown)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.horizontalLayout.addLayout(self.verticalLayout_2)


        self.verticalLayout.addWidget(self.grpFilelist)

        self.buttonBox = QDialogButtonBox(CombineDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(CombineDialog)
        self.buttonBox.accepted.connect(CombineDialog.accept)
        self.buttonBox.rejected.connect(CombineDialog.reject)

        QMetaObject.connectSlotsByName(CombineDialog)
    # setupUi

    def retranslateUi(self, CombineDialog):
        CombineDialog.setWindowTitle(QCoreApplication.translate("CombineDialog", u"\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u043f\u0443\u0442\u0435\u043c \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f \u0444\u0430\u0439\u043b\u043e\u0432", None))
        self.grpFilelist.setTitle(QCoreApplication.translate("CombineDialog", u"\u0421\u043f\u0438\u0441\u043e\u043a \u0444\u0430\u0439\u043b\u043e\u0432", None))
        self.btnAdd.setText(QCoreApplication.translate("CombineDialog", u"\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c", None))
        self.btnRemove.setText(QCoreApplication.translate("CombineDialog", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c", None))
        self.btnSort.setText(QCoreApplication.translate("CombineDialog", u"  \u0421\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c  ", None))
        self.btnUp.setText(QCoreApplication.translate("CombineDialog", u"\u0412\u0432\u0435\u0440\u0445", None))
        self.btnDown.setText(QCoreApplication.translate("CombineDialog", u"\u0412\u043d\u0438\u0437", None))
    # retranslateUi

