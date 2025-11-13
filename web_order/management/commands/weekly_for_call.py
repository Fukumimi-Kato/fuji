from django.core.management.base import BaseCommand
from web_order.models import UnitMaster, MenuDisplay, MealDisplay, Order
import datetime as dt
from datetime import timedelta
import logging

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('date', nargs='+', type=str)
        parser.add_argument('units', nargs='+', type=str)

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        date_time_now = dt.datetime.now().date()
        in_date = options['date'][0]  # 呼び出し時の引数1つ目
        in_units = options['units'][0]  # 呼び出し時の引数1つ目
        date_time_start = dt.datetime.strptime(in_date, '%Y-%m-%d').date()
        while date_time_start.weekday() != 1:
            date_time_start += dt.timedelta(days=1)
        while date_time_now.weekday() != 1:
            date_time_now -= dt.timedelta(days=1)

        start_day = date_time_now
        hoge_day = start_day + dt.timedelta(days=42)
        end_day = date_time_start
        if end_day < hoge_day:
            end_day = hoge_day

        date_list = []
        sp = in_units.split(',')
        unit_ids = [int(x) for x in sp]
        while start_day <= end_day:
            for i in range(7):  # 7日分を作成する
                date_list.append(start_day + timedelta(days=i))

            unt_list = UnitMaster.objects.filter(is_active=True, id__in=unit_ids).order_by('id')  # id順にすべきか？
            for unt in unt_list:

                log_message = str(unt.username) + ',' + str(unt.unit_name)
                log_message += ',の注文フォームを,'
                log_message += str(start_day) + ',の週から7日分を作成しました'
                logger.info(log_message)

                men_list = MenuDisplay.objects.filter(username=unt.username).order_by('id')
                for men in men_list:
                    if men.menu_name.menu_name == '薄味':
                        logger.info('薄味は廃止のためスキップします。')
                        continue

                    mel_list = MealDisplay.objects.filter(username=unt.username).order_by('id')
                    for mel in mel_list:

                        for day in date_list:

                            Order.objects.create(
                                    unit_name_id=unt.id,
                                    menu_name_id=men.menu_name_id,
                                    meal_name_id=mel.meal_name_id,
                                    eating_day=day,
                                    allergen_id=1,
                            )

            date_list.clear()
            start_day += dt.timedelta(days=7)
