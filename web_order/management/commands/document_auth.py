from django.core.management.base import BaseCommand
from web_order.models import MenuDisplay, DocumentDirDisplay
from web_order.contract import ContractManager
from accounts.models import User
import datetime as dt
from datetime import timedelta
import logging


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--enable', nargs='?', default=None, type=str)

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)

        in_enable_at = options['enable']
        if in_enable_at:
            sp = in_enable_at.split('-')
            year = int(sp[0])
            month = int(sp[1])
            enable_date = dt.date(year, month, 1)
        else:
            now = dt.datetime.now()  # 現在の日時と時刻
            enable_date = dt.date(now.year, now.month, 1)
        print(enable_date)

        user_list = User.objects.filter(is_active=True)
        manager = ContractManager()
        manager.read_all()

        for user in user_list:

            # 既存データの削除
            DocumentDirDisplay.objects.filter(username=user, enable_date=enable_date).delete()

            menu_qs = MenuDisplay.objects.filter(username=user).order_by('username')
            contracts = manager.get_user_contract(user)

            for menu in menu_qs:
                plate = contracts.get_soup_contract_name(menu.menu_name.menu_name)
                if plate:
                    DocumentDirDisplay.objects.create(
                        username=user,
                        plate_dir_name=plate,
                        enable_date=enable_date
                    )
