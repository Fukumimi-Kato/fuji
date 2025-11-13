import io
import os
import re
import logging
import pandas as pd

from django.conf import settings
from django.db.models import Sum, Count
from django_pandas.io import read_frame

from .cooking_direction_plates import PlateNameAnalizeUtil
from .models import UnitPackage, Order, AllergenPlateRelations, CookingDirectionPlate, UncommonAllergenHistory, \
    UnitMaster, CommonAllergen, PlatePackageForPrint, PlateMenuForPrint
from .picking import EatingManagement

logger = logging.getLogger(__name__)


class DesignSealCsvWriter:
    def __init__(self, cooking_day, output_type: str):
        self.cooking_day = cooking_day
        self.output_type = output_type

        self.meal_list = []

    def read_eating_time(self):
        """
        喫食日に紐づく食事を読み込む
        """
        self.meal_list.clear()

        # 製造日に紐づく喫食日を取得する
        tmp_list = []
        eating_dict = EatingManagement.get_meals_dict_by_cooking_day(self.cooking_day)
        for key, meal_name_list in eating_dict.items():
            for meal_name in meal_name_list:
                tmp_list.append((key, meal_name))

        # ソート
        self.meal_list = sorted(tmp_list)

    def get_mix_rice_type_label(self, type: str):
        if type:
            if type == 'none':
                return '対象外'
            elif type == 'main':
                return 'メイン'
            elif type == 'parts':
                return 'パーツ'
            else:
                return type
        else:
            return '対象外'

    def get_soup_type_label(self, type: str):
        if type:
            if type == 'none':
                return '対象外'
            elif type == 'soup':
                return '汁(スープ)'
            elif type == 'filling':
                return '汁具'
            else:
                return type
        else:
            return '対象外'

    def get_output_meal(self, meal: str):
        if meal == '朝食':
            return '△朝食'
        elif meal == '昼食':
            return '〇昼食'
        elif meal == '夕食':
            return '□夕食'
        else:
            return meal

    def get_output_package(self, package: str):
        if package == 'ENGE_7':
            return '7人用'
        elif package == 'ENGE_14':
            return '14人用'
        elif package == 'ENGE_20':
            return '20人用'
        elif package == 'ENGE_2':
            return '2人用'
        elif package == 'BASIC_FRACTION':
            return '端数'
        elif package == 'BASIC_UNIT':
            return '施設毎'
        else:
            return package

    def write_for_basic(self):
        # 対象喫食日の全施設の情報を読み込む
        qs = UnitPackage.objects.filter(cooking_day=self.cooking_day, is_basic_plate=True, menu_name='常食').order_by(
            'register_at')
        all_df = read_frame(qs)
        qs_list = list(qs)

        unit_qs = UnitMaster.objects.all().exclude(unit_code__range=[80001, 80008]).values('unit_number', 'calc_name', 'short_name').distinct()
        unit_df = read_frame(unit_qs)
        unit_df = unit_df.append({'unit_number':4, 'calc_name':'社会福祉法人サンシティあい', 'short_name':'柊桜茜葵'}, ignore_index=True)
        all_df = pd.merge(
            all_df, unit_df,
            left_on=['unit_number', 'unit_name'],
            right_on=['unit_number', 'calc_name'],
            how='inner')

        # 個食の抽出
        koshoku_list = []
        self.read_eating_time()
        for eating_day, meal_name in self.meal_list:
            order_qs = Order.objects.filter(
                eating_day=eating_day, meal_name__meal_name=meal_name, allergen__allergen_name='なし',
                menu_name__menu_name='常食', quantity__gt=0).select_related('unit_name')
            for order in order_qs:
                if '個食' in order.unit_name.calc_name:
                    if order.quantity == 1:
                        # 1人用の袋になるため、シール出力対象外
                        continue
                    for unit_package in qs_list:
                        if (order.unit_name.unit_number == unit_package.unit_number) and\
                            (order.meal_name.meal_name == unit_package.meal_name) and\
                                (order.eating_day == unit_package.eating_day):
                            koshoku_list.append((UnitPackage(
                                unit_name=order.unit_name.calc_name,
                                unit_number=unit_package.unit_number,
                                plate_name=unit_package.plate_name,
                                cooking_day=unit_package.cooking_day,
                                index=unit_package.index,
                                eating_day=unit_package.eating_day,
                                meal_name=unit_package.meal_name,
                                package=unit_package.package,
                                count=1,
                                menu_name=unit_package.meal_name,
                                register_at=unit_package.register_at,
                                is_basic_plate=True,
                                cooking_direction=unit_package.cooking_direction,
                                mix_rice_type=unit_package.mix_rice_type,
                                soup_type=unit_package.soup_type,
                            ), order.unit_name.short_name))

        for koshoku_unitpackage, short_name in koshoku_list:
            all_df = all_df.append({
                'unit_name': koshoku_unitpackage.unit_name,
                'unit_number': koshoku_unitpackage.unit_number,
                'plate_name': koshoku_unitpackage.plate_name,
                'index': koshoku_unitpackage.index,
                'eating_day': koshoku_unitpackage.eating_day,
                'meal_name': koshoku_unitpackage.meal_name,
                'package': koshoku_unitpackage.package,
                'count': 1,
                'register_at': koshoku_unitpackage.register_at,
                'is_basic_plate': koshoku_unitpackage.is_basic_plate,
                'cooking_direction': koshoku_unitpackage.cooking_direction,
                'mix_rice_type': self.get_mix_rice_type_label(koshoku_unitpackage.mix_rice_type),
                'soup_type': self.get_soup_type_label(koshoku_unitpackage.soup_type),
                'short_name': short_name,
                'menu_name': '常食',
            }, ignore_index=True)

        all_df = all_df.astype({'package': str})
        all_df.to_csv("tmp/Design-b-0.csv", index=False)

        # 食事区分ソート順などの設定
        for index, data in all_df.iterrows():
            if data['meal_name'] == '朝食':
                all_df.loc[index, 'meal_name_seq'] = 0
            elif data['meal_name'] == '昼食':
                all_df.loc[index, 'meal_name_seq'] = 1
            elif data['meal_name'] == '夕食':
                all_df.loc[index, 'meal_name_seq'] = 2

            # 5人袋の端数かどうかを区別する
            if PlateNameAnalizeUtil.is_5p_package_plate(data['plate_name']):
                all_df.loc[index, 'is_5p'] = True
            else:
                all_df.loc[index, 'is_5p'] = False

            all_df.loc[index, 'eating_time'] = f'{data["eating_day"].strftime("%Y年%m月%d日")}　{self.get_output_meal(data["meal_name"])}'

            # 印刷枚数は、10人・5人の端数以外で出力する
            if data['package'] == 'BASIC_FRACTION':
                all_df.loc[index, 'print_count'] = 0
            else:
                all_df.loc[index, 'print_count'] = data['count']

            if '個' in data['short_name']:
                all_df.loc[index, 'unit_seq'] = data['unit_number'] + 0.5
            else:
                all_df.loc[index, 'unit_seq'] = data['unit_number']

            all_df.loc[index, 'plate_name'] = self.get_output_plate_name(data['plate_name'])
            # 個食の調整(集約されているものを分ける)
            for unitpackage, _ in koshoku_list:
                if (unitpackage.eating_day == data['eating_day']) and \
                        (unitpackage.meal_name == data['meal_name']) and \
                        (unitpackage.unit_number == data['unit_number']):
                    if not ('個食' in data['unit_name']):
                        logger.info(f'設計図シール出力(基本食)-個食調整({unitpackage.unit_number})：{unitpackage.count}')
                        all_df.loc[index, 'count'] = all_df.loc[index, 'count'] - unitpackage.count
                        if all_df.loc[index, 'print_count'] > 0:
                            all_df.loc[index, 'print_count'] = all_df.loc[index, 'print_count'] - unitpackage.count
                        break

        all_df = all_df.sort_values(['eating_day', 'meal_name_seq', 'index', 'unit_seq']).reset_index()
        all_df = all_df.astype({'print_count': 'int64'})

        # 混ぜご飯：サンシティ合算-施設番号修正
        # (先に置き換えてしまうと、型不一致でソートに影響をあたえるため、ここで置き換え)
        for index, data in all_df.iterrows():
            if data['short_name'] == '柊桜茜葵':
                all_df.loc[index, 'unit_number'] = '4、5、6、7'

            if '個' in data['short_name']:
                all_df.loc[index, 'unit_number'] = f'D　{all_df.loc[index, "unit_number"]}'

        all_df.to_csv("tmp/Design-b-1.csv", index=False)

        new_dir_path = os.path.join(settings.OUTPUT_DIR, 'design_seal_csv', '基本食')
        os.makedirs(new_dir_path, exist_ok=True)

        # 基本食端数の袋(10人用)のみ抽出
        fraction_base_df = all_df[(all_df.package == 'BASIC_FRACTION') & (all_df.soup_type == '対象外') & (
                    all_df.mix_rice_type == '対象外')]
        fraction_10p_df = fraction_base_df[fraction_base_df.is_5p == False]
        fraction_10p_df.to_csv("tmp/Design-b-2.csv", index=False)
        filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_10人用端数.csv"
        fraction_10p_df = fraction_10p_df.drop(columns=[
            'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day', 'cooking_day',
            'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name', 'is_5p',
            'unit_seq'
        ])
        fraction_10p_df = fraction_10p_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
        fraction_10p_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食端数の袋(5人用)のみ抽出
        fraction_5p_df = fraction_base_df[fraction_base_df.is_5p == True]
        if len(fraction_5p_df):
            # 5人袋は、あった場合のみ出力する
            filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_5人用端数.csv"
            fraction_5p_df = fraction_5p_df.drop(columns=[
                'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day',
                'cooking_day',
                'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name',
                'is_5p', 'unit_seq'
            ])
            fraction_5p_df = fraction_5p_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
            fraction_5p_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食施設毎の袋のみ抽出
        unit_df = all_df[
            (all_df.package == 'BASIC_UNIT') & (all_df.soup_type == '対象外') & (all_df.mix_rice_type == '対象外')]
        filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_施設毎.csv"
        unit_df = unit_df.drop(columns=[
            'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day', 'cooking_day',
            'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name', 'is_5p',
            'unit_seq'
        ])
        unit_df = unit_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
        unit_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食端数の袋(混ぜご飯)のみ抽出
        mixrice_df = all_df[(all_df.package == 'BASIC_UNIT') & (all_df.soup_type == '対象外') & (
                    all_df.mix_rice_type != '対象外')]
        if len(mixrice_df):
            filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_混ぜご飯.csv"
            mixrice_df = mixrice_df.drop(columns=[
                'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day',
                'cooking_day',
                'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name',
                'is_5p', 'unit_seq'
            ])
            mixrice_df = mixrice_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
            mixrice_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食端数の汁のみ抽出
        soup_base_df = all_df[(all_df.package == 'SOUP_FRACTION') | (all_df.package == 'SOUP_UNIT')]
        soup_df = soup_base_df[soup_base_df.soup_type == '汁(スープ)']
        soup_df.to_csv("tmp/Design-b-3.csv", index=False)
        filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_汁.csv"
        soup_df = soup_df.drop(columns=[
            'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day', 'cooking_day',
            'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name', 'is_5p',
            'unit_seq'
        ])
        soup_df = soup_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
        soup_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食端数の汁のみ抽出
        filling_df = soup_base_df[soup_base_df.soup_type == '汁具']
        filename = new_dir_path + f"/{self.cooking_day}_基本食シール用csv_汁具.csv"
        filling_df.to_csv("tmp/Design-b-4.csv", index=False)
        filling_df = filling_df.drop(columns=[
            'level_0', 'id', 'unit_name', 'meal_name_seq', 'package', 'menu_name', 'register_at', 'eating_day', 'cooking_day',
            'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name', 'is_5p',
            'unit_seq'
        ])
        filling_df = filling_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name']]
        filling_df.to_csv(filename, index=False, header=False, encoding='cp932')

    def write_for_enge(self, menu_name: str):
        # 対象喫食日の全施設の情報を読み込む
        qs = UnitPackage.objects.filter(
            cooking_day=self.cooking_day, is_basic_plate=True, menu_name=menu_name).order_by('register_at')
        all_df = read_frame(qs)

        unit_qs = UnitMaster.objects.all().exclude(unit_code__range=[80001, 80008]).values('unit_number', 'calc_name', 'short_name').distinct()
        unit_df = read_frame(unit_qs)
        all_df = pd.merge(
            all_df, unit_df,
            left_on=['unit_number', 'unit_name'],
            right_on=['unit_number', 'calc_name'],
            how='inner')

        # 食事区分ソート順の設定
        for index, data in all_df.iterrows():
            if data['meal_name'] == '朝食':
                all_df.loc[index, 'meal_name_seq'] = 0
            elif data['meal_name'] == '昼食':
                all_df.loc[index, 'meal_name_seq'] = 1
            elif data['meal_name'] == '夕食':
                all_df.loc[index, 'meal_name_seq'] = 2
            all_df.loc[index, 'eating_time'] = f'{data["eating_day"].strftime("%Y年%m月%d日")}　{self.get_output_meal(data["meal_name"])}'
            all_df.loc[index, 'package_name'] = self.get_output_package(data['package'])
            all_df.loc[index, 'plate_name'] = self.get_output_plate_name(data['plate_name'])
            if '(ルー)' in all_df.loc[index, 'plate_name']:
                all_df.loc[index, 'index'] = all_df.loc[index, 'index'] + 0.5

            # 印刷枚数
            all_df.loc[index, 'print_count'] = data['count']

        all_df = all_df.sort_values(['eating_day', 'meal_name_seq', 'index', 'unit_number']).reset_index()
        all_df = all_df.astype({'print_count': 'int64'})
        all_df.to_csv("tmp/Design-e-1.csv", index=False)

        new_dir_path = os.path.join(settings.OUTPUT_DIR, 'design_seal_csv', menu_name)
        os.makedirs(new_dir_path, exist_ok=True)

        # ファイルの出力
        enge_df = all_df[(all_df.package == 'ENGE_2') | (all_df.package == 'ENGE_7') | (all_df.package == 'ENGE_14') | (
                    all_df.package == 'ENGE_20')]
        filename = new_dir_path + f"/{self.cooking_day}_嚥下食シール用csv_{menu_name}.csv"
        enge_df = enge_df.drop(columns=[
            'level_0', 'id', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'cooking_day',
            'index', 'meal_name', 'is_basic_plate', 'cooking_direction', 'mix_rice_type', 'soup_type', 'calc_name', 'package'
        ])
        enge_df = enge_df[['short_name', 'unit_number', 'eating_time', 'print_count', 'count', 'plate_name', 'package_name']]
        enge_df.to_csv(filename, index=False, header=False, encoding='cp932')

    def write_for_allergen_basic(self, df):
        # アレルギー基本食の出力
        sorted_df = df.sort_values(['eating_day', 'meal_name_seq', 'source_index', 'ar_plate_index', 'unit_number']).reset_index(drop=True)
        sorted_df = sorted_df[sorted_df.enge_package_seq >= 10]

        new_dir_path = os.path.join(settings.OUTPUT_DIR, 'design_seal_csv', 'アレルギー', '基本食')
        os.makedirs(new_dir_path, exist_ok=True)

        # 施設番号に「アレルギー」の文字を付与
        for index, data in sorted_df.iterrows():
            sorted_df.loc[index, 'unit_number'] = f"{sorted_df.loc[index, 'unit_number']}アレルギー"
        df.to_csv("tmp/Design-ab-1.csv", index=False)

        # 基本食端数の袋(10人用)＋1人用のみ抽出
        fraction_base_df = sorted_df[sorted_df.package != 'BASIC_UNIT']
        fraction_10p_df = fraction_base_df[fraction_base_df.is_5p == False]
        filename = new_dir_path + f"/{self.cooking_day}_アレルギー基本食シール用csv_10人用端数.csv"
        fraction_10p_df = fraction_10p_df.drop(columns=[
            'level_0', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'package', 'package_name',
            'index', 'meal_name', 'calc_name', 'is_5p', 'code', 'cooking_direction__id', 'enge_package_seq', 'plate_id',
            'print_count', 'source_seq', 'source_index', 'ar_plate_index'
        ])
        fraction_10p_df = fraction_10p_df[
            ['short_name', 'unit_number', 'eating_time', 'source_plate_name', 'allergen', 'quantity', 'count', 'plate_name']]
        fraction_10p_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食端数の袋(5人用)のみ抽出
        fraction_5p_df = fraction_base_df[fraction_base_df.is_5p == True]
        if len(fraction_5p_df):
            # 5人袋は、あった場合のみ出力する(5人用料理の1人分も出力する)
            filename = new_dir_path + f"/{self.cooking_day}_アレルギー基本食シール用csv_5人用端数.csv"
            fraction_5p_df = fraction_5p_df.drop(columns=[
                'level_0', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'package',
                'package_name',
                'index', 'meal_name', 'calc_name', 'is_5p', 'code', 'cooking_direction__id', 'enge_package_seq',
                'plate_id', 'print_count', 'source_seq', 'source_index', 'ar_plate_index'
            ])
            fraction_5p_df = fraction_5p_df[
                ['short_name', 'unit_number', 'eating_time', 'source_plate_name', 'allergen', 'quantity', 'count', 'plate_name']]
            fraction_5p_df.to_csv(filename, index=False, header=False, encoding='cp932')

        # 基本食施設毎の袋のみ抽出
        unit_df = sorted_df[sorted_df.package == 'BASIC_UNIT']
        if len(unit_df):
            filename = new_dir_path + f"/{self.cooking_day}_アレルギー基本食シール用csv_施設毎.csv"
            unit_df = unit_df.drop(columns=[
                'level_0', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'package', 'package_name',
                'index', 'meal_name', 'calc_name', 'is_5p', 'code', 'cooking_direction__id', 'enge_package_seq',
                'plate_id', 'print_count', 'source_seq', 'source_index', 'ar_plate_index'
            ])
            unit_df = unit_df[['short_name', 'unit_number', 'eating_time', 'source_plate_name', 'allergen', 'quantity', 'count', 'plate_name']]
            unit_df.to_csv(filename, index=False, header=False, encoding='cp932')

    def write_for_allergen_enge(self, df):
        # アレルギー嚥下食の出力
        df.to_csv("tmp/Design-ae-1.csv", index=False)
        sorted_df = df.sort_values(['eating_day', 'meal_name_seq', 'source_index', 'ar_plate_index', 'unit_number', 'source_seq']).reset_index(drop=True)
        sorted_df = sorted_df[sorted_df.enge_package_seq <= 10]

        # 施設番号に「アレルギー」の文字を付与
        for index, data in sorted_df.iterrows():
            sorted_df.loc[index, 'unit_number'] = f"{sorted_df.loc[index, 'unit_number']}アレルギー"
        sorted_df.to_csv("tmp/Design-ae-2.csv", index=False)

        for menu in ['ソフト', 'ゼリー', 'ミキサー']:
            new_dir_path = os.path.join(settings.OUTPUT_DIR, 'design_seal_csv', 'アレルギー', menu)
            os.makedirs(new_dir_path, exist_ok=True)

            enge_df = sorted_df[sorted_df.menu_name == menu]
            if len(enge_df):
                # 1人用
                enge_1p_df = enge_df[enge_df.source_seq == 0]
                if len(enge_1p_df):
                    filename = new_dir_path + f"/{self.cooking_day}_アレルギー{menu}シール1人用csv.csv"
                    enge_1p_df = enge_1p_df.drop(columns=[
                        'level_0', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'package',
                        'index', 'meal_name', 'calc_name', 'is_5p', 'code', 'cooking_direction__id', 'enge_package_seq',
                        'plate_id', 'print_count', 'source_seq', 'source_index', 'ar_plate_index'
                    ])
                    enge_1p_df = enge_1p_df[
                        ['short_name', 'unit_number', 'eating_time', 'source_plate_name', 'allergen', 'quantity', 'count', 'plate_name',
                         'package_name']]
                    enge_1p_df.to_csv(filename, index=False, header=False, encoding='cp932')

                # 2,7,14,20人用
                enge_np_df = enge_df[enge_df.source_seq != 0]
                if len(enge_np_df):
                    filename = new_dir_path + f"/{self.cooking_day}_アレルギー{menu}シール複数人用csv.csv"
                    enge_np_df = enge_np_df.drop(columns=[
                        'level_0', 'unit_name', 'meal_name_seq', 'menu_name', 'register_at', 'eating_day', 'package',
                        'index', 'meal_name', 'calc_name', 'is_5p', 'code', 'cooking_direction__id', 'enge_package_seq',
                        'plate_id', 'print_count', 'source_seq', 'source_index', 'ar_plate_index'
                    ])
                    enge_np_df = enge_np_df[
                        ['short_name', 'unit_number', 'eating_time', 'source_plate_name', 'allergen', 'quantity', 'count', 'plate_name',
                         'package_name']]
                    enge_np_df.to_csv(filename, index=False, header=False, encoding='cp932')

    def get_kind_menu_name(self, code):
        """
        食種の献立種類を取得する
        """
        if '常' in code:
            return '常食'
        elif 'ソ' in code:
            return 'ソフト'
        elif 'ゼ' in code:
            return 'ゼリー'
        elif 'ミ' in code:
            return 'ミキサー'
        else:
            return ''

    def get_allergens_with_menu(self, code):

        # 献立種類名の取得
        menu_name = self.get_kind_menu_name(code)

        # 散発アレルギー履歴から検索(履歴未登録は運用流れ上ありえない)
        uc_hist_qs = UncommonAllergenHistory.objects.filter(code=code, cooking_day=self.cooking_day, menu_name=menu_name)
        if uc_hist_qs.exists():
            logger.debug(f'menu={menu_name}')
            allergen = uc_hist_qs.first().allergen
            logger.debug(f'allergen={repr(allergen)}-{allergen.allergen_name}')

            return [allergen], menu_name
        else:
            # 頻発アレルギーの検索
            common_qs = CommonAllergen.objects.filter(code=code, menu_name__menu_name=menu_name)
            if common_qs.exists():
                return [x.allergen for x in common_qs], menu_name
            else:
                return [], None

    def get_output_plate_name(self, plate_name: str):
        replaced = re.sub('(\d).*$', '', plate_name)
        replaced = replaced.replace('①', '')
        replaced = replaced.replace('②', '')
        replaced = replaced.replace('③', '')
        replaced = replaced.replace('④', '')
        replaced = replaced.replace('⑤', '')

        # 計量表出力様記号の無効化
        replaced = replaced.replace('■', '')
        replaced = replaced.replace('▼', '')
        replaced = replaced.replace('△', '')
        replaced = replaced.replace('◎', '')

        replaced = replaced.strip()
        if (replaced[-1] == '(') or (replaced[-1] == '（'):
            replaced = replaced[:-1]

        if '◆' in plate_name:
            res = re.findall('具(\d+|\d+\.\d+)[g|ｇ]\s*\D液(\d+|\d+\.\d+)[g|ｇ]', plate_name)
            if res and (res[0][0] and res[0][1]):
                if 'ルー' in plate_name:
                    replaced = f'{replaced}(ルー)'
        elif ('カレーライス' in plate_name) or ('シチュー' in plate_name):
            if 'ルー' in plate_name:
                replaced = f'{replaced}(ルー)'

        return replaced

    def get_output_allergen_kana_name(self, kana_name: str, menu: str):
        if menu == 'ソフト':
            return f'ソ　{kana_name}'
        elif menu == 'ゼリー':
            return f'ゼ　{kana_name}'
        elif menu == 'ミキサー':
            return f'ミ　{kana_name}'
        else:
            return kana_name

    def get_menu_index_diff(self):
        # 製造日の喫食日初日のPlatePackageForPrint最大index取得
        print_qs = PlatePackageForPrint.objects.filter(
            cooking_day=self.cooking_day, is_basic_plate=True, menu_name='常食').order_by('eating_day', 'id')
        print_day_first = print_qs.first()
        print_count = PlatePackageForPrint.objects.filter(
            cooking_day=self.cooking_day, is_basic_plate=True, menu_name='常食',
            eating_day=print_day_first.eating_day, meal_name=print_day_first.meal_name).count()

        # 喫食日初日のPlateMenuForPrint最大index取得
        menu_count = PlateMenuForPrint.objects.filter(
            eating_day=print_day_first.eating_day, type_name='通常', menu_name='基本食', meal_name=print_day_first.meal_name).count()

        return menu_count - print_count

    def _is_need_adjust_index(self, plate_name):
        if '◆' in plate_name:
            res = re.findall('具(\d+|\d+\.\d+)g\s*＋液(\d+|\d+\.\d+)g', plate_name)
            if res and (res[0][0] and res[0][1]):
                return True
        elif ('カレーライス' in plate_name) or ('シチュー' in plate_name):
            if 'ルー' in plate_name:
                return True
        return False

    def get_menu_index_list(self, diff: int, is_enge: bool = False):
        print_qs = CookingDirectionPlate.objects.filter(cooking_day=self.cooking_day, is_basic_plate=True).order_by('id')

        result_list = []
        prev_eating_day = None
        prev_meal = None
        index = diff
        for print in print_qs:
            if print.meal_name != prev_meal:
                if prev_eating_day:
                    # indexは再カウント。初回はそのまま
                    index = 0
                prev_eating_day = print.eating_day
                prev_meal = print.meal_name

            result_dict = {
                'eating_day': print.eating_day, 'meal_name': print.meal_name, 'direction_index': print.index,
                'menu_index': index
            }
            result_list.append(result_dict)

            if is_enge and self._is_need_adjust_index(print.plate_name):
                index += 2
            else:
                index += 1

        return result_list

    def get_menu_plate_name(self, menu_name: str, cooking_direction_plate: CookingDirectionPlate, basic_index_list, enge_index_list):
        if menu_name == '常食':
            search_menu = '基本食'
            index_list = basic_index_list
        else:
            search_menu = menu_name
            index_list = enge_index_list

        # メニュー上のインデックスを取得
        menu_index = None
        for index_dict in index_list:
            if (index_dict['eating_day'] == cooking_direction_plate.eating_day) and \
               (index_dict['meal_name'] == cooking_direction_plate.meal_name) and \
               (index_dict['direction_index'] == cooking_direction_plate.index):
                    menu_index = index_dict['menu_index']
                    break

        if menu_index is not None:
            menu = PlateMenuForPrint.objects.filter(
                eating_day=cooking_direction_plate.eating_day, meal_name=cooking_direction_plate.meal_name,
                type_name='通常', menu_name=search_menu, index=menu_index
            ).first()
            if menu:
                return menu.name

        # 対象の献立料理名(P7に出しているもの)が見つからなかった場合
        logger.warning(f'アレルギー元料理名不明-{cooking_direction_plate}')
        return cooking_direction_plate.plate_name

    def write_for_allergen(self):
        diff = self.get_menu_index_diff()
        basic_index_list = self.get_menu_index_list(diff)
        enge_index_list = self.get_menu_index_list(diff, True)

        # 対象喫食日の全施設の情報を読み込む
        qs = UnitPackage.objects.filter(cooking_day=self.cooking_day, is_basic_plate=False).values(
            'unit_name', 'unit_number', 'plate_name', 'index', 'eating_day', 'package', 'meal_name', 'package', 'count',
            'menu_name', 'register_at', 'cooking_direction__id'
        ).distinct()
        all_df = read_frame(qs)
        all_df.to_csv("tmp/Design-a-0.csv", index=False)

        # UnitPackage登録時は、アレルギー一覧画面での編集前の状態で登録しているため、正確ではない。
        # 本メソッドで情報を参照して袋数を構築するので、ここでは料理情報をユニークにする。
        read_dict = {}
        delete_index_list = []
        for index, data in all_df.iterrows():
            if (data['unit_number'], data['meal_name'], data['package'], data['eating_day'], data['menu_name'], data['plate_name']) in read_dict:
                prev_index = read_dict[(data['unit_number'], data['meal_name'], data['package'], data['eating_day'], data['menu_name'], data['plate_name'])]

                units = UnitMaster.objects.filter(unit_number=data['unit_number'])
                if [x for x in units if '個食' in x.unit_name]:
                    all_df.loc[prev_index, 'count'] = all_df.loc[prev_index, 'count'] + data['count']
                delete_index_list.append(index)
            else:
                read_dict[(data['unit_number'], data['meal_name'], data['package'], data['eating_day'], data['menu_name'], data['plate_name'])] = index
        all_df = all_df.drop(all_df.index[delete_index_list]).reset_index()
        all_df = all_df.drop(columns=['level_0'])

        df_data_list = []
        for index, data in all_df.iterrows():
            if data['meal_name'] == '朝食':
                all_df.loc[index, 'meal_name_seq'] = 0
            elif data['meal_name'] == '昼食':
                all_df.loc[index, 'meal_name_seq'] = 1
            elif data['meal_name'] == '夕食':
                all_df.loc[index, 'meal_name_seq'] = 2

            if data['package'] == 'ENGE_7':
                all_df.loc[index, 'enge_package_seq'] = 0
            elif data['package'] == 'ENGE_14':
                all_df.loc[index, 'enge_package_seq'] = 1
            elif data['package'] == 'ENGE_20':
                all_df.loc[index, 'enge_package_seq'] = 2
            elif data['package'] == 'ENGE_2':
                all_df.loc[index, 'enge_package_seq'] = 3
            elif data['package'] == 'ENGE_1':
                all_df.loc[index, 'enge_package_seq'] = 4
            else:
                all_df.loc[index, 'enge_package_seq'] = 10

            # 5人袋の端数かどうかを区別する
            if PlateNameAnalizeUtil.is_5p_package_plate(data['plate_name']):
                all_df.loc[index, 'is_5p'] = True
            else:
                all_df.loc[index, 'is_5p'] = False

            all_df.loc[index, 'eating_time'] = f'{data["eating_day"].strftime("%Y年%m月%d日")}　{self.get_output_meal(data["meal_name"])}'
            all_df.loc[index, 'package_name'] = self.get_output_package(data['package'])

            # 印刷枚数は、10人・5人の端数以外で出力する
            if data['package'] == 'BASIC_FRACTION':
                all_df.loc[index, 'print_count'] = 0
            else:
                all_df.loc[index, 'print_count'] = data['count']

            ar_plate_id = data['cooking_direction__id']
            all_df.loc[index, 'plate_id'] = ar_plate_id

            # 代替元料理の取得
            relation_qs = AllergenPlateRelations.objects.filter(plate_id=ar_plate_id).select_related('source')
            logger.info(f'{data["unit_number"]}-{data["menu_name"]}-{data["plate_name"]}-{list(relation_qs)}')
            for relation in relation_qs:
                allergens, menu = self.get_allergens_with_menu(relation.code)
                if allergens and menu:
                    if not [x for x in df_data_list if
                            (x[0] == ar_plate_id) and (x[2] == relation.code) and (x[3] == data['unit_name']) and
                            (x[4] == data['unit_number']) and (x[5] == menu)]:

                        source_unitpackage = UnitPackage.objects.filter(
                            cooking_day=self.cooking_day, eating_day=data['eating_day'], meal_name=data['meal_name'],
                            is_basic_plate=True, cooking_direction=relation.source,
                            package_id__in=[
                                settings.PICKING_PACKAGES['ENGE_7'], settings.PICKING_PACKAGES['ENGE_14'],
                                settings.PICKING_PACKAGES['ENGE_20']
                            ]).first()

                        source_cooking = CookingDirectionPlate.objects.get(id=ar_plate_id)

                        for allergen in allergens:
                            oqs = Order.objects.filter(eating_day=data['eating_day'], meal_name__meal_name=data['meal_name'],
                                                       allergen=allergen, unit_name__unit_number=data['unit_number'],
                                                       unit_name__calc_name=data['unit_name'],
                                                       menu_name__menu_name=menu
                                                       ).values(
                                                            'unit_name__unit_number', 'unit_name__unit_name', 'quantity'
                                                       )

                            if oqs.exists():
                                for base_order in oqs:
                                    total_quantity = base_order['quantity']
                                    if not total_quantity:
                                        continue
                                    if menu == '常食':
                                        source_package_seq = 10
                                    else:
                                        if total_quantity == 1:
                                            source_package_seq = 0
                                        elif total_quantity == 2:
                                            source_package_seq = 1
                                        else:
                                            if source_unitpackage:
                                                if source_unitpackage.package_id == settings.PICKING_PACKAGES['ENGE_7']:
                                                    source_package_seq = 2
                                                elif source_unitpackage.package_id == settings.PICKING_PACKAGES['ENGE_14']:
                                                    source_package_seq = 3
                                                elif source_unitpackage.package_id == settings.PICKING_PACKAGES['ENGE_20']:
                                                    source_package_seq = 4
                                                else:
                                                    source_package_seq = 9
                                            else:
                                                source_package_seq = 9

                                    # 献立料理名の取得
                                    menu_plate_name = self.get_menu_plate_name(menu, relation.source, basic_index_list, enge_index_list)

                                    data_list = [
                                        ar_plate_id, f'{menu_plate_name}代替', relation.code,
                                        data['unit_name'], data['unit_number'], menu, total_quantity,
                                        self.get_output_allergen_kana_name(allergen.kana_name, menu),
                                        source_package_seq, relation.source.index, source_cooking.index
                                    ]
                                    df_data_list.append(data_list)
                else:
                    logger.warning(f'アレルギー食種{relation.code}：履歴にない')

        column_list = [
            'plate_id', 'source_plate_name', 'code', 'unit_name', 'unit_number', 'menu_name', 'quantity', 'allergen', 'source_seq', 'source_index', 'ar_plate_index'
        ]
        relation_df = pd.DataFrame(data=df_data_list, columns=column_list)

        all_df = all_df.astype({'plate_id': 'int64'})
        relation_df = relation_df.astype({'plate_id': 'int64'})

        all_df.to_csv("tmp/Design-a-1.csv", index=False)
        relation_df.to_csv("tmp/Design-a-2.csv", index=False)

        merge_df = pd.merge(
            all_df, relation_df, left_on=['menu_name', 'plate_id', 'unit_name', 'unit_number'],
            right_on=['menu_name', 'plate_id', 'unit_name', 'unit_number'],how='inner').reset_index()
        merge_df.to_csv("tmp/Design-a-3.csv", index=False)

        unit_qs = UnitMaster.objects.all().exclude(unit_code__range=[80001, 80008]).values('unit_number', 'calc_name', 'short_name').distinct()
        unit_df = read_frame(unit_qs)
        merge_df = pd.merge(
            merge_df, unit_df,
            left_on=['unit_number', 'unit_name'],
            right_on=['unit_number', 'calc_name'],
            how='inner')
        merge_df.to_csv("tmp/Design-a-4.csv", index=False)

        # 本来含まれないサイズの結合を削除(単純内部結合のため、組み合わせの妥当性は判断できていない)
        delete_index_list = []
        for index, data in merge_df.iterrows():
            if data['package'] == 'BASIC_10':
                if data['quantity'] < 10:
                    delete_index_list.append(index)
                else:
                    merge_df.loc[index, 'count'] = int(data['quantity'] / 10)
                    merge_df.loc[index, 'quantity'] = 10
            elif data['package'] == 'BASIC_1':
                if data['quantity'] % 10 != 1:
                    delete_index_list.append(index)
                else:
                    merge_df.loc[index, 'count'] = 1
                    merge_df.loc[index, 'quantity'] = data['quantity'] % 10
            elif data['package'] == 'BASIC_FRACTION':
                if data['quantity'] % 10 == 1:
                    delete_index_list.append(index)
                else:
                    merge_df.loc[index, 'count'] = 1
                    merge_df.loc[index, 'quantity'] = data['quantity'] % 10
        merge_df = merge_df.drop(columns=['level_0'])
        merge_df = merge_df.drop(merge_df.index[delete_index_list]).reset_index()
        merge_df.to_csv("tmp/Design-a-5.csv", index=False)

        # 基本食の出力
        self.write_for_allergen_basic(merge_df)

        # 嚥下食の出力
        self.write_for_allergen_enge(merge_df)


    def wite(self):
        logger.info(f'設計図シール出力({self.output_type})　開始')

        if self.output_type == '01':
            # 基本食用の情報を読み込む
            self.write_for_basic()
        elif self.output_type == '02':
            # 基本食用の情報を読み込む
            self.write_for_enge('ソフト')
        elif self.output_type == '03':
            # 基本食用の情報を読み込む
            self.write_for_enge('ゼリー')
        elif self.output_type == '04':
            # 基本食用の情報を読み込む
            self.write_for_enge('ミキサー')
        elif self.output_type == '05':
            # 基本食用の情報を読み込む
            self.write_for_allergen()
