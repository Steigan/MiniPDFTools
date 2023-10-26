"""
Этот файл содержит функции для обработки деперсонификации ПД
"""

import io
import re
from itertools import groupby

import fitz
from PIL import Image as PILImage
from PIL import ImageDraw
from PIL import ImageOps
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol

from params import SaveParams


def censore_page(doc, pno: int, param: SaveParams, add_selection_callback=None):  # noqa: ignore=C901
    """Деперсонификация одной страницы файла PDF

    Args:
        doc (fitz doc): документ PDF
        pno (int): индекс обрабатываемой страницы
        param (SaveParams): параметры сохранения файла (в том числе setselectionsonly)
        add_selection_callback (func): функция добавления выделений, ей передаются индекс страницы и область Rect

    Returns:
        (Pixmap) или None: результат рендеринга и деперсонификации
    """

    zoom = param.dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pixelator = param.dpi // 20
    page = doc[pno]
    anon_rects = []
    fio = []
    addr = []

    for docimg in doc.get_page_images(pno, full=True):
        # docimg[2] и docimg[3] - это ширина и высота изображения в исходных пикселях
        # shrink - матрица сжатия исходного изображения
        shrink = fitz.Matrix(1 / docimg[2], 0, 0, 1 / docimg[3], 0, 0)
        # imgrect = fitz.Rect(0, 0, docimg[2], docimg[3])

        # bbox - положение изображения в координатах PDF
        # transform - матрица для перевода координат внутри исходного изображения во
        #             "внешние" координаты страницы PDF
        _, transform = page.get_image_bbox(docimg, transform=True)

        # Выделяем изображение и запихиваем его в PIL

        # Перестало работать в версии PyMuPDF-1.22.0...
        # image = doc.extract_image(docimg[0])

        # Вариант для версии PyMuPDF-1.22.0...
        pix = fitz.Pixmap(doc, docimg[0])
        temp = io.BytesIO(pix.tobytes())

        img = PILImage.open(temp)

        # Левый верхний пиксель изображения черный??? Тогда инвертируем цвета
        if img.getpixel(xy=(0, 0)) == 0:
            img = ImageOps.invert(img)
        # Распознаем QR коды
        decocde_qr = decode(img, [ZBarSymbol.QRCODE])
        qr_txt = ''
        fio = []
        addr = []
        # Обходим все распознанные QR коды
        for qr_obj in decocde_qr:
            txt = qr_obj.data.decode('utf-8')
            # Это банковский QR код?
            if txt.startswith('ST00012|'):
                if not qr_txt:
                    qr_txt = txt

                # Расширяем границы QR (в исходных координатах изображения)
                r = fitz.Rect(
                    qr_obj.rect.left,
                    qr_obj.rect.top,
                    qr_obj.rect.left + qr_obj.rect.width,
                    qr_obj.rect.top + qr_obj.rect.height,
                ) + fitz.Rect(-3, -3, 4, 4)

                # Переводим в координаты PDF
                r = r * shrink * transform

                # Добавляем QR КОД в список скрываемых полей
                anon_rects.append([r, 'QR'])

        # Хоть один банковский QR код найден?
        if qr_txt:
            # Выделяем ключевые слова из ФИО
            try:
                fio = [w for w in re.search(r'\|lastName=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
            except (TypeError, ValueError):
                fio = []
            # Выделяем ключевые слова из адреса
            try:
                addr = [w for w in re.search(r'\|payerAddress=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
            except (TypeError, ValueError):
                addr = []
            # print(fio, addr)

    # !!! page.rect.width - это ширина с учетом поворота страницы !!!
    hcenter = page.rect.width // 2
    vcenter = page.rect.height // 2
    # print(hcenter, vcenter)

    # Получаем список слов на странице с их координатами
    words = page.get_text("words")

    r_ls = r_period = r_kuda = r_kogo = None
    r_fio_addr = []
    # rFIO = []
    r_fio_grpd = []
    # rAddr = []
    r_addr_grpd = []

    # Обходим список слов на странице
    for w in words:
        # if w[4] in fio:
        #     r = fitz.Rect(w[:4])
        #     rFIO.append(r)
        # if w[4] in addr:
        #     r = fitz.Rect(w[:4])
        #     rAddr.append(r)
        if w[4] in fio or w[4] in addr:
            r = fitz.Rect(w[:4])
            r_fio_addr.append(r)
        if w[4] == 'КУДА:':
            r_kuda = fitz.Rect(w[:4])
        if w[4] == 'КОГО:':
            r_kogo = fitz.Rect(w[:4])
        if w[4] == 'л.с':
            r_ls = fitz.Rect(w[:4])
        if w[4] == 'период:':
            r_period = fitz.Rect(w[:4])

    if r_kuda and r_kogo:
        hght = r_kuda.y1 - r_kogo.y1 - 0
        lft = 100

        r_kuda.y0 = r_kuda.y1 - hght
        r_kuda.x1 = r_kuda.x0 - 1
        r_kuda.x0 = lft
        anon_rects.append([r_kuda, 'POST'])

    if r_ls and r_period:
        r_ls.y0 = r_period.y1 + 1
        r_ls.x1 += 1
        r_ls.y1 += 1
        anon_rects.append([r_ls, 'IPU'])

    def rectsort_x0_key(x):
        return x.x0

    left_fio_ind = 1
    right_fio_ind = 1
    max_y = 1000
    if r_kogo:
        max_y = min(r_kogo.y0, r_kogo.y1)

    r_fio_addr.sort(key=rectsort_x0_key)
    for grp, items in groupby(r_fio_addr, key=rectsort_x0_key):
        r = fitz.Rect(grp, 1000, 0, 0)
        for item in items:
            r.y0 = min(r.y0, item.y0, item.y1)
            r.y1 = max(r.y1, item.y0, item.y1)
            r.x1 = item.x1
        if r.x0 < vcenter:
            if (r.y1 > hcenter) and (r.y0 < max_y):
                if left_fio_ind == 1:
                    r_fio_grpd.append(r)
                    left_fio_ind = 2
                elif left_fio_ind == 2:
                    r_addr_grpd.append(r)
                    left_fio_ind = 0
            else:
                if right_fio_ind == 1:
                    r_fio_grpd.append(r)
                    right_fio_ind = 2
                elif right_fio_ind == 2:
                    r_addr_grpd.append(r)
                    right_fio_ind = 0

    is_do_addr = False
    if len(r_fio_grpd) > 0:
        r = fitz.Rect(r_fio_grpd[0])
        if len(r_addr_grpd) > 0:
            r.y0 = min(r.y0, r_addr_grpd[0].y0)
            r.y1 = max(r.y1, r_addr_grpd[0].y1)
            is_do_addr = True
        r.y0 -= 20
        r.y1 += 20
        r.x1 += 1
        anon_rects.append([fitz.Rect(r), 'FIO'])

    if is_do_addr:
        # noinspection PyUnboundLocalVariable
        r.x0 = r_addr_grpd[0].x0
        r.x1 = r_addr_grpd[0].x1 + 1
        anon_rects.append([fitz.Rect(r), 'ADDR'])
    elif len(r_addr_grpd) > 0:
        r = fitz.Rect(r_addr_grpd[0])
        r.y0 -= 20
        r.y1 += 20
        r.x1 += 1
        anon_rects.append([fitz.Rect(r), 'ADDR'])

    is_do_addr = False
    if len(r_fio_grpd) > 1:
        r = r_fio_grpd[1]
        if len(r_addr_grpd) > 1:
            r.y0 = min(r.y0, r_addr_grpd[1].y0)
            r.y1 = max(r.y1, r_addr_grpd[1].y1)
            is_do_addr = True
        r.y0 -= 20
        r.y1 += 20
        r.x1 += 1
        anon_rects.append([fitz.Rect(r), 'FIO', False])

    if is_do_addr:
        r.x0 = r_addr_grpd[1].x0
        r.x1 = r_addr_grpd[1].x1 + 1
        anon_rects.append([fitz.Rect(r), 'ADDR'])
    elif len(r_addr_grpd) > 1:
        r = fitz.Rect(r_addr_grpd[1])
        r.y0 -= 20
        r.y1 += 20
        r.x1 += 1
        anon_rects.append([fitz.Rect(r), 'ADDR'])

    md_list = ['FIO', 'ADDR', 'POST', 'IPU', 'QR']
    chks_list = [param.censore_fio, param.censore_addr, param.censore_post, param.censore_ipu, param.censore_qr]

    if not param.setselectionsonly:
        # Растеризуем страницу и запихиваем изображение в PIL
        pix = page.get_pixmap(matrix=mat)
        pix.set_dpi(param.dpi, param.dpi)
        img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)

    for anon_rect in anon_rects:
        if chks_list[md_list.index(anon_rect[1])]:
            if param.setselectionsonly and (add_selection_callback is not None):
                add_selection_callback(pno, anon_rect[0])
            else:
                # noinspection PyTypeChecker
                r = anon_rect[0] * page.rotation_matrix * mat
                try:
                    r.x0 = int(r.x0)
                    r.x1 = int(r.x1)
                    r.y0 = int(r.y0)
                    r.y1 = int(r.y1)

                    if param.censore == 1:
                        crop_img = img.crop(r)
                        img_small = crop_img.resize((crop_img.size[0] // pixelator, crop_img.size[1] // pixelator))
                        blur_image = img_small.resize(crop_img.size, PILImage.NEAREST)
                        img.paste(blur_image, r)
                    else:
                        draw = ImageDraw.Draw(img)
                        draw.rectangle(r, fill=(255, 255, 255, 0))

                except Exception:
                    pass

    if param.setselectionsonly:
        return None

    samples = img.tobytes()
    pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)
    return pix
