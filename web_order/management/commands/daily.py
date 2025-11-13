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

        date_time_now = dt.datetime.now()  # 現在の日時と時刻

        youbi = date_time_now.weekday()  # 本日の曜日(月曜日が0〜日曜日が6)
        jikoku = int(date_time_now.strftime('%H'))  # 現在の時刻

        # 土曜の17時を締め切りとして、翌々週の火曜日以降の日時が最短の注文可能開始日
        if youbi == 6:  # 日曜日なら
            start_day = date_time_now + timedelta(days=16)
        elif youbi == 0:  # 月曜日なら
            start_day = date_time_now + timedelta(days=15)
        elif youbi == 1:
            start_day = date_time_now + timedelta(days=14)
        elif youbi == 2:
            start_day = date_time_now + timedelta(days=13)
        elif youbi == 3:
            start_day = date_time_now + timedelta(days=12)
        elif youbi == 4:
            start_day = date_time_now + timedelta(days=11)
        elif youbi == 5:  # 土曜日なら
            if jikoku >= 17:  # 17を過ぎていた場合
                start_day = date_time_now + timedelta(days=17)
            else:
                start_day = date_time_now + timedelta(days=10)
        else:
            start_day = date_time_now

        # 直近の週次バッチで作成済みの週（火曜日）
        weekly_start_day = start_day + timedelta(days=28)

        # 時刻を除外して日付のみに変更
        start_day = start_day.date()
        weekly_start_day = weekly_start_day.date()

        date_list = []
        for i in range(35):  # 5週分を作成する
            date_list.append(start_day + timedelta(days=i))

        unit_list = UnitMaster.objects.filter(is_active=True)

        for unt in unit_list:

            order_exists = Order.objects.filter(unit_name=unt, eating_day=weekly_start_day)

            if (order_exists):
                log_message = str(unt.username) + ',' + str(unt.unit_name)
                log_message += ',' + str(weekly_start_day) + ',の週のレコードは作成済みです'
                logger.warning(log_message)

            else:
                log_message = str(unt.username) + ',' + str(unt.unit_name)
                log_message += ',の注文フォームを,'
                log_message += str(start_day) + ',の週から35日分を作成しました'
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
