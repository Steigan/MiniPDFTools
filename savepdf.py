"""
Этот файл содержит функции для сохранения файла PDF
(с возможностью деперсонификации выделенных областей)
"""

import io
import logging
import os
import shutil
import subprocess

import fitz
from PIL import Image as PILImage
from PIL import ImageDraw
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWidgets import QMessageBox

from censorepd import censore_page
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


def check_new_file(wnd, outfile, ext, ind, overwrite_all):
    if ind < 10000:
        fn = f'{outfile}-%04i{ext}' % ind
    else:
        fn = f'{outfile}-{ind}{ext}'
    if not overwrite_all and os.path.exists(fn):
        wnd.ui.msg_box.setText(f'Файл \'{fn}\' уже существует. Перезаписать поверх?')
        res = wnd.ui.msg_box.exec()
        if (res == QMessageBox.StandardButton.No) or (res == QMessageBox.StandardButton.Cancel):
            fn = ''
        return fn, (res == QMessageBox.StandardButton.YesToAll), (res == QMessageBox.StandardButton.Cancel)
    else:
        return fn, overwrite_all, False


def show_save_error_msg(wnd, e):
    m_msg_box = QMessageBox(wnd)
    m_msg_box.setIcon(QMessageBox.Icon.Warning)
    m_msg_box.setWindowTitle(wnd.title)
    m_msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    m_msg_box.button(QMessageBox.StandardButton.Ok).setText('  ОК  ')
    m_msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
    m_msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
    m_msg_box.setText(f'Ошибка: {e}\n\nПродолжить процесс сохранения остальных файлов?')
    res = m_msg_box.exec()
    return res


def saveas_process(wnd, p: SaveParams, censore: bool):  # noqa: ignore=C901
    if censore:
        wnd.title = 'Деперсонификация данных'
    else:
        wnd.title = 'Сохранить как'

        pageranges, approx_pgcount = p.get_pages_ranges(wnd.pdf_view)

        if not pageranges:
            QMessageBox.critical(wnd, wnd.title, "Не задан список страниц!")
            return

    if p.setselectionsonly:
        if wnd.pdf_view.selections_all_count > 0:
            wnd.ui.msg_box.setIcon(QMessageBox.Icon.Question)
            wnd.ui.msg_box.setWindowTitle(wnd.title)
            wnd.ui.msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            wnd.ui.msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
            wnd.ui.msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
            wnd.ui.msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
            wnd.ui.msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')
            wnd.ui.msg_box.setText('Документ уже содержит выделенные области. Очистить их?')
            res = wnd.ui.msg_box.exec()
            if res == QMessageBox.StandardButton.Cancel:
                return
            elif res == QMessageBox.StandardButton.Yes:
                wnd.pdf_view.remove_selection(True)

        wnd.statusBar().showMessage('Поиск и выделение персональных данных...')
        wnd.ui.progress_bar.setValue(0)
        wnd.ui.progress_bar.setVisible(True)
        wnd.setDisabled(True)
        QApplication.processEvents()
        ind = 0
        doc = wnd.pdf_view.doc
        for pages in pageranges:
            for pno in pages:
                if 0 <= pno < doc.page_count:
                    censore_page(doc=doc, pno=pno, param=p, add_selection_callback=wnd.pdf_view.add_selection)
                    ind += 1
                    wnd.ui.progress_bar.setValue(ind * 100 // approx_pgcount)
                    QApplication.processEvents()

        wnd.process_rect_selection(wnd.pdf_view.selected_rect > -1)
        return

    # outfile, _ = os.path.splitext(wnd.m_currentFileName)

    if p.format in (FileFormat.FMT_JPEG, FileFormat.FMT_PNG):
        m_singles = True
    else:
        m_singles = p.singles

    if m_singles:
        ext_tp = [".pdf", ".jpg", ".png"][max(p.format.value - 1, 0)]
        outfile, _ = QFileDialog.getSaveFileName(
            wnd,
            wnd.title,
            os.path.dirname(wnd.current_filename),
            r'Серия файлов {имя}' + f'-XXXX{ext_tp} (*{ext_tp})',
            options=QFileDialog.Option.DontConfirmOverwrite,
        )

        outfile, ext = os.path.splitext(outfile)
        if outfile:
            # для debian/GNOME
            if ext.lower() != ext_tp:
                ext = ext_tp
    else:
        outfile, _ = QFileDialog.getSaveFileName(
            wnd, wnd.title, os.path.dirname(wnd.current_filename), r'Файл PDF (*.pdf)'
        )
        if outfile:
            _, ext = os.path.splitext(outfile)
            # для debian/GNOME
            if ext.lower() != ".pdf":
                ext = ".pdf"
                outfile += ext

    if not outfile:
        return

    if outfile == wnd.current_filename:
        QMessageBox.critical(wnd, wnd.title, "Нельзя сохранять файл в самого себя!")
        return

    wnd.statusBar().showMessage('Сохранение файла/файлов...')
    wnd.ui.progress_bar.setValue(0)
    wnd.ui.progress_bar.setVisible(True)
    wnd.setDisabled(True)
    QApplication.processEvents()

    # doc = fitz.open(wnd.m_currentFileName)
    doc = wnd.pdf_view.doc

    zoom = p.dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    if p.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG) and not m_singles:
        # noinspection PyUnresolvedReferences
        pdfout = fitz.open()
    ind = 0

    wnd.ui.msg_box.setIcon(QMessageBox.Icon.Question)
    wnd.ui.msg_box.setWindowTitle(wnd.title)
    wnd.ui.msg_box.setStandardButtons(
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.YesToAll
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel
    )
    wnd.ui.msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
    wnd.ui.msg_box.button(QMessageBox.StandardButton.Yes).setText('  Да  ')
    wnd.ui.msg_box.button(QMessageBox.StandardButton.YesToAll).setText('  Да для всех  ')
    wnd.ui.msg_box.button(QMessageBox.StandardButton.No).setText('  Нет  ')
    wnd.ui.msg_box.button(QMessageBox.StandardButton.Cancel).setText('  Отмена  ')

    # Эксклюзивный режим ...
    if (
        wnd.is_real_file
        and p.format == FileFormat.FMT_PDF
        and p.pgmode == PageMode.PG_ALL
        and (not m_singles)
        and doc.can_save_incrementally()
    ):
        # noinspection PyUnboundLocalVariable
        pdfout.close()
        # doc.close()
        # doc = None
        try:
            shutil.copyfile(wnd.current_filename, outfile)
        except Exception as e:
            QMessageBox.critical(
                wnd, wnd.title, f"Ошибка: {e}\n\nПопробуйте сохранить файл как диапазон из всех страниц [1-]."
            )
            return

        # print('Эксклюзивный режим ...')
        # noinspection PyUnresolvedReferences
        doc = fitz.open(outfile)
        if doc.needs_pass:
            doc.authenticate(wnd.pdf_view.psw)
        for pno in range(approx_pgcount):
            # if p.rotation != PageRotation.rtNone:
            # Пытаемся повернуть страницу в соответствии с отображаемым на экране объектом
            doc[pno].set_rotation((wnd.pdf_view.doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)
            wnd.ui.progress_bar.setValue(pno * 95 // approx_pgcount)
            QApplication.processEvents()
        try:
            doc.save(
                outfile, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
            )  # , garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
        except Exception as e:
            QMessageBox.critical(wnd, wnd.title, f"Ошибка: {e}")
            doc.close()
            # shutil. copyfile(wnd.m_currentFileName, outfile)
            return
        doc.close()
    else:
        pixelator = p.dpi // 20
        overwrite_all = False
        for pages in pageranges:
            for pno in pages:
                if 0 <= pno < doc.page_count:
                    ind += 1

                    wnd.ui.progress_bar.setValue(ind * 100 // approx_pgcount)
                    QApplication.processEvents()

                    old_rot = doc[pno].rotation
                    if p.rotation != PageRotation.RT_NONE:
                        doc[pno].set_rotation((doc[pno].rotation + (0, 270, 90, 180)[p.rotation.value]) % 360)

                    try:
                        if p.format == FileFormat.FMT_PDF:
                            if m_singles:
                                # noinspection PyUnresolvedReferences
                                newdoc = fitz.open()
                                newdoc.insert_pdf(doc, from_page=pno, to_page=pno)

                                fn, overwrite_all, abort = check_new_file(wnd, outfile, ext, ind, overwrite_all)
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
                                        )
                                    except Exception as e:
                                        if show_save_error_msg(wnd, e) == QMessageBox.StandardButton.Cancel:
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
                                    sels = [
                                        sel for sel in wnd.pdf_view.selections_all if (sel.pno == -1 or sel.pno == pno)
                                    ]
                                    if len(sels) > 0:
                                        img = PILImage.frombytes('RGB', (pix.width, pix.height), pix.samples)
                                        page_r = fitz.Rect(0, 0, pix.width, pix.height)
                                        for sel in sels:
                                            r = (
                                                wnd.pdf_view.get_selection_fitz_rect(pno, old_rot, sel)
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
                                                            (
                                                                crop_img.size[0] // pixelator,
                                                                crop_img.size[1] // pixelator,
                                                            )
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

                                    fn, overwrite_all, abort = check_new_file(wnd, outfile, ext, ind, overwrite_all)
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
                                            if show_save_error_msg(wnd, e) == QMessageBox.StandardButton.Cancel:
                                                newdoc.close()
                                                raise

                                    newdoc.close()
                                else:
                                    opage = pdfout.new_page(width=page.rect.width, height=page.rect.height)
                                    opage.insert_image(opage.rect, stream=temp)
                            else:
                                fn, overwrite_all, abort = check_new_file(wnd, outfile, ext, ind, overwrite_all)
                                if abort:
                                    raise FileNotFoundError('Файл для записи не определен')
                                if fn:
                                    try:
                                        if p.format == FileFormat.FMT_JPEG:
                                            pix.pil_save(fn, format="jpeg", quality=p.quality)
                                        else:
                                            pix.pil_save(fn, format="png")
                                    except Exception as e:
                                        if show_save_error_msg(wnd, e) == QMessageBox.StandardButton.Cancel:
                                            raise
                    except Exception:
                        logger.error('', exc_info=True)
                        # Вертаем поворот страницы взад
                        if p.rotation != PageRotation.RT_NONE:
                            doc[pno].set_rotation(old_rot)
                        return

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
                return
            pdfout.close()

    wnd.ui.progress_bar.setValue(100)
    QApplication.processEvents()

    wnd.statusBar().showMessage('Готово!')
    if p.format in (FileFormat.FMT_PDF, FileFormat.FMT_PDF_JPEG) and not m_singles:
        # if platform.system() == 'Windows':
        #     subprocess.Popen(('start', outfile), shell = True)
        if wnd._pdfviewer_cmd:
            subprocess.Popen((wnd._pdfviewer_cmd, outfile))
    QMessageBox.information(wnd, "Сохранение файла/файлов", "Готово!")
