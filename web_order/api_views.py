from datetime import timedelta
import datetime
from dateutil.relativedelta import relativedelta
from itertools import groupby
import json
import math
import logging
import re
import traceback
import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from accounts.models import User
from .api_models import OperatedUnit, OrderRateOutput, UnitOrder, MixRiceStructureOutput, GosuCalculationItemOutput, \
    GosuCalculationOutput
from .encrypt import Encrypt
from .models import NewYearDaySetting, UserOption, GenericSetoutDirection, \
    UnitMaster, Order, OrderRice, UserCreationInput, AggMeasureMixRiceMaster, MixRiceDay, MealDisplay, NewUnitPrice, \
    MenuDisplay, GosuLogging, UnitGosuLogging
from .serializers import OperatedUnitSerializer, OrderRateInputSerializer, OrderRateOutputSerializer, \
    MixRiceStructureInputSerializer, MixRiceStructureOutputSerializer, GosuCalculationSerializer, GosuLogInputSerializer


logger = logging.getLogger(__name__)


def invoice_auth_api(request):
    passwd = request.META.get('HTTP_X_AUTH', None)
    if passwd:
        invoice_pass = request.user.invoice_pass
        if invoice_pass and (passwd == invoice_pass):
            id = str(uuid.uuid4())
            request.session['onetime_token'] = id
            return HttpResponse(id)
    return HttpResponse(status=403)


def get_stetout_direction(request):
    if not request.user.is_staff:
        return HttpResponse('このリクエストは処理できません', status=403)

    id = request.GET.get('direction_id', None)
    if id:
        try:
            direction = GenericSetoutDirection.objects.get(id=id)
            return HttpResponse(direction.direction)
        except Exception as e:
            return HttpResponse(status=404)
    return HttpResponse(status=400)


def show_new_year_api(request):
    now = datetime.datetime.now()
    hour = int(now.strftime('%H'))  # 現在の時刻
    today = now.date()

    # 対象施設の特別対応取得
    qs_user_option = UserOption.objects.filter(unlock_limitation=True)
    user_option = None
    for usr in qs_user_option:
        if usr.username_id == request.user.id:
            user_option = usr
            break

    to_date = (today - timedelta(days=7)) if user_option else today

    settings = NewYearDaySetting.objects.filter(year=today.year + 1, enable_date_from__lte=today, enable_date_to__gte=to_date)
    if settings.exists():
        # 10時を入力の起点にする
        setting = settings.first()
        if (setting.enable_date_from == today) and (hour < 10):
            # 表示期間の開始日でも10時前なら、画面を表示しない
            return HttpResponse(0)
        elif (setting.enable_date_to == to_date) and (hour >= 17):
            # 表示期間の終了日でも10時以後なら、画面を表示しない
            return HttpResponse(0)
        else:
            return HttpResponse(1)
    else:
        return HttpResponse(0)


def _authenticate_key(secret):
    if secret:
        raw_key = Encrypt.b64_decode(secret)
        return raw_key == settings.WEB_API_KEY
    else:
        return False


class FixOrders:
    def __init__(self):
        # 針刺し用(基本20、ソフト10)
        self.basic_needle_orders = 20
        self.soft_needle_orders = 10
        self.jelly_needle_orders = 0
        self.mixer_needle_orders = 0

        # 保存用
        self.saved_orders = 50

        # 保存用(1人袋) 基本食(保存0+写真2+注文数1の施設数)
        self.saved_1p_basic = 2

        # 保存用(1人袋) ソフト3、ゼリー・ミキサー各1
        self.saved_1p_soft = 3
        self.saved_1p_jelly = 1
        self.saved_1p_mixer = 1

        # 保存用(50g)　基本・ソフト・ゼリー・ミキサー各1
        self.saved_50g_basic = 1
        self.saved_50g_soft = 1
        self.saved_50g_jelly = 1
        self.saved_50g_mixer = 1

    @property
    def order_total(self):
        """
        固定分全て(基本食・嚥下)の食数を
        """
        return self.basic_needle_orders + self.soft_needle_orders + self.jelly_needle_orders + \
               self.mixer_needle_orders + self.saved_orders + self.saved_1p_basic + self.saved_1p_soft + \
               self.saved_1p_jelly + self.saved_1p_mixer + self.saved_50g_basic + self.saved_50g_soft + \
               self.saved_50g_jelly + self.saved_50g_mixer

    @property
    def basic_needle_packs(self):
        return self.basic_needle_orders / 10

    @property
    def basic_saved_packs(self):
        return self.saved_orders / 10

    @property
    def soft_orders(self):
        return self.saved_1p_soft + self.soft_needle_orders + self.saved_50g_soft

    @property
    def jelly_orders(self):
        return self.saved_1p_jelly + self.jelly_needle_orders + self.saved_50g_jelly

    @property
    def mixer_orders(self):
        return self.saved_1p_mixer + self.mixer_needle_orders + self.saved_50g_mixer


class OperatedUnitsView(APIView):
    def _get_operate_status(self, unit):
        if unit.is_active:
            return '運用中'
        else:
            return '注文停止中'

    def _get_operated_units(self):
        unit_qs = UnitMaster.objects.all().exclude(unit_code__range=[80001, 80008]).order_by('unit_number')
        return [OperatedUnit(
            id=x.id, code=x.unit_number, name=x.unit_name, status=self._get_operate_status(x)) for x in unit_qs]

    def get(self, request):
        api_key = request.GET.get('key', '')
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        units = self._get_operated_units()
        serializer = OperatedUnitSerializer(units, many=True)
        return Response(serializer.data)


class OrdersRateView(APIView):
    """
    発注数比率取得API
    """
    WEEKDAY_LIST = ['月', '火', '水', '木', '金', '土', '日']
    MEAL_LIST = ["朝食", "昼食", "夕食"]

    def __init__(self):
        self.stored_is_contract_soup_filling = {}

    def _get_enable_eating_day(self, target_day, limit_day, week_setting):
        enables = []
        first_index = target_day.day // 7
        while target_day >= limit_day:
            week_index = target_day.day // 7
            if (week_index in week_setting) and (week_index == first_index):
                enables.append(target_day)
            target_day -= relativedelta(days=7)
        return enables

    def _get_alternative_orders_custom(self, eating_day, meal, unit, logic, creation_input, is_mix_rice_meal):
        if creation_input:
            limit_day = creation_input.enable_start_day
        else:
            limit_day = datetime.datetime(year=2024, month=1, day=2).date()

        # 期限日までの有効日リストを作成
        target_day = eating_day
        target_weekday = target_day.weekday()
        weekday = self.WEEKDAY_LIST[target_weekday]
        enable_eatings = self._get_enable_eating_day(target_day, limit_day, logic.get_weekday(weekday))

        meal_setting = logic.get_meal_setting(meal)
        logger.info(f'meal:{meal}-meal_setting:{meal_setting}')
        if meal_setting == "disabled":
            return 0, 0, 0, 0, 0, 0
        elif meal_setting is None:
            meal_setting = meal

        if logic.menu_settings:
            # 食事種類の設定がある場合
            menu_settings = logic.menu_settings

            if is_mix_rice_meal:
                basic_quantity = 0
                soft_quantity = 0
                jelly_quantity = 0
                mixer_quantity = 0
                is_1p = False
                qs = Order.objects.filter(
                    unit_name=unit, eating_day__in=enable_eatings, quantity__gt=0,
                    meal_name__meal_name=meal_setting).select_related('menu_name').order_by('-eating_day')
                for key, group in groupby(qs, key=lambda x: x.eating_day):
                    # 有効喫食日の降順で集計
                    list_group = list(group)

                    not_1p_order = False
                    unit_quantity = sum([x.quantity for x in list_group])
                    if unit_quantity:
                        for menu_key, value in menu_settings.items():
                            if value == "-":
                                # 取得対象喫食日が過去の場合は、取得数から除く
                                # (指摘喫食日当日が0であることは、本メソッドに入った時点で確定済みのため、ここでは無条件に除外対象になる)
                                key_unit_quantity = sum(
                                    [x.quantity for x in list_group if x.menu_name.menu_name == menu_key])
                                unit_quantity -= key_unit_quantity
                                continue

                            key_unit_quantity = sum(
                                [x.quantity for x in list_group if x.menu_name.menu_name == menu_key])
                            if not key_unit_quantity:
                                # 置き換え対象の献立種類の食数が0のため、置き換え先の食数を取得
                                alter_unit_quantity = sum(
                                    [x.quantity for x in list_group if x.menu_name.menu_name == value])
                                if alter_unit_quantity:
                                    key_unit_quantity = alter_unit_quantity
                                    unit_quantity += alter_unit_quantity

                            if key_unit_quantity:
                                # 各献立種類に合わせて集計
                                if menu_key == '常食':
                                    basic_quantity += key_unit_quantity
                                    if key_unit_quantity == 1:
                                        is_1p = True
                                    else:
                                        not_1p_order = True
                                elif menu_key == 'ソフト':
                                    basic_quantity += key_unit_quantity
                                elif menu_key == 'ゼリー':
                                    jelly_quantity += key_unit_quantity
                                elif menu_key == 'ミキサー':
                                    mixer_quantity += key_unit_quantity
                        if unit_quantity > 0:
                            # 無効化によって数が減る場合もあるので、再確認
                            count_1p = 1 if is_1p and (not not_1p_order) else 0
                            return unit_quantity, basic_quantity, count_1p, soft_quantity, jelly_quantity, mixer_quantity
                    # unit_quantityがない場合、置き換え先もないため、次(さらに過去)の喫食日の集計を行う
            else:
                qs = Order.objects.filter(
                    unit_name=unit, eating_day__in=enable_eatings, quantity__gt=0,
                    meal_name__meal_name=meal_setting).select_related('menu_name').order_by('-eating_day')
                for key, group in groupby(qs, key=lambda x: x.eating_day):
                    # 有効喫食日の降順で集計
                    list_group = list(group)
                    unit_quantity = sum([x.quantity for x in list_group])
                    if unit_quantity:
                        for menu_key, value in menu_settings.items():
                            if value == "-":
                                # 取得対象喫食日が過去の場合は、取得数から除く
                                # (指摘喫食日当日が0であることは、本メソッドに入った時点で確定済みのため、ここでは無条件に除外対象になる)
                                key_unit_quantity = sum(
                                    [x.quantity for x in list_group if x.menu_name.menu_name == menu_key])
                                unit_quantity -= key_unit_quantity
                                continue

                            key_unit_quantity = sum([x.quantity for x in list_group if x.menu_name.menu_name == menu_key])
                            if not key_unit_quantity:
                                # 置き換え対象の献立種類の食数が0のため、置き換え先の食数を取得
                                alter_unit_quantity = sum([x.quantity for x in list_group if x.menu_name.menu_name == value])
                                if alter_unit_quantity:
                                    unit_quantity += alter_unit_quantity
                        if unit_quantity > 0:
                            # 無効化によって数が減る場合もあるので、再確認
                            return unit_quantity, 0, 0, 0, 0, 0
                    # unit_quantityがない場合、置き換え先もないため、次(さらに過去)の喫食日の集計を行う
        else:
            if is_mix_rice_meal:
                # 献立種類の設定がない場合(献立種類による置き換えは行わない)
                qs = Order.objects.filter(
                    unit_name=unit, eating_day__in=enable_eatings, quantity__gt=0,
                    meal_name__meal_name=meal_setting).select_related('menu_name').order_by('-eating_day')
                for key, group in groupby(qs, key=lambda x: x.eating_day):
                    unit_quantity = 0
                    basic_quantity = 0
                    soft_quantity = 0
                    jelly_quantity = 0
                    mixer_quantity = 0
                    is_1p_list = []
                    not_1p_order = False
                    for order in group:
                        unit_quantity += order.quantity
                        menu_name = order.menu_name.menu_name
                        if menu_name == '常食':
                            basic_quantity += order.quantity
                            if order.quantity == 1:
                                is_1p_list.append(order)
                            else:
                                not_1p_order = True
                        elif menu_name == 'ソフト':
                            soft_quantity += order.quantity
                        elif menu_name == 'ゼリー':
                            jelly_quantity += order.quantity
                        elif menu_name == 'ミキサー':
                            mixer_quantity += order.quantity
                    if unit_quantity:
                        count_1p = 1 if len(is_1p_list) == 1 else 0
                        return unit_quantity, basic_quantity, count_1p, soft_quantity, jelly_quantity, mixer_quantity
            else:
                # 献立種類の設定がない場合(献立種類による置き換えは行わない)
                qs = Order.objects.filter(
                    unit_name=unit, eating_day__in=enable_eatings, quantity__gt=0,
                    meal_name__meal_name=meal_setting).order_by('-eating_day')
                for key, group in groupby(qs, key=lambda x: x.eating_day):
                    unit_quantity = sum([x.quantity for x in group])
                    if unit_quantity:
                        return unit_quantity, 0, 0, 0, 0, 0

        return 0, 0, 0, 0, 0, 0

    def _get_alternative_orders_basic(self, eating_day, meal, unit, creation_input, is_mix_rice_meal):
        if creation_input:
            limit_day = creation_input.enable_start_day
        else:
            limit_day = datetime.datetime(year=2024, month=1, day=2).date()

        dt_day = relativedelta(days=7)
        target_day = eating_day - dt_day

        if is_mix_rice_meal:
            # 混ぜご飯のある喫食の場合
            qs = Order.objects.filter(
                unit_name=unit, eating_day__lte=target_day, eating_day__gte=limit_day, quantity__gt=0,
                meal_name__meal_name=meal).select_related('menu_name').order_by('-eating_day')
            for key, group in groupby(qs, key=lambda x: x.eating_day):
                while target_day > key:
                    target_day -= dt_day
                if key != target_day:
                    # 同じ曜日でないものは除外する
                    continue
                group_list = list(group)

                # 基本食の集計
                unit_quantity = 0
                basic_quantity = 0
                soft_quantity = 0
                jelly_quantity = 0
                mixer_quantity = 0
                order_1p_list = []
                not_1p_order = False
                for order in group_list:
                    unit_quantity += order.quantity

                    ordered_menu_name = order.menu_name.menu_name
                    if ordered_menu_name == '常食':
                        basic_quantity += order.quantity
                        if order.quantity == 1:
                            order_1p_list.append(order.id)
                        else:
                            not_1p_order = True

                    # 嚥下の集計
                    if ordered_menu_name == 'ソフト':
                        soft_quantity += order.quantity
                    elif ordered_menu_name == 'ゼリー':
                        jelly_quantity += order.quantity
                    elif ordered_menu_name == 'ミキサー':
                        mixer_quantity += order.quantity

                if unit_quantity:
                    if (len(order_1p_list) == 1) and (not not_1p_order):
                        basic_1p_quantity = 1
                    else:
                        basic_1p_quantity = 0
                    return unit_quantity, basic_quantity, basic_1p_quantity, soft_quantity, jelly_quantity, mixer_quantity
        else:
            qs = Order.objects.filter(
                unit_name=unit, eating_day__lte=target_day, eating_day__gte=limit_day, quantity__gt=0,
                meal_name__meal_name=meal).order_by('-eating_day')
            for key, group in groupby(qs, key=lambda x: x.eating_day):
                while target_day > key:
                    target_day -= dt_day
                if key != target_day:
                    # 同じ曜日でないものは除外する
                    continue
                group_list = list(group)
                unit_quantity = sum([x.quantity for x in group_list])
                if unit_quantity:
                    return unit_quantity, 0, 0, 0, 0, 0

        if creation_input:
            qs = creation_input.default_orders.filter(meal_name=meal)
            if qs.exists():
                unit_quantity = 0.000
                if is_mix_rice_meal:
                    basic_quantity = 0
                    soft_quantity = 0
                    jelly_quantity = 0
                    mixer_quantity = 0
                    only_1p_list = []
                    not_1p_order = False
                    for default_orders in qs:
                        unit_quantity += default_orders.quantity
                        if default_orders.menu_name == '常食':
                            basic_quantity += default_orders.quantity
                            if default_orders.quantity == 1:
                                only_1p_list.append(default_orders)
                        elif default_orders.menu_name == 'ソフト':
                            soft_quantity += default_orders.quantity
                        elif default_orders.menu_name == 'ゼリー':
                            jelly_quantity += default_orders.quantity
                        elif default_orders.menu_name == 'ミキサー':
                            mixer_quantity += default_orders.quantity
                    if (len(only_1p_list) == 1) and (not not_1p_order):
                        flag_1p = True
                    else:
                        flag_1p = False
                    return unit_quantity, basic_quantity, 1 if flag_1p else 0, soft_quantity, jelly_quantity, mixer_quantity
                else:
                    for default_orders in qs:
                        unit_quantity += default_orders.quantity
                    return unit_quantity, 0, 0, 0, 0, 0
            else:
                return 0, 0, 0, 0, 0, 0
        else:
            return 0, 0, 0, 0, 0, 0

    def _get_logic(self, unit, logic_list, eating_day):
        for logic in logic_list:
            if logic.user_id == unit.id:
                if logic.from_day and logic.to_day:
                    # 有効期間の設定がある場合
                    if (eating_day >= logic.from_day) and (eating_day <= logic.to_day):
                        # 対象喫食日が有効期限内ならロジック使用
                        return logic
                    else:
                        # 基本パターン使用
                        return None
                else:
                    # 設定期間の設定が無ければ無条件で適用
                    return logic
        # 基本パターン使用
        return None

    def _generate_past_order_rice_day(self, eating_day, mix_rice_name):
        current_day = eating_day
        mix_rice_day = MixRiceDay.objects.filter(
            eating_day__lt=current_day, mix_rice_name=mix_rice_name).order_by('-eating_day')
        for mix_rice in mix_rice_day:
            yield mix_rice.eating_day

    def _get_gosu_quantity(self, unit, eating_day, mix_rice_name, gosu_logging):
        is_ignore = False
        # 契約を参照
        gosu_item_logging = UnitGosuLogging(gosu_logging=gosu_logging, unit=unit)
        new_price = NewUnitPrice.objects.filter(username=unit.username, eating_day__lt=eating_day).order_by(
            '-eating_day').first()
        if new_price:
            if new_price.price_lunch == 0:
                is_ignore = True
        else:
            disp = MenuDisplay.objects.filter(username=unit.username, menu_name__menu_name='常食').first()
            if disp:
                # 通常、disp=Noneはありえない
                if disp.price_lunch == 0:
                    is_ignore = True
        if is_ignore:
            logger.info('昼食の契約なし')
            # 合数ログの保存
            gosu_item_logging.status = '昼食の契約なし'
            gosu_item_logging.save()

            return 0.0

        order_rice_qs = OrderRice.objects.filter(unit_name=unit, eating_day=eating_day, quantity__gte=0)
        if order_rice_qs.exists():
            logger.info('合数注文を取得')
            quantity = sum([x.quantity for x in order_rice_qs])
            f_quantity = float(quantity)

            # 合数ログの保存
            gosu_item_logging.quantity = f_quantity
            gosu_item_logging.save()

            return f_quantity
        else:
            logger.info(f'過去の同じ混ぜご飯を検索:{mix_rice_name}')
            for past_day in self._generate_past_order_rice_day(eating_day, mix_rice_name):
                order_rice_qs = OrderRice.objects.filter(unit_name=unit, eating_day=past_day, quantity__gt=0)
                if order_rice_qs.exists():
                    quantity = sum([x.quantity for x in order_rice_qs])
                    logger.info(f'過去の合数を取得:{past_day}')
                    f_quantity = float(quantity)

                    # 合数ログの保存
                    gosu_item_logging.quantity = f_quantity
                    gosu_item_logging.status = '過去の合数を取得'
                    gosu_item_logging.save()

                    return f_quantity

            # 対象混ぜご飯の合数注文が存在しない場合
            logger.info(f'合数なし-注文数を検索:{unit}-{eating_day}')
            order_qs = Order.objects.filter(
                unit_name=unit, eating_day=eating_day, meal_name__meal_name='昼食', quantity__gt=0)
            if order_qs.exists():
                # 通常の注文数を元に計算する
                qty = sum([x.quantity for x in order_qs])
                logger.info(f'注文数から計算:{qty/3}')
                f_quantity = qty / 3

                # 合数ログの保存
                gosu_item_logging.quantity = f_quantity
                gosu_item_logging.status = '注文数から計算'
                gosu_item_logging.save()

                return f_quantity
            else:
                gosu_item_logging.quantity = 0.0
                gosu_item_logging.save()
                return 0.0

        gosu_item_logging.quantity = 0.0
        gosu_item_logging.save()
        return 0.0

    def _is_contract_soup_filling(self, unit):
        if unit.id in self.stored_is_contract_soup_filling:
            return self.stored_is_contract_soup_filling[unit.id]
        else:
            self.stored_is_contract_soup_filling[unit.id] = \
                MealDisplay.objects.filter(username=unit.username, meal_name__filling=True).exists()
            return self.stored_is_contract_soup_filling[unit.id]

    def _get_units(self):
        units = UnitMaster.objects.filter(is_active=True).exclude(unit_code__range=[80001, 80008]).\
            prefetch_related('reservedstop_set').order_by('unit_number', 'id')
        return list(units)

    def _get_fix_orders(self):
        orders = 0

        # 針刺し用(基本20、ソフト10)
        orders += 30

        # 保存用
        orders += 50

        # 保存用(1人袋) ソフト3、ゼリー・ミキサー各1
        orders += 5

        # 保存用(50g)　基本・ソフト・ゼリー・ミキサー各1
        orders += 4

        # 見本(1+1)
        orders += 2

        return orders

    def _get_mix_rice_package_quantity(self, timing_order, orders):
        mix_rice_quantity = timing_order.mix_rice_quantity
        total_quantity = mix_rice_quantity * orders
        mix_rice_liquid_quantity = timing_order.liquid_quantity
        total_liquid_quantity = mix_rice_liquid_quantity * orders
        logger.info(f'具と液：{timing_order.mix_rice_quantity}-{timing_order.liquid_quantity}/{total_quantity}-{total_liquid_quantity}')

        # 1000 = 1袋の最大数
        packages, mod = divmod(total_quantity + total_liquid_quantity, 1000)
        if mod:
            packages += 1
        if packages <= 0:
            packages = 1
        package_quantity = total_quantity / packages

        return package_quantity, packages, orders

    def _get_order_quantities(self, eating_day, meal, input, is_mix_rice_day):
        unit_order_list = []
        total_quantity = 0
        basic_total_quantity = 0
        basic_1p_quantity = 0
        soft_total_quantity = 0
        jelly_total_quantity = 0
        mixer_total_quantity = 0
        filling_total_quantity = 0
        gosu_total = 0
        dry_gosu = 0.0
        logic_list = input.logic_list

        logger.info(f'api:食数取得:(喫食日:{eating_day},食事区分:{meal})')

        # 混ぜご飯情報の取得
        mix_rice_day = MixRiceDay.objects.filter(eating_day=eating_day).first()

        # 対象喫食タイミングの情報を抽出
        timing_order = None
        for eating_timing_order in input.eating_list:
            if (eating_timing_order.eating_day == eating_day) and (eating_timing_order.meal in meal):
                timing_order = eating_timing_order
                break
        logger.info(f'api:timing_order={timing_order}')
        if timing_order:
            logger.info(f'{timing_order.mix_rice_quantity}')

        # 合数ログ用のインスタンスを作成
        need_gosu = is_mix_rice_day and (meal == '昼食')
        mix_rice_package_list = []
        gosu_logging = None
        if need_gosu and mix_rice_day:
            gosu_logging, is_create = GosuLogging.objects.get_or_create(eating_day=eating_day)
            if not is_create:
                UnitGosuLogging.objects.filter(gosu_logging=gosu_logging).delete()

        for unit in self._get_units():
            #　施設毎の発注数を計算する

            # 注文停止以降は計算を行わない
            reserved = None
            if unit.reservedstop_set.exists():
                reserved = unit.reservedstop_set.all().first()
                if reserved.order_stop_day <= eating_day:
                    # 注文停止対象日以降
                    logger.info(f'注文停止中のため、食数は取得しません({unit.unit_name}/停止:{reserved.order_stop_day})')
                    continue

            # 運用開始前は取得対象から外す
            user = unit.username
            creation_input = UserCreationInput.objects.filter(
                company_name=user.company_name, facility_name=user.facility_name).order_by('-id').first()
            if creation_input:
                if creation_input.enable_start_day > eating_day:
                    logger.info(f'運用開始前のため、食数は取得しません({unit.unit_name}/運用開始:{creation_input.enable_start_day})')
                    continue

            is_filling = self._is_contract_soup_filling(unit)

            # 停止設定がない or 注文停止対象日前
            unit_quantity = 0
            basic_unit_quantity = 0
            soft_unit_quantity = 0
            jelly_unit_quantity = 0
            mixer_unit_quantity = 0
            is_only_1p = False
            is_mix_rice_meal = need_gosu and mix_rice_day
            if is_mix_rice_meal:
                # 基本食/嚥下で分けて集計
                only_1p_list = []
                not_1p_order = False
                basic_qs = Order.objects.filter(
                    unit_name=unit, eating_day=eating_day, menu_name__menu_name='常食', quantity__gt=0,
                    meal_name__meal_name=meal)
                for basic_order in basic_qs:
                    basic_unit_quantity += basic_order.quantity
                    unit_quantity += basic_order.quantity
                    if basic_order.quantity == 1:
                        only_1p_list.append(basic_order.id)
                    else:
                        not_1p_order = True

                if (len(only_1p_list) == 1) and (not not_1p_order):
                    is_only_1p = True

                # ソフトの集計
                aggregate_dict = Order.objects.filter(
                    unit_name=unit, eating_day=eating_day, menu_name__menu_name='ソフト', quantity__gt=0,
                    meal_name__meal_name=meal).aggregate(sum_quantity=Sum('quantity'))
                soft_unit_quantity = aggregate_dict['sum_quantity'] or 0
                unit_quantity += soft_unit_quantity

                # ゼリーの集計
                aggregate_dict = Order.objects.filter(
                    unit_name=unit, eating_day=eating_day, menu_name__menu_name='ゼリー', quantity__gt=0,
                    meal_name__meal_name=meal).aggregate(sum_quantity=Sum('quantity'))
                jelly_unit_quantity = aggregate_dict['sum_quantity'] or 0
                unit_quantity += jelly_unit_quantity

                # ミキサーの集計
                aggregate_dict = Order.objects.filter(
                    unit_name=unit, eating_day=eating_day, menu_name__menu_name='ミキサー', quantity__gt=0,
                    meal_name__meal_name=meal).aggregate(sum_quantity=Sum('quantity'))
                mixer_unit_quantity = aggregate_dict['sum_quantity'] or 0
                unit_quantity += mixer_unit_quantity
            else:
                aggregate_dict = Order.objects.filter(
                    unit_name=unit, eating_day=eating_day,
                    meal_name__meal_name=meal).aggregate(sum_quantity=Sum('quantity'))
                unit_quantity += aggregate_dict['sum_quantity'] or 0
                soft_unit_quantity = 0
                jelly_unit_quantity = 0
                mixer_unit_quantity = 0

            # 注文数「0」入力の有無確認
            is_input_zero = False
            if not unit_quantity:
                if Order.objects.filter(
                    unit_name=unit, eating_day=eating_day, quantity=0, meal_name__meal_name=meal).exists():
                    logger.info(f'0件の注文あり=過去参照停止:{unit}')
                    is_input_zero = True

            if is_input_zero or unit_quantity:
                # 対象喫食日で取得出来た場合
                unit_order_list.append(
                    UnitOrder(unit.unit_number, unit.unit_name, unit_quantity, False)
                )
                total_quantity += unit_quantity
                if is_only_1p:
                    logger.info(f'{unit.unit_name}:1人袋')
                logger.info(f'{unit.unit_name}-{unit_quantity}=>{total_quantity}')

                basic_total_quantity += basic_unit_quantity
                basic_1p_quantity += 1 if is_only_1p else 0
                soft_total_quantity += soft_unit_quantity
                jelly_total_quantity += jelly_unit_quantity
                mixer_total_quantity += mixer_unit_quantity
            else:
                logic = self._get_logic(unit, logic_list, eating_day)
                if logic:
                    # 参照ロジックにしたがって、過去から注文数を取得
                    unit_quantities = self._get_alternative_orders_custom(
                        eating_day, meal, unit, logic, creation_input, is_mix_rice_meal)
                    if unit_quantities[2]:
                        logger.info(f'{unit.unit_name}:1人袋(特殊ロジック)')
                else:
                    # 基本参照パターン
                    unit_quantities = self._get_alternative_orders_basic(
                        eating_day, meal, unit, creation_input, is_mix_rice_meal)
                    if unit_quantities[2]:
                        logger.info(f'{unit.unit_name}:1人袋(基本ロジック)')
                unit_quantity = unit_quantities[0]
                total_quantity += unit_quantity
                basic_total_quantity += unit_quantities[1]
                basic_1p_quantity += unit_quantities[2]
                soft_total_quantity += unit_quantities[3]
                jelly_total_quantity += unit_quantities[4]
                mixer_total_quantity += unit_quantities[5]
                logger.info(f'{unit.unit_name}-{unit_quantity}=>{total_quantity}')
                if unit_quantity:
                    unit_order_list.append(
                        UnitOrder(unit.unit_number, unit.unit_name, unit_quantity, True)
                    )

            # 汁具比率の集計
            if is_filling:
                filling_total_quantity += unit_quantity
            else:
                pass

            # 合数の計算
            if need_gosu:
                if mix_rice_day:
                    # 合数の集計
                    unit_gosu = self._get_gosu_quantity(unit, eating_day, mix_rice_day.mix_rice_name, gosu_logging)
                    gosu_total += unit_gosu
                    logger.warning(f'{unit.unit_name}-合数:{unit_gosu}=>{gosu_total}')
                    if unit.username.dry_cold_type == '乾燥':
                        dry_gosu += unit_gosu
                        logger.warning(f'乾燥:{unit_gosu}=>{dry_gosu}')

                    # 混ぜご飯袋情報の取得
                    if unit_gosu:
                        tpl_package_info = self._get_mix_rice_package_quantity(timing_order, unit_gosu)
                        logger.warning(f'{unit.unit_name}-TPL:{tpl_package_info}')
                        mix_rice_package_list.append((unit, tpl_package_info[0], tpl_package_info[1], tpl_package_info[2]))
                else:
                    logger.warning(f'({eating_day})混ぜご飯の情報がありません。')

        # 針刺し袋サイズの袋量を取得
        needle_orders_per_pack = 0
        if is_mix_rice_meal:
            logger.info('混ぜご飯針刺し用-袋判定')
            max_package_size = 0
            packages_for_max = 0
            max_unit_gosu = 0
            for tpl_mix_rice in mix_rice_package_list:
                unit = tpl_mix_rice[0]
                package_size = tpl_mix_rice[1]
                packages = tpl_mix_rice[2]
                unit_gosu = tpl_mix_rice[3]

                if package_size > max_package_size:
                    max_package_size = package_size
                    packages_for_max = packages
                    max_unit_gosu = unit_gosu

                # 合数内容をログ出力
                logger.info(f'{unit.unit_name}-{package_size}-{packages}-{unit_gosu}=>max={max_package_size}-{packages_for_max}-{max_unit_gosu}')

            needle_orders_per_pack = max_unit_gosu * 3 / packages_for_max
            logger.info(f'混ぜご飯針刺し用-袋:内容量={max_package_size}-袋数={packages_for_max}-1袋の食数={needle_orders_per_pack}')
            gosu_logging.needle_quantity = max_package_size
            gosu_logging.needle_orders = needle_orders_per_pack

        # 食数固定分の追加
        fix_orders = FixOrders()
        total_quantity += fix_orders.order_total
        logger.info(f'固定食数分：{total_quantity}=>{total_quantity}')

        if total_quantity:
            if timing_order:
                rate = float(total_quantity) / float(timing_order.quantity)
            else:
                rate = 1.00000000

        if filling_total_quantity:
            if timing_order:
                filling_rate = float(filling_total_quantity) / float(timing_order.quantity)
            else:
                filling_rate = 1.00000000
        else:
            filling_rate = 1.00000000

        # 切り上げ
        total_quantity = math.ceil(total_quantity)
        gosu_total = math.ceil(gosu_total)

        logger.info(f'total_quantity:{total_quantity}')
        basic_1p_packs = fix_orders.saved_1p_basic + fix_orders.saved_50g_basic + basic_1p_quantity
        soft_orders = fix_orders.soft_orders + soft_total_quantity
        logger.info(f'ソフト食数:{fix_orders.soft_orders}-{soft_total_quantity}={soft_orders}')
        jelly_orders = fix_orders.jelly_orders + jelly_total_quantity
        logger.info(f'ゼリー食数:{fix_orders.jelly_orders}-{jelly_total_quantity}={jelly_orders}')
        mixer_orders = fix_orders.mixer_orders + mixer_total_quantity
        logger.info(f'ミキサー食数:{fix_orders.mixer_orders}-{mixer_total_quantity}={mixer_orders}')

        if gosu_logging:
            # 合数ログの保存
            gosu_logging.soft_orders = soft_orders
            gosu_logging.jelly_orders = jelly_orders
            gosu_logging.mixer_orders = mixer_orders
            gosu_logging.save()

        output = OrderRateOutput(eating_day=eating_day, meal=meal, rate=rate, soup_filling_rate=filling_rate,
                                 total=total_quantity, unit_order_list=unit_order_list, gosu_total=gosu_total,
                                 dry_gosu=dry_gosu,
                                 needle_quantity_per_pack=math.ceil(needle_orders_per_pack),
                                 needle_packs=fix_orders.basic_needle_packs,
                                 saved_packs=fix_orders.basic_saved_packs, saved_1_packs=basic_1p_packs,
                                 soft_orders=soft_orders, jelly_orders=jelly_orders,
                                 mixer_orders=mixer_orders)
        return output

    def is_mix_rice_day(self, eating_day):
        """
        指定した喫食日で、混ぜご飯の注文が存在するかどうかを判定する。
        合数注文の有無で判断
        """
        return OrderRice.objects.filter(eating_day=eating_day, quantity__gt=0).exists()

    def _get_rate_list(self, order_rate_input):
        output_list = []
        current_day = order_rate_input.from_day

        try:
            while current_day <= order_rate_input.to_day:
                logger.info(f'API:食数参照({current_day})')
                has_mix_rice = self.is_mix_rice_day(current_day)
                for meal in self.MEAL_LIST:
                    # 喫食タイミング毎に発注数取得+比率計算
                    output = self._get_order_quantities(current_day, meal, order_rate_input, has_mix_rice)
                    logger.info(f'API:食数参照結果:({output})')
                    output_list.append(output)
                current_day += relativedelta(days=1)
        except BaseException as e:
            logger.error('APIエラー')
            logger.error(e)
            raise e
        return output_list

    def post(self, request):
        logger.info('●食数参照APIリクエスト受信')
        # 認証
        api_key = request.META.get('HTTP_AUTHORIZATION', None)
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        try:
            logger.info(request.data)
            serializer = OrderRateInputSerializer(data=request.data)
            if serializer.is_valid():
                logger.info('リクエストパラメータ解析完了')
                order_rate_input = serializer.save()
                logger.info('リクエストパラメータ読込')

                rate_list = self._get_rate_list(order_rate_input)

                list_serializer = OrderRateOutputSerializer(rate_list, many=True)
                return Response(list_serializer.data)
            else:
                return HttpResponse(status=401)
        except Exception as e:
            logger.info(traceback.format_exc())
            raise e


class GosuInputView(APIView):
    def _get_gosu_rate(self, start, end):
        total_gosu = 0
        total_order_quantity = 0
        for rice_order in OrderRice.objects.filter(
                eating_day__range=[start, end], quantity__gt=0).values('unit_name').annotate(sum=Sum('quantity')):
            total_gosu += rice_order['sum']
            dict = Order.objects.filter(unit_name=rice_order['unit_name']).aggregate(sum=Sum('quantity'))
            total_order_quantity += dict['sum']

        if total_gosu and total_order_quantity:
            return total_order_quantity / total_gosu
        else:
            return 1.0

    def get(self, request):
        api_key = request.GET.get('key', '')
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        year = int(request.GET.get('year', '0'))
        month = int(request.GET.get('month', '0'))

        base_day = datetime.datetime(year=year, month=month, day=1)
        start_day = base_day - relativedelta(months=3)
        end_day = base_day - relativedelta(days=1)

        rate = self._get_gosu_rate(start_day.date(), end_day.date())
        return Response(rate)


class MixRiceStructureView(APIView):
    """
    混ぜご飯判定API
    """
    def _get_gosu_quantity_from_plate(self, plate: str, index: int = 0) -> float:
        """
        料理名から1合当たりの数量を取得する
        """
        replaced_name = plate.replace('ｇ', 'g')
        logger.info('_get_gosu_quantity_from_plate')
        logger.info(replaced_name)
        res = re.findall('(\d+|\d+.\d+)g', replaced_name)
        res2 = re.findall('(\d+|\d+.\d+)枚', replaced_name)
        if res:
            base_quantity = float(res[index])

            if ('１合' in plate) or ('1合' in plate) or ('一合' in plate):
                gosu_quantity = base_quantity
            else:
                gosu_quantity = base_quantity * 3
        if res2:
            gosu_quantity = float(res2[index])

        return gosu_quantity

    def _convert(self, plate_list, meal):
        is_find = False
        is_rice_completed = False
        mix_rice_list = [x for x in AggMeasureMixRiceMaster.objects.all()]
        converted_list = []
        mix_rice_name = None
        is_mix_package = False
        gosu_quantity = 0.00
        liquid_gosu_quantity = 0.00
        for index, plate in enumerate(plate_list):
            logger.info(f'{plate}の判定---')
            number = plate[0]
            is_mix_rice = False
            if not ('昼' in meal):
                # 昼食以外は、混ぜご飯に該当する名前であっても、混ぜご飯として判定しない
                is_mix_package = False
            elif number == '①':
                if is_rice_completed:
                    pass
                else:
                    # 該当する混ぜご飯マスタを抽出
                    for mix_rice_master in mix_rice_list:
                        if mix_rice_master.search_word in plate:
                            logger.info(f'混ぜご飯:{mix_rice_master.name}')
                            is_mix_rice = True
                            is_find = True
                            is_mix_package = mix_rice_master.is_mix_package
                            mix_rice_name = mix_rice_master.name
                            logger.info(f'混ぜご飯具液同封:{is_mix_package}')
                    if not is_mix_rice:
                        is_find = False
                        is_rice_completed = True
            elif number == '④' and is_find:
                is_mix_rice = True
                is_mix_package = False
            else:
                is_find = False
                is_rice_completed = True
                is_mix_package = False

            if is_mix_rice and (index == 0):
                # 混ぜご飯メイン料理の数量(通常はこちらのみ)
                logger.info('混ぜご飯メイン料理(main):')
                gosu_quantity = self._get_gosu_quantity_from_plate(plate)
                logger.info(f'数量:{gosu_quantity}')
            if is_mix_package and (index == 0):
                # 具と液同封の混ぜご飯の場合は、次の液の料理の量も取得する
                logger.info('液料理数量')
                liquid_gosu_quantity = self._get_gosu_quantity_from_plate(plate, 1)
                logger.info(f'数量:{liquid_gosu_quantity}')

            converted_list.append(MixRiceStructureOutput(
                name=mix_rice_name or 'none', plate_name=plate, is_mix_rice=is_mix_rice, gosu_quantity=gosu_quantity,
                gosu_liquid_quantity=liquid_gosu_quantity
            ))
        return converted_list

    def get(self, request):
        logger.info('●混ぜご飯構成取得API実行')
        api_key = request.GET.get('key', '')
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        serializer = MixRiceStructureInputSerializer(data=request.data)
        if serializer.is_valid():
            input = serializer.save()
            output_list = self._convert(input.plate_list, input.meal)
            list_serializer = MixRiceStructureOutputSerializer(output_list, many=True)
            return Response(list_serializer.data)
        else:
            return HttpResponse(status=401)

    def _save_mix_rice_day(self, eating_day, mix_rice_list):
        tmp_list = [x for x in mix_rice_list if x.is_mix_rice]
        if tmp_list:
            MixRiceDay.objects.update_or_create(
                eating_day=eating_day, defaults={'eating_day': eating_day, 'mix_rice_name': tmp_list[0].name})

    def post(self, request):
        logger.info('●混ぜご飯構成取得API実行')
        api_key = request.META.get('HTTP_AUTHORIZATION', None)
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        serializer = MixRiceStructureInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                input = serializer.save()

                output_list = self._convert(input.plate_list, input.meal)
                self._save_mix_rice_day(input.eating_day, output_list)

                list_serializer = MixRiceStructureOutputSerializer(output_list, many=True)
                return Response(list_serializer.data)
            except Exception as e:
                logger.info(traceback.format_exc())
                raise e
        else:
            return HttpResponse(status=401)


class GosuLogView(APIView):
    """
    合数ログ取得API
    """
    def _get_logs(self, eating_day):
        # 合数ログ内容を取得
        gosu_logging = GosuLogging.objects.filter(eating_day=eating_day).first()
        logging_list = []
        if gosu_logging:
            unit_log_qs = UnitGosuLogging.objects.filter(
                gosu_logging=gosu_logging).select_related('unit').order_by('unit__unit_number', 'id')
            for unit_log in unit_log_qs:
                output_item = GosuCalculationItemOutput(
                    unit_number=unit_log.unit.unit_number, unit_name=unit_log.unit.unit_name, status=unit_log.status,
                    quantity=unit_log.quantity
                )
                logging_list.append(output_item)

        output = GosuCalculationOutput(
            eating_day=eating_day, needle_quantity=gosu_logging.needle_quantity,
            needle_orders=gosu_logging.needle_orders, soft_quantity=gosu_logging.soft_orders,
            jelly_quantity=gosu_logging.jelly_orders, mixer_quantity=gosu_logging.mixer_orders,
            unit_logging_list=logging_list)
        return output

    def post(self, request):
        api_key = request.META.get('HTTP_AUTHORIZATION', None)
        if not _authenticate_key(api_key):
            return HttpResponse(status=400)

        serializer = GosuLogInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                input = serializer.save()

                output = self._get_logs(input.eating_day)

                serializer = GosuCalculationSerializer(output)
                return Response(serializer.data)
            except Exception as e:
                logger.info(traceback.format_exc())
                raise e
        else:
            return HttpResponse(status=401)
