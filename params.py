"""
Этот файл содержит классы и функции для работы с настройками и параметрами программы
"""

import configparser
import enum
import os

from PySide2.QtCore import QSettings

import const


class FileFormat(enum.IntEnum):
    """Форматы файлов"""

    FMT_PDF = 0
    FMT_PDF_JPEG = 1
    FMT_JPEG = 2
    FMT_PNG = 3


class PageMode(enum.IntEnum):
    """Варианты выбора страниц"""

    PG_ALL = 0
    PG_CURRENT = 1
    PG_RANGE = 2


class PageRotation(enum.IntEnum):
    """Варианты вращения страницы"""

    RT_NONE = 0
    RT_LEFT = 1
    RT_RIGHT = 2
    RT_180 = 3


class CensoreMode(enum.IntEnum):
    """Варианты деперсонификации"""

    CM_NONE = 0
    CM_BLUR = 1
    CM_FILLWHITE = 2


class SaveParams:  # pylint: disable=too-many-instance-attributes
    """Настройки сохранения документа"""

    def __init__(self):
        # Считывание настроек
        settings = QSettings(const.SETTINGS_ORGANIZATION, const.SETTINGS_APPLICATION)

        self.format = FileFormat(int(settings.value('format', str(FileFormat.FMT_PDF))))
        self.format_censore = FileFormat(int(settings.value('format_censore', str(FileFormat.FMT_PDF_JPEG))))
        self.pgmode = PageMode(int(settings.value('pgmode', str(PageMode.PG_ALL))))
        # Если нужно восстанавливать старое значение, то поменять местами комментарии в следующих строках
        # self.rotation = PageRotation(int(settings.value('rotation', str(PageMode.RT_NONE))))
        self.rotation = PageRotation.RT_NONE

        self.pgrange = settings.value('pgrange', '')
        self.dpi = settings.value('dpi', '300')
        self.quality = int(settings.value('quality', '75'))
        self.singles = self.value_to_bool(settings.value('singles', False))

        self.censore_fio = self.value_to_bool(settings.value('censoreFIO', True))
        self.censore_addr = self.value_to_bool(settings.value('censoreAddr', True))
        self.censore_post = self.value_to_bool(settings.value('censorePost', True))
        self.censore_ipu = self.value_to_bool(settings.value('censoreIPU', True))
        self.censore_qr = self.value_to_bool(settings.value('censoreQR', True))

        self.censore = CensoreMode.CM_NONE
        self.setselectionsonly = False

    def save_params(self):
        """Сохранение настроек в реестре"""
        settings = QSettings(const.SETTINGS_ORGANIZATION, const.SETTINGS_APPLICATION)
        settings.setValue('format', str(self.format.value))
        settings.setValue('format_censore', str(self.format_censore.value))
        settings.setValue('pgmode', str(self.pgmode.value))
        settings.setValue('rotation', str(self.rotation.value))

        settings.setValue('pgrange', self.pgrange)
        settings.setValue('dpi', self.dpi)
        settings.setValue('quality', str(self.quality))
        settings.setValue('singles', str(self.singles))

        settings.setValue('censoreFIO', str(self.censore_fio))
        settings.setValue('censoreAddr', str(self.censore_addr))
        settings.setValue('censorePost', str(self.censore_post))
        settings.setValue('censoreIPU', str(self.censore_ipu))
        settings.setValue('censoreQR', str(self.censore_qr))

    @staticmethod
    def value_to_bool(value) -> bool:
        """Вспомогательная функция перевода значения из реестра в bool"""
        return value.lower() == 'true' if isinstance(value, str) else bool(value)


def get_lastfilename() -> str:
    """Получение пути последнего файла из настроек в реестре"""
    settings = QSettings(const.SETTINGS_ORGANIZATION, const.SETTINGS_APPLICATION)
    return settings.value('lastfilename', '')


def set_lastfilename(lastfilename: str):
    """Сохранение пути последнего файла в настройках в реестре"""
    settings = QSettings(const.SETTINGS_ORGANIZATION, const.SETTINGS_APPLICATION)
    settings.setValue('lastfilename', lastfilename)


def get_apps_paths() -> tuple:
    """Получение из ini файла путей к внешним приложениям

    Возвращается кортеж из трёх строк (tesseract_cmd, pdfviewer_cmd, xlseditor_cmd)
    """
    # Загружаем настройки для запуска внешних приложений
    config = configparser.ConfigParser()
    try:
        config.read(os.path.join(os.path.dirname(__file__), const.SETTINGS_FILENAME))
        return (
            config.get(const.SETTINGS_SECTION, 'tesseract_cmd', fallback=''),
            config.get(const.SETTINGS_SECTION, 'pdfviewer_cmd', fallback=''),
            config.get(const.SETTINGS_SECTION, 'xlseditor_cmd', fallback=''),
        )
    except configparser.Error:
        return '', '', ''
