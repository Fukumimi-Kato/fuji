from django.core.management.base import BaseCommand
from web_order.models import JapanHoliday
import datetime as dt
from datetime import timedelta
import csv
import logging
import os
import requests

from django.conf import settings

# 内閣府が後悔する祝日情報を読み取り、システム内に保存する

class Command(BaseCommand):

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        # 内閣府　国民の祝日CSV
        url = 'https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv'
        response = requests.get(url)
        try:
            response.raise_for_status()
        except Exception as exc:
            logger.error('祝日CSVダウンロード失敗')
            raise exc

        # CSVファイルへ書き込み
        holiday_dir_path = os.path.join(settings.MEDIA_ROOT, 'download')
        os.makedirs(holiday_dir_path, exist_ok=True)  # 上書きOK

        holiday_file_path = os.path.join(holiday_dir_path, 'holiday.csv')
        file = open(holiday_file_path, 'wb')

        # ファイルを保存
        for chunk in response.iter_content(100000):
            file.write(chunk)
        file.close()

        # csvファイル読み込み
        date_time_now = dt.datetime.now()  # 現在の日時と時刻
        with open(holiday_file_path, encoding='cp932') as csvfile:
            # 実行年以降のデータを一旦削除
            date_now_year = date_time_now.replace(month=1, day=1)
            JapanHoliday.objects.filter(date__gte=date_now_year).delete()

            # ヘッダ行読み飛ばし
            header = next(csv.reader(csvfile))

            # CSVの内容をDBに登録
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                date = dt.datetime.strptime(row[0], '%Y/%m/%d')
                if date.year >= date_time_now.year:
                    JapanHoliday.objects.create(
                        date=date,
                        name=row[1]
                    )
