import datetime as dt

from dateutil.relativedelta import relativedelta

from django.conf import settings


class SalesDayUtil:
    """
    売上日操作クラス
    """
    @classmethod
    def get_by_eating_day(cls, eating_day, date_settings):
        dt_list = [(x[0], dt.datetime.strptime(x[1], '%Y-%m-%d').date()) for x in date_settings]
        dt_days = [y[0] for y in dt_list if y[1] <= eating_day][-1]
        return eating_day - relativedelta(days=dt_days)

    @classmethod
    def get_by_eating_day_by_settings(cls, eating_day):
        return cls.get_by_eating_day(eating_day, settings.EATING_SALES_SETTINGS)

    @classmethod
    def get_adjust_days(cls, day, date_settings):
        dt_list = [(x[0], dt.datetime.strptime(x[1], '%Y-%m-%d').date()) for x in date_settings]
        dt_days = [y[0] for y in dt_list if y[1] <= day][-1]
        return dt_days

    @classmethod
    def get_adjust_days_settings(cls, day):
        return cls.get_adjust_days(day, settings.EATING_SALES_SETTINGS)


class OrderChangableDayUtil:
    """
    食数変更可能日時クラス
    """

    @classmethod
    def get_rule_version(cls, current_day, hour, date_settings):
        if hour >= 10:
            current_day += relativedelta(days=1)
        dt_list = [(x[0], dt.datetime.strptime(x[1], '%Y-%m-%d').date()) for x in date_settings]
        dt_ver = [y[0] for y in dt_list if y[1] <= current_day][-1]
        return dt_ver

    @classmethod
    def get_rule_version_by_settings(cls, current_day):
        return cls.get_rule_version(current_day.date(), current_day.hour, settings.ORDER_CHANGEABLE_SETTINGS)
