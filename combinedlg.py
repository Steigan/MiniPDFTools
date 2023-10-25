"""
Этот файл содержит класс диалога выбора и сортировки файлов для последующего объединения
"""

import os

from PySide2.QtCore import QItemSelectionModel
from PySide2.QtCore import Slot
from PySide2.QtWidgets import QDialog
from PySide2.QtWidgets import QDialogButtonBox
from PySide2.QtWidgets import QFileDialog

import const
import params
from combine_ui import Ui_CombineDialog


class CombineDialog(QDialog):
    """Диалог выбора и сортировки файлов для объединения"""

    def __init__(self, parent=None, filelist=None):
        # Инициализируем интерфейс на основе автокода QT
        super().__init__(parent)
        self.ui = Ui_CombineDialog()
        self.ui.setupUi(self)

        # Берем из настроек путь к последнему открытому файлу
        self.m_lastfn = params.get_lastfilename()

        # Меняем надписи кнопок
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText('  Создать  ')
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText('  Отмена  ')

        # Если передан filelist, то заполняем поле интерфейса со списком файлов
        if filelist is not None:
            for fl in filelist:
                self.ui.lstFiles.addItem(fl)

        # Обновляем доступность кнопок изменения порядка файлов и др.
        self.on_lstFiles_itemSelectionChanged()

        # Разрешаем прием DragAndDrop
        self.setAcceptDrops(True)

    def get_filelist(self) -> list:
        """Возвращает список файлов, выбранных пользователем для объединения"""
        return [self.ui.lstFiles.item(ind).text() for ind in range(self.ui.lstFiles.count())]

    def dragEnterEvent(self, event):  # pylint: disable=invalid-name
        """Обработчик события DragEnter"""

        # Проверяем формат перетаскиваемого объекта
        if event.mimeData().hasFormat('text/uri-list'):
            # Подтверждаем готовность принять объект
            event.acceptProposedAction()

    def dropEvent(self, event):  # pylint: disable=invalid-name
        """Обработчик события Drop"""

        # Обходим полученный список ссылок, выбираем приемлемые файлы и добавляем их в экранный список
        for url in event.mimeData().urls():
            if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in const.VALID_EXTENSIONS:
                self.ui.lstFiles.addItem(url.toLocalFile())

        # Обновляем доступность кнопок изменения порядка файлов и др.
        self.on_lstFiles_itemSelectionChanged()

        # Подтверждаем принятие объекта
        event.acceptProposedAction()

    ###########################################################################
    # Обработчики событий QT
    ###########################################################################

    @Slot()
    def on_btnAdd_clicked(self):  # pylint: disable=invalid-name
        """Обработчик нажатия кнопки <Добавить>"""

        # Открываем диалог выбора файлов в папке из m_lastfn
        directory = os.path.dirname(self.m_lastfn)
        to_open, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы PDF",
            directory,
            f"Поддерживаемые файлы ({''.join(f'*{ext} ' for ext in const.VALID_EXTENSIONS).strip()})",
        )

        # Если ничего не выбрано, то выходим
        if not to_open:
            return

        # Сохраняем путь первого файла в m_lastfn
        self.m_lastfn = to_open[0]

        # Добавляем файлы в поле ввода со списком файлов
        for fl in to_open:
            if os.path.splitext(fl)[1].lower() in const.VALID_EXTENSIONS:
                self.ui.lstFiles.addItem(fl)

        # Обновляем доступность кнопок изменения порядка файлов и др.
        self.on_lstFiles_itemSelectionChanged()

    @Slot()
    def on_btnRemove_clicked(self):  # pylint: disable=invalid-name
        """Обработчик нажатия кнопки <Удалить>"""

        # Удаляем первый выделенный элемент списка
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        self.ui.lstFiles.takeItem(ind)

        # Обновляем доступность кнопок изменения порядка файлов и др.
        self.on_lstFiles_itemSelectionChanged()

    @Slot()
    def on_btnSort_clicked(self):  # pylint: disable=invalid-name
        """Обработчик нажатия кнопки <Сортировать>"""
        self.ui.lstFiles.sortItems()

    @Slot()
    def on_btnUp_clicked(self):  # pylint: disable=invalid-name
        """Обработчик нажатия кнопки <Вверх>"""

        # Выдергиваем из списка первый выделенный элемент
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        itm = self.ui.lstFiles.takeItem(ind)

        # И вставаляем его выше на одну позицию
        ind -= 1
        self.ui.lstFiles.insertItem(ind, itm)

        # Делаем вставленную строку активной
        self.ui.lstFiles.setCurrentRow(ind, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot()
    def on_btnDown_clicked(self):  # pylint: disable=invalid-name
        """Обработчик нажатия кнопки <Вниз>"""

        # Выдергиваем из списка первый выделенный элемент
        ind = self.ui.lstFiles.selectedIndexes()[0].row()
        itm = self.ui.lstFiles.takeItem(ind)

        # И вставаляем его ниже на одну позицию
        ind += 1
        self.ui.lstFiles.insertItem(ind, itm)

        # Делаем вставленную строку активной
        self.ui.lstFiles.setCurrentRow(ind, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot()
    def on_lstFiles_itemSelectionChanged(self):  # pylint: disable=invalid-name
        """Обработчик изменения выбранного элемента в списке файлов"""

        # Если выделенный элементов в списке файлов нет, то дизейблим кнопки
        if not self.ui.lstFiles.selectedIndexes():
            self.ui.btnRemove.setEnabled(False)
            self.ui.btnUp.setEnabled(False)
            self.ui.btnDown.setEnabled(False)
        else:
            # Иначе переключаем доступность кнопок в зависимости от текущей позиции в списке
            ind = self.ui.lstFiles.selectedIndexes()[0].row()
            self.ui.btnRemove.setEnabled(True)
            self.ui.btnUp.setEnabled(ind > 0)
            self.ui.btnDown.setEnabled(ind < (self.ui.lstFiles.count() - 1))

        # Если список файлов пуст, дизейблим кнопку <Создать>
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.ui.lstFiles.count() > 0)
