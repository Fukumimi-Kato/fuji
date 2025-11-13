from django.core.management.base import BaseCommand
from web_order.models import UnitMaster, MenuDisplay, MealDisplay, Order
from accounts.models import User
import datetime as dt
from datetime import timedelta
import logging

# 新規施設を登録する際の必要処理にするか、日次処理としてcron登録するか検討

class Command(BaseCommand):

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)


        dt_str = '2023-11-21 01:00:00'  # 火曜日を指定すること
        start_day = dt.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

        # 時刻を除外して日付のみに変更
        start_day = start_day.date()

        date_list = []
        for i in range(49):  # 7週分を作成する
            date_list.append(start_day + timedelta(days=i))

        unit_list = UnitMaster.objects.filter(is_active=True)

        for unt in unit_list:

            order_exists = Order.objects.filter(unit_name=unt, eating_day=start_day)

            if (order_exists):
                log_message = str(unt.username) + ',' + str(unt.unit_name)
                log_message += ',' + str(start_day) + ',の週のレコードは作成済みです'
                logger.warning(log_message)

            else:
                log_message = str(unt.username) + ',' + str(unt.unit_name)
                log_message += ',の注文フォームを,'
                log_message += str(start_day) + ',の週から49日分を作成しました'
                logger.info(log_message)

                men_list = MenuDisplay.objects.filter(username=unt.username).order_by('id')
                for men in men_list:

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
