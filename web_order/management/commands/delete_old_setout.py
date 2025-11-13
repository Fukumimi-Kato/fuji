import datetime as dt
from datetime import timedelta
import logging

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from web_order.models import MonthlyMenu

class Command(BaseCommand):

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        # 現在の日時と時刻 日曜午前1時に実施
        today = dt.datetime.now().date()

        # より古い情報を削除する期日を取得
        start_day = today - dt.timedelta(days=7)  # 1w

        # 月間献立の削除
        log_message = '盛付指示書のうち,'
        log_message += str(start_day) + 'より古いものを削除します。'
        logger.info(log_message)
        month_menu_list = MonthlyMenu.objects.filter(eating_day__lt=start_day)
        for month_menu in month_menu_list:
            # FoodPhoto,EngeFoodDirectionはCASCADEなので、同時に削除される
            # FoodPhoto削除時に、アップロードした画像ファイルも削除される
            month_menu.delete()

        # サイズ変更後の画像(CACHEフォルダ以下にimageKitが出力したもの)は削除しない。
