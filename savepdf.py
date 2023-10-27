"""
Этот файл содержит функции для сохранения файла PDF
(с возможностью деперсонификации выделенных областей)
"""

import io
import logging
import os
import shutil

import fitz
from PIL import Image as PILImage
from PIL import ImageDraw
from PySide2.QtWidgets import QMessageBox

from censorepd import censore_page

# from mainwindow import MainWindow
from params import FileFormat
from params import PageMode
from params import PageRotation
from params import SaveParams


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler('log.log')
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)


def check_new_file(
    outfile: str, ext: str, ind: int, overwrite_all: bool, overwrite_msg_callback=None
) -> (str, bool, bool):
    """Проверка на существование файла с индексом ind, если такой уже есть, то
    вывод сообщения с четырьмя вариантами ответа Да-Да для всех-Нет-Отмена

    Возвращает: имя файла, признак "перезаписывать все без запроса", признак прекращения
    """
    # Формируем имя нового файла - к outfile добавляем число ind и расширение
    if ind < 10000:
        fn = f'{outfile}-%04i{ext}' % ind
    else:
        fn = f'{outfile}-{ind}{ext}'

    # Если не установлен признак "перезаписывать все без запроса", то проверяем существование файла
    if not overwrite_all and os.path.exists(fn):
        # Вызываем callback функцию для вывода сообщения с четырьмя вариантами ответа Да-Да для всех-Нет-Отмена
        if overwrite_msg_callback is not None:
            res = overwrite_msg_callback(fn)
        else:
            res = QMessageBox.StandardButton.No

        # Если пропуск файла или прекращение, то возвращаем пустое имя файла
        if res in (QMessageBox.StandardButton.No, res == QMessageBox.StandardButton.Cancel):
            fn = ''

        # Возвращаем имя файла, признак "перезаписывать все без запроса", признак прекращения
        return fn, (res == QMessageBox.StandardButton.YesToAll), (res == QMessageBox.StandardButton.Cancel)

    # Возвращаем имя файла, без изменения признак "перезаписывать все без запроса", признак прекращения False
    return fn, overwrite_all, False


def saveas_process(  # noqa: ignore=C901
    wnd,
    pdf_view,
    page_ranges: list,
    ranges_page_count: int,
    outfile: str,
    ext: str,
    p: SaveParams,
    censore: bool,
    progress_callback=None,
    overwrite_msg_callback=None,
) -> bool:
    """Сохранение файла/файлов с деперсонификацией данных или без"""

    # Имя файла не выбрано, страницы не выбраны
    if (not outfile) or (not ext) or (not ranges_page_count):
        return False

    # Если сохраняем в графический формат, либо стоит галка "разбивать по страницам", то m_singles=True
    if p.format in (FileFormat.FMT_JPEG, FileFormat.FMT_PNG):
        m_singles = True
    else:
        m_singles = p.singles

    # Объект fitz с документом
    doc = pdf_view.doc

    # Эксклюзивный вариант - когда пересохраняется существующий файл целиком в исходном формате
    # (например, необходимо только повернуть страницы)
    if (
        pdf_view.is_real_file
        and p.format == FileFormat.FMT_PDF
        and p.pgmode == PageMode.PG_ALL
        and (not m_singles)
        and doc.can_save_incrementally()
    ):
        # Копируем исходный файл в файл с новым именем
        shutil.copyfile(pdf_view.current_filename, outfile)

        # noinspection PyUnresolvedReferences
        doc = fitz.open(outfile)
        if doc.needs_pass:
            doc.authenticate(pdf_view.psw)
        for pno in range(ranges_page_count):
            # if p.rotation != PageRotation.rtNone:
            # Пытаемся повернуть страницу в соответствии с отображаемым на экране объектом
            doc[pno].set_rotation((pdf_view.doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)

            # Вызываем callback функцию для обновления прогрессбара
            if progress_callback is not None:
                progress_callback(pno * 95 // ranges_page_count)
        try:
            doc.save(
                outfile, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
            )  # , garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
        except Exception as e:
            QMessageBox.critical(wnd, wnd.title, f"Ошибка: {e}")
            doc.close()
            # shutil. copyfile(wnd.m_currentFileName, outfile)
            return False
        doc.close()
        return True

    zoom = p.dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    if p.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG) and not m_singles:
        # noinspection PyUnresolvedReferences
        pdfout = fitz.open()
    ind = 0

    pixelator = p.dpi // 20
    overwrite_all = False
    for pages in page_ranges:
        for pno in pages:
            if 0 <= pno < doc.page_count:
                ind += 1

                # Вызываем callback функцию для обновления прогрессбара
                if progress_callback is not None:
                    progress_callback(ind * 100 // ranges_page_count)

                old_rot = doc[pno].rotation
                if p.rotation != PageRotation.RT_NONE:
                    doc[pno].set_rotation((doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)

                try:
                    if p.format == FileFormat.FMT_PDF:
                        if m_singles:
                            # noinspection PyUnresolvedReferences
                            newdoc = fitz.open()
                            newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

                            fn, overwrite_all, abort = check_new_file(
                                outfile, ext, ind, overwrite_all, overwrite_msg_callback
                            )
                            if abort:
                                raise FileNotFoundError('Файл для записи не определен')
                            if fn:
                                try:
                                    newdoc.save(
                                        fn, garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True
                                    )
                                except Exception as e:
                                    if not wnd.show_save_error_msg(e):
                                        newdoc.close()
                                        raise
                            newdoc.close()
                        else:
                            # noinspection PyUnboundLocalVariable
                            pdfout.insert_pdf(doc, from_page=pno, to_page=pno)
                            # pg = pdfout[pdfout.page_count - 1]
                            # print(pg.rotation)
                            # new_rotation = (0, 270, 90, 180)[p.rotation.value]
                            # pg.set_rotation(new_rotation)

                    else:
                        page = doc[pno]
                        if censore:
                            pix = censore_page(doc=doc, pno=pno, param=p)
                        else:
                            # Растеризуем страницу и запихиваем изображение в PIL
                            pix = page.get_pixmap(matrix=mat)
                            pix.set_dpi(p.dpi, p.dpi)

                            if p.censore:
                                sels = [sel for sel in pdf_view.selections_all if (sel.pno == -1 or sel.pno == pno)]
                                if len(sels) > 0:
                                    img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)
                                    page_r = fitz.Rect(0, 0, pix.width, pix.height)
                                    for sel in sels:
                                        r = (
                                            pdf_view.get_selection_fitz_rect(pno, old_rot, sel)
                                            * page.rotation_matrix
                                            * mat
                                        )
                                        if page_r.contains(r):
                                            # print(r)
                                            try:
                                                r.x0 = int(r.x0)
                                                r.x1 = int(r.x1)
                                                r.y0 = int(r.y0)
                                                r.y1 = int(r.y1)
                                                if p.censore == 1:
                                                    crop_img = img.crop(r)
                                                    img_small = crop_img.resize(
                                                        (crop_img.size[0] // pixelator, crop_img.size[1] // pixelator)
                                                    )
                                                    blur_image = img_small.resize(crop_img.size, PILImage.NEAREST)
                                                    img.paste(blur_image, r)
                                                else:
                                                    draw = ImageDraw.Draw(img)
                                                    draw.rectangle(r, fill=(255, 255, 255, 0))
                                            except Exception:
                                                pass
                                    samples = img.tobytes()
                                    pix = fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)

                        if p.format == FileFormat.FMT_PDF_JPEG:
                            temp = io.BytesIO()
                            pix.pil_save(temp, format="jpeg", quality=p.quality)
                            if m_singles:
                                # noinspection PyUnresolvedReferences
                                newdoc = fitz.open()
                                opage = newdoc.new_page(width=page.rect.width, height=page.rect.height)
                                opage.insert_image(opage.rect, stream=temp)

                                fn, overwrite_all, abort = check_new_file(
                                    outfile, ext, ind, overwrite_all, overwrite_msg_callback
                                )
                                if abort:
                                    raise FileNotFoundError('Файл для записи не определен')
                                if fn:
                                    try:
                                        newdoc.save(
                                            fn,
                                            garbage=4,
                                            clean=True,
                                            deflate=True,
                                            deflate_images=True,
                                            deflate_fonts=True,
                                            encryption=fitz.PDF_ENCRYPT_KEEP,
                                        )
                                    except Exception as e:
                                        if not wnd.show_save_error_msg(e):
                                            newdoc.close()
                                            raise

                                newdoc.close()
                            else:
                                opage = pdfout.new_page(width=page.rect.width, height=page.rect.height)
                                opage.insert_image(opage.rect, stream=temp)
                        else:
                            fn, overwrite_all, abort = check_new_file(
                                outfile, ext, ind, overwrite_all, overwrite_msg_callback
                            )
                            if abort:
                                raise FileNotFoundError('Файл для записи не определен')
                            if fn:
                                try:
                                    if p.format == FileFormat.FMT_JPEG:
                                        pix.pil_save(fn, format="jpeg", quality=p.quality)
                                    else:
                                        pix.pil_save(fn, format="png")
                                except Exception as e:
                                    if not wnd.show_save_error_msg(e):
                                        raise
                except Exception:
                    logger.error('', exc_info=True)
                    # Вертаем поворот страницы взад
                    if p.rotation != PageRotation.RT_NONE:
                        doc[pno].set_rotation(old_rot)
                    return False

                if p.rotation != PageRotation.RT_NONE:
                    doc[pno].set_rotation(old_rot)

    if p.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG) and not m_singles:
        try:
            pdfout.save(
                outfile,
                garbage=4,
                clean=True,
                deflate=True,
                deflate_images=True,
                deflate_fonts=True,
                encryption=fitz.PDF_ENCRYPT_KEEP,
            )
        except Exception as e:
            QMessageBox.critical(wnd, wnd.title, f"Ошибка: {e}")
            pdfout.close()
            return False
        pdfout.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)
    return True
