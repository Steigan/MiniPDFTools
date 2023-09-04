from PySide2.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog)
from PySide2.QtCore import Signal, Slot, QItemSelectionModel, QSettings
from combine_ui import Ui_CombineDialog
import os

class CombineDialog(QDialog):
    def __init__(self, parent=None, filelist=[], validExtensions=[]):
        super().__init__(parent)
        self.ui = Ui_CombineDialog()
        self.ui.setupUi(self)
        
        self.m_validExtensions = validExtensions
        settings = QSettings('Steigan', 'Mini PDF Tools')
        self.m_lastfn = settings.value('lastfilename', '')

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.accept)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('  Создать  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('  Отмена  ')
        
        for fl in filelist:
            self.ui.lstFiles.addItem(fl)

        self.on_lstFiles_itemSelectionChanged()
        self.setAcceptDrops(True)
        # self.ui.lstFiles.currentRowChanged.connect(lambda: self.ui.btnRemove.setEnabled(currentRow >= 0))
        # self.resize(self.minimumSizeHint())currentChanged

    def getFilelist(self):
        return [self.ui.lstFiles.item(ind).text() for ind in range(self.ui.lstFiles.count())]

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()
        
    def dropEvent(self, event):
        url_list = event.mimeData().urls()
        for url in url_list:
            if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in self.m_validExtensions:
                self.ui.lstFiles.addItem(url.toLocalFile())
        self.on_lstFiles_itemSelectionChanged()
        event.acceptProposedAction()

    @Slot()
    def on_btnAdd_clicked(self):
        directory = os.path.dirname(self.m_lastfn)
        to_open, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы PDF",
            directory, f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in self.m_validExtensions).strip()})")

        if to_open:
            self.m_lastfn = to_open[0]
        for fl in to_open:
            if os.path.splitext(fl)[1].lower() in self.m_validExtensions:
                self.ui.lstFiles.addItem(fl)
        self.on_lstFiles_itemSelectionChanged()

    @Slot()
    def on_btnRemove_clicked(self):
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        itm = self.ui.lstFiles.takeItem(ind)
        self.on_lstFiles_itemSelectionChanged()

    @Slot()
    def on_btnSort_clicked(self):
        self.ui.lstFiles.sortItems()

    @Slot()
    def on_btnUp_clicked(self):
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        itm = self.ui.lstFiles.takeItem(ind)
        ind -= 1
        self.ui.lstFiles.insertItem(ind, itm)
        self.ui.lstFiles.setCurrentRow(ind, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot()
    def on_btnDown_clicked(self):
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        itm = self.ui.lstFiles.takeItem(ind)
        ind += 1
        self.ui.lstFiles.insertItem(ind, itm)
        self.ui.lstFiles.setCurrentRow(ind, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot()
    def on_lstFiles_itemSelectionChanged(self):
        if len(self.ui.lstFiles.selectedIndexes()) > 0:
            ind = self.ui.lstFiles.selectedIndexes()[0].row()
            self.ui.btnRemove.setEnabled(True)
            self.ui.btnUp.setEnabled(ind > 0)
            self.ui.btnDown.setEnabled(ind < (self.ui.lstFiles.count() - 1))
        else:
            self.ui.btnRemove.setEnabled(False)
            self.ui.btnUp.setEnabled(False)
            self.ui.btnDown.setEnabled(False)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.ui.lstFiles.count() > 0)
