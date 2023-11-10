"""
Класс для хранения данных о выделенных областях в документе (для виджета SiaPdfView)

Зависимости
===========
* PySide2
"""

from PySide2.QtCore import QPoint
from PySide2.QtCore import QRect
from PySide2.QtCore import QRectF


# Участки выделенной области (в том числе "маркеры" для изменения размеров области)
DIR_OUT = 0  # Вне границ области
DIR_NW = 1  # Левый верхний угол
DIR_N = 2  # Середина верхней стороны
DIR_NE = 3  # Правый верхний угол
DIR_W = 4  # Середина левой стороны
DIR_IN = 5  # Внутри границ области
DIR_E = 6  # Середина правой стороны
DIR_SW = 7  # Левый нижний угол
DIR_S = 8  # Середина нижней стороны
DIR_SE = 9  # Правый нижний угол

# Допуск в пикселях вокруг центров маркеров, используемых для изменения размера выделенной области
MOUSE_TOLERANCE = 4


class SelectionRect:
    """Класс для хранения данных о выделенных областях"""

    def __init__(self, pno: int = -1):
        self.pno = pno  # Номер страницы, к которой "привязана" область. Если -1,
        # то это глобальная область (т.е. действует на всех страницах)
        self.rect = QRect(0, 0, 0, 0)  # Экранные координаты выделенной области
        self.rect_ref = QRectF(0.0, 0.0, 0.0, 0.0)  # Координаты выделенной области в "эталонном" масштабе
        self.enabled = True  # Признак доступности области на просматриваемой странице (область не доступна,
        # если выходит за границы страницы)

    @property
    def x1(self) -> int:
        """Координата X первого угла экранного QRect

        Returns:
            int: координата X
        """
        return self.rect.x()

    @property
    def y1(self) -> int:
        """Координата Y первого угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.rect.y()

    @property
    def x2(self) -> int:
        """Координата X второго угла экранного QRect

        Returns:
            int: координата X
        """
        return self.rect.x() + self.rect.width()

    @property
    def y2(self) -> int:
        """Координата Y второго угла экранного QRect

        Returns:
            int: координата Y
        """
        return self.rect.y() + self.rect.height()

    @property
    def is_null(self) -> bool:
        """Признак соответствия выделенной области минимально допустимому размеру

        Returns:
            bool: признак соответствия минимально допустимому размеру
        """
        return abs(self.rect_ref.width()) < 15 or abs(self.rect_ref.height()) < 15

    def normalize(self):
        """Нормализовать экранные размеры выделенной области"""
        # Косяк в PySide2
        # self.r = self.r.normalized()
        # x1, y1, x2, y2 = self.r.getCoords()

        doit = False
        x1 = self.x1
        x2 = self.x2
        y1 = self.y1
        y2 = self.y2

        if x2 < x1:
            x1, x2 = x2, x1
            doit = True

        if y2 < y1:
            y1, y2 = y2, y1
            doit = True

        if doit:
            self.rect.setRect(x1, y1, x2 - x1, y2 - y1)

    def update_rect_ref(self, scr_w: int, scr_h: int, ref_w: int, ref_h: int):
        """Пересчитать "эталлонный" QRect в соответствии с указанным масштабом и
        текущими экранными размерами выделенной области

        Args:
            scr_w (int): экранная ширина страницы
            scr_h (int): экранная высота страницы
            ref_w (int): ширина эталлоной страницы
            ref_h (int): высота эталлоной страницы
        """
        self.normalize()
        self.rect_ref.setX(self.rect.x() * ref_w / scr_w)
        self.rect_ref.setY(self.rect.y() * ref_h / scr_h)
        self.rect_ref.setWidth((self.rect.width() + 1) * ref_w / scr_w)
        self.rect_ref.setHeight((self.rect.height() + 1) * ref_h / scr_h)

    def update_rect(self, scr_w: int, scr_h: int, ref_w: int, ref_h: int):  # pylint: disable=too-many-arguments
        """Пересчитать экранный QRect в соответствии с указанным масштабом и
        "эталлонными" размерами выделенной области

        Args:
            scr_w (int): экранная ширина страницы
            scr_h (int): экранная высота страницы
            ref_w (int): ширина эталлоной страницы
            ref_h (int): высота эталлоной страницы
        """
        # Проверяем размеры области на вместимость на странице
        self.enabled = QRectF(0, 0, ref_w, ref_h).contains(self.rect_ref)

        self.rect.setX(round(self.rect_ref.x() * scr_w / ref_w))
        self.rect.setY(round(self.rect_ref.y() * scr_h / ref_h))
        self.rect.setWidth(round((self.rect_ref.x() + self.rect_ref.width()) * scr_w / ref_w) - self.rect.x() - 1)
        self.rect.setHeight(round((self.rect_ref.y() + self.rect_ref.height()) * scr_h / ref_h) - self.rect.y() - 1)

    def get_scaled_rect(self, new_w: int, new_h: int, ref_w: int, ref_h: int) -> QRect:
        """Сформировать QRect в соответствии с указанным масштабом и "эталлонными"
        размерами выделенной области

        Args:
            new_w (int): новая ширина страницы
            new_h (int): новая высота страницы
            ref_w (int): ширина эталлоной страницы
            ref_h (int): высота эталлоной страницы

        Returns:
            QRect: масштабированная прямоугольная область
        """
        m_r = QRect()
        m_r.setX(round(self.rect_ref.x() * new_w / ref_w))
        m_r.setY(round(self.rect_ref.y() * new_h / ref_h))
        m_r.setWidth(round(self.rect_ref.width() * new_w / ref_w))
        m_r.setHeight(round(self.rect_ref.height() * new_h / ref_h))
        return m_r

    def set_x1y1_x2y2(self, pt1: QPoint, pt2: QPoint):
        """Установить параметры экранного QRect исходя их координат двух переданных точек
        ("эталонный" QRect не пересчитывается)

        Args:
            pt1 (QPoint): точка первого угла прямоугольной области
            pt2 (QPoint): точка второго (диагонально противоположного) угла прямоугольной области
        """
        self.rect.setRect(pt1.x(), pt1.y(), pt2.x() - pt1.x(), pt2.y() - pt1.y())

    def get_dir_rect(self, pt: QPoint) -> int:
        """Получить номер угла выделенной области, находящийся в зоне "досягаемости"
        указанной точки (1, 3, 7, 9), или идентификатор иного участка области/экрана
        (5 - внутри области, 0 (DIR_OUT) - за пределами области или область disabled)

        1 - 2 - 3           DIR_NW - DIR_N -  DIR_NE

        4 - 5 - 6           DIR_W -  DIR_IN - DIR_E

        7 - 8 - 9           DIR_SW - DIR_S -  DIR_SE

        Args:
            pt (QPoint): точка (например, положение указателя мыши)

        Returns:
            int: идентификатор угла выделенной области или иного участка области/экрана
        """

        # Если область неактивна (выходит за пределы страницы), то не реагируем на нее
        if not self.enabled:
            return DIR_OUT

        # Используем экранные координаты прямоугольной области
        r = self.rect

        # Определяем координаты центра центр
        x_center = (self.x1 + self.x2) // 2
        y_center = (self.y1 + self.y2) // 2

        if r.x() - MOUSE_TOLERANCE < pt.x() < r.x() + MOUSE_TOLERANCE:  # левая сторона
            if r.y() - MOUSE_TOLERANCE < pt.y() < r.y() + MOUSE_TOLERANCE:  # верхняя сторона
                return DIR_NW
            if r.bottom() - MOUSE_TOLERANCE + 1 < pt.y() < r.bottom() + MOUSE_TOLERANCE + 1:  # нижняя сторона
                return DIR_SW
            if y_center - MOUSE_TOLERANCE < pt.y() < y_center + MOUSE_TOLERANCE:  # середина по вертикали
                return DIR_W

        elif r.right() - MOUSE_TOLERANCE + 1 < pt.x() < r.right() + MOUSE_TOLERANCE + 1:  # правая сторона
            if r.y() - MOUSE_TOLERANCE < pt.y() < r.y() + MOUSE_TOLERANCE:  # верхняя сторона
                return DIR_NE
            if r.bottom() - MOUSE_TOLERANCE + 1 < pt.y() < r.bottom() + MOUSE_TOLERANCE + 1:  # нижняя сторона
                return DIR_SE
            if y_center - MOUSE_TOLERANCE < pt.y() < y_center + MOUSE_TOLERANCE:  # середина по вертикали
                return DIR_E

        elif r.y() - MOUSE_TOLERANCE < pt.y() < r.y() + MOUSE_TOLERANCE:  # верхняя сторона
            if x_center - MOUSE_TOLERANCE < pt.x() < x_center + MOUSE_TOLERANCE:  # середина по горизонтали
                return DIR_N

        elif r.bottom() - MOUSE_TOLERANCE + 1 < pt.y() < r.bottom() + MOUSE_TOLERANCE + 1:  # нижняя сторона
            if x_center - MOUSE_TOLERANCE < pt.x() < x_center + MOUSE_TOLERANCE:  # середина по горизонтали
                return DIR_S

        if r.contains(pt):
            return DIR_IN
        return DIR_OUT

    def adjust_position(self, page_width: int, page_height: int):
        """Проверить, укладывается ли выделенная область в размеры страницы, и сдвинуть ее
        обратно на страницу, если область вышла за края

        Args:
            page_width (int): ширина страницы
            page_height (int): высота страницы

        Returns:
            int, int: величина "вылета" за пределы страницы по X и Y
        """
        # Ищем минимальный х, ушедший в минус
        dx = min(self.x1, self.x2, 0)
        # Если в минус (влево) по x не уходили,
        if not dx:
            # то проверяем выход за пределы страницы вправо - ищем максимальный лишний плюс
            dx = max(self.x1 - (page_width - 1), self.x2 - (page_width - 1), 0)

        # Ищем минимальный y, ушедший в минус
        dy = min(self.y1, self.y2, 0)
        # Если в минус (вверх) по y не уходили,
        if not dy:
            # то проверяем выход за пределы страницы вниз - ищем максимальный лишний плюс
            dy = max(self.y1 - (page_height - 1), self.y2 - (page_height - 1), 0)

        # Если ушли запределы страницы по x или y
        if dx or dy:
            # то возвращаем прямоугольник на страницу
            self.rect.adjust(-dx, -dy, -dx, -dy)

        # Возвращаем величину предотвращенного "вылета" за пределы страницы по X и Y
        return dx, dy

    def shift_x(self, offset: int, is_scale: bool, page_width: int, page_height: int):
        """Сдвинуть выделенную область или изменить ее размер по горизонтали на указанное число пикселей
        в пределах страницы

        Args:
            offset (int): количество пикселей
            is_scale (bool): признак изменения размера области, иначе - перемещение
            page_width (int): ширина страницы
            page_height (int): высота страницы

        Returns:
            SelectionRect: этот объект
        """
        # Нормализуем координаты
        self.normalize()
        if not is_scale:  # перемещение
            # Сдвигаем весь прямоугольник за левую сторону на величину смещения
            self.rect.moveLeft(self.rect.left() + offset)
            # Проверяем, укладывается ли теперь смещенная выделенная область в размеры страницы,
            # если нет - немного сдвигаем обратно, чтобы вернуть на страницу
            self.adjust_position(page_width, page_height)
            # Возвращаем себя
            return self

        # изменение размера
        # меняем размер только в том случае, если новый не будет меньше 11 пикселей
        if self.rect.width() + offset > 10:
            # устанавливаем новую ширину, ограничив ее размерами страницы
            self.rect.setWidth(min(self.rect.width() + offset, page_width - self.x1 - 1))
        # Возвращаем себя
        return self

    def shift_y(self, offset: int, is_scale: bool, page_width: int, page_height: int):
        """Сдвинуть выделенную область или изменить ее размер по вертикали на указанное число пикселей
        в пределах страницы

        Args:
            offs (int): количество пикселей
            is_scale (bool): признак изменения размера области, иначе - перемещение
            page_width (int): ширина страницы
            page_height (int): высота страницы

        Returns:
            SelectionRect: этот объект
        """
        # Нормализуем координаты
        self.normalize()
        if not is_scale:  # перемещение
            # Сдвигаем весь прямоугольник за "верх" на величину смещения
            self.rect.moveTop(self.rect.top() + offset)
            # Проверяем, укладывается ли теперь смещенная выделенная область в размеры страницы,
            # если нет - немного сдвигаем обратно, чтобы вернуть на страницу
            self.adjust_position(page_width, page_height)
            # Возвращаем себя
            return self

        # изменение размера
        # меняем размер только в том случае, если новый не будет меньше 11 пикселей
        if self.rect.height() + offset > 10:
            # устанавливаем новую высоту, ограничив ее размерами страницы
            self.rect.setHeight(min(self.rect.height() + offset, page_height - self.y1 - 1))
        # Возвращаем себя
        return self
