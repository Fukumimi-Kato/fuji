from django.core.management.base import BaseCommand
from web_order.models import UnitMaster, MenuDisplay, MealDisplay, Order
import datetime as dt
from datetime import timedelta
import logging

from accounts.models import User
from web_order.models import Order, OrderBackup, UnitMaster

class Command(BaseCommand):
    """
    契約変更-嚥下追加コマンド。嚥下の追加状態を反映する。
    嚥下の注文内容はあらかじめ登録しておくこと
    """

    def add_arguments(self, parser):
        # 有効日
        parser.add_argument('--date', type=str)

        # 施設のID
        parser.add_argument('--user', type=int, required=True)

    def get_duration(self, in_date):
        date_time_now = dt.datetime.now().date()

        # データ更新する注文データの末日
        date_time_start = in_date
        while date_time_start.weekday() != 1:
            date_time_start -= dt.timedelta(days=1)

        # データ更新する注文データの開始日
        while date_time_now.weekday() != 1:
            date_time_now += dt.timedelta(days=1)

        start_day = date_time_start
        hoge_day = start_day + dt.timedelta(days=43)
        end_day = date_time_now
        if end_day < hoge_day:
            end_day = hoge_day

        return start_day, end_day

    def restore(self, backups):
        for backup in backups:
            order = Order.objects.filter(unit_name=backup.unit_name, eating_day=backup.eating_day,
                                        menu_name__menu_name=backup.menu_name, meal_name__meal_name=backup.meal_name).first()
            if order:
                order.quantity = backup.quantity
                order.save()

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        # 施設情報取得
        user_id = options['user']
        user = User.objects.get(id=user_id)

        in_date = options['date']
        date_time_start = dt.datetime.strptime(in_date, '%Y-%m-%d').date()
        start_day, end_day = self.get_duration(date_time_start)
        logger.info(f'{start_day}～{end_day}')
        print(f'{start_day}～{end_day}')

        unit_list = list(UnitMaster.objects.filter(username=user, is_active=True).order_by('seq_order'))
        for unit in unit_list:
            # 既存のバックアップを削除する。
            OrderBackup.objects.filter(unit_name=unit, eating_day__range=[start_day, end_day]).delete()

            order_qs = Order.objects.filter(
                unit_name=unit, eating_day__range=[start_day, end_day],
                allergen_id=1).select_related('meal_name', 'menu_name').order_by('id')
            backups = []
            for order in order_qs:
                # 対象期間の食数のバックアップを保存する。
                backup = OrderBackup(unit_name=unit, eating_day=order.eating_day,
                                     meal_name=order.meal_name.meal_name, menu_name=order.menu_name.menu_name,
                                     quantity=order.quantity, allergen_id=1)
                backup.save()
                if backup.quantity:
                    if backup.quantity > 0:
                        logger.info(f'バックアップ実施:{backup.quantity}')
                        backups.append(backup)

                # 発注を削除する。
                order.delete()

        # 発注の再作成
        date_list = []
        while start_day <= end_day:
            for i in range(7):  # 7日分を作成する
                date_list.append(start_day + timedelta(days=i))

            for unt in unit_list:

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

        # バックアップした食数を反映する
        self.restore(backups)
