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
    """Экспорт рееста ПД в XLSX

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

    workbook = xlsxwriter.Workbook(xlsfile)

    cell_format = workbook.add_format()
    cell_format.set_align('center')
    cell_format.set_align('vcenter')
    cell_format.set_text_wrap()
    cell_format.set_border(1)

    worksheet = workbook.add_worksheet('Свод')
    worksheet_det = workbook.add_worksheet('Детально')
    worksheet_det.set_column(0, 0, 10)
    worksheet_det.set_column(1, 1, 60)
    worksheet_det.write_row(0, 0, ("Страница файла PDF", "Адрес доставки"), cell_format)
    if recognize_qr:
        worksheet_det.set_column(2, 2, 110)
        worksheet_det.write_string(0, 2, "Информация из QR кода", cell_format)

    # Тест переноса дат в Эксель
    # worksheet_det.write_datetime(0, 3, datetime.date(2023, 6, 30), cell_format)
    # worksheet_det.write_datetime(0, 4, datetime.date(1900, 1, 1), cell_format)
    # worksheet_det.write_datetime(0, 4, datetime.date(1900, 2, 29), cell_format) - такая дата
    # есть только в Экселе и т.п. программах (наследство от Лотуса)

    pgcount = len(doc)

    np_list = []
    old_np = ""
    np_start_pg = 0
    ii = 0

    for current_page in range(pgcount):
        page = doc.load_page(current_page)
        page_text = page.get_text("text")

        ii += 1
        worksheet_det.write(ii, 0, ii, cell_format)

        # if ii == 1:
        #     print(page_text)

        res = re.compile(r'^КУДА: (.*)').search(page_text)
        if res is not None:
            dest = res.group(1)
        else:
            page_lines = page_text.splitlines()
            if page_lines[-1] == 'Куда:':
                dest = page_lines[-4]
            else:
                dest = '----'

        if dest == '----':
            np = "ПД не распознан или в нем ошибка"
            worksheet_det.write_string(ii, 1, np, cell_format)
        else:
            worksheet_det.write_string(ii, 1, dest, cell_format)
            np = re.compile(r'[^,]*').search(dest + ",").group(0)
            np = np.replace('ё', 'е').replace('Ё', 'Е')

        if recognize_qr:
            txt = ''
            for docimg in doc.get_page_images(current_page):
                # xref = docimg[0]
                # width = docimg[2]
                # height = docimg[3]
                # if min(width, height) <= dimlimit:
                #     continue

                # Перестало работать в версии PyMuPDF-1.22.0...
                # image = doc.extract_image(docimg[0])

                # Вариант для версии PyMuPDF-1.22.0...
                pix = fitz.Pixmap(doc, docimg[0])
                temp = io.BytesIO(pix.tobytes())

                img = PILImage.open(temp)

                if img.getpixel(xy=(0, 0)) == 0:
                    img = ImageOps.invert(img)
                decocde_qr = decode(img, [ZBarSymbol.QRCODE])
                for qr_obj in decocde_qr:
                    txt += ('\n-------------------\n' if txt else '') + qr_obj.data.decode('utf-8')
            worksheet_det.write_string(ii, 2, txt, cell_format)

        if np != old_np:
            if old_np:
                np_list.append((old_np, np_start_pg, current_page))

            old_np = np
            np_start_pg = current_page + 1

        if progress_callback is not None:
            progress_callback((current_page + 1) * 98 // pgcount)

    if old_np:
        # noinspection PyUnboundLocalVariable
        np_list.append((old_np, np_start_pg, current_page + 1))

    # print(np_list)
    worksheet_det.freeze_panes(1, 0)
    if recognize_qr:
        worksheet_det.autofilter(0, 0, pgcount, 2)
    else:
        worksheet_det.autofilter(0, 0, pgcount, 1)

    worksheet.set_column(0, 0, 7)
    worksheet.set_column(1, 1, 45)
    worksheet.set_column(2, 2, 20)
    worksheet.set_column(3, 3, 20)
    worksheet.set_column(4, 4, 45)

    worksheet.write_row(
        0, 0, ("№ п/п", "Населенный пункт", "Страницы файла PDF", "Кол-во страниц", "Файл PDF"), cell_format
    )

    fnm = os.path.basename(current_filename)
    ii = 0
    for data in np_list:
        ii += 1
        worksheet.write(ii, 0, ii, cell_format)
        worksheet.write_string(ii, 1, data[0], cell_format)
        worksheet.write_string(ii, 2, f'{data[1]} - {data[2]}', cell_format)
        worksheet.write(ii, 3, data[2] - data[1] + 1, cell_format)
        worksheet.write_string(ii, 4, fnm, cell_format)

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, ii, 3)

    workbook.close()

    if progress_callback is not None:
        progress_callback(100)

    return True
