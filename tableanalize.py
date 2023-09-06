"""
Анализ PDF файла на наличие в нем таблиц (с рамками!!!) и сохранение найденных табличных данных в файл XLSX
"""
import re

import fitz
import xlsxwriter


# Константы для описания характеристик узлов сетки таблицы
NODE_DIR_UP = 1
NODE_DIR_DOWN = 2
NODE_DIR_LEFT = 4
NODE_DIR_RIGHT = 8


class tableBorder:
    """Класс для хранения данных о найденных границах/рамках между ячейками таблицы"""

    def __init__(self, original_coord, start_coord, end_coord):
        """Инициализация

        Args:
            original_coord (float): координата (по первой оси) прямой, на которой находится отрезок границы/рамки
            start_coord (float): координата (по второй оси) начала отрезка границы/рамки
            end_coord (float): координата (по второй оси) конца отрезка границы/рамки
        """
        self.original_coord = original_coord
        self.start_coord = start_coord
        self.end_coord = end_coord
        self.guideline_idx = -1
        self.start_idx = -1
        self.end_idx = -1

    def glue(self, guideline_map, guidelines):
        """Привязка отрезков границ/рамок к направляющим по обеим осям

        Args:
            guideline_map (dict): карта соответствий по первой оси {координата : индекс направляющей}
            guidelines (list): список направляющих по второй оси для привязки концов отрезка
        """
        self.guideline_idx = guideline_map[self.original_coord]
        self.start_idx = -1
        self.end_idx = -1
        prev_coord = -100
        max_gl_idx = len(guidelines) - 1
        for i, gl in enumerate(guidelines):
            if self.start_idx == -1:  # начало еще не привязано
                if i == 0 and self.start_coord <= gl:  # начало приходится на начальный край или находится до него
                    self.start_idx = i
                elif prev_coord <= self.start_coord <= gl:  # начало между предыдущей направляющей и текущей
                    if (self.start_coord - prev_coord) / (gl - prev_coord) < 0.5:
                        self.start_idx = i - 1
                    else:
                        self.start_idx = i
            if self.start_idx > -1 and self.end_idx == -1:  # конец еще не привязан
                if i == max_gl_idx and self.end_coord >= gl:  # конец приходится на конечный край или находится за ним
                    self.end_idx = i
                elif prev_coord <= self.end_coord <= gl:  # конец между предыдущей направляющей и текущей
                    if (self.end_coord - prev_coord) / (gl - prev_coord) < 0.5:
                        self.end_idx = i - 1
                    else:
                        self.end_idx = i
            prev_coord = gl


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
    max_delta = 1
    rm = page.rotation_matrix  # матрица для переворота исходных координат документа в отображаемые на экране

    # Первый этап: собираем данные о всех вертикальных и горизонтальных линиях на странице
    # Python/овский 'set' позволяет избавиться от дубликатов без дополнительного кода.
    vert = set()  # вертикальные координаты
    hori = set()  # горизонтальные координаты
    vert_borders = []  # вертикальные границы
    hori_borders = []  # горизонтальные границы
    paths = page.get_drawings()  # получаем все линии и прочую векторную графику на странице
    for p in paths:
        for item in p["items"]:  # просматриваем все элементы
            # print(item)
            if item[0] == "l":  # это линия
                p1, p2 = item[1:]  # начало и конец
                p1 *= rm  # приводим к "экранной" системе координат
                p2 *= rm  # приводим к "экранной" системе координат
                if p1.x == p2.x:  # это вертикальная линия
                    if p1.y <= p2.y:
                        m_start, m_end = p1.y, p2.y
                    else:
                        m_start, m_end = p2.y, p1.y

                    vert.add(p1.x)
                    vert_borders.append(tableBorder(p1.x, m_start, m_end))

                elif p1.y == p2.y:  # это горизонтальная линия
                    if p1.x <= p2.x:
                        m_start, m_end = p1.x, p2.x
                    else:
                        m_start, m_end = p2.x, p1.x

                    hori.add(p1.y)
                    hori_borders.append(tableBorder(p1.y, m_start, m_end))

            elif item[0] == "re":  # это прямоугольник
                rect = item[1] * rm  # приводим к "экранной" системе координат
                rect.normalize()
                vert.add(rect.x0)
                vert.add(rect.x1)
                hori.add(rect.y0)
                hori.add(rect.y1)
                vert_borders.append(tableBorder(rect.x0, rect.y0, rect.y1))
                vert_borders.append(tableBorder(rect.x1, rect.y0, rect.y1))
                hori_borders.append(tableBorder(rect.y0, rect.x0, rect.x1))
                hori_borders.append(tableBorder(rect.y1, rect.x0, rect.x1))

    # Второй этап: определяем "округленные" вертикальные и горизонтальные направляющие
    s_vert = sorted(list(vert))
    vert = []  # Типа вертикальные направляющие
    vert_guideline_map = (
        {}
    )  # Типа карта перевода горизонатальных координат в индекс соответствующей вертикальной направляющей
    last_cc = -100
    gl_idx = -1
    for it in s_vert:
        if it - last_cc > max_delta:
            gl_idx += 1
            vert.append(it)
            last_cc = it
        vert_guideline_map[it] = gl_idx

    s_hori = sorted(list(hori))
    hori = []  # Типа горизонтальные направляющие
    hori_guideline_map = (
        {}
    )  # Типа карта перевода вертикальных координат в индекс соответствующей горизонтальной направляющей
    last_cc = -100
    gl_idx = -1
    for it in s_hori:
        if it - last_cc > max_delta:
            gl_idx += 1
            hori.append(it)
            last_cc = it
        hori_guideline_map[it] = gl_idx

    if strong:  # если задан "строгий" режим привязки к разметке
        # Третий этап: привязка вертикальных отрезков к направляющим
        for bd in vert_borders:
            bd.glue(vert_guideline_map, hori)
            # print(bd.guideline_idx, bd.start_idx, bd.end_idx)

        # Четвертый этап: привязка горизонтальных отрезков к направляющим + заодно формируем матрицу узлов
        nodes = [[0] * (len(vert)) for _ in range(len(hori))]
        for bd in hori_borders:
            bd.glue(hori_guideline_map, vert)
            m_idx = bd.start_idx
            if m_idx >= 0:  # если у этого горизонтального отрезка есть начало
                while m_idx <= bd.end_idx:  # обходим все возможные точки пересечения с перпендикулярными направляющими
                    if m_idx == bd.start_idx:
                        hor_dir = NODE_DIR_RIGHT
                    elif m_idx == bd.end_idx:
                        hor_dir = NODE_DIR_LEFT
                    else:
                        hor_dir = NODE_DIR_LEFT | NODE_DIR_RIGHT

                    for (
                        cross_bd
                    ) in vert_borders:  # проверяем все перпендикулярные направляющие на пересечение в текущей точке
                        if cross_bd.guideline_idx == m_idx:  # есть вероятность пересечения
                            if cross_bd.start_idx == bd.guideline_idx:
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= (
                                    hor_dir | NODE_DIR_DOWN
                                )  # в этом узле есть пересечение
                            elif cross_bd.end_idx == bd.guideline_idx:
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= (
                                    hor_dir | NODE_DIR_UP
                                )  # в этом узле есть пересечение
                            elif cross_bd.start_idx < bd.guideline_idx < cross_bd.end_idx:
                                nodes[bd.guideline_idx][cross_bd.guideline_idx] |= (
                                    hor_dir | NODE_DIR_DOWN | NODE_DIR_UP
                                )  # в этом узле есть пересечение
                    m_idx += 1

        # Пятый этап: распознание текста в найденных прямоугольных областях и заполнение таблицы
        for rdx in range(len(hori)):
            for cdx in range(len(vert)):
                node = nodes[rdx][cdx]
                if (node & NODE_DIR_RIGHT) and (node & NODE_DIR_DOWN):  # найден стартовый узел
                    for cdx2 in range(cdx + 1, len(vert)):  # обходим следующие узлы по горизонтали
                        if nodes[rdx][cdx2] & NODE_DIR_DOWN:  # найден верхний правый узел
                            for rdx2 in range(
                                rdx + 1, len(hori)
                            ):  # обходим следующие узлы по вертикали по правой стороне
                                # типа оптимистический вариант, без вложенных областей
                                if nodes[rdx2][cdx2] & NODE_DIR_LEFT:  # найден нижний правый узел
                                    rc = fitz.Rect([vert[cdx], hori[rdx], vert[cdx2], hori[rdx2]]) / rm
                                    recttext = page.get_text("text", clip=rc).rstrip()
                                    recttext = re.sub(r'\s+', ' ', recttext)
                                    if (rdx2 > rdx + 1) or (cdx2 > cdx + 1):
                                        worksheet.merge_range(
                                            start_row + rdx, cdx, start_row + rdx2 - 1, cdx2 - 1, recttext, cell_format
                                        )
                                    else:
                                        worksheet.write_string(start_row + rdx, cdx, recttext, cell_format)
                                    # worksheet.write_string(rdx, cdx, f'R{rdx}C{cdx}:R{rdx2}C{cdx2}')
                                    break
                            break
    else:  # упрощенный режим - шинковка по направляющим, без учета "объединенности" ячеек
        words = page.get_text("words")  # список слов на странице
        # переводим в "экранные" координаты
        transwords = []
        for w in words:
            rc = fitz.Rect(w[:4]) * rm
            transwords.append((rc.x0, rc.y0, rc.x1, rc.y1, w[4], w[5], w[6], w[7]))

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


def parse_tables(doc, xlsfile: str, strong: bool = True):
    """Анализ и разбор табличных данных на всех страницах файла PDF и сохранение их в файл XLSX

    Args:
        doc (object): файл PDF (объект fitz document)
        xlsfile (str): имя сохраняемого файла XLSX
        strong (bool): True - режим строгого поиска разметки таблицы,
                       False - упрощенное дробление таблицы на сетку по найденным направляющим

    Returns:
        int: количество добавленных в файл XLSX строк
    """
    workbook = xlsxwriter.Workbook(xlsfile)
    worksheet = workbook.add_worksheet()

    cell_format = workbook.add_format()
    cell_format.set_align('center')
    cell_format.set_align('vcenter')
    cell_format.set_text_wrap()
    cell_format.set_border(1)
    # worksheet.set_column(0, 0, 7)
    # worksheet.write_row(0, 0, ("Код","Объем"))

    start_row = 0
    # noinspection PyTypeChecker
    for pno in range(len(doc)):
        start_row += parse_page_tables(doc[pno], worksheet, start_row, cell_format, strong)

    # worksheet.freeze_panes(1, 0)
    # worksheet.autofilter(0, 0, row_num, 3)
    workbook.close()
    return start_row


# if __name__ == "__main__":
#     # doc = fitz.open(r"1-0002.pdf")
#     # doc = fitz.open(r"f:\PythonProjects\PdfTools64\vypisdata\pd1.pdf")
#     # doc = fitz.open(r"f:\PythonProjects\PdfTools64\vypisdata\pdffile2.pdf")
#     # doc = fitz.open("2022_список.pdf")
#     # doc = fitz.open("2023_список.pdf")
#     # doc = fitz.open(r"f:\PythonProjects\PdfTools64\vypisdata\pdffile1.pdf")
#     doc = fitz.open(r"f:\PythonProjects\PdfTools64\source2\Колонка Подзь февраль 2023.pdf")
#     fitz.Tools().set_small_glyph_heights(True)
#     if not parse_tables(doc, 'output.xlsx', False):
#         print('Ничо нетуть')
