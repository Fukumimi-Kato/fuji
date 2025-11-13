import datetime as dt
from dateutil.relativedelta import relativedelta
import logging
import numpy as np
import openpyxl as excel
import os
import pandas as pd
import unicodedata

from django.conf import settings
from django_pandas.io import read_frame

from web_order.models import PlateMenuForPrint, PlatePackageForPrint, OutputSampleP7


logger = logging.getLogger(__name__)


class P7Plate:
    def __init__(self, index, date, meal, name, additive, allergen, cal, protein, fat, carbohydrates, salt):
        self.index = index
        self.raw_date = date
        self.meal = meal
        self.name = name
        self.additive = additive
        self.allergen = allergen
        self.cal = cal
        self.protein = protein
        self.fat = fat
        self.carbohydrates = carbohydrates
        self.salt = salt

        self.date = dt.date(int(self.raw_date[:4]), int(self.raw_date[4:6]), int(self.raw_date[6:8]))

    def get_plate_name(self):
        replaced = self.name.replace('▲', '')
        replaced = replaced.replace('●', '')
        return replaced


class P7SourceFileReader:
    NAME_MAX_LENGTH = 36
    ADDITIVE_MAX_LENGTH = 132
    ALLERGEN_MAX_LENGTH = 104

    def __init__(self, filename):
        self.filename = filename

    def is_valid_length(self, target: str, value: str):
        if target == 'name':
            max = self.NAME_MAX_LENGTH
        elif target == 'additive':
            max = self.ADDITIVE_MAX_LENGTH
        elif target == 'allergen':
            max = self.ALLERGEN_MAX_LENGTH
        else:
            return True

        half_max = max * 2
        total_half_count = 0
        for v in value:
            res = unicodedata.east_asian_width(v)
            if res in 'FWA':
                total_half_count += 2
            else:
                total_half_count += 1

        return total_half_count <= half_max, total_half_count - half_max

    def validate_length(self, plate):
        res, length = self.is_valid_length('name', plate.name)
        if not res:
            return False, 'name', length

        res, length = self.is_valid_length('additive', plate.additive)
        if not res:
            return False, 'additive', length

        res, length = self.is_valid_length('allergen', plate.allergen)
        if not res:
            return False, 'allergen', length

        return True, '', -1

    def read(self, sub_dir, menu_name, menu_type, cooking_day=None):
        if settings.STUB_MODE_P7_READ:
            # 読み込んだ体にして終了
            return

        # 実ファイル読込
        source_file = os.path.join(settings.MEDIA_ROOT, self.filename.name)
        wb = excel.load_workbook(source_file)

        if cooking_day:
            # 製造日ありのデータは上書き時に料理がなくなる喫食日・食事区分を考慮し、まとめて既存を削除
            PlateMenuForPrint.objects.filter(
                menu_name=menu_name,
                type_name=menu_type,
                cooking_day=cooking_day
            ).delete()

        ws = wb.worksheets[0]
        index = 0
        invalid_plate_list = []
        prev_key = None
        line_cnt = 0
        for row in ws.iter_rows(min_row=2):
            line_cnt += 1

            date = row[1].value
            meal = row[4].value
            name = row[6].value

            additive = row[8].value
            allergen = row[9].value
            cal = row[11].value
            protein = row[12].value
            fat = row[13].value
            carbohydrates = row[14].value
            salt = row[26].value

            if name =="ごはん":
                continue

            if prev_key != (date, meal):
                prev_key = (date, meal)
                index = 0

                plate = P7Plate(
                    index=index,
                    date=date,
                    meal=meal,
                    name=name,
                    additive=additive or '',
                    allergen=allergen or '',
                    cal=float(cal),
                    protein=float(protein),
                    fat=float(fat),
                    carbohydrates=float(carbohydrates),
                    salt=float(salt)
                )

                # 1日単位の再登録のため、既存データを削除する
                # 製造日がないデータは常にDelete-Insert対象
                PlateMenuForPrint.objects.filter(
                    eating_day=plate.date,
                    meal_name=plate.meal,
                    menu_name=menu_name,
                    type_name=menu_type,
                    cooking_day=None
                ).delete()
            else:
                plate = P7Plate(
                    index=index,
                    date=date,
                    meal=meal,
                    name=name,
                    additive=additive or '',
                    allergen=allergen or '',
                    cal=float(cal),
                    protein=float(protein),
                    fat=float(fat),
                    carbohydrates=float(carbohydrates),
                    salt=float(salt)
                )

            # 文字数チェック
            validate_result, reason, over = self.validate_length(plate)
            if validate_result:
                # テーブル登録
                menu, is_create = PlateMenuForPrint.objects.get_or_create(
                    eating_day=plate.date,
                    meal_name=plate.meal,
                    menu_name=menu_name,
                    type_name=menu_type,
                    cooking_day=cooking_day,
                    index=plate.index
                )

                menu.name = plate.get_plate_name()
                menu.additive = plate.additive
                menu.allergen = plate.allergen
                menu.cal = plate.cal
                menu.protein = plate.protein
                menu.fat = plate.fat
                menu.carbohydrates = plate.carbohydrates
                menu.salt = plate.salt

                menu.save()

                index += 1
            else:
                if reason == 'name':
                    invalid_name = '献立名'
                elif reason == 'additive':
                    invalid_name = '添加物'
                elif reason == 'allergen':
                    invalid_name = 'アレルギー'
                else:
                    invalid_name = '不明'
                invalid_plate_list.append((plate.name, invalid_name, line_cnt, over))

        # 終了処理
        wb.close()

        return invalid_plate_list

class P7CsvFileWriter:
    def __init__(self):
        pass

    def get_plate_number(self, menu, cooking_day, index, type_name):
        """
        CSVに出力する,料理番号を取得する。
        フォーマット：6桁、1桁目:種別、2桁目:アレルギー/サンプル、3・4桁目：日付、5・6桁目:連番
        """
        # 日付を0埋め
        day_str = str(cooking_day.day).zfill(2)

        # 0オリジンを1オリジンに変更
        number_index = index + 1

        # インデックスを0埋め
        index_str = str(number_index).zfill(2)

        if (menu == '基本食') or (menu == '常食'):
            kind = '1'
        elif menu == 'ソフト':
            kind = '5'
        elif menu == 'ゼリー':
            kind = '6'
        elif menu == 'ミキサー':
            kind = '7'
        else:
            # 通常ありえない
            kind = 'F'

        if type_name == '通常':
            opt = '0'
        elif type_name == 'アレルギー':
            opt = '8'
        elif type_name == 'サンプル':
            opt = '9'
        else:
            # 通常ありえない
            opt = 'F'

        number = f'{kind}{opt}{day_str}{index_str}'
        return number

    def adjust_index(self, menu_df, package_df, output_df, eating_day, meal_name, type_name, menu_name_list):
        menu_len = len(menu_df)
        package_len = len(package_df)

        diff = menu_len - package_len
        if diff > 0:
            # インデックスの修正
            prev_delete_index_list = []
            for index, data in output_df.iterrows():
                if (data['eating_day'] == eating_day) and (
                        meal_name == data['meal_name']) and (
                        type_name == data['type_name']) and (data['menu_name'] in menu_name_list):
                    if data['index'] < diff:
                        logger.info(f'[{data["menu_name"]}]削除対象行({index}：{data["name"]}-{data["index"]}')
                        prev_delete_index_list.append(index)
                    else:
                        output_df.loc[index, 'index'] = data['index'] - diff

            return prev_delete_index_list
        else:
            return []

    def is_miso_soup_liquid(cls, plate_name):
        """
        対象の料理の名称が味噌汁の汁かどうかを判断する。
        """
        if '具' in plate_name:
            return False

        if '味噌汁' in plate_name:
            return True
        elif 'みそ汁' in plate_name:
            return True
        elif 'みそしる' in plate_name:
            return True
        else:
            return False

    def write_csv(self, cooking_day):
        """
        P7対応のCSVファイルを出力する
        """
        logger.info('●P7-CSVファイル出力開始')
        logger.info(f'出力対象製造日={cooking_day}')

        # 袋情報の取得
        package_qs = PlatePackageForPrint.objects.filter(cooking_day=cooking_day).order_by('id')
        package_first = package_qs.filter(is_basic_plate=True).first()
        package_df = read_frame(package_qs)
        basic_package_df = package_df[package_df.is_basic_plate == True]
        basic_package_df.to_csv("tmp/Plate-0.csv", index=False)

        # 献立情報取得のため、対象製造日に紐づく喫食委、食事区分を判断
        distinct_qs = PlatePackageForPrint.objects.filter(
            cooking_day=cooking_day, is_basic_plate=True).distinct().values_list('eating_day', 'meal_name')
        distinct_list = list(distinct_qs)
        logger.info(f'distinct_list={distinct_list}')
        eating_day_list = []
        for x in distinct_qs:
            eating_day = x[0]
            if not (eating_day in eating_day_list):
                eating_day_list.append(eating_day)

        # 喫食日の単位で献立情報取得(不要な食事区分も含んでいる)
        logger.info(f'出力対象喫食日={eating_day_list}')
        qs = PlateMenuForPrint.objects.filter(
            eating_day__in=eating_day_list, type_name__in=['通常', 'アレルギー']).order_by('eating_day', 'meal_name', 'index')
        plate_menu_df = read_frame(qs)
        plate_menu_df.to_csv("tmp/Plate-1.csv", index=False)

        # id列を削除
        plate_menu_no_id_df = plate_menu_df.drop(columns=plate_menu_df.columns[[0,]])

        # 範囲外の食事区分を除く
        delete_index_list = []
        for index, data in plate_menu_no_id_df.iterrows():
            tmp = (data['eating_day'], data['meal_name'])
            if data['menu_name'] == '基本食':
                plate_menu_no_id_df.loc[index, 'menu_name'] = '常食'
            if not (tmp in distinct_list):
                delete_index_list.append(index)
            if data['cooking_day']:
                if data['cooking_day'] != cooking_day:
                    delete_index_list.append(index)

        plate_menu_no_id_df = plate_menu_no_id_df.drop(plate_menu_no_id_df.index[delete_index_list]).reset_index()
        plate_menu_no_id_df.to_csv("tmp/Plate-1_1.csv", index=False)

        menu_first = plate_menu_no_id_df.iloc[0]
        is_same_eating_time = \
            (package_first.eating_day == menu_first['eating_day']) and \
            (package_first.meal_name == menu_first['meal_name'])

        if is_same_eating_time:
            # 基本食
            menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == '通常') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == '常食')]
            menu_first_df.to_csv("tmp/Plate-1_1_menu.csv", index=False)

            package_first_df = basic_package_df[
                (basic_package_df.eating_day == package_first.eating_day) &
                (basic_package_df.meal_name == package_first.meal_name) & (basic_package_df.menu_name == '常食')]
            package_first_df.to_csv("tmp/Plate-1_1_pack.csv", index=False)

            prev_delete_index_list = self.adjust_index(
                menu_first_df, package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, '通常', ['常食'])

            # 嚥下食
            menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == '通常') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == 'ソフト')]
            menu_first_df.to_csv("tmp/Plate-1_1E_menu.csv", index=False)

            package_first_df = basic_package_df[
                (basic_package_df.eating_day == package_first.eating_day) &
                (basic_package_df.meal_name == package_first.meal_name) & (basic_package_df.menu_name == 'ソフト')]
            package_first_df.to_csv("tmp/Plate-1_1E_pack.csv", index=False)

            prev_delete_index_list += self.adjust_index(
                menu_first_df, package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, '通常', ['ソフト', 'ゼリー', 'ミキサー'])

            # 基本食(アレルギー)
            allergen_package_df = package_df[package_df.is_basic_plate == False]
            ar_normal_menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == 'アレルギー') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == '常食')]

            ar_normal_package_first_df = allergen_package_df[
                (allergen_package_df.eating_day == package_first.eating_day) &
                (allergen_package_df.meal_name == package_first.meal_name) & (allergen_package_df.menu_name == '常食')]

            prev_delete_index_list += self.adjust_index(
                ar_normal_menu_first_df, ar_normal_package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, 'アレルギー', '常食')

            # 基本食(ソフト)
            ar_soft_menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == 'アレルギー') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == 'ソフト')]

            ar_soft_package_first_df = allergen_package_df[
                (allergen_package_df.eating_day == package_first.eating_day) &
                (allergen_package_df.meal_name == package_first.meal_name) & (allergen_package_df.menu_name == 'ソフト')]

            prev_delete_index_list += self.adjust_index(
                ar_soft_menu_first_df, ar_soft_package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, 'アレルギー', 'ソフト')

            # 基本食(ゼリー)
            ar_jelly_menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == 'アレルギー') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == 'ゼリー')]

            ar_jelly_package_first_df = allergen_package_df[
                (allergen_package_df.eating_day == package_first.eating_day) &
                (allergen_package_df.meal_name == package_first.meal_name) & (allergen_package_df.menu_name == 'ゼリー')]

            prev_delete_index_list += self.adjust_index(
                ar_jelly_menu_first_df, ar_jelly_package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, 'アレルギー', 'ゼリー')

            # 基本食(ミキサー)
            ar_mixer_menu_first_df = plate_menu_no_id_df[
                (plate_menu_no_id_df.eating_day == package_first.eating_day) & (plate_menu_no_id_df.type_name == 'アレルギー') &
                (plate_menu_no_id_df.meal_name == package_first.meal_name) & (plate_menu_no_id_df.menu_name == 'ミキサー')]

            ar_mixer_package_first_df = allergen_package_df[
                (allergen_package_df.eating_day == package_first.eating_day) &
                (allergen_package_df.meal_name == package_first.meal_name) & (allergen_package_df.menu_name == 'ミキサー')]

            prev_delete_index_list += self.adjust_index(
                ar_mixer_menu_first_df, ar_mixer_package_first_df, plate_menu_no_id_df,
                package_first.eating_day, package_first.meal_name, 'アレルギー', 'ミキサー')

            if prev_delete_index_list:
                plate_menu_no_id_df = plate_menu_no_id_df.drop(plate_menu_no_id_df.index[prev_delete_index_list])

                plate_menu_no_id_df.to_csv("tmp/Plate-1_2.csv", index=False)
        else:
            logger.info(f'package_first.eating_day:{package_first.eating_day}')
            logger.info(f'menu_first_eating_day:{menu_first["eating_day"]}')
            logger.info(f'package_first.meal_name:{package_first.meal_name}')
            logger.info(f'menu_first_meal_name:{menu_first["meal_name"]}')

        # 献立と袋数情報の結合
        basic_package_df.to_csv("tmp/Plate-1_3_p.csv", index=False)
        merged_df = pd.merge(plate_menu_no_id_df, basic_package_df, on=['eating_day', 'index', 'meal_name', 'menu_name'], how='left')
        merged_df.fillna(0)
        merged_df.to_csv("tmp/Plate-1_3.csv", index=False)

        # 製造日再設定
        for index, data in merged_df.iterrows():
            merged_df.loc[index, 'cooking_day'] = data['cooking_day_y']
        merged_df = merged_df.drop(columns=['cooking_day_x', 'cooking_day_y'])

        d_indexes = []
        for index, data in merged_df.iterrows():
            if data['type_name'] != 'アレルギー':
                if pd.isnull(data['cooking_day']):
                    d_indexes.append(index)
        if d_indexes:
            merged_df = merged_df.drop(merged_df.index[d_indexes])
        merged_df.to_csv("tmp/Plate-1_3_a.csv", index=False)

        # アレルギーの袋数の修正
        prev_c_day = None
        for index, data in merged_df.iterrows():
            if data['type_name'] != 'アレルギー':
                continue

            c_day = data['cooking_day']
            if (pd.isnull(data['cooking_day'])) and prev_c_day:
                logger.info(f'製造日が空')
                c_day = prev_c_day
            try:
                logger.info(f"{c_day}-{data['eating_day']}-{data['index']}")
                ar_plate_ps = PlatePackageForPrint.objects.filter(
                    cooking_day=c_day,
                    eating_day=data['eating_day'],
                    meal_name=data['meal_name'],
                    menu_name=data['menu_name'],
                    is_basic_plate=False,
                    index=data['index']
                )
            except Exception as e:
                logger.error(data['cooking_day'])
                raise e
            prev_c_day = c_day
            if ar_plate_ps.exists():
                ar_plate = ar_plate_ps.first()
                merged_df.loc[index, 'id'] = ar_plate.id
                merged_df.loc[index, 'count'] = ar_plate.count
                merged_df.loc[index, 'count_one_p'] = ar_plate.count_one_p
                merged_df.loc[index, 'count_one_50g'] = ar_plate.count_one_50g
            else:
                merged_df.loc[index, 'id'] = 0
                merged_df.loc[index, 'count'] = 0
                merged_df.loc[index, 'count_one_p'] = 0
                merged_df.loc[index, 'count_one_50g'] = 0

        merged_df.to_csv("tmp/Plate-2.csv", index=False)

        # ソート用の項目を追加
        for index, data in merged_df.iterrows():
            if data['menu_name'] == '常食':
                if data['type_name'] == 'アレルギー':
                    merged_df.loc[index, 'sort_1'] = '81'
                elif data['type_name'] == 'サンプル':
                    merged_df.loc[index, 'sort_1'] = '91'
                else:
                    merged_df.loc[index, 'sort_1'] = '01'
            elif data['menu_name'] == 'ソフト':
                if data['type_name'] == 'アレルギー':
                    merged_df.loc[index, 'sort_1'] = '85'
                elif data['type_name'] == 'サンプル':
                    merged_df.loc[index, 'sort_1'] = '95'
                else:
                    merged_df.loc[index, 'sort_1'] = '05'
            elif data['menu_name'] == 'ゼリー':
                if data['type_name'] == 'アレルギー':
                    merged_df.loc[index, 'sort_1'] = '86'
                elif data['type_name'] == 'サンプル':
                    merged_df.loc[index, 'sort_1'] = '96'
                else:
                    merged_df.loc[index, 'sort_1'] = '06'
            elif data['menu_name'] == 'ミキサー':
                if data['type_name'] == 'アレルギー':
                    merged_df.loc[index, 'sort_1'] = '87'
                elif data['type_name'] == 'サンプル':
                    merged_df.loc[index, 'sort_1'] = '97'
                else:
                    merged_df.loc[index, 'sort_1'] = '07'
            else:
                merged_df.loc[index, 'sort_1'] = '99'

            if data['meal_name'] == '朝食':
                merged_df.loc[index, 'sort_2'] = '1'
            elif data['meal_name'] == '昼食':
                merged_df.loc[index, 'sort_2'] = '2'
            elif data['meal_name'] == '夕食':
                merged_df.loc[index, 'sort_2'] = '3'
            else:
                merged_df.loc[index, 'sort_2'] = '9'

        merged_df.to_csv("tmp/Plate-2-0.csv", index=False)

        # level_0列を削除
        merged_df = merged_df.drop(columns=merged_df.columns[[0,]])

        merged_df2 = merged_df.sort_values(['sort_1', 'eating_day', 'sort_2', 'index']).reset_index()
        merged_df2.to_csv("tmp/Plate-2-1.csv", index=False)

        # 固定列の追加、番号の付与
        target = None
        plate_index = 0
        miso_ingredient_dict = {}
        miso_id = 19000
        miso_id_list = []
        for index, data in merged_df2.iterrows():
            current_target = data['sort_1']
            if target != current_target:
                target = current_target
                plate_index = 0

            if self.is_miso_soup_liquid(data['name']):
                # 成分違い毎に別の味噌汁として登録
                ingredient = (data['cal'], data['protein'], data['fat'], data['carbohydrates'], data['salt'])
                if ingredient in miso_ingredient_dict:
                    merged_df2.loc[index, 'number'] = miso_ingredient_dict[ingredient]
                    merged_df2.loc[index, 'count_one_50g'] = 0
                else:
                    str_id = str(miso_id)
                    merged_df2.loc[index, 'number'] = str_id
                    miso_ingredient_dict[ingredient] = str_id
                    miso_id_list.append(str_id)
                    miso_id += 1
            else:
                merged_df2.loc[index, 'number'] = self.get_plate_number(data['menu_name'], cooking_day, plate_index, data['type_name'])
                plate_index += 1

            # 固定内容の追加
            merged_df2.loc[index, 'notice'] = '4℃以下で保存して下さい。 '
            merged_df2.loc[index, 'measure'] = '(１食当たり)'

        # 不要列の削除
        merged_df_converted = merged_df2.drop(columns=merged_df2.columns[[0, 2, 3, 4, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24]])
        merged_df_converted.to_csv("tmp/Plate-3.csv", index=False)

        for index, data in merged_df_converted.iterrows():
            merged_df_converted.loc[index, 'blank1'] = ''
            merged_df_converted.loc[index, 'total'] = data['count'] + data['count_one_p'] + data['count_one_50g']

        # 列の並べ替え
        reindex_df = merged_df_converted.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        reindex_df.to_csv("tmp/Plate-4.csv", index=False)

        # 味噌汁の抽出・集計(袋数(count)で集計)
        miso_soup_df = reindex_df[reindex_df.number.isin(miso_id_list)]
        miso_soup_sum_df = miso_soup_df.groupby([
            'name', 'notice', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1']).sum().reset_index()

        # 味噌汁用の番号を追加
        for index, data in miso_soup_sum_df.iterrows():
            str_index = str(index).zfill(3)
            miso_soup_sum_df.loc[index, 'number'] = f'19{str_index}'

        # 列の並べ替え
        reindex_miso_soup_df = miso_soup_sum_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        reindex_miso_soup_df.to_csv("tmp/Plate-5.csv", index=False)

        append_df = reindex_miso_soup_df.append(['', '', '', '', ''])
        append_df = append_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df.to_csv("tmp/Plate-6.csv", index=False)

        # 基本食(常食)の内容を出力
        without_miso_df = reindex_df[reindex_df.name != '味噌汁']
        basic_df = without_miso_df.query('number.str.startswith("10")', engine='python')
        append_df = append_df.append(basic_df)
        append_df.to_csv("tmp/Plate-7.csv", index=False)

        # ソフトの内容を出力
        append_df = append_df.append([''])
        for_soft_df = without_miso_df.query('number.str.startswith("50")', engine='python')
        for_soft_df = for_soft_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(for_soft_df)
        append_df.to_csv("tmp/Plate-8.csv", index=False)

        # ゼリー
        append_df = append_df.append([''])
        for_jelly_df = without_miso_df.query('number.str.startswith("60")', engine='python')
        for_jelly_df = for_jelly_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(for_jelly_df)
        append_df.to_csv("tmp/Plate-9.csv", index=False)

        # ミキサー
        append_df = append_df.append([''])
        for_mixer_df = without_miso_df.query('number.str.startswith("70")', engine='python')
        for_mixer_df = for_mixer_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(for_mixer_df)
        append_df.to_csv("tmp/Plate-A.csv", index=False)

        # アレルギー
        append_df = append_df.append([''])
        ar_basic_df = without_miso_df.query('number.str.startswith("18")', engine='python')
        ar_basic_df = ar_basic_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(ar_basic_df)

        append_df = append_df.append([''])
        ar_soft_df = without_miso_df.query('number.str.startswith("58")', engine='python')
        ar_soft_df = ar_soft_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(ar_soft_df)

        append_df = append_df.append([''])
        ar_jelly_df = without_miso_df.query('number.str.startswith("68")', engine='python')
        ar_jelly_df = ar_jelly_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(ar_jelly_df)

        append_df = append_df.append([''])
        ar_mixer_df = without_miso_df.query('number.str.startswith("78")', engine='python')
        ar_mixer_df = ar_mixer_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
        append_df = append_df.append(ar_mixer_df)

        # サンプル
        sample_qs = PlateMenuForPrint.objects.filter(
            eating_day__in=eating_day_list, type_name='サンプル').order_by('id')
        if sample_qs.exists():
            sample_df = read_frame(sample_qs)
            sample_df.to_csv("tmp/Plate-S.csv", index=False)
            append_df.to_csv("tmp/Plate-B2.csv", index=False, encoding='cp932')

            delete_index_list = []
            output_sample_list = []
            ignore_sample_list = []
            for index, data in sample_df.iterrows():
                tmp = (data['eating_day'], data['meal_name'])
                if data['menu_name'] == '基本食':
                    sample_df.loc[index, 'menu_name'] = '常食'

                # 有効な喫食日・食事区分のみ対象とする
                if tmp in distinct_list:
                    # 出力済みに記録する
                    if not (tmp in output_sample_list):
                        output_sample_list.append(tmp)
                else:
                    if tmp in output_sample_list:
                        # 今回出力対象なら、削除しない(DB検索を2回異常実行させないための措置)
                        pass
                    else:
                        # 対象製造日にサンプルのみを作る喫食日・食事区分の場合を対応するため、別製造日で出力済みかを検索
                        if tmp in ignore_sample_list:
                            # 前のループで出力対象外が確定している喫食日・食事区分
                            delete_index_list.append(index)
                        else:
                            # 出力記録を見て判断
                            qs = OutputSampleP7.objects.filter(
                                eating_day=tmp[0], meal_name=tmp[1], cooking_day=cooking_day)
                            if qs.exists():
                                # 出力対象に含める
                                output_sample_list.append(tmp)
                            else:
                                # 出力対象になっていない場合のみ削除する
                                delete_index_list.append(index)
                                ignore_sample_list.append(tmp)
            for tmp in output_sample_list:
                OutputSampleP7.objects.get_or_create(
                                eating_day=tmp[0], meal_name=tmp[1], cooking_day=cooking_day)
            logger.info(f'delete:{delete_index_list}')
            sample_df = sample_df.drop(sample_df.index[delete_index_list])

            for index, data in sample_df.iterrows():
                if data['menu_name'] == '常食':
                    if data['type_name'] == 'アレルギー':
                        sample_df.loc[index, 'sort_1'] = '81'
                    elif data['type_name'] == 'サンプル':
                        sample_df.loc[index, 'sort_1'] = '91'
                    else:
                        sample_df.loc[index, 'sort_1'] = '01'
                elif data['menu_name'] == 'ソフト':
                    if data['type_name'] == 'アレルギー':
                        sample_df.loc[index, 'sort_1'] = '85'
                    elif data['type_name'] == 'サンプル':
                        sample_df.loc[index, 'sort_1'] = '95'
                    else:
                        sample_df.loc[index, 'sort_1'] = '05'
                elif data['menu_name'] == 'ゼリー':
                    if data['type_name'] == 'アレルギー':
                        sample_df.loc[index, 'sort_1'] = '86'
                    elif data['type_name'] == 'サンプル':
                        sample_df.loc[index, 'sort_1'] = '96'
                    else:
                        sample_df.loc[index, 'sort_1'] = '06'
                elif data['menu_name'] == 'ミキサー':
                    if data['type_name'] == 'アレルギー':
                        sample_df.loc[index, 'sort_1'] = '87'
                    elif data['type_name'] == 'サンプル':
                        sample_df.loc[index, 'sort_1'] = '97'
                    else:
                        sample_df.loc[index, 'sort_1'] = '07'
                else:
                    sample_df.loc[index, 'sort_1'] = '99'

                if data['meal_name'] == '朝食':
                    sample_df.loc[index, 'sort_2'] = '1'
                elif data['meal_name'] == '昼食':
                    sample_df.loc[index, 'sort_2'] = '2'
                elif data['meal_name'] == '夕食':
                    sample_df.loc[index, 'sort_2'] = '3'
                else:
                    sample_df.loc[index, 'sort_2'] = '9'

            sample_df.to_csv("tmp/Plate-S2.csv", index=False, encoding='cp932')

            if len(sample_df):
                sample_df = sample_df.sort_values(['sort_1', 'eating_day', 'sort_2', 'index']).reset_index()

                target = None
                for index, data in sample_df.iterrows():
                    current_target = data['sort_1']
                    if target != current_target:
                        target = current_target
                        plate_index = 0

                    sample_df.loc[index, 'number'] = self.get_plate_number(data['menu_name'], cooking_day, plate_index,
                                                                            data['type_name'])

                    sample_df.loc[index, 'notice'] = '4℃以下で保存して下さい。 '
                    sample_df.loc[index, 'measure'] = '(１食当たり)'
                    sample_df.loc[index, 'count'] = ''

                    plate_index += 1
                sample_df = sample_df.drop(columns=sample_df.columns[[0, 1, 3, 4, 5, 13, 14, 15, 16, 17]])
                for index, data in sample_df.iterrows():
                    sample_df.loc[index, 'blank1'] = ''
                    sample_df.loc[index, 'blank2'] = ''
                    sample_df.loc[index, 'total'] = ''

                # 列の並べ替え
                sample_df = sample_df.reindex(
                    columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                             'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])

                sample_df.to_csv("tmp/Plate-S3.csv", index=False)

                append_df = append_df.append([''])
                sample_basic_df = sample_df.query('number.str.startswith("19")', engine='python')
                sample_basic_df = sample_basic_df.reindex(
                    columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                             'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
                append_df = append_df.append(sample_basic_df)

                append_df = append_df.append([''])
                sample_soft_df = sample_df.query('number.str.startswith("59")', engine='python')
                sample_soft_df = sample_soft_df.reindex(
                    columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                             'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
                append_df = append_df.append(sample_soft_df)

                append_df = append_df.append([''])
                sample_jelly_df = sample_df.query('number.str.startswith("69")', engine='python')
                sample_jelly_df = sample_jelly_df.reindex(
                    columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                             'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
                append_df = append_df.append(sample_jelly_df)

                append_df = append_df.append([''])
                sample_mixer_df = sample_df.query('number.str.startswith("79")', engine='python')
                sample_mixer_df = sample_mixer_df.reindex(
                    columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                             'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])
                append_df = append_df.append(sample_mixer_df)

        append_df = append_df.reindex(
            columns=['number', 'name', 'notice', 'count', 'measure', 'additive', 'allergen', 'cal',
                     'protein', 'fat', 'carbohydrates', 'salt', 'blank1', 'count_one_p', 'count_one_50g', 'total'])

        output_dir = os.path.join(settings.OUTPUT_DIR, 'p7')
        os.makedirs(output_dir, exist_ok=True)  # 上書きOK
        filepath = os.path.join(output_dir, f'商品_栄養成分有_{cooking_day.strftime("%Y%m%d")}.csv')
        append_df.to_csv(filepath, index=False, header=False, encoding='cp932')

        logger.info('●P7-CSVファイル出力完了')


class P7Util:
    @classmethod
    def save_package_count_for_print(
            cls, cooking_day, aggregation_day, index, count: int, count_1p: int, menu: str, meal,
            count_50g=0, is_raw_save=False):
        if index == -1:
            return

        # アレルギー食はP7対応不要のため、ここでは出力しない
        plate_package_qs = PlatePackageForPrint.objects.filter(
            cooking_day=cooking_day, eating_day=aggregation_day,
            is_basic_plate=True, meal_name=meal, menu_name=menu, index=index)
        if plate_package_qs.exists():
            plate_package = plate_package_qs.first()
            if is_raw_save or (not ('原体' in plate_package.plate_name)):
                # 原体は特別な指定がない限り袋数を出力しない。
                plate_package.count = count
                plate_package.count_one_p = count_1p
                plate_package.count_one_50g = count_50g
                plate_package.save()

    @classmethod
    def get_number_prefix(cls, menu: str, is_allergen: bool, is_sample: bool, cooking_day):
        """
        P7番号のインデックスより前の部分を取得する。
        """
        # 日付を0埋め
        day_str = str(cooking_day.day).zfill(2)

        if (menu == '基本食') or (menu == '常食'):
            kind = '1'
        elif menu == 'ソフト':
            kind = '5'
        elif menu == 'ゼリー':
            kind = '6'
        elif menu == 'ミキサー':
            kind = '7'
        else:
            # 通常ありえない
            kind = 'F'

        if is_allergen:
            opt = '8'
        elif is_sample:
            opt = '9'
        else:
            # 通常ありえない
            opt = '0'

        number = f'{kind}{opt}{day_str}'
        return number

    @classmethod
    def get_number_index(cls, index: int):
        """
        P7番号のインデックス部分を取得する。
        ※何桁の文字列を取得すべきかの判断が分散しないように共通化。
        indexは0オリジンを想定
        """

        # 0オリジンを1オリジンに変更
        number_index = index + 1

        # インデックスを0埋め
        index_str = str(number_index).zfill(2)

        return index_str

    @classmethod
    def get_number_miso_soup(cls):
        """
        味噌汁のP7番号を取得する
        """
        return '19000'
