"""setout.py
盛付指示書に関連するモジュール
"""
import datetime as dt
from dateutil.relativedelta import relativedelta
from itertools import groupby
import openpyxl as excel
import os

from django.conf import settings

from .exceptions import SetoutDirectionNotExistError
from .models import FoodPhoto, EngeFoodDirection, MealMaster

class ImageClearRequest:
    """ImageClearRequest
    登録済み画像削除指示に関するクラス
    """

    @staticmethod
    def get_request_name(item_name: str):
        """
        formが生成するクリアするかどうかのInput内容を取得するためのname文字列を取得する。
        """
        return f'{item_name}-clear'


class EditSetoutDirecion:
    """EditSetoutDirecion
    更新対象の盛付説明情報を管理するクラス
    """

    def __init__(self, param_dict):
        self.food_id = param_dict.get('food_id', None)
        self.enge_id = param_dict.get('enge_id', None)
        self.menu_id = param_dict.get('menu_id', None)
        self.meal_name = param_dict.get('meal_name', '朝食')
        self.next = param_dict.get('next', None)
        self.prev = param_dict.get('prev', None)
        date_str = param_dict.get('date', None)
        if date_str:
            self.date = dt.datetime.strptime(date_str, '%Y-%m-%d')
        else:
            self.date = dt.datetime.now().date()

        self.meal_list = self.get_meal_list()

    def is_common_food(self):
        if self.food_id:
            return True
        else:
            return False

    def is_enge_food(self):
        if self.enge_id:
            return True
        else:
            return False

    def get_directions(self, queryset):
        list = queryset.order_by('menu__meal_name', 'id')
        directions = {}
        first_key = None
        for key, group in groupby(list, key=lambda x: x.menu.meal_name):
            if not first_key:
                first_key = key
            directions[key] = [x for x in group]

        return directions

    def get_common_directions(self, date, id=None):
        if id:
            qs = FoodPhoto.objects.filter(
                menu__isnull=False, menu__eating_day=date, id__gt=self.food_id).select_related('menu')
        else:
            qs = FoodPhoto.objects.filter(
                menu__isnull=False, menu__eating_day=date).select_related('menu')
        direction_list = self.get_directions(qs)
        return direction_list

    def get_enge_directions(self, date):
        qs = EngeFoodDirection.objects.filter(
            menu__isnull=False, menu__eating_day=self.date).select_related('menu')
        direction_list = self.get_directions(qs)
        return direction_list

    def get_meal_list(self):
        meal_list_tpl = MealMaster.objects.distinct().exclude(meal_name='間食').order_by('seq_order').values_list('meal_name')
        meal_list = [x[0] for x in meal_list_tpl]

        return meal_list

    def get_edit_target(self):
        meal_index = self.meal_list.index(self.meal_name)
        if self.next == 'on':
            # 次の情報を取得
            if self.food_id:
                if meal_index == 2:
                    enge_list = self.get_enge_directions(self.date)
                    if enge_list:
                        result_list = enge_list[self.meal_list[0]]
                        if result_list:
                            return ('enge', result_list, [x.id for x in result_list])
                else:
                    common_list = self.get_common_directions(self.date)
                    if common_list:
                        result_list = common_list[self.meal_list[meal_index + 1]]
                        if result_list:
                            return ('common', result_list, [x.id for x in result_list])
                raise SetoutDirectionNotExistError(message='月間献立対象なし')
            elif self.enge_id:
                # 現在は嚥下の情報を表示
                if meal_index == 2:
                    common_list = self.get_common_directions(self.date + relativedelta(days=1))
                    if common_list:
                        result_list = common_list[self.meal_list[0]]
                        if result_list:
                            return ('common', result_list, [x.id for x in result_list])
                else:
                    enge_list = self.get_enge_directions(self.date)
                    if enge_list:
                        result_list = enge_list[self.meal_list[meal_index + 1]]
                        if result_list:
                            return ('enge', result_list, [x.id for x in result_list])
                raise SetoutDirectionNotExistError(message='月間献立対象なし')
            else:
                # ありえない想定
                raise ValueError("パラメータエラー")
        elif self.prev == 'on':
            # 次の情報を取得
            if self.food_id:
                if meal_index == 0:
                    enge_list = self.get_enge_directions(self.date - relativedelta(days=1))
                    if enge_list:
                        result_list = enge_list[self.meal_list[2]]
                        if result_list:
                            return ('enge', result_list, [x.id for x in result_list])
                else:
                    common_list = self.get_common_directions(self.date)
                    if common_list:
                        result_list = common_list[self.meal_list[meal_index - 1]]
                        if result_list:
                            return ('common', result_list, [x.id for x in result_list])
                raise SetoutDirectionNotExistError(message='月間献立対象なし')
            elif self.enge_id:
                # 現在は嚥下の情報を表示
                if meal_index == 0:
                    common_list = self.get_common_directions(self.date)
                    if common_list:
                        result_list = common_list[self.meal_list[2]]
                        if result_list:
                            return ('common', result_list, [x.id for x in result_list])
                else:
                    enge_list = self.get_enge_directions(self.date)
                    if enge_list:
                        result_list = enge_list[self.meal_list[meal_index - 1]]
                        if result_list:
                            return ('enge', result_list, [x.id for x in result_list])
                raise SetoutDirectionNotExistError(message='月間献立対象なし')
            else:
                # ありえない想定
                raise ValueError("パラメータエラー")
        else:
            if self.enge_id:
                enge_list = self.get_enge_directions((self.date))
                if enge_list:
                    result_list = enge_list[self.meal_name]
                    if result_list:
                        return ('enge', result_list, [x.id for x in result_list])
            else:
                common_list = self.get_common_directions(self.date)
                if common_list:
                    result_list = common_list[self.meal_name]
                    if result_list:
                        return ('common', result_list, [x.id for x in result_list])

            raise SetoutDirectionNotExistError(message='月間献立対象なし')


class OutputSetoutHelper:
    """OutputSetoutHelper
    盛付指示書出力を補助するクラス
    """
    @classmethod
    def get_filename_without_extention(cls, date):
        return f"献立指示書_{date.strftime('%Y-%m-%d')}"

    @classmethod
    def get_prev_enge_option(cls, date):
        # 前の日付の取得
        prev_day = date - relativedelta(days=1)

        # 盛付指示書参照
        prev_day_str = prev_day
        base_filename = cls.get_filename_without_extention(prev_day_str)
        setout_output_dir = os.path.join(settings.OUTPUT_DIR, 'setout', base_filename)
        prev_file_path = os.path.join(setout_output_dir, base_filename + '.xlsx')
        if os.path.isfile(prev_file_path):
            book = excel.load_workbook(prev_file_path)

            result = book['オプション・嚥下'].sheet_state == 'visible'
            book.close()
        else:
            result = False

        return result

    @classmethod
    def get_previous_direction(cls, date, name, get_func):
        # 前回最後に登場した同一料理名を取得
        last_food_ps = FoodPhoto.objects.filter(menu__eating_day__lte=date, menu__food_name=name).order_by('-menu__eating_day', '-id')
        for food in last_food_ps:
            value = get_func(food)
            if value:
                return value

        return ''

    @classmethod
    def get_previous_enge_direction(cls, date, name, get_func):
        # 前回最後に登場した同一料理名を取得
        last_food_ps = EngeFoodDirection.objects.filter(menu__eating_day__lte=date, menu__food_name=name).order_by('-menu__eating_day', '-id')
        for food in last_food_ps:
            value = get_func(food)
            if value:
                return value

        return ''
