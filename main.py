# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import sys

# import os
from argparse import ArgumentParser
from argparse import RawTextHelpFormatter

from PySide2.QtCore import QCoreApplication
from PySide2.QtCore import QUrl
from PySide2.QtWidgets import QApplication

from mainwindow import MainWindow


# apt-get install qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools tesseract-ocr tesseract-ocr-rus

if __name__ == "__main__":
    argument_parser = ArgumentParser(description="Mini PDF Tools", formatter_class=RawTextHelpFormatter)
    argument_parser.add_argument("file", help="The file(s) to open", nargs='*', type=str)
    options = argument_parser.parse_args()

    a = QApplication(sys.argv)
    # a.setApplicationDisplayName("Mini PDF Tools")
    w = MainWindow()
    w.show()
    if options.file:
        if len(options.file) == 1:
            w.open(QUrl.fromLocalFile(options.file[0]))
        else:
            a.processEvents()
            w.combine_files(options.file)
    # !!! For debugging !!!
    # w.open(QUrl.fromLocalFile(r'f:\PythonProjects\PdfTools64\test.pdf'))
    # w.open(QUrl.fromLocalFile(r'f:\PythonProjects\PdfTools64\source\Платежные документы КТК.pdf'))
    sys.exit(QCoreApplication.exec_())
