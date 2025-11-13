import os
import pandas as pd
import datetime as dt
import platform
import shutil

from django_pandas.io import read_frame
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Sum

from web_order.models import Order, OrderEveryday

# ログファイルの「↓」はpd.concatで「→」はpd.mergeでの結合を示す

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('date', nargs='+', type=str)

    def handle(self, *args, **options):

        #######################################################
        # らくらく献立に食数を入力するため、食種別に集計する処理（これまでの方式）
        #######################################################

        # 集計日時を喫食日で指定する
        # in_date = '2022-04-01'
        in_date = options['date'][0]  # 呼び出し時の引数1つ目

        aggregation_day = dt.datetime.strptime(in_date, '%Y-%m-%d')
        aggregation_day = aggregation_day.date()  # 時刻部分を除外

        rakukon_output_dir = os.path.join(settings.OUTPUT_DIR, settings.RAKUKON_DIR)

        new_dir_path = os.path.join(rakukon_output_dir, str(aggregation_day) + '_食数集計表')
        os.makedirs(new_dir_path, exist_ok=True)

        quantity_aggregation_file = os.path.join(new_dir_path, str(aggregation_day) + '_食数集計表.csv')

        aggregation_res = pd.DataFrame(index=[],
                                       columns=[str(aggregation_day) + ' 喫食分', ''])

        if platform.system() == 'Windows':
            aggregation_res.loc[len(aggregation_res)] = [str(dt.datetime.now().strftime('%m/%d %H:%M')) + ' 集計開始', '食数']
        else:
            aggregation_res.loc[len(aggregation_res)] = [str(dt.datetime.now().strftime('%-m/%d %-H:%M')) + ' 集計開始', '食数']

        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']

        # ------------------------------------------------------------------------------
        # 当日の全データ
        # ------------------------------------------------------------------------------
        qs_all = Order.objects\
            .filter(eating_day=aggregation_day, quantity__gt=0)\
            .values('unit_name__unit_number', 'unit_name',
                    'meal_name__meal_name',
                    'menu_name',
                    'allergen', 'quantity', 'eating_day')\
            .exclude(unit_name__unit_code__range=[80001, 80008])\
            .order_by('unit_name__unit_number', 'meal_name__seq_order',
                      'menu_name__seq_order', 'allergen__seq_order')

        df = read_frame(qs_all)
        with open(new_dir_path + "/" + str(aggregation_day) + "_注文データ_アレ込.csv", mode="w",
                  encoding="cp932", errors="backslashreplace") as f:
            df.to_csv(f, index=False)

        shokusu = qs_all.aggregate(Sum('quantity'))['quantity__sum']
        aggregation_res.loc[len(aggregation_res)] = ['注文データ_アレ込', shokusu]


        # ------------------------------------------------------------------------------
        # 食数固定製造データ
        # ------------------------------------------------------------------------------

        qs_everyday = OrderEveryday.objects.all()\
            .values('unit_name__unit_number', 'unit_name',
                    'meal_name__meal_name',
                    'menu_name',
                    'allergen', 'quantity', 'eating_day') \
            .order_by('unit_name__unit_number', 'meal_name__seq_order',
                      'menu_name__seq_order', 'allergen__seq_order')

        df_everyday = read_frame(qs_everyday)
        df_everyday = df_everyday.fillna(aggregation_day)  # 検食分は喫食日が入っていないので設定する

        df_everyday.to_csv(new_dir_path + "/_食数固定製造分.csv", index=False)


        # ------------------------------------------------------------------------------
        # 当日の全データからアレルギーを抽出
        # ------------------------------------------------------------------------------
        qs_allergen = qs_all.filter(allergen_id__gte=2)

        df = read_frame(qs_allergen)
        with open(new_dir_path + "/" + str(aggregation_day) + "_注文データ_アレのみ.csv", mode="w",
                  encoding="cp932", errors="backslashreplace") as f:
            df.to_csv(f, index=False)

        shokusu = qs_allergen.aggregate(Sum('quantity'))['quantity__sum']
        aggregation_res.loc[len(aggregation_res)] = ['注文データ_アレのみ', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        def aggregation(mnu, sup, fll, mel, lst, fnm):

            # 注文テーブルから抽出分
            qs_order = qs_all.filter(menu_name__menu_name=mnu,
                                     meal_name__soup=sup,
                                     meal_name__filling=fll,
                                     meal_name__meal_name=mel,
                                     allergen_id=1,
                                     unit_name__unit_number__in=lst)

            # 食数固定製造テーブルから抽出分
            qs_fix = qs_everyday.filter(menu_name__menu_name=mnu,
                                        meal_name__soup=sup,
                                        meal_name__filling=fll,
                                        meal_name__meal_name=mel,
                                        unit_name__unit_number__in=lst)

            df_order = read_frame(qs_order)
            df_fix = read_frame(qs_fix)
            df_concat = pd.concat([df_order, df_fix])
            df_concat.to_csv(new_dir_path + fnm, index=False)

            if qs_order.exists():
                shokusu_o = qs_order.aggregate(Sum('quantity'))['quantity__sum']
            else:
                shokusu_o = 0

            if qs_fix.exists():
                shokusu_f = qs_fix.aggregate(Sum('quantity'))['quantity__sum']
            else:
                shokusu_f = 0

            shokusu_all = shokusu_o + shokusu_f

            return shokusu_all


        # ------------------------------------------------------------------------------
        # 常食_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/J-1-1_常_汁なし_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/J-1-2_常_汁なし_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁なし_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/J-1-3_常_汁なし_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 23, 26, 27, 28, 32, 901, 902, 903, 904]
        f_name = "/J-2-1_常_汁3回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 23, 26, 27, 28, 32, 901, 902, 903, 904]
        f_name = "/J-2-2_常_汁3回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 23, 26, 27, 28, 32, 901, 902, 903, 904]
        f_name = "/J-2-3_常_汁3回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食_汁朝昼_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/J-3-1_常_汁朝昼_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁朝昼_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁朝昼_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/J-3-2_常_汁朝昼_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁朝昼_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁朝昼_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/J-3-3_常_汁朝昼_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁朝昼_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [66, 67, 68, 69]
        f_name = "/J-4-1_常_汁昼夕_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [66, 67, 68, 69]
        f_name = "/J-4-2_常_汁昼夕_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [66, 67, 68, 69]
        f_name = "/J-4-3_常_汁昼夕_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食_具朝昼_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [42, 44, 45, 46]
        f_name = "/J-5-1_常_具朝昼_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_具朝昼_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_具朝昼_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [42, 44, 45, 46]
        f_name = "/J-5-2_常_具朝昼_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_具朝昼_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食_具朝昼_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [42, 44, 45, 46]
        f_name = "/J-5-3_常_具朝昼_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食_具朝昼_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        # ------------------------------------------------------------------------------
        # 薄味_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [3, 4, 5, 6, 7, 13, 16, 35, 38, 39, 53]
        f_name = "/U-1-1_薄_汁なし_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [3, 4, 5, 6, 7, 13, 16, 35, 38, 39, 53]
        f_name = "/U-1-2_薄_汁なし_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁なし_昼食', shokusu]



        # ------------------------------------------------------------------------------
        # 薄味_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [3, 4, 5, 6, 7, 13, 16, 35, 38, 39, 53]
        f_name = "/U-1-3_薄_汁なし_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 薄味_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 22, 24, 25, 28, 29, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/U-2-1_薄_汁3回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 22, 24, 25, 28, 29, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/U-2-2_薄_汁3回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 22, 24, 25, 28, 29, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/U-2-3_薄_汁3回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 薄味_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/U-3-1_薄_汁昼夕_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/U-3-2_薄_汁昼夕_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/U-3-3_薄_汁昼夕_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 薄味_具３回_朝食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [64]
        f_name = "/U-4-1_薄_具３回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具３回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_具３回_昼食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [64]
        f_name = "/U-4-2_薄_具３回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具３回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_具３回_夕食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = True
        meal = '夕食'
        unit_list = [64]
        f_name = "/U-4-3_薄_具３回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具３回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 薄味_具朝昼_朝食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [42]
        f_name = "/U-5-1_薄_具朝昼_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具朝昼_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_具朝昼_昼食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [42]
        f_name = "/U-5-2_薄_具朝昼_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具朝昼_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 薄味_具朝昼_夕食
        # ------------------------------------------------------------------------------
        menu = '薄味'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [42]
        f_name = "/U-5-3_薄_具朝昼_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['薄味_具朝昼_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        # ------------------------------------------------------------------------------
        # ソフト_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [53]
        f_name = "/S-1-1_ソ_汁なし_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [53]
        f_name = "/S-1-2_ソ_汁なし_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁なし_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [53]
        f_name = "/S-1-3_ソ_汁なし_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ソフト_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/S-2-1_ソ_汁3回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/S-2-2_ソ_汁3回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/S-2-3_ソ_汁3回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ソフト_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [65]
        f_name = "/S-3-1_ソ_汁昼夕_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [65]
        f_name = "/S-3-2_ソ_汁昼夕_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [65]
        f_name = "/S-3-3_ソ_汁昼夕_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ソフト_具３回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [64]
        f_name = "/S-4-1_ソ_具３回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_具３回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_具３回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [64]
        f_name = "/S-4-2_ソ_具３回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_具３回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ソフト_具３回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ソフト'
        soup = False
        filling = True
        meal = '夕食'
        unit_list = [64]
        f_name = "/S-4-3_ソ_具３回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ソフト_具３回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        # ------------------------------------------------------------------------------
        # ミキサー_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [53]
        f_name = "/M-1-1_ミ_汁なし_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [53]
        f_name = "/M-1-2_ミ_汁なし_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁なし_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [53]
        f_name = "/M-1-3_ミ_汁なし_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ミキサー_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/M-2-1_ミ_汁3回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/M-2-2_ミ_汁3回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/M-2-3_ミ_汁3回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ミキサー_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [65]
        f_name = "/M-3-1_ミ_汁昼夕_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [65]
        f_name = "/M-3-2_ミ_汁昼夕_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [65]
        f_name = "/M-3-3_ミ_汁昼夕_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ミキサー_具３回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [64]
        f_name = "/M-4-1_ミ_具３回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_具３回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_具３回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [64]
        f_name = "/M-4-2_ミ_具３回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_具３回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ミキサー_具３回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ミキサー'
        soup = False
        filling = True
        meal = '夕食'
        unit_list = [64]
        f_name = "/M-4-3_ミ_具３回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ミキサー_具３回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        # ------------------------------------------------------------------------------
        # ゼリー_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [53]
        f_name = "/Z-1-1_ゼ_汁なし_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [53]
        f_name = "/Z-1-2_ゼ_汁なし_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁なし_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [53]
        f_name = "/Z-1-3_ゼ_汁なし_夕食.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ゼリー_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/Z-2-1_ゼ_汁3回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/Z-2-2_ゼ_汁3回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 22, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/Z-2-3_ゼ_汁3回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ゼリー_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [65]
        f_name = "/Z-3-1_ゼ_汁昼夕_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [65]
        f_name = "/Z-3-2_ゼ_汁昼夕_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [65]
        f_name = "/Z-3-3_ゼ_汁昼夕_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # ゼリー_具３回_朝食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [64]
        f_name = "/Z-4-1_ゼ_具３回_朝.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_具３回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_具３回_昼食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [64]
        f_name = "/Z-4-2_ゼ_具３回_昼.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_具３回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # ゼリー_具３回_夕食
        # ------------------------------------------------------------------------------
        menu = 'ゼリー'
        soup = False
        filling = True
        meal = '夕食'
        unit_list = [64]
        f_name = "/Z-4-3_ゼ_具３回_夕.csv"

        shokusu = aggregation(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['ゼリー_具３回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        def agg_by_group(mnu, sup, fll, mel, lst, fnm):

            # 注文テーブルから抽出分
            qs_order = qs_all.filter(menu_name__group=mnu,
                                     meal_name__soup=sup,
                                     meal_name__filling=fll,
                                     meal_name__meal_name=mel,
                                     allergen_id=1,
                                     unit_name__unit_number__in=lst)

            # 食数固定製造テーブルから抽出分
            qs_fix = qs_everyday.filter(menu_name__group=mnu,
                                        meal_name__soup=sup,
                                        meal_name__filling=fll,
                                        meal_name__meal_name=mel,
                                        unit_name__unit_number__in=lst)

            df_order = read_frame(qs_order)
            df_fix = read_frame(qs_fix)
            df_concat = pd.concat([df_order, df_fix])
            df_concat.to_csv(new_dir_path + fnm, index=False)

            if qs_order.exists():
                shokusu_o = qs_order.aggregate(Sum('quantity'))['quantity__sum']
            else:
                shokusu_o = 0

            if qs_fix.exists():
                shokusu_f = qs_fix.aggregate(Sum('quantity'))['quantity__sum']
            else:
                shokusu_f = 0

            shokusu_all = shokusu_o + shokusu_f

            return shokusu_all


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁なし_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/A-1-1_常食嚥下_汁なし_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁なし_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁なし_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '昼食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/A-1-2_常食嚥下_汁なし_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁なし_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁なし_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [2, 8, 9, 10, 11, 12, 13, 14, 17, 31, 33, 34, 36, 37,
                     40, 41, 43, 48, 49, 53]
        f_name = "/A-1-3_常食嚥下_汁なし_夕.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁なし_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁3回_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [21, 22, 23, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/A-2-1_常食嚥下_汁3回_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁3回_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [21, 22, 23, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/A-2-2_常食嚥下_汁3回_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁3回_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [21, 22, 23, 24, 25, 26, 27, 28, 32, 50, 51, 52, 901, 902, 903, 904]
        f_name = "/A-2-3_常食嚥下_汁3回_夕食.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁朝昼_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '朝食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/A-3-1_常食嚥下_汁朝昼_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁朝昼_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁朝昼_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/A-3-2_常食嚥下_汁朝昼_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁朝昼_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁朝昼_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [55, 56, 57, 58, 59, 60, 61, 62, 63]
        f_name = "/A-3-3_常食嚥下_汁朝昼_夕.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁朝昼_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁昼夕_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '朝食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/A-4-1_常食嚥下_汁昼夕_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁昼夕_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁昼夕_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '昼食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/A-4-2_常食嚥下_汁昼夕_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁昼夕_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_汁昼夕_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = True
        filling = True
        meal = '夕食'
        unit_list = [65, 66, 67, 68, 69]
        f_name = "/A-4-3_常食嚥下_汁昼夕_夕.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_汁昼夕_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食嚥下_具3回_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [64]
        f_name = "/A-5-1_常食嚥下_具3回_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具3回_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_具3回_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [64]
        f_name = "/A-5-2_常食嚥下_具3回_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具3回_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_具3回_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '夕食'
        unit_list = [64]
        f_name = "/A-5-3_常食嚥下_具3回_夕.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具3回_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '']


        # ------------------------------------------------------------------------------
        # 常食嚥下_具朝昼_朝食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '朝食'
        unit_list = [42, 44, 45, 46]
        f_name = "/A-6-1_常食嚥下_具朝昼_朝.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具朝昼_朝食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_具朝昼_昼食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = True
        meal = '昼食'
        unit_list = [42, 44, 45, 46]
        f_name = "/A-6-2_常食嚥下_具朝昼_昼.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具朝昼_昼食', shokusu]


        # ------------------------------------------------------------------------------
        # 常食嚥下_具朝昼_夕食
        # ------------------------------------------------------------------------------
        menu = '常食'
        soup = False
        filling = False
        meal = '夕食'
        unit_list = [42, 44, 45, 46]
        f_name = "/A-6-3_常食嚥下_具朝昼_夕.csv"

        shokusu = agg_by_group(menu, soup, filling, meal, unit_list, f_name)

        aggregation_res.loc[len(aggregation_res)] = ['常食嚥下_具朝昼_夕食', shokusu]
        aggregation_res.loc[len(aggregation_res)] = ['---------------------', '----------------']


        # ログを出力
        aggregation_res.to_csv(quantity_aggregation_file, index=False)
        shutil.make_archive(new_dir_path, 'zip', root_dir=new_dir_path)
