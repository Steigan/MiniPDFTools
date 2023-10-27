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
from PySide2.QtWidgets import QMessageBox

from censorepd import censore_img
from censorepd import censore_page

# from mainwindow import MainWindow
from params import FileFormat
from params import PageMode
from params import SaveParams
from siapdfview import SiaPdfView


# Настраиваем логирование
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# настройка обработчика и форматировщика для logger2
handler = logging.FileHandler('log.log')
handler.setFormatter(logging.Formatter('%(name)s %(asctime)s %(levelname)s %(message)s'))

# добавление обработчика к логгеру
logger.addHandler(handler)


def _check_new_file(
    outfile: str, ext: str, ind: int, is_overwrite_all: bool, overwrite_msg_callback=None
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
    if not is_overwrite_all and os.path.exists(fn):
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
    return fn, is_overwrite_all, False


def _saveas_incrementally(pdf_view: SiaPdfView, outfile: str, progress_callback=None, show_error_message_callback=None):
    """Инкрементальный вариант сохранения - когда существующий файл пересохраняется
    сам в себя целиком в исходном формате (когда необходимо только повернуть страницы)
    """
    # Копируем исходный файл в файл с новым именем
    shutil.copyfile(pdf_view.current_filename, outfile)

    # noinspection PyUnresolvedReferences
    doc = fitz.open(outfile)
    if doc.needs_pass:
        doc.authenticate(pdf_view.psw)

    ranges_page_count = len(doc)
    for pno in range(ranges_page_count):
        # Поворачиваем страницу в соответствии с отображаемым на экране объектом
        doc[pno].set_rotation(pdf_view.doc[pno].rotation)

        # Вызываем callback функцию для обновления прогрессбара
        if progress_callback is not None:
            progress_callback(pno * 95 // ranges_page_count)
    try:
        # Сохраняем файл в инкрементальном режиме
        doc.save(
            outfile, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
        )  # , garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
    except Exception as e:
        doc.close()
        if show_error_message_callback is not None:
            show_error_message_callback(e)
        os.remove(outfile)
        return False
    doc.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)
    return True


def _saveas_by_ranges(
    pdf_view: SiaPdfView,
    page_ranges: list,
    ranges_page_count: int,
    outfile: str,
    progress_callback=None,
    show_error_message_callback=None,
):
    """Вариант сохранения по диапазонам - когда файл сохраняется в исходном формате диапазонами страниц
    (например, когда необходимо разделить файл)
    """
    # Объект fitz с документом
    doc = pdf_view.doc

    # Создаем объект fitz Document для нового документа
    pdfout = fitz.open()

    ind = 0  # Счетчик страниц в конечном файле

    # Обходим все объекты range из списка page_ranges
    for page_range in page_ranges:
        # Если это нормальный диапазон (не обратный), то сразу его и переносим в новый документ
        if page_range.step == 1:
            ind += page_range.stop - page_range.start  # Счетчик страниц/файлов в конечном файле
        else:
            ind += page_range.start - page_range.stop  # Счетчик страниц/файлов в конечном файле

        # Копируем диапазон страниц
        pdfout.insert_pdf(doc, from_page=page_range.start, to_page=page_range.stop - page_range.step, final=0)

        # Вызываем callback функцию для обновления прогрессбара
        if progress_callback is not None:
            progress_callback(ind * 97 // ranges_page_count)

    try:
        # Сохраняем новый файл
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
        pdfout.close()
        if show_error_message_callback is not None:
            show_error_message_callback(e)
        return False

    pdfout.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)
    return True


def saveas_process(  # noqa: ignore=C901
    pdf_view: SiaPdfView,
    page_ranges: list,
    ranges_page_count: int,
    outfile: str,
    ext: str,
    param: SaveParams,
    censore: bool,
    progress_callback=None,
    overwrite_msg_callback=None,
    show_error_msg_callback=None,
    show_save_error_msg_callback=None,
) -> bool:
    """Сохранение файла/файлов с деперсонификацией данных или без"""

    # Имя файла не выбрано, страницы не выбраны
    if (not outfile) or (not ext) or (not ranges_page_count):
        return False

    # Если сохраняем в графический формат, либо стоит галка "разбивать по страницам", то m_singles=True
    if param.format in (FileFormat.FMT_JPEG, FileFormat.FMT_PNG):
        m_singles = True
    else:
        m_singles = param.singles

    # Инкрементальный вариант сохранения - когда существующий файл пересохраняется
    # сам в себя целиком в исходном формате (когда необходимо только повернуть страницы)
    if (
        pdf_view.is_real_file
        and param.format == FileFormat.FMT_PDF
        and param.pgmode == PageMode.PG_ALL
        and (not m_singles)
        and pdf_view.doc.can_save_incrementally()
    ):
        # Обрабатываем инкрементальное сохранение и возвращаем результат
        return _saveas_incrementally(pdf_view, outfile, progress_callback, show_error_msg_callback)

    # Вариант сохранения по диапазонам - когда файл сохраняется в исходном формате диапазонами страниц
    # (например, когда необходимо разделить файл)
    if param.format == FileFormat.FMT_PDF and (not m_singles):
        # Обрабатываем подиапазонное сохранение и возвращаем результат
        return _saveas_by_ranges(
            pdf_view, page_ranges, ranges_page_count, outfile, progress_callback, show_error_msg_callback
        )

    # Объект fitz с документом
    doc = pdf_view.doc

    # Если сохраняем целиком файл в формате PDF_JPG, то создаем объект fitz Document (pdfout)
    if param.format == FileFormat.FMT_PDF_JPEG and not m_singles:
        # noinspection PyUnresolvedReferences
        pdfout = fitz.open()

    zoom = param.dpi / 72  # зум-фактор для растеризации изображения
    mat = fitz.Matrix(zoom, zoom)  # матрица трансформирования для растеризации изображения
    pixelator = param.dpi // 20  # коэффициент пикселизации конфиденциальной информации

    is_overwrite_all = False  # признак "перезаписывать все файлы"
    ind = 0  # Счетчик страниц/файлов в конечном файле

    # Обходим все объекты range из списка page_ranges
    for page_range in page_ranges:
        # Обходим все номера страниц из range
        for pno in page_range:
            ind += 1  # Счетчик страниц/файлов в конечном файле

            # Вызываем callback функцию для обновления прогрессбара
            if progress_callback is not None:
                progress_callback(ind * 99 // ranges_page_count)

            ###################################################################
            # Сохраняем файлы в PDF? (остался только постраничный вариант)
            ###################################################################
            if param.format == FileFormat.FMT_PDF:
                # Создаем новый объект fitz Document
                newdoc = fitz.open()

                # Вставляем страницу
                newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

                # Проверяем существование файла с таким же именем, спрашиваем пользователя если что
                fn, is_overwrite_all, abort = _check_new_file(
                    outfile, ext, ind, is_overwrite_all, overwrite_msg_callback
                )
                # Если пользователь прервал процесс, то инициируем исключение
                if abort:
                    raise FileNotFoundError('Файл для записи не определен')
                # Если пользователь решил не перезаписывать файл, то идем к следующей странице
                if not fn:
                    # Закрываем объект fitz Document
                    newdoc.close()
                    continue

                while True:
                    try:
                        # Пытаемся записать файл
                        newdoc.save(fn, garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
                        break
                    except Exception as e:
                        # Вызываем callback функцию для вывода сообщения об ошибке и получаем реакцию пользователя
                        if show_save_error_msg_callback is not None:
                            res = show_save_error_msg_callback(e)
                        else:
                            res = False

                        if res:
                            break

                        newdoc.close()
                        raise FileNotFoundError('Пользователь прервал процесс') from e

                # Закрываем объект fitz Document и идем к следующей странице
                newdoc.close()
                continue

            ###################################################################
            # Остались варианты с графическими форматами
            ###################################################################

            # Если мы в режиме деперсонификации,
            if censore:
                # то формируем отцензуренное изображение (при этом выделения игнорируются)
                pix = censore_page(doc=doc, pno=pno, param=param)
            else:
                # иначе растеризуем страницу (при этом учитывается настройка размытия выделений)
                pix = _render_page(pdf_view, pno, param, mat, pixelator)

            # Берем страницу документа
            page = doc[pno]

            ###################################################################
            # Это формат PDF с растровым изображением???
            ###################################################################
            if param.format == FileFormat.FMT_PDF_JPEG:
                # Сохраняем изображение в буфер в формате jpeg
                temp = io.BytesIO()
                pix.pil_save(temp, format="jpeg", quality=param.quality)

                # Если без разбивки на отдельные PDF, то добавляем страницу в pdfout и переходим к следующей странице
                if not m_singles:
                    opage = pdfout.new_page(width=page.rect.width, height=page.rect.height)
                    opage.insert_image(opage.rect, stream=temp)
                    continue

                # Создаем новый объект fitz Document
                newdoc = fitz.open()

                # Вставляем страницу
                opage = newdoc.new_page(width=page.rect.width, height=page.rect.height)
                opage.insert_image(opage.rect, stream=temp)

                # Проверяем существование файла с таким же именем, спрашиваем пользователя если что
                fn, is_overwrite_all, abort = _check_new_file(
                    outfile, ext, ind, is_overwrite_all, overwrite_msg_callback
                )
                # Если пользователь прервал процесс, то инициируем исключение
                if abort:
                    raise FileNotFoundError('Файл для записи не определен')

                # Если пользователь решил не перезаписывать файл, то идем к следующей странице
                if not fn:
                    # Закрываем объект fitz Document
                    newdoc.close()
                    continue

                while True:
                    try:
                        # Пытаемся записать файл
                        newdoc.save(
                            fn,
                            garbage=4,
                            clean=True,
                            deflate=True,
                            deflate_images=True,
                            deflate_fonts=True,
                            encryption=fitz.PDF_ENCRYPT_KEEP,
                        )
                        break
                    except Exception as e:
                        # Вызываем callback функцию для вывода сообщения об ошибке и получаем реакцию пользователя
                        if show_save_error_msg_callback is not None:
                            res = show_save_error_msg_callback(e)
                        else:
                            res = False

                        if res:
                            break

                        newdoc.close()
                        raise FileNotFoundError('Пользователь прервал процесс') from e

                # Закрываем объект fitz Document и идем к следующей странице
                newdoc.close()
                continue

            ###################################################################
            # Остались форматы JPEG и PNG
            ###################################################################
            # Проверяем существование файла с таким же именем, спрашиваем пользователя если что
            fn, is_overwrite_all, abort = _check_new_file(outfile, ext, ind, is_overwrite_all, overwrite_msg_callback)
            # Если пользователь прервал процесс, то инициируем исключение
            if abort:
                raise FileNotFoundError('Файл для записи не определен')

            # Если пользователь решил не перезаписывать файл, то идем к следующей странице
            if not fn:
                continue

            while True:
                try:
                    # Пытаемся записать файл
                    if param.format == FileFormat.FMT_JPEG:
                        pix.pil_save(fn, format="jpeg", quality=param.quality)
                    else:
                        pix.pil_save(fn, format="png")
                    break

                except Exception as e:
                    # Вызываем callback функцию для вывода сообщения об ошибке и получаем реакцию пользователя
                    if show_save_error_msg_callback is not None:
                        res = show_save_error_msg_callback(e)
                    else:
                        res = False

                    if res:
                        break

                    raise FileNotFoundError('Пользователь прервал процесс') from e

    # Если сохраняем целиком файл в формате PDF_JPG, то завершаем этот процесс
    if param.format == FileFormat.FMT_PDF_JPEG and not m_singles:
        try:
            # Пфтаемся сохранить файл
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
            pdfout.close()
            # Вызываем callback функцию для вывода сообщения об ошибке
            if show_error_msg_callback is not None:
                show_error_msg_callback(e)
            return False
        pdfout.close()

    # Вызываем callback функцию для обновления прогрессбара
    if progress_callback is not None:
        progress_callback(100)
    return True


def _render_page(pdf_view: SiaPdfView, pno: int, param: SaveParams, mat, pixelator: int):
    """Растеризуем страницу с учетом настроек размытия выделений"""

    # Берем страницу документа
    page = pdf_view.doc[pno]

    # Растеризуем страницу
    pix = page.get_pixmap(matrix=mat)
    pix.set_dpi(param.dpi, param.dpi)

    # Если размывать не надо, то возвращаем результат рендера
    if not param.censore:
        return pix

    # Собираем список выделенных областей на этой странице
    sels = [sel for sel in pdf_view.selections_all if (sel.pno == -1 or sel.pno == pno)]

    # Если выделенных областей нет, то возвращаем результат рендера
    if not sels:
        return pix

    # Запихиваем изображение в PIL
    img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)
    # Задаем область всей страницы
    page_r = fitz.Rect(0, 0, pix.width, pix.height)

    # Перебираем выделения
    for sel in sels:
        # Трансформируем выделение в координаты изображения
        r = pdf_view.get_selection_fitz_rect(pno, page.rotation, sel) * page.rotation_matrix * mat
        # Выделение в пределах страницы???
        if page_r.contains(r):
            # Замазываем участок
            censore_img(img, r, pixelator, param.censore)

    # Обратно конвертируем картинку в формат fitz.Pixmap и возвращаем...
    samples = img.tobytes()
    return fitz.Pixmap(fitz.csRGB, img.size[0], img.size[1], samples)
