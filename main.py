"""
Приложение Mini PDF Tools
"""

import sys
from argparse import ArgumentParser
from argparse import RawTextHelpFormatter

from PySide2.QtCore import QCoreApplication
from PySide2.QtWidgets import QApplication

from mainwindow import MainWindow


# apt-get install qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools tesseract-ocr tesseract-ocr-rus

if __name__ == "__main__":
    argument_parser = ArgumentParser(description="Mini PDF Tools", formatter_class=RawTextHelpFormatter)
    argument_parser.add_argument("file", help="The file(s) to open", nargs='*', type=str)
    options = argument_parser.parse_args()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    if options.file:
        if len(options.file) == 1:
            win.open_or_combine_files(options.file[0])
        else:
            app.processEvents()
            win.show_combine_files_dialog(options.file)
    sys.exit(QCoreApplication.exec_())
