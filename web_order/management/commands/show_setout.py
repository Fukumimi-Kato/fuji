from django.core.management.base import BaseCommand
from web_order.models import SetoutDuration
import datetime as dt
from datetime import timedelta
import logging

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('setout_date', nargs='+', type=str)
        parser.add_argument('enable_date', nargs='+', type=str)

    def handle(self, *args, **options):
        """
        表示停止済みの盛付指示書を、施設に対し指定期間まで表示可能にする
        """

        logger = logging.getLogger(__name__)
        logger.info('盛付指示書表示再会処理--開始')

        in_date = options['setout_date'][0]  # 呼び出し時の引数1つ目
        if not in_date:
            logger.warning('入力パラメータ不正')
            return

        setout_name = f'盛付指示書_{in_date}'

        enable_date = options['enable_date'][0]  # 呼び出し時の引数2つ目
        setout_day = dt.datetime.strptime(enable_date, '%Y-%m-%d')
        setout_day = setout_day.date()  # 時刻部分を除外

        today = dt.datetime.now().date()
        limit = today - timedelta(365)
        if setout_day < limit:
            loger.info(f'[{setout_name}]再表示可能期限を超えているので、処理を中断します。')
            return

        # 盛付指示書保持期間を取得
        qs = SetoutDuration.objects.filter(name=setout_name)
        if qs.exists():
            duration = qs.first()

            # 指定日まで再表示可能に設定
            duration.last_enable = setout_day
            duration.save()
            logger.info(f'[{setout_name}]再表示しました。')
        else:
            logger.warning(f'[{setout_name}]対象の盛付指示書表示が存在しません。')

