from django.core.management.base import BaseCommand
from web_order.models import UnitMaster, MenuDisplay, MealDisplay, Order, ReservedStop
import datetime as dt
from datetime import timedelta
import logging

class Command(BaseCommand):

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        today = dt.datetime.now().date()

        # 予約を取得
        qs = ReservedStop.objects.filter(unit_name__username__is_active=True).select_related('unit_name').order_by('unit_name')

        for reserved in qs:

            unit = reserved.unit_name
            log_message = str(unit.username) + ',' + str(unit)
            log_message += ',の予約内容を確認'
            logger.info(log_message)

            if reserved.order_stop_day:
                if reserved.order_stop_day <= today:
                    if unit.is_active:
                        unit.is_active = False
                        unit.save()
                        logger.info('利用停止を実行。')
                    else:
                        logger.info('利用停止済みのため、更新しません。')

            if reserved.login_stop_day and (not unit.is_active):
                if reserved.login_stop_day <= today:
                    # qsのfilter条件により、is_activeの判定不要
                    user = unit.username
                    unit_qs = UnitMaster.objects.filter(is_active=True).exclude(username=user)
                    if unit_qs.exists():
                        logger.info('他に利用停止でないユニットが存在するため、ログイン停止できません。')
                    else:
                        user.is_active = False
                        user.save()
                        logger.info('ログイン停止を実行。')

