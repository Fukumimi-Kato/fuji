import datetime as dt
from datetime import timedelta
import logging
import os
import qrcode

from django.conf import settings
from django.core.management.base import BaseCommand
from web_order.models import UnitMaster
from web_order.picking import QrCodeUtil

class Command(BaseCommand):
    PICKING_MEAL_VALUES = {
        '01',
        '02',
        '03',
    }
    PICKING_TYPE_VALUES = [
        '01',   # 基本食
        '02',   # 嚥下食
        '03',   # 汁・汁具
        '04',   # 原体
    ]

    logger = logging.getLogger(__name__)


    def handle(self, *args, **options):
        # 画像ファイル保存先
        image_dir_path = QrCodeUtil.get_image_path_root()
        os.makedirs(image_dir_path, exist_ok=True)  # 上書きOK

        unt_list = UnitMaster.objects.filter(is_active=True).exclude(unit_code__range=[80001, 80008]).order_by('id')  # id順にすべきか？
        for unt in unt_list:
            log_message = str(unt.username) + ',' + str(unt.unit_name)
            log_message += ',QRコード画像を作成します。'
            self.logger.info(log_message)

            # 中袋、ピッキング指示書用の画像を作成
            for meal in self.PICKING_MEAL_VALUES:
                for picking_type in self.PICKING_TYPE_VALUES:
                    # 喫食日ごとのQRコードを出力
                    for day in range(1, 32):
                        qr_value = QrCodeUtil.get_value_v2(unt, meal, picking_type, day)
                        path = os.path.join(image_dir_path, QrCodeUtil.get_file_name_by_value(qr_value))
                        if not os.path.isfile(path):
                            # 既存は上書きしない
                            qr = qrcode.QRCode(
                                version=2,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=2,
                                border=4
                            )

                            qr.add_data(qr_value)
                            qr.make()

                            img = qr.make_image(fill_color="black", back_color="#ffffff")
                            img.save(path)

                        # 配送リスト(配送用段ボールに使用)用の画像を作成
                        qr_transfer_value = QrCodeUtil.get_all_in_value_v2(unt, meal, day)
                        path = os.path.join(image_dir_path, QrCodeUtil.get_file_name_by_prefix_all_value_v2(qr_transfer_value, day))
                        if not os.path.isfile(path):
                            qr = qrcode.QRCode(
                                version=2,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=2,
                                border=4
                            )
                            self.logger.debug('配送リスト(配送用段ボールに使用)用の画像')
                            self.logger.debug(qr_transfer_value)
                            qr.add_data(qr_transfer_value)
                            qr.make()

                            # 既存は上書きしない
                            img = qr.make_image(fill_color="black", back_color="#ffffff")
                            img.save(path)

        """
        log_message = 'サンシティ混ぜご飯用QRコード画像を作成します。'
        self.logger.info(log_message)

        mix_rice_number = [904, 903]
        for number in mix_rice_number:
            for meal in self.PICKING_MEAL_VALUES:
                for picking_type in self.PICKING_TYPE_VALUES:
                    qr = qrcode.QRCode(
                        version=2,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=2,
                        border=4
                    )

                    qr_value = QrCodeUtil.get_value_from_number(number, meal, picking_type)
                    self.logger.debug(qr_value)
                    qr.add_data(qr_value)
                    qr.make()

                    img = qr.make_image(fill_color="black", back_color="#ffffff")
                    path = os.path.join(image_dir_path, QrCodeUtil.get_file_name_by_value(qr_value))
                    img.save(path)
        """

