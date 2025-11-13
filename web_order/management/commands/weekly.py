from django.core.management.base import BaseCommand
from web_order.models import UnitMaster, MenuDisplay, MealDisplay, Order
import datetime as dt
from datetime import timedelta
import logging

class Command(BaseCommand):

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        # 現在の日時と時刻 日曜午前1時に実施
        # (手動実行時は、日曜日に実行するか、下記を日曜日の日付に書き換えて実行すること。そうでないと、仮注文入力画面の入力欄にズレが発生する)
        date_time_now = dt.datetime.now()

        # 約1ヶ月先の入力枠を1週間分用意するため
        start_day = date_time_now + dt.timedelta(days=44)  # 7dx6w+2d

        # 時刻を除外して日付のみに変更
        start_day = start_day.date()

        date_list = []
        for i in range(7):  # 7日分を作成する
            date_list.append(start_day + timedelta(days=i))

        unt_list = UnitMaster.objects.filter(is_active=True).order_by('id')  # id順にすべきか？
        for unt in unt_list:

            log_message = str(unt.username) + ',' + str(unt.unit_name)
            log_message += ',の注文フォームを,'
            log_message += str(start_day) + ',の週から7日分を作成しました'
            logger.info(log_message)

            men_list = MenuDisplay.objects.filter(username=unt.username).order_by('menu_name__seq_order')
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
