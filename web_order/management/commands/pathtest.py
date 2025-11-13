import os
import re

import pandas as pd

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from web_order.models import MonthlyMenu, FoodPhoto
import logging
import zipfile
import platform

"""
    月間献立表から料理名を抜き出し、月間献立DBにレコードを追加する処理

# 引数
    filename: 月間献立表　M月.csv

# 献立DB
    Model: MonthlyMenu
    Model: FoodPhoto
"""


class Command(BaseCommand):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_uploading_replaced_path(self, sp, border):
        self.logger.info(sp)
        if len(sp) >= border:
            if sp[2] in ['ソフト', 'ミキサー', 'ゼリー']:
                if len(sp) > 3:
                    index = 3
                    filename = sp[3]
                else:
                    filename = None
            else:
                index = 2
                filename = sp[2]

            if filename:
                # 半角空白を全角空白へ
                filename = filename.replace(' ', '　')

                # 半角数字の変換(4以上は食種フォルダにないため、変換しない)
                filename = filename.replace('１', '1')
                filename = filename.replace('２', '2')
                filename = filename.replace('３', '3')

                pre_path = sp[0:index]
                replaced = ''
                for x in pre_path:
                    replaced = os.path.join(replaced, x)
                replaced = os.path.join(replaced, filename)
                for x in sp[index + 1:]:
                    replaced = os.path.join(replaced, x)
                result = replaced.replace(os.sep, '/')
                self.logger.info(result)
                return result

        return None

    def handle(self, *args, **options):
        # zipファイルの展開
        zip_file_path = os.path.join(settings.MEDIA_ROOT, 'upload', '2023_2.zip')
        output_path = os.path.join(settings.OUTPUT_DIR, 'document')
        os.makedirs(output_path, exist_ok=True)  # 上書きOK
        top_folder_name = ''
        with zipfile.ZipFile(zip_file_path) as z:
            self.logger.info('ZIPファイル展開スタート')
            for info in z.infolist():
                info.filename = info.orig_filename.encode('cp437').decode('cp932')
                if platform.system() == 'Windows':
                    if os.sep != "/" and os.sep in info.filename:
                        info.filename = info.filename.replace(os.sep, "/")
                if not top_folder_name:
                    sp = info.filename.split("/")
                    top_folder_name = sp[0]
                self.logger.info(info.filename)

                # フォルダ名の表記ゆれの対応
                if info.is_dir():
                    res = re.match('^\d{4年}\d{1,2}年/?$', info.filename)
                    if res:
                        pass
                    else:
                        # 対象のフォルダ名
                        sp = info.filename[:-1].split('/')
                        replaced = self.get_uploading_replaced_path(sp, 3)
                        if replaced:
                            info.filename = replaced + '/'
                else:
                    sp = info.filename.split('/')
                    original_filename = sp[-1]
                    replaced = self.get_uploading_replaced_path(sp, 4)
                    if replaced:
                        info.filename = replaced

                z.extract(info, output_path)
            self.logger.info('ZIPファイル展開完了')
