from django.core.management.base import BaseCommand
from web_order.models import Order, UnitMaster

class Command(BaseCommand):
    def handle(self, *args, **options):

        units = UnitMaster.objects.all()
        for unit in units:
            unit.calc_name = unit.unit_name
            unit.save()


        '''
        odr = Order.objects.filter(unit_name_id=46, meal_name_id=1)  # みどりケアの「朝・汁具あり」を
        odr.update(meal_name_id=4)  # 「朝・具のみ」に更新

        odr = Order.objects.filter(unit_name_id=46, meal_name_id=2)  # みどりケアの「昼・汁具あり」を
        odr.update(meal_name_id=5)  # 「昼・具のみ」に更新

        odr = Order.objects.filter(unit_name_id=61, meal_name_id=7)  # こすもすの「朝・汁なし」を
        odr.update(meal_name_id=1)  # 「朝・汁具あり」に更新

        odr = Order.objects.filter(unit_name_id=61, meal_name_id=8)  # こすもすの「昼・汁なし」を
        odr.update(meal_name_id=2)  # 「昼・汁具あり」に更新

        '''
