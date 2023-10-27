import unittest

from params import PageMode
from params import SaveParams


class TestPageRanges(unittest.TestCase):
    def setUp(self):
        self.params = SaveParams()

    def test_pg_all(self):
        self.params.pgmode = PageMode.PG_ALL
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(0, 20)], 20))

    def test_pg_current(self):
        self.params.pgmode = PageMode.PG_CURRENT
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(4, 5)], 1))

    def test_pg_range_minus7(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '-7'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(0, 7)], 7))

    def test_pg_range_7minus(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '7-'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(6, 20)], 14))

    def test_pg_range_minus7_7minus(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '-7,7-'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(0, 7), range(6, 20)], 21))

    def test_pg_range_0to100(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '0-100'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(0, 20)], 20))

    def test_pg_range_100to0(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '100-0'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(19, -1, -1)], 20))

    def test_pg_range_10to5_comma(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '10-5,'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(9, 3, -1)], 6))

    def test_pg_range_minus(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = '-'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([range(0, 20)], 20))

    def test_pg_range_onlycommas(self):
        self.params.pgmode = PageMode.PG_RANGE
        self.params.pgrange = ',,,,'
        self.assertEqual(self.params.get_pages_ranges(4, 20), ([], 0))


if __name__ == '__main__':
    unittest.main()
