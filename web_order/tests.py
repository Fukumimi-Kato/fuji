import datetime as dt
from django.test import TestCase

from .date_management import SalesDayUtil
from .exceptions import NotChangeOrderError
from .models import JapanHoliday, AggMeasureSoupMaster
from .views import get_order_change_dates


# Create your tests here.
class SalesDayUtilTests(TestCase):
    def test_default(self):
        test_settings = [
            (2, '2000-01-01'),
            (3, '2024-02-25')
        ]

        eating_day = dt.datetime.strptime('2023-01-01', '%Y-%m-%d')
        sales_day = SalesDayUtil.get_by_eating_day(eating_day, test_settings)

        self.assertEqual(sales_day.year, 2022)
        self.assertEqual(sales_day.month, 12)
        self.assertEqual(sales_day.day, 30)

    def test_not_change(self):
        test_settings = [
            (2, '2000-01-01'),
            (3, '2024-02-25')
        ]

        eating_day = dt.datetime.strptime('2024-02-24', '%Y-%m-%d')
        sales_day = SalesDayUtil.get_by_eating_day(eating_day, test_settings)

        self.assertEqual(sales_day.year, 2024)
        self.assertEqual(sales_day.month, 2)
        self.assertEqual(sales_day.day, 22)

    def test_eq_change(self):
        test_settings = [
            (2, '2000-01-01'),
            (3, '2024-02-25')
        ]

        eating_day = dt.datetime.strptime('2024-02-25', '%Y-%m-%d')
        sales_day = SalesDayUtil.get_by_eating_day(eating_day, test_settings)

        self.assertEqual(sales_day.year, 2024)
        self.assertEqual(sales_day.month, 2)
        self.assertEqual(sales_day.day, 22)

    def test_over_change(self):
        test_settings = [
            (2, '2000-01-01'),
            (3, '2024-02-25')
        ]

        eating_day = dt.datetime.strptime('2024-02-26', '%Y-%m-%d')
        sales_day = SalesDayUtil.get_by_eating_day(eating_day, test_settings)

        self.assertEqual(sales_day.year, 2024)
        self.assertEqual(sales_day.month, 2)
        self.assertEqual(sales_day.day, 23)


class OrderChangeDatesTests(TestCase):
    """
    食数変更期限の取得テスト
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-07-18', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-08-11', '%Y-%m-%d'),
        )
        holiday.save()

    def test_monday_before_10(self):
        """
        月曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-04 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 11)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_monday_after_10(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-04 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 12)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_tuesday_before_10(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-05 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 12)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_tuesday_after_10(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-05 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 13)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_wednesday_before_10(self):
        """
        水曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-06 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 13)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_wednesday_after_10(self):
        """
        水曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-06 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 14)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_thursday_before_10(self):
        """
        木曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-07 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 14)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_thursday_after_10(self):
        """
        木曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-07 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 15)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_friday_before_10(self):
        """
        金曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-08 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 15)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_friday_after_10(self):
        """
        金曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-08 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 16)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_saturday_before_10(self):
        """
        土曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-09 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 16)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_saturday_with_holiday_10_17(self):
        """
        土曜日10時～17時の期限の確認(祝日あり)
        """
        date_time_now = dt.datetime.strptime('2022-07-09 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_with_holiday_after_17(self):
        """
        土曜日17時以後の期限の確認(祝日あり)
        """
        date_time_now = dt.datetime.strptime('2022-07-09 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_sunday_with_holiday_before_10(self):
        """
        日曜日10時前の期限の確認(祝日あり)
        """
        date_time_now = dt.datetime.strptime('2022-07-10 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_sunday_with_holiday_after_10(self):
        """
        日曜日10時以後の期限の確認(祝日あり)
        """
        date_time_now = dt.datetime.strptime('2022-07-10 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_10_17(self):
        """
        土曜日10時～17時の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-02 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 11)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 11)

    def test_saturday_after_17(self):
        """
        土曜日17時以後の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-02 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 11)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_sunday_before_10(self):
        """
        日曜日10時前の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-03 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 11)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    def test_sunday_after_10(self):
        """
        日曜日10時以後の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-03 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 11)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 18)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

class OrderChangeDates202207w3Tests(TestCase):
    """
    食数変更期限の取得テスト
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-07-18', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-08-11', '%Y-%m-%d'),
        )
        holiday.save()

    def test_monday_before_10(self):
        """
        月曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-11 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_monday_after_10(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-11 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 20)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_tuesday_before_10(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-12 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 20)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_tuesday_after_10(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-12 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 21)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_wednesday_before_10(self):
        """
        水曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-13 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 21)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_wednesday_after_10(self):
        """
        水曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-13 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 22)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_thursday_before_10(self):
        """
        木曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-14 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 22)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_thursday_after_10(self):
        """
        木曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-14 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 23)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_friday_before_10(self):
        """
        金曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-15 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 23)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_friday_after_10(self):
        """
        金曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-15 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 25)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_before_10(self):
        """
        土曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 25)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_10_17(self):
        """
        土曜日10時～17時の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_saturday_after_17(self):
        """
        土曜日17時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_before_10(self):
        """
        日曜日10時前の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-17 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_after_10(self):
        """
        日曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-17 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

class OrderChangeDates202207w4Tests(TestCase):
    """
    食数変更期限の取得テスト
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-07-18', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-08-11', '%Y-%m-%d'),
        )
        holiday.save()

    def test_monday_before_10(self):
        """
        月曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-18 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_monday_after_10(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-18 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_tuesday_before_10(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-19 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_tuesday_after_10(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-19 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 27)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_wednesday_before_10(self):
        """
        水曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-20 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 27)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_wednesday_after_10(self):
        """
        水曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-20 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 28)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_thursday_before_10(self):
        """
        木曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-21 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 28)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_thursday_after_10(self):
        """
        木曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-21 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 29)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_friday_before_10(self):
        """
        金曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-22 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 29)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_friday_after_10(self):
        """
        金曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-22 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 30)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_saturday_before_10(self):
        """
        土曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-23 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 30)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_saturday_10_17(self):
        """
        土曜日10時～17時の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-23 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_saturday_after_17(self):
        """
        土曜日17時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-23 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 8)

    def test_sunday_before_10(self):
        """
        日曜日10時前の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-24 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 8)

    def test_sunday_after_10(self):
        """
        日曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-24 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 8)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()


from .models import HolidayList
class OrderChangeDates2022SummerHolidayTests(TestCase):
    """
    食数変更期限の取得テスト(夏季休暇)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = HolidayList(
            holiday_name='any',
            start_date=dt.datetime.strptime('2022-08-02', '%Y-%m-%d'),
            end_date=dt.datetime.strptime('2022-08-29', '%Y-%m-%d')
        )
        holiday.save()

    def test_saturday_after_17_holiday_start(self):
        """
        土曜日17時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-23 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_before_10_holiday_start(self):
        """
        日曜日10時以前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-24 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_after_10_holiday_start(self):
        """
        日曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-24 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_monday_after_10_holiday_end(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-08-22 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 30)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 5)

    def test_monday_after_10_exception(self):
        """
        食数変更不可となるケース
        """
        date_time_now = dt.datetime.strptime('2022-07-25 10:00', '%Y-%m-%d %H:%M')

        with self.assertRaises(NotChangeOrderError):
            get_order_change_dates(date_time_now)

    def test_monday_before_10_exception(self):
        """
        食数変更不可となるケース
        """
        date_time_now = dt.datetime.strptime('2022-08-22 9:59', '%Y-%m-%d %H:%M')

        with self.assertRaises(NotChangeOrderError):
            res = get_order_change_dates(date_time_now)

    def test_tuesday_before_10(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-08-23 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 30)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 5)

    def test_tuesday_after_10(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-08-23 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 8)
        self.assertEqual(res[0].day, 31)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 5)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

class OrderChangeDates202209Tests(TestCase):
    """
    食数変更期限の取得テスト
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-09-19', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2022-09-23', '%Y-%m-%d'),
        )
        holiday.save()

    def test_1(self):
        """
        月曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-12 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 20)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 26)

    def test_2(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-13 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 21)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 26)

    def test_3(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-14 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 22)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 26)

    def test_4(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-15 09:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 24)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 26)

    def test_5(self):
        """
        水曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-16 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 9)
        self.assertEqual(res[1].day, 26)

    def test_6(self):
        """
        水曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-17 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 27)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_6_2(self):
        date_time_now = dt.datetime.strptime('2022-09-17 11:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 27)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_7(self):
        """
        木曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-18 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 28)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_8(self):
        """
        木曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-19 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 28)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_9(self):
        """
        金曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-20 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 28)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_10(self):
        """
        金曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-21 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 29)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_11(self):
        """
        土曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-22 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 9)
        self.assertEqual(res[0].day, 30)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_12(self):
        """
        土曜日10時～17時の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-23 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 10)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_13(self):
        """
        土曜日17時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-09-24 9:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 10)
        self.assertEqual(res[0].day, 1)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 3)

    def test_14(self):
        """
        日曜日10時前の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-09-25 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 10)
        self.assertEqual(res[0].day, 3)
        self.assertEqual(res[1].month, 10)
        self.assertEqual(res[1].day, 10)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()


# from .management.commands.cooking_direction import Command as CookingCommand
from .management.commands.cooking_direction import AggMeasureTargetAnalyzer
from .management.commands.cooking_direction import AggMeasureTarget, AggMeasurePlate, AggMeasurePlateWithDensity
from .management.commands.cooking_direction import AggMeasurePlateWithAnotherUnit, AggMeasureMisoDevide, AggMeasureSoupDevide
from .management.commands.cooking_direction import AggMeasureMiso, AggMeasureSoupFilling, AggMeasureSoupLiquid
from .management.commands.cooking_direction import AggMeasureLiquidSeasoning, AggMeasureMisoNone, AggMeasureSoupNone, AggMeasurePlateKoGram

class AggMesureTargetanalyzerTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        AggMeasureSoupMaster.objects.create(
            name='お吸い物',
            search_word='吸い物',
            soup_group='汁'
        )
        AggMeasureSoupMaster.objects.create(
            name='すまし汁',
            search_word='すまし',
            soup_group='汁'
        )
        AggMeasureSoupMaster.objects.create(
            name='コンソメスープ',
            search_word='コンソメ',
            soup_group='スープ'
        )
        AggMeasureSoupMaster.objects.create(
            name='ポタージュスープ',
            search_word='ポタージュ',
            soup_group='スープ'
        )
        AggMeasureSoupMaster.objects.create(
            name='コーンスープ',
            search_word='コーン',
            soup_group='スープ'
        )
        AggMeasureSoupMaster.objects.create(
            name='パンプキンスープ',
            search_word='パンプキン',
            soup_group='スープ'
        )

    def test_個とgの味噌汁判定(self):
        name = '⑤味噌汁 里芋2個・さつま揚げ5g '
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureMisoDevide)
        self.assertEqual(result.name, '味噌汁 里芋')
        self.assertEqual(result.quantity, '2')
        self.assertEqual(result.unit, '個')
        self.assertEqual(result.name2, 'さつま揚げ')
        self.assertEqual(result.quantity2, '5')
        self.assertEqual(result.unit2, 'g')


    def test_個とgの味噌汁以外判定(self):
        name = '⑤すまし汁 里芋2個・さつま揚げ5g '
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupDevide)
        self.assertEqual(result.name, 'すまし汁 里芋')
        self.assertEqual(result.quantity, '2')
        self.assertEqual(result.unit, '個')
        self.assertEqual(result.name2, 'さつま揚げ')
        self.assertEqual(result.quantity2, '5')
        self.assertEqual(result.unit2, 'g')

    def test_gの味噌汁判定(self):
        name = '⑤味噌汁具 玉葱・しめじ 16g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureMiso)
        self.assertEqual(result.name, '味噌汁具 玉葱・しめじ 16g')
        self.assertEqual(result.quantity, '16')
        self.assertEqual(result.unit, 'g')

    def test_gの味噌汁以外の汁具判定(self):
        name = '⑤コンソメ 玉葱・人参 16g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupFilling)
        self.assertEqual(result.name, 'コンソメ 玉葱・人参 16g')
        self.assertEqual(result.quantity, '16')
        self.assertEqual(result.unit, 'g')

    def test_gの味噌汁以外の汁具判定_すまし具(self):
        name = '⑤すまし具 菜の花・大根 16g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupFilling)
        self.assertEqual(result.name, 'すまし具 菜の花・大根 16g')
        self.assertEqual(result.quantity, '16')
        self.assertEqual(result.unit, 'g')

    def test_gの味噌汁以外の汁具判定_すまし汁具(self):
        name = '⑤すまし汁具 菜の花・大根 16g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupFilling)
        self.assertEqual(result.name, 'すまし汁具 菜の花・大根 16g')
        self.assertEqual(result.quantity, '16')
        self.assertEqual(result.unit, 'g')

    def test_gの味噌汁以外のスープ判定_コンソメ(self):
        name = '⑤スープ希釈 コンソメ 29.45g 150g水入れる'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupLiquid)
        self.assertEqual(result.name, 'スープ希釈 コンソメ 29.45g 150g水入れる')
        self.assertEqual(result.quantity, '29.45')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.soup.name, 'コンソメスープ')

    def test_gの味噌汁以外のスープ判定_ポタージュ(self):
        name = '⑤ポタージュスープ　16g　水150g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupLiquid)
        self.assertEqual(result.name, 'ポタージュスープ　16g　水150g')
        self.assertEqual(result.quantity, '16')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.soup.name, 'ポタージュスープ')

    def test_gの味噌汁以外のスープ判定_パンプキン(self):
        name = '⑤パンプキンスープ　32g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupLiquid)
        self.assertEqual(result.name, 'パンプキンスープ　32g')
        self.assertEqual(result.quantity, '32')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.soup.name, 'パンプキンスープ')

    def test_gの味噌汁以外のスープ判定_すまし汁(self):
        name = '⑤すまし汁希釈30g　水120㏄いれる'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupLiquid)
        self.assertEqual(result.name, 'すまし汁希釈30g　水120㏄いれる')
        self.assertEqual(result.quantity, '30')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.soup.name, 'すまし汁')

    def test_gの味噌汁以外のスープ判定_お吸い物(self):
        name = '⑤お吸い物希釈30g　水120㏄いれる'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupLiquid)
        self.assertEqual(result.name, 'お吸い物希釈30g　水120㏄いれる')
        self.assertEqual(result.quantity, '30')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.soup.name, 'お吸い物')

    def test_gなし味噌汁判定(self):
        name = '⑤味噌汁30cc 希釈140'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureMisoNone)

    def test_gなし味噌汁以外判定(self):
        name = '⑤スープの具（コーン）'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureSoupNone)

    def test_調味料の汁判定(self):
        name = '④■ポン酢7g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureLiquidSeasoning)
        self.assertEqual(result.name, 'ポン酢7g')
        self.assertEqual(result.quantity, '7')
        self.assertEqual(result.unit, 'g')

    def test_魚1尾(self):
        name = '①鮭の塩焼き60ｇ1尾'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlate)
        self.assertEqual(result.name, '鮭の塩焼き60ｇ1尾')
        self.assertEqual(result.quantity, '1')
        self.assertEqual(result.unit, '尾')

    def test_切_判定(self):
        name = '①鰆照り焼き1切れ'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlate)
        self.assertEqual(result.name, '鰆照り焼き1切れ')
        self.assertEqual(result.quantity, '1')
        self.assertEqual(result.unit, '切')

    def test_本_判定(self):
        name = '④いんげん2本'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlateWithDensity)
        self.assertEqual(result.name, 'いんげん2本')
        self.assertEqual(result.quantity, '2')
        self.assertEqual(result.unit, '本')
        self.assertEqual(result.density, 0)

    def test_個とg_判定(self):
        name = '①白身フライ60g1個'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlateWithDensity)
        self.assertEqual(result.name, '白身フライ60g1個')
        self.assertEqual(result.quantity, '1')
        self.assertEqual(result.unit, '個')
        self.assertEqual(result.density, 0)

    def test_g_2重表記判定(self):
        name = '①すきやき76g+48g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlateWithAnotherUnit)
        self.assertEqual(result.quantity, '76')
        self.assertEqual(result.unit, 'g')
        self.assertEqual(result.quantity2, '48')
        self.assertEqual(result.unit2, 'g')

    def test_想定外判定(self):
        name = '①すきやき76りっとる'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureTarget)

    def test_嚥下袋数ルール確認_主菜(self):
        name = '①すきやき76g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'main')

    def test_嚥下袋数ルール確認_三色丼(self):
        name = '①三色丼(卵) 50g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub')

    def test_嚥下袋数ルール確認_主菜_記号無効(self):
        name = '①▼ステーキ1個'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'main')

    def test_嚥下袋数ルール確認_添え物(self):
        name = '④そえもの76g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub-less')

    def test_嚥下袋数ルール確認_添え物2(self):
        name = '④そえもの6g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub-less')

    def test_嚥下袋数ルール確認_添え物＿個(self):
        name = '④そえもの6個'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub-less')

    def test_嚥下袋数ルール確認_副菜(self):
        name = '③副菜76g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub')

    def test_嚥下袋数ルール確認_副菜2(self):
        name = '③副菜7g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        # g以外の単位だったら、14人前のルールが適用される。gなので、コマンド内で20人前のルールが適用される。
        self.assertEqual(result.get_package_rule(), 'sub')

    def test_嚥下袋数ルール確認_副菜_記号確認(self):
        name = '③副菜1個'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub')

    def test_嚥下袋数ルール確認_副菜2_記号確認(self):
        name = '③▼副菜1個'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertEqual(result.get_package_rule(), 'sub-less')
        self.assertEqual(result.name, '副菜1個')

    def test_Analyzer_四角記号(self):
        name = '①■しかく1g'
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasureLiquidSeasoning)
        self.assertEqual(result.name, 'しかく1g')

    def test_Analyzer_個_g_Plate(self):
        name = '②味噌煮 鶏  里芋1個＋具75g +常22％ きのこ無 '
        eating_day = '2022-08-31'
        meal = '朝'

        analyzer = AggMeasureTargetAnalyzer('2022-09-01')
        analyzer.add_cook(name, eating_day, meal)
        result = analyzer.generate_analyzed().__next__()

        self.assertTrue(type(result) is AggMeasurePlateKoGram)
        self.assertEqual(result.prefix_name, '味噌煮 ')
        self.assertEqual(result.name, '鶏  里芋')
        self.assertEqual(result.quantity, '1')
        self.assertEqual(result.quantity2, '75')
        self.assertEqual(result.density, 22)

from .management.commands.utils import AggEngePackageMixin

class TestMixin(AggEngePackageMixin):
    pass

class CommdandsUtilTest(TestCase):
    def test_味噌汁_g_less(self):
        result = TestMixin().get_miso_soup_package_function('g', 19, 1)

        self.assertIn('20', result)

    def test_味噌汁_g(self):
        result = TestMixin().get_miso_soup_package_function('g', 20, 1)

        self.assertIn('14', result)

    def test_味噌汁_個_less(self):
        result = TestMixin().get_miso_soup_package_function('個', 1, 1)

        self.assertIn('20', result)

    def test_味噌汁_個(self):
        result = TestMixin().get_miso_soup_package_function('個', 2, 1)

        self.assertIn('14', result)

    def test_味噌汁以外_g_主菜(self):
        result = TestMixin().get_filling_package_excel_function('g', 19, 'main', 1)

        self.assertIn('7', result)

    def test_味噌汁以外_g_主菜2(self):
        result = TestMixin().get_filling_package_excel_function('g', 20, 'main', 1)

        self.assertIn('7', result)

    def test_味噌汁以外_本_主菜(self):
        result = TestMixin().get_filling_package_excel_function('本', 20, 'main', 1)

        self.assertIn('7', result)

    def test_味噌汁以外_尾_主菜(self):
        result = TestMixin().get_filling_package_excel_function('尾', 20, 'main', 1)

        self.assertIn('7', result)

    def test_味噌汁以外_g_副菜_less(self):
        result = TestMixin().get_filling_package_excel_function('g', 19, 'sub-less', 1)

        self.assertIn('20', result)

    def test_味噌汁以外_g_副菜_less2(self):
        result = TestMixin().get_filling_package_excel_function('g', 19, 'sub', 1)

        self.assertIn('20', result)

    def test_味噌汁以外_g_副菜(self):
        result = TestMixin().get_filling_package_excel_function('g', 20, 'sub-less', 1)

        self.assertIn('14', result)

    def test_味噌汁以外_g_副菜2(self):
        result = TestMixin().get_filling_package_excel_function('g', 20, 'sub', 1)

        self.assertIn('14', result)

    def test_味噌汁以外_個_副菜_less(self):
        result = TestMixin().get_filling_package_excel_function('個', 19, 'sub-less', 1)

        self.assertIn('20', result)

    def test_味噌汁以外_g_副菜_less2(self):
        result = TestMixin().get_filling_package_excel_function('個', 19, 'sub', 1)

        self.assertIn('14', result)

    def test_味噌汁以外_個_副菜(self):
        result = TestMixin().get_filling_package_excel_function('個', 20, 'sub-less', 1)

        self.assertIn('20', result)

    def test_味噌汁以外_個_副菜2(self):
        result = TestMixin().get_filling_package_excel_function('個', 20, 'sub', 1)

        self.assertIn('14', result)

from  .views import convert_invoice_userid_to_parent
class InvoiceUseridConvertTet(TestCase):
    def test_10002(self):
        userid = '10002'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910002')

    def test_10004(self):
        userid = '10004'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910004')

    def test_10022(self):
        userid = '10022'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910022')

    def test_10053(self):
        userid = '10053'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910053')

    def test_10037(self):
        userid = '10037'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910037')

    def test_10055(self):
        userid = '10055'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910055')

    def test_22029(self):
        userid = '22029'
        # よんやくは22029で登録されている
        self.assertEqual(convert_invoice_userid_to_parent(userid), '22029')

    def test_10066(self):
        userid = '10066'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910066')

    def test_10070(self):
        userid = '10070'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910070')

    def test_10080(self):
        userid = '10084'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910084')

    def test_10090(self):
        userid = '10090'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '910090')

    def test_others(self):
        userid = '10008'
        self.assertEqual(convert_invoice_userid_to_parent(userid), '10008')

class OrderChangeDates202212Tests(TestCase):
    """
    食数変更期限の取得テスト
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2023-01-01', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2023-01-02', '%Y-%m-%d'),
        )
        holiday.save()
        holiday = JapanHoliday(
            name='any',
            date=dt.datetime.strptime('2023-01-09', '%Y-%m-%d'),
        )
        holiday.save()
        holiday_list = HolidayList(
            holiday_name='',
            start_date=dt.datetime.strptime('2022-12-27', '%Y-%m-%d'),
            end_date=dt.datetime.strptime('2023-01-09', '%Y-%m-%d'),
            limit_day=dt.datetime.strptime('2022-12-10', '%Y-%m-%d'),
        )
        holiday_list.save()
        holiday_list = HolidayList(
            holiday_name='',
            start_date=dt.datetime.strptime('2023-01-09', '%Y-%m-%d'),
            end_date=dt.datetime.strptime('2023-01-23', '%Y-%m-%d'),
            limit_day=dt.datetime.strptime('2022-12-17', '%Y-%m-%d'),
        )
        holiday_list.save()

    def test_monday_before_10(self):
        """
        月曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-11 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 19)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_monday_after_10(self):
        """
        月曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-11 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 20)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_tuesday_before_10(self):
        """
        火曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-12 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 20)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_tuesday_after_10(self):
        """
        火曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-12 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 21)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_wednesday_before_10(self):
        """
        水曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-13 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 21)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_wednesday_after_10(self):
        """
        水曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-13 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 22)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_thursday_before_10(self):
        """
        木曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-14 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 22)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_thursday_after_10(self):
        """
        木曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-14 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 23)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_friday_before_10(self):
        """
        金曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-15 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 23)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_friday_after_10(self):
        """
        金曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-15 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 25)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_before_10(self):
        """
        土曜日10時前の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 25)
        self.assertEqual(res[1].month, 7)
        self.assertEqual(res[1].day, 25)

    def test_saturday_10_17(self):
        """
        土曜日10時～17時の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_saturday_after_17(self):
        """
        土曜日17時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-16 17:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_before_10(self):
        """
        日曜日10時前の期限の確認(祝日なし)
        """
        date_time_now = dt.datetime.strptime('2022-07-17 9:59', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    def test_sunday_after_10(self):
        """
        日曜日10時以後の期限の確認
        """
        date_time_now = dt.datetime.strptime('2022-07-17 10:00', '%Y-%m-%d %H:%M')
        res = get_order_change_dates(date_time_now)

        self.assertEqual(res[0].month, 7)
        self.assertEqual(res[0].day, 26)
        self.assertEqual(res[1].month, 8)
        self.assertEqual(res[1].day, 1)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

