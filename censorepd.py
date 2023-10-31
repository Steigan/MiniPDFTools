"""
Этот файл содержит функции для обработки деперсонификации ПД
"""

import io
import logging
import os
import re
from itertools import groupby

import fitz
from PIL import Image as PILImage
from PIL import ImageDraw
from PIL import ImageOps
from pyzbar.pyzbar import decode
from pyzbar.wrapper import ZBarSymbol

from params import SaveParams


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'log.log'))
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)


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

    page = doc[pno]  # обрабатываемая страница документа
    anon_rects = []  # список участков с персональными данными
    qr_txt = ''  # Для текста из банковского QR кода

    # Перебираем все картинки на странице в поисках QR кода
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

        # Загружаем картинку в Pillow
        img = PILImage.open(temp)

        # Левый верхний пиксель изображения черный??? Тогда инвертируем цвета
        if img.getpixel(xy=(0, 0)) == 0:
            img = ImageOps.invert(img)

        # Распознаем QR коды
        decocde_qr = decode(img, [ZBarSymbol.QRCODE])

        # Обходим все распознанные QR коды
        for qr_obj in decocde_qr:
            txt = qr_obj.data.decode('utf-8')
            # Это банковский QR код?
            if txt.startswith('ST00012|'):
                if not qr_txt:  # сохраняем первый попавшийся
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

    fio_keywords = []  # список ключевых слов из ФИО
    addr_keywords = []  # список ключевых слов из адреса

    # Хоть один банковский QR код найден?
    if qr_txt:
        # Выделяем ключевые слова из ФИО
        try:
            fio_keywords = [w for w in re.search(r'\|lastName=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
        except (TypeError, ValueError):
            fio_keywords = []
        # Выделяем ключевые слова из адреса
        try:
            addr_keywords = [w for w in re.search(r'\|payerAddress=([^|]*)', qr_txt)[1].split(' ') if len(w) > 3]
        except (TypeError, ValueError):
            addr_keywords = []

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # !!! Документ ПД КТК формируется в портретном положении листа А4 корешком вниз !!!
    # !!! отсчет координат обычный - от угла сверху слева                           !!!
    # !!! page.rect.width - это ширина с учетом поворота страницы на 90, поэтому в  !!!
    # !!!                   исходных координатах это высота                         !!!
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    # находим примерный центр страницы документа
    vert_center = page.rect.width // 2
    hor_center = page.rect.height // 2

    # Получаем список слов на странице с их координатами
    words = page.get_text("words")

    # Переменные для fitz.Rect областей с соответствующими словами
    rect_ls = rect_period = rect_kuda = rect_kogo = None
    # Список fitz.Rect областей, содержащих части ФИО и адреса
    rects_fio_addr = []

    # Обходим список слов на странице
    for w in words:
        if w[4] in fio_keywords or w[4] in addr_keywords:  # это часть имени или адреса
            r = fitz.Rect(w[:4])
            rects_fio_addr.append(r)  # добавляем в общий список все похожие варианты
        if w[4] == 'КУДА:':  # это корешок с адресом доставки
            rect_kuda = fitz.Rect(w[:4])
        if w[4] == 'КОГО:':  # это корешок с отправителем
            rect_kogo = fitz.Rect(w[:4])
        if w[4] == 'л.с':  # это л/с в разделе показаний ИПУ
            rect_ls = fitz.Rect(w[:4])
        if w[4] == 'период:':  # это период в разделе показаний ИПУ
            rect_period = fitz.Rect(w[:4])

    if rect_kuda and rect_kogo:  # почтовый корешок найден
        # Определяем примерные границы области, в которой находится адрес доставки
        hght = rect_kuda.y1 - rect_kogo.y1 - 0
        lft = 100

        rect_kuda.y0 = rect_kuda.y1 - hght
        rect_kuda.x1 = rect_kuda.x0 - 1
        rect_kuda.x0 = lft
        # Сохраняем область, в которой находится адрес доставки
        anon_rects.append((rect_kuda, 'POST'))

    if rect_ls and rect_period:  # раздел ИПУ найден
        # Определяем примерные границы области, в которой находится ФИО в разделе ИПУ
        rect_ls.y0 = rect_period.y1 + 1
        rect_ls.x1 += 1
        rect_ls.y1 += 1
        # Сохраняем область, в которой находится адрес доставки
        anon_rects.append((rect_ls, 'IPU'))

    def rectsort_x0_key(x):  # функция сортировки областей (по левому X)
        return x.x0

    # Переменные для fitz.Rect областей с соответствующими словами
    rect_fio1 = rect_fio2 = rect_addr1 = rect_addr2 = None

    left_fioaddr_ind = 0  # статус обнаружения ФИО/Адр слева (0-нет, 1-нашли первую область, 2-нашли обе)
    right_fioaddr_ind = 0  # статус обнаружения ФИО/Адр справа (0-нет, 1-нашли первую область, 2-нашли обе)

    # Определяем максимум по Y: если найдена область "от кого",
    # то берем минимальный Y для этой области (над надписью "от кого"),
    # иначе берем весь лист
    if rect_kogo:
        max_y = min(rect_kogo.y0, rect_kogo.y1)
    else:
        max_y = 1000

    # Сортируем области по их левому X
    rects_fio_addr.sort(key=rectsort_x0_key)
    # Группируем области по их левому X и обходим
    for grp, items in groupby(rects_fio_addr, key=rectsort_x0_key):
        # Создаем новую область с заданным левым X
        r = fitz.Rect(grp, 1000, 0, 0)

        # Обходим все имеющиеся варианты остальных координат
        # в результате чего:
        # - верхний Y будет равен наименьшему Y
        # - нижний Y будет равен наибольшему Y
        # - правый X будет равен последнему попавшемуся правому X (они все равны в ПД КТК)
        for item in items:
            r.y0 = min(r.y0, item.y0, item.y1)
            r.y1 = max(r.y1, item.y0, item.y1)
            r.x1 = item.x1

        # Левый X находится на правой половине листа А4? - тогда область не нужна
        if r.x0 > hor_center:
            continue

        # Нижний Y находится на нижней половине листа, верхний Y внизу в пределах листа?
        if (r.y1 > vert_center) and (r.y0 < max_y):
            # это левая сторона печатного варианта ПД КТК
            if left_fioaddr_ind == 0:
                # нашли первую область ФИО/Адр - ФИО слева
                left_fioaddr_ind = 1
                r.x1 += 1  # увеличиваем область на 1 влево
                r.y0 -= 20  # увеличиваем область на 20 вверх
                r.y1 += 20  # увеличиваем область на 20 вниз
                rect_fio1 = r

            elif left_fioaddr_ind == 1:
                # нашли вторую область ФИО/Адр - Адр слева
                left_fioaddr_ind = 2
                r.x1 += 1  # увеличиваем область на 1 влево
                r.y0 -= 20  # увеличиваем область на 20 вверх
                r.y1 += 20  # увеличиваем область на 20 вниз
                # выравниваем ФИО и Адр в ровный столбик
                r.y0 = min(r.y0, rect_fio1.y0)
                r.y1 = max(r.y1, rect_fio1.y1)
                rect_fio1.y0 = r.y0
                rect_fio1.y1 = r.y1
                rect_addr1 = r

        else:  # Нижний Y находится на верхней половине листа или верхний Y внизу за пределами листа
            # это правая сторона печатного варианта ПД КТК
            if right_fioaddr_ind == 0:
                # нашли первую область ФИО/Адр - ФИО справа
                right_fioaddr_ind = 1
                r.x1 += 1  # увеличиваем область на 1 влево
                r.y0 -= 20  # увеличиваем область на 20 вверх
                r.y1 += 20  # увеличиваем область на 20 вниз
                rect_fio2 = r

            elif right_fioaddr_ind == 1:
                # нашли вторую область ФИО/Адр - Адр справа
                right_fioaddr_ind = 2
                r.x1 += 1  # увеличиваем область на 1 влево
                r.y0 -= 20  # увеличиваем область на 20 вверх
                r.y1 += 20  # увеличиваем область на 20 вниз
                # выравниваем ФИО и Адр в ровный столбик
                r.y0 = min(r.y0, rect_fio2.y0)
                r.y1 = max(r.y1, rect_fio2.y1)
                rect_fio2.y0 = r.y0
                rect_fio2.y1 = r.y1
                rect_addr2 = r

    # Добавляем обнаруженные и обработанные области в общий список
    if rect_fio1:
        anon_rects.append((rect_fio1, 'FIO'))
    if rect_fio2:
        anon_rects.append((rect_fio2, 'FIO'))
    if rect_addr1:
        anon_rects.append((rect_addr1, 'ADDR'))
    if rect_addr2:
        anon_rects.append((rect_addr2, 'ADDR'))

    # Словарь для значений чекбоксов из настроек по каждой категории персданных
    check_dict = {
        'FIO': param.censore_fio,
        'ADDR': param.censore_addr,
        'POST': param.censore_post,
        'IPU': param.censore_ipu,
        'QR': param.censore_qr,
    }

    # Если не выделяем области, а формируем картинку
    if not param.setselectionsonly:
        zoom = param.dpi / 72  # зум-фактор для растеризации изображения
        mat = fitz.Matrix(zoom, zoom)  # матрица трансформирования для растеризации изображения
        pixelator = param.dpi // 20  # коэффициент пикселизации конфиденциальной информации

        # Растеризуем страницу и запихиваем изображение в PIL
        pix = page.get_pixmap(matrix=mat)
        pix.set_dpi(param.dpi, param.dpi)
        img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)

    # Пробегаем по всем найденным областям
    for anon_rect in anon_rects:
        # Если в настройках обработка такого типа данных не включена, то continue
        if not check_dict[anon_rect[1]]:
            continue

        # Если просто выделяем области, а не формируем картинку, запускаем callback
        if param.setselectionsonly:
            if add_selection_callback is not None:
                add_selection_callback(pno, anon_rect[0])
            continue

        # Трансформируем координаты в масштаб изображения
        r = anon_rect[0] * page.rotation_matrix * mat
        # Замазываем участок
        censore_img(img, r, pixelator, param.censore)

    # Если просто выделяем области, а не формируем картинку, выходим с None
    if param.setselectionsonly:
        return None

    # Обратно конвертируем картинку в формат fitz.Pixmap и возвращаем...
    samples = img.tobytes()
    pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)
    return pix


def censore_img(img: PILImage.Image, rect, pixelator: int, mode: int = 1):
    """Замазать участок изображения

    Args:
        img (PILImage.Image): изображение
        rect (fitz.Rect): область для "деперсонификации"
        pixelator (int): коэффициент пикселизации
        mode (int, optional): режим 1-пикселизация, 2 или др.-заливка белым. По умолчанию 1.
    """
    rect.x0 = int(rect.x0)
    rect.x1 = int(rect.x1)
    rect.y0 = int(rect.y0)
    rect.y1 = int(rect.y1)
    if mode == 1:
        # Пикселизация: вырезаем, уменьшаем (теряя детализацию), обратно увеличиваем и вставляем на место
        crop_img = img.crop(rect)
        img_small = crop_img.resize((crop_img.size[0] // pixelator, crop_img.size[1] // pixelator))
        blur_image = img_small.resize(crop_img.size, PILImage.NEAREST)
        img.paste(blur_image, rect)
    else:
        # Заливка белым
        draw = ImageDraw.Draw(img)
        draw.rectangle(rect, fill=(255, 255, 255, 0))
