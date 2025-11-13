import datetime as dt
import os
import re

import pandas as pd

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from web_order.models import MonthlyMenu, FoodPhoto, EngeFoodDirection, MenuMaster, GenericSetoutDirection, SetoutDuration
from web_order.setout import OutputSetoutHelper

"""
    月間献立表から料理名を抜き出し、月間献立DBにレコードを追加する処理

# 引数
    filename: 月間献立表　M月.csv

# 献立DB
    Model: MonthlyMenu
    Model: FoodPhoto
"""


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='+', type=str)

    def handle(self, *args, **options):

        # 呼び出し時の引数1つ目「月間献立表　M月.csv」
        in_file = options['filename'][0]
        monthly_menu_file = os.path.join(settings.MEDIA_ROOT, 'upload', in_file)

        # アップロードされた月間献立表CSVの整形---------------------------------------------------------------------------------
        menus = pd.read_csv(monthly_menu_file, header=None, encoding='cp932', names=['tmp_A', '料理名', 'tmp_B'])

        # ごはんは指示書に使わないので除外
        menus['料理名'] = menus['料理名'].str.replace('　ごはん', '', regex=True)
        # 料理名に●があるものは1つ前の料理名の添えものとみなし、1つの料理名として接続する
        menus['料理名'] = menus['料理名'].str.replace('\s●', '・', regex=True)

        menus['料理名'] = menus['料理名'].str.replace('みそ汁', '味噌汁', regex=True)
        menus['料理名'] = menus['料理名'].str.replace(' ', '', regex=True)

        # 栄養摂取値の列（C列）削除
        menus = menus.drop(columns=menus.columns[2])

        # 該当セルの記載『月間献立表　常食(汁と具3回)冷　2022/05/01～2022/05/31』
        sheet_title = menus.iloc[0, 0]

        # YYYY/MM/DD を抽出 YYYY-MM-DD とする
        sheet_title = re.sub('(\d{4})\/(\d{2})\/(\d{2})', '\\1-\\2-\\3', sheet_title)
        # YYYY-MM- を抽出、データ成形時に利用する
        cooking_month = re.search('\d{4}-\d{2}-', sheet_title).group()
        # 月初と月末の日時として利用する
        res = re.findall('\d{4}-\d{2}-\d{2}', sheet_title)
        first_day = res[0]  # 月初
        last_day = res[1]   # 月末

        # A列の食事区分を削除し、新規に列名を「eating_day」として喫食日のみの列を追加
        menus['eating_day'] = menus['tmp_A']
        # 0埋めして D を DD に（YYYY-MM-は後で追加）
        menus['eating_day'] = menus['eating_day'].str.replace('^(\d{1})$', '0\\1', regex=True)

        menus['meal'] = meal_now = ''  # 初期化
        for index, row in menus.iterrows():
            # 「eating_day」にYYYY-MM-の追加
            row['eating_day'] = cooking_month + row['eating_day']

            # ソート用の数字を冒頭に追加し、基本食の文字列を除外したものをmeal列に記入
            if row['tmp_A'] == '朝食　基本食':
                meal_now = '1朝食'
            elif row['tmp_A'] == '昼食　基本食':
                meal_now = '2昼食'
            elif row['tmp_A'] == '夕食　基本食':
                meal_now = '3夕食'

            row['meal'] = meal_now


        for index, row in menus.iterrows():

            # 不要な行を除外
            if re.search('月間献立表', row['tmp_A']):
                menus.drop(index=[index], axis=0, inplace=True)
            elif re.search('基本食', row['tmp_A']):
                menus.drop(index=[index], axis=0, inplace=True)
            elif re.search('日付', row['tmp_A']):
                menus.drop(index=[index], axis=0, inplace=True)

        # 1列目を除外
        menus = menus.drop(columns=menus.columns[0])

        # 喫食日で朝昼夕がまとまっていないのでソートし直す
        sorted_menus = menus.sort_values(['eating_day', 'meal']).reset_index(drop=True)
        # sorted_menus.to_csv("tmp/C-1.csv", index=False)
        # 整形ここまで ----------------------------------------------------------------------------------------------------


        # 献立内容をDBに登録 -----------------------------------------------------------------------------------------------
        def get_generic_direction(shortening: str):
            generic_text = GenericSetoutDirection.objects.filter(shortening=shortening, for_enge=False)
            if generic_text.exists():
                return generic_text.first().direction
            else:
                return None

        # 実行するたびにレコードが増えるので該当月のレコードをいったん削除する
        # 盛付指示書発行済みのレコードは削除しないように対応
        qs = MonthlyMenu.objects.filter(eating_day__range=(first_day, last_day))
        not_delete_list = []
        delete_ids = []

        for monthly_menu in qs:
            file_name = OutputSetoutHelper.get_filename_without_extention(monthly_menu.eating_day)
            if SetoutDuration.objects.filter(name=file_name).exists():
                not_delete_list.append(monthly_menu)
            else:
                delete_ids.append(monthly_menu.id)
        MonthlyMenu.objects.filter(id__in=delete_ids).delete()

        # 定型文の取得
        # ここでは登録しないようにするため、コメントアウト
        """
        generic_text = get_generic_direction('温め定型')
        hot_text = generic_text if generic_text else '再加熱カートの場合は温めモード、スチーム88℃、\nもしくは湯煎で15分加熱後、開封して盛付け'

        generic_text = get_generic_direction('冷蔵定型')
        cold_text = generic_text if generic_text else '再加熱カートの場合は冷蔵モード、加熱せず、開封して盛付け'
        """

        for index, row in sorted_menus.iterrows():

            e_day = row['eating_day']
            meal = row['meal'][1:]  # ソートしたときに使った先頭の数字は除外
            menu_list = re.split('\s', row['料理名'])

            for menu in menu_list:
                # 同一料理の判定のため、冷蔵・温めの判断は先に行う
                if (re.findall('▲', menu)):
                    choice = '冷蔵'
                    menu = menu[1:]
                else:
                    choice = '温め'

                is_skip = False
                e_day_date = dt.datetime.strptime(e_day, '%Y-%m-%d').date()
                for nd in not_delete_list:
                    if (e_day_date == nd.eating_day) and (meal == nd.meal_name) and (menu == nd.food_name):
                        is_skip = True
                        break
                if is_skip:
                    continue

                if '★' in menu:
                    flag = False
                    menu = menu.replace('★', '')
                elif (re.findall('味噌汁', menu)
                        or re.findall('かき卵汁', menu)
                        or re.findall('汁具', menu)
                        or re.findall('スープ', menu)
                        or re.findall('お吸い物', menu)
                        or re.findall('吸い物具', menu)
                        or re.findall('すまし', menu)):
                    flag = True
                else:
                    flag = False

                # 月間献立テーブルに追加
                monthly_menu = MonthlyMenu.objects.create(
                    eating_day=e_day,
                    meal_name=meal,
                    food_name=menu,
                    option=flag
                )

                FoodPhoto.objects.create(
                    food_name=menu,
                    menu=monthly_menu,
                    hot_cool=choice
                )
                EngeFoodDirection.objects.create(menu=monthly_menu)


