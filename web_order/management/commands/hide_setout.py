from django.core.management.base import BaseCommand
from web_order.models import SetoutDuration
import datetime as dt
from datetime import timedelta
import logging

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('date', nargs='+', type=str)

    def handle(self, *args, **options):
        """
        発行済みの盛付指示書を、施設に対し非表示にする
        """

        logger = logging.getLogger(__name__)
        logger.info('盛付指示書表示停止処理--開始')

        in_date = options['date'][0]  # 呼び出し時の引数1つ目
        if not in_date:
            logger.warning('入力パラメータ不正')
            return

        setout_name = f'盛付指示書_{in_date}'


        # 盛付指示書保持期間を取得
        qs = SetoutDuration.objects.filter(name=setout_name)
        if qs.exists():
            duration = qs.first()
            today = dt.datetime.now().date()
            if duration.last_enable < today:
                loger.info(f'[{setout_name}]既に表示停止済みです。')
                return
            else:
                # 停止させるため、現在値の1年前に更新
                duration.last_enable = duration.last_enable - timedelta(days=365)
                duration.save()
                logger.info(f'[{setout_name}]非表示にしました。')
        else:
            logger.warning(f'[{setout_name}]対象の盛付指示書表示が存在しません。')

