"""
Этот файл содержит функции для экспорта реестра платежных документов КТК в файл xlsx
"""

import io
import os
import re

import fitz
import xlsxwriter
from PIL import Image as PILImage
from PIL import ImageOps
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol


def export_pd(doc, xlsfile: str, current_filename: str, recognize_qr: bool = True, progress_callback=None):
    """Экспорт реестра ПД в XLSX

    Args:
        doc (object): файл PDF (объект fitz document)
        xlsfile (str): имя сохраняемого файла XLSX
        current_filename (str): имя текущего файла PDF
        recognize_qr (bool): True - распознавать QR коды,
                             False - не распознавать QR коды
        process_callback: callback-функция, которой необходимо передать процент проделанной работы

    Returns:
        bool: успешность выполнения
    """

    # Создаем объект Workbook Excel
    workbook = xlsxwriter.Workbook(xlsfile)

    # Создаем формат ячеек
    cell_format = workbook.add_format()
    cell_format.set_align('center')
    cell_format.set_align('vcenter')
    cell_format.set_text_wrap()
    cell_format.set_border(1)

    # Создаем лист для сводных данных
    worksheet = workbook.add_worksheet('Свод')
    # Задаем ширину и шапку пяти колонок
    worksheet.set_column(0, 0, 7)
    worksheet.set_column(1, 1, 45)
    worksheet.set_column(2, 2, 20)
    worksheet.set_column(3, 3, 20)
    worksheet.set_column(4, 4, 45)
    worksheet.write_row(
        0, 0, ("№ п/п", "Населенный пункт", "Страницы файла PDF", "Кол-во страниц", "Файл PDF"), cell_format
    )

    # Создаем лист для детальных данных
    worksheet_det = workbook.add_worksheet('Детально')
    # Задаем ширину и шапку двух колонок
    worksheet_det.set_column(0, 0, 10)
    worksheet_det.set_column(1, 1, 60)
    worksheet_det.write_row(0, 0, ("Страница файла PDF", "Адрес доставки"), cell_format)
    # Если нужен столбец с расшифровкой QR кода, то задаем ширину и шапку третьей колонки
    if recognize_qr:
        worksheet_det.set_column(2, 2, 110)
        worksheet_det.write_string(0, 2, "Информация из QR кода", cell_format)

    ###########################################################################
    # Тест переноса дат в Эксель
    # worksheet_det.write_datetime(0, 3, datetime.date(2023, 6, 30), cell_format)
    # worksheet_det.write_datetime(0, 4, datetime.date(1900, 1, 1), cell_format)
    # worksheet_det.write_datetime(0, 4, datetime.date(1900, 2, 29), cell_format) - такая дата
    # есть только в Экселе и т.п. программах (наследство от Лотуса)
    ###########################################################################

    page_count = len(doc)  # Количество страниц в файле PDF

    settlements_list = []  # Список обнаруженных населенных пунктов
    prev_settlement = ""  # Наименование предыдущего населенного пункта
    settlement_start_page = 0  # Стартовая страница для текущего населенного пункта
    current_row = 0  # Текущая строка таблицы Excel

    # Обходим все страницы файла PDF
    for current_page in range(page_count):
        # Переходим на следующую строку листа с детальной информацией
        current_row += 1

        # Из текстового слоя очередной страницы берем все содержимое
        page = doc.load_page(current_page)
        page_text = page.get_text("text")

        # Заполняем номер строки по порядку
        worksheet_det.write(current_row, 0, current_row, cell_format)

        # Ищем адрес доставки в самом начале текста (соответствует формату КТК ПД)
        res = re.compile(r'^КУДА: (.*)').search(page_text)
        if res is not None:
            # Если нашли, то выкусываем адрес доставки
            destination = res.group(1)
        else:
            # Иначе ищем адрес доставки в четвертой строке с конца (соответствует формату сводного ПД)
            destination = '----'
            page_lines = page_text.splitlines()
            if len(page_lines) > 3:
                if page_lines[-1] == 'Куда:':
                    destination = page_lines[-4]

        if destination == '----':  # Формат файла не подходит...
            # Заполняем в таблице адрес доставки
            settlement = "ПД не распознан или в нем ошибка"
            worksheet_det.write_string(current_row, 1, settlement, cell_format)
        else:
            # Заполняем в таблице адрес доставки
            worksheet_det.write_string(current_row, 1, destination, cell_format)
            # Выкусываем название населенного пункта
            settlement = re.compile(r'[^,]*').search(destination + ",").group(0)
            settlement = settlement.replace('ё', 'е').replace('Ё', 'Е')

        # Если нужен столбец с расшифровкой QR кода
        if recognize_qr:
            qr_codes = []

            # Перебираем все картинки на странице
            for docimg in doc.get_page_images(current_page):
                # Вариант для версии PyMuPDF-1.22.0...
                pix = fitz.Pixmap(doc, docimg[0])
                temp = io.BytesIO(pix.tobytes())

                # Загружаем картинку в Pillow
                img = PILImage.open(temp)

                # Проверяем цвет первого пикселя, если он черный, то инвертируем изображение
                if img.getpixel(xy=(0, 0)) == 0:
                    img = ImageOps.invert(img)

                # Декодируем код или несколько кодов QR
                decocde_qr = decode(img, [ZBarSymbol.QRCODE])

                # Собираем все полученные расшифровки кодов QR в одну строку
                qr_codes.extend(qr_obj.data.decode('utf-8') for qr_obj in decocde_qr)

            # Заполняем в таблице расшифровки кодов QR
            worksheet_det.write_string(
                current_row, 2, '\n-------------------\n'.join(qr for qr in qr_codes), cell_format
            )

        # Если сменился населенный пункт, то добавляем предыдущий населенный
        # пункт в сводный список (с указанием страниц начала и конца)
        if settlement != prev_settlement:
            if prev_settlement:  # Если это не первая смена НП
                settlements_list.append((prev_settlement, settlement_start_page, current_page))

            # Фиксируем наименование нового населенного пункта и его стартовой страницы
            prev_settlement = settlement
            settlement_start_page = current_page + 1

        # Вызываем callback функцию для обновления прогрессбара
        if progress_callback is not None:
            progress_callback((current_page + 1) * 99 // page_count)

    # Последний населенный пункт (если такой есть) добавляем
    # в сводный список (с указанием страниц начала и конца)
    if prev_settlement:
        settlements_list.append((prev_settlement, settlement_start_page, current_page + 1))

    # Фиксируем верхнюю строку с шапкой и включаем автофильтр
    worksheet_det.freeze_panes(1, 0)
    if recognize_qr:
        worksheet_det.autofilter(0, 0, page_count, 2)
    else:
        worksheet_det.autofilter(0, 0, page_count, 1)

    # Заполняем таблицу со сводной информацией
    fnm = os.path.basename(current_filename)
    current_row = 0
    for data in settlements_list:
        current_row += 1
        worksheet.write(current_row, 0, current_row, cell_format)  # № п/п
        worksheet.write_string(current_row, 1, data[0], cell_format)  # Населенный пункт
        worksheet.write_string(current_row, 2, f'{data[1]} - {data[2]}', cell_format)  # Диапазон страниц
        worksheet.write(current_row, 3, data[2] - data[1] + 1, cell_format)  # Количество страниц
        worksheet.write_string(current_row, 4, fnm, cell_format)  # Имя исходного файла PDF

    # Фиксируем верхнюю строку с шапкой и включаем автофильтр
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, current_row, 3)

    # Сохраняем и закрываем файл XLSX
    workbook.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)

    return True
