"""
Анализ PDF файла на наличие в нем таблиц (с рамками!!!) и сохранение найденных табличных данных в файл XLSX
"""
import logging
import os
import re

import fitz
import xlsxwriter


# Константы для описания характеристик узлов сетки таблицы
NODE_DIR_UP = 1
NODE_DIR_DOWN = 2
NODE_DIR_LEFT = 4
NODE_DIR_RIGHT = 8


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'log.log'))
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)


class TableBorder:
    """Класс для хранения данных о найденных границах/рамках между ячейками таблицы"""

    def __init__(self, original_coord: float, start_coord: float, end_coord: float):
        """Инициализация

        Args:
            original_coord (float): координата (по первой оси) прямой, на которой находится отрезок границы/рамки
            start_coord (float): координата (по второй оси) начала отрезка границы/рамки
            end_coord (float): координата (по второй оси) конца отрезка границы/рамки
        """
        self.original_coord = original_coord  # координата, на которой находится весь отрезок (по первой оси)
        self.start_coord = start_coord  # координата, на которой находится начало отрезка (по второй оси)
        self.end_coord = end_coord  # координата, на которой находится конец отрезка (по второй оси)
        self.guideline_idx = -1  # индекс направляющей, на которой расположен весь отрезок (по первой оси)
        self.start_idx = -1  # индекс направляющей, на которой расположено начало отрезка (по второй оси)
        self.end_idx = -1  # индекс направляющей, на которой расположен конец отрезка (по второй оси)

    def glue(self, guideline_map: dict, guidelines: list):
        """Привязка отрезков границ/рамок к направляющим по обеим осям

        Args:
            guideline_map (dict): карта соответствий по первой оси {координата : индекс направляющей}
            guidelines (list): список направляющих по второй оси для привязки концов отрезка
        """
        # индекс направляющей, на которой расположен весь отрезок
        self.guideline_idx = guideline_map[self.original_coord]
        self.start_idx = -1  # начало не привязано
        self.end_idx = -1  # конец не привязан

        prev_coord = -100  # предыдущая координата за пределами листа слева
        max_gl_idx = len(guidelines) - 1  # индекс последней направляющей по второй оси

        # Обходим весь список направляющих по второй оси для привязки/выравнивания концов отрезка
        for i, gl_coord in enumerate(guidelines):
            # начало еще не привязано?
            if self.start_idx == -1:
                # начало приходится на первую направляющую или находится до неё?
                if i == 0 and self.start_coord <= gl_coord:
                    self.start_idx = 0

                # начало находится между предыдущей направляющей и текущей?
                elif prev_coord <= self.start_coord <= gl_coord:
                    # начало ближе к предыдущей направляющей, чем к текущей?
                    if (self.start_coord - prev_coord) / (gl_coord - prev_coord) < 0.5:
                        self.start_idx = i - 1
                    else:
                        self.start_idx = i

            # начало уже привязяно, а конец еще нет?
            if self.start_idx > -1 and self.end_idx == -1:
                # конец приходится на последнюю направляющую или находится за ней?
                if i == max_gl_idx and self.end_coord >= gl_coord:
                    self.end_idx = max_gl_idx

                # конец находится между предыдущей направляющей и текущей?
                elif prev_coord <= self.end_coord <= gl_coord:
                    # конец ближе к предыдущей направляющей, чем к текущей?
                    if (self.end_coord - prev_coord) / (gl_coord - prev_coord) < 0.5:
                        self.end_idx = i - 1
                    else:
                        self.end_idx = i

            # сохраняем координату обработанной направляющей
            prev_coord = gl_coord


def make_text(words):
    """Return textstring output of get_text("words").

    Word items are sorted for reading sequence left to right,
    top to bottom.
    (besaed on textbox-extract-1.py sample code)
    """
    line_dict = {}  # key: vertical coordinate, value: list of words
    words.sort(key=lambda ww: ww[0])  # sort by horizontal coordinate
    for w in words:  # fill the line dictionary
        y1 = round(w[3], 1)  # bottom of a word: don't be too picky!
        word = w[4]  # the text of the word
        line = line_dict.get(y1, [])  # read current line content
        line.append(word)  # append new word
        line_dict[y1] = line  # write back to dict
    lines = list(line_dict.items())
    lines.sort()  # sort vertically
    return "\n".join([" ".join(line[1]) for line in lines])


def parse_page_tables(page, worksheet, start_row, cell_format, strong: bool = True):  # noqa: ignore=C901
    """Анализ и разбор табличных данных на странице файла PDF и добавление их на лист файла XLSX

    Args:
        page (object): сраница файла PDF
        worksheet (object): лист файла XLSX
        start_row (int): строка листа файла XLSX, с которой начнется добавление данных
        cell_format (object): формат ячеек файла XLSX
        strong (bool): True - режим строгого поиска разметки таблицы,
                       False - упрощенное дробление таблицы на сетку по найденным направляющим

    Returns:
        int: количество добавленных на лист файла XLSX строк
    """
    min_delta = 1  # Погрешность x и y, в пределах которой дополнительные наравляющие не создаются
    rm = page.rotation_matrix  # матрица для переворота исходных координат документа в отображаемые на экране

    # Первый этап: собираем данные о всех вертикальных и горизонтальных линиях на странице
    vert = set()  # координаты вертикальных отрезков
    hori = set()  # координаты горизонтальных отрезков
    vert_borders = []  # вертикальные границы
    hori_borders = []  # горизонтальные границы
    paths = page.get_drawings()  # получаем все линии и прочую векторную графику на странице

    for p in paths:
        for item in p["items"]:  # просматриваем все элементы
            if item[0] == "l":  # это линия
                p1, p2 = item[1:]  # начало и конец
                p1 *= rm  # приводим к "экранной" системе координат
                p2 *= rm  # приводим к "экранной" системе координат
                if p1.x == p2.x:  # это вертикальная линия
                    # нормализуем координаты
                    if p1.y <= p2.y:
                        m_start, m_end = p1.y, p2.y
                    else:
                        m_start, m_end = p2.y, p1.y

                    # дополняем множество всех вариантов координат вертикальных отрезков
                    vert.add(p1.x)
                    # дополняем список вертикальных отрезков
                    vert_borders.append(TableBorder(p1.x, m_start, m_end))

                elif p1.y == p2.y:  # это горизонтальная линия
                    # нормализуем координаты
                    if p1.x <= p2.x:
                        m_start, m_end = p1.x, p2.x
                    else:
                        m_start, m_end = p2.x, p1.x

                    # дополняем множество всех вариантов координат горизонтальных отрезков
                    hori.add(p1.y)
                    # дополняем список горизонтальных отрезков
                    hori_borders.append(TableBorder(p1.y, m_start, m_end))

            elif item[0] == "re":  # это прямоугольник
                rect = item[1] * rm  # приводим к "экранной" системе координат

                # нормализуем координаты
                rect.normalize()

                # дополняем множество всех вариантов координат вертикальных отрезков
                vert.add(rect.x0)
                vert.add(rect.x1)
                # дополняем множество всех вариантов координат горизонтальных отрезков
                hori.add(rect.y0)
                hori.add(rect.y1)
                # дополняем список вертикальных отрезков
                vert_borders.append(TableBorder(rect.x0, rect.y0, rect.y1))
                vert_borders.append(TableBorder(rect.x1, rect.y0, rect.y1))
                # дополняем список горизонтальных отрезков
                hori_borders.append(TableBorder(rect.y0, rect.x0, rect.x1))
                hori_borders.append(TableBorder(rect.y1, rect.x0, rect.x1))

    # Второй этап: определяем "округленные" вертикальные и горизонтальные направляющие
    s_vert = sorted(list(vert))  # сохраняем отсортированный список из всего множества
    vert = []  # список вертикальных направляющих
    # карта перевода горизонатальных координат в индекс соответствующей вертикальной направляющей
    vert_guideline_map = {}

    prev_coord = -100  # координата предыдущей направляющей
    gl_idx = -1  # текущий индекс направляющей
    # обходим отсортированный список из всего множества координат вертикальных отрезков
    for coord in s_vert:
        # расстояние от предыдущей направляющей больше погрешности?
        if coord - prev_coord > min_delta:
            gl_idx += 1  # инкрементируем текущий индекс направляющей
            vert.append(coord)  # добавляем координату направляющей в список
            prev_coord = coord  # сохраняем координату в качестве координаты предыдущей направляющей

        # дополняем словарь с картой перевода горизонатальных координат
        # в индекс соответствующей вертикальной направляющей
        vert_guideline_map[coord] = gl_idx

    s_hori = sorted(list(hori))  # сохраняем отсортированный список из всего множества
    hori = []  # список горизонтальных направляющих
    # карта перевода вертикальных координат в индекс соответствующей горизонтальной направляющей
    hori_guideline_map = {}

    prev_coord = -100  # координата предыдущей направляющей
    gl_idx = -1  # текущий индекс направляющей
    # обходим отсортированный список из всего множества координат горизонтальных отрезков
    for coord in s_hori:
        # расстояние от предыдущей направляющей больше погрешности?
        if coord - prev_coord > min_delta:
            gl_idx += 1  # инкрементируем текущий индекс направляющей
            hori.append(coord)  # добавляем координату направляющей в список
            prev_coord = coord  # сохраняем координату в качестве координаты предыдущей направляющей

        # дополняем словарь с картой перевода вертикальных координат
        # в индекс соответствующей горизонатальной направляющей
        hori_guideline_map[coord] = gl_idx

    # Задан "строгий" режим привязки к разметке?
    if strong:  # pylint: disable=too-many-nested-blocks
        # Третий этап: привязка вертикальных отрезков к направляющим
        for bd in vert_borders:
            # привязываем вертикальные отрезки к горизонтальным направляющим
            bd.glue(vert_guideline_map, hori)

        # Четвертый этап: привязка горизонтальных отрезков к направляющим + заодно формируем матрицу узлов
        nodes = [[0] * (len(vert)) for _ in range(len(hori))]
        # обходим все горизонтальные отрезки
        for bd in hori_borders:
            # привязываем концы отрезка к вертикальным направляющим
            bd.glue(hori_guideline_map, vert)

            m_idx = bd.start_idx  # берем начало этого горизонтального отрезка
            if m_idx >= 0:  # если у этого горизонтального отрезка есть начало
                # обходим все возможные точки пересечения этого отрезка с перпендикулярными направляющими
                while m_idx <= bd.end_idx:
                    if m_idx == bd.start_idx:  # если найдем, то это будет пересечение в начале отрезка
                        hor_dir = NODE_DIR_RIGHT
                    elif m_idx == bd.end_idx:  # если найдем, то это будет пересечение в конце отрезка
                        hor_dir = NODE_DIR_LEFT
                    else:  # если найдем, то это будет пересечение в середине отрезка
                        hor_dir = NODE_DIR_LEFT | NODE_DIR_RIGHT

                    # проверяем все перпендикулярные направляющие на пересечение в текущей точке
                    for cross_bd in vert_borders:
                        # "точка" m_idx находится на направляющей "cross_bd.guideline_idx"?
                        if cross_bd.guideline_idx == m_idx:
                            # значит, есть вероятность пересечения
                            if cross_bd.start_idx == bd.guideline_idx:
                                # пересечение в начале перпендикулярного отрезка
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= hor_dir | NODE_DIR_DOWN
                            elif cross_bd.end_idx == bd.guideline_idx:
                                # пересечение в конце перпендикулярного отрезка
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= hor_dir | NODE_DIR_UP
                            elif cross_bd.start_idx < bd.guideline_idx < cross_bd.end_idx:
                                # пересечение в середине перпендикулярного отрезка
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= hor_dir | NODE_DIR_DOWN | NODE_DIR_UP

                    m_idx += 1  # сдвигаемся по горизонтальному отрезку на одну вертикальную направляющую вправо

        # Пятый этап: распознание текста в найденных прямоугольных областях и заполнение таблицы
        # Обходим все найденные узлы
        for rdx, hori_rdx in enumerate(hori):
            for cdx, vert_cdx in enumerate(vert):
                node = nodes[rdx][cdx]  # берем очередной узел
                if (node & NODE_DIR_RIGHT) and (node & NODE_DIR_DOWN):  # этот узел является стартовым
                    for cdx2 in range(cdx + 1, len(vert)):  # обходим следующие узлы по горизонтали
                        if nodes[rdx][cdx2] & NODE_DIR_DOWN:  # найден верхний правый узел
                            # обходим следующие узлы по вертикали по правой стороне
                            for rdx2 in range(rdx + 1, len(hori)):
                                # типа оптимистический вариант, без вложенных областей
                                if nodes[rdx2][cdx2] & NODE_DIR_LEFT:  # найден нижний правый узел
                                    rc = fitz.Rect([vert_cdx, hori_rdx, vert[cdx2], hori[rdx2]]) / rm
                                    recttext = page.get_text("text", clip=rc).rstrip()
                                    recttext = re.sub(r'\s+', ' ', recttext)
                                    if (rdx2 > rdx + 1) or (cdx2 > cdx + 1):
                                        # отлавливаем ошибку, т.к. в некоторых таблицах могут быть пересечения областей
                                        try:
                                            worksheet.merge_range(
                                                start_row + rdx,
                                                cdx,
                                                start_row + rdx2 - 1,
                                                cdx2 - 1,
                                                recttext,
                                                cell_format,
                                            )
                                        except xlsxwriter.exceptions.OverlappingRange:
                                            logger.info('Ячейка %s:%s = %s', start_row + rdx + 1, cdx + 1, recttext)
                                    else:
                                        worksheet.write_string(start_row + rdx, cdx, recttext, cell_format)
                                    break
                            break

    else:  # упрощенный режим - шинковка по направляющим, без учета "объединенности" ячеек
        words = page.get_text("words")  # получаем список всех слов на странице
        # переводим в "экранные" координаты
        transwords = []
        for w in words:
            rc = fitz.Rect(w[:4]) * rm
            transwords.append((rc.x0, rc.y0, rc.x1, rc.y1, w[4], w[5], w[6], w[7]))

        # Обходим все "клетки" и заполняем таблицу Excel
        for rdx in range(len(hori) - 1):
            for cdx in range(len(vert) - 1):
                rc = fitz.Rect([vert[cdx], hori[rdx], vert[cdx + 1], hori[rdx + 1]])
                mywords = [w for w in transwords if fitz.Rect(w[:4]).intersects(rc)]
                recttext = make_text(mywords)
                recttext = re.sub(r'\s+', ' ', recttext)
                worksheet.write_string(start_row + rdx, cdx, recttext, cell_format)

    # Если это первая страница, то устанавливаем по ней ширину столбцов таблицы
    if not start_row:
        old_cc = 0
        for i, cc in enumerate(vert):
            if i:
                worksheet.set_column(i - 1, i - 1, (cc - old_cc) / 4)
            old_cc = cc

    # Возвращаем количество добавленных в таблицу строк
    return len(hori) - 1


def parse_tables(doc, xlsfile: str, strong: bool = True, progress_callback=None):
    """Анализ и разбор табличных данных на всех страницах файла PDF и сохранение их в файл XLSX

    Args:
        doc (object): файл PDF (объект fitz document)
        xlsfile (str): имя сохраняемого файла XLSX
        strong (bool): True - режим строгого поиска разметки таблицы,
                       False - упрощенное дробление таблицы на сетку по найденным направляющим
        process_callback: callback-функция, которой необходимо передать процент проделанной работы

    Returns:
        int: количество добавленных в файл XLSX строк
    """

    # Создаем объект Workbook Excel
    workbook = xlsxwriter.Workbook(xlsfile)
    # Создаем лист
    worksheet = workbook.add_worksheet()

    # Создаем формат ячеек
    cell_format = workbook.add_format()
    cell_format.set_align('center')
    cell_format.set_align('vcenter')
    cell_format.set_text_wrap()
    cell_format.set_border(1)

    page_count = len(doc)  # Количество страниц в файле PDF
    current_row = 0  # Текущая строка таблицы Excel

    # Обходим все страницы файла PDF
    for pno, page in enumerate(doc):
        # Добавляем на лист данные из текущей страницы
        current_row += parse_page_tables(page, worksheet, current_row, cell_format, strong)

        # Вызываем callback функцию для обновления прогрессбара
        if progress_callback is not None:
            progress_callback((pno + 1) * 100 // page_count)

    # Сохраняем и закрываем файл XLSX
    workbook.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)

    return current_row


# if __name__ == "__main__":
#     doc = fitz.open(r"f:\PythonProjects\PdfTools64\source2\Колонка Подзь февраль 2023.pdf")
#     fitz.Tools().set_small_glyph_heights(True)
#     if not parse_tables(doc, 'output.xlsx', False):
#         print('Ничо нетуть')
