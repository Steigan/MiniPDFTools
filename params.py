"""
Этот файл содержит классы и функции для работы с настройками и параметрами программы
"""

import configparser
import enum
import os
import platform
import re

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


# class PageRotation(enum.IntEnum):
#     """Варианты вращения страницы"""

#     RT_NONE = 0
#     RT_LEFT = 1
#     RT_RIGHT = 2
#     RT_180 = 3


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

        self.format = FileFormat(int(settings.value('format', FileFormat.FMT_PDF.value)))
        self.format_censore = FileFormat(int(settings.value('format_censore', FileFormat.FMT_PDF_JPEG.value)))
        self.pgmode = PageMode(int(settings.value('pgmode', PageMode.PG_ALL.value)))

        self.pgrange = settings.value('pgrange', '')
        self.dpi = settings.value('dpi', 300)
        self.quality = int(settings.value('quality', 75))
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
        settings.setValue('format', self.format.value)
        settings.setValue('format_censore', self.format_censore.value)
        settings.setValue('pgmode', self.pgmode.value)

        settings.setValue('pgrange', self.pgrange)
        settings.setValue('dpi', self.dpi)
        settings.setValue('quality', self.quality)
        settings.setValue('singles', self.singles)

        settings.setValue('censoreFIO', self.censore_fio)
        settings.setValue('censoreAddr', self.censore_addr)
        settings.setValue('censorePost', self.censore_post)
        settings.setValue('censoreIPU', self.censore_ipu)
        settings.setValue('censoreQR', self.censore_qr)

    @staticmethod
    def value_to_bool(value) -> bool:
        """Вспомогательная функция перевода значения из реестра в bool"""
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

    def get_pages_ranges(self, current_page: int, pdf_page_count: int):
        """Формирование списка объектов range c указанными в настройках диапазонами страниц

        Возвращает: список объектов range и количество страниц к обработке
        """

        if self.pgmode == PageMode.PG_ALL:  # Все страницы
            pageranges = [range(0, pdf_page_count)]
            page_count = pdf_page_count

        elif self.pgmode == PageMode.PG_CURRENT:  # Текущая страница
            pageranges = [range(current_page, current_page + 1)]
            page_count = 1

        else:  # Разные диапазоны
            page_count = 0
            pageranges = []

            # Разбираем по запятым на непустые группы
            for grp in re.findall('([0-9-]+),', self.pgrange + ','):
                # Разбираем на числовые подгруппы
                subgrp = re.findall(r'(\d*)-*', grp)

                r_start = 0
                r_end = pdf_page_count - 1

                if not grp.startswith('-'):
                    # Если группа начинается с номера страницы, то берем его и укладываем в рамки
                    # Эта страница должна быть не меньше первой и не больше последней
                    r_start = min(max(r_start, int(subgrp[0]) - 1), r_end)

                if not grp.endswith('-'):
                    # Если группа заканчивается на номер страницы, то берем его и укладываем в рамки
                    # Эта страница должна быть не меньше первой и не больше последней
                    r_end = max(min(r_end, int(subgrp[-2]) - 1), 0)

                if r_start > r_end:
                    # обратный порядок
                    pageranges.append(range(r_start, r_end - 1, -1))
                    page_count += r_start - r_end + 1  # количество страниц
                else:
                    # прямой порядок
                    pageranges.append(range(r_start, r_end + 1))
                    page_count += r_end - r_start + 1  # количество страниц

        return pageranges, page_count


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
        # Считываем INI файл
        config.read(os.path.join(os.path.dirname(__file__), const.SETTINGS_FILENAME))

        cmd_list = [
            config.get(const.SETTINGS_SECTION, 'tesseract_cmd', fallback=''),
            config.get(const.SETTINGS_SECTION, 'pdfviewer_cmd', fallback=''),
            config.get(const.SETTINGS_SECTION, 'xlseditor_cmd', fallback=''),
        ]

        # Проверяем файлы на существование. Если их нет, то меняем путь на пустую строку
        for i, filename in enumerate(cmd_list):
            if not filename:
                continue
            if not os.path.exists(filename):
                cmd_list[i] = ''

        # Если запустили под Windows, то подменяем пути pdfviewer и xlseditor спец. заглушкой
        if platform.system() == 'Windows':
            cmd_list[1] = cmd_list[2] = 'standard app'

        return (cmd_list[0], cmd_list[1], cmd_list[2])

    except configparser.Error:
        return '', '', ''
