import io
import os
import logging
import datetime as dt
import calendar
from decimal import Decimal
import math
import pandas as pd
import platform
import traceback
import re
import zipfile

from dateutil.relativedelta import relativedelta

from datetime import timedelta
from itertools import groupby
from natsort import natsorted
from functools import reduce, cmp_to_key
from operator import and_
import platform
import shutil
from urllib.parse import urlencode

from accounts.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Max, OuterRef, Exists, Q
from django.forms import modelformset_factory
from django.http import HttpResponse, FileResponse
from django_pandas.io import read_frame
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, ListView, UpdateView, DetailView, TemplateView, DeleteView

from .contract import ContractManager, UserContract
from .cooking_direction_plates import CookingDirectionPlatesManager, PlateNameAnalizeUtil
from .date_management import OrderChangableDayUtil, SalesDayUtil
from .desigin_seal_csv import DesignSealCsvWriter
from .exceptions import NotChangeOrderError, SetoutDirectionNotExistError

from .forms import OrderForm, OrderListForm, OrderChangeForm, OrderRiceForm, AllergenForm, OrderNewYearForm, AllergenNewYearForm
from .forms import CommunicationForm, PaperDocumentsForm, InvoiceFilesForm, DocumentsUploadForm, OrderListSalesForm
from .forms import ImportMenuNameForm, ConvertCookingDirectionForm, CreateMeasureTableForm, RegisterMonthlyMenuForm
from .forms import FoodPhotoForm, HeatingProcessingForm, DocumentCheckForm, ExecCalculateSalesPriceForm, EngeFoodDirectionForm, ImportMonthlyReportForm
from .forms import ExecForm, ExecMonthForm, ChatForm, AggrigationSearchForm, FoodDirectionForm, EngeFoodDirectionForm
from .forms import ImportP7FileForm, OutputP7FileForm, SearchSalesPriceForm, ExecOutputKakiokoshiForm, PickingResultFileForm, DirectionPickingForm,OutputSealCsvForm
from .forms import OrderListCsvForm, OrderUnitForm, OrderMaintenanceForm, OrderMaintenanceSearchForm
from .forms import OutputPouchDesignForm, DesignSealCsvForm
from .forms import PickingNoticeForm, SearchSalesInvoiceForm
from .forms import UnitSearchForm, UnitImportForm, EverydaySellingForm, NewUnitPriceForm, PreorderSettingForm
from .forms import OrderRiceMasterForm, OrderRiceMasterUpdateForm, LongHolidayForm, NewYearDaySettingForm
from .forms import AllergenMasterCreateForm, AllergenMasterUpdateForm, AllergenSettingForm, SalesDaySettingForm
from .forms import MixRicePackageForm, SetOutDirectionForm, DocumentFolderForm, TaxSettingsForm, CommonAllergenForm
from .forms import UserDryColdUpdateForm, MixRicePlateForm, RawPlateForm, SetoutDurationSearchForm, SetoutDurationForm
from accounts.forms import CustomUserUpdateDryColdForm

from .meal import MealUtil
from .models import Order, OrderRice, Communication, OrderEveryday, AllergenDisplay, MealDisplay, MenuDisplay
from .models import UnitMaster, UserOption, DocGroupDisplay, PaperDocuments, InvoiceFiles, ReservedMealDisplay
from .models import Chat, FoodPhoto, MonthlyMenu, HolidayList, JapanHoliday, NewYearDaySetting, DocumentDirDisplay, ImportMonthlyReport
from .models import GenericSetoutDirection, EngeFoodDirection, SetoutDuration, MonthlySalesPrice, ImportP7SourceFile
from .models import AllergenPlateRelations, CookingDirectionPlate, BackupAllergenPlateRelations, PickingResultRaw
from .models import InvoiceException, PickingNotice, ReqirePickingPackage, InvoiceDataHistory, ReservedStop
from .models import UnitPackage, PlatePackageForPrint, TaxEverydaySellingSetting
from .models import EverydaySelling, NewUnitPrice, AllergenMaster, MixRicePackageMaster, TaxSetting, TaxMaster
from .models import CommonAllergen, ImportUnit, UserCreationInput, AggMeasureMixRiceMaster, RawPlatePackageMaster

from .p7 import P7SourceFileReader, P7CsvFileWriter
from .picking import ChillerPicking, PickingDirectionOutputManagement, EatingManagement, InnerPackageManagement
from .picking import QrCodeUtil, PickingResultFileReader

from .pouch_design import PouchAggregate, PouchDesignWriter

from .services import AggregateOrder, CookingProduceExporter
from .setout import ImageClearRequest, EditSetoutDirecion, OutputSetoutHelper
from .units import UnitImporter, KarteWriter


logger = logging.getLogger(__name__)


# 共通関数 -----------------------------------------------------------
def get_first_date(datetime):
    return datetime.replace(day=1)


def get_last_date(datetime):
    return datetime.replace(day=calendar.monthrange(datetime.year, datetime.month)[1])


def get_holiday_list(order_limit_day):

    queryset = HolidayList.objects.filter(limit_day__gte=order_limit_day).order_by('limit_day')
    holiday_list = []

    name = ''
    for res in queryset:
        holidays = []
        name = res.holiday_name
        s_date = res.start_date
        e_date = res.end_date
        holidays.append(s_date)
        next_date = s_date + timedelta(days=1)

        while next_date <= e_date:
            holidays.append(next_date)
            next_date = next_date + timedelta(days=1)

        holiday_list.append((sorted(holidays), res.limit_day))

    return holiday_list, name


def is_in_holiday_list(target_day):
    """
    指定日が長期休暇に含まれるかどうかを返す
    """
    try:
        all = list(HolidayList.objects.all())
        queryset = HolidayList.objects.filter(end_date__gte=target_day, start_date__lte=target_day)
        q_list = list(queryset)
        return queryset.exists()
    except BaseException as e:
        test = f'test'
        return False


def get_holiday_next_day(target_day):
    current_day = target_day
    queryset = HolidayList.objects.filter(end_date__gte=current_day).order_by('limit_day')

    holiday_list = [x for x in queryset if (x.start_date <= current_day) and (x.end_date >= current_day)]

    while holiday_list:
        current_day += timedelta(days=1)
        holiday_list = [x for x in queryset if (x.start_date <= current_day) and (x.end_date >= current_day)]

    return current_day


def get_holiday_prev_day(target_day):
    current_day = target_day
    queryset = HolidayList.objects.filter(start_date__lte=current_day).order_by('limit_day')

    holiday_list = [x for x in queryset if (x.start_date <= current_day) and (x.end_date >= current_day)]

    while holiday_list:
        current_day -= timedelta(days=1)
        holiday_list = [x for x in queryset if (x.start_date <= current_day) and (x.end_date >= current_day)]

    return current_day


def is_holiday(input_date, holiday_list):
    # 指定された日が祝日(振替休日含む)かどうかを取得する
    # 引数： 日時、祝日リスト(日付)
    # 返り値： input_dateが祝日かどうか

    date = input_date.date()
    matched = [x for x in holiday_list if x == date]
    return matched


def get_delta_working_day_v1(input_date, holiday_list, days):
    delta_date = input_date
    while is_holiday(delta_date, holiday_list) or (delta_date.weekday() == 6):
        delta_date = delta_date + timedelta(days=1)

    for _ in range(days):
        delta_date = delta_date + timedelta(days=1)
        while is_holiday(delta_date, holiday_list) or (delta_date.weekday() == 6):
            delta_date = delta_date + timedelta(days=1)

    return delta_date


def get_order_change_limit(date, holiday_list, days_of_rule):
    # dateが日曜なら、それ以外まで巻き戻す(日曜以外は変更期限の最短日になる可能性がある)
    delta_date = date
    while delta_date.weekday() in [6]:
        delta_date = delta_date - timedelta(days=1)

    # 平日6日分戻す
    for _ in range(days_of_rule):
        delta_date = delta_date - timedelta(days=1)
        while is_holiday(delta_date, holiday_list) or (delta_date.weekday() in [5, 6]):
            delta_date = delta_date - timedelta(days=1)

    return delta_date

def get_delta_working_day_v2(input_date, holiday_list, days):
    # +6日、必ず土日は挟むので+2の計8日
    delta_date = input_date + timedelta(days=8)

    # 仮基準日のリミットを取得
    limit = get_order_change_limit(delta_date, holiday_list, days)
    if limit == input_date:
        # 同日の場合は、制限日を確定
        return delta_date
    elif limit > input_date:
        delta_date -= timedelta(days=1)
        before_limit = get_order_change_limit(delta_date, holiday_list, days)
        while before_limit > input_date:
            # 同じか追い越すまで、さかのぼる
            delta_date -= timedelta(days=1)
            before_limit = get_order_change_limit(delta_date, holiday_list, days)

        if before_limit == input_date:
            # 入力と同じ日なら、再取得日が制限日
            return delta_date
        else:
            # 入力を下回ったら、入力日を始めて追い越した日が制限日
            return delta_date + timedelta(days=1)
    else:
        delta_date += timedelta(days=1)
        after_limit = get_order_change_limit(delta_date, holiday_list, days)
        while after_limit < input_date:
            # 同じか追い越すまで、進める
            delta_date += timedelta(days=1)
            after_limit = get_order_change_limit(delta_date, holiday_list, days)

        return delta_date


def is_working_day_v1(youbi, input_date, holiday_list):
    # 日曜でない、かつ祝日でもない
    return (not (youbi == 6)) and (not is_holiday(input_date, holiday_list))


def is_working_day_v2(youbi, input_date, holiday_list):
    # 日曜でない、かつ祝日でもない
    return (not (youbi in [5, 6])) and (not is_holiday(input_date, holiday_list))


def get_order_change_dates(input_date, ignore_holiday_list=False):
    version_no = OrderChangableDayUtil.get_rule_version_by_settings(input_date)
    if version_no == 1:
        return get_order_change_dates_v1(input_date, ignore_holiday_list)
    elif version_no == 2:
        return get_order_change_dates_v2(input_date, ignore_holiday_list)
    else:
        logger.warning('食数変更期限ルール適用解析失敗')
        return get_order_change_dates_v1(input_date, ignore_holiday_list)


def get_order_change_dates_v1(input_date, ignore_holiday_list=False):
    """
    # 仮注文後の食数変更が可能な期間を返す(ルールバージョン1)。日祝以外を平日とする。
    # 引数： 日時、長期休暇を無視するかどうか
    # 返り値： 開始日と終了日
    """

    # 前提： 食数変更期限は日曜・祝日を除いた喫食日の6営業日前まで

    youbi = input_date.weekday()  # 今日現在の曜日(月曜日が0〜日曜日が6)
    jikoku = int(input_date.strftime('%H'))  # 現在の時刻

    # 終了日は、今日を起点に翌々週の月曜日（それ以降は仮注文フォームで入力可能）

    # 祝日対応：国民の祝日を読み込む
    holiday_list_qs = JapanHoliday.objects.filter(date__gte=input_date).values('date').order_by('date')
    holiday_list = [x['date'] for x in holiday_list_qs]

    # 開始日の計算
    start_days = 6
    # 営業日は10:00で締め切りの切り替えが発生する
    if is_working_day_v1(youbi, input_date, holiday_list) and (jikoku >= 10):
        start_days += 1

    # 今日が日曜日なら土曜午後から引き続き次の月曜喫食日分、つまり8日後以降のものが変更可能で、10時以降も変更なし
    if youbi == 6:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=15)

    # 今日が月曜なら10時までは次の月曜喫食日分、つまり7日後(日曜を除いた6日後)以降のものが変更可能で、10時を過ぎると8日後以降のものが可能
    elif youbi == 0:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=14)

    # 今日が火曜なら10時までは次の火曜曜喫食日分、つまり7日後以降のものが変更可能で、10時を過ぎると8日後以降のものが可能
    elif youbi == 1:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=13)

    # 今日が水曜なら10時までは次の水曜曜喫食日分、つまり7日後以降のものが変更可能で、10時を過ぎると8日後以降のものが可能
    elif youbi == 2:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=12)

    # 今日が木曜なら10時までは次の木曜曜喫食日分、つまり7日後以降のものが変更可能で、10時を過ぎると8日後以降のものが可能
    elif youbi == 3:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=11)

    # 今日が金曜なら10時までは次の金曜曜喫食日分、つまり7日後以降のものが変更可能で、10時を過ぎると8日後以降のものが可能
    elif youbi == 4:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)
        to_date = input_date + timedelta(days=10)

    # 今日が土曜なら10時までは次の土曜曜喫食日分、つまり7日後以降のものが変更可能で、10時を過ぎると9日後以降のものが可能
    # (次の日曜日喫食分は、10時まで変更可能)
    elif youbi == 5:
        from_date = get_delta_working_day_v1(input_date, holiday_list, start_days)

        if jikoku >= 17:  # 17を過ぎていた場合
            to_date = input_date + timedelta(days=16)
        else:
            to_date = input_date + timedelta(days=9)
    else:
        from_date = input_date
        to_date = input_date

    # 祝日の関係でto_dateを追い越してしまった場合は、to_dateを一週間伸ばす
    # (仮注文とかぶってしまうが、とくに不整合は発生しないので、そのまま)
    if from_date > to_date:
        to_date = to_date + timedelta(days=7)

    # 時刻を除外して日付のみに変更
    from_date = from_date.date()  # 最短注文可能開始日
    to_date = to_date.date()

    # 長期休暇対応
    if not ignore_holiday_list:
        # 休暇中は変更不可とする
        if is_in_holiday_list(from_date):
            raise NotChangeOrderError("長期休暇", get_holiday_next_day(from_date))

        # to_dateが休暇にかかっている場合は、休暇の前日までとする
        if is_in_holiday_list(to_date):
            to_date = get_holiday_prev_day(to_date)

    # 仮注文期間の開始日を追い越してしまっていた場合、アレルギー注文が出来なくなってしまうので、仮注文の開始日に合わせる
    reserved_from = get_next_next_tuesday(input_date).date()
    if from_date > reserved_from:
        from_date = reserved_from

    return (from_date, to_date)


def get_order_change_dates_v2(input_date, ignore_holiday_list=False):
    """
    # 仮注文後の食数変更が可能な期間を返す(ルールバージョン2)。土日祝以外を平日とする。
    # 引数： 日時、長期休暇を無視するかどうか
    # 返り値： 開始日と終了日
    """

    # 前提： 食数変更期限は土用・日曜・祝日を除いた喫食日の6営業日前まで

    youbi = input_date.weekday()  # 今日現在の曜日(月曜日が0〜日曜日が6)
    jikoku = int(input_date.strftime('%H'))  # 現在の時刻

    # 終了日は、今日を起点に翌々週の月曜日（それ以降は仮注文フォームで入力可能）

    # 祝日対応：国民の祝日を読み込む
    search_date = input_date - relativedelta(days=7)
    holiday_list_qs = JapanHoliday.objects.filter(date__gte=search_date).values('date').order_by('date')
    holiday_list = [x['date'] for x in holiday_list_qs]

    # 開始日の計算
    start_days = 6
    start_day = input_date
    # 営業日は10:00で締め切りの切り替えが発生する
    # V2では、非営業日でも10:00に切り替える
    # if is_working_day_v2(youbi, input_date, holiday_list) and (jikoku >= 10):
    if jikoku >= 10:
        start_day += relativedelta(days=1)

    # 今日が日曜日
    if youbi == 6:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=17)
        else:
            to_date = start_day + timedelta(days=16)

    # 今日が月曜
    elif youbi == 0:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=16)
        else:
            to_date = start_day + timedelta(days=15)

    # 今日が火曜
    elif youbi == 1:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=15)
        else:
            to_date = start_day + timedelta(days=14)

    # 今日が水曜
    elif youbi == 2:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=14)
        else:
            to_date = start_day + timedelta(days=13)

    # 今日が木曜
    elif youbi == 3:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=13)
        else:
            to_date = start_day + timedelta(days=12)

    # 今日が金曜
    elif youbi == 4:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=12)
        else:
            to_date = start_day + timedelta(days=11)

    # 今日が土曜
    elif youbi == 5:
        from_date = get_delta_working_day_v2(start_day, holiday_list, start_days)
        if jikoku < 10:
            to_date = start_day + timedelta(days=11)
        else:
            to_date = start_day + timedelta(days=17)

    else:
        from_date = start_day
        to_date = start_day

    # 祝日の関係でto_dateを追い越してしまった場合は、to_dateを一週間伸ばす
    # (仮注文とかぶってしまうが、とくに不整合は発生しないので、そのまま)
    if from_date > to_date:
        to_date = to_date + timedelta(days=7)

    # 特別補正
    if (from_date.year == 2024) and (from_date.month == 3) and (from_date.day == 4):
        from_date += timedelta(days=1)

    # 時刻を除外して日付のみに変更
    from_date = from_date.date()  # 最短注文可能開始日
    to_date = to_date.date()

    # 長期休暇対応
    if not ignore_holiday_list:
        # 休暇中は変更不可とする
        if is_in_holiday_list(from_date):
            raise NotChangeOrderError("長期休暇", get_holiday_next_day(from_date))

        # to_dateが休暇にかかっている場合は、休暇の前日までとする
        if is_in_holiday_list(to_date):
            to_date = get_holiday_prev_day(to_date)

    # 仮注文期間の開始日を追い越してしまっていた場合、アレルギー注文が出来なくなってしまうので、仮注文の開始日に合わせる
    reserved_from = get_next_next_tuesday(input_date).date()
    if from_date > reserved_from:
        from_date = reserved_from

    return (from_date, to_date)


def get_next_next_tuesday(input_date):
    # 土曜の17時を境界として、翌々週の火曜日を返す
    # 引数： 日時
    # 返り値： 翌々週の火曜日

    youbi = input_date.weekday()  # 入力日時の曜日(月曜日が0〜日曜日が6)
    jikoku = int(input_date.strftime('%H'))  # 入力日時の時刻

    if youbi == 6:  # 日曜日なら
        next_next_tue = input_date + timedelta(days=16)
    elif youbi == 0:  # 月曜日なら
        next_next_tue = input_date + timedelta(days=15)
    elif youbi == 1:
        next_next_tue = input_date + timedelta(days=14)
    elif youbi == 2:
        next_next_tue = input_date + timedelta(days=13)
    elif youbi == 3:
        next_next_tue = input_date + timedelta(days=12)
    elif youbi == 4:
        next_next_tue = input_date + timedelta(days=11)
    elif youbi == 5:  # 土曜日なら
        if jikoku >= 17:  # 17を過ぎていた場合
            next_next_tue = input_date + timedelta(days=17)
        else:
            next_next_tue = input_date + timedelta(days=10)
    else:
        next_next_tue = input_date

    return next_next_tue


def get_next_tuesday(input_date):
    # 日曜0時を境界として、翌々週の火曜日を返す
    # 引数： 日時
    # 返り値： 翌週の火曜日

    youbi = input_date.weekday()  # 入力日時の曜日(月曜日が0〜日曜日が6)

    if youbi == 6:  # 日曜日なら
        next_tue = input_date + timedelta(days=8)
    elif youbi == 0:  # 月曜日なら
        next_tue = input_date + timedelta(days=8)
    elif youbi == 1:
        next_tue = input_date + timedelta(days=7)
    elif youbi == 2:
        next_tue = input_date + timedelta(days=6)
    elif youbi == 3:
        next_tue = input_date + timedelta(days=5)
    elif youbi == 4:
        next_tue = input_date + timedelta(days=4)
    elif youbi == 5:  # 土曜日なら
        next_tue = input_date + timedelta(days=3)
    else:
        next_tue = input_date

    return next_tue


# トップページの表示 ----------------------------------------------------
def index(request):
    qs1 = Communication.objects.filter(group_id=1).select_related('group') \
        .order_by('-updated_at')

    return render(request, template_name='index.html', context={'qs1': qs1})


# 仮注文・週間注文フォーム ------------------------------------------------
def order(request):
    date_time_now = dt.datetime.now()  # 現在の日時と時刻
    from_date = get_next_next_tuesday(date_time_now).date()  # 仮注文が可能な直近の喫食日

    # ----------------------------------------------------------------------------
    # 特定の施設のみ仮発注期限を一時的に解除する（前週に戻す）
    # ----------------------------------------------------------------------------
    qs_user_option = UserOption.objects.filter(unlock_limitation=True)
    user_option = None

    for usr in qs_user_option:
        if usr.username_id == request.user.id:
            user_option = usr
            from_date = from_date - timedelta(days=7)
    # ----------------------------------------------------------------------------


    to_date = from_date + timedelta(days=6)  # 1画面に表示する日数(１週間分）

    # from_date -> 今日から翌々週の火曜日（仮注文可能な直近の喫食日）
    # to_date   -> 今日から翌々々週の月曜日

    # ----------------------------------------------------------------------------
    # 画面上部に表示する告知内容
    # ----------------------------------------------------------------------------
    # 仮注文の期限日（今日から直近の土曜日）
    order_limit_day = from_date - timedelta(days=10)

    # 仮注文の期限日までに入力してもらう喫食開始日・火曜日
    order_start = order_limit_day + timedelta(days=10)
    # 仮注文の期限日までに入力してもらう喫食終了日・月曜日
    order_end = order_limit_day + timedelta(days=16)
    # ----------------------------------------------------------------------------

    # 長期休暇に設定されている日付のリストを取得
    holiday_list, _ = get_holiday_list(order_limit_day)
    for holidays, holiday_limit_day in holiday_list:
        if order_end in holidays:
            duration = order_start - holidays[0]
            if (date_time_now.weekday() == 5) and (date_time_now.hour >= 17):
                judge_days = 6
            else:
                judge_days = 7
            if (duration.days >= judge_days) and (order_start in holidays):
                # 各期日を1週間延長
                order_limit_day = order_limit_day + timedelta(days=7)
                from_date = from_date + timedelta(days=7)
                to_date = to_date + timedelta(days=7)
                order_start = order_start + timedelta(days=7)
                order_end = order_end + timedelta(days=7)

                # まだorder_endが休暇期間内なら、越えるまで延長
                while order_end in holidays:
                    order_limit_day = order_limit_day + timedelta(days=7)
                    from_date = from_date + timedelta(days=7)
                    to_date = to_date + timedelta(days=7)
                    order_start = order_start + timedelta(days=7)
                    order_end = order_end + timedelta(days=7)

                # order_endが休暇期間を超えている状態
                # 入力開始期間は、休み明けの日から
                order_start = holidays[-1] + timedelta(days=1)
            else:
                # order_startはかえる必要ないはず・・・
                order_end = holidays[-1]

            break
        else:
            duration = holiday_limit_day - order_limit_day
            if (date_time_now.weekday() == 5) and (date_time_now.hour >= 17):
                judge_days = 6
            else:
                judge_days = 7
            if duration.days < judge_days:
                # この期間の入力を設定
                if (order_end + timedelta(days=1)) == holidays[0]:
                    order_end = holidays[-1]
                    order_limit_day = holiday_limit_day
                else:
                    order_start = holidays[0]
                    order_end = holidays[-1]
                    from_date = holidays[0] # 火曜日である前提
                    to_date = from_date + timedelta(days=6)
                    order_limit_day = holiday_limit_day
                break
    change_limit_day = None
    if not holiday_list:
        next_day = get_holiday_next_day(order_start)
        if order_start != next_day:
            s_day = next_day
            while s_day.weekday() != 5:
                # 土曜日まで戻す
                s_day -= timedelta(days=1)
            # もう一週間(仮注文入力期間)分戻す
            s_day -= timedelta(days=7)
            order_limit_day = s_day
            order_start = next_day  # 火曜日である前提
            # TODO:next_day以降に日本の祝日がある場合の対応
            order_end = next_day + timedelta(days=6)
            e_day = next_day
            if e_day.weekday() != 1:
                # 長期休暇明け以前を入力不可にする
                change_limit_day = next_day
                while e_day.weekday() != 1:
                    # 火曜日まで戻す
                    e_day -= timedelta(days=1)
                from_date = e_day  # 火曜日である前提
                to_date = from_date + timedelta(days=6)
                order_end = to_date
    """
    if order_end in holidays:
        # 仮注文期限日が、休暇期間に含まれるなら、休暇期間までに入力してもらう。
        # 休暇期間から1週間以上経過していなければ、まだ休暇前の期間の仮入力を受け付けている期間
        duration = order_start - holidays[0]
        if (date_time_now.weekday() == 5) and (date_time_now.hour >= 17):
            judge_days = 6
        else:
            judge_days = 7
        if (duration.days >= judge_days) and (order_start in holidays):
            # 各期日を1週間延長
            order_limit_day = order_limit_day + timedelta(days=7)
            from_date = from_date + timedelta(days=7)
            to_date = to_date + timedelta(days=7)
            order_start = order_start + timedelta(days=7)
            order_end = order_end + timedelta(days=7)

            # まだorder_endが休暇期間内なら、越えるまで延長
            while order_end in holidays:
                order_limit_day = order_limit_day + timedelta(days=7)
                from_date = from_date + timedelta(days=7)
                to_date = to_date + timedelta(days=7)
                order_start = order_start + timedelta(days=7)
                order_end = order_end + timedelta(days=7)

            # order_endが休暇期間を超えている状態
            # 入力開始期間は、休み明けの日から
            order_start = holidays[-1] + timedelta(days=1)
        else:
            # order_startはかえる必要ないはず・・・
            order_end = holidays[-1]
    else:
        if order_start in holidays:
            # order_startがまだ休暇期間に含まれる場合
            # 休暇期間終了の手前までは前の週で締め切っているはず・・・
            # 入力開始期間は、休み明けの日から
            order_start = holidays[-1] + timedelta(days=1)
    """

    # ----------------------------------------------------------------------------
    # 特定の施設のみ仮発注期限を一時的に解除する（日付指定）
    # ----------------------------------------------------------------------------
    if user_option and user_option.unlock_day:
        unlock_day = user_option.unlock_day

        # unlock_dayがfrom_dateより未来の場合は対応しない
        if from_date > unlock_day:
            while from_date > unlock_day:
                from_date = from_date - timedelta(days=7)
                to_date = to_date - timedelta(days=7)
            order_start = unlock_day
            change_limit_day = get_order_change_dates(date_time_now, True)[0]
    # ----------------------------------------------------------------------------
    # 「翌週へ」「前週へ」ボタンを押すと仮注文が可能な喫食日の週を移動させる
    # ----------------------------------------------------------------------------
    if 'n' in request.GET:
        # 翌週を表示
        this_week = request.GET.get('n')
        this_week = dt.datetime.strptime(this_week, '%Y%m%d')  # 文字列型から日付+時間型に変換
        from_date = (this_week + timedelta(days=7)).date()  # 日付+時間型から日付型に変換 翌週の火曜日から
        to_date = (this_week + timedelta(days=13)).date()  # 翌々週の月曜日まで

    elif 'p' in request.GET:
        # 前週を表示
        this_week = request.GET.get('p')
        this_week = dt.datetime.strptime(this_week, '%Y%m%d')
        from_date_prev = (this_week - timedelta(days=7)).date()  # 前週の火曜日から
        to_date_prev = (this_week - timedelta(days=1)).date()  # 前日である月曜日まで

        if from_date > from_date_prev:  # 前週ボタンを押して、最短注文可能日よりも過去になってしまった場合
            pass
        else:
            from_date = from_date_prev
            to_date = to_date_prev

    # 食数入力欄のフォームセットが連続して出力されるため、ループの途中で空行や日付行を挿入するために区切る数を準備する

    order_this_week = Order.objects.filter(unit_name__username_id=request.user, allergen=1,
                                           eating_day__range=[from_date, to_date])

    # Weeklyバッチで未作成の週になった場合は、それ以上遷移しない処理
    if not order_this_week.exists():
        from_date = from_date - timedelta(days=7)
        to_date = from_date + timedelta(days=6)
        order_this_week = Order.objects.filter(unit_name__username_id=request.user, allergen=1,
                                               eating_day__range=[from_date, to_date])

    # 利用しているユニットを取り出す
    unit_list = order_this_week.values_list('unit_name__unit_name', flat=True) \
        .annotate(Count('unit_name')).order_by('unit_name_id')
    unit_cnt = unit_list.count()  # ユニットの数

    # 提供している献立種類（常食・ソフトなど）
    menu_list = order_this_week \
        .values_list('menu_name__menu_name', flat=True) \
        .annotate(Count('menu_name')) \
        .order_by('menu_name_id')
    menu_cnt = menu_list.count()  # 献立種類の数
    if from_date >= dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date():
        menu_list = list(menu_list)
        for i, m in enumerate(menu_list):
            if m == '常食':
                menu_list[i] = '基本食'

    # 提供している食事種別（朝食・昼食・夕食など）
    meal_list = order_this_week \
        .values_list('meal_name__meal_name', flat=True) \
        .annotate(Count('meal_name')) \
        .order_by('meal_name__seq_order')
    meal_cnt = meal_list.count()  # 食事種別種類の数

    meal_cells = meal_cnt * 7  # 次の日付行を表示するまでに使う食数入力欄の数 21とか28 ステップ数に使う
    menu_cells = meal_cells * menu_cnt  # 複数ある献立ごとに日付行を挿入するための区切りリスト作成時のステップ数に使う
    unit_cells = meal_cells * menu_cnt * unit_cnt  # 全ユニット分の食数入力欄 区切りリスト作成時の最大値に使う

    menu_cycle = []  # 献立が複数あるときは変わるたびに日付行を挿入する用
    for x in range(0, unit_cells, meal_cells):
        menu_cycle.append(x)

    unit_cycle = []  # ユニットが複数あるときに献立が変わるたびに空行と日付行を挿入する用
    for y in range(0, unit_cells, menu_cells):
        unit_cycle.append(y)

    date_list = []
    for d in range(7):
        date_list.append(from_date + timedelta(days=d))

    OrderFormSet = modelformset_factory(Order, form=OrderForm, extra=0)

    # このクエリセットのORDER_BYは、Weeklyでバッチ作成したときのID順になっているので変更すると並びがおかしくなる
    # 下記コメントアウト行はユニットの環境では上手くいった。
    # qs = Order.objects.filter(unit_name__username_id=request.user, allergen=1, eating_day__range=[from_date, to_date]).order_by('menu_name', 'meal_name', 'eating_day')
    qs = Order.objects.filter(unit_name__username_id=request.user, allergen=1, eating_day__range=[from_date, to_date]).order_by('id')
    qs_count = qs.count()

    formset = OrderFormSet(request.POST or None, queryset=qs, form_kwargs={'change_limit_day': change_limit_day})

    # レコード数が７の倍数出ない場合は不整合が発生しているためエラーを出す

    qs_prev = Order.objects\
        .filter(unit_name__username_id=request.user,
                allergen=1, eating_day__range=[from_date - timedelta(days=7), to_date - timedelta(days=7)])\
        .order_by('id')
    prev_counts = ",".join([str(x.quantity or 0) for x in qs_prev])

    if request.method == "POST" and formset.is_valid():
        logger.info(f"●仮注文入力開始({request.user.facility_name})-{from_date}")

        for fm in formset:
            updated_order = fm.save(commit=False)
            if (updated_order.eating_day.month == 1) and (updated_order.eating_day.day == 1):
                pass
            else:
                updated_order.save()

        logger.info(f"●仮注文入力完了({request.user.facility_name})")
        messages.success(request, 'この週の注文を確定しました。')
        return redirect("web_order:order")
    else:
        if request.method == "POST" and (not formset.is_valid()):
            messages.error(request, '入力内容に不備があります。0以上の整数で入力してください。')
        context = {
            "unit_cnt": unit_cnt,
            "menu_cnt": menu_cnt,
            "meal_cnt": meal_cnt,
            "unit_cells": unit_cells,
            "meal_cells": meal_cells,
            "menu_cells": menu_cells,

            "formset": formset,
            "order_limit_day": order_limit_day,
            "order_start": order_start,
            "order_end": order_end,
            "unit_list": unit_list,
            "menu_list": menu_list,
            "meal_list": meal_list,
            "unit_cycle": unit_cycle,
            "menu_cycle": menu_cycle,
            "date_list": date_list,
            "from_date": from_date,
            "prev_counts": prev_counts,
        }
        return render(request, template_name="order.html", context=context)

    # 21で割り切れなかったらエラーとかチェックするポイント用意する


# 元日注文フォーム ------------------------------------------------
def is_show_new_year(request):
    now = dt.datetime.now()
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
            return False
        elif (setting.enable_date_to == to_date) and (hour >= 10):
            # 表示期間の終了日でも10時以後なら、画面を表示しない
            return False
        else:
            return True
    else:
        return False

def order_new_year(request):
    def get_valid_allergen_orders(post):
        orders = []
        result = True
        for i in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
            id_value = post.get(f'ar_order_{i}_id', None)
            unit_value = post.get(f'ar_order_{i}_unit', None)
            meal_value = post.get(f'ar_order_{i}_meal', None)
            menu_value = post.get(f'ar_order_{i}_menu', None)
            allergen_value = post.get(f'ar_order_{i}_allergen', None)
            quantity_value = post.get(f'ar_order_{i}_quantity', 0)
            if unit_value and meal_value and menu_value and allergen_value:
                orders.append((id_value, unit_value, meal_value, menu_value, allergen_value, int(quantity_value) if quantity_value else 0))
            elif unit_value or meal_value or menu_value or allergen_value:
                # いずれかの項目に空がある場合
                result = False
        return (result, orders)

    def get_input_allergen_orders(post):
        orders = []
        none_list = []
        for i in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
            id_value = post.get(f'ar_order_{i}_id', None)
            unit_value = post.get(f'ar_order_{i}_unit', None)
            meal_value = post.get(f'ar_order_{i}_meal', None)
            menu_value = post.get(f'ar_order_{i}_menu', None)
            allergen_value = post.get(f'ar_order_{i}_allergen', None)
            quantity_value = post.get(f'ar_order_{i}_quantity', None)
            if id_value:
                order = Order.objects.get(id=id_value)
            else:
                if not(unit_value or meal_value or menu_value or allergen_value or quantity_value):
                    order = None
                else:
                    order = Order()
            if order:
                order.unit_name_id = int(unit_value) if unit_value else None
                order.meal_name_id = int(meal_value) if meal_value else None
                order.menu_name_id = int(menu_value) if menu_value else None
                order.allergen_id = int(allergen_value) if allergen_value else None
                order.quantity = quantity_value
            if order:
                orders.append(order)
            else:
                none_list.append(order)

        orders += none_list
        return orders

    # 処理対象外の日時の場合に、表示・更新をさせない対応
    if not is_show_new_year(request):
        messages.error(request, '処理できません。')
        context = {
            "error_message": '対応可能時間を過ぎておりますので、処理できません。',
            "disable_processing": True
        }
        return render(request, template_name="order_new_year.html", context=context)

    date_time_now = dt.datetime.now()  # 現在の日時と時刻
    new_year_day = dt.datetime.strptime(f'{date_time_now.year + 1}-01-01', '%Y-%m-%d')
    new_year_settings = NewYearDaySetting.objects.get(year=new_year_day.year)

    # 利用しているユニットを取り出す
    order_new_year_day = Order.objects.filter(unit_name__username_id=request.user, allergen=1,
                                           eating_day=new_year_day)
    unit_list = order_new_year_day.values_list('unit_name__unit_name', flat=True) \
        .annotate(Count('unit_name')).order_by('unit_name_id')
    unit_cnt = unit_list.count()  # ユニットの数

    # 提供している献立種類（常食・ソフトなど）
    menu_list = order_new_year_day \
        .values_list('menu_name__menu_name', flat=True) \
        .annotate(Count('menu_name')) \
        .order_by('menu_name_id')
    menu_cnt = menu_list.count()  # 献立種類の数

    if new_year_day >= dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d'):
        menu_list = list(menu_list)
        for i, m in enumerate(menu_list):
            if m == '常食':
                menu_list[i] = '基本食'

    # 提供している食事種別（朝食・昼食・夕食など）
    meal_list = order_new_year_day \
        .values_list('meal_name__meal_name', flat=True) \
        .annotate(Count('meal_name')) \
        .order_by('meal_name__seq_order')
    meal_cnt = meal_list.count()  # 食事種別種類の数
    is_only_meal = True if meal_cnt == 1 else False

    # 食事区分が2つの場合の対応
    meals = list(meal_list)
    two_meal = ''
    if len(meals) == 2:
        if ('朝食' in meals) and ('昼食' in meals):
            two_meal = '朝昼'
        elif ('朝食' in meals) and ('夕食' in meals):
            two_meal = '朝夕'
        elif ('昼食' in meals) and ('夕食' in meals):
            two_meal = '昼夕'

    meal_cells = meal_cnt  # 次の行を表示するまでに使う食数入力欄の数
    menu_cells = meal_cells * menu_cnt  # 複数ある献立ごとに行を挿入するための区切りリスト作成時のステップ数に使う
    unit_cells = meal_cells * menu_cnt * unit_cnt  # 全ユニット分の食数入力欄 区切りリスト作成時の最大値に使う

    menu_cycle = []  # 献立が複数あるときは変わるたびに日付行を挿入する用
    for x in range(0, unit_cells, meal_cells):
        menu_cycle.append(x)

    unit_cycle = []  # ユニットが複数あるときに献立が変わるたびに空行と日付行を挿入する用
    for y in range(0, unit_cells, menu_cells):
        unit_cycle.append(y)

    qs = Order.objects.filter(unit_name__username_id=request.user, allergen=1, eating_day=new_year_day)
    qs_count = qs.count()
    OrderFormSet = modelformset_factory(Order, form=OrderNewYearForm, extra=0)
    formset = OrderFormSet(request.POST or None, queryset=qs)

    # アレルギー注文画面用の選択肢
    ar_unit_list = UnitMaster.objects.filter(username=request.user)
    ar_meal_list = MealDisplay.objects.filter(username=request.user)
    ar_menu_list = MenuDisplay.objects.filter(username=request.user).exclude(menu_name__menu_name='薄味')
    allergen_list = AllergenDisplay.objects.filter(username=request.user)

    allergen_orders = []
    if allergen_list.exists():
        for x in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
            allergen_orders.append(None)

        qs2 = Order.objects.filter(unit_name__username=request.user, eating_day=new_year_day, quantity__gt=0, allergen__gt=1) \
            .order_by('meal_name__seq_order', 'menu_name')
        al_temp_list = list(qs2)
        for index, x in enumerate(al_temp_list[0:30]):
            allergen_orders[index] = x

    if request.method == "POST":
        is_valid_allergen, orders = get_valid_allergen_orders(request.POST)
        if formset.is_valid() and is_valid_allergen:
            # 通常注文の反映
            formset.save()

            # アレルギー注文の反映
            for x in orders:
                if x[0]:    # IDがある場合
                    order = Order.objects.get(id=x[0])
                    if x[5]:    # 食数がある場合
                        order.unit_name_id = x[1]
                        order.meal_name_id = x[2]
                        order.menu_name_id = x[3]
                        order.allergen_id = x[4]
                        order.quantity = x[5]
                        order.save()
                    else:
                        order.delete()
                else:
                    Order.objects.create(
                        eating_day=new_year_day,
                        unit_name_id=x[1],
                        meal_name_id=x[2],
                        menu_name_id=x[3],
                        allergen_id=x[4],
                        quantity=x[5])
            messages.success(request, '元日の注文を確定しました。')
            return redirect("web_order:order_new_year")
        else:
            ar_orders = get_input_allergen_orders(request.POST)
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "order_limit_day": new_year_settings.enable_date_to,
                "year": date_time_now.year + 1,

                "unit_cycle": unit_cycle,
                "menu_cycle": menu_cycle,
                "formset": formset,
                "allergen_orders": ar_orders,
                "unit_list": unit_list,
                "menu_list": menu_list,

                "ar_unit_list": ar_unit_list,
                "ar_meal_list": ar_meal_list,
                "ar_menu_list": ar_menu_list,
                "allergen_list": allergen_list,
                "is_only_meal": is_only_meal,
                "two_meal": two_meal,
            }
    else:
        context = {
            "order_limit_day": new_year_settings.enable_date_to,
            "year": date_time_now.year + 1,

            "unit_cycle": unit_cycle,
            "menu_cycle": menu_cycle,
            "formset": formset,
            "allergen_orders": list(allergen_orders),
            "unit_list": unit_list,
            "menu_list": menu_list,

            "ar_unit_list": ar_unit_list,
            "ar_meal_list": ar_meal_list,
            "ar_menu_list": ar_menu_list,
            "allergen_list": allergen_list,
            "is_only_meal": is_only_meal,
            "two_meal": two_meal,
        }
    return render(request, template_name="order_new_year.html", context=context)


# 仮注文後の食数変更・一覧 ------------------------------------------------
class OrderChangeList(ListView):
    template_name = 'order_change_list.html'
    model = Order

    def get_context_data(self, **kwargs):
        # dt_str = '2022-05-07 18:00:00'  # 検証用に適当な日時を指定している
        # date_time_now = dt.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

        date_time_now = dt.datetime.now()  # 現在の日時と時刻

        try:
            res = get_order_change_dates(date_time_now)
        except NotChangeOrderError as e:
            context = super().get_context_data(**kwargs)
            context['holiday_name'] = e.message
            return context

        from_date = res[0]
        to_date = res[1]

        new_year_day = dt.datetime(date_time_now.year + 1, 1, 1).date()
        qs = Order.objects.filter(unit_name__username_id=self.request.user, allergen=1,
                                  quantity__gt=0, eating_day__range=[from_date, to_date]) \
            .exclude(eating_day=new_year_day) \
            .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
            .order_by('menu_name__seq_order', 'eating_day', 'meal_name__seq_order', 'allergen__seq_order')

        context = super().get_context_data(**kwargs)
        context['object_list'] = qs
        context['from_date'] = from_date
        context['to_date'] = to_date
        return context

# 仮注文後の食数変更・更新
class OrderChangeUpdate(UpdateView):
    model = Order
    template_name = 'order_change_update.html'
    form_class = OrderChangeForm

    def get_form_kwargs(self):
        kwargs = super(OrderChangeUpdate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(self.request, '修正しました。')
        logger.info(f'仮注文後食数自動更新:[{self.kwargs["pk"]}]-{self.request.user.username}')

        return reverse_lazy('web_order:order_change_list')

    def form_valid(self, form):
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)


class OrderMaintenanceView(TemplateView):
    template_name = 'order_maintenance.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        unit_id = request.GET.get('unit_name', None)
        eating_day_str = request.GET.get('eating_day', None)
        context = {
            'unit_name': unit_id,
            'eating_day': eating_day_str
        }
        today = dt.datetime.today().date()
        adjust_days = SalesDayUtil.get_adjust_days_settings(today)

        if unit_id and eating_day_str:
            eating_day = dt.datetime.strptime(eating_day_str, '%Y-%m-%d')
            # 対象ユニットの対象喫食日の注文を検索
            # 利用しているユニットを取り出す
            unit = UnitMaster.objects.get(id=unit_id)
            order_qs = Order.objects.filter(unit_name=unit, allergen=1,
                                                      eating_day=eating_day)
            unit_list = order_qs.values_list('unit_name__unit_name', flat=True) \
                .annotate(Count('unit_name')).order_by('unit_name_id')
            unit_cnt = unit_list.count()  # ユニットの数

            # 提供している献立種類（常食・ソフトなど）
            menu_list = order_qs \
                .values_list('menu_name__menu_name', flat=True) \
                .annotate(Count('menu_name')) \
                .order_by('menu_name_id')
            menu_cnt = menu_list.count()  # 献立種類の数
            if eating_day >= dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d'):
                menu_list = list(menu_list)
                for i, m in enumerate(menu_list):
                    if m == '常食':
                        menu_list[i] = '基本食'

            # 提供している食事種別（朝食・昼食・夕食など）
            meal_list = order_qs \
                .values_list('meal_name__meal_name', flat=True) \
                .annotate(Count('meal_name')) \
                .order_by('meal_name__seq_order')
            meal_cnt = meal_list.count()  # 食事種別種類の数
            is_only_meal = True if meal_cnt == 1 else False

            # 食事区分が2つの場合の対応
            meals = list(meal_list)
            two_meal = ''
            if len(meals) == 2:
                if ('朝食' in meals) and ('昼食' in meals):
                    two_meal = '朝昼'
                elif ('朝食' in meals) and ('夕食' in meals):
                    two_meal = '朝夕'
                elif ('昼食' in meals) and ('夕食' in meals):
                    two_meal = '昼夕'

            meal_cells = meal_cnt  # 次の行を表示するまでに使う食数入力欄の数
            menu_cells = meal_cells * menu_cnt  # 複数ある献立ごとに行を挿入するための区切りリスト作成時のステップ数に使う
            unit_cells = meal_cells * menu_cnt * unit_cnt  # 全ユニット分の食数入力欄 区切りリスト作成時の最大値に使う

            menu_cycle = []  # 献立が複数あるときは変わるたびに日付行を挿入する用
            for x in range(0, unit_cells, meal_cells):
                menu_cycle.append(x)

            unit_cycle = []  # ユニットが複数あるときに献立が変わるたびに空行と日付行を挿入する用
            for y in range(0, unit_cells, menu_cells):
                unit_cycle.append(y)

            logger.debug(f'cycle=unit:{unit_cycle}/menu:{menu_cycle}')
            qs = Order.objects.filter(unit_name=unit, allergen=1, eating_day=eating_day, unit_name__is_active=True)
            OrderFormSet = modelformset_factory(Order, form=OrderMaintenanceForm, extra=0)
            formset = OrderFormSet(None, queryset=qs)

            # アレルギー注文画面用の選択肢
            ar_unit_list = UnitMaster.objects.filter(unit_name=unit)
            ar_meal_list = MealDisplay.objects.filter(username=unit.username).order_by('meal_name__seq_order')
            ar_menu_list = MenuDisplay.objects.filter(
                username=unit.username).exclude(menu_name__menu_name='薄味').order_by('menu_name__seq_order')
            allergen_list = AllergenDisplay.objects.filter(username=unit.username)

            allergen_orders = []
            if allergen_list.exists():
                for x in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
                    allergen_orders.append(None)

                qs2 = Order.objects.filter(unit_name=unit, eating_day=eating_day, quantity__gt=0,
                                           allergen__gt=1, unit_name__is_active=True) \
                    .order_by('meal_name__seq_order', 'menu_name')
                al_temp_list = list(qs2)
                for index, x in enumerate(al_temp_list[0:30]):
                    allergen_orders[index] = x

            context["unit_cycle"] = unit_cycle
            context["menu_cycle"] = menu_cycle
            context["formset"] = formset
            context["allergen_orders"] = list(allergen_orders)
            context["unit_list"] = unit_list
            context["menu_list"] = menu_list
            context["is_only_meal"] = is_only_meal
            context["two_meal"] = two_meal

            context["ar_unit_list"] = ar_unit_list
            context["ar_meal_list"] = ar_meal_list
            context["ar_menu_list"] = ar_menu_list
            context["allergen_list"] = allergen_list

            search_form = OrderMaintenanceSearchForm(None, initial={'eating_day': eating_day, 'unit_name': unit})

            limit_day = today + relativedelta(days=adjust_days + 1)
            is_disable = limit_day > eating_day.date()
            context['disable_processing'] = is_disable
            if is_disable:
                enable_orders = [x for x in context["allergen_orders"] if x]
                context["allergen_orders"] = enable_orders
        else:
            search_form = OrderMaintenanceSearchForm()
            context['disable_processing'] = True

            # 食数の更新部品は表示刺せない予定だが、念のため
            context['disable_processing'] = True

        context['search_form'] = search_form
        context['adjust_days'] = adjust_days

        return self.render_to_response(context)

    def get_valid_allergen_orders(self, post):
        orders = []
        result = True
        for i in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
            id_value = post.get(f'ar_order_{i}_id', None)
            unit_value = post.get(f'ar_order_{i}_unit', None)
            meal_value = post.get(f'ar_order_{i}_meal', None)
            menu_value = post.get(f'ar_order_{i}_menu', None)
            allergen_value = post.get(f'ar_order_{i}_allergen', None)
            quantity_value = post.get(f'ar_order_{i}_quantity', 0)
            if unit_value and meal_value and menu_value and allergen_value:
                orders.append((id_value, unit_value, meal_value, menu_value, allergen_value, int(quantity_value) if quantity_value else 0))
            elif meal_value or menu_value or allergen_value:
                # いずれかの項目に空がある場合
                result = False
        return (result, orders)

    def get_input_allergen_orders(self, post):
        orders = []
        none_list = []
        for i in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
            id_value = post.get(f'ar_order_{i}_id', None)
            unit_value = post.get(f'ar_order_{i}_unit', None)
            meal_value = post.get(f'ar_order_{i}_meal', None)
            menu_value = post.get(f'ar_order_{i}_menu', None)
            allergen_value = post.get(f'ar_order_{i}_allergen', None)
            quantity_value = post.get(f'ar_order_{i}_quantity', None)
            if id_value:
                order = Order.objects.get(id=id_value)
            else:
                if not(unit_value or meal_value or menu_value or allergen_value or quantity_value):
                    order = None
                else:
                    order = Order()
            if order:
                order.unit_name_id = int(unit_value) if unit_value else None
                order.meal_name_id = int(meal_value) if meal_value else None
                order.menu_name_id = int(menu_value) if menu_value else None
                order.allergen_id = int(allergen_value) if allergen_value else None
                order.quantity = quantity_value
            if order:
                orders.append(order)
            else:
                none_list.append(order)

        orders += none_list
        return orders

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        is_valid_allergen, orders = self.get_valid_allergen_orders(request.POST)
        ar_orders = None
        OrderMaintenanceFormOrderFormSet = modelformset_factory(Order, form=OrderMaintenanceForm, extra=0)
        oid = request.POST['form-0-id']
        base_order = Order.objects.get(id=oid)
        qs = Order.objects.filter(unit_name=base_order.unit_name, eating_day=base_order.eating_day, allergen=1, unit_name__is_active=True)
        formset = OrderMaintenanceFormOrderFormSet(request.POST or None, queryset=qs)
        unit = None
        eating_day = None
        if formset.is_valid() and is_valid_allergen:
            # 通常注文の反映
            formset.save()

            unit = base_order.unit_name
            eating_day = base_order.eating_day

            # アレルギー注文の反映
            for x in orders:
                if x[0]:    # IDがある場合
                    order = Order.objects.get(id=x[0])
                    if x[5]:    # 食数がある場合
                        order.unit_name_id = x[1]
                        order.meal_name_id = x[2]
                        order.menu_name_id = x[3]
                        order.allergen_id = x[4]
                        order.quantity = x[5]
                        order.save()
                    else:
                        order.delete()
                else:
                    Order.objects.create(
                        eating_day=eating_day,
                        unit_name_id=x[1],
                        meal_name_id=x[2],
                        menu_name_id=x[3],
                        allergen_id=x[4],
                        quantity=x[5])
            messages.success(request, '注文を更新しました。')

        context = {
        }
        if unit and eating_day:
            # 対象ユニットの対象喫食日の注文を検索
            # 利用しているユニットを取り出す
            order_qs = Order.objects.filter(unit_name=unit, allergen=1,
                                                      eating_day=eating_day)
            unit_list = order_qs.values_list('unit_name__unit_name', flat=True) \
                .annotate(Count('unit_name')).order_by('unit_name_id')
            unit_cnt = unit_list.count()  # ユニットの数

            # 提供している献立種類（常食・ソフトなど）
            menu_list = order_qs \
                .values_list('menu_name__menu_name', flat=True) \
                .annotate(Count('menu_name')) \
                .order_by('menu_name_id')
            menu_cnt = menu_list.count()  # 献立種類の数
            if eating_day >= dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date():
                menu_list = list(menu_list)
                for i, m in enumerate(menu_list):
                    if m == '常食':
                        menu_list[i] = '基本食'

            # 提供している食事種別（朝食・昼食・夕食など）
            meal_list = order_qs \
                .values_list('meal_name__meal_name', flat=True) \
                .annotate(Count('meal_name')) \
                .order_by('meal_name__seq_order')
            meal_cnt = meal_list.count()  # 食事種別種類の数
            is_only_meal = True if meal_cnt == 1 else False

            # 食事区分が2つの場合の対応
            meals = list(meal_list)
            two_meal = ''
            if len(meals) == 2:
                if ('朝食' in meals) and ('昼食' in meals):
                    two_meal = '朝昼'
                elif ('朝食' in meals) and ('夕食' in meals):
                    two_meal = '朝夕'
                elif ('昼食' in meals) and ('夕食' in meals):
                    two_meal = '昼夕'

            meal_cells = meal_cnt  # 次の行を表示するまでに使う食数入力欄の数
            menu_cells = meal_cells * menu_cnt  # 複数ある献立ごとに行を挿入するための区切りリスト作成時のステップ数に使う
            unit_cells = meal_cells * menu_cnt * unit_cnt  # 全ユニット分の食数入力欄 区切りリスト作成時の最大値に使う

            menu_cycle = []  # 献立が複数あるときは変わるたびに日付行を挿入する用
            for x in range(0, unit_cells, meal_cells):
                menu_cycle.append(x)

            unit_cycle = []  # ユニットが複数あるときに献立が変わるたびに空行と日付行を挿入する用
            for y in range(0, unit_cells, menu_cells):
                unit_cycle.append(y)

            qs = Order.objects.filter(unit_name=unit, allergen=1, eating_day=eating_day, unit_name__is_active=True)
            qs_count = qs.count()
            OrderFormSet = modelformset_factory(Order, form=OrderMaintenanceForm, extra=0)
            formset = OrderFormSet(None, queryset=qs)

            # アレルギー注文画面用の選択肢
            ar_unit_list = UnitMaster.objects.filter(unit_name=unit)
            ar_meal_list = MealDisplay.objects.filter(username=unit.username).order_by('meal_name__seq_order')
            ar_menu_list = MenuDisplay.objects.filter(
                username=unit.username).exclude(menu_name__menu_name='薄味').order_by('menu_name__seq_order')
            allergen_list = AllergenDisplay.objects.filter(username=unit.username)

            allergen_orders = []
            if allergen_list.exists():
                for x in range(settings.NEW_YEAR_ALLERGEN_MAX_ROWS):
                    allergen_orders.append(None)

                qs2 = Order.objects.filter(unit_name=unit, eating_day=eating_day, quantity__gt=0,
                                           allergen__gt=1, unit_name__is_active=True) \
                    .order_by('meal_name__seq_order', 'menu_name')
                al_temp_list = list(qs2)
                for index, x in enumerate(al_temp_list[0:30]):
                    allergen_orders[index] = x

            context["unit_cycle"] = unit_cycle
            context["menu_cycle"] = menu_cycle
            context["formset"] = formset
            context["allergen_orders"] = list(allergen_orders)
            context["unit_list"] = unit_list
            context["menu_list"] = menu_list
            context["is_only_meal"] = is_only_meal
            context["two_meal"] = two_meal

            context["ar_unit_list"] = ar_unit_list
            context["ar_meal_list"] = ar_meal_list
            context["ar_menu_list"] = ar_menu_list
            context["allergen_list"] = allergen_list

            search_form = OrderMaintenanceSearchForm(None, initial={'eating_day': eating_day, 'unit_name': unit})
        else:
            search_form = OrderMaintenanceSearchForm()
        context['search_form'] = search_form

        return self.render_to_response(context)


# アレルギーの注文 ------------------------------------------------------
def order_allergen(request):
    # dt_str = '2022-04-30 14:00:00'  # 検証用に適当な日時を指定している
    # date_time_now = dt.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

    date_time_now = dt.datetime.now()  # 現在の日時と時刻

    try:
        res = get_order_change_dates(date_time_now)
    except NotChangeOrderError as e:
        res = (e.next_from, e.next_from + timedelta(days=6))

    from_date = res[0]
    to_date = res[1]

    # モデルフォームセットの作成・userカラムは非表示に
    AllergenFormSet = modelformset_factory(Order, form=AllergenForm, extra=7, can_delete=True)

    # 注文DBからアレルギーなしのレコードは除外し、ログインユーザーのレコードのみ表示する
    # qs = Order.objects.filter(user=request.user, eating_day__range=[from_date, to_date]).exclude(allergen=1)
    qs = Order.objects.none()
    formset = AllergenFormSet(
        request.POST or None, queryset=qs, form_kwargs={'user': request.user, 'from_date': from_date})

    # 対象施設の変更予定を取得する
    # 1つの施設で設定する予定の期日は、1種類のみとする
    reserved_meal_list = ReservedMealDisplay.objects.filter(username=request.user, disable_date__gt=from_date)
    if reserved_meal_list.exists():
        change_date = reserved_meal_list.first().disable_date
        raw_meal_list = MealDisplay.objects.filter(username=request.user).order_by('meal_name__seq_order')
    else:
        change_date = None
        raw_meal_list = []

    if request.method == "POST":

        if formset.is_valid():
            # バリデーションされたデータを一時保存
            instances = formset.save(commit=False)

            # 削除チェックがついたentryを取り出して削除
            for entry in formset.deleted_objects:
                entry.delete()

            # 新たに作成されたentryと更新されたentryを取り出し、ユーザーを紐づけて保存
            for entry in instances:
                entry.user = request.user
                entry.save()

            # 全フォームセットを最終保存
            formset.save()
            messages.success(request, '登録しました。')
            return redirect("web_order:order_allergen_list")

        else:
            # バリデーション失敗した場合
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "formset": formset,
                "from_date": from_date,
                "change_date": change_date,
                "reserved_meal_list": reserved_meal_list,
                "raw_meal_list": raw_meal_list,
                "count": len(formset.forms),
            }

    else:
        context = {
            "formset": formset,
            "from_date": from_date,
            "to_date": to_date,
            "change_date": change_date,
            "reserved_meal_list": reserved_meal_list,
            "raw_meal_list": raw_meal_list,
            "count": len(formset.forms),
        }

    return render(request, template_name="order_allergen.html", context=context)


def order_allergen_list(request):
    # dt_str = '2022-04-30 14:00:00'  # 検証用に適当な日時を指定している
    # date_time_now = dt.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

    date_time_now = dt.datetime.now()  # 現在の日時と時刻

    try:
        res = get_order_change_dates(date_time_now)
    except NotChangeOrderError as e:
        res = (e.next_from, e.next_from + timedelta(days=6))

    from_date = res[0]
    to_date = res[1]

    # モデルフォームセットの作成・userカラムは非表示に
    AllergenFormSet = modelformset_factory(Order, form=AllergenForm, extra=0, can_delete=True)

    # 食数が0として削除したレコードは表示させないように変更

    # 注文DBからアレルギーなしのレコードは除外し、ログインユーザーのレコードのみ表示する
    new_year_day = dt.datetime(date_time_now.year + 1, 1, 1).date()
    qs = Order.objects.filter(unit_name__username=request.user, eating_day__gte=from_date, quantity__gt=0) \
        .exclude(allergen=1) \
        .exclude(eating_day=new_year_day) \
        .order_by('eating_day', 'meal_name__seq_order', 'menu_name')

    formset = AllergenFormSet(
        request.POST or None, queryset=qs, form_kwargs={'user': request.user, 'from_date': from_date})
    meal_select = [x.meal_name_id for x in qs]

    # 対象施設の変更予定を取得する
    # 1つの施設で設定する予定の期日は、1種類のみとする
    reserved_meal_list = ReservedMealDisplay.objects.filter(username=request.user, disable_date__gt=from_date)
    if reserved_meal_list.exists():
        change_date = reserved_meal_list.first().disable_date
        raw_meal_list = MealDisplay.objects.filter(username=request.user).order_by('meal_name__seq_order')
    else:
        change_date = None
        raw_meal_list = []

    if request.method == "POST":

        if formset.is_valid():
            # バリデーションされたデータを一時保存
            instances = formset.save(commit=False)

            # 削除チェックがついたentryを取り出して削除
            for entry in formset.deleted_objects:
                entry.delete()

            # 新たに作成されたentryと更新されたentryを取り出し、ユーザーを紐づけて保存
            for entry in instances:
                entry.user = request.user
                entry.save()

            # 全フォームセットを最終保存
            formset.save()
            messages.success(request, '登録しました。')
            return redirect("web_order:order_allergen_list")

        else:
            # バリデーション失敗した場合
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "formset": formset,
                "from_date": from_date,
                "change_date": change_date,
                "reserved_meal_list": reserved_meal_list,
                "raw_meal_list": raw_meal_list,
                "count": len(formset.forms),
                "meal_select": meal_select,
            }

    else:
        context = {
            "formset": formset,
            "from_date": from_date,
            "to_date": to_date,
            "change_date": change_date,
            "reserved_meal_list": reserved_meal_list,
            "raw_meal_list": raw_meal_list,
            "count": len(formset.forms),
            "meal_select": meal_select,
        }

    return render(request, template_name="order_allergen.html", context=context)

# 未使用
class OrderAllergenList(ListView):
    template_name = 'order_allergen_list.html'
    model = Order

    def get_queryset(self):
        qs = Order.objects.filter(unit_name__username_id=self.request.user, quantity__gt=0).exclude(allergen=1) \
            .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
            .order_by('eating_day', 'meal_name_id')
        return qs


class OrderAllergenUpdate(UpdateView):
    model = Order
    template_name = 'order_allergen_update.html'
    form_class = AllergenForm

    def get_form_kwargs(self):
        kwargs = super(OrderAllergenUpdate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('web_order:order_allergen_list')

    def form_valid(self, form):
        messages.success(self.request, '登録しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)


def _is_over_order_change_limit(target_day, limit_day, now_hour):
    """
    食数変更締め切りを超えたかどうかを判断。
    締め切り日当日の17以降は締め切り外と判定する。
    """
    if target_day > limit_day:
        return True
    if target_day == limit_day:
        if now_hour >= 17:
            return True
    return False


# 混ぜご飯の注文 -------------------------------------------------------
def order_rice(request):
    logger.info('合数入力ビュー処理開始')
    date_time_now = dt.datetime.now()  # 現在の日時と時刻

    try:
        res = get_order_change_dates(date_time_now)
    except NotChangeOrderError as e:
        res = (e.next_from + timedelta(days=14), e.next_from + timedelta(days=21))

    from_date, to_date = res

    from_view_date = from_date - timedelta(days=14)

    # モデルフォームセットの作成・userカラムは非表示に
    OrderRiceFormSet = modelformset_factory(OrderRice, form=OrderRiceForm, extra=4, can_delete=True)

    # 合数指定DBからログインユーザーのレコードのみ表示する
    qs = OrderRice.objects.filter(unit_name__username=request.user, eating_day__gte=from_view_date).order_by('eating_day')
    # qs = OrderRice.objects.none()
    formset = OrderRiceFormSet(request.POST or None, queryset=qs, form_kwargs={'user': request.user, 'from_date': from_date})
    id_list = [x.id for x in OrderRice.objects.filter(unit_name__username=request.user, eating_day__gte=from_view_date).order_by('eating_day')]
    logger.info(f'【{request.method}】User={request.user.facility_name}({request.user.username})/')
    logger.info(id_list)

    if request.method == "POST":

        if formset.is_valid():
            check_list = []
            for form in formset:
                if form.instance.eating_day and form.instance.unit_name:
                    check_list.append((form.cleaned_data['eating_day'], form.cleaned_data['unit_name'].id))

            for value in check_list:
                if not value[0]:
                    continue

                count = 0
                eating_day_1, unit_1 = value
                for value2 in check_list:
                    eating_day_2, unit_2 = value2
                    if (eating_day_1 == eating_day_2) and (unit_1 == unit_2):
                        count += 1

                if count >= 2:
                    messages.error(request, '同一喫食日・同一ユニットは1件のみ入力してください。')
                    context = {
                        "formset": formset,
                        "from_date": from_date,
                    }
                    return render(request, template_name="order_rice.html", context=context)

            # バリデーションされたデータを一時保存
            instances = formset.save(commit=False)

            # 不正な日付を直接入力した場合の対応
            for entry in instances:
                if entry.eating_day:
                    if entry.eating_day < from_date:
                        context = {
                            "error_message": '入力内容に不備がありますのでご確認ください',
                            "formset": formset,
                            "from_date": from_date,
                        }
                        return render(request, template_name="order_rice.html", context=context)

                    before = OrderRice.objects.filter(id=entry.id).first()
                    if before:
                        if (before.quantity != entry.quantity) or (before.eating_day != entry.eating_day):
                            target_eating_day = date_time_now.date()
                            unit = entry.unit_name
                            if UserOption.objects.filter(username=unit.username, unlock_limitation=True).exists():
                                target_eating_day -= relativedelta(days=7)

                            enable_holiday_list = HolidayList.objects.filter(start_date__lte=entry.eating_day,
                                                                             end_date__gte=entry.eating_day).first()
                            if enable_holiday_list and _is_over_order_change_limit(target_eating_day, enable_holiday_list.limit_day,
                                                                                   date_time_now.hour):
                                # 入力の喫食日が長期休暇で食数変更不可の場合
                                messages.error(request, f'運送便の長期休暇による仕入れの都合により、{entry.eating_day.strftime("%m月%d日")}の合数変更は行えません。')
                                context = {
                                    "formset": formset,
                                    "from_date": from_date,
                                }
                                logger.info('合数変更不可')
                                return render(request, template_name="order_rice.html", context=context)
                    else:
                        target_eating_day = date_time_now.date()
                        unit = entry.unit_name
                        if UserOption.objects.filter(username=unit.username, unlock_limitation=True).exists():
                            target_eating_day -= relativedelta(days=7)

                        enable_holiday_list = HolidayList.objects.filter(start_date__lte=entry.eating_day,
                                                                         end_date__gte=entry.eating_day).first()
                        if enable_holiday_list and _is_over_order_change_limit(target_eating_day, enable_holiday_list.limit_day,
                                                                               date_time_now.hour):
                            # 入力の喫食日が長期休暇で食数変更不可の場合
                            messages.error(request, f'運送便の長期休暇による仕入れの都合により、{entry.eating_day.strftime("%m月%d日")}の合数変更は行えません。')
                            context = {
                                "formset": formset,
                                "from_date": from_date,
                            }
                            logger.info('合数変更不可')
                            return render(request, template_name="order_rice.html", context=context)


            # 削除チェックがついたentryを取り出して削除
            for entry in formset.deleted_objects:
                entry.delete()

            # 新たに作成されたentryと更新されたentryを取り出し、ユーザーを紐づけて保存
            delete_list = []
            for entry in instances:
                if entry.eating_day:
                    rice_entry, is_create = OrderRice.objects.get_or_create(eating_day=entry.eating_day, unit_name=entry.unit_name)
                    if is_create:
                        if entry.id:
                            # 更新先が存在しない場合は、既存の情報を更新
                            entry.user = request.user
                            entry.save()

                            rice_entry.delete()
                        else:
                            # 更新先が存在しない、新規データはそのまま登録
                            rice_entry.quantity = entry.quantity
                            rice_entry.user = request.user
                            rice_entry.save()
                    else:
                        rice_entry.quantity = entry.quantity
                        rice_entry.user = request.user
                        rice_entry.save()

                        for enum_index, e in enumerate(delete_list):
                            if e.id == rice_entry.id:
                                delete_list.pop(enum_index)
                        if entry.id:
                            # 更新先が存在する場合は、既存の情報を削除して、上書き
                            delete_list.append(entry)
                        else:
                            # 更新先が存在する場合、新規データは無視して更新に使う
                            pass
                else:
                    delete_list.append(entry)

            for entry in delete_list:
                entry.delete()
            messages.success(request, '登録しました。')
            return redirect("web_order:order_rice")

        else:
            # バリデーション失敗した場合
            errors = formset.errors
            lost_messages = [x for x in errors if ('id' in x) and ('選択したものは候補にありません' in x['id'][0])]
            if lost_messages:
                context = {
                    "error_message": '更新対象のデータが、他の画面から削除されています。メニュー「混ぜご飯の合数指定」をクリックして、画面を再表示してください。',
                    "formset": formset,
                    "from_date": from_date,
                }
            else:
                context = {
                    "error_message": '入力内容に不備がありますのでご確認ください',
                    "formset": formset,
                    "from_date": from_date,
                }
    else:
        context = {
            "formset": formset,
            "from_date": from_date,
        }

    return render(request, template_name="order_rice.html", context=context)


def get_all_units(request):
    qs = UnitMaster.objects.filter(username__company_name=request.user.company_name)
    return list(qs)


def generate_sales_date(qs, exception_masters):
    for order in qs:
        unit_em = [x for x in exception_masters if x.unit_name_id == order.unit_name_id]
        if unit_em:
            unit_em_first = unit_em[0]
            solid_day = SalesDayUtil.get_by_eating_day_by_settings(order.eating_day)
            week_day = solid_day.weekday()
            if week_day == 4:
                # 金曜日の場合
                if unit_em_first.is_far:
                    sales_date = solid_day + relativedelta(days=-1)
                    yield order, sales_date
                else:
                    sales_date = solid_day
                    yield order, sales_date
            elif week_day == 5:
                # 土曜日の場合
                sales_date = solid_day + relativedelta(days=unit_em_first.ng_saturday)
                yield order, sales_date
            elif week_day == 6:
                # 日曜日の場合
                sales_date = solid_day + relativedelta(days=unit_em_first.ng_sunday)
                yield order, sales_date
            elif unit_em_first.reduced_rate:
                # 業務委託の場合は、喫食日=売上日とする
                yield order, order.eating_day
            else:
                sales_date = solid_day
                yield order, sales_date
        else:
            sales_date = SalesDayUtil.get_by_eating_day_by_settings(order.eating_day)
            yield order, sales_date


# すべての注文データの表示 ------------------------------------------------
def order_list(request):

    if request.user.is_parent:
        form = OrderListSalesForm(request.POST)
    else:
        form = OrderListForm(request.POST)

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻
    enable_date = dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date()

    if request.method == "POST":

        if form.is_valid():

            in_date = form.cleaned_data['in_date']
            if request.user.is_parent:
                out_date = form.cleaned_data['out_date']

            if 'this' in request.GET:
                from_date = get_first_date(date_time_now)  # 今月の初日
                to_date = get_last_date(date_time_now)  # 今月の最終日

            elif 'prev' in request.GET:
                this_month = request.GET.get('prev')
                this_month = dt.datetime.strptime(this_month, '%Y%m%d')
                prev_month = this_month - relativedelta(months=1)
                prev_month = prev_month.date()
                from_date = get_first_date(prev_month)  # 今月の初日
                to_date = get_last_date(prev_month)  # 今月の最終日

            elif 'next' in request.GET:
                this_month = request.GET.get('next')
                this_month = dt.datetime.strptime(this_month, '%Y%m%d')
                next_month = this_month + relativedelta(months=1)
                next_month = next_month.date()
                from_date = get_first_date(next_month)  # 今月の初日
                to_date = get_last_date(next_month)  # 今月の最終日
            else:
                from_date = get_first_date(date_time_now)  # 今月の初日
                to_date = get_last_date(date_time_now)  # 今月の最終日

            if request.user.is_parent:
                # 余裕を持って取得
                delta = relativedelta(days=5)
                tmp_from_date = from_date - delta
                tmp_to_date = to_date + delta
                if in_date:
                    tmp_in_date = in_date - delta
                    if not out_date:
                        tmp_out_date = tmp_in_date + relativedelta(months=3)
                        alter_out_date = in_date + relativedelta(months=3)
                if out_date:
                    tmp_out_date = out_date + delta
                    if not in_date:
                        tmp_in_date = tmp_out_date - relativedelta(months=3)
                        alter_in_date = out_date - relativedelta(months=3)

                # 請求書確認用親会社でログインの場合
                unit_list = get_all_units(request)
            else:
                unit_list = []

            # 合計金額(親会社ログインでのみ使用)
            total_sales = 0

            if request.user.is_parent:
                # 親会社でログインの場合

                unit_id_list = [x.id for x in unit_list]
                if in_date or out_date:
                    # 日付の指定がある場合
                    qs = Order.objects.filter(unit_name_id__in=unit_id_list, quantity__gt=0,
                                              eating_day__range=[tmp_in_date, tmp_out_date]) \
                        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                        .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order',
                                  'allergen__seq_order')
                    exception_masters = InvoiceException.objects.filter(unit_name_id__in=unit_id_list)

                    # 売上日の情報を抽出
                    i_date = in_date if in_date else alter_in_date
                    o_date = out_date if out_date else alter_out_date
                    order_list = [x for x in generate_sales_date(qs, exception_masters) if
                                  (x[1] >= i_date) and (x[1] <= o_date)]

                    # CSV出力用の日時指定
                    d_dict = dict(in_date=i_date, out_date=o_date)
                    csv_form = OrderListCsvForm(None, initial=d_dict)
                else:
                    # 日付の直接指定がない場合(前月、今月、翌月はこちら)
                    qs = Order.objects.filter(unit_name_id__in=unit_id_list, quantity__gt=0,
                                              eating_day__range=[tmp_from_date, tmp_to_date]) \
                        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                        .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order', 'allergen__seq_order')
                    exception_masters = InvoiceException.objects.filter(unit_name_id__in=unit_id_list)

                    # 売上日の情報を抽出
                    order_list = [x for x in generate_sales_date(qs, exception_masters) if
                                  (x[1] >= from_date) and (x[1] <= to_date)]

                    # CSV出力用の日時指定
                    d_dict = dict(in_date=from_date, out_date=to_date)
                    csv_form = OrderListCsvForm(None, initial=d_dict)

                # 単価情報の取得
                user_list = [x[0] for x in
                             UnitMaster.objects.filter(id__in=unit_id_list).distinct().values_list('username')]
                qs2 = MenuDisplay.objects.filter(username__in=user_list)
                object_list = []
                sales_dict = {}
                num_dict = {}
                for order, sales_day in order_list:
                    menu_display = qs2.filter(username=order.unit_name.username, menu_name=order.menu_name).first()
                    if menu_display:
                        new_price = NewUnitPrice.objects.filter(
                            username=order.unit_name.username, menu_name=order.menu_name.menu_name,
                            eating_day__lte=sales_day).order_by('eating_day').first()
                        disp_dict = {'order': order, 'sales_day': sales_day}
                        if order.meal_name.meal_name == '朝食':
                            if new_price:
                                disp_dict['price'] = new_price.price_breakfast
                            else:
                                disp_dict['price'] = menu_display.price_breakfast
                        elif order.meal_name.meal_name == '昼食':
                            if new_price:
                                disp_dict['price'] = new_price.price_lunch
                            else:
                                disp_dict['price'] = menu_display.price_lunch
                        elif order.meal_name.meal_name == '夕食':
                            if new_price:
                                disp_dict['price'] = new_price.price_dinner
                            else:
                                disp_dict['price'] = menu_display.price_dinner
                        disp_dict['sales'] = disp_dict['price'] * order.quantity
                        total_sales += disp_dict['sales']
                        if disp_dict['sales_day'] in sales_dict:
                            tpl = sales_dict[disp_dict['sales_day']]
                            new_tpl = (disp_dict['sales'] + tpl[0], order.quantity + tpl[1])
                            sales_dict[disp_dict['sales_day']] = new_tpl
                        else:
                            sales_dict[disp_dict['sales_day']] = (disp_dict['sales'], order.quantity)
                        object_list.append(disp_dict)

                unit_name_list = [(x.id, x.unit_name) for x in unit_list]
            else:
                # 通常の施設でログインの場合
                if in_date:
                    # 日付の指定がある場合
                    qs = Order.objects.filter(unit_name__username_id=request.user, quantity__gt=0, eating_day=in_date) \
                        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                        .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order', 'allergen__seq_order')
                    unit_name_list = []
                else:
                    qs = Order.objects.filter(unit_name__username_id=request.user, quantity__gt=0,
                                              eating_day__range=[from_date, to_date]) \
                        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                        .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order', 'allergen__seq_order')
                    unit_name_list = []

                # CSV出力用の日時指定(通常施設では出力しないので、空出力
                csv_form = OrderListCsvForm()
                sales_dict = {}
                num_dict = {}

            # 常食->基本食置き換え
            if request.user.is_parent:
                for disp_dict in object_list:
                    order = disp_dict['order']
                    if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
                        order.menu_name.menu_name = '基本食'
            else:
                object_list = list(qs)
                for order in object_list:
                    if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
                        order.menu_name.menu_name = '基本食'

            context = {
                "object_list": object_list,
                "unit_list": unit_name_list,
                "form": form,
                "csv_form": csv_form,
                "from_date": from_date,
                "sales_dict": sales_dict,
                "num_dict": sales_dict,
                "total_sales": total_sales
            }

        else:
            # バリデーション失敗した場合
            messages.warning(request, '入力内容に不備がありますのでご確認ください')
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "form": form,
                "csv_form": csv_form,
            }

    else:
        from_date = get_first_date(date_time_now)  # 今月の初日
        to_date = get_last_date(date_time_now)  # 今月の最終日

        if request.user.is_parent:
            # 余裕を持って取得
            delta = relativedelta(days=5)
            tmp_from_date = from_date - delta
            tmp_to_date = to_date + delta

            # 請求書確認用親会社でログインの場合
            unit_list = get_all_units(request)
        else:
            unit_list = []

        total_sales = 0
        if request.user.is_parent:
            # 親会社でログインの場合

            unit_id_list = [x.id for x in unit_list]

            # 日付の直接指定がない場合(前月、今月、翌月はこちら)
            qs = Order.objects.filter(unit_name_id__in=unit_id_list, quantity__gt=0,
                                      eating_day__range=[tmp_from_date, tmp_to_date]) \
                .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order', 'allergen__seq_order')
            exception_masters = InvoiceException.objects.filter(unit_name_id__in=unit_id_list)

            # 売上日の情報を抽出
            order_list = [x for x in generate_sales_date(qs, exception_masters) if
                          (x[1] >= from_date) and (x[1] <= to_date)]

            # CSV出力用の日時指定
            d_dict = dict(in_date=from_date, out_date=to_date)
            csv_form = OrderListCsvForm(None, initial=d_dict)

            # 単価情報の取得
            user_list = [x[0] for x in
                         UnitMaster.objects.filter(id__in=unit_id_list).distinct().values_list('username')]
            qs2 = MenuDisplay.objects.filter(username__in=user_list)
            object_list = []
            sales_dict = {}
            num_dict = {}
            for order, sales_day in order_list:
                menu_display = qs2.filter(username=order.unit_name.username, menu_name=order.menu_name).first()
                if menu_display:
                    disp_dict = {'order': order, 'sales_day': sales_day}
                    if order.meal_name.meal_name == '朝食':
                        disp_dict['price'] = menu_display.price_breakfast
                    elif order.meal_name.meal_name == '昼食':
                        disp_dict['price'] = menu_display.price_lunch
                    elif order.meal_name.meal_name == '夕食':
                        disp_dict['price'] = menu_display.price_dinner
                    disp_dict['sales'] = disp_dict['price'] * order.quantity
                    total_sales += disp_dict['sales']
                    if disp_dict['sales_day'] in sales_dict:
                        tpl = sales_dict[disp_dict['sales_day']]
                        new_tpl = (disp_dict['sales'] + tpl[0], order.quantity + tpl[1])
                        sales_dict[disp_dict['sales_day']] = new_tpl
                    else:
                        sales_dict[disp_dict['sales_day']] = (disp_dict['sales'], order.quantity)
                    object_list.append(disp_dict)

            unit_name_list = [(x.id, x.unit_name) for x in unit_list]
        else:
            qs = Order.objects.filter(unit_name__username_id=request.user, quantity__gt=0,
                                      eating_day__range=[from_date, to_date]) \
                .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
                .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order', 'allergen__seq_order')

            # CSV出力用の日時指定(通常施設では出力しないので、空出力
            csv_form = OrderListCsvForm()

            total_sales = 0
            unit_name_list = []
            sales_dict = {}
            num_dict = {}

        # 常食->基本食置き換え
        if request.user.is_parent:
            for disp_dict in object_list:
                order = disp_dict['order']
                if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
                    order.menu_name.menu_name = '基本食'
        else:
            object_list = list(qs)
            for order in object_list:
                if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
                    order.menu_name.menu_name = '基本食'

        context = {
            "object_list": object_list,
            "unit_list": unit_name_list,
            "form": form,
            "csv_form": csv_form,
            "from_date": from_date,
            "sales_dict": sales_dict,
            "num_dict": sales_dict,
            "total_sales": total_sales
        }

    return render(request, template_name="order_list.html", context=context)


def order_list_csv(request):
    if not request.user.is_parent:
        return HttpResponse('このページは表示できません', status=500)

    unit_id = request.GET.get('unit_id', None)
    # 入力値
    in_date = dt.datetime.strptime(request.GET['in_date'], '%Y-%m-%d').date()
    out_date = dt.datetime.strptime(request.GET['out_date'], '%Y-%m-%d').date()

    tmp_in_date = in_date - relativedelta(days=5)
    tmp_out_date = out_date + relativedelta(days=5)

    # 請求書確認用親会社でログインの場合
    if unit_id:
        unit_id_list = [unit_id]
    else:
        unit_list = get_all_units(request)
        unit_id_list = [x.id for x in unit_list]

    qs = Order.objects.filter(unit_name_id__in=unit_id_list, quantity__gt=0,
                          eating_day__range=[tmp_in_date, tmp_out_date]) \
        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
        .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order',
                  'allergen__seq_order')
    exception_masters = InvoiceException.objects.filter(unit_name_id__in=unit_id_list)

    # 売上日の情報を抽出
    order_list = [x for x in generate_sales_date(qs, exception_masters) if
                  (x[1] >= in_date) and (x[1] <= out_date)]

    # 単価情報の取得
    user_list = [x[0] for x in
                 UnitMaster.objects.filter(id__in=unit_id_list).distinct().values_list('username')]
    qs2 = MenuDisplay.objects.filter(username__in=user_list)
    object_list = []
    for order, sales_day in order_list:
        menu_display = qs2.filter(username=order.unit_name.username, menu_name=order.menu_name).first()
        if menu_display:
            disp_dict = {'order': order, 'sales_day': sales_day}
            if order.meal_name.meal_name == '朝食':
                disp_dict['price'] = menu_display.price_breakfast
            elif order.meal_name.meal_name == '昼食':
                disp_dict['price'] = menu_display.price_lunch
            elif order.meal_name.meal_name == '夕食':
                disp_dict['price'] = menu_display.price_dinner
            disp_dict['sales'] = disp_dict['price'] * order.quantity
            object_list.append(disp_dict)

    # 常食->基本食置換
    enable_date = dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date()
    for dict in object_list:
        order = dict['order']
        if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
            order.menu_name.menu_name = '基本食'

    # Dataframeの作成
    df_data_list = []
    for dict in object_list:
        order = dict['order']
        data_list = [
            order.unit_name, dict['sales_day'], order.eating_day, order.meal_name, order.menu_name, order.allergen,
            order.quantity, dict['price'], dict['sales']
        ]
        df_data_list.append(data_list)
    column_list = [
        'ユニット名','売上日','喫食日','食事区分','献立種類','アレルギー', '数量', '単価','金額'
    ]
    df = pd.DataFrame(data=df_data_list, columns=column_list)
    new_dir_path = os.path.join(settings.OUTPUT_DIR, 'orders_csv')
    os.makedirs(new_dir_path, exist_ok=True)

    filename = f"{request.user.username}_{request.user.company_name}様_注文データ.csv"
    path = os.path.join(new_dir_path, filename)

    df.to_csv(path, index=False, encoding='cp932')
    return FileResponse(
        open(path, 'rb'), as_attachment=True, filename=filename)


# すべての注文データの表示 ------------------------------------------------
def order_unit(request):
    if not request.user.is_parent:
        return HttpResponse('このページは表示できません', status=500)

    form = OrderListSalesForm(request.GET)

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻
    enable_date = dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date()

    if request.method == "GET":

        # 入力値
        in_date = dt.datetime.strptime(request.GET['in_date'], '%Y-%m-%d').date()
        out_date = dt.datetime.strptime(request.GET['out_date'], '%Y-%m-%d').date()

        tmp_in_date = in_date - relativedelta(days=5)
        tmp_out_date = out_date + relativedelta(days=5)

        # 請求書確認用親会社でログインの場合
        unit_id = int(request.GET.get('unit', '0'))
        if unit_id:
            unit_id_list = [unit_id]
        else:
            unit_list = get_all_units(request)
            unit_id_list = [x.id for x in unit_list]

        # 合計金額(親会社ログインでのみ使用)
        total_sales = 0

        # 日付の指定がある場合
        qs = Order.objects.filter(unit_name_id__in=unit_id_list, quantity__gt=0,
                                  eating_day__range=[tmp_in_date, tmp_out_date]) \
            .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
            .order_by('eating_day', 'meal_name__seq_order', 'menu_name__seq_order',
                      'allergen__seq_order')
        exception_masters = InvoiceException.objects.filter(unit_name_id__in=unit_id_list)

        # 売上日の情報を抽出
        i_date = in_date if in_date else alter_in_date
        o_date = out_date if out_date else alter_out_date
        order_list = [x for x in generate_sales_date(qs, exception_masters) if
                      (x[1] >= i_date) and (x[1] <= o_date)]
        d_dict = dict(in_date=i_date, out_date=o_date)
        csv_form = OrderListCsvForm(None, initial=d_dict)

        # 単価情報の取得
        user_list = [x[0] for x in
                     UnitMaster.objects.filter(id__in=unit_id_list).distinct().values_list('username')]
        qs2 = MenuDisplay.objects.filter(username__in=user_list)
        object_list = []
        sales_dict = {}
        num_dict = {}
        for order, sales_day in order_list:
            menu_display = qs2.filter(menu_name=order.menu_name).first()
            if menu_display:
                disp_dict = {'order': order, 'sales_day': sales_day}
                if order.meal_name.meal_name == '朝食':
                    disp_dict['price'] = menu_display.price_breakfast
                elif order.meal_name.meal_name == '昼食':
                    disp_dict['price'] = menu_display.price_lunch
                elif order.meal_name.meal_name == '夕食':
                    disp_dict['price'] = menu_display.price_dinner
                disp_dict['sales'] = disp_dict['price'] * order.quantity
                total_sales += disp_dict['sales']
                if disp_dict['sales_day'] in sales_dict:
                    tpl = sales_dict[disp_dict['sales_day']]
                    new_tpl = (disp_dict['sales'] + tpl[0], order.quantity + tpl[1])
                    sales_dict[disp_dict['sales_day']] = new_tpl
                else:
                    sales_dict[disp_dict['sales_day']] = (disp_dict['sales'], order.quantity)
                object_list.append(disp_dict)

        unit_list = get_all_units(request)
        unit_name_list = [(x.id, x.unit_name) for x in unit_list]

        # 常食->基本食置き換え
        for disp_dict in object_list:
            order = disp_dict['order']
            if (order.eating_day >= enable_date) and (order.menu_name.menu_name == '常食'):
                order.menu_name.menu_name = '基本食'

        context = {
            "object_list": object_list,
            "unit_list": unit_name_list,
            "form": form,
            "csv_form": csv_form,
            "from_date": in_date,
            "sales_dict": sales_dict,
            "num_dict": sales_dict,
            "total_sales": total_sales
        }
        if unit_id:
            context["unit_id"] = unit_id

    return render(request, template_name="order_list.html", context=context)


# お知らせの作成 -------------------------------------------------------
class CommunicationCreate(CreateView):
    model = Communication
    template_name = 'communication.html'
    form_class = CommunicationForm
    success_url = reverse_lazy('web_order:communication_list')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)


# お知らせの一覧表示
class CommunicationList(ListView):
    model = Communication
    template_name = 'communication_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = Communication.objects.all().order_by('-updated_at')
        return qs


# お知らせの詳細表示
class CommunicationDetail(DetailView):
    template_name = "communication_detail.html"
    model = Communication

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        output_object = context['object']
        if output_object.document_file:
            # 添付ファイルがある場合、参照URLの設定
            file = output_object.document_file
            file_name = os.path.basename(file.path)
            file_url = os.path.join(settings.MEDIA_URL, file.url)
            context['file_name'] = file_name
            context['file_url'] = file_url

        return context


# お知らせの更新
class CommunicationUpdate(UpdateView):
    model = Communication
    template_name = 'communication_update.html'
    form_class = CommunicationForm

    def get_success_url(self):
        return reverse_lazy('web_order:communication_list')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        output_object = context['object']

        today = dt.datetime.today().date()
        diff = today - output_object.created_at.date()
        context['is_enable_delete'] = diff.days <= settings.NEW_COMMUNICATION_DAYS

        return context


# お知らせの削除
class CommunicationDelete(DeleteView):
    model = Communication
    success_url = reverse_lazy('web_order:communication_list')


# 調理表を変換 ---------------------------------------------
def convert_cooking_direction(request):
    if request.method == 'POST':
        form = ConvertCookingDirectionForm(request.POST, request.FILES)
        filename = str(request.FILES['document_file'])
        if form.is_valid():
            form.save()
            direction_type = form.cleaned_data['type']
            call_command('convert_cooking_direction', filename, type=direction_type)

            messages.success(request, '調理表の変換が完了しました')
            redirect_url = reverse('web_order:converted_cooking_files')
            parameters = urlencode(dict(direction_type=direction_type))
            return redirect(f'{redirect_url}?{parameters}')
        else:
            messages.warning(request, '拡張子「.xlsx」のファイルを選択してください。')
            return redirect('web_order:control_panel')
    else:
        form = CreateMeasureTableForm()
    return render(request, 'paper_documents.html', {'form': form})


# 調理表を登録し、計量表を出力 ---------------------------------------------
def create_measure_table(request):
    if request.method == 'POST':
        form = CreateMeasureTableForm(request.POST, request.FILES)
        filename = str(request.FILES['document_file'])
        if form.is_valid():
            form.save()
            command_errors = call_command('cooking_direction', filename)

            error_sp = command_errors.split(",") if command_errors else []
            if error_sp:
                message = "以下の調理表出力に失敗しました。"
                messages.warning(request, message)
                for error in error_sp:
                    messages.warning(request, f'・{error}')
            else:
                messages.success(request, '計量表の出力が完了しました')
            return redirect('web_order:control_panel')
    else:
        form = CreateMeasureTableForm()
    return render(request, 'paper_documents.html', {'form': form})


# 月間献立表を登録し、料理名をDBに追加 --------------------------------------
def register_monthly_menu(request):
    if request.method == 'POST':
        form = RegisterMonthlyMenuForm(request.POST, request.FILES)
        filename = str(request.FILES['document_file'])
        if form.is_valid():
            form.save()
            call_command('monthly_menu', filename)
            messages.success(request, '月間献立表のアップロードが完了しました。')
            return redirect('web_order:control_panel')
    else:
        form = RegisterMonthlyMenuForm()
    return render(request, 'paper_documents.html', {'form': form})


# 料理写真の一覧表示 ----------------------------------------------------
class FoodPhotoList(ListView):
    model = FoodPhoto
    template_name = 'food_photo_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = FoodPhoto.objects.all().order_by('id')
        keyword = self.request.GET.get('kw')
        # AND検索
        if keyword:
            # キーワードを区切っている全角スペースを半角スペースに変換
            exclusion = set([' ', '　'])
            q_list = ''
            for i in keyword:
                if i in exclusion:
                    pass
                else:
                    q_list += i
            query = reduce(
                and_, [Q(food_name__icontains=q) | Q(direction__icontains=q) for q in q_list]
            )
            qs = qs.filter(query)

        return qs

# 料理写真のデータを更新
class FoodPhotoUpdate(UpdateView):
    model = FoodPhoto
    template_name = 'food_photo_update.html'
    form_class = FoodPhotoForm

    def get_success_url(self):
        foodname_pk = self.kwargs['pk']
        return reverse_lazy('web_order:food_photo_detail', kwargs={'pk': foodname_pk})

    def form_valid(self, form):
        messages.success(self.request, '登録しました。')
        call_command('generateimages')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました")
        return super().form_invalid(form)


# 料理写真の詳細表示
class FoodPhotoDetail(DetailView):
    template_name = "food_photo_detail.html"
    model = FoodPhoto


def register_generic_setout_direction(direction: str, is_enge: bool):
    if (direction is None) or (str.strip(direction) == ''):
        return

    if not GenericSetoutDirection.objects.filter(direction=direction, for_enge=is_enge).exists():
        shortening = direction if len(direction) <= 20 else direction[:20] + "..."
        generic = GenericSetoutDirection(
            direction=direction,
            shortening=shortening,
            for_enge=is_enge
        )
        generic.save()

def register_common_food_direction(request):
    FoodDirectionFormSet = modelformset_factory(FoodPhoto, form=FoodDirectionForm, extra=0)
    date_str = request.POST['date']
    date = dt.datetime.strptime(date_str, '%Y-%m-%d')
    qs = FoodPhoto.objects.filter(
                menu__isnull=False, menu__eating_day=date, menu__meal_name=request.POST['meal_name']).select_related('menu').order_by('id')
    formset = FoodDirectionFormSet(request.POST, files=request.FILES or None, queryset=qs)
    for form in formset:
        if form.is_valid():
            # 情報の登録・更新
            model = form.save(commit=True)
            model.save()

            # 定型文への登録
            register_generic_setout_direction(model.direction, False)
            register_generic_setout_direction(model.direction2, False)

    return formset

def register_enge_food_direction(request):
    EngeDirectionFormSet = modelformset_factory(EngeFoodDirection, form=EngeFoodDirectionForm, extra=0)
    date_str = request.POST['date']
    date = dt.datetime.strptime(date_str, '%Y-%m-%d')
    qs = EngeFoodDirection.objects.filter(
                menu__isnull=False, menu__eating_day=date, menu__meal_name=request.POST['meal_name']).select_related('menu').order_by('id')
    formset = EngeDirectionFormSet(request.POST, queryset=qs)

    for form in formset:
        if form.is_valid():
            # 情報の登録・更新
            model = form.save(commit=False)

            # 空更新後に前回内容が表示されないように、入力がない場合は半角空白に置き換え
            # (定型文はトリムして空でなければ登録なので、半角空白の定型文が入ることはないはず)
            model.soft_direction = model.soft_direction if model.soft_direction else ' '
            model.soft_direction2 = model.soft_direction2 if model.soft_direction2 else ' '
            model.soft_direction3 = model.soft_direction3 if model.soft_direction3 else ' '
            model.soft_direction4 = model.soft_direction4 if model.soft_direction4 else ' '
            model.soft_direction5 = model.soft_direction5 if model.soft_direction5 else ' '

            model.mixer_direction = model.mixer_direction if model.mixer_direction else ' '
            model.mixer_direction2 = model.mixer_direction2 if model.mixer_direction2 else ' '
            model.mixer_direction3 = model.mixer_direction3 if model.mixer_direction3 else ' '
            model.mixer_direction4 = model.mixer_direction4 if model.mixer_direction4 else ' '
            model.mixer_direction5 = model.mixer_direction5 if model.mixer_direction5 else ' '

            model.jelly_direction = model.jelly_direction if model.jelly_direction else ' '
            model.jelly_direction2 = model.jelly_direction2 if model.jelly_direction2 else ' '
            model.jelly_direction3 = model.jelly_direction3 if model.jelly_direction3 else ' '
            model.jelly_direction4 = model.jelly_direction4 if model.jelly_direction4 else ' '
            model.jelly_direction5 = model.jelly_direction5 if model.jelly_direction5 else ' '

            model.save()

            # 定型文への登録
            register_generic_setout_direction(model.soft_direction, True)
            register_generic_setout_direction(model.soft_direction2, True)
            register_generic_setout_direction(model.soft_direction3, True)
            register_generic_setout_direction(model.soft_direction4, True)
            register_generic_setout_direction(model.soft_direction5, True)

            register_generic_setout_direction(model.mixer_direction, True)
            register_generic_setout_direction(model.mixer_direction2, True)
            register_generic_setout_direction(model.mixer_direction3, True)
            register_generic_setout_direction(model.mixer_direction4, True)
            register_generic_setout_direction(model.mixer_direction5, True)

            register_generic_setout_direction(model.jelly_direction, True)
            register_generic_setout_direction(model.jelly_direction2, True)
            register_generic_setout_direction(model.jelly_direction3, True)
            register_generic_setout_direction(model.jelly_direction4, True)
            register_generic_setout_direction(model.jelly_direction5, True)

    return formset


def food_register(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == "POST":
        edit_direction = EditSetoutDirecion(request.POST)
        form = None
        if edit_direction.is_common_food():
            register_common_food_direction(request)
        elif edit_direction.is_enge_food():
            register_enge_food_direction(request)

        if form:
            messages.success(request, '登録完了')
    else:
        edit_direction = EditSetoutDirecion(request.GET)

    try:
        direction_type, ins, id_list = edit_direction.get_edit_target()
        if direction_type == "common":
            photo = ins[0]
            enge = None
            FoodDirectionFormSet = modelformset_factory(FoodPhoto, form=FoodDirectionForm, extra=0)
            qs = FoodPhoto.objects.filter(id__in=id_list).select_related('menu').order_by('menu_id')
            formset = FoodDirectionFormSet(queryset=qs)

            # 前回の引継ぎ
            for index, fm in enumerate(formset):
                tmp_photo = ins[index]
                # 説明
                if not fm.initial['direction']:
                    direction = \
                        OutputSetoutHelper.get_previous_direction(
                            edit_direction.date, ins[index].food_name, lambda x: x.direction)
                    if direction:
                        fm.initial['direction'] = direction
                    else:
                        # 温め・冷蔵の定型文設定
                        if tmp_photo.hot_cool == "温め":
                            fm.initial['direction'] = '再加熱カートの場合は温めモード、\n\nスチコンの場合はスチーム88℃で15分加熱、\n湯煎の場合は沸騰後15分加熱し、開封して盛付け'
                        else:
                            fm.initial['direction'] = '再加熱カートの場合は冷蔵モード、加熱せず、開封して盛付け'

                # 説明2
                if not fm.initial['direction2']:
                    fm.initial['direction2'] = \
                        OutputSetoutHelper.get_previous_direction(
                            edit_direction.date, ins[index].food_name, lambda x: x.direction2)
            menu = photo.menu
            directions = GenericSetoutDirection.objects.filter(for_enge=False).order_by('shortening')
        else:
            photo = None
            enge = ins[0]
            menu = enge.menu

            EngeDirectionFormSet = modelformset_factory(EngeFoodDirection, form=EngeFoodDirectionForm, extra=0)
            qs = EngeFoodDirection.objects.filter(id__in=id_list).select_related('menu').order_by('id')
            formset = EngeDirectionFormSet(queryset=qs)
            # 前回の引継ぎ
            for index, fm in enumerate(formset):
                # ソフト
                if not fm.initial['soft_direction']:
                    fm.initial['soft_direction'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.soft_direction)
                if not fm.initial['soft_direction2']:
                    fm.initial['soft_direction2'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.soft_direction2)
                if not fm.initial['soft_direction3']:
                    fm.initial['soft_direction3'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.soft_direction3)
                if not fm.initial['soft_direction4']:
                    fm.initial['soft_direction4'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.soft_direction4)
                if not fm.initial['soft_direction5']:
                    fm.initial['soft_direction5'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.soft_direction5)

                # ミキサー
                if not fm.initial['mixer_direction']:
                    fm.initial['mixer_direction'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.mixer_direction)
                if not fm.initial['mixer_direction2']:
                    fm.initial['mixer_direction2'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.mixer_direction2)
                if not fm.initial['mixer_direction3']:
                    fm.initial['mixer_direction3'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.mixer_direction3)
                if not fm.initial['mixer_direction4']:
                    fm.initial['mixer_direction4'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.mixer_direction4)
                if not fm.initial['mixer_direction5']:
                    fm.initial['mixer_direction5'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.mixer_direction5)

                # ゼリー
                if not fm.initial['jelly_direction']:
                    fm.initial['jelly_direction'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.jelly_direction)
                if not fm.initial['jelly_direction2']:
                    fm.initial['jelly_direction2'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.jelly_direction2)
                if not fm.initial['jelly_direction3']:
                    fm.initial['jelly_direction3'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.jelly_direction3)
                if not fm.initial['jelly_direction4']:
                    fm.initial['jelly_direction4'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.jelly_direction4)
                if not fm.initial['jelly_direction5']:
                    fm.initial['jelly_direction5'] = \
                        OutputSetoutHelper.get_previous_enge_direction(
                            edit_direction.date, ins[index].menu.food_name, lambda x: x.jelly_direction5)
            directions = GenericSetoutDirection.objects.filter(for_enge=True).order_by('shortening')

        check_value = 'on' if OutputSetoutHelper.get_prev_enge_option(menu.eating_day) else 'off'
        content = {
            'formset': formset,
            'food_photo': ins if photo else None,
            'menu': menu,
            'directions': directions,
            'target_date': edit_direction.date,
            'enge': ins if enge else None,
            'direction_type': direction_type,
            'check_value': check_value
        }

        return render(request, template_name="food_direction.html", context=content)
    except SetoutDirectionNotExistError:
        messages.warning(request, '献立情報が存在しません。月間献立のインポートを実施してくだい。')
        return render(request, template_name="food_direction.html", context={'target_date': edit_direction.date})


def exec_setout_create(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    # 盛付指示書の出力
    in_date = request.POST['in_date']
    output_enge_option = request.POST.get('enge_option_output', 'off')

    call_command('gen_setout_direction', in_date, output_enge_option)

    messages.success(request, '出力が完了しました')

    # 画面の再表示
    edit_direction = EditSetoutDirecion(request.POST)
    direction_type, ins, id_list = edit_direction.get_edit_target()
    if direction_type == "common":
        photo = ins[0]
        enge = None
        FoodDirectionFormSet = modelformset_factory(FoodPhoto, form=FoodDirectionForm, extra=0)
        qs = FoodPhoto.objects.filter(id__in=id_list).select_related('menu').order_by('id')
        formset = FoodDirectionFormSet(queryset=qs)
        menu = photo.menu
        directions = GenericSetoutDirection.objects.filter(for_enge=False)
    else:
        photo = None
        enge = ins[0]
        menu = enge.menu

        EngeDirectionFormSet = modelformset_factory(EngeFoodDirection, form=EngeFoodDirectionForm, extra=0)
        qs = EngeFoodDirection.objects.filter(id__in=id_list).select_related('menu').order_by('id')
        formset = EngeDirectionFormSet(queryset=qs)
        directions = GenericSetoutDirection.objects.filter(for_enge=True)

    check_value = 'on' if OutputSetoutHelper.get_prev_enge_option(menu.eating_day) else 'off'
    content = {
        'formset': formset,
        'food_photo': ins if photo else None,
        'menu': menu,
        'directions': directions,
        'target_date': edit_direction.date,
        'enge': ins if enge else None,
        'direction_type': direction_type,
        'check_value': check_value
    }

    return render(request, template_name="food_direction.html", context=content)


# 料理写真が未登録の一覧を表示 --------------------------------------------
def monthly_menu_list(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    form = OrderListForm(request.POST)

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻

    if request.method == "POST":

        if form.is_valid():

            in_date = form.cleaned_data['in_date']

            if 'this' in request.GET:
                from_date = get_first_date(date_time_now)  # 今月の初日
                to_date = get_last_date(date_time_now)  # 今月の最終日

            elif 'prev' in request.GET:
                this_month = request.GET.get('prev')
                this_month = dt.datetime.strptime(this_month, '%Y%m%d')
                prev_month = this_month - relativedelta(months=1)
                from_date = get_first_date(prev_month)  # 今月の初日
                to_date = get_last_date(prev_month)  # 今月の最終日

            elif 'next' in request.GET:
                this_month = request.GET.get('next')
                this_month = dt.datetime.strptime(this_month, '%Y%m%d')
                next_month = this_month + relativedelta(months=1)
                from_date = get_first_date(next_month)  # 今月の初日
                to_date = get_last_date(next_month)  # 今月の最終日

            else:
                from_date = get_first_date(date_time_now)  # 今月の初日
                to_date = get_last_date(date_time_now)  # 今月の最終日

            if in_date:
                qs = MonthlyMenu.objects\
                    .filter(eating_day=in_date,
                            food_name__in=[FoodPhoto.objects.filter(direction__isnull=True).values_list('food_name')])\
                    .order_by('id')


            else:
                qs = MonthlyMenu.objects \
                    .filter(eating_day__range=[from_date, to_date],
                            food_name__in=[FoodPhoto.objects.filter(direction__isnull=True)
                            .values_list('food_name')]).order_by('id')


            context = {
                "object_list": qs,
                "form": form,
                "from_date": from_date,
            }

        else:
            # バリデーション失敗した場合
            messages.warning(request, '入力内容に不備がありますのでご確認ください')
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "form": form,
            }

    else:
        from_date = get_first_date(date_time_now)  # 今月の初日
        to_date = get_last_date(date_time_now)  # 今月の最終日

        qs = MonthlyMenu.objects\
            .filter(eating_day__range=[from_date, to_date],
                    food_name__in=[FoodPhoto.objects.filter(direction__isnull=True)
                    .values_list('food_name')]).order_by('id')

        context = {
            "form": form,
            "object_list": qs,
            "from_date": from_date,
        }

    return render(request, template_name="monthly_menu_list.html", context=context)


# 献立資料の登録 -------------------------------------------------------
class PaperDocumentsCreate(CreateView):
    model = PaperDocuments
    template_name = 'paper_documents.html'
    form_class = PaperDocumentsForm
    success_url = reverse_lazy('web_order:paper_documents_list_all')

# 献立資料一覧
class PaperDocumentsListALL(ListView):
    model = PaperDocuments
    template_name = 'paper_documents_list_all.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = PaperDocuments.objects.all().order_by('-updated_at')
        return qs


def paper_documents_list(request):
    pk_list = DocGroupDisplay.objects.filter(username=request.user).values_list('group_name_id', flat=True)

    pk_list = list(pk_list)

    qs = PaperDocuments.objects.filter(document_group__in=pk_list)

    form = ChatForm(request.POST)

    if request.method == "POST":

        if form.is_valid():

            pass

            return redirect("web_order:chat")

        else:
            # バリデーション失敗した場合
            messages.warning(request, '入力内容に不備がありますのでご確認ください')
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "form": form,
            }

    else:
        context = {
            "form": form,
            "object_list": qs,
            "pk_list": pk_list,
        }

    return render(request, template_name="paper_documents_list.html", context=context)


# 献立資料の登録 --------------------------------------------------------
def exclude_invalid_not_enge_dir(top_path, top_dir):
    dir_path = os.path.join(top_path, top_dir)

    # 食種フォルダのチェック
    plate_dir_list, _ = default_storage.listdir(dir_path)

    for plate_dir in plate_dir_list:
        free_parent_path = os.path.join(dir_path, plate_dir)
        free_parent_dir_list, _ = default_storage.listdir(free_parent_path)

        # 食種以下1階層は全て許可
        for free_parent_dir in free_parent_dir_list:
            free_child_path = os.path.join(free_parent_path, free_parent_dir)
            free_child_dir_list, _ = default_storage.listdir(free_child_path)

            # 食種以下2階層も全て許可
            for free_child_dir in free_child_dir_list:
                grand_child_path = os.path.join(free_child_path, free_child_dir)
                free_exclude_dir_list, _ = default_storage.listdir(grand_child_path)

                # 食種以下3階層以下はも全て不許可
                for exclude_dir in free_exclude_dir_list:
                    shutil.rmtree(os.path.join(grand_child_path, exclude_dir))


def exclude_invalid_enge_dir(root_path, root_dir):
    enge_path = os.path.join(root_path, root_dir)

    # 嚥下種類フォルダのチェック
    kind_dir_list, _ = default_storage.listdir(enge_path)
    exclude_list = [dir for dir in kind_dir_list if not (dir in ['ソフト', 'ゼリー', 'ミキサー'])]
    for p1 in exclude_list:
        shutil.rmtree(os.path.join(enge_path, p1))

    for valid_dir in [dir for dir in kind_dir_list if dir in ['ソフト', 'ゼリー', 'ミキサー']]:
        exclude_invalid_not_enge_dir(enge_path, valid_dir)


def exclude_invalid_dir(document_path, root_dir, year, month):
    root_path = os.path.join(document_path, root_dir)
    res_root = re.findall('^(\d+)年(\d+)月', root_dir)

    # ルート(年月)フォルダのチェック
    if res_root and (int(res_root[0][0]) == year) and (int(res_root[0][1]) == month):
        # 第一階層のフォルダのチェック
        dir_list, _ = default_storage.listdir(root_path)
        exclude_list = [dir for dir in dir_list if not (dir in ['基本食', '常食', '薄味', '嚥下'])]
        for p1 in exclude_list:
            shutil.rmtree(os.path.join(root_path, p1))
        valid_list = [dir for dir in dir_list if dir in ['基本食', '常食', '薄味', '嚥下']]

        # 第2階層のフォルダをチェック
        for p_top in valid_list:
            if p_top == '嚥下':
                exclude_invalid_enge_dir(root_path, p_top)
            else:
                exclude_invalid_not_enge_dir(root_path, p_top)

        return True
    else:
        shutil.rmtree(root_path)
        return False


def generate_delete_folder(post_param):
    for key, value in post_param.items():
        res_key = re.findall('folder-(\d+)', key)
        if res_key:
            yield value


def generate_delete_file(post_param):
    for key, value in post_param.items():
        res_key = re.findall('file-(\d+)', key)
        if res_key:
            yield value


def documents_delete(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        path = request.POST.get('path', None)
        sp_path = []
        if path:
            sp_path = path[1:].split('/')

        # 現在日時の年月フォルダを参照
        tmp = request.POST.get('upper_btn', None)
        if tmp:
            path = tmp if tmp != '/' else ''
            date = request.POST.get('current_date')
        else:
            path = request.POST.get('path', None)
            date = request.POST.get('date', '')

        if date:
            sp_date = date.split('-')
            year = sp_date[0]
            month = sp_date[1]
        else:
            now = dt.datetime.now()
            year = now.year
            month = now.month
        month_folder = f'{year}年{month}月'

        month_path = os.path.join(settings.MEDIA_ROOT, "output", "document", month_folder)

        # 管理用ページなので、全てのフォルダ・ファイルを表示する(通常の画面表示と同様に取得)
        if os.path.isdir(month_path):
            if path:
                dir_path = ''
                for p in sp_path:
                    dir_path = os.path.join(dir_path, p)
                target_path = os.path.join(month_path, dir_path)
                dirs, files = default_storage.listdir(target_path)
                if files:
                    # ファイル名のみのリストを更新日時を含めたタプルに変換
                    files = [(x, get_lastmoddate(os.path.join(target_path, x))) for x in files]

                # ダウンロード・参照用のURL生成
                document_url = os.path.join(settings.MEDIA_URL, "output", "document", month_folder, dir_path)
                if dir_path:
                    parent = ''
                    for p in sp_path[:-1]:
                        parent = os.path.join(parent, p)
                    if parent:
                        parent = os.path.join('/', parent)
                    current = os.path.join('/', dir_path)

                    current = current.replace(os.sep, '/')
                    parent = parent.replace(os.sep, '/')

                # 削除対象のフォルダを削除する。
                for dir in generate_delete_folder(request.POST):
                    shutil.rmtree(os.path.join(target_path, dir))
                    for x in dirs:
                        if x == dir:
                            dirs.remove(dir)
                            break

                # 削除対象のファイルを削除する。
                for delete_file in generate_delete_file(request.POST):
                    os.remove(os.path.join(target_path, delete_file))
                    for x in files:
                        if x[0] == delete_file:
                            files.remove(x)
                            break
            else:
                messages.error(request, '対象のフォルダは削除できません。')
                dirs, files = default_storage.listdir(
                    os.path.join(settings.MEDIA_ROOT, "output", "document", month_folder))
                parent = None
                current = ''
                document_url = os.path.join(settings.MEDIA_URL, "output", "document", month_folder)
        else:
            dirs = []
            files = []
            parent = None
            current = ''
            document_url = ''

        if not (dirs or files):
            messages.info(request, '登録されたフォルダ・ファイルがありません。')

        redirect_url = reverse('web_order:document_files')
        parameters = urlencode(dict(parent=parent,
                                    path=path,
                                    date=f'{year}-{month}'))
        url = f'{redirect_url}?{parameters}'
        return redirect(url)
    else:
        return redirect('web_order:document_files')


def get_uploading_replaced_path(sp, border):
    if len(sp) >= border:
        if sp[2] in ['ソフト', 'ミキサー', 'ゼリー']:
            if len(sp) > 3:
                index = 3
                filename = sp[3]
            else:
                filename = None
        else:
            index = 2
            filename = sp[2]

        if filename:
            # 半角空白を全角空白へ
            filename = filename.replace(' ', '　')

            # 半角数字の変換(4以上は食種フォルダにないため、変換しない)
            filename = filename.replace('１', '1')
            filename = filename.replace('２', '2')
            filename = filename.replace('３', '3')

            pre_path = sp[0:index]
            replaced = ''
            for x in pre_path:
                replaced = os.path.join(replaced, x)
            replaced = os.path.join(replaced, filename)
            for x in sp[index + 1:]:
                replaced = os.path.join(replaced, x)
            return replaced.replace(os.sep, '/')

    return None


def documents_upload(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':

        form = DocumentsUploadForm(request.POST, request.FILES)

        if form.is_valid():
            upload_form = form.save(commit=False)
            file = upload_form.document_file
            year = upload_form.year
            month = upload_form.month

            file.name = f'{year}_{month}.zip'
            # 既存のファイルを削除
            zip_file_path = os.path.join(settings.MEDIA_ROOT, 'upload', file.name)
            if os.path.isfile(zip_file_path):
                os.remove(zip_file_path)

            # ファイルの保存
            upload_form.save()

            # zipファイルの展開
            output_path = os.path.join(settings.OUTPUT_DIR, 'document')
            os.makedirs(output_path, exist_ok=True)  # 上書きOK
            top_folder_name = ''
            with zipfile.ZipFile(zip_file_path) as z:
                for info in z.infolist():
                    if not (info.flag_bits & 0x800):
                        if info.flag_bits & 0x008:
                            info.filename = info.orig_filename.encode("cp437").decode("utf-8")
                        else:
                            info.filename = info.orig_filename.encode("cp437").decode("cp932")
                    # info.filename = info.orig_filename.encode('cp437').decode('cp932')
                    if platform.system() == 'Windows':
                        if os.sep != "/" and os.sep in info.filename:
                            info.filename = info.filename.replace(os.sep, "/")
                    if not top_folder_name:
                        sp = info.filename.split("/")
                        top_folder_name = sp[0]

                    # フォルダ名の表記ゆれの対応
                    if info.is_dir():
                        res = re.match('^\d{4年}\d{1,2}年/?$', info.filename)
                        if res:
                            pass
                        else:
                            # 対象のフォルダ名
                            sp = info.filename[:-1].split('/')
                            replaced = get_uploading_replaced_path(sp, 3)
                            if replaced:
                                info.filename = replaced + '/'
                    else:
                        sp = info.filename.split('/')
                        replaced = get_uploading_replaced_path(sp, 4)
                        if replaced:
                            info.filename = replaced

                    z.extract(info, output_path)

            # 規格外のフォルダを削除
            if exclude_invalid_dir(output_path, top_folder_name, year, month):
                messages.success(request, '献立資料を一括登録しました。')
            else:
                messages.error(request, 'zipファイルの構成が不正です。')
        context = {
            "form": form,
        }

    else:
        form = DocumentsUploadForm()
        context = {
            "form": form,
        }

    return render(request, template_name="document_upload.html", context=context)


# 売価計算表の出力 --------------------------------------------------------
def sales_price_output(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = ExecCalculateSalesPriceForm(request.POST)
        if form.is_valid():
            in_date = form.cleaned_data['in_date']
            if platform.system() == 'Windows':
                month = in_date.strftime('%Y-%m')
            else:
                month = in_date.strftime('%Y-%-m')

            # 売価計算表出力
            call_command('calc_sales_price', month, form.cleaned_data['in_transport_price'])

            messages.success(request, '出力が完了しました')

            return redirect('web_order:sales_price_files')
        else:
            context = {
                "form": form
            }
    else:
        form = ExecCalculateSalesPriceForm()
        context = {
            "form": form
        }

    return render(request, template_name="sales_price_output.html", context=context)


# 売価計算表管理画面の出力 --------------------------------------------------------
def is_include_current_month(from_day, to_day, today):
    if from_day and to_day:
        if (from_day <= to_day) and (to_day >= today):
            return True
        else:
            return False
    elif from_day:
        if from_day <= today:
            return True
        else:
            return False
    elif to_day:
        if to_day >= to_day:
            return True
        else:
            return False
    else:
        return False


def add_to_list_if_condition(list, dict, from_day, to_day, cond_from, cond_to, monthly_price, is_updated):
    # 売上条件判定
    if cond_from and (dict['sales_total'] < from_sales):
        return
    if cond_to and (dict['sales_total'] > to_sales):
        return

    # 日割り計算用日数保存
    if monthly_price.month == 12:
        dict['full_days'] = 31
    else:
        tmp_day = dt.date(year=monthly_price.year, month=monthly_price.month + 1, day=1) - relativedelta(days=1)
        dict['full_days'] = tmp_day.day
    if is_updated:
        dict['days'] = dict['full_days']
    else:
        if from_day and (monthly_price.year == from_day.year) and (monthly_price.month == from_day.month) and (from_day.day > 1):
            dict['days'] = dict['full_days'] - from_day.day
        elif to_day and (monthly_price.year == to_day.year) and (monthly_price.month == to_day.month) and (
                to_day + relativedelta(days=1)).day != 1:
            # 月の最終日でない場合
            dict['days'] = to_day.day
        else:
            dict['days'] = dict['full_days']

    list.append(dict)


def get_transport_aggregation(price_dict_list):
    # 送料計算
    transfer_total = 0
    transfer_full_total = 0
    months_total = 0
    total_rate = 0
    total_rate_b = 0
    total_rate_l = 0
    total_rate_d = 0
    for x in price_dict_list:
        if x['is_updated']:
            continue

        total_rate += x['price'].transport_breakfast_rate + x['price'].transport_lunch_rate + x[
            'price'].transport_dinner_rate
        total_rate_b += x['price'].transport_breakfast_rate
        total_rate_l += x['price'].transport_lunch_rate
        total_rate_d += x['price'].transport_dinner_rate
        transfer_tmp = x['price'].transport_price / x['count_total'] * 3
        if x['full_days'] == x['days']:
            transfer_total += transfer_tmp
            transfer_full_total += x['price'].transport_price
        else:
            # 日割り計算
            transfer_total += transfer_tmp * (x['days'] / x['full_days'])
            transfer_full_total += x['price'].transport_price * (x['days'] / x['full_days'])
        months_total += 1

    # 平均配送料
    if months_total:
        average_transport = transfer_total / months_total
    else:
        average_transport = 0

    # 食事区分別配送料
    if average_transport:
        meal_transport_b = average_transport * float(total_rate_b / total_rate)
        meal_transport_l = average_transport * float(total_rate_l / total_rate)
        meal_transport_d = average_transport * float(total_rate_d / total_rate)
        meal_transport_t = meal_transport_b + meal_transport_l + meal_transport_d
    else:
        meal_transport_b = 0
        meal_transport_l = 0
        meal_transport_d = 0
        meal_transport_t = 0

    return transfer_full_total, average_transport, meal_transport_b, meal_transport_l, meal_transport_d, meal_transport_t


def get_price_averages(price_dict_list):
    days_list = []
    for x in price_dict_list:
        days_list.append(x['days'])
    days_total = sum(days_list)
    total_average_include = 0
    total_average_without = 0
    for x in price_dict_list:
        if x['is_updated']:
            continue

        tmp_include = x['total_average_include']
        total_average_include += tmp_include * x['days']

        tmp_without = x['total_average_without']
        total_average_without += tmp_without * x['days']
    average_include = total_average_include / days_total
    average_without = total_average_without / days_total

    return average_include, average_without


def get_simple_averages(price_dict_list, average_transport):
    simple_cnt_basic = 0
    simple_cnt_enge = 0
    simple_cnt_total = 0
    simple_total_basic = 0
    simple_total_enge = 0
    simple_total_total = 0
    # -日割りを考慮した食数、売上の計算
    for x in price_dict_list:
        if x['is_updated']:
            continue

        if x['full_days'] == x['days']:
            tmp_simple_total_basic = x['basic_sales_total']
            tmp_simple_total_enge = x['enge_sales_total']
            tmp_simple_cnt_basic = x['basic_count_total']
            tmp_simple_cnt_enge = x['enge_count_total']
        else:
            # 日割り計算
            tmp_simple_total_basic = x['basic_sales_total'] * (x['days'] / x['full_days'])
            tmp_simple_total_enge = x['enge_sales_total'] * (x['days'] / x['full_days'])
            tmp_simple_cnt_basic = x['basic_count_total'] * (x['days'] / x['full_days'])
            tmp_simple_cnt_enge = x['enge_count_total'] * (x['days'] / x['full_days'])
        simple_total_basic += tmp_simple_total_basic
        simple_total_enge += tmp_simple_total_enge
        simple_total_total += tmp_simple_total_basic + tmp_simple_total_enge
        simple_cnt_basic += tmp_simple_cnt_basic
        simple_cnt_enge += tmp_simple_cnt_enge
        simple_cnt_total += tmp_simple_cnt_basic + tmp_simple_cnt_enge

    if simple_cnt_basic:
        simple_average_basic_include = simple_total_basic / simple_cnt_basic * 3
    else:
        simple_average_basic_include = 0
    if simple_cnt_enge:
        simple_average_enge_include = simple_total_enge / simple_cnt_enge * 3
    else:
        simple_average_enge_include = 0
    if simple_cnt_total:
        simple_average_total_include = simple_total_total / simple_cnt_total * 3
    else:
        simple_average_total_include = 0
    simple_average_basic_without = simple_average_basic_include - average_transport
    simple_average_enge_without = simple_average_enge_include - average_transport
    simple_average_total_without = simple_average_total_include - average_transport

    return simple_average_basic_include, simple_average_enge_include, simple_average_total_include, \
           simple_average_basic_without, simple_average_enge_without, simple_average_total_without

def sales_price_management_view(request):
    if not request.user.is_staff:
        if not (request.user.is_superuser or request.user.is_management):
            return HttpResponse('このページは表示できません', status=500)

    if request.method == 'GET':
        item_choices = []
        meal_choices = []
        output_choices = []
        price_dict_list = []            # 汁売上除外
        price_dict_list_included = []   # 汁売上含む
        form = None
        if request.GET:
            form = SearchSalesPriceForm(request.GET)
            if form.is_valid():
                from_day = form.cleaned_data['from_date']
                to_day = form.cleaned_data['to_date']
                from_sales = form.cleaned_data['from_sales']
                to_sales = form.cleaned_data['to_sales']

                item_choices = form.cleaned_data['display_item_group']
                meal_choices = form.cleaned_data['display_meal_group']
                output_choices = form.cleaned_data['display_output_group']

                # 当月の検索があった場合は、当月分の売価計算表を出力して、集計結果を得る(配送料は0のまま計算)
                today = dt.datetime.today().date()
                is_updated = False
                is_error = False
                if is_include_current_month(from_day, to_day, today):
                    qs = MonthlySalesPrice.objects.filter(year=today.year, month=today.month, transport_price__gt=0)
                    if not qs.exists():
                        try:
                            call_command('calc_sales_price', f'{today.year}-{today.month}', 0)
                            is_updated = True
                        except Exception as e:
                            logger.info(traceback.format_exc())
                            is_error = True

                if not is_error:
                    if from_day and to_day:
                        price_list = MonthlySalesPrice.objects.filter(
                            year__range=[from_day.year, to_day.year]).\
                            exclude(year=from_day.year, month__lt=from_day.month).\
                            exclude(year=to_day.year, month__gt=to_day.month).order_by('year', 'month')
                    elif from_day:
                        # 開始日のみ
                        today = dt.datetime.today()
                        price_list = MonthlySalesPrice.objects.filter(
                            year__range=[from_day.year, today.year]).\
                            exclude(year=from_day.year, month__lt=from_day.month).\
                            exclude(year=today.year, month__gt=to_day.month).order_by('year', 'month')
                    elif to_day:
                        # 終了日のみ
                        today = dt.datetime.today()
                        price_list = MonthlySalesPrice.objects.filter(
                            year__range=[today.year, to_day.year]).\
                            exclude(year=today.year, month__lt=from_day.month).\
                            exclude(year=to_day.year, month__gt=to_day.month).order_by('year', 'month')
                    else:
                        price_list = MonthlySalesPrice.objects.all().order_by('year', 'month')

                    if price_list:
                        # 不足情報の補填(表示対象外は除いた方がいいかも・・・)
                        for monthly_price in price_list:
                            price_dict = {}
                            price_dict_included = {}
                            price_dict['price'] = monthly_price
                            price_dict_included['price'] = monthly_price
                            if (monthly_price.year == today.year) and (monthly_price.month == today.month):
                                price_dict['is_updated'] = is_updated
                            else:
                                price_dict['is_updated'] = False
                            price_dict_included['is_updated'] = price_dict['is_updated']

                            # 食数合計の計算
                            price_dict['breakfast_count'] = monthly_price.basic_breakfast_count + monthly_price.enge_breakfast_count
                            price_dict['lunch_count'] = monthly_price.basic_lunch_count + monthly_price.enge_lunch_count
                            price_dict['dinner_count'] = monthly_price.basic_dinner_count + monthly_price.enge_dinner_count
                            price_dict['basic_count_total'] = \
                                monthly_price.basic_breakfast_count + monthly_price.basic_lunch_count + monthly_price.basic_dinner_count
                            price_dict['enge_count_total'] = \
                                monthly_price.enge_breakfast_count + monthly_price.enge_lunch_count + monthly_price.enge_dinner_count
                            price_dict['count_total'] = \
                                price_dict['basic_count_total'] + price_dict['enge_count_total']

                            price_dict_included['breakfast_count'] = price_dict['breakfast_count']
                            price_dict_included['lunch_count'] = price_dict['lunch_count']
                            price_dict_included['dinner_count'] = price_dict['dinner_count']
                            price_dict_included['basic_count_total'] = price_dict['basic_count_total']
                            price_dict_included['enge_count_total'] = price_dict['enge_count_total']
                            price_dict_included['count_total'] = price_dict['count_total']

                            # 売上合計の計算(汁売上を除く)
                            price_dict[
                                'breakfast_sales'] = int(monthly_price.basic_breakfast_sales + monthly_price.enge_breakfast_sales)
                            price_dict['lunch_sales'] = int(monthly_price.basic_lunch_sales + monthly_price.enge_lunch_sales)
                            price_dict['dinner_sales'] = int(monthly_price.basic_dinner_sales + monthly_price.enge_dinner_sales)
                            price_dict['basic_sales_total'] = \
                                int(monthly_price.basic_breakfast_sales + monthly_price.basic_lunch_sales + monthly_price.basic_dinner_sales)
                            price_dict['enge_sales_total'] = \
                                int(monthly_price.enge_breakfast_sales + monthly_price.enge_lunch_sales + monthly_price.enge_dinner_sales)
                            price_dict['sales_total'] = \
                                int(price_dict['basic_sales_total'] + price_dict['enge_sales_total'])

                            # 売上合計の計算(汁売上を含む)
                            price_dict_included['breakfast_sales'] = price_dict['breakfast_sales'] + monthly_price.basic_breakfast_soup_sales + monthly_price.enge_breakfast_soup_sales
                            price_dict_included['lunch_sales'] = price_dict['lunch_sales'] + monthly_price.basic_lunch_soup_sales + monthly_price.enge_lunch_soup_sales
                            price_dict_included['dinner_sales'] = price_dict['dinner_sales'] + monthly_price.basic_dinner_soup_sales + monthly_price.enge_dinner_soup_sales
                            price_dict_included['basic_sales_total'] = price_dict['basic_sales_total'] + \
                                int(monthly_price.basic_breakfast_soup_sales + monthly_price.basic_lunch_soup_sales + monthly_price.basic_dinner_soup_sales)
                            price_dict_included['enge_sales_total'] = price_dict['enge_sales_total'] + \
                                int(monthly_price.enge_breakfast_soup_sales + monthly_price.enge_lunch_soup_sales + monthly_price.enge_dinner_soup_sales)
                            price_dict_included['sales_total'] = \
                                int(price_dict_included['basic_sales_total'] + price_dict_included['enge_sales_total'])

                            # 1食あたり平均売価(配送料込み)の計算
                            # -基本食
                            if monthly_price.basic_breakfast_count == 0:
                                price_dict['basic_breakfast_average_include'] = 0
                                price_dict_included['basic_breakfast_average_include'] = 0
                            else:
                                price_dict[
                                    'basic_breakfast_average_include'] = monthly_price.basic_breakfast_sales / monthly_price.basic_breakfast_count
                                price_dict_included[
                                    'basic_breakfast_average_include'] = \
                                    (monthly_price.basic_breakfast_sales + monthly_price.basic_breakfast_soup_sales) / monthly_price.basic_breakfast_count
                            if monthly_price.basic_lunch_count == 0:
                                price_dict['basic_lunch_average_include'] = 0
                                price_dict_included['basic_lunch_average_include'] = 0
                            else:
                                price_dict['basic_lunch_average_include'] = monthly_price.basic_lunch_sales / monthly_price.basic_lunch_count
                                price_dict_included[
                                    'basic_lunch_average_include'] = \
                                    (monthly_price.basic_lunch_sales + monthly_price.basic_lunch_soup_sales) / monthly_price.basic_lunch_count
                            if monthly_price.basic_dinner_count == 0:
                                price_dict['basic_dinner_average_include'] = 0
                                price_dict_included['basic_dinner_average_include'] = 0
                            else:
                                price_dict['basic_dinner_average_include'] = monthly_price.basic_dinner_sales / monthly_price.basic_dinner_count
                                price_dict_included[
                                    'basic_dinner_average_include'] = \
                                    (monthly_price.basic_dinner_sales + monthly_price.basic_dinner_soup_sales) / monthly_price.basic_dinner_count

                            # -嚥下
                            if monthly_price.enge_breakfast_count == 0:
                                price_dict['enge_breakfast_average_include'] = 0
                                price_dict_included['enge_breakfast_average_include'] = 0
                            else:
                                price_dict[
                                    'enge_breakfast_average_include'] = monthly_price.enge_breakfast_sales / monthly_price.enge_breakfast_count
                                price_dict_included[
                                    'enge_breakfast_average_include'] = \
                                    (monthly_price.enge_breakfast_sales + monthly_price.enge_breakfast_soup_sales) / monthly_price.enge_breakfast_count
                            if monthly_price.enge_lunch_count == 0:
                                price_dict['enge_lunch_average_include'] = 0
                                price_dict_included['enge_lunch_average_include'] = 0
                            else:
                                price_dict[
                                    'enge_lunch_average_include'] = monthly_price.enge_lunch_sales / monthly_price.enge_lunch_count
                                price_dict_included[
                                    'enge_lunch_average_include'] = \
                                    (monthly_price.enge_lunch_sales + monthly_price.enge_lunch_soup_sales) / monthly_price.enge_lunch_count
                            if monthly_price.basic_dinner_count == 0:
                                price_dict['enge_dinner_average_include'] = 0
                                price_dict_included['enge_dinner_average_include'] = 0
                            else:
                                price_dict['enge_dinner_average_include'] = monthly_price.enge_dinner_sales / monthly_price.enge_dinner_count
                                price_dict_included[
                                    'enge_dinner_average_include'] = \
                                    (monthly_price.enge_dinner_sales + monthly_price.enge_dinner_soup_sales) / monthly_price.enge_dinner_count

                            # -全体
                            bc = price_dict['breakfast_count'] or 1
                            lc = price_dict['lunch_count'] or 1
                            dc = price_dict['dinner_count'] or 1
                            price_dict['breakfast_average_include'] = \
                                Decimal(monthly_price.basic_breakfast_sales / bc) + \
                                Decimal(monthly_price.enge_breakfast_sales / bc)
                            price_dict['lunch_average_include'] = \
                                Decimal(monthly_price.basic_lunch_sales / lc) + \
                                Decimal(monthly_price.enge_lunch_sales / lc)
                            price_dict['dinner_average_include'] = \
                                Decimal(monthly_price.basic_dinner_sales / dc) + \
                                Decimal(monthly_price.enge_dinner_sales / dc)

                            price_dict_included['breakfast_average_include'] = \
                                Decimal((monthly_price.basic_breakfast_sales + monthly_price.basic_breakfast_soup_sales) / bc) + \
                                Decimal((monthly_price.enge_breakfast_sales + monthly_price.enge_breakfast_soup_sales) / bc)
                            price_dict_included['lunch_average_include'] = \
                                Decimal((monthly_price.basic_lunch_sales + monthly_price.basic_lunch_soup_sales) / lc) + \
                                Decimal((monthly_price.enge_lunch_sales + monthly_price.enge_lunch_soup_sales) / lc)
                            price_dict_included['dinner_average_include'] = \
                                Decimal((monthly_price.basic_dinner_sales + monthly_price.basic_dinner_soup_sales) / dc) + \
                                Decimal((monthly_price.enge_dinner_sales + monthly_price.enge_dinner_soup_sales) / dc)

                            price_dict['basic_average_include'] = price_dict['basic_breakfast_average_include'] + price_dict['basic_lunch_average_include'] + price_dict['basic_dinner_average_include']
                            price_dict['enge_average_include'] = price_dict['enge_breakfast_average_include'] + price_dict['enge_lunch_average_include'] + price_dict['enge_dinner_average_include']
                            price_dict['total_average_include'] = \
                                price_dict['breakfast_average_include'] + price_dict['lunch_average_include'] + price_dict['dinner_average_include']

                            price_dict_included['basic_average_include'] = price_dict_included['basic_breakfast_average_include'] + price_dict_included['basic_lunch_average_include'] + price_dict_included['basic_dinner_average_include']
                            price_dict_included['enge_average_include'] = price_dict_included['enge_breakfast_average_include'] + price_dict_included['enge_lunch_average_include'] + price_dict_included['enge_dinner_average_include']
                            price_dict_included['total_average_include'] = \
                                price_dict_included['breakfast_average_include'] + price_dict_included['lunch_average_include'] + price_dict_included['dinner_average_include']

                            # 1食あたり平均売価(配送料抜き)の計算
                            average_transport = Decimal(monthly_price.transport_price / price_dict['count_total'] * 3)
                            rate_total = monthly_price.transport_breakfast_rate + monthly_price.transport_lunch_rate + monthly_price.transport_dinner_rate
                            breakfast_ave_transport = average_transport / rate_total * monthly_price.transport_breakfast_rate
                            lunch_ave_transport = average_transport / rate_total * monthly_price.transport_lunch_rate
                            dinner_ave_transport = average_transport / rate_total * monthly_price.transport_dinner_rate
                            price_dict['basic_breakfast_average_without'] = price_dict['basic_breakfast_average_include'] - breakfast_ave_transport
                            price_dict['basic_lunch_average_without'] = price_dict['basic_lunch_average_include'] - lunch_ave_transport
                            price_dict['basic_dinner_average_without'] = price_dict['basic_dinner_average_include'] - dinner_ave_transport

                            price_dict_included['basic_breakfast_average_without'] = price_dict_included['basic_breakfast_average_include'] - breakfast_ave_transport
                            price_dict_included['basic_lunch_average_without'] = price_dict_included['basic_lunch_average_include'] - lunch_ave_transport
                            price_dict_included['basic_dinner_average_without'] = price_dict_included['basic_dinner_average_include'] - dinner_ave_transport

                            price_dict['enge_breakfast_average_without'] = price_dict['enge_breakfast_average_include'] - breakfast_ave_transport
                            price_dict['enge_lunch_average_without'] = price_dict['enge_lunch_average_include'] - lunch_ave_transport
                            price_dict['enge_dinner_average_without'] = price_dict['enge_dinner_average_include'] - dinner_ave_transport

                            price_dict_included['enge_breakfast_average_without'] = price_dict_included['enge_breakfast_average_include'] - breakfast_ave_transport
                            price_dict_included['enge_lunch_average_without'] = price_dict_included['enge_lunch_average_include'] - lunch_ave_transport
                            price_dict_included['enge_dinner_average_without'] = price_dict_included['enge_dinner_average_include'] - dinner_ave_transport

                            price_dict['breakfast_average_without'] = price_dict['breakfast_average_include'] - breakfast_ave_transport
                            price_dict['lunch_average_without'] = price_dict['lunch_average_include'] - lunch_ave_transport
                            price_dict['dinner_average_without'] = price_dict['dinner_average_include'] - dinner_ave_transport

                            price_dict_included['breakfast_average_without'] = price_dict_included['breakfast_average_include'] - breakfast_ave_transport
                            price_dict_included['lunch_average_without'] = price_dict_included['lunch_average_include'] - lunch_ave_transport
                            price_dict_included['dinner_average_without'] = price_dict_included['dinner_average_include'] - dinner_ave_transport

                            price_dict['basic_average_without'] = price_dict['basic_breakfast_average_without'] + price_dict[
                                'basic_lunch_average_without'] + price_dict['basic_dinner_average_without']
                            price_dict['enge_average_without'] = price_dict['enge_breakfast_average_without'] + price_dict[
                                'enge_lunch_average_without'] + price_dict['enge_dinner_average_without']
                            price_dict['total_average_without'] = price_dict['breakfast_average_without'] + \
                                                                  price_dict['lunch_average_without'] + price_dict['dinner_average_without']

                            price_dict_included['basic_average_without'] = price_dict_included['basic_breakfast_average_without'] + price_dict_included[
                                'basic_lunch_average_without'] + price_dict_included['basic_dinner_average_without']
                            price_dict_included['enge_average_without'] = price_dict_included['enge_breakfast_average_without'] + price_dict_included[
                                'enge_lunch_average_without'] + price_dict_included['enge_dinner_average_without']
                            price_dict_included['total_average_without'] = price_dict_included['breakfast_average_without'] + \
                                                                  price_dict_included['lunch_average_without'] + price_dict_included['dinner_average_without']

                            add_to_list_if_condition(price_dict_list, price_dict, from_day, to_day, from_sales, to_sales, monthly_price, is_updated)
                            add_to_list_if_condition(price_dict_list_included, price_dict_included, from_day, to_day, from_sales, to_sales, monthly_price, is_updated)

                        logger.info(price_dict_list)
                        tpl_transfer = get_transport_aggregation(price_dict_list)
                        transfer_full_total = tpl_transfer[0]
                        average_transport = tpl_transfer[1]
                        meal_transport_b = tpl_transfer[2]
                        meal_transport_l = tpl_transfer[3]
                        meal_transport_d = tpl_transfer[4]
                        meal_transport_t = tpl_transfer[5]

                        tpl_transfer_included = get_transport_aggregation(price_dict_list_included)
                        transfer_full_total_in = tpl_transfer_included[0]
                        average_transport_in = tpl_transfer_included[1]
                        meal_transport_b_in = tpl_transfer_included[2]
                        meal_transport_l_in = tpl_transfer_included[3]
                        meal_transport_d_in = tpl_transfer_included[4]
                        meal_transport_t_in = tpl_transfer_included[5]

                        # 平均売価計算
                        average_include, average_without = get_price_averages(price_dict_list)
                        average_include_in, average_without_in = get_price_averages(price_dict_list_included)

                        # 単純平均売価(汁売上含まない)
                        simple_averages = get_simple_averages(price_dict_list, average_transport)
                        simple_average_basic_include = simple_averages[0]
                        simple_average_enge_include = simple_averages[1]
                        simple_average_total_include = simple_averages[2]
                        simple_average_basic_without = simple_averages[3]
                        simple_average_enge_without = simple_averages[4]
                        simple_average_total_without = simple_averages[5]

                        # 単純平均売価(汁売上含む)
                        simple_averages_in = get_simple_averages(price_dict_list_included, average_transport_in)
                        simple_average_basic_include_in = simple_averages_in[0]
                        simple_average_enge_include_in = simple_averages_in[1]
                        simple_average_total_include_in = simple_averages_in[2]
                        simple_average_basic_without_in = simple_averages_in[3]
                        simple_average_enge_without_in = simple_averages_in[4]
                        simple_average_total_without_in = simple_averages_in[5]

                        # 非表示判定
                        is_show_basic = '1' in item_choices
                        is_show_enge = '2' in item_choices
                        is_show_total = is_show_basic or is_show_enge

                        is_show_breakfast = '1' in meal_choices
                        is_show_lunch = '2' in meal_choices
                        is_show_dinner = '3' in meal_choices
                        is_show_sum = '4' in meal_choices

                        is_show_count = '1' in output_choices
                        is_show_sales = '2' in output_choices
                        is_show_ave_include = '3' in output_choices
                        is_show_ave_without = '4' in output_choices
        if not price_dict_list:
            if not form:
                form = SearchSalesPriceForm()

            is_show_basic = True
            is_show_enge = True
            is_show_total = is_show_basic or is_show_enge

            is_show_breakfast = True
            is_show_lunch = True
            is_show_dinner = True
            is_show_sum = True

            is_show_count = True
            is_show_sales = True
            is_show_ave_include = True
            is_show_ave_without = True

            average_transport = 0
            average_include = 0
            average_without = 0

            average_transport_in = 0
            average_include_in = 0
            average_without_in = 0

            transfer_full_total = 0
            meal_transport_b = 0
            meal_transport_l = 0
            meal_transport_d = 0
            meal_transport_t = 0

            transfer_full_total_in = 0
            meal_transport_b_in = 0
            meal_transport_l_in = 0
            meal_transport_d_in = 0
            meal_transport_t_in = 0

            simple_average_basic_include = 0
            simple_average_enge_include = 0
            simple_average_total_include = 0
            simple_average_basic_without = 0
            simple_average_enge_without = 0
            simple_average_total_without = 0

            simple_average_basic_include_in = 0
            simple_average_enge_include_in = 0
            simple_average_total_include_in = 0
            simple_average_basic_without_in = 0
            simple_average_enge_without_in = 0
            simple_average_total_without_in = 0

        part_column_count = len([x for x in [is_show_breakfast, is_show_lunch, is_show_dinner, is_show_sum] if x])
        context = {
            "form": form,

            "item_choices": item_choices,
            "meal_choices": meal_choices,
            "output_choices": output_choices,

            "is_show_basic": is_show_basic,
            "is_show_enge": is_show_enge,
            "is_show_total": is_show_total,

            "is_show_breakfast": is_show_breakfast,
            "is_show_lunch": is_show_lunch,
            "is_show_dinner": is_show_dinner,
            "is_show_sum": is_show_sum,

            "is_show_count": is_show_count,
            "is_show_sales": is_show_sales,
            "is_show_ave_include": is_show_ave_include,
            "is_show_ave_without": is_show_ave_without,

            "t1": {
                "price_list": price_dict_list,
                "part_column_count": part_column_count,
                "average_transport": average_transport,
                "average_include": average_include,
                "average_without": average_without,

                "transport_total": transfer_full_total,
                "meal_transport_b": meal_transport_b,
                "meal_transport_l": meal_transport_l,
                "meal_transport_d": meal_transport_d,
                "meal_transport_t": meal_transport_t,

                "simple_average_basic_include": simple_average_basic_include,
                "simple_average_enge_include": simple_average_enge_include,
                "simple_average_total_include": simple_average_total_include,
                "simple_average_basic_without": simple_average_basic_without,
                "simple_average_enge_without": simple_average_enge_without,
                "simple_average_total_without": simple_average_total_without,
            },
            "t2": {
                "price_list": price_dict_list_included,
                "part_column_count": part_column_count,
                "average_transport": average_transport_in,
                "average_include": average_include_in,
                "average_without": average_without_in,

                "transport_total": transfer_full_total_in,
                "meal_transport_b": meal_transport_b_in,
                "meal_transport_l": meal_transport_l_in,
                "meal_transport_d": meal_transport_d_in,
                "meal_transport_t": meal_transport_t_in,

                "simple_average_basic_include": simple_average_basic_include_in,
                "simple_average_enge_include": simple_average_enge_include_in,
                "simple_average_total_include": simple_average_total_include_in,
                "simple_average_basic_without": simple_average_basic_without_in,
                "simple_average_enge_without": simple_average_enge_without_in,
                "simple_average_total_without": simple_average_total_without_in,
            },
        }

    return render(request, template_name="sales_price_management.html", context=context)


# 請求書の登録 --------------------------------------------------------
def convert_invoice_userid_to_parent(userid: str) -> str:
    for target in settings.CONVERT_INVERT_USERID_TO_PARENTS:
        if userid == target:
            return '9' + userid
    return userid

def invoice_upload(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':

        form = InvoiceFilesForm(request.POST, request.FILES)

        if form.is_valid():

            pdf_files = request.FILES.getlist('document_file')

            for file in pdf_files:

                userid = re.match('^\d*', file.name).group()
                userid = re.sub('^0(.*)', '\\1', userid)
                user = User.objects.filter(username=userid, is_parent=True).first()
                if user:
                    # 親会社のuseridなので、そのまま使用
                    pass
                else:
                    userid = re.sub('^9(\d{5})', '\\1', userid)

                    userid = convert_invoice_userid_to_parent(userid)

                invoice_file = InvoiceFiles(
                    document_file=file,
                    username_id=userid,
                )
                invoice_file.save()

            messages.success(request, '請求書ファイルを一括登録しました。')

        context = {
            "form": form,
            "pdf_file": userid,
        }

    else:
        form = InvoiceFilesForm()
        context = {
            "form": form,
        }

    return render(request, template_name="invoice_upload.html", context=context)


class InvoiceList(ListView):
    model = InvoiceFiles
    template_name = 'invoice_list.html'

    def get_queryset(self):
        qs = InvoiceFiles.objects.filter(username=self.request.user) \
            .order_by('-updated_at')
        return qs

    def get(self, request, *args, **kwargs):
        token = request.session.pop('onetime_token', None)
        if token:
            return super(InvoiceList, self).get(request, *args, **kwargs)
        else:
            return redirect("web_order:index")


# P7対応(ラベル印刷用CSV出力) ----------------------------------------------------
def index_to_menu_type(raw_index: int):
    if raw_index == 1:
        return '基本食', '通常'
    if raw_index == 2:
        return '基本食', 'アレルギー'
    if raw_index == 3:
        return '基本食', 'サンプル'

    if raw_index == 4:
        return 'ソフト', '通常'
    if raw_index == 5:
        return 'ソフト', 'アレルギー'
    if raw_index == 6:
        return 'ソフト', 'サンプル'

    if raw_index == 7:
        return 'ゼリー', '通常'
    if raw_index == 8:
        return 'ゼリー', 'アレルギー'
    if raw_index == 9:
        return 'ゼリー', 'サンプル'

    if raw_index == 10:
        return 'ミキサー', '通常'
    if raw_index == 11:
        return 'ミキサー', 'アレルギー'
    if raw_index == 12:
        return 'ミキサー', 'サンプル'

    raise ValueError('インデックス不正')


def p7_source_upload(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    ImportP7FileFormSet = modelformset_factory(ImportP7SourceFile, form=ImportP7FileForm, extra=12)
    if request.method == 'POST':

        formset = ImportP7FileFormSet(request.POST, request.FILES)
        for index, form in enumerate(formset):
            if form.is_valid():
                if form.instance.document_file.name:
                    res_cooking_day_match = re.findall('^\d{6}', form.instance.document_file.name)
                    if res_cooking_day_match:
                        cooking_day = dt.datetime.strptime(res_cooking_day_match[0], '%y%m%d')
                        form.instance.cooking_day = cooking_day
                        form.instance.file_type_no = index + 1
                    else:
                        cooking_day = None
                    form.instance.file_type_no = index + 1
                    menu_name, menu_type = index_to_menu_type(form.instance.file_type_no)
                    if (not cooking_day) and (menu_type == 'アレルギー'):
                        messages.error(request, f'ファイル「{form.instance.document_file.name}」の登録に失敗しました。アレルギー献立は製造日指定のあるファイルをアップロードしてください。')
                    else:
                        form.save()
                        filename = form.instance.document_file

                        invalid_plates = []
                        try:
                            # トランザクション
                            with transaction.atomic():
                                # ファイル読込処理
                                reader = P7SourceFileReader(filename)
                                invalid_plates = reader.read(form.instance.file_type_no, menu_name, menu_type, cooking_day)
                                if invalid_plates:
                                    raise ValueError('max length invalid.')

                                messages.success(request, f'ファイル「{filename}」を登録しました。')
                        except ValueError:
                            messages.error(request, f'ファイル「{filename}」で文字数オーバーを検出しました。')
                            for plate, invalid_name, line, over in invalid_plates:
                                messages.warning(request, f'{line}番目の料理、「{plate}」の{invalid_name}で半角{over}文字分超過')
                else:
                    # ファイル名なし=アップロードしない
                    pass
            else:
                return HttpResponse('登録に失敗しました。', status=500)

        form2 = OutputP7FileForm()
        context = {
            "formset": formset,
            "output_form": form2
        }

    else:
        form2 = OutputP7FileForm()
        formset = ImportP7FileFormSet(None, queryset=ImportP7SourceFile.objects.none())
        context = {
            "formset": formset,
            "output_form": form2
        }

    return render(request, template_name="print_csv_output.html", context=context)


def p7_csv_output(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    ImportP7FileFormSet = modelformset_factory(ImportP7SourceFile, form=ImportP7FileForm, extra=12)

    if request.method == "POST":
        form2 = OutputP7FileForm(request.POST)

        if form2.is_valid():
            cooking_day = form2.cleaned_data['cooking_date']

            # CSVファイル検索
            writer = P7CsvFileWriter()
            writer.write_csv(cooking_day)

            messages.success(request, 'ファイルを出力しました。')
            last_modify = PlatePackageForPrint.objects.filter(cooking_day=cooking_day).order_by('-updated_at').first()
            logger.info(f'最終データ更新日時：{last_modify.updated_at.strftime("%Y/%m/%d %H:%M:%S")}')
            logger.info(f'帳票出力完了(P7用CSV)-{cooking_day}製造')

    formset = ImportP7FileFormSet(None, queryset=ImportP7SourceFile.objects.none())
    form2 = OutputP7FileForm()
    context = {
        "formset": formset,
        "output_form": form2
    }

    return render(request, template_name="print_csv_output.html", context=context)




# コントロールパネル ----------------------------------------------------
def control_panel(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    # 未確認チャットメッセージの有無を判断
    qs = Chat.objects.filter(is_sendto=False, is_read=False)
    if qs.exists():
        messages.info(request, '未確認のチャットメッセージがあります')

    date_time_now = dt.datetime.now()  # 現在の日時と時刻

    # 直近の1週間分の仮発注期間を取得
    from_date = get_next_next_tuesday(date_time_now).date()  # 仮注文が可能な直近の喫食日
    to_date = from_date + timedelta(days=6)  # 1画面に表示する日数(１週間分）

    # さらにもう一週前の仮発注期間を取得
    last_from_date = from_date - timedelta(days=7)
    last_to_date = last_from_date + timedelta(days=6)  # 1画面に表示する日数(１週間分）

    # 直近1週間で未発注の施設を取得する(アレルギー以外の注文の発注有無を確認する)
    this_week = Order.objects\
        .filter(eating_day__range=[from_date, to_date], unit_name__is_active=True, allergen=1) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .values('unit_name__unit_name') \
        .annotate(qt_sum=Sum('quantity')) \
        .order_by('unit_name__username_id')

    ignore_this_week = Order.objects\
        .filter(eating_day__range=[from_date, to_date], unit_name__is_active=True, quantity=0, allergen=1) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .select_related('unit_name')

    list_this_week = list(this_week)
    for ignore in ignore_this_week:
        for i, this_week_order in enumerate(list_this_week):
            if this_week_order['unit_name__unit_name'] == ignore.unit_name.unit_name:
                list_this_week.pop(i)
                break

    # さらに1週前の未発注の施設を取得する(アレルギー以外の注文の発注有無を確認する)
    last_week = Order.objects\
        .filter(eating_day__range=[last_from_date, last_to_date], unit_name__is_active=True, allergen=1) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .values('unit_name__unit_name') \
        .annotate(qt_sum=Sum('quantity')) \
        .order_by('unit_name__username_id')

    ignore_last_week = Order.objects\
        .filter(eating_day__range=[last_from_date, last_to_date], unit_name__is_active=True, quantity=0, allergen=1) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .select_related('unit_name')

    list_last_week = list(last_week)
    for ignore in ignore_last_week:
        for i, last_week_order in enumerate(list_last_week):
            if last_week_order['unit_name__unit_name'] == ignore.unit_name.unit_name:
                list_last_week.pop(i)
                break

    # 画面上は使用していない
    queryset = Order.objects\
        .filter(unit_name__username_id=910090, allergen=1, eating_day__range=[from_date, to_date], unit_name__is_active=True) \
        .values('meal_name__meal_name') \
        .annotate(qt_sum=Count('meal_name')) \
        .order_by('meal_name__seq_order')

    form = ExecForm()
    month_form = ExecMonthForm()
    import_form = ImportMenuNameForm()
    convert_form = ConvertCookingDirectionForm()

    _, ck_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "rakukon"))
    ck_files = natsorted(ck_files, reverse=True)
    cooking_url = os.path.join(settings.MEDIA_URL, 'output', "rakukon")

    _, ms_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "measure"))
    ms_files = natsorted(ms_files, reverse=True)
    measure_url = os.path.join(settings.MEDIA_URL, 'output', "measure")

    _, iv_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "invoice"))
    iv_files = natsorted(iv_files, reverse=True)
    invoice_url = os.path.join(settings.MEDIA_URL, 'output', "invoice")

    _, lbl_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "label"))
    lbl_files = natsorted(lbl_files, reverse=True)
    label_url = os.path.join(settings.MEDIA_URL, 'output', "label")

    context = {
        "from_date": from_date,
        "to_date": to_date,
        "this_week": list_this_week,

        "last_from_date": last_from_date,
        "last_to_date": last_to_date,
        "last_week": list_last_week,

        "queryset": queryset,

        "cooking_files": ck_files,
        "cooking_url": cooking_url,
        "measure_files": ms_files,
        "measure_url": measure_url,
        "invoice_files": iv_files,
        "invoice_url": invoice_url,
        "label_files": lbl_files,
        "label_url": label_url,

        "convert_form": convert_form,
        "import_form": import_form,
        "form": form,
        "month_form": month_form,
    }

    return render(request, template_name="control_panel.html", context=context)


# 変換後調理表一覧ページ
def converted_cooking_direction_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    direction_type = request.GET.get('direction_type', 'normal')
    if direction_type == 'normal':
        _, all_cooking_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "converted_cook"))
    else:
        _, all_cooking_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "converted_cook_filter"))

    all_cooking_files = natsorted(all_cooking_files, reverse=True)
    if direction_type == 'normal':
        cooking_url = os.path.join(settings.MEDIA_URL, 'output', "converted_cook")
    else:
        cooking_url = os.path.join(settings.MEDIA_URL, 'output', "converted_cook_filter")

    context = {
        "cooking_files": all_cooking_files,
        "cooking_url": cooking_url,
        "direction_type": direction_type,
    }

    return render(request, template_name="converted_cooking_files.html", context=context)


# 食数集計表一覧ページ
def cooking_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_cooking_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "rakukon"))
    all_cooking_files = natsorted(all_cooking_files, reverse=True)
    cooking_url = os.path.join(settings.MEDIA_URL, 'output', "rakukon")

    context = {
        "cooking_files": all_cooking_files,
        "cooking_url": cooking_url,
    }

    return render(request, template_name="cooking_files.html", context=context)


def is_exclude_start_meal(meal, exclude_meal):
    if exclude_meal == '朝食':
        return False
    elif exclude_meal == '昼食':
        return meal == '朝食'
    else:
        return meal in ['昼食', '朝食']


def is_exclude_end_meal(meal, exclude_meal):
    if exclude_meal == '夕食':
        return False
    elif exclude_meal == '昼食':
        return meal == '夕食'
    else:
        return (meal == '昼食') or (meal== '夕食')


def is_exclude(eating_day, meal_name, from_date, to_date, start_meal, end_meal):
    if from_date == to_date:
        result_1 = is_exclude_start_meal(meal_name, start_meal)
        result_2 = is_exclude_end_meal(meal_name, end_meal)
        return is_exclude_start_meal(meal_name, start_meal) or is_exclude_end_meal(meal_name, end_meal)

    if eating_day == from_date:
        return is_exclude_start_meal(meal_name, start_meal)
    elif eating_day == to_date:
        return is_exclude_end_meal(meal_name, end_meal)


def is_exclude_by_order(target_order, from_date, to_date, start_meal, end_meal):
    return is_exclude(target_order.eating_day, target_order.meal_name.meal_name, from_date, to_date, start_meal, end_meal)


def get_sort_index(unit_number):
    try:
        index = settings.AGGREGATE_UNIT_SORT_ORDER.index(unit_number)
        return index
    except ValueError:
        # 定義配列に存在しないものは最後尾で、その中でもunit_number順になる値を返却
        # unit_numberが最大でも3桁までしか使われない前提
        index = 1000+unit_number
        return index

def compare_unit(order1, order2):
    # 呼び出し番号でのソート
    comp_unit_number = order1.unit_name.unit_number - order2.unit_name.unit_number
    if comp_unit_number:
        return comp_unit_number
    else:
        name1 = order1.unit_name.calc_name or order1.unit_name.unit_name
        name2 = order2.unit_name.calc_name or order2.unit_name.unit_name
        is_special_1 = ('個食' in name1) or ('フリーズ' in name1) or ('検食用' in name1)
        is_special_2 = ('個食' in name2) or ('フリーズ' in name2) or ('検食用' in name2)
        if is_special_1 == is_special_2:
            if name1 > name2:
                return 1
            elif name1 < name2:
                return -1
            else:
                return 0
        elif is_special_1 and (not is_special_2):
            return 1
        elif is_special_2 and (not is_special_1):
            return -1

# 集計確認画面の献立種類の並び順(配列のindexは存在しないものを渡すと例外が発生するため、全ての内容を記載しておくこと)
AGGREGATE_MENU_SORT_ORDER = ['常食', 'ソフト', 'ミキサー', 'ゼリー', '薄味', '検食']
def compare_aggregate_order(order1, order2):
    # ユニットによるソート
    comp_unit = compare_unit(order1, order2)
    if comp_unit:
        return comp_unit
    else:
        # 献立種類によるソート
        menu_name_index_1 = AGGREGATE_MENU_SORT_ORDER.index(order1.menu_name.menu_name)
        menu_name_index_2 = AGGREGATE_MENU_SORT_ORDER.index(order2.menu_name.menu_name)
        comp_menu = menu_name_index_1 - menu_name_index_2
        if comp_menu:
            return comp_menu
        else:
            return order1.id - order2.id


AGGREGATE_MEAL_SORT_ORDER = ['朝食', '昼食', '夕食']
def compare_aggregate_allergen(order1, order2):
    # 喫食日によるソート
    if order1.eating_day > order2.eating_day:
        return 1
    elif order1.eating_day < order2.eating_day:
        return -1
    else:
        comp_unit = compare_unit(order1, order2)
        if comp_unit:
            return comp_unit
        else:
            # 食事区分によるソート
            meal_name_index_1 = AGGREGATE_MEAL_SORT_ORDER.index(order1.meal_name.meal_name)
            meal_name_index_2 = AGGREGATE_MEAL_SORT_ORDER.index(order2.meal_name.meal_name)
            comp = meal_name_index_1 - meal_name_index_2
            if comp:
                return comp
            else:
                # 献立種類によるソート
                menu_name_index_1 = AGGREGATE_MENU_SORT_ORDER.index(order1.menu_name.menu_name)
                menu_name_index_2 = AGGREGATE_MENU_SORT_ORDER.index(order2.menu_name.menu_name)
                return menu_name_index_1 - menu_name_index_2


# 集計確認画面の固定分の並び順
AGGREGATE_UNIT_SORT_ORDER_EVEYDAY = ['針刺し', '保存', '保存1人袋', '保存50g', '見本', '針刺し用']
def compare_aggregate_order_everyday(order1, order2):
    # ユニットによるソート
    unit_name_index_1 = AGGREGATE_UNIT_SORT_ORDER_EVEYDAY.index(order1.unit_name.unit_name)
    unit_name_index_2 = AGGREGATE_UNIT_SORT_ORDER_EVEYDAY.index(order2.unit_name.unit_name)
    comp_unit = unit_name_index_1 - unit_name_index_2
    if comp_unit:
        return comp_unit
    else:
        # 献立種類によるソート
        menu_name_index_1 = AGGREGATE_MENU_SORT_ORDER.index(order1.menu_name.menu_name)
        menu_name_index_2 = AGGREGATE_MENU_SORT_ORDER.index(order2.menu_name.menu_name)
        comp_menu = menu_name_index_1 - menu_name_index_2
        if comp_menu:
            return comp_menu
        else:
            return order1.id - order2.id


class BaseSoupCounter:
    def __init__(self):
        # カウンタは乾燥と冷凍で施設を分けてカウント
        self.g_b_l = {"dry": [0, 0, 0], "cold": [0, 0, 0]}     # 具のみ 朝・昼
        self.g_l_d = {"dry": [0, 0, 0], "cold": [0, 0, 0]}     # 具のみ 昼・夕
        self.g_b_d = {"dry": [0, 0, 0], "cold": [0, 0, 0]}     # 具のみ 朝・夕

        self.sg_b_l = {"dry": [0, 0, 0], "cold": [0, 0, 0]}    # 汁と具 朝・昼
        self.sg_l_d = {"dry": [0, 0, 0], "cold": [0, 0, 0]}    # 汁と具 昼・夕
        self.sg_b_d = {"dry": [0, 0, 0], "cold": [0, 0, 0]}    # 汁と具 朝・夕

        self.g_b_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 具のみ 朝1回
        self.g_l_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 具のみ 昼1回
        self.g_d_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 具のみ 夕1回

        self.sg_b_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 汁と具 朝1回
        self.sg_l_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 汁と具 昼1回
        self.sg_d_1 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}  # 汁と具 夕1回

        self.g_3 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}       # 具のみ3回
        self.sg_3 = {"dry": [0, 0, 0], "cold": [0, 0, 0]}      # 汁と具3回
        self.s_none = {"dry": [0, 0, 0], "cold": [0, 0, 0]}    # 汁なし


class JoshokuSoupCounter(BaseSoupCounter):
    def add(self, target_order, meal, menu, quantity, manager):
        # アレルギーも集計に含める

        number = target_order.unit_name.unit_number
        if meal == '朝食':
            index = 0
        elif meal == '昼食':
            index = 1
        else:
            index = 2

        if number == 999:
            self.sg_3['cold'][index] += quantity
        elif '木沢・個食' in target_order.unit_name.unit_name:
            pass
        elif 'フリーズ' in target_order.unit_name.unit_name:
            pass
        else:
            user = target_order.unit_name.username
            contract = manager.get_user_contract(user).get_soup_contract_name(menu)
            if user.dry_cold_type == '乾燥':
                dry_cold_key = 'dry'
            else:
                dry_cold_key = 'cold'

            if contract == '汁と具　3回':
                self.sg_3[dry_cold_key][index] += quantity
            elif contract == '具のみ　3回':
                self.g_3[dry_cold_key][index] += quantity
            elif contract == '汁無し':
                self.s_none[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・昼':
                self.sg_b_l[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　昼・夕':
                self.sg_l_d[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・夕':
                self.sg_b_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・昼':
                self.g_b_l[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　昼・夕':
                self.g_l_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・夕':
                self.g_b_d[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　朝食':
                self.sg_b_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　昼食':
                self.sg_l_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　夕食':
                self.sg_d_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　朝食':
                self.g_b_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　昼食':
                self.g_l_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　夕食':
                self.g_d_1[dry_cold_key][index] += quantity


class UsuajiSoupCounter(BaseSoupCounter):
    def add(self, target_order, meal, menu, quantity, manager):
        none


class SoftSoupCounter(BaseSoupCounter):
    def add(self, target_order, meal, menu, quantity, manager):
        # アレルギーも集計に含める

        number = target_order.unit_name.unit_number
        if meal == '朝食':
            index = 0
        elif meal == '昼食':
            index = 1
        else:
            index = 2

        if number == 999:
            if ('針刺し' in target_order.unit_name.unit_name) or ('保存' in target_order.unit_name.unit_name):
                # 汁と具3回(冷凍にカウントする)
                self.sg_3['cold'][index] += quantity
        else:
            user = target_order.unit_name.username
            contract = manager.get_user_contract(user).get_soup_contract_name(menu)
            if user.dry_cold_type == '乾燥':
                dry_cold_key = 'dry'
            else:
                dry_cold_key = 'cold'

            if contract == '汁と具　3回':
                self.sg_3[dry_cold_key][index] += quantity
            elif contract == '具のみ　3回':
                self.g_3[dry_cold_key][index] += quantity
            elif contract == '汁無し':
                self.s_none[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・昼':
                self.sg_b_l[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　昼・夕':
                self.sg_l_d[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・夕':
                self.sg_b_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・昼':
                self.g_b_l[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　昼・夕':
                self.g_l_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・夕':
                self.g_b_d[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　朝食':
                self.sg_b_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　昼食':
                self.sg_l_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　夕食':
                self.sg_d_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　朝食':
                self.g_b_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　昼食':
                self.g_l_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　夕食':
                self.g_d_1[dry_cold_key][index] += quantity


class MixerSoupCounter(BaseSoupCounter):
    def add(self, target_order, meal, menu, quantity, manager):
        # アレルギーも集計に含める

        number = target_order.unit_name.unit_number
        if meal == '朝食':
            index = 0
        elif meal == '昼食':
            index = 1
        else:
            index = 2

        if number == 999:
            if ('針刺し' in target_order.unit_name.unit_name) or ('保存' in target_order.unit_name.unit_name):
                # 汁と具3回(冷凍にカウントする)
                self.sg_3['cold'][index] += quantity
        else:
            user = target_order.unit_name.username
            contract = manager.get_user_contract(user).get_soup_contract_name(menu)
            if user.dry_cold_type == '乾燥':
                dry_cold_key = 'dry'
            else:
                dry_cold_key = 'cold'

            if contract == '汁と具　3回':
                self.sg_3[dry_cold_key][index] += quantity
            elif contract == '具のみ　3回':
                self.g_3[dry_cold_key][index] += quantity
            elif contract == '汁無し':
                self.s_none[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・昼':
                self.sg_b_l[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　昼・夕':
                self.sg_l_d[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・夕':
                self.sg_b_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・昼':
                self.g_b_l[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　昼・夕':
                self.g_l_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・夕':
                self.g_b_d[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　朝食':
                self.sg_b_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　昼食':
                self.sg_l_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　夕食':
                self.sg_d_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　朝食':
                self.g_b_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　昼食':
                self.g_l_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　夕食':
                self.g_d_1[dry_cold_key][index] += quantity


class JellySoupCounter(BaseSoupCounter):
    def add(self, target_order, meal, menu, quantity, manager):
        # アレルギーも集計に含める

        number = target_order.unit_name.unit_number
        if meal == '朝食':
            index = 0
        elif meal == '昼食':
            index = 1
        else:
            index = 2

        if number == 999:
            if ('針刺し' in target_order.unit_name.unit_name) or ('保存' in target_order.unit_name.unit_name):
                # 汁と具3回(冷凍にカウントする)
                self.sg_3['cold'][index] += quantity
        else:
            user = target_order.unit_name.username
            contract = manager.get_user_contract(user).get_soup_contract_name(menu)
            if user.dry_cold_type == '乾燥':
                dry_cold_key = 'dry'
            else:
                dry_cold_key = 'cold'

            if contract == '汁と具　3回':
                self.sg_3[dry_cold_key][index] += quantity
            elif contract == '具のみ　3回':
                self.g_3[dry_cold_key][index] += quantity
            elif contract == '汁無し':
                self.s_none[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・昼':
                self.sg_b_l[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　昼・夕':
                self.sg_l_d[dry_cold_key][index] += quantity
            elif contract == '汁具　2回　朝・夕':
                self.sg_b_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・昼':
                self.g_b_l[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　昼・夕':
                self.g_l_d[dry_cold_key][index] += quantity
            elif contract == '具のみ　2回　朝・夕':
                self.g_b_d[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　朝食':
                self.sg_b_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　昼食':
                self.sg_l_1[dry_cold_key][index] += quantity
            elif contract == '汁具　1回　夕食':
                self.sg_d_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　朝食':
                self.g_b_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　昼食':
                self.g_l_1[dry_cold_key][index] += quantity
            elif contract == '具のみ　1回　夕食':
                self.g_d_1[dry_cold_key][index] += quantity


class SoupCounter:
    def __init__(self):
        self.contract_manager = ContractManager()
        self.contract_manager.read_all()
        self.jsc = JoshokuSoupCounter()
        self.usc = UsuajiSoupCounter()
        self.ssc = SoftSoupCounter()
        self.msc = MixerSoupCounter()
        self.zsc = JellySoupCounter()
        self.freeze_counter = [0, 0, 0]
        self.koshoku_counter = [0, 0, 0]

    def add(self, target_order):
        if not target_order.quantity:
            return

        meal = target_order.meal_name.meal_name
        menu = target_order.menu_name.menu_name

        # フリーズ・個食の集計
        # 個食を別集計するのは、木沢・個食のみ。他の個食は常食にカウント
        if 'フリーズ' in target_order.unit_name.unit_name:
            self.add_freeze(meal, target_order.quantity)
            return
        elif '木沢・個食' in target_order.unit_name.unit_name:
            self.add_koshoku(meal, target_order.quantity)
            return

        if menu == '常食':
            self.jsc.add(target_order, meal, menu, target_order.quantity, self.contract_manager)
        elif menu == '薄味':
            self.usc.add(target_order, meal, menu, target_order.quantity, self.contract_manager)
        elif menu == 'ソフト':
            self.ssc.add(target_order, meal, menu, target_order.quantity, self.contract_manager)
        elif menu == 'ミキサー':
            self.msc.add(target_order, meal, menu, target_order.quantity, self.contract_manager)
        elif menu == 'ゼリー':
            self.zsc.add(target_order, meal, menu, target_order.quantity, self.contract_manager)

    def add_freeze(self, meal, quantity):
        if meal == '朝食':
            self.freeze_counter[0] += quantity
        elif meal == '昼食':
            self.freeze_counter[1] += quantity
        elif meal == '夕食':
            self.freeze_counter[2] += quantity

    def add_koshoku(self, meal, quantity):
        if meal == '朝食':
            self.koshoku_counter[0] += quantity
        elif meal == '昼食':
            self.koshoku_counter[1] += quantity
        elif meal == '夕食':
            self.koshoku_counter[2] += quantity

    def add_for_everyday(self, target_order, meal, quantity, eating_day):
        if not quantity:
            return

        menu = target_order.menu_name.menu_name
        if menu == '常食':
            self.jsc.add(target_order, meal, menu, quantity, self.contract_manager)
        elif menu == '薄味':
            if eating_day < dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date():
                self.usc.add(target_order, meal, menu, quantity, self.contract_manager)
            else:
                self.jsc.add(target_order, meal, menu, quantity, self.contract_manager)
        elif menu == 'ソフト':
            self.ssc.add(target_order, meal, menu, quantity, self.contract_manager)
        elif menu == 'ミキサー':
            self.msc.add(target_order, meal, menu, quantity, self.contract_manager)
        elif menu == 'ゼリー':
            self.zsc.add(target_order, meal, menu, quantity, self.contract_manager)


def adjust_fix_saving(object_list, eating_day):
    if eating_day < dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date():
        return object_list

    # 保存用の調整
    saving_basic = None
    saving_usuaji = None
    for x in object_list:
        model = x.model
        if (model.unit_name.unit_number == 999) and (model.unit_name.unit_name == '保存'):
            if model.menu_name.menu_name == '常食':
                saving_basic = x
            elif model.menu_name.menu_name == '薄味':
                saving_usuaji = x

            if saving_basic and saving_usuaji:
                # 両方検出できたらループを抜ける
                break

    if saving_basic and saving_usuaji:
        saving_basic.morning += saving_usuaji.morning
        saving_basic.lunch += saving_usuaji.lunch
        saving_basic.dinner += saving_usuaji.dinner

    # 食数固定分以外に薄味が混ざることはない前提
    return [x for x in object_list if x.model.menu_name.menu_name != '薄味']

# 注文食数確認ページ
def cooking_produce(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    form = AggrigationSearchForm(request.GET)
    if form.is_valid():
        from_date = form.cleaned_data['start_date']
        to_date = form.cleaned_data['end_date']
        start_meal = form.cleaned_data['start_meal']
        end_meal = form.cleaned_data['end_meal']
    else:
        form = AggrigationSearchForm()
        today = dt.datetime.now().date()
        from_date = today
        to_date = today
        start_meal = '朝食'
        end_meal = '夕食'

    # 食数詳細
    breakfast_total = 0
    lunch_total = 0
    dinner_total = 0
    soup_counter = SoupCounter()

    # 通常注文の情報を取得
    qs = Order.objects\
        .filter(eating_day__range=[from_date, to_date], quantity__gt=0, unit_name__is_active=True) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen')
    object_list = []
    sorted_qs = sorted(qs, key=cmp_to_key(compare_aggregate_order))

    # 同一ユニット、同一献立種類で情報をまとめる
    for key, group in groupby(sorted_qs, key=lambda x: (x.unit_name.calc_name, x.menu_name.menu_name)):
        obj = next(group)

        # 検索指定範囲外のOrderを除外(初回)
        while is_exclude_by_order(obj, from_date, to_date, start_meal, end_meal):
            try:
                obj = next(group)
            except StopIteration:
                obj = None
                break
        if not obj:
            continue

        # 朝、昼、夕の食数を計算
        breakfast = 0
        lunch = 0
        dinner = 0
        if obj.meal_name.meal_name == '朝食':
            breakfast = obj.quantity
        elif obj.meal_name.meal_name == '昼食':
            lunch = obj.quantity
        elif obj.meal_name.meal_name == '夕食':
            dinner = obj.quantity
        soup_counter.add(obj)

        for x in group:
            # 検索指定範囲外のOrderを除外(初回以降)
            if is_exclude_by_order(x, from_date, to_date, start_meal, end_meal):
                continue
            if x.meal_name.meal_name == '朝食':
                breakfast += x.quantity
            elif x.meal_name.meal_name == '昼食':
                lunch += x.quantity
            elif x.meal_name.meal_name == '夕食':
                dinner += x.quantity
            soup_counter.add(x)

        # 全体の食数に反映
        breakfast_total += breakfast
        lunch_total += lunch
        dinner_total += dinner

        # 一覧に追加
        object_list.append(AggregateOrder(obj, breakfast, lunch, dinner))


    # 固定分追加
    # 固定分の乗数を計算
    eating_day = from_date
    times_list = [0, 0, 0]  # 各固定分を何倍するかの情報(日数分計上するための情報)
    while eating_day <= to_date:
        times_list[0] += 1
        times_list[1] += 1
        times_list[2] += 1
        eating_day += timedelta(days=1)
    if start_meal == '昼食':
        times_list[0] -= 1
    elif start_meal == '夕食':
        times_list[0] -= 1
        times_list[1] -= 1
    if end_meal == '朝食':
        times_list[1] -= 1
        times_list[2] -= 1
    elif end_meal == '昼食':
        times_list[2] -= 1

    # 固定注文の情報を取得
    qs_everyday = OrderEveryday.objects\
        .filter(unit_name__unit_name__in=['針刺し', '保存', '保存1人袋', '保存50g', '見本', '針刺し用'])\
        .select_related('unit_name', 'meal_name', 'menu_name')
    sorted_qs_everyday = sorted(qs_everyday, key=cmp_to_key(compare_aggregate_order_everyday))

    # 同一ユニット、同一献立種類で情報をまとめる(固定注文は合算名称がない)
    for key, group in groupby(sorted_qs_everyday, key=lambda x: (x.unit_name, x.menu_name.menu_name)):
        obj = next(group)

        # 朝、昼、夕の食数を計算
        breakfast = 0
        lunch = 0
        dinner = 0
        if obj.meal_name.meal_name == '朝食':
            breakfast = obj.quantity
        elif obj.meal_name.meal_name == '昼食':
            lunch = obj.quantity
        elif obj.meal_name.meal_name == '夕食':
            dinner = obj.quantity
        for x in group:
            if x.meal_name.meal_name == '朝食':
                breakfast += x.quantity
            elif x.meal_name.meal_name == '昼食':
                lunch += x.quantity
            elif x.meal_name.meal_name == '夕食':
                dinner += x.quantity

        # 乗数を反映
        breakfast = breakfast * times_list[0]
        lunch = lunch * times_list[1]
        dinner = dinner * times_list[2]

        # 全体の食数に反映
        breakfast_total += breakfast
        lunch_total += lunch
        dinner_total += dinner

        # 一覧に追加(modelが違うのでコンバート)
        order_for_display = Order(
            eating_day=obj.eating_day,
            unit_name=obj.unit_name,
            meal_name=obj.meal_name,
            menu_name=obj.menu_name,
            allergen=obj.allergen,
        )
        order_for_display.unit_name.unit_number = 999
        object_list.append(AggregateOrder(order_for_display, breakfast, lunch, dinner))

        soup_counter.add_for_everyday(order_for_display, '朝食', breakfast, eating_day)
        soup_counter.add_for_everyday(order_for_display, '昼食', lunch, eating_day)
        soup_counter.add_for_everyday(order_for_display, '夕食', dinner, eating_day)

    # アレルギー情報
    qs2 = Order.objects\
        .filter(eating_day__range=[from_date, to_date], quantity__gt=0, allergen_id__gte=2, unit_name__is_active=True) \
        .exclude(unit_name__unit_code__range=[80001, 80008]) \
        .select_related('unit_name', 'meal_name', 'menu_name', 'allergen') \
        .order_by('eating_day', 'unit_name__unit_number', 'menu_name__menu_name', 'allergen')
    sorted_qs2 = sorted(qs2, key=cmp_to_key(compare_aggregate_allergen))
    allergen_list = [x for x in sorted_qs2 if not is_exclude_by_order(x, from_date, to_date, start_meal, end_meal)]

    context = {
        "object_list": adjust_fix_saving(object_list, eating_day),
        "allergen_list": allergen_list,
        "search_form": form,
        "meals_total": (breakfast_total, lunch_total, dinner_total),
        "total": breakfast_total + lunch_total + dinner_total,
        "j_soup": soup_counter.jsc,
        "u_soup": soup_counter.usc,
        "s_soup": soup_counter.ssc,
        "m_soup": soup_counter.msc,
        "z_soup": soup_counter.zsc,
        "freeze_counter": soup_counter.freeze_counter,
        "koshoku_counter": soup_counter.koshoku_counter,
    }

    return render(request, template_name="order_aggregation_list.html", context=context)


# 注文食数エクスポート
def cooking_produce_export(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    form = AggrigationSearchForm(request.GET)
    if form.is_valid():
        from_date = form.cleaned_data['start_date']
        to_date = form.cleaned_data['end_date']
        start_meal = form.cleaned_data['start_meal']
        end_meal = form.cleaned_data['end_meal']
        logger.info(f'食数-export:{from_date}({start_meal})-{to_date}({end_meal})')
    else:
        soup_counter = SoupCounter()
        context = {
            "object_list": [],
            "allergen_list": [],
            "search_form": form,
            "meals_total": (0, 0, 0),
            "total": 0,
            "j_soup": soup_counter.jsc,
            "u_soup": soup_counter.usc,
            "s_soup": soup_counter.ssc,
            "m_soup": soup_counter.msc,
            "z_soup": soup_counter.zsc,
        }
        return render(request, template_name="order_aggregation_list.html", context=context)

    service = CookingProduceExporter()
    eating_day = from_date
    soup_counter = SoupCounter()
    while eating_day <= to_date:
        # 通常注文の情報を取得(エクスポートしやすいように0も含めて取得)
        qs = Order.objects\
            .filter(eating_day=eating_day, unit_name__is_active=True) \
            .exclude(unit_name__unit_code__range=[80001, 80008]) \
            .exclude(quantity__lt=0) \
            .select_related('unit_name', 'meal_name', 'menu_name', 'allergen')
        object_list = []
        sorted_qs = sorted(qs, key=cmp_to_key(compare_aggregate_order))

        # 同一ユニット、同一献立種類で情報をまとめる
        for key, group in groupby(sorted_qs, key=lambda x: (x.unit_name.calc_name, x.menu_name.menu_name)):
            obj = next(group)

            # 検索指定範囲外のOrderを除外(初回)
            try:
                while is_exclude_by_order(obj, from_date, to_date, start_meal, end_meal):
                    obj = next(group)
            except StopIteration:
                continue

            # 朝、昼、夕の食数を計算
            breakfast = 0
            lunch = 0
            dinner = 0
            if obj.meal_name.meal_name == '朝食':
                breakfast = obj.quantity or 0
            elif obj.meal_name.meal_name == '昼食':
                lunch = obj.quantity or 0
            elif obj.meal_name.meal_name == '夕食':
                dinner = obj.quantity or 0
            #soup_counter.add(obj)

            for x in group:
                # 検索指定範囲外のOrderを除外(初回以降)
                if is_exclude_by_order(x, from_date, to_date, start_meal, end_meal):
                    continue
                if x.meal_name.meal_name == '朝食':
                    breakfast += x.quantity or 0
                elif x.meal_name.meal_name == '昼食':
                    lunch += x.quantity or 0
                elif x.meal_name.meal_name == '夕食':
                    dinner += x.quantity or 0
                #soup_counter.add(x)

            # 一覧に追加
            object_list.append(AggregateOrder(obj, breakfast, lunch, dinner))

        # 固定注文の情報を取得
        # 本番環境に存在するユニット名(サンシティあい様検食用を除く)のみを抽出
        qs_everyday = OrderEveryday.objects\
        .filter(unit_name__unit_name__in=['針刺し', '保存', '保存1人袋', '保存50g', '見本', '針刺し用'])\
            .select_related('unit_name', 'meal_name', 'menu_name')
        sorted_qs_everyday = sorted(qs_everyday, key=cmp_to_key(compare_aggregate_order_everyday))

        # 同一ユニット、同一献立種類で情報をまとめる
        for key, group in groupby(sorted_qs_everyday, key=lambda x: (x.unit_name, x.menu_name.menu_name)):
            obj = next(group)
            while is_exclude(eating_day, obj.meal_name.meal_name, from_date, to_date, start_meal, end_meal):
                obj = next(group)

            # 朝、昼、夕の食数を計算
            breakfast = 0
            lunch = 0
            dinner = 0
            if obj.meal_name.meal_name == '朝食':
                breakfast = obj.quantity or 0
            elif obj.meal_name.meal_name == '昼食':
                lunch = obj.quantity or 0
            elif obj.meal_name.meal_name == '夕食':
                dinner = obj.quantity or 0
            for x in group:
                if is_exclude_by_order(x, from_date, to_date, start_meal, end_meal):
                    continue
                if x.meal_name.meal_name == '朝食':
                    breakfast += x.quantity or 0
                elif x.meal_name.meal_name == '昼食':
                    lunch += x.quantity or 0
                elif x.meal_name.meal_name == '夕食':
                    dinner += x.quantity or 0

            # 一覧に追加(modelが違うのでコンバート)
            order_for_display = Order(
                eating_day=obj.eating_day,
                unit_name=obj.unit_name,
                meal_name=obj.meal_name,
                menu_name=obj.menu_name,
                allergen=obj.allergen,
            )
            order_for_display.unit_name.unit_number = 999
            object_list.append(AggregateOrder(order_for_display, breakfast, lunch, dinner))
            #soup_counter.add_for_everyday(order_for_display, '朝食', breakfast, eating_day)
            #soup_counter.add_for_everyday(order_for_display, '昼食', lunch, eating_day)
            #soup_counter.add_for_everyday(order_for_display, '夕食', dinner, eating_day)

        #service.soup_counter = soup_counter
        service.pre_export(adjust_fix_saving(object_list, eating_day), eating_day, from_date, to_date, start_meal, end_meal)
        service.save(eating_day)
        eating_day += timedelta(days=1)

    messages.success(request, '製造作成表の出力が完了しました')
    return redirect('web_order:cooking_produce_files')


# 食数集計表一覧ページ
def cooking_produce_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_cooking_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "produce"))
    all_cooking_files = natsorted(all_cooking_files, reverse=True)
    cooking_url = os.path.join(settings.MEDIA_URL, 'output', "produce")

    context = {
        "cooking_files": all_cooking_files,
        "cooking_url": cooking_url,
    }

    return render(request, template_name="cooking_produce_files.html", context=context)


# 計量表一覧ページ
def measure_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_measure_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "measure"))
    all_measure_files = natsorted(all_measure_files, reverse=True)
    measure_url = os.path.join(settings.MEDIA_URL, 'output', "measure")

    context = {
        "measure_files": all_measure_files,
        "measure_url": measure_url,
    }

    return render(request, template_name="measure_files.html", context=context)

# 配送ラベル一覧ページ
def label_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_label_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "label"))
    all_label_files = natsorted(all_label_files, reverse=True)
    label_url = os.path.join(settings.MEDIA_URL, 'output', "label")

    context = {
        "label_files": all_label_files,
        "label_url": label_url,
    }

    return render(request, template_name="label_files.html", context=context)

# 盛付指示書一覧ページ(施設用)
def setout_files(request):

    all_setout_dirs, _ = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "setout"))
    all_setout_dirs = natsorted(all_setout_dirs, reverse=True)

    # 表示可能なディレクトリのリストを取得
    today = dt.datetime.now().date()
    enabels = [x.name for x in SetoutDuration.objects.filter(last_enable__gte=today, is_hide=False)]
    enabels += [f'{dir}(一枚表示)' for dir in enabels if f'{dir}(一枚表示)' in all_setout_dirs]
    enabels += [f'{dir}(おせち用)' for dir in enabels if f'{dir}(おせち用)' in all_setout_dirs]

    logger.debug(f'実ディレクトリ:{all_setout_dirs}')
    logger.debug(f'参照可能ファイル:{enabels}')
    display_setout_dirs = [x for x in all_setout_dirs if x in enabels]

    #setout_url = os.path.join(settings.MEDIA_URL, 'output', "setout")
    setout_url = reverse_lazy('web_order:setout_file_download')

    context = {
        "setout_files": display_setout_dirs,
        "setout_url": setout_url,
    }

    return render(request, template_name="setout_files.html", context=context)

# 盛付指示書一覧ページ(管理用)
def setout_files_manage(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    # 全ての盛付指示書を表示できるようにする
    all_setout_dirs, _ = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "setout"))
    all_setout_dirs = natsorted(all_setout_dirs, reverse=True)
    setout_url = reverse_lazy('web_order:setout_files_manage_download')

    context = {
        "setout_files": all_setout_dirs,
        "setout_url": setout_url,
    }

    return render(request, template_name="setout_files_manage.html", context=context)


# 盛付指示書ダウンロード
def setout_file_download(request):
    in_filename = request.GET['file']

    # 汁有無の判定
    has_contract_soup = MealDisplay.objects.filter(username=request.user, meal_name__filling=True).exists()

    # 嚥下有無の判定
    has_contract_enge = MenuDisplay.objects.filter(username=request.user, menu_name__menu_name__in=['ゼリー', 'ミキザー', 'ソフト']).exists()

    # ユーザの契約内容判定->ダウンロード対象ファイル決定
    if 'おせち用' in in_filename:
        if has_contract_soup and has_contract_enge:
            filename = f'{in_filename}.xlsx'
        elif has_contract_soup:
            filename = f'{in_filename}_noenge.xlsx'
        elif has_contract_enge:
            filename = f'{in_filename}.xlsx'
        else:
            filename = f'{in_filename}_noenge.xlsx'
    else:
        if has_contract_soup and has_contract_enge:
            filename = f'{in_filename}.xlsx'
        elif has_contract_soup:
            filename = f'{in_filename}_noenge.xlsx'
        elif has_contract_enge:
            filename = f'{in_filename}_nosoup.xlsx'
        else:
            filename = f'{in_filename}_only.xlsx'

    # 対象ファイル返却
    filepath = os.path.join(settings.OUTPUT_DIR, 'setout', in_filename, filename)
    return FileResponse(
        open(filepath, 'rb'), as_attachment=True, filename=f'{in_filename}.xlsx')


# 盛付指示書ダウンロード(管理者ページ用)
def setout_file_download_for_manage(request):
    in_filename = request.GET['file']

    filename = f'{in_filename}.xlsx'

    # 対象ファイル返却
    filepath = os.path.join(settings.OUTPUT_DIR, 'setout', in_filename, filename)
    return FileResponse(
        open(filepath, 'rb'), as_attachment=True, filename=f'{in_filename}.xlsx')

# 売価計算表一覧ページ
def sales_price_files(request):

    _, all_setout_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "sales"))
    all_sales_files = natsorted(all_setout_files, reverse=True)
    sales_url = os.path.join(settings.MEDIA_URL, 'output', "sales")

    context = {
        "sales_files": all_sales_files,
        "sales_url": sales_url,
    }

    return render(request, template_name="sales_files.html", context=context)

# 請求データ一覧ページ
def invoice_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_invoice_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "invoice"))
    all_invoice_files = natsorted(all_invoice_files, reverse=True)
    invoice_url = os.path.join(settings.MEDIA_URL, 'output', "invoice")

    context = {
        "invoice_files": all_invoice_files,
        "invoice_url": invoice_url,
    }

    return render(request, template_name="invoice_files.html", context=context)


def filter_readable_top_folder(user_name, dir_list):
    result = []
    menu_list = list(MenuDisplay.objects.filter(username__username=user_name).select_related('menu_name'))
    for dir in dir_list:
        if dir == '嚥下':
            result.append(dir)
            continue
        for menu in menu_list:
            if dir == menu.menu_name.menu_name:
                result.append(dir)
                break
            elif (dir == '基本食') and (menu.menu_name.menu_name):
                result.append(dir)
                break
    logger.debug(f'[献立資料表示({user_name})]top_folder:{result}')
    return result


def filter_readable_folder(user, dir_list, sp_path):
    # 指定されたパスが食種フォルダかそれより上のフォルダの場合のみチェックする。
    # 上記より下の階層は、入力パスチェックで検証済みのため
    depth = len(sp_path)
    if depth == 0:
        return dir_list

    menu_dir = sp_path[0]
    if menu_dir == "嚥下":
        if depth == 1:
            # 嚥下フォルダ指定時
            menu_list = list(
                MenuDisplay.objects.filter(username=user).values_list('menu_name__menu_name', flat=True)
            )
            result = [dir for dir in dir_list if dir in menu_list]
            return result
        elif depth == 2:
            readables = list(
                DocumentDirDisplay.objects.filter(
                    username=user).values_list('plate_dir_name', flat=True)
            )
            result = [dir for dir in dir_list if dir in readables]
            return result
        # 2以上は、入力パスチェックで参照可否対応済み
    else:
        # 献立種類フォルダのパス指定時
        if depth == 1:
            qs = DocumentDirDisplay.objects.filter(
                    username=user).values_list('plate_dir_name', flat=True)
            readables = list(
                qs
            )
            result = [dir for dir in dir_list if (dir in readables)]
            return result
        # 2以上は、入力パスチェックで参照可否対応済み

    return dir_list


def filter_readable_plate_folder(user, dir_list, year, month, contract):
    logger.debug(f'階層フォルダ表示({user}):contract={contract}')
    # 最新の設定を取得
    enable = dt.datetime(int(year), int(month), 1)
    last_date = DocumentDirDisplay.objects.filter(
        username=user, enable_date__lte=enable).values_list('enable_date', flat=True) \
        .annotate(Max('enable_date')).order_by('-enable_date')

    if last_date:
        # 専用フォルダ設定がある場合
        latest = last_date.first()
        qs = DocumentDirDisplay.objects.filter(
            username=user, enable_date=latest).values_list('plate_dir_name', flat=True)
        readables = list(qs)
    else:
        readables = []

    result_readables = [dir for dir in dir_list if (dir in readables)]
    if not result_readables:
        # 参照先がない=対象階層に専用フォルダがない、場合は共有フォルダを表示可能にする
        result_readables = [dir for dir in dir_list if dir == contract]
    return result_readables


def filter_readable_enge_folder(user, dir_list):
    menu_list = list(
        MenuDisplay.objects.filter(username=user).\
            exclude(menu_name__menu_name__in=['常食', '薄味']).\
            values_list('menu_name__menu_name', flat=True)
    )
    result = [dir for dir in dir_list if dir in menu_list]
    return result


def get_child_files(user, dir_list, month_path, parent, year, month, contract_user):
    display_file_list = []
    for dir in dir_list:
        dir_path = os.path.join(month_path, parent, dir)
        child_dirs, child_files = default_storage.listdir(dir_path)
        if dir == '嚥下':
            child_dirs = filter_readable_enge_folder(user, child_dirs)
        elif dir in ['基本食', '常食', '薄味', 'ソフト', 'ゼリー', 'ミキサー']:
            child_dirs = filter_readable_plate_folder(user, child_dirs, year, month, contract_user.get_soup_contract_name(dir))
        elif (dir == '乾燥') and ('冷凍' in user.dry_cold_type):
                continue
        elif (dir == '冷凍') and (user.dry_cold_type == '乾燥'):
                continue

        # 取得したファイルの抽出
        for file in child_files:
            display_file_list.append((os.path.join(parent, dir, file), file))

        # さらに下のフォルダの抽出
        display_file_list += get_child_files(user, child_dirs, month_path, os.path.join(parent, dir), year, month, contract_user)

    return display_file_list


def get_lastmoddate(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path))


def cooking_document_files(request):
    # 現在日時の年月フォルダを参照
    date = request.GET.get('date', '')
    if date:
        sp_date = date.split('-')
        year = sp_date[0]
        month = sp_date[1]
    else:
        now = dt.datetime.now()
        year = now.year
        month = now.month
    month_folder = f'{year}年{month}月'
    user_name = request.GET.get('usr', None)
    if user_name:
        usr = User.objects.get(username=user_name)
        not_login = True
    else:
        usr = request.user
        user_name = request.user.username
        not_login = False

    month_path = os.path.join(settings.MEDIA_ROOT, "output", "document", month_folder)
    display_file_list = []
    if os.path.isdir(month_path):
        contract = ContractManager()
        contract.read_all()
        contract_user = contract.get_user_contract(usr)

        dirs, files = default_storage.listdir(month_path)

        display_file_list += [(os.path.join("/", file), file) for file in files]
        display_file_list += get_child_files(usr, filter_readable_top_folder(user_name, dirs), month_path, '', year, month, contract_user)

        result = []
        for x in display_file_list:
            p = os.path.join("/", x[0])
            p = p.replace(os.sep, "/")
            file_path = os.path.join(month_path, p[1:])
            result.append((p, x[1], get_lastmoddate(file_path)))
        document_url = os.path.join(settings.MEDIA_URL, "output", "document", month_folder)
    else:
        result = []
        document_url = ''

    if not result:
        # 表示対象のフォルダ・ファイルがない場合
        messages.info(request, '表示できるファイルがありません。')

    context = {
        "document_files": result,
        "date": f'{year}-{month}',
        "document_url": document_url,
    }
    if not_login:
        context["usr"] = user_name

    return render(request, template_name="cooking_document_files.html", context=context)


def document_files_check(request):
    form = DocumentCheckForm()
    context = {
        "form": form
    }

    return render(request, template_name="document_files_check.html", context=context)


def document_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    # 現在日時の年月フォルダを参照
    tmp = request.GET.get('upper_btn', None)
    if tmp:
        path = tmp if tmp != '/' else ''
        date = request.GET.get('current_date')
    else:
        path = request.GET.get('path', None)
        date = request.GET.get('date', '')

    sp_path = []
    if path:
        sp_path = path[1:].split('/')

    if date:
        sp_date = date.split('-')
        year = sp_date[0]
        month = sp_date[1]
    else:
        now = dt.datetime.now()
        year = now.year
        month = now.month
    month_folder = f'{year}年{month}月'

    month_path = os.path.join(settings.MEDIA_ROOT, "output", "document", month_folder)

    # 管理用ページなので、全てのフォルダ・ファイルを表示する
    if os.path.isdir(month_path):
        if path:
            dir_path = ''
            for p in sp_path:
                dir_path = os.path.join(dir_path, p)
            target_path = os.path.join(month_path, dir_path)
            dirs, files = default_storage.listdir(target_path)
            if files:
                # ファイル名のみのリストを更新日時を含めたタプルに変換
                files = [(x, get_lastmoddate(os.path.join(target_path, x))) for x in files]

            document_url = os.path.join(settings.MEDIA_URL, "output", "document", month_folder, dir_path)
            if dir_path:
                parent = ''
                for p in sp_path[:-1]:
                    parent = os.path.join(parent, p)
                if parent:
                    parent = os.path.join('/', parent)
                current = os.path.join('/', dir_path)

                current = current.replace(os.sep, '/')
                parent = parent.replace(os.sep, '/')
        else:
            target_path = os.path.join(settings.MEDIA_ROOT, "output", "document", month_folder)
            dirs, files = default_storage.listdir(target_path)
            if files:
                # ファイル名のみのリストを更新日時を含めたタプルに変換
                files = [(x, get_lastmoddate(os.path.join(target_path, x))) for x in files]
            parent = None
            current = ''
            document_url = os.path.join(settings.MEDIA_URL, "output", "document", month_folder)
    else:
        dirs = []
        files = []
        parent = None
        current = ''
        document_url = ''

    if not (dirs or files):
        messages.info(request, '登録されたフォルダ・ファイルがありません。')

    context = {
        "document_dirs": dirs,
        "document_files": files,
        "current": current,
        "parent": parent,
        "path": path,
        "date": f'{year}-{month}',
        "document_url": document_url,
        "path_list": sp_path,
    }

    return render(request, template_name="document_files.html", context=context)


# 管理者操作マニュアルページ(らくらく献立用)
def manual_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files.html", context=context)


# 顧客・商品マスタマニュアル
def manual_files_master(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_master"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_master')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_master.html", context=context)


# 売上・請求マスタマニュアル
def manual_files_sales(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_sales"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_sales')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_sales.html", context=context)


# 注文関連マニュアル
def manual_files_order(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_order"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_order')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_order.html", context=context)


# 売価計算マニュアルページ
def manual_files_calc(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_calc"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_calc')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_calc.html", context=context)


# 調理表マニュアルページ
def manual_files_cooiking(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_cooking"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_cooking')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_cooking.html", context=context)


# 計量表マニュアルページ
def manual_files_measure(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_measure"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_measure')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_measure.html", context=context)


# 盛付指示書マニュアルページ
def manual_files_recipe(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_recipe"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_recipe')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_recipe.html", context=context)


# 配送ラベルマニュアルページ
def manual_files_label(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_label"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_label')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_label.html", context=context)


# 加熱加工記録簿マニュアルページ
def manual_files_heating(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_heating"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_heating')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_heating.html", context=context)


# 献立資料マニュアルページ
def manual_files_document(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_document"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_document')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_document.html", context=context)


# 原体マニュアルページ
def manual_files_raw_plate(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_raw_plate"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_raw_plate')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_raw_plate.html", context=context)


# 書き起こしマニュアルページ
def manual_files_kakiokoshi(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_kakiokoshi"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_kakiokoshi')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_kakiokoshi.html", context=context)


# P7対応マニュアルページ
def manual_files_p7(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_p7"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_p7')

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_p7.html", context=context)


# ピッキングマニュアルページ
def manual_files_picking(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_picking"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_picking',)

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_picking.html", context=context)


# パウチ設計図マニュアルページ
def manual_files_pouch(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "documents", "manual_pouch"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", 'manual_pouch',)

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="manual_files_pouch.html", context=context)


# submit押下時に呼び出されるもの -----------------------------------------
def exec_agg_temp(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    # call_command('agg_temp', in_date)
    call_command('aggregation', in_date)

    messages.success(request, '食数集計表の出力が完了しました')

    return redirect('web_order:control_panel')


def exec_agg_measure(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    call_command('agg_measure', in_date)
    return redirect('web_order:control_panel')

# 請求データ集計の実行
def exec_invoice_label(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    call_command('gen_invoice_label', in_date)

    messages.success(request, '出力が完了しました')

    return redirect('web_order:control_panel')


# 配送ラベル出力の実行
def exec_transfer_label(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    call_command('gen_transfer_label', in_date)

    messages.success(request, '出力が完了しました')

    return redirect('web_order:control_panel')


# 売価計算表出力の実行
def exec_sales_price(request):
    form = ExecMonthForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']
    if platform.system() == 'Windows':
        month = in_date.strftime('%Y-%m')
    else:
        month = in_date.strftime('%Y-%-m')

    call_command('calc_sales_price', month)

    messages.success(request, '出力が完了しました')

    return redirect('web_order:control_panel')

def exec_aggregation(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    call_command('aggregation', in_date)

    context = {
        "form": form
    }

    return render(request, template_name='control_panel.html', context=context)


def exec_setout_direction(request):
    form = ExecForm(request.POST)

    if not form.is_valid():
        return HttpResponse('入力した日付が不正です', status=500)

    in_date = form.cleaned_data['in_date']

    #call_command('setout_direction', in_date)
    call_command('gen_setout_direction', in_date)

    context = {
        "form": form
    }

    messages.success(request, '出力が完了しました')
    return render(request, template_name='monthly_menu_list.html', context=context)


# チャット -----------------------------------------------------------
def chat(request):
    qs = Chat.objects.filter(username=request.user).order_by('created_at')
    form = ChatForm(request.POST)

    if request.method == "POST":

        if form.is_valid():

            Chat.objects.create(
                username=request.user,
                is_sendto=False,
                message=form.cleaned_data['message'],
                is_read=False
            )

            subject = "新規問い合わせが入りました"
            message = "施設様からチャットにて問い合わせが入っています。\nコントロールパネルにログインしご確認ください。"
            from_email = 'wada1@dan1.jp'  # 送信者
            recipient_list = ["harradyn@icloud.com", "wada1@dan1.jp"]  # 宛先リスト
            send_mail(subject, message, from_email, recipient_list)

            return redirect("web_order:chat")

        else:
            # バリデーション失敗した場合
            messages.warning(request, '入力内容に不備がありますのでご確認ください')
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
                "form": form,
            }

    else:
        qs_chat = Chat.objects.filter(username=request.user, is_sendto=True, is_read=False)
        for entry in qs_chat:
            entry.is_read = True
            entry.save()

        context = {
            "form": form,
            "object_list": qs,
        }

    return render(request, template_name="chat.html", context=context)


# 管理者側の一覧表示
def chat_all(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    form = ChatForm(request.POST)

    if request.method == "POST":

        if form.is_valid():

            Chat.objects.create(
                username_id=request.POST['user_id'],
                is_sendto=True,
                message=form.cleaned_data['message'],
                is_read=False
            )

            user_id = request.POST['user_id']
            redirect_url = reverse('web_order:chat_all')
            parameters = urlencode(dict(u=user_id))
            url = f'{redirect_url}?{parameters}'
            return redirect(url)

        else:
            # バリデーション失敗した場合
            context = {
                "error_message": '入力内容に不備がありますのでご確認ください',
            }

    else:
        context = {}
        if 'u' in request.GET:
            user_id = request.GET.get('u')
            qs_chat_detail = Chat.objects.filter(username=user_id).order_by('created_at')
            context['user_id'] = user_id
            context['chat_detail'] = qs_chat_detail

            qs_chat_detail = qs_chat_detail.filter(is_sendto=False, is_read=False)
            for entry in qs_chat_detail:
                entry.is_read = True
                entry.save()

        qs_chat = Chat.objects.all()
        sub_qs = qs_chat.filter(username=OuterRef("username"), created_at__gt=OuterRef("created_at"), )
        qs = qs_chat.filter(~Exists(sub_qs)).order_by('-created_at')

        context['message_list'] = qs
        context['form'] = form

    return render(request, template_name="chat_all.html", context=context)


# 管理者側のチャットメッセージ削除
def chat_delete(request, pk):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == "POST":
        try:
            chat = Chat.objects.get(id=pk)
            if chat.is_read:
                # 削除失敗
                messages.error(request, 'メッセージが既読になったため、削除できませんでした。')
            else:
                # 削除成功
                chat.delete()
                messages.success(request, 'メッセージを削除しました。')
        except:
            # 削除失敗
            messages.error(request, 'メッセージが削除されました。')

        user_id = request.POST.get('userid', '')
        redirect_url = reverse('web_order:chat_all')
        parameters = urlencode(dict(u=user_id))
        url = f'{redirect_url}?{parameters}'
        return redirect(url)
    else:
        return redirect("web_order:chat_all")


# 加熱加工記録簿実行ページ
def heating_processing(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == "POST":
        form = HeatingProcessingForm(request.POST)

        if form.is_valid():
            cooking_day = form.cleaned_data['cokking_date']
            # 調理表ファイル検索
            agg_day_short = cooking_day.strftime('%Y.%m.%d')
            _, ck_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "upload"))
            file = None
            for x in ck_files:
                if ('調理表' in x) and (agg_day_short in x) and ('.xlsx' in x):
                    file = x
                    break

            # コマンド実行
            if file:
                # 加熱加工記録簿出力コマンド実行
                call_command('gen_heating_processing', filename=file, date=agg_day_short)
                messages.success(request, 'ファイルを出力しました。')
            else:
                messages.warning(request, '対象製造日の調理表がシステムに存在しません。')
    else:
        form = HeatingProcessingForm()

    context = {
        "form": form,
    }

    return render(request, template_name="heating_processing.html", context=context)


# 加熱加工記録簿一覧ページ
def heating_processing_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_cooking_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "heating_processing"))
    all_files = natsorted(all_cooking_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "heating_processing")

    context = {
        "files": all_files,
        "url": file_url,
    }

    return render(request, template_name="heating_processing_files.html", context=context)


# 栄養月報登録ページ
def monthly_report_import(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == "POST":
        form = ImportMonthlyReportForm(request.POST, request.FILES)
        filename = str(request.FILES['document_file'])

        if form.is_valid():
            form.save()

            # 栄養月報の変換(提供列、治療食選択プルダウンの付与)
            call_command('convert_monthly_report', filename)

            # ファイルを直接ダウンロードする形式だと、画面に表示できず溜まり続けてしまうのでコメントアウト
            # messages.success(request, '栄養月報の変換が完了しました。')
            filepath = os.path.join(settings.OUTPUT_DIR, 'monthly_report', filename)
            return FileResponse(
                open(filepath, 'rb'), as_attachment=True, filename=f'{filename}')

        else:
            messages.warning(request, '入力内容に不備がありますのでご確認ください')
    else:
        form = ImportMonthlyReportForm()

    context = {
        "form": form
    }
    return render(request, template_name="monthly_report.html", context=context)


# P7対応CSVファイル一覧ページ
def p7_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_csv_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "p7"))
    all_csv_files = natsorted(all_csv_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "p7")

    context = {
        "csv_files": all_csv_files,
        "file_url": file_url,
    }

    return render(request, template_name="p7_csv_files.html", context=context)


# 書き起こし出力の実行
def exec_output_kakiokoshi(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = ExecOutputKakiokoshiForm(request.POST)

        if form.is_valid():
            in_date = form.cleaned_data['in_date']
            if platform.system() == 'Windows':
                date = in_date.strftime('%Y-%m-%d')
            else:
                #date = in_date.strftime('%Y-%-m%-d')
                date = in_date.strftime('%Y-%m-%d')

            call_command('kakiokoshi_output', date)

            messages.success(request, '出力が完了しました')
            logger.info(f'帳票出力完了(書き起こし表)-{in_date}製造')

            new_form = ExecOutputKakiokoshiForm()
            context = {
                "form": new_form
            }
        else:
            context = {
                "form": form
            }
    else:
        form = ExecOutputKakiokoshiForm()
        context = {
            "form": form
        }

    return render(request, template_name="kakiokoshi_output.html", context=context)


# P7対応CSVファイル一覧ページ
def kakiokoshi_list_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "kakiokoshi"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "kakiokoshi")

    context = {
        "files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="kakiokoshi_files.html", context=context)


def plate_relation_list_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        cooking_day = request.POST.get('cooking_day', None)
        for key, value in request.POST.items():
            if 'allergen_plate_' in key:
                id = key[key.rfind('_') + 1:]

                relation = AllergenPlateRelations.objects.get(id=id)
                if value == "0":
                    relation.plate = None
                else:
                    relation.plate = CookingDirectionPlate.objects.get(id=int(value))
                relation.save()

        # 追加した行の情報を登録
        for key in request.POST.keys():
            if 'allergen_new_' in key:
                id = key[key.rfind('_') + 1:]
                source_relation = AllergenPlateRelations.objects.get(id=id)
                values = request.POST.getlist(key, [])
                int_values = [int(v) for v in values]
                for v in int_values:
                    qs = AllergenPlateRelations.objects.filter(
                        source=source_relation.source, plate_id=v, code=source_relation.code)
                    if qs.exists():
                        # すでに同じ内容が登録済みのため、何もしない
                        pass
                    else:
                        # 新しい設定として登録する
                        ins = AllergenPlateRelations(
                            source=source_relation.source, plate_id=v, code=source_relation.code
                        )
                        ins.save()

        # 不要な入力欄の削除
        qs = AllergenPlateRelations.objects.filter(
            source__cooking_day=cooking_day, source__is_basic_plate=True
        ).select_related('source', 'plate').order_by(
            'source__eating_day', 'source__seq_meal', 'source__index', 'code')
        for key, group in groupby(qs, key=lambda x: (x.source.eating_day, x.source.seq_meal, x.source.index, x.code)):
            dst_list = [(x.id, x.plate) for x in group]
            list_len = len(dst_list)
            if list_len > 1:
                for r_id, plate in dst_list:
                    if not plate:
                        AllergenPlateRelations.objects.filter(id=r_id).delete()
                        list_len -= 1
                        if list_len <= 1:
                            break

        messages.success(request, '情報を更新しました。')
    if request.method == 'GET':
        cooking_day = request.GET.get('cooking_day', None)

    if cooking_day:
        qs = AllergenPlateRelations.objects.filter(
            source__cooking_day=cooking_day, source__is_basic_plate=True
        ).select_related('source', 'plate').order_by(
            'source__eating_day', 'source__seq_meal', 'source__index', 'code')

        allergens_dict = {}
        relations = []
        eating_day_list = []
        plate_name_list = []
        allergen_name_list = []
        for x in qs:
            dict_key = (x.source.eating_day, x.source.meal_name, x.source.is_soup)

            # 選択先アレルギー食取得
            if not (dict_key in allergens_dict):
                # 代替先料理
                allergen_qs = CookingDirectionPlate.objects.filter(
                    cooking_day=cooking_day, eating_day=dict_key[0],
                    meal_name=dict_key[1], is_soup=dict_key[2], is_basic_plate=False)
                allergen_plates = [(x.id, x.plate_name) for x in allergen_qs]
                allergens_dict[dict_key] = allergen_plates
            else:
                allergen_plates = allergens_dict[dict_key]

            # アレルギー名の取得
            code = x.code
            if ('木沢個' in code) or ('ﾌﾘｰｽﾞ' in code):
                allergen_name = code
                menu_name = ''
            else:
                allergen_masters, _ = CookingDirectionPlatesManager.get_allergens_with_menu(code, cooking_day)
                allergen_name = ",".join([x.allergen_name for x in allergen_masters]) if allergen_masters else ""
                if '常' == code[0]:
                    menu_name = '基本食'
                elif 'ソ' == code[0]:
                    menu_name = 'ソフト'
                elif 'ミ' == code[0]:
                    menu_name = 'ミキサー'
                elif 'ゼ' == code[0]:
                    menu_name = 'ゼリー'
                else:
                    menu_name = ''

            # 画面条件指定用のリストを設定
            # -喫食日
            if not (x.source.eating_day in eating_day_list):
                eating_day_list.append(x.source.eating_day)
            # -料理名
            if not (x.source.plate_name in plate_name_list):
                plate_name_list.append(x.source.plate_name)
            # -アレルギー名
            if not (allergen_name in allergen_name_list):
                allergen_name_list.append(allergen_name)

            dict = {
                'id': x.id,
                'eating_day': x.source.eating_day,
                'meal_name': x.source.meal_name,
                'source_name': x.source.plate_name,
                'plate_name': x.plate.plate_name if x.plate else None,
                'code': code,
                'allergen': f'({menu_name}){allergen_name}' if menu_name else allergen_name,
                'allergen_name': allergen_name,
                'menu_name': menu_name,
                'selected': x.plate.id if x.plate else -1,
                'allergens': allergen_plates
            }
            relations.append(dict)

        context = {
            'cooking_day': cooking_day,
            'items': relations,
            'eating_day_list': eating_day_list,
            'plate_list': plate_name_list,
            'allergen_list': allergen_name_list,
            'meal_list': ['朝食', '昼食', '夕食'],
            'menu_list': ['基本食', 'ゼリー', 'ミキサー', 'ソフト'],
            'number_list': ['①', '②', '③', '④', '⑤', '⑩']
        }
    else:
        context = {}

    return render(request, template_name="plate_relation_edit.html", context=context)


def plate_relation_list_add_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'GET':
        return redirect('web_order:plate_relation')
    if request.method == 'POST':
        for key, value in request.POST.items():
            if 'add_' in key:
                id = key[key.rfind('_') + 1:]

                relation = AllergenPlateRelations.objects.get(id=id)
                new_relation = AllergenPlateRelations(
                    code=relation.code,
                    plate=None,
                    source=relation.source
                )
                new_relation.save()

        messages.success(request, '入力欄を追加しました。')
        cooking_day = request.POST.get('cooking_day', None)

        # 画面の再表示
        qs = AllergenPlateRelations.objects.filter(
            source__cooking_day=cooking_day, source__is_basic_plate=True
        ).select_related('source', 'plate').order_by(
            'source__eating_day', 'source__seq_meal', 'source__index')

        allergens_dict = {}
        relations = []
        for x in qs:
            dict_key = (x.source.eating_day, x.source.meal_name, x.source.is_soup)

            # 選択先アレルギー食取得
            if not (dict_key in allergens_dict):
                # 代替先料理
                allergen_qs = CookingDirectionPlate.objects.filter(
                    cooking_day=cooking_day, eating_day=dict_key[0],
                    meal_name=dict_key[1], is_soup=dict_key[2], is_basic_plate=False)
                allergen_plates = [(x.id, x.plate_name) for x in allergen_qs]
                allergens_dict[dict_key] = allergen_plates
            else:
                allergen_plates = allergens_dict[dict_key]

            # アレルギー名の取得
            code = x.code
            if ('木沢個' in code) or ('ﾌﾘｰｽﾞ' in code):
                allergen_name = code
                menu_name = ''
            else:
                allergen_masters, _ = CookingDirectionPlatesManager.get_allergens_with_menu(code, cooking_day)
                allergen_name = ",".join([x.allergen_name for x in allergen_masters]) if allergen_masters else ""
                if '常' == code[0]:
                    menu_name = '基本食'
                elif 'ソ' == code[0]:
                    menu_name = 'ソフト'
                elif 'ミ' == code[0]:
                    menu_name = 'ミキサー'
                elif 'ゼ' == code[0]:
                    menu_name = 'ゼリー'
                else:
                    menu_name = ''
            dict = {
                'id': x.id,
                'eating_day': x.source.eating_day,
                'meal_name': x.source.meal_name,
                'source_name': x.source.plate_name,
                'plate_name': x.plate.plate_name if x.plate else None,
                'code': code,
                'allergen': f'({menu_name}){allergen_name}' if menu_name else allergen_name,
                'selected': x.plate.id if x.plate else -1,
                'allergens': allergen_plates
            }
            relations.append(dict)

        context = {
            'cooking_day': cooking_day,
            'items': relations
        }

    return render(request, template_name="plate_relation_edit.html", context=context)


# ピッキングWiFi通信アップロード
def picking_upload(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = PickingResultFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.save()

            doc_file = file.document_file
            df = pd.read_csv(doc_file, delimiter=',', header=None, dtype=str)
            reader = PickingResultFileReader(df, doc_file.name)
            reader.read_to_save()

            now = dt.datetime.now()
            messages.success(request, f'[{now.strftime("%Y/%m/%d %H:%M:%S")}]結果のアップロードが完了しました')
            render(request, 'picking_upload.html', {'form': form})
        else:
            messages.error(request, '結果のアップロードに失敗しました')
            render(request, 'picking_upload.html', {'form': form})
    else:
        form = PickingResultFileForm()
    return render(request, 'picking_upload.html', {'form': form})


class PickingResultView(TemplateView):
    template_name = "picking_result_list.html"

    def judge_result(self, result_list, package_count):
        if result_list:
            last_result = result_list[-1]
            if last_result == 'NG':
                return 'NG未解消'

        result_len = len([x for x in result_list if x == 'OK'])
        if (result_len == 0) or (package_count == 0):
            return 'データ不正'
        if package_count > result_len:
            return '読み取り件数不足'
        elif package_count < result_len:
            return '照合重複'
        elif 'NG' in result_list:
            return '正常(NG訂正)'
        return '-'

    def parse_qr_value_v2(self, value: str, terminal_no: str, picking_date, require_qs, phase: str):
        """
        QRコード値の解析
        """
        unit_number, meal_name, type_value, eating_day = QrCodeUtil.perse_qr_value_v2(value)
        type_name = QrCodeUtil.parse_type(type_value)
        qs = require_qs.filter(unit_number=unit_number, meal_name=meal_name, picking_type_code=type_value)
        result = None
        for require in qs:
            if require.eating_day.day == eating_day:
                result = require
                break

        if result:
            return {
                'require_id': result.id,
                'terminal_no': terminal_no,
                'unit_number': unit_number,
                'unit_name': result.short_name,
                'picking_date': picking_date.strftime('%Y年%m月%d日'),
                'qr_value': value,
                'meal_name': meal_name,
                'type': type_name,
                'picking_phase': 'ピッキング指示書と中袋' if phase == '中袋' else '配送用ダンボールと中袋',
                'eating_day': result.eating_day,
                'order_count': result.order_count,
                'package_count': result.package_count,
            }
        else:
            # logger.warning(f'value_skip:{unit_number}-{meal_name}-{type_name}-{eating_day}')
            return None

    def get_records(self, cooking_day, picking_day, is_show_corrected: bool=False, visible_phase_code="", visible_meal_code="", visible_type_code=""):
        object_list = []

        # 読み取り結果なしの施設をNG表示するため、照合が必要な施設の一覧を取得
        require_qs = ReqirePickingPackage.objects.filter(cooking_day=cooking_day, package_count__gt=0).order_by('unit_number')

        max_date = picking_day + relativedelta(days=1)
        result_qs = PickingResultRaw.objects.filter(picking_date__gte=picking_day).filter(
            picking_date__lt=max_date).order_by('terminal_no', 'qr_value', 'picking_phase', 'created_at')

        # 一覧フィルタリング条件
        if is_show_corrected:
            filter_status = ['-']
        else:
            filter_status = ['正常(NG訂正)', '-']
        if visible_phase_code:
            if visible_phase_code == "0":
                visible_phase = ['ピッキング指示書と中袋']
                visible_phase_for_none = ['中袋']
            else:
                visible_phase = ['配送用ダンボールと中袋']
                visible_phase_for_none = ['段ボール']
        else:
            visible_phase = ['ピッキング指示書と中袋', '配送用ダンボールと中袋']
            visible_phase_for_none = ['中袋', '段ボール']
        if visible_meal_code:
            if visible_meal_code == "1":
                visible_meals = ['朝食']
            elif visible_meal_code == "2":
                visible_meals = ['昼食']
            elif visible_meal_code == "3":
                visible_meals = ['夕食']
            else:
                visible_meals = []
        else:
            visible_meals = ['朝食', '昼食', '夕食']
        if visible_type_code:
            if visible_type_code == "1":
                visible_types = ['基本食']
                visible_types_code = ['01']
            elif visible_type_code == "2":
                visible_types = ['嚥下食']
                visible_types_code = ['02']
            elif visible_type_code == "3":
                visible_types = ['汁・汁具']
                visible_types_code = ['03']
            elif visible_type_code == "4":
                visible_types = ['原体']
                visible_types_code = ['04']
            else:
                visible_types = []
                visible_types_code = []
        else:
            visible_types = ['基本食', '嚥下食', '汁・汁具', '原体']
            visible_types_code = ['01', '02', '03', '04']

        # 検索条件ログ出力
        logger.info('ピッキング結果表示条件:')
        logger.info(filter_status)
        logger.info(visible_phase)
        logger.info(visible_meals)
        logger.info(visible_types)

        result_exists_dict = {}
        for key, group in groupby(result_qs, key=lambda x: (x.terminal_no, x.qr_value, x.picking_phase)):
            terminal_no, qr_value, picking_phase = key
            result_dict = self.parse_qr_value_v2(
                qr_value, terminal_no, picking_day, require_qs, phase=picking_phase)

            if result_dict:
                # 結果リストの設定
                result_list = [x.result for x in group]
                result_dict['result_list'] = result_list
                result_dict['warning'] = self.judge_result(result_list, result_dict['package_count'])

                if (not (result_dict['warning'] in filter_status)) and \
                        (result_dict['picking_phase'] in visible_phase)and \
                        (result_dict['meal_name'] in visible_meals) and \
                        (result_dict['type'] in visible_types):
                    object_list.append(result_dict)

                # 出力済み施設の検証
                if result_dict['require_id'] in result_exists_dict:
                    result_exists_dict[result_dict['require_id']] += [picking_phase]
                else:
                    result_exists_dict[result_dict['require_id']] = [picking_phase]

        for require in require_qs:
            # 取得済みの除外
            exists_phase = []
            target_phase = []
            if require.id in result_exists_dict:
                if len(result_exists_dict[require.id]) == 2:
                    # ピッキング指示書照合、段ボール照合両方取得済み
                    continue
                elif require.id in result_exists_dict:
                    exists_phase = result_exists_dict[require.id]

            # フィルタリング条件に合わないものを除外
            if not (require.meal_name in visible_meals):
                continue
            if not (require.picking_type_code in visible_types_code):
                continue
            if exists_phase:
                for p in visible_phase_for_none:
                    if p in exists_phase:
                        pass
                    else:
                        target_phase += [p]
            else:
                target_phase = visible_phase_for_none

            # 施設の照合結果がないので、追加する
            for phase in target_phase:
                dict = {}
                dict['terminal_no'] = '-'
                dict['picking_date'] = picking_day.strftime('%Y年%m月%d日')
                dict['eating_day'] = require.eating_day.strftime('%Y年%m月%d日')
                dict['qr_value'] = ''
                dict['result_list'] = []
                if require.picking_type_code == '01':
                    dict['type'] = '基本食'
                elif require.picking_type_code == '02':
                    dict['type'] = '嚥下食'
                elif require.picking_type_code == '03':
                    dict['type'] = '汁・汁具'
                elif require.picking_type_code == '04':
                    dict['type'] = '原体'
                dict['picking_phase'] = 'ピッキング指示書と中袋' if phase == '中袋' else '配送用ダンボールと中袋'
                dict['warning'] = '読み取り件数不足'
                dict['unit_number'] = require.unit_number
                dict['unit_name'] = require.short_name
                dict['order_count'] = require.order_count
                dict['package_count'] = require.package_count
                dict['meal_name'] = require.meal_name
                object_list.append(dict)

        return object_list

    def get_label_list(self, object_list):
        # 結果最大数分の反映
        if object_list:
            # 画面に表示する、各照合の結果を作成
            for dict in object_list:
                res_list = []
                ng_count = 0
                for shot_result in dict['result_list']:
                    if shot_result == 'OK':
                        if ng_count:
                            # NGが解消した場合
                            # (NG発生時とOKで厳密な繋がりはないが、シンプルな作りにするため、単純に紐づける)
                            res_list.append('NG->OK')
                            ng_count -= 1
                        else:
                            # NGが発生していない場合
                            res_list.append(shot_result)
                    else:
                        # NGの発生。解消するかもしれないので、ここではappendしない
                        ng_count += 1

                # 未解決のNG
                if ng_count:
                    for _ in range(ng_count):
                        res_list.append('NG')

                dict['display_results'] = res_list

            # 照合結果の動的列表示対応
            tmp_list = [len(x['display_results']) for x in object_list if x['warning'] != '-']
            if tmp_list:
                max_result = max(tmp_list)
            else:
                max_result = 0
            result_label_list = []
            for i in range(max_result):
                result_label_list.append(f'袋{i + 1}')

            # 表示列に満たない分の対応
            for dict in object_list:
                res_list = dict['display_results']
                result_list_len = len(res_list)
                for i in range(max_result - result_list_len):
                    res_list.append('-')

        else:
            result_label_list = []

        return result_label_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.info('ピッキング結果追跡表示')

        today = dt.datetime.today().replace(
            hour=0, minute=0, second=0
        )
        if settings.DEBUG_READ_PICKING_RESULT:
            today = today - relativedelta(days=settings.DEBUG_ADJUST_PICKING_DAY)
        cooking_day = InnerPackageManagement.get_cooking_day_from_picking_day(today)

        object_list = self.get_records(cooking_day, today)
        result_label_list = self.get_label_list(object_list)

        context['object_list'] = object_list
        context['result_label_list'] = result_label_list
        context['interval'] = settings.PICKING_RESULT_AUTO_RELOAD_INTERVAL
        return context


class PickingHistoriesView(PickingResultView):
    template_name = "picking_result_history.html"

    def get_context_data(self, **kwargs):
        context = super(TemplateView, self).get_context_data(**kwargs)

        logger.info('ピッキング結果履歴表示')
        if 'cooking_day' in self.request.GET:
            cooking_day = dt.datetime.strptime(self.request.GET['cooking_day'], '%Y-%m-%d')
        else:
            if 'cooking_day' in context:
                cooking_day = context['cooking_day']
            else:
                cooking_day = dt.datetime.now()

        is_show_corrected = self.request.GET.get('corrected', 'off') == 'on'
        visible_phase = self.request.GET.get('visible_phase', '')
        visible_meal = self.request.GET.get('visible_meal', '')
        visible_type = self.request.GET.get('visible_type', '')
        object_list = self.get_records(
            cooking_day, cooking_day,
            is_show_corrected=is_show_corrected, visible_phase_code=visible_phase,
            visible_meal_code=visible_meal, visible_type_code=visible_type)
        result_label_list = self.get_label_list(object_list)

        context['cooking_day'] = cooking_day.strftime('%Y-%m-%d')
        context['object_list'] = object_list
        context['result_label_list'] = result_label_list
        context['is_show_corrected'] = is_show_corrected
        context['visible_phase'] = visible_phase
        context['visible_meal'] = visible_meal
        context['visible_type'] = visible_type
        qs = PickingNotice.objects.filter(cooking_date=cooking_day.date())
        if qs.exists():
            context['notice_form'] = PickingNoticeForm(instance=qs.first())
        else:
            notice = PickingNotice(cooking_date=cooking_day)
            context['notice_form'] = PickingNoticeForm(instance=notice)
        return context

    def post(self, request, *args, **kwargs):
        cooking_day = dt.datetime.strptime(request.POST['cooking_date'], '%Y-%m-%d %H:%M:%S')
        notice, _ = PickingNotice.objects.get_or_create(cooking_date=cooking_day)
        notice.note = request.POST['note']
        notice.save()

        context = self.get_context_data(cooking_day=cooking_day)
        messages.success(request, '備考欄入力内容を登録しました。')
        return self.render_to_response(context)

def picking_output_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == "POST":
        form = DirectionPickingForm(request.POST)
        if form.is_valid():
            chiller1 = ChillerPicking(1, form.cleaned_data['chiller_1_unit_from'], form.cleaned_data['chiller_1_unit_to'])
            chiller2 = ChillerPicking(2, form.cleaned_data['chiller_2_unit_from'], form.cleaned_data['chiller_2_unit_to'])
            chiller3 = ChillerPicking(3, form.cleaned_data['chiller_3_unit_from'], form.cleaned_data['chiller_3_unit_to'])
            chiller4 = ChillerPicking(4, form.cleaned_data['chiller_4_unit_from'], form.cleaned_data['chiller_4_unit_to'])
            chiller_list = [chiller1, chiller2, chiller3, chiller4]
            picking_type = form.cleaned_data['output_type']

            # ピッキング指示書の出力
            management = PickingDirectionOutputManagement(form.cleaned_data['cooking_date'], chiller_list)
            management.write_directions(picking_type)

            messages.success(request, '出力が完了しました')
        else:
            messages.error(request, '施設番号の入力が不正です。')
    else:
        initial_dict = {
            'chiller_1_unit_from': request.COOKIES.get('chiller-1-from', ''),
            'chiller_1_unit_to': request.COOKIES.get('chiller-1-to', ''),

            'chiller_2_unit_from': request.COOKIES.get('chiller-2-from', ''),
            'chiller_2_unit_to': request.COOKIES.get('chiller-2-to', ''),

            'chiller_3_unit_from': request.COOKIES.get('chiller-3-from', ''),
            'chiller_3_unit_to': request.COOKIES.get('chiller-3-to', ''),

            'chiller_4_unit_from': request.COOKIES.get('chiller-4-from', ''),
            'chiller_4_unit_to': request.COOKIES.get('chiller-4-to', ''),
        }
        form = DirectionPickingForm(initial=initial_dict)

    context = {
        "form": form,
    }

    return render(request, template_name="picking_output.html", context=context)


# ピッキング指示書ファイル一覧ページ
def picking_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "picking"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "picking")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="picking_files.html", context=context)


picking_file_keys = [
    ('01', '01'),   # 基本食-朝食
    ('01', '02'),   # 基本食-昼食
    ('01', '03'),   # 基本食-夕食

    ('02', '01'),  # 嚥下-朝食
    ('02', '02'),  # 嚥下-昼食
    ('02', '03'),  # 嚥下-夕食

    ('03', '01'),  # 汁・汁具-朝食
    ('03', '02'),  # 汁・汁具-昼食
    ('03', '03'),  # 汁・汁具-夕食

    ('04', '01'),  # 原体-朝食
    ('04', '02'),  # 原体-昼食
    ('04', '03'),  # 原体-夕食
]
def generate_picking_df(df, meal):
    f_keys = [x for x in picking_file_keys if x[1] == meal]
    for keys in f_keys:
        type_code, meal_code = keys
        yield df[(df.meal == meal_code) & (df.picking_type == type_code)]


def get_picking_sancity_df(meal_code: str, type_code: str, qty: int, eating_day: str, eat_meal):

    if meal_code == '01':
        meal = '△朝食'
    elif meal_code == '02':
        meal = '〇昼食'
    else:
        meal = '□夕食'

    if type_code == '01':
        type_name = 'きほん'
    elif type_code == '02':
        type_name = 'えんげ'
    elif type_code == '03':
        type_name = 'しる'
    else:
        type_name = 'げん体'
    sp = eating_day.split('-')

    return pd.DataFrame({
        'unit_number': [4],
        'short_name': ['サンシティ'],
        'meal': [meal],
        'picking_type': [type_name],
        'quantity': [qty],
        'code': [f'004{meal_code}{type_code}{eating_day[-2:]}'],
        'eating_day': f'{sp[1]}/{sp[2]}',
        'raw_unit_number': ['004'],
        'eat_meal': eat_meal
    })


def seal_csv_output_view(request):
    """
    中袋印刷用CSV出力
    """
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = OutputSealCsvForm(request.POST)
        if form.is_valid():
            cooking_date = form.cleaned_data['cooking_date']
            input_meal = form.cleaned_data['meal']

            # 個食等で同一施設番号がある場合、本体はidの小さい方のため、ソート順にidの指定を明記
            unit_qs = UnitMaster.objects.filter(is_active=True, username__is_active=True, username__is_staff=False)\
                .values('unit_number', 'short_name', 'username__dry_cold_type').exclude(unit_code=None) \
                .order_by('unit_number', 'id')
            unit_df = read_frame(unit_qs).drop_duplicates().reset_index()

            # 同一施設番号の情報はまとめる
            prev_unit_number = None
            delete_unit_list = []
            for index, data in unit_df.iterrows():
                if prev_unit_number != data['unit_number']:
                    prev_unit_number = data['unit_number']
                else:
                    if data['short_name']:
                        if '個食' in data['short_name']:
                            delete_unit_list.append(index)
                        # フリーズは運用中がないため、一旦場外
                    else:
                        # 短縮名がない場合も一旦除外
                        delete_unit_list.append(index)

            unit_df = unit_df.drop(unit_df.index[delete_unit_list]).reset_index()
            unit_df.to_csv("tmp/Seal-0.csv", index=False, header=False, encoding='cp932')

            # 中袋数の計算
            eating_dict = EatingManagement.get_meals_dict_by_cooking_day(cooking_date)
            inner_package_manager = InnerPackageManagement(eating_dict)
            unit_count_list = []
            if input_meal == '01':
                ReqirePickingPackage.objects.filter(cooking_day=cooking_date, meal_name='朝食').delete()
            elif input_meal == '02':
                ReqirePickingPackage.objects.filter(cooking_day=cooking_date, meal_name='昼食').delete()
            else:
                ReqirePickingPackage.objects.filter(cooking_day=cooking_date, meal_name='夕食').delete()

            order_def_dict_list = [{}]

            basic_count = 0
            enge_count = 0
            for eating_day, meal_name in inner_package_manager.generate_eating_day(input_meal):
                logger.info(f'{eating_day}-{meal_name}')
                order_qs = Order.objects.filter(
                    eating_day=eating_day, meal_name__meal_name=meal_name
                ).values(
                    'unit_name__unit_number', 'unit_name__short_name', 'eating_day', 'meal_name__meal_name',
                    'meal_name__soup', 'meal_name__filling','menu_name__menu_name', 'quantity'
                ).order_by('unit_name__unit_number', 'menu_name__menu_name')
                order_df = read_frame(order_qs)

                for o_dict in order_def_dict_list:
                    o_dict['eating_day'] = eating_day
                    o_dict['meal_name'] = meal_name

                pre_df = pd.DataFrame(data=order_def_dict_list)
                unit_pre_df = pd.merge(unit_df, pre_df, how='cross')

                merged_df = pd.merge(
                    unit_pre_df, order_df,
                    left_on=['unit_number', 'short_name', 'eating_day', 'meal_name',],
                    right_on=['unit_name__unit_number', 'unit_name__short_name', 'eating_day', 'meal_name__meal_name'], how='left')
                merged_df.fillna({'quantity': 0, 'meal_name__soup': False, 'meal_name__filling': False, 'menu_name__menu_name': '常食'}, inplace=True)
                merged_df = merged_df.sort_values(
                    ['eating_day', 'unit_number', 'short_name', 'menu_name__menu_name']).reset_index(drop=True)
                merged_df = merged_df.drop(columns=merged_df.columns[[0, 1, 7, 8, 9, ]])
                for index, data in merged_df.iterrows():
                    if data.isna().any():
                        merged_df.loc[index, 'menu_name__menu_name'] = '常食'
                merged_df = merged_df.groupby(['eating_day', 'unit_number', 'short_name', 'username__dry_cold_type',
                                           'meal_name', 'meal_name__soup', 'meal_name__filling',
                                           'menu_name__menu_name']).sum().reset_index()

                has_soup = inner_package_manager.has_soup(cooking_date, eating_day, meal_name)
                has_mixrice = inner_package_manager.has_mix_rice(cooking_date, eating_day, meal_name)
                has_miso_soup = inner_package_manager.has_plate_miso_soup(eating_day, meal_name)
                raw_plates = inner_package_manager.get_raw_plates(cooking_date, eating_day, meal_name)

                mixrice_basic_count = 0
                mixrice_enge_count = 0
                if has_mixrice and input_meal == '02' and meal_name:
                    for index, data in merged_df.iterrows():
                        if data['unit_number'] in settings.MIX_RICE_AGGREGATE_UNITS[0]:
                            if data['menu_name__menu_name'] == '常食':
                                mixrice_basic_count += data['quantity']
                            elif data['menu_name__menu_name'] in ['ソフト', 'ゼリー', 'ミキサー']:
                                mixrice_enge_count += data['quantity']
                prev_unit = None
                basic_count = 0
                enge_count = 0
                prev_tpl = None
                for index, data in merged_df.iterrows():
                    current_unit = (data['unit_number'], data['short_name'])
                    logger.info(f'{current_unit}')

                    if prev_unit:
                        if prev_unit != current_unit:
                            # 嚥下の登録
                            package_count = math.ceil(enge_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                            dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                                      'meal': input_meal, 'picking_type': '02', 'quantity': package_count,
                                      'eating_day': eating_day}
                            if (prev_unit[0] == 500) and (package_count == 0):
                                pass
                            else:
                                logger.info(f'嚥下情報追加:{dict_m}')
                                unit_count_list.append(dict_m)
                            ReqirePickingPackage.objects.create(
                                unit_number=prev_unit[0],
                                short_name=prev_unit[1],
                                cooking_day=cooking_date,
                                eating_day=eating_day,
                                meal_name=meal_name,
                                picking_type_code='02',
                                order_count=enge_count,
                                package_count=package_count
                            )

                            # 汁・汁具の登録
                            if has_soup:
                                if prev_tpl[0]:
                                    if has_miso_soup:
                                        # 嚥下の味噌汁の汁は、汁・汁具の中袋に入れるため、基本食と嚥下の合計が必要
                                        soup_count = basic_count + enge_count
                                    else:
                                        # 嚥下の汁(味噌汁、それ以外の汁・スープ)の汁具は、嚥下の中袋に入れるため、汁・汁具の中袋は基本食のみ
                                        soup_count = basic_count
                                elif prev_tpl[1]:
                                    # 具のみの場合は、中袋の計算外(汁の注文数で計算を行う)だが0は実体に合わないので数を設定
                                    if (basic_count + enge_count) > 0:
                                        soup_count = 1
                                else:
                                    soup_count = 0
                            else:
                                soup_count = 0
                            package_count = math.ceil(soup_count / inner_package_manager.ORDER_COUNT_PER_SOUP_PACKAGE)
                            dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                                      'meal': input_meal, 'picking_type': '03', 'quantity': package_count,
                                      'eating_day': eating_day}
                            if (prev_unit[0] == 500) and (package_count == 0):
                                pass
                            else:
                                logger.info(f'汁情報追加:{dict_m}')
                                unit_count_list.append(dict_m)

                            if soup_count:
                                ReqirePickingPackage.objects.create(
                                    unit_number=prev_unit[0],
                                    short_name=prev_unit[1],
                                    cooking_day=cooking_date,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    picking_type_code='03',
                                    order_count=soup_count,
                                    package_count=package_count
                                )
                                logger.debug(f'{prev_unit[0]}.{prev_unit[1]}:{soup_count}(base:{basic_count},enge:{enge_count})')

                            # 原体の計算
                            has_raw_plate = False
                            for raw_plate in raw_plates:
                                if prev_tpl[2] == "乾燥":
                                    is_direct = raw_plate.is_direct_dry
                                elif "冷凍" in prev_tpl[2]:
                                    is_direct = raw_plate.is_direct_cold
                                elif prev_tpl[2] == "冷蔵":
                                    is_direct = raw_plate.is_direct_chilled
                                else:
                                    logger.warn(f'施設の冷凍乾燥区分異常：{first_unit.dry_cold_type}')
                                    is_direct = False

                                # 原体送りの施設の区分が直送でないの場合、対象献立(基本 or 嚥下)のフラグを立てる
                                if is_direct:
                                    if ("冷凍" in prev_tpl[2]) and (UnitMaster.objects.filter(
                                            unit_number=prev_unit[0], short_name=prev_unit[1],
                                            username__dry_cold_type='冷凍_談').exists()):
                                        has_raw_plate = True
                                else:
                                    if basic_count:
                                        has_raw_plate = True
                                    elif enge_count and \
                                            (not PlateNameAnalizeUtil.is_raw_enge_plate_name(raw_plate.base_name, eating_day)[0]):
                                        # 嚥下のみで、製造対象外があれば袋が必要
                                        has_raw_plate = True
                                    else:
                                        has_raw_plate = False
                                    break
                            dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                                      'meal': input_meal, 'picking_type': '04', 'quantity': 1 if has_raw_plate else 0,
                                      'eating_day': eating_day}
                            if (prev_unit[0] == 500) and (not has_raw_plate):
                                pass
                            else:
                                logger.info(f'原体追加:{dict_m}')
                                unit_count_list.append(dict_m)
                            if has_raw_plate:
                                ReqirePickingPackage.objects.create(
                                    unit_number=prev_unit[0],
                                    short_name=prev_unit[1],
                                    cooking_day=cooking_date,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    picking_type_code='04',
                                    order_count=1,
                                    package_count=1
                                )

                            # サンシティ(混ぜご飯用)の対応(集計)
                            if has_mixrice and input_meal == '02':
                                # 運用上、混ぜご飯は昼ごはんとして作成していることを前提
                                if prev_unit[0] == settings.MIX_RICE_AGGREGATE_UNITS[0][0]:
                                    if meal_name == '昼食':
                                        # 基本食
                                        package_count = math.ceil(
                                            mixrice_basic_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                                        dict_m = {'unit_number': prev_unit[0], 'short_name': 'サンシティ',
                                                  'meal': input_meal, 'picking_type': '01', 'quantity': package_count,
                                                  'eating_day': eating_day}
                                        if (prev_unit[0] == 500) and (package_count == 0):
                                            pass
                                        else:
                                            unit_count_list.append(dict_m)
                                        ReqirePickingPackage.objects.create(
                                            unit_number=prev_unit[0],
                                            short_name=prev_unit[1],
                                            cooking_day=cooking_date,
                                            eating_day=eating_day,
                                            meal_name='昼食',
                                            picking_type_code='01',
                                            order_count=mixrice_basic_count,
                                            package_count=package_count
                                        )

                                        # 嚥下食
                                        package_count = math.ceil(
                                            mixrice_enge_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                                        dict_m = {'unit_number': prev_unit[0], 'short_name': 'サンシティ',
                                                  'meal': input_meal, 'picking_type': '02', 'quantity': package_count,
                                                  'eating_day': eating_day}
                                        if (prev_unit[0] == 500) and (package_count == 0):
                                            pass
                                        else:
                                            unit_count_list.append(dict_m)
                                        ReqirePickingPackage.objects.create(
                                            unit_number=prev_unit[0],
                                            short_name=prev_unit[1],
                                            cooking_day=cooking_date,
                                            eating_day=eating_day,
                                            meal_name='昼食',
                                            picking_type_code='02',
                                            order_count=mixrice_enge_count,
                                            package_count=package_count
                                        )

                            basic_count = 0
                            enge_count = 0
                            prev_unit = current_unit
                            prev_tpl = (
                            data['meal_name__soup'], data['meal_name__filling'], data['username__dry_cold_type'])
                    else:
                        prev_unit = current_unit
                        prev_tpl = (data['meal_name__soup'], data['meal_name__filling'], data['username__dry_cold_type'])

                    if data['menu_name__menu_name'] == '常食':
                        # 基本食は即時登録
                        basic_count = data['quantity']
                        package_count = math.ceil(basic_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                        dict_m = {'unit_number': data['unit_number'], 'short_name': data['short_name'],
                                  'meal': input_meal, 'picking_type': '01', 'quantity': package_count,
                                  'eating_day': data['eating_day']}
                        if (data['unit_number'] == 500) and (basic_count == 0):
                            pass
                        else:
                            unit_count_list.append(dict_m)
                        ReqirePickingPackage.objects.create(
                            unit_number=data['unit_number'],
                            short_name=data['short_name'],
                            cooking_day=cooking_date,
                            eating_day=data['eating_day'],
                            meal_name=data['meal_name'],
                            picking_type_code='01',
                            order_count=basic_count,
                            package_count=package_count
                        )
                    else:
                        # 嚥下の加算
                        enge_count += data['quantity']

                        # 混ぜご飯集計の中袋数の計算

                # 最終データの登録
                # 嚥下の登録
                package_count = math.ceil(enge_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                          'meal': input_meal, 'picking_type': '02', 'quantity': package_count,
                          'eating_day': eating_day}
                if (prev_unit[0] == 500) and (package_count == 0):
                    pass
                else:
                    logger.info(f'嚥下情報追加:{dict_m}')
                    unit_count_list.append(dict_m)
                ReqirePickingPackage.objects.create(
                    unit_number=prev_unit[0],
                    short_name=prev_unit[1],
                    cooking_day=cooking_date,
                    eating_day=eating_day,
                    meal_name=meal_name,
                    picking_type_code='02',
                    order_count=enge_count,
                    package_count=package_count
                )

                # 汁・汁具の登録
                if prev_tpl[0]:
                    if has_miso_soup:
                        # 嚥下の味噌汁の汁は、汁・汁具の中袋に入れるため、基本食と嚥下の合計が必要
                        soup_count = basic_count + enge_count
                    else:
                        # 嚥下の汁(味噌汁、それ以外の汁・スープ)の汁具は、嚥下の中袋に入れるため、汁・汁具の中袋は基本食のみ
                        if (basic_count + enge_count) > 0:
                            soup_count = 1
                elif prev_tpl[1]:
                    # 具のみの場合は、中袋の計算外(汁の注文数で計算を行う)だが0は実体に合わないので数を設定
                    soup_count = 1
                else:
                    soup_count = 0
                package_count = math.ceil(soup_count / inner_package_manager.ORDER_COUNT_PER_SOUP_PACKAGE)
                dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                          'meal': input_meal, 'picking_type': '03', 'quantity': package_count,
                          'eating_day': eating_day}
                if (prev_unit[0] == 500) and (package_count == 0):
                    pass
                else:
                    unit_count_list.append(dict_m)

                if soup_count:
                    ReqirePickingPackage.objects.create(
                        unit_number=prev_unit[0],
                        short_name=prev_unit[1],
                        cooking_day=cooking_date,
                        eating_day=eating_day,
                        meal_name=meal_name,
                        picking_type_code='03',
                        order_count=soup_count,
                        package_count=package_count
                    )

                # 原体の計算
                has_raw_plate = False
                for raw_plate in raw_plates:
                    if prev_tpl[2] == "乾燥":
                        is_direct = raw_plate.is_direct_dry
                    elif "冷凍" in prev_tpl[2]:
                        is_direct = raw_plate.is_direct_cold
                    elif prev_tpl[2] == "冷蔵":
                        is_direct = raw_plate.is_direct_chilled
                    else:
                        logger.warn(f'施設の冷凍乾燥区分異常：{first_unit.dry_cold_type}')
                        is_direct = False

                    # 原体送りの施設の区分が直送でないの場合、対象献立(基本 or 嚥下)のフラグを立てる
                    if is_direct:
                        if ("冷凍" in prev_tpl[2]) and (UnitMaster.objects.filter(
                                unit_number=prev_unit[0], short_name=prev_unit[1],
                                username__dry_cold_type='冷凍_談').exists()):
                            has_raw_plate = True
                    else:
                        if basic_count:
                            has_raw_plate = True
                        elif enge_count and \
                                (not PlateNameAnalizeUtil.is_raw_enge_plate_name(raw_plate.base_name, eating_day)[0]):
                            # 嚥下のみで、製造対象外があれば袋が必要
                            has_raw_plate = True
                        else:
                            has_raw_plate = False
                        break
                dict_m = {'unit_number': prev_unit[0], 'short_name': prev_unit[1],
                          'meal': input_meal, 'picking_type': '04', 'quantity': 1 if has_raw_plate else 0,
                          'eating_day': eating_day}
                if (prev_unit[0] == 500) and (not has_raw_plate):
                    pass
                else:
                    unit_count_list.append(dict_m)
                if has_raw_plate:
                    ReqirePickingPackage.objects.create(
                        unit_number=prev_unit[0],
                        short_name=prev_unit[1],
                        cooking_day=cooking_date,
                        eating_day=eating_day,
                        meal_name=meal_name,
                        picking_type_code='04',
                        order_count=1,
                        package_count=1
                    )

                # サンシティ(混ぜご飯用)の対応(集計)
                if has_mixrice and input_meal == '02':
                    # 運用上、混ぜご飯は昼ごはんとして作成していることを前提
                    if prev_unit[0] == settings.MIX_RICE_AGGREGATE_UNITS[0][0]:
                        if meal_name == '昼食':
                            # 基本食
                            package_count = math.ceil(
                                mixrice_basic_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                            dict_m = {'unit_number': prev_unit[0], 'short_name': 'サンシティ',
                                      'meal': input_meal, 'picking_type': '01', 'quantity': package_count,
                                      'eating_day': eating_day}
                            if (prev_unit[0] == 500) and (package_count == 0):
                                pass
                            else:
                                unit_count_list.append(dict_m)
                            ReqirePickingPackage.objects.create(
                                unit_number=prev_unit[0],
                                short_name=prev_unit[1],
                                cooking_day=cooking_date,
                                eating_day=eating_day,
                                meal_name='昼食',
                                picking_type_code='01',
                                order_count=mixrice_basic_count,
                                package_count=package_count
                            )

                            # 嚥下食
                            package_count = math.ceil(
                                mixrice_enge_count / inner_package_manager.ORDER_COUNT_PER_PACKAGE)
                            dict_m = {'unit_number': prev_unit[0], 'short_name': 'サンシティ',
                                      'meal': input_meal, 'picking_type': '02', 'quantity': package_count,
                                      'eating_day': eating_day}
                            if (prev_unit[0] == 500) and (package_count == 0):
                                pass
                            else:
                                unit_count_list.append(dict_m)
                            ReqirePickingPackage.objects.create(
                                unit_number=prev_unit[0],
                                short_name=prev_unit[1],
                                cooking_day=cooking_date,
                                eating_day=eating_day,
                                meal_name='昼食',
                                picking_type_code='02',
                                order_count=mixrice_enge_count,
                                package_count=package_count
                            )

            count_df = pd.DataFrame(data=unit_count_list)
            count_df.to_csv("tmp/Seal-1-pre.csv", index=False, header=False, encoding='cp932')
            count_df = count_df.astype({'eating_day': 'str', 'unit_number': 'int64', 'quantity': 'int64'})
            count_df.to_csv("tmp/Seal-1.csv", index=False, header=False, encoding='cp932')

            # 食事区分、種類の単位でファイル出力
            for filterd_df in generate_picking_df(count_df, input_meal):
                sancity_qty = 0
                for index, data in filterd_df.iterrows():

                    # 食事区分の設定
                    if data['meal'] == '01':
                        filterd_df.loc[index, 'meal'] = MealUtil.add_name_mark('朝食')
                        filterd_df.loc[index, 'eat_meal'] = '△あさ'
                        current_eat_meal = '△あさ'
                        fname_meal = f'{data["meal"]}朝食'
                    elif data['meal'] == '02':
                        filterd_df.loc[index, 'meal'] = MealUtil.add_name_mark('昼食')
                        filterd_df.loc[index, 'eat_meal'] = '〇ひる'
                        fname_meal = f'{data["meal"]}昼食'
                        current_eat_meal = '〇ひる'
                    else:   # 03
                        filterd_df.loc[index, 'meal'] = MealUtil.add_name_mark('夕食')
                        filterd_df.loc[index, 'eat_meal'] = '□ゆう'
                        fname_meal = f'{data["meal"]}夕食'
                        current_eat_meal = '□ゆう'

                    # 中袋種類の設定
                    if data['picking_type'] == '01':
                        filterd_df.loc[index, 'picking_type'] = MealUtil.add_name_mark('きほん')
                        fname_type = f'{data["picking_type"]}基本食'
                    elif data['picking_type'] == '02':
                        filterd_df.loc[index, 'picking_type'] = MealUtil.add_name_mark('えんげ')
                        fname_type = f'{data["picking_type"]}嚥下'
                    elif data['picking_type'] == '03':
                        filterd_df.loc[index, 'picking_type'] = MealUtil.add_name_mark('しる')
                        fname_type = f'{data["picking_type"]}汁・汁具'
                    elif data['picking_type'] == '04':
                        filterd_df.loc[index, 'picking_type'] = MealUtil.add_name_mark('げん体')
                        fname_type = f'{data["picking_type"]}原体'

                    # 喫食日の設定
                    sp = data['eating_day'].split('-')
                    filterd_df.loc[index, 'eating_day'] = f'{sp[1]}/{sp[2]}'
                    # 個食とフリーズは出力しない

                    # QRコード内容
                    value_unit_number = str(data['unit_number']).zfill(3)
                    filterd_df.loc[index, 'code'] = QrCodeUtil.get_value_from_number_v2(
                        value_unit_number, data['meal'], data['picking_type'], data['eating_day'][-2:])

                # サンシティ(混ぜご飯用)の対応
                mix_rice_df = get_picking_sancity_df(data['meal'], data['picking_type'], sancity_qty, data["eating_day"], current_eat_meal)
                filterd_df = filterd_df.append(mix_rice_df)

                # id、index列を削除し、並べ替え
                if filterd_df.empty:
                    new_dir_path = os.path.join(settings.OUTPUT_DIR, 'seal_csv')
                    os.makedirs(new_dir_path, exist_ok=True)

                    filename = new_dir_path + f"/{cooking_date}_seal_csv_{fname_meal}_{fname_type}.csv"
                    filterd_df.to_csv(filename, index=False, header=False, encoding='cp932')
                else:
                    filterd_df = filterd_df.reindex(
                        ['unit_number', 'short_name', 'meal', 'picking_type', 'quantity', 'eating_day', 'eat_meal', 'code'],
                        axis=1)

                    new_dir_path = os.path.join(settings.OUTPUT_DIR, 'seal_csv')
                    os.makedirs(new_dir_path, exist_ok=True)

                    filename = new_dir_path + f"/{cooking_date}_seal_csv_{fname_meal}_{fname_type}.csv"
                    filterd_df.to_csv(filename, index=False, header=False, encoding='cp932')
            messages.success(request, '出力しました。')
            last_modify = UnitPackage.objects.filter(cooking_day=cooking_date).order_by('-register_at').first()
            logger.info(f'最終データ更新日時：{last_modify.register_at.strftime("%Y/%m/%d %H:%M:%S")}')
            logger.info(f'帳票出力完了(中袋シール用CSV)-{cooking_date}製造-{input_meal}')

    form = OutputSealCsvForm()
    context = {
        "form": form,
    }

    return render(request, template_name="seal_csv_output.html", context=context)


# 中袋シールCSVファイル一覧ページ
def seal_csv_files_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "seal_csv"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "seal_csv")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="seal_csv_files.html", context=context)


# 中袋シールCSVファイル一覧ページ
def seal_csv_files_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "seal_csv"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "seal_csv")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="seal_csv_files.html", context=context)


def pouch_output_view(request):
    """
    パウチ設計図出力
    """
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = OutputPouchDesignForm(request.POST)
        if form.is_valid():
            cooking_date = form.cleaned_data['cooking_date']

            # 集計処理の実施
            aggregator = PouchAggregate(cooking_date)
            aggregator.read_eating_time()
            aggregator.aggreate()

            # パウチ設計図の出力
            writer = PouchDesignWriter(aggregator)
            writer.write()

            messages.success(request, '出力しました。')
    form = OutputPouchDesignForm()
    context = {
        "form": form,
    }

    return render(request, template_name="pouch_output.html", context=context)


# パウチ設計図ファイル一覧ページ
def pouch_files(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "pouch_design"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "pouch_design")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="pouch_files.html", context=context)


def convert_notice(notice: str):
    no_rt = notice.replace('\n', '').replace('\r', '')
    return f'{no_rt[:80]}...' if len(no_rt) > 80 else no_rt


# ピッキング結果備考一覧ページ
def picking_notices_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    view_limit_date = dt.datetime.now().date() + relativedelta(years=-1)

    notice_list = []
    notices_qs = PickingNotice.objects.filter(cooking_date__gte=view_limit_date).order_by('-cooking_date')
    for notice in notices_qs:
        notice_list.append((notice.cooking_date, convert_notice(notice.note)))

    context = {
        "notice_list": notice_list,
    }

    return render(request, template_name="picking_notices.html", context=context)


# ピッキング結果印刷ページ
def picking_notice_print_view(request, id):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    # 備考情報取得
    notice = PickingNotice.objects.get(id=id)

    context = {
        "notice": notice,
    }

    return render(request, template_name="picking_notice_print.html", context=context)


class InvoiceHistoriesList(ListView):
    template_name = 'invoice_history.html'
    model = InvoiceDataHistory


    def get_context_data(self, **kwargs):
        unit_name = None
        from_day = None
        to_day = None
        from_sales = None
        to_sales = None
        form = SearchSalesInvoiceForm(self.request.GET)
        if form.is_valid():
            unit_name = form.cleaned_data['unit_name']
            from_day = form.cleaned_data['from_date']
            to_day = form.cleaned_data['to_date']
            from_sales = form.cleaned_data['from_sales']
            to_sales = form.cleaned_data['to_sales']

        qs = InvoiceDataHistory.objects.all() \
            .order_by('sale_day', 'unit_code', 'calc_name', '-created_at')
        if unit_name:
            unit = UnitMaster.objects.get(id=unit_name)
            qs = qs.filter(unit_code=unit.unit_code, calc_name=unit.unit_name)
        if from_day and to_day:
            day_range = [from_day, to_day]
            qs = qs.filter(sale_day__range=day_range)
        elif from_day:
            qs = qs.filter(sale_day__gte=from_day)
        elif to_day:
            qs = qs.filter(sale_day__lte=to_day)
        if from_sales and to_sales:
            sales_range = [from_sales, to_sales]
            qs = qs.filter(sales__rane=[sales_range])
        elif from_sales:
            qs = qs.filter(sales__gte=from_sales)
        elif to_sales:
            qs = qs.filter(sale_day__lte=to_sales)

        object_list = []
        for key, group in groupby(qs, key=lambda x: (x.sale_day, x.unit_code, x.calc_name)):
            # 最新の1件だけを取得
            object_list.append(next(group))

        context = super().get_context_data(**kwargs)
        context['object_list'] = object_list
        context['form'] = form
        return context


# 設計図シール出力
def design_seal_csv_output_view(request):
    """
    設計図パウチ出力用CSV出力
    """
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        form = DesignSealCsvForm(request.POST)
        if form.is_valid():
            cooking_date = form.cleaned_data['cooking_date']
            output_type = form.cleaned_data['output_type']

            # 集計処理の実施
            writer = DesignSealCsvWriter(cooking_date, output_type)
            writer.wite()

            messages.success(request, 'ファイルを出力しました。')
            last_modify = UnitPackage.objects.filter(cooking_day=cooking_date).order_by('-register_at').first()
            logger.info(f'最終データ更新日時：{last_modify.register_at.strftime("%Y/%m/%d %H:%M:%S")}')
            logger.info(f'帳票出力完了(設計図シール用CSV)-{cooking_date}製造-{output_type}')

    form = DesignSealCsvForm()
    context = {
        "form": form,
    }

    return render(request, template_name="design_seal_output.html", context=context)


# 設計図シール出力CSVファイル一覧ページ
def design_seal_csv_files_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    return render(request, template_name="design_seal_csv_root.html", context={})


def design_seal_csv_files_basic_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    path = os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "基本食")
    _, all_files = default_storage.listdir(path)
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "基本食")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_files_soft_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "ソフト"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "ソフト")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_files_jelly_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "ゼリー"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "ゼリー")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_files_mixer_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "ミキサー"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "ミキサー")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_allergen_files_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    return render(request, template_name="design_seal_csv_allergen.html", context={})


def design_seal_csv_allergen_basic_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "アレルギー", "基本食"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "アレルギー", "基本食")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_allergen_soft_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "アレルギー", "ソフト"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "アレルギー", "ソフト")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_allergen_jelly_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "アレルギー", "ゼリー"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "アレルギー", "ゼリー")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


def design_seal_csv_allergen_mixer_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_files = default_storage.listdir(os.path.join(settings.MEDIA_ROOT, "output", "design_seal_csv", "アレルギー", "ミキサー"))
    all_files = natsorted(all_files, reverse=True)
    file_url = os.path.join(settings.MEDIA_URL, 'output', "design_seal_csv", "アレルギー", "ミキサー")

    context = {
        "csv_files": all_files,
        "file_url": file_url,
    }

    return render(request, template_name="design_seal_csv_files.html", context=context)


# 施設登録
class UnitImportView(TemplateView):
    template_name = 'unit_import.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        context = {
            'form': UnitImportForm(),
        }
        return self.render_to_response(context)

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        form = UnitImportForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('document_file')
            total_require_confirm = False
            total_user_list = []
            total_error_list = []
            ins_list = []
            confirm_dict = {}
            for file in files:
                ins = ImportUnit(document_file=file)
                ins.save()

                importer = UnitImporter()
                require_company, require_facility, user_id, error_list = importer.pre_read(ins)

                # 問い合わせ発生判定
                if require_company and require_facility:
                    if require_company in confirm_dict:
                        confirm_dict[require_company].append(require_facility)
                    else:
                        confirm_dict[require_company] = [require_facility, ]
                    ins_list.append(user_id)

                if user_id:
                    total_user_list.append(user_id)

                if error_list:
                    total_error_list.append(error_list)

            if total_error_list:
                if len(total_error_list) == 1:
                    for error in total_error_list[0]:
                        messages.error(request, error)
                else:
                    for error_list in total_error_list:
                        messages.error(request, f'{error}...他{len(error_list)}件')

                # 元の画面を表示
                context = {
                    'form': UnitImportForm(),
                }
                return self.render_to_response(context)
            elif confirm_dict:
                # 処理の続行を問い合わせ
                confirm_context = {
                    'object_list': [{'name': key, 'facilities': value} for key, value in confirm_dict.items()],
                    'inputs': [x for x in ins_list]
                }
                return render(request, 'user_master_register_confirm.html', context=confirm_context)

            # エラーも問い合わせもないので、登録処理続行
            for user_id in total_user_list:
                importer.read(user_id)
                importer.register()

            messages.success(request, '登録しました。')
        context = {
            'form': UnitImportForm(),
        }
        return self.render_to_response(context)


# 施設登録確認
class UnitImportConfirmView(TemplateView):
    template_name = 'user_master_register_confirm.html'

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        input_ids = request.POST.getlist('inputid', [])
        importer = UnitImporter()

        try:
            for id in input_ids:
                importer.read(id)
                importer.register()

            messages.success(request, '登録しました。')
            return redirect('web_order:user_masters')
        except Exception as e:
            return HttpResponse('登録に失敗しました', status=500)

# 施設削除
class UserDeleteView(TemplateView):
    template_name = 'unit_import.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        userid = kwargs['pk']
        user = User.objects.get(id=userid)

        Order.objects.filter(unit_name__username=user).delete()
        MealDisplay.objects.filter(username=user).delete()
        MenuDisplay.objects.filter(username=user).delete()
        AllergenDisplay.objects.filter(username=user).delete()
        InvoiceException.objects.filter(unit_name__username=user).delete()

        # ユニット削除
        UnitMaster.objects.filter(username=user).delete()

        # 施設削除
        user.delete()

        # 親会社の削除
        if len(User.objects.filter(company_name=user.company_name, is_parent=False)) <= 1:
            # 削除したことにより、親会社配下の施設が1件だけになるなら削除する
            User.objects.filter(company_name=user.company_name, is_parent=True).delete()

        messages.success(request, '削除しました。')
        return redirect('web_order:user_masters')


# 施設削除
class UserDetailView(DetailView):
    model = User
    template_name = 'user_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = context['object']
        create_input = UserCreationInput.objects.filter(
            company_name=user.company_name, facility_name=user.facility_name).order_by("-id").first()
        if create_input:
            context['source_file'] = os.path.basename(create_input.import_file.document_file.name)
            context['enable_day'] = create_input.enable_start_day

        # 親会社
        parent = User.objects.filter(facility_name=user.company_name, is_parent=True).first()
        if parent:
            context['parent'] = True
            context['parent_code'] = parent.username

        # ユニット情報
        units = UnitMaster.objects.filter(username=user).order_by('unit_number')
        context['units'] = units

        # 食事区分
        meals = []
        for meal_display in MealDisplay.objects.filter(username=user).order_by('meal_name__seq_order'):
            meal = meal_display.meal_name
            if meal.soup:
                meals.append(f'{meal.meal_name}(汁具あり)')
            elif meal.filling:
                meals.append(f'{meal.meal_name}(具のみ)')
            else:
                meals.append(f'{meal.meal_name}(汁なし)')
        context['meals'] = ",".join(meals)


        # 献立種類
        menus = []
        for menu_display in MenuDisplay.objects.filter(username=user).order_by('menu_name__seq_order'):
            menu = menu_display.menu_name
            menus.append(
                (f'{menu.menu_name}単価', f'朝食:{menu_display.price_breakfast}/昼食:{menu_display.price_lunch}/夕食:{menu_display.price_dinner}')
            )

        context['menus'] = menus

        # アレルギー
        context['allergens'] = AllergenDisplay.objects.filter(username=user).order_by('allergen_name__seq_order')
        return context

def dry_cold_update_view(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    if request.method == 'POST':
        update_form = CustomUserUpdateDryColdForm(request.POST)
        if update_form.is_valid():
            username_id = request.POST['username']
            dry_cold_type = request.POST['dry_cold_type']

            user = User.objects.get(id=username_id)
            user.dry_cold_type = dry_cold_type
            user.save()
            messages.success(request, '更新しました。')
        else:
            messages.error(request, '失敗しました。')

    form = CustomUserUpdateDryColdForm()

    context = {
        "form": form,
    }

    return render(request, template_name="dry_cold_update.html", context=context)


# ==== マスタメンテナンス画面の対応 =====
# マスタメンテトップページの表示 ----------------------------------------------------
def master_index(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    return render(request, template_name='master_index.html', context={})


# region 販売固定商品-マスタメンテ
# region 販売固定商品
class EverydaySellingCreate(CreateView):
    """
    販売固定商品登録ビュー
    """
    model = EverydaySelling
    template_name = 'everyday_selling_create.html'
    form_class = EverydaySellingForm
    success_url = reverse_lazy('web_order:everyday_selling_list')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)


class EverydaySellingList(ListView):
    """
    販売固定商品一覧ビュー
    """
    model = EverydaySelling
    template_name = 'everyday_selling_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = EverydaySelling.objects.all().order_by('-enable')
        return qs


class EverydaySellingUpdate(UpdateView):
    """
    販売固定商品更新ビュー
    """
    model = EverydaySelling
    template_name = 'everyday_selling_update.html'
    form_class = EverydaySellingForm

    def get_success_url(self):
        return reverse_lazy('web_order:everyday_selling_list')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)
# endregion


# region 単価情報
class NewUnitPriceCreate(TemplateView):
    """
    単価情報登録ビュー
    """
    template_name = 'new_price_create.html'

    def get(self, request, **kwargs):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        user_id = kwargs['userid']
        user = User.objects.get(id=user_id)

        #　基本食・嚥下の契約有無を取得
        is_basic_enable = MenuDisplay.objects.filter(username=user, menu_name__menu_name='常食').exists()
        is_enge_enable = MenuDisplay.objects.filter(
            username=user, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).exists()

        # 現在の単価を取得(基本食)
        today = dt.datetime.today()
        current_basic_new_price = NewUnitPrice.objects.filter(
            username=user, menu_name="常食", eating_day__lte=today).order_by('-eating_day').first()
        if current_basic_new_price:
            basic_price_breakfast = current_basic_new_price.price_breakfast
            basic_price_lunch = current_basic_new_price.price_lunch
            basic_price_dinner = current_basic_new_price.price_dinner
        else:
            basic_menu = MenuDisplay.objects.filter(username=user, menu_name__menu_name='常食').first()
            if basic_menu:
                basic_price_breakfast = basic_menu.price_breakfast
                basic_price_lunch = basic_menu.price_lunch
                basic_price_dinner = basic_menu.price_dinner
            else:
                basic_price_breakfast = 0
                basic_price_lunch = 0
                basic_price_dinner = 0


        # 現在の単価を取得(嚥下)
        current_enge_new_price = NewUnitPrice.objects.filter(
            username=user, menu_name__in=["ソフト", "ゼリー", "ミキサー"], eating_day__lte=today).order_by('-eating_day').first()
        if current_enge_new_price:
            enge_price_breakfast = current_enge_new_price.price_breakfast
            enge_price_lunch = current_enge_new_price.price_lunch
            enge_price_dinner = current_enge_new_price.price_dinner
        else:
            enge_menu = MenuDisplay.objects.filter(username=user, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).first()
            if enge_menu:
                enge_price_breakfast = enge_menu.price_breakfast
                enge_price_lunch = enge_menu.price_lunch
                enge_price_dinner = enge_menu.price_dinner
            else:
                enge_price_breakfast = 0
                enge_price_lunch = 0
                enge_price_dinner = 0

        context = {
            'disable_day_error': True,
            'user': user,
            'form': NewUnitPriceForm(None, {'is_basic_enable': is_basic_enable, 'is_enge_enable': is_enge_enable}),
            'basic_price_breakfast': basic_price_breakfast,
            'basic_price_lunch': basic_price_lunch,
            'basic_price_dinner': basic_price_dinner,
            'enge_price_breakfast': enge_price_breakfast,
            'enge_price_lunch': enge_price_lunch,
            'enge_price_dinner': enge_price_dinner,
        }
        return render(request, template_name=self.template_name, context=context)

    def validate_enable_day(self, user, enable_day):
        if NewUnitPrice.objects.filter(username=user, eating_day=enable_day).exists():
            return False
        else:
            return True

    def post(self, request, **kwargs):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        user_id = kwargs['userid']
        user = User.objects.get(id=user_id)
        #　基本食・嚥下の契約有無を取得
        is_basic_enable = MenuDisplay.objects.filter(username=user, menu_name__menu_name='常食').exists()
        is_enge_enable = MenuDisplay.objects.filter(
            username=user, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).exists()

        form = NewUnitPriceForm(request.POST, {'is_basic_enable': is_basic_enable, 'is_enge_enable': is_enge_enable})
        if form.is_valid():
            enable_day = form.cleaned_data['enable_day']
            if self.validate_enable_day(user, enable_day):
                basic_breakfast_price = form.cleaned_data['basic_breakfast_price'] or 0
                basic_lunch_price = form.cleaned_data['basic_lunch_price'] or 0
                basic_dinner_price = form.cleaned_data['basic_dinner_price'] or 0

                # 基本食の登録
                new_price_basic = NewUnitPrice(
                    username=user,
                    menu_name='常食',
                    price_breakfast=basic_breakfast_price,
                    price_lunch=basic_lunch_price,
                    price_dinner=basic_dinner_price,
                    price_snack=0,
                    eating_day=enable_day
                )
                new_price_basic.save()

                enge_breakfast_price = form.cleaned_data['enge_breakfast_price'] or 0
                enge_lunch_price = form.cleaned_data['enge_lunch_price'] or 0
                enge_dinner_price = form.cleaned_data['enge_dinner_price'] or 0

                # 嚥下の登録
                for menu in ['ゼリー', 'ミキサー', 'ソフト']:
                    new_price_enge = NewUnitPrice(
                        username=user,
                        menu_name=menu,
                        price_breakfast=enge_breakfast_price,
                        price_lunch=enge_lunch_price,
                        price_dinner=enge_dinner_price,
                        price_snack=0,
                        eating_day=enable_day
                    )
                    new_price_enge.save()

                return redirect('web_order:new_price_history', pk=user.id)

            else:
                messages.error(request, f'指定された変更価格適用(売上計上日)の単価変更は既に登録済みです。')
                context = {
                    'user': user,
                    'form': form
                }
                return render(request, template_name=self.template_name, context=context)
        else:
            context = {
                'user': user,
                'form': form
            }
            return render(request, template_name=self.template_name, context=context)


class NewUnitPriceList(ListView):
    """
    単価情報一覧ビュー
    """
    model = NewUnitPrice
    template_name = 'new_price_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = User.objects.filter(is_parent=False, is_staff=False, is_active=True).order_by('username')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        user_list = context['object_list']
        object_list = []
        today = dt.datetime.today()
        for user in user_list:
            # 基本食
            menu_basic = MenuDisplay.objects.filter(username=user, menu_name__menu_name='常食').first()
            changed_basic_prices = NewUnitPrice.objects.filter(
                username=user, menu_name='常食', eating_day__lte=today).order_by('-eating_day').first()
            if menu_basic:
                if changed_basic_prices:
                    # 単価変更あり
                    basic_price = [
                        changed_basic_prices.price_breakfast, changed_basic_prices.price_lunch, changed_basic_prices.price_dinner
                    ]
                else:
                    # システム稼働以来、単価変更なし
                    basic_price = [
                        menu_basic.price_breakfast, menu_basic.price_lunch, menu_basic.price_dinner
                    ]
            else:
                basic_price = [0, 0, 0]

            # 嚥下食
            enge_names = ['ソフト', 'ミキサー', 'ゼリー']
            menu_enge = MenuDisplay.objects.filter(username=user, menu_name__menu_name__in=enge_names).first()
            changed_enge_prices = NewUnitPrice.objects.filter(
                username=user, menu_name__in=enge_names, eating_day__lte=today).order_by('-eating_day').first()
            if menu_enge:
                if changed_enge_prices:
                    # 単価変更あり
                    enge_price = [
                        changed_enge_prices.price_breakfast, changed_enge_prices.price_lunch, changed_enge_prices.price_dinner
                    ]
                else:
                    # システム稼働以来、単価変更なし
                    enge_price = [
                        menu_enge.price_breakfast, menu_enge.price_lunch, menu_enge.price_dinner
                    ]
            else:
                enge_price = [0, 0, 0]

            # 単価変更予定
            reserved_list = list(NewUnitPrice.objects.filter(
                username=user, eating_day__gt=today).values('eating_day').distinct().order_by('eating_day'))
            reserved_len = len(reserved_list)
            if reserved_len == 0:
                next_reserved_day = None
                max_reserved_day = None
            elif reserved_len == 1:
                next_reserved_day = reserved_list[0]['eating_day']
                max_reserved_day = None
            else:
                next_reserved_day = reserved_list[0]['eating_day']
                max_reserved_day = reserved_list[-1]['eating_day']

            object_list.append({
                'facility_name': user.facility_name,
                'user_id': user.id,
                'price_basic_breakfast': basic_price[0],
                'price_basic_lunch': basic_price[1],
                'price_basic_dinner': basic_price[2],
                'price_enge_breakfast': enge_price[0],
                'price_enge_lunch': enge_price[1],
                'price_enge_dinner': enge_price[2],

                'next_reserved_day': next_reserved_day,
                'max_reserved_day': max_reserved_day
            })

        context['object_list'] = object_list
        return context


class NewUnitPriceUpdate(TemplateView):
    """
    単価情報更新ビュー
    """
    template_name = 'new_price_update.html'

    def get(self, request, **kwargs):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        new_price_id = kwargs['pk']
        delegate_new_price = NewUnitPrice.objects.get(id=new_price_id)

        # 対象単価情報の内容を取得-基本食
        basic_target_price = NewUnitPrice.objects.filter(
            username=delegate_new_price.username, menu_name='常食', eating_day=delegate_new_price.eating_day).first()
        if basic_target_price:
            basic_breakfast_price = basic_target_price.price_breakfast
            basic_lunch_price = basic_target_price.price_lunch
            basic_dinner_price = basic_target_price.price_dinner
        else:
            basic_breakfast_price = 0
            basic_lunch_price = 0
            basic_dinner_price = 0

        # 対象単価情報の内容を取得-嚥下
        enge_target_price = NewUnitPrice.objects.filter(
            username=delegate_new_price.username, menu_name__in=['ソフト', 'ゼリー', 'ミキサー'],
            eating_day=delegate_new_price.eating_day).first()
        if enge_target_price:
            enge_breakfast_price = enge_target_price.price_breakfast
            enge_lunch_price = enge_target_price.price_lunch
            enge_dinner_price = enge_target_price.price_dinner
        else:
            enge_breakfast_price = 0
            enge_lunch_price = 0
            enge_dinner_price = 0

        # フォームの取得
        initial_dict = {
            'basic_breakfast_price': basic_breakfast_price,
            'basic_lunch_price': basic_lunch_price,
            'basic_dinner_price': basic_dinner_price,
            'enge_breakfast_price': enge_breakfast_price,
            'enge_lunch_price': enge_lunch_price,
            'enge_dinner_price': enge_dinner_price,

            'enable_day': delegate_new_price.eating_day,
        }
        form = NewUnitPriceForm(None, initial=initial_dict)

        # 直近単価の取得-基本食
        basic_prev_price = NewUnitPrice.objects.filter(
            username=delegate_new_price.username, menu_name='常食',
            eating_day__lt=delegate_new_price.eating_day).order_by('-eating_day').first()
        if basic_prev_price:
            basic_breakfast_prev_price = basic_prev_price.price_breakfast
            basic_lunch_prev_price = basic_prev_price.price_lunch
            basic_dinner_prev_price = basic_prev_price.price_dinner
        else:
            # 施設毎_献立種類から取得
            prev_menu = MenuDisplay.objects.filter(username=delegate_new_price.username, menu_name__menu_name='常食').first()
            if prev_menu:
                basic_breakfast_prev_price = prev_menu.price_breakfast
                basic_lunch_prev_price = prev_menu.price_lunch
                basic_dinner_prev_price = prev_menu.price_dinner
            else:
                basic_breakfast_prev_price = 0
                basic_lunch_prev_price = 0
                basic_dinner_prev_price = 0

        # 直近単価の取得-嚥下食
        enge_prev_price = NewUnitPrice.objects.filter(
            username=delegate_new_price.username, menu_name__in=['ソフト', 'ゼリー', 'ミキサー'],
            eating_day__lt=delegate_new_price.eating_day).order_by('-eating_day').first()
        if enge_prev_price:
            enge_breakfast_prev_price = enge_prev_price.price_breakfast
            enge_lunch_prev_price = enge_prev_price.price_lunch
            enge_dinner_prev_price = enge_prev_price.price_dinner
        else:
            # 施設毎_献立種類から取得
            prev_menu = MenuDisplay.objects.filter(
                username=delegate_new_price.username, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).first()
            if prev_menu:
                enge_breakfast_prev_price = prev_menu.price_breakfast
                enge_lunch_prev_price = prev_menu.price_lunch
                enge_dinner_prev_price = prev_menu.price_dinner
            else:
                enge_breakfast_prev_price = 0
                enge_lunch_prev_price = 0
                enge_dinner_prev_price = 0

        context = {
            'disable_day_error': True,
            'user': delegate_new_price.username,
            'form': form,

            'basic_breakfast_prev_price': basic_breakfast_prev_price,
            'basic_lunch_prev_price': basic_lunch_prev_price,
            'basic_diner_prev_price': basic_dinner_prev_price,

            'enge_breakfast_prev_price': enge_breakfast_prev_price,
            'enge_lunch_prev_price': enge_lunch_prev_price,
            'enge_diner_prev_price': enge_dinner_prev_price,
        }
        return render(request, template_name=self.template_name, context=context)

    def validate_enable_day(self, user, enable_day, ignore_ids):
        if NewUnitPrice.objects.filter(username=user, eating_day=enable_day).exclude(id__in=ignore_ids).exists():
            return False
        else:
            return True

    def post(self, request, **kwargs):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        price_id = kwargs['pk']
        delegate_new_price = NewUnitPrice.objects.get(id=price_id)
        user = delegate_new_price.username

        #　基本食・嚥下の契約有無を取得
        is_basic_enable = MenuDisplay.objects.filter(
            username=user, menu_name__menu_name='常食').exists()
        is_enge_enable = MenuDisplay.objects.filter(
            username=user, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).exists()

        # 更新対象のID取得
        target_ids = [x.id for x in NewUnitPrice.objects.filter(username=user, eating_day=delegate_new_price.eating_day)]

        form = NewUnitPriceForm(request.POST)
        if form.is_valid():
            enable_day = form.cleaned_data['enable_day']
            if self.validate_enable_day(user, enable_day, target_ids):
                if is_basic_enable:
                    basic_breakfast_price = form.cleaned_data['basic_breakfast_price'] or 0
                    basic_lunch_price = form.cleaned_data['basic_lunch_price'] or 0
                    basic_dinner_price = form.cleaned_data['basic_dinner_price'] or 0

                    # 基本食の登録
                    new_price_basic, _ = NewUnitPrice.objects.get_or_create(
                        username=user,
                        menu_name='常食',
                        eating_day=enable_day
                    )
                    new_price_basic.price_breakfast = basic_breakfast_price
                    new_price_basic.price_lunch = basic_lunch_price
                    new_price_basic.price_dinner = basic_dinner_price
                    new_price_basic.save()

                if is_enge_enable:
                    enge_breakfast_price = form.cleaned_data['enge_breakfast_price'] or 0
                    enge_lunch_price = form.cleaned_data['enge_lunch_price'] or 0
                    enge_dinner_price = form.cleaned_data['enge_dinner_price'] or 0

                    # 嚥下の登録
                    for menu in ['ゼリー', 'ミキサー', 'ソフト']:
                        # 基本食の登録
                        new_price_enge, _ = NewUnitPrice.objects.get_or_create(
                            username=user,
                            menu_name=menu,
                            eating_day=enable_day
                        )
                        new_price_enge.price_breakfast = enge_breakfast_price
                        new_price_enge.price_lunch = enge_lunch_price
                        new_price_enge.price_dinner = enge_dinner_price
                        new_price_enge.save()

                    messages.success(request, '更新しました。')
                    return redirect('web_order:new_price_history', pk=user.id)
            else:
                messages.error(request, f'指定された変更価格適用(売上計上日)の単価変更は既に登録済みです。')
                context = {
                    'user': user,
                    'form': form
                }
                return render(request, template_name=self.template_name, context=context)
        else:
            context = {
                'user': user,
                'form': form
            }
            return render(request, template_name=self.template_name, context=context)


class NewUnitPriceHistory(TemplateView):
    """
    単価情報詳細(履歴)ビュー
    """
    template_name = 'new_price_history.html'

    def _get_context(self, id):
        histories = []
        user = User.objects.get(id=id)
        menu_qs = MenuDisplay.objects.filter(username=user)

        # システム運用時の履歴を取得
        # -基本食
        basic_meal = menu_qs.filter(menu_name__menu_name='常食').first()
        if basic_meal:
            basic_prices = [basic_meal.price_breakfast, basic_meal.price_lunch, basic_meal.price_dinner]
        else:
            basic_prices = [0, 0, 0]

        # -嚥下食
        enge_meal = menu_qs.filter(menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).first()
        if enge_meal:
            enge_prices = [enge_meal.price_breakfast, enge_meal.price_lunch, enge_meal.price_dinner]
        else:
            enge_prices = [0, 0, 0]

        histories.append({
            'start': user.date_joined.date(),
            'price_id': None,
            'basic_price_breakfast': basic_prices[0],
            'basic_price_lunch': basic_prices[1],
            'basic_price_dinner': basic_prices[2],
            'enge_price_breakfast': enge_prices[0],
            'enge_price_lunch': enge_prices[1],
            'enge_price_dinner': enge_prices[2],
            'is_apply': False,
            'is_preserve': False,
        })

        basic_prev_prices = basic_prices
        enge_prev_prices = enge_prices
        price_qs = NewUnitPrice.objects.filter(username=user).order_by('eating_day')
        for key, group in groupby(price_qs, key=lambda x: x.eating_day):
            list_group = list(group)

            # -基本食
            basic_new_prices = [x for x in list_group if x.menu_name == '常食']
            if basic_new_prices:
                prices = basic_new_prices[0]
                basic_prices = [prices.price_breakfast, prices.price_lunch, prices.price_dinner]
            else:
                basic_prices = [basic_prev_prices[0], basic_prev_prices[1], basic_prev_prices[2]]

            # -嚥下食
            enge_new_prices = [x for x in list_group if x.menu_name in ['ソフト', 'ゼリー', 'ミキサー']]
            if enge_new_prices:
                prices = enge_new_prices[0]
                enge_prices = [prices.price_breakfast, prices.price_lunch, prices.price_dinner]
            else:
                enge_prices = [enge_prev_prices[0], enge_prev_prices[1], enge_prev_prices[2]]

            histories.append({
                'start': key,
                'price_id': list_group[0].id,
                'basic_price_breakfast': basic_prices[0],
                'basic_price_lunch': basic_prices[1],
                'basic_price_dinner': basic_prices[2],
                'enge_price_breakfast': enge_prices[0],
                'enge_price_lunch': enge_prices[1],
                'enge_price_dinner': enge_prices[2],
                'is_apply': False,
                'is_preserve': False,
            })

            # 次回ループ用
            basic_prev_prices = [basic_prices[0], basic_prices[1], basic_prices[2]]
            enge_prev_prices = [enge_prices[0], enge_prices[1], enge_prices[2]]

        # 範囲末尾、フラグの設定
        len_history = len(histories)
        today = dt.datetime.today().date()
        is_apply = False
        for index, history_dict in enumerate(histories):
            # 先の適用日を見て、設定の末尾を取得する
            if index == (len_history - 1):
                history_dict['end'] = None
            else:
                history_dict['end'] = histories[index + 1]['start'] - relativedelta(days=1)

            start_day = history_dict['start']
            end_day = history_dict['end']
            if is_apply:
                # 適用日現在以降のデータは全て予約データ
                history_dict['is_preserve'] = True
            if not is_apply:
                if end_day:
                    if (today >= start_day) and (today <= end_day):
                        is_apply = True
                        history_dict['is_apply'] = True
                    if (today == start_day) and (index > 0):
                        # 当日までは更新・削除可能とする
                        history_dict['is_preserve'] = True
                else:
                    # 末尾データ
                    is_apply = True
                    history_dict['end'] = today
                    history_dict['is_apply'] = True
                    if (today == start_day) and (index > 0):
                        # 当日までは更新・削除可能とする
                        history_dict['is_preserve'] = True

        context = {
            'user': user,
            'histories': histories
        }
        return context

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        context = self._get_context(kwargs['pk'])
        return render(request, template_name='new_price_history.html', context=context)


class NewUnitPriceDelete(TemplateView):
    """
    単価情報削除ビュー
    """
    template_name = 'new_price_history.html'

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        delegate_id = kwargs['delegate']
        delegate_new_price = NewUnitPrice.objects.get(id=delegate_id)

        #　代表として指定された変更情報と同日のデータを全削除する
        NewUnitPrice.objects.filter(username=delegate_new_price.username, eating_day=delegate_new_price.eating_day).delete()
        messages.success(request, '削除しました。')

        return redirect("web_order:new_price_history", pk=delegate_new_price.username.id)

# endregion


# region 仮注文特別対応
class PreorderSettingCreate(CreateView):
    """
    仮注文特別対応登録ビュー
    """
    model = UserOption
    template_name = 'pre_order_setting_create.html'
    form_class = PreorderSettingForm
    success_url = reverse_lazy('web_order:pre_order_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "登録に失敗しました。")
        return super().form_invalid(form)


class PreorderSettingList(ListView):
    """
    仮注文特別対応一覧ビュー
    """
    model = UserOption
    template_name = 'pre_order_setting_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = UserOption.objects.all().order_by('-id')
        return qs


class PreorderSettingUpdate(UpdateView):
    """
    仮注文特別対応更新ビュー
    """
    model = UserOption
    template_name = 'pre_order_setting_update.html'
    form_class = PreorderSettingForm

    def get_success_url(self):
        return reverse_lazy('web_order:pre_order_settings')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class PreorderSettingDelete(DeleteView):
    """
    仮注文特別対応削除ビュー
    """
    model = UserOption
    success_url = reverse_lazy('web_order:pre_order_settings')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)
# endregion


# region 注文データ_合数変更
class RiceOrderCreate(CreateView):
    """
    注文データ_合数登録ビュー
    """
    model = OrderRice
    template_name = 'rice_order_create.html'
    form_class = OrderRiceMasterForm
    success_url = reverse_lazy('web_order:rice_orders')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        today = dt.datetime.today().date()
        context['adjust_days'] = SalesDayUtil.get_adjust_days_settings(today)
        return context

class RiceOrderList(ListView):
    """
    注文データ_合数一覧ビュー
    """
    model = OrderRice
    template_name = 'rice_orders.html'
    search_conditions = {}

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        # 検索条件指定内容を取得
        self.get_conditions(request)

        return super().get(request)

    def get_queryset(self):
        min_day = dt.datetime.today().date() - relativedelta(days=90)
        qs = OrderRice.objects.filter(eating_day__gte=min_day).order_by('-eating_day', 'unit_name__unit_number')
        return qs

    def get_conditions(self, request):
        conditions = {
            'eating_day': None,
            'unit': '0'
        }

        # 条件解除ボタン押下の取得
        clear = request.GET.get('clear', None)
        if clear:
            # 解除ボタンが推されたため、デフォルトに戻す
            pass
        else:
            # 検索条件の取得
            # -喫食日
            eating_day = request.GET.get('eating_day', None)
            if eating_day:
                conditions['eating_day'] = dt.datetime.strptime(eating_day, '%Y-%m-%d')

            # -施設
            unit = self.request.GET.get('unit', None)
            if unit:
                conditions['unit'] = unit

        self.search_conditions = conditions

    def _is_match_condition(self, unit, order_eating_day):
        """
        検索条件によって除外対象となるかどうかを判定
        """
        # 喫食日
        eating_day = self.search_conditions['eating_day']
        if eating_day:
            if eating_day.date() != order_eating_day:
                return False

        # 施設名
        unit_id = self.search_conditions['unit']
        if unit_id and (unit_id != '0'):
            if unit.id != int(unit_id):
                return False

        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        order_rice_list = context['object_list']
        object_list = []
        for order_rice in order_rice_list:
            if not self._is_match_condition(order_rice.unit_name, order_rice.eating_day):
                # 条件に合わない施設は含めない
                continue

            object_list.append(order_rice)

        context['object_list'] = object_list

        # 検索条件の設定
        context['eating_day'] = self.search_conditions['eating_day']
        context['unit'] = self.search_conditions['unit']

        # フィルタリング候補の取得
        context['filter_units'] = [
            (str(x.id) == self.search_conditions['unit'], x) for x in UnitMaster.objects.filter(is_active=True).\
            exclude(unit_code__range=[50001, 50002]).\
            exclude(unit_code__range=[80001, 80010]).order_by('unit_number')]

        return context

class RiceOrderUpdate(UpdateView):
    """
    注文データ_合数更新ビュー
    """
    model = OrderRice
    template_name = 'rice_order_update.html'
    form_class = OrderRiceMasterUpdateForm

    def get_success_url(self):
        return reverse_lazy('web_order:rice_orders')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        form = context['form']

        today = dt.datetime.today().date()
        adjust_days = SalesDayUtil.get_adjust_days_settings(today)
        limit_day = today + relativedelta(days=adjust_days+1)
        is_disable = limit_day > form.initial['eating_day']

        context['adjust_days'] = adjust_days
        context['disable_processing'] = is_disable
        return context


# endregion


# region 長期休暇
class LongHolidaysCreate(CreateView):
    """
    長期休暇登録ビュー
    """
    model = HolidayList
    template_name = 'long_holidays_create.html'
    form_class = LongHolidayForm
    success_url = reverse_lazy('web_order:long_holidays_list')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class LongHolidaysList(ListView):
    """
    長期休暇一覧ビュー
    """
    model = HolidayList
    template_name = 'long_holidays_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = HolidayList.objects.all().order_by('-limit_day')
        return qs


class LongHolidaysUpdate(UpdateView):
    """
    長期休暇更新ビュー
    """
    model = HolidayList
    template_name = 'long_holidays_update.html'
    form_class = LongHolidayForm

    def get_success_url(self):
        return reverse_lazy('web_order:long_holidays_list')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 元旦注文設定
class NewYearSettingCreate(CreateView):
    """
    元旦注文設定登録ビュー
    """
    model = NewYearDaySetting
    template_name = 'new_year_setting_create.html'
    form_class = NewYearDaySettingForm
    success_url = reverse_lazy('web_order:new_year_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class NewYearSettingList(ListView):
    """
    元旦注文設定一覧ビュー
    """
    model = NewYearDaySetting
    template_name = 'new_year_setting_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = NewYearDaySetting.objects.all().order_by('-year')
        return qs


class NewYearSettingUpdate(UpdateView):
    """
    元旦注文設定更新ビュー
    """
    model = NewYearDaySetting
    template_name = 'new_year_setting_update.html'
    form_class = NewYearDaySettingForm

    def get_success_url(self):
        return reverse_lazy('web_order:new_year_settings')

    def form_valid(self, form):
        messages.success(self.request, '更新しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region アレルギーマスタ設定
class AllergenMasterCreate(CreateView):
    """
    アレルギーマスタ登録ビュー
    """
    model = AllergenMaster
    template_name = 'allergen_master_create.html'
    form_class = AllergenMasterCreateForm
    success_url = reverse_lazy('web_order:allergen_masters')

    def _get_seq_order(self):
        allergen_id = self.request.POST.get('display_orders', '0')
        if allergen_id != '0':
            allergen = AllergenMaster.objects.get(id=allergen_id)
            seq = allergen.seq_order + 1
        else:
            seq = 1

        # seqに他のアレルギーが存在していれば、ところてん式にずらしていく
        # 同一seq_orderは存在しない前提
        next_seq = seq
        ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']
        update_allergen = AllergenMaster.objects.filter(seq_order=next_seq).exclude(
            allergen_name__in=ignore_allergen_names).order_by('seq_order', '-id').first()
        while update_allergen:
            next_seq = update_allergen.seq_order + 1
            update_allergen.seq_order = next_seq
            update_allergen.save()

            update_allergen = AllergenMaster.objects.filter(seq_order=next_seq).exclude(
                allergen_name__in=ignore_allergen_names).exclude(
                id=update_allergen.id).order_by('seq_order', '-id').first()

        return seq

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.seq_order = self._get_seq_order()
        instance.save()

        # カルテの更新
        path = os.path.join(settings.MEDIA_ROOT, "user_karte")
        writer = KarteWriter(path, "karte.xlsx")
        writer.refreesh()

        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class AllergenMasterList(ListView):
    """
    アレルギーマスタ一覧ビュー
    """
    model = AllergenMaster
    template_name = 'allergen_master_list.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']
        qs = AllergenMaster.objects.all().exclude(allergen_name__in=ignore_allergen_names).order_by('seq_order', '-id')
        return qs


class AllergenMasterUpdate(UpdateView):
    """
    アレルギーマスタ更新ビュー
    """
    model = AllergenMaster
    template_name = 'allergen_master_update.html'
    form_class = AllergenMasterUpdateForm

    def get_success_url(self):
        return reverse_lazy('web_order:allergen_masters')

    def _get_seq_order(self, instance):
        allergen_id = self.request.POST.get('display_orders', '')
        if allergen_id and (allergen_id != '0'):
            allergen = AllergenMaster.objects.get(id=allergen_id)
            seq = allergen.seq_order + 1
        elif allergen_id == '0':
            seq = 1
        else:
            seq = None

        if seq:
            # seqに他のアレルギーが存在していれば、ところてん式にずらしていく
            # 同一seq_orderは存在しない前提。自分のIDは対象外となるように制御
            next_seq = seq
            ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']
            update_allergen = AllergenMaster.objects.filter(seq_order=next_seq).exclude(
                allergen_name__in=ignore_allergen_names).exclude(
                id=instance.id).order_by('seq_order', '-id').first()
            while update_allergen:
                next_seq = update_allergen.seq_order + 1
                update_allergen.seq_order = next_seq
                update_allergen.save()

                update_allergen = AllergenMaster.objects.filter(seq_order=next_seq).exclude(
                    allergen_name__in=ignore_allergen_names).exclude(
                    id__in=[update_allergen.id, instance.id]).order_by('seq_order', '-id').first()

        return seq

    def form_valid(self, form):
        instance = form.save(commit=False)
        seq_order = self._get_seq_order(instance)
        if seq_order is not None:
            instance.seq_order = seq_order
        instance.save()

        # カルテの更新
        path = os.path.join(settings.MEDIA_ROOT, "user_karte")
        writer = KarteWriter(path, "karte.xlsx")
        writer.refreesh()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 施設別_売上日数調整設定
class AllergenSettingList(ListView):
    """
    施設別_アレルギー設定覧ビュー
    """
    model = AllergenDisplay
    template_name = 'allergen_settings.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = AllergenDisplay.objects.all().order_by('username')
        return qs


class AllergenSettingCreate(CreateView):
    """
    施設別_アレルギー設定登録ビュー
    """
    model = AllergenMaster
    template_name = 'allergen_setting_create.html'
    form_class = AllergenSettingForm
    success_url = reverse_lazy('web_order:allergen_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class AllergenSettingUpdate(UpdateView):
    """
    施設別_アレルギー設定更新ビュー
    """
    model = AllergenDisplay
    template_name = 'allergen_setting_update.html'
    form_class = AllergenSettingForm

    def get_success_url(self):
        return reverse_lazy('web_order:allergen_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 施設別_売上日調整日数設定
class SalesDaySettingList(ListView):
    """
    施設別_売上日調整日数一覧ビュー
    """
    model = InvoiceException
    template_name = 'sales_day_settings.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = InvoiceException.objects.all().order_by('unit_name__unit_number')
        return qs


class SalesDaySettingCreate(CreateView):
    """
    施設別_売上日調整日数登録ビュー
    """
    model = InvoiceException
    template_name = 'sales_day_setting_create.html'
    form_class = SalesDaySettingForm
    success_url = reverse_lazy('web_order:sales_day_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class SalesDaySettingUpdate(UpdateView):
    """
    施設別_売上日調整日数更新ビュー
    """
    model = InvoiceException
    template_name = 'sales_day_setting_update.html'
    form_class = SalesDaySettingForm

    def get_success_url(self):
        return reverse_lazy('web_order:sales_day_settings')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 混ぜご飯袋サイズ設定
class MixRicePackageList(ListView):
    """
    混ぜご飯袋サイズ一覧ビュー
    """
    model = MixRicePackageMaster
    template_name = 'mix_rice_package_settings.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = MixRicePackageMaster.objects.all().order_by('-id')
        return qs


class MixRicePackageCreate(CreateView):
    """
    混ぜご飯袋サイズ登録ビュー
    """
    model = MixRicePackageMaster
    template_name = 'mix_rice_package_create.html'
    form_class = MixRicePackageForm
    success_url = reverse_lazy('web_order:mix_rice_packages')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.parts_name = instance.parts_name.strip()
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class MixRicePackageUpdate(UpdateView):
    """
    混ぜご飯袋サイズ更新ビュー
    """
    model = MixRicePackageMaster
    template_name = 'mix_rice_package_update.html'
    form_class = MixRicePackageForm

    def get_success_url(self):
        return reverse_lazy('web_order:mix_rice_packages')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.parts_name = instance.parts_name.strip()
        instance.save()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class MixRicePackageDelete(DeleteView):
    """
    混ぜご飯袋サイズ削除ビュー
    """
    model = MixRicePackageMaster
    success_url = reverse_lazy('web_order:mix_rice_packages')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)
# endregion


# region 献立定型文
class SetOutDirectionList(ListView):
    """
    献立定型文一覧ビュー
    """
    model = GenericSetoutDirection
    template_name = 'set_out_directions.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = GenericSetoutDirection.objects.all().order_by('-id')
        return qs


class SetOutDirectionCreate(CreateView):
    """
    献立定型文登録ビュー
    """
    model = GenericSetoutDirection
    template_name = 'set_out_direction_create.html'
    form_class = SetOutDirectionForm
    success_url = reverse_lazy('web_order:set_out_directions')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class SetOutDirectionUpdate(UpdateView):
    """
    献立定型文更新ビュー
    """
    model = GenericSetoutDirection
    template_name = 'set_out_direction_update.html'
    form_class = SetOutDirectionForm

    def get_success_url(self):
        return reverse_lazy('web_order:set_out_directions')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class SetOutDirectionDelete(DeleteView):
    """
    献立定型文削除ビュー
    """
    model = GenericSetoutDirection
    success_url = reverse_lazy('web_order:set_out_directions')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)
# endregion


# region 献立資料フォルダ
class DocumentFolderList(ListView):
    """
    献立資料フォルダ一覧ビュー
    """
    model = DocumentDirDisplay
    template_name = 'document_folders.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = DocumentDirDisplay.objects.all().order_by('username', 'plate_dir_name')
        return qs


class DocumentFolderCreate(CreateView):
    """
    献立資料フォルダ登録ビュー
    """
    model = DocumentDirDisplay
    template_name = 'document_folder_create.html'
    form_class = DocumentFolderForm
    success_url = reverse_lazy('web_order:document_folders')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class DocumentFolderUpdate(UpdateView):
    """
    献立資料フォルダ更新ビュー
    """
    model = DocumentDirDisplay
    template_name = 'document_folder_update.html'
    form_class = DocumentFolderForm

    def get_success_url(self):
        return reverse_lazy('web_order:document_folders')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.save()

        messages.success(self.request, '更新しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class DocumentFolderDelete(DeleteView):
    """
    献立資料フォルダ削除ビュー
    """
    model = DocumentDirDisplay
    success_url = reverse_lazy('web_order:document_folders')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)
# endregion


# 税率設定
class TaxSettingsView(TemplateView):
    """
    税率設定画面ビュー
    """
    template_name = 'tax_settings.html'

    def get_context(self):
        is_subcontracting_setting = TaxSetting.objects.filter(is_subcontracting=True).first()
        if is_subcontracting_setting:
            is_subcontracting_setting_id = is_subcontracting_setting.rate.id
        else:
            is_subcontracting_setting_id = None

        not_subcontracting_setting = TaxSetting.objects.filter(is_subcontracting=False).first()
        if not_subcontracting_setting:
            not_subcontracting_setting_id = not_subcontracting_setting.rate.id
        else:
            not_subcontracting_setting_id = None

        tax_masters = TaxMaster.objects.all().order_by('code')

        # 販売固定商品一覧
        fix_products = EverydaySelling.objects.all().values('product_code', 'product_name').distinct()
        object_list = []
        sub_list = []
        for fp in fix_products:
            fp['ins'] = TaxEverydaySellingSetting.objects.filter(product_code=fp['product_code']).first()
            sub_list.append(fp)
            if len(sub_list) == 2:
                object_list.append(sub_list)
                sub_list = []
        if sub_list:
            object_list.append(sub_list)

        context = {
            'is_subcontracting_setting': is_subcontracting_setting,
            'not_subcontracting_setting': not_subcontracting_setting,
            'tax_masters': tax_masters,
            'object_list': object_list,
            'form': TaxSettingsForm(
                initial={'subcontracting': is_subcontracting_setting_id, 'notcontracting': not_subcontracting_setting_id})
        }

        return context

    def get(self, request, **kwargs):
        context = self.get_context()

        return self.render_to_response(context)

    def post(self, request, **kwargs):
        form = TaxSettingsForm(request.POST)

        if form.is_valid():
            s = form.cleaned_data['subcontracting']
            n = form.cleaned_data['notcontracting']

            # 設定内容の保存
            subcontracting = TaxSetting.objects.filter(is_subcontracting=True).first()
            subcontracting.rate = TaxMaster.objects.get(id=s)
            subcontracting.save()

            not_subcontracting = TaxSetting.objects.filter(is_subcontracting=False).first()
            not_subcontracting.rate = TaxMaster.objects.get(id=n)
            not_subcontracting.save()

            fix_products = EverydaySelling.objects.all().values('product_code', 'product_name').distinct()
            for fp in fix_products:
                selected = request.POST.get(f'tax_{fp["product_code"]}', None)
                if selected:
                    tax_master = TaxMaster.objects.get(id=selected)
                    setting, is_created = TaxEverydaySellingSetting.objects.update_or_create(
                        product_code=fp['product_code'], defaults={"rate_id": 1})
                    setting.rate = tax_master
                    setting.save()

            messages.success(request, '登録しました。')

        context = self.get_context()

        return self.render_to_response(context)
# endregion


# 施設登録
class UserListView(ListView):
    """
    施設一覧ビュー
    """
    model = User
    template_name = 'user_master_list.html'
    search_conditions = {}

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')

        # 検索条件指定内容を取得
        self.get_conditions(request)

        return super().get(request)

    def get_queryset(self):
        qs = User.objects.filter(is_parent=False, is_staff=False).\
            exclude(username__range=[50001, 50002]).\
            exclude(username__range=[80001, 80010]).order_by('username')

        return qs

    def get_conditions(self, request):
        conditions = {
            'menu_name': 'all',
            'options': ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
            'dry_cold': 'all',
            'status': 'all',
            'parent': '',
            'user': '0'
        }

        # 条件解除ボタン押下の取得
        clear = request.GET.get('clear', None)
        if clear:
            # 解除ボタンが推されたため、デフォルトに戻す
            pass
        else:
            # 検索条件の取得
            # -献立種類
            menu_name = request.GET.get('menu_name', None)
            if menu_name:
                conditions['menu_name'] = menu_name

            # -汁オプション
            options = self.request.GET.getlist('option', None)
            if options:
                conditions['options'] = options

            # -乾燥冷凍区分
            dry_cold = self.request.GET.get('dry_cold', None)
            if dry_cold:
                conditions['dry_cold'] = dry_cold

            # -運用状態
            status = self.request.GET.get('status', None)
            if status:
                conditions['status'] = status

            # -親会社
            parent = self.request.GET.get('parent', None)
            if parent:
                conditions['parent'] = parent

            # -施設
            user = self.request.GET.get('user', None)
            if user:
                conditions['user'] = user

        self.search_conditions = conditions

    def _is_match_condition(self, user):
        """
        検索条件によって除外対象となるかどうかを判定
        """
        # 献立種類
        menu_name = self.search_conditions['menu_name']
        if menu_name == 'basic':
            if not MenuDisplay.objects.filter(username=user, menu_name__menu_name='常食').exists():
                return False
        elif menu_name == 'enge':
            if not MenuDisplay.objects.filter(username=user, menu_name__menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).exists():
                return False

        # 汁オプション
        is_option_match = False
        for meal_display in MealDisplay.objects.filter(username=user).select_related('meal_name'):
            meal = meal_display.meal_name
            for option_condition in self.search_conditions['options']:
                # 朝食 汁具
                if (option_condition == '1') and (meal.meal_name == '朝食') and meal.soup and meal.filling:
                    is_option_match = True
                    break

                # 朝食 具のみ
                if (option_condition == '2') and (meal.meal_name == '朝食') and (not meal.soup) and meal.filling:
                    is_option_match = True
                    break

                # 朝食 具のみ
                if (option_condition == '3') and (meal.meal_name == '朝食') and (not meal.soup) and (not meal.filling):
                    is_option_match = True
                    break

                # 昼食 汁具
                if (option_condition == '4') and (meal.meal_name == '昼食') and meal.soup and meal.filling:
                    is_option_match = True
                    break

                # 昼食 具のみ
                if (option_condition == '5') and (meal.meal_name == '昼食') and (not meal.soup) and meal.filling:
                    is_option_match = True
                    break

                # 昼食 具のみ
                if (option_condition == '6') and (meal.meal_name == '昼食') and (not meal.soup) and (not meal.filling):
                    is_option_match = True
                    break

                # 夕食 汁具
                if (option_condition == '7') and (meal.meal_name == '夕食') and meal.soup and meal.filling:
                    is_option_match = True
                    break

                # 夕食 具のみ
                if (option_condition == '8') and (meal.meal_name == '夕食') and (not meal.soup) and meal.filling:
                    is_option_match = True
                    break

                # 夕食 具のみ
                if (option_condition == '9') and (meal.meal_name == '夕食') and (not meal.soup) and (not meal.filling):
                    is_option_match = True
                    break

            if is_option_match:
                break

        if not is_option_match:
            return False

        # 乾燥冷凍区分
        dry_cold = self.search_conditions['dry_cold']
        if dry_cold == 'dry':
            if user.dry_cold_type != '乾燥':
                return False
        elif dry_cold == 'cold':
            if not (user.dry_cold_type in ['冷凍', '冷凍_談']):
                return False

        # 運用状態
        status = self.search_conditions['status']
        has_units = UnitMaster.objects.filter(username=user, is_active=True).exists()
        if status == 'running':
            if not (user.is_active and has_units):
                return False
        elif status == 'order_stop':
            if not user.is_active:
                # ログイン停止中なので対象外
                return False
            if has_units:
                # 注文停止中なので対象外
                return False
        elif status == 'login_stop':
            if user.is_active:
                return False

        # 親会社
        parent_id = self.search_conditions['parent']
        if parent_id:
            if parent_id == '0':
                # 親会社なし
                if User.objects.filter(company_name=user.company_name, is_parent=True).exists():
                    # 親会社があるので対象外
                    return False
            else:
                parent_user = User.objects.get(id=parent_id)
                if user.company_name != parent_user.company_name:
                    return False

        # 施設名
        user_id = self.search_conditions['user']
        if user_id and (user_id != '0'):
            if user.id != int(user_id):
                return False

        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        user_list = context['object_list']
        object_list = []
        for user in user_list:
            if not self._is_match_condition(user):
                # 条件に合わない施設は含めない
                continue

            # ユニットの取得
            unit_qs = UnitMaster.objects.filter(username=user)
            if len(unit_qs) > 1:
                display_unit = '複数'
            else:
                unit = unit_qs.first()
                display_unit = f'{unit.unit_number}.{unit.unit_name}'

            # 契約開始日
            reserved = UserCreationInput.objects.filter(
                company_name=user.company_name, facility_name=user.facility_name).order_by('-id').first()

            # 運用状態
            if reserved and (reserved.enable_start_day > dt.datetime.today().date()):
                status = '運用前'
            elif user.is_active:
                if unit_qs.filter(is_active=True).exists():
                    status = '運用中'
                else:
                    status = '注文停止中'
            else:
                status = 'ログイン停止中'

            # 乾燥・冷凍
            if user.dry_cold_type == '乾燥':
                display_dry_cold = '乾燥'
            elif user.dry_cold_type == '冷凍':
                display_dry_cold = '冷凍(直送)'
            elif user.dry_cold_type == '冷凍_談':
                display_dry_cold = '冷凍(談から送る)'
            else:
                display_dry_cold = '不正値'

            object_list.append({
                'pk': user.id,
                'name': user.facility_name,
                'code': user.username,
                'company_name': user.company_name,
                'unit': display_unit,
                'start': reserved.enable_start_day if reserved else None,
                'status': status,
                'dry_cold': display_dry_cold
            })

        context['object_list'] = object_list

        # 検索条件の設定
        context['menu_name'] = self.search_conditions['menu_name']
        context['options'] = self.search_conditions['options']
        context['dry_cold'] = self.search_conditions['dry_cold']
        context['status'] = self.search_conditions['status']
        context['parent'] = self.search_conditions['parent']
        context['user'] = self.search_conditions['user']

        # フィルタリング候補の取得
        context['parent_companies'] = [(str(x.id) == self.search_conditions['parent'], x) for x in User.objects.filter(is_parent=True).order_by('username')]
        context['filter_users'] = [
            (str(x.id) == self.search_conditions['user'], x) for x in User.objects.filter(is_parent=False, is_staff=False).\
            exclude(username__range=[50001, 50002]).\
            exclude(username__range=[80001, 80010]).order_by('username')]

        return context


class UserListForUpdateView(UserListView):
    """
    施設一覧(施設更新用)ビュー
    """
    template_name = 'user_master_list_for_update.html'


# 施設更新
class UserUpdateView(TemplateView):
    template_name = 'user_dry_cold_update.html'

    def get(self, request, pk):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        user = User.objects.get(id=pk)

        context = {
            'user': user,
            'form': UserDryColdUpdateForm(instance=user)
        }
        return render(request, template_name=self.template_name, context=context)

    def post(self, request, pk):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        user = User.objects.get(id=pk)
        form = UserDryColdUpdateForm(request.POST, instance=user)
        if form.is_valid():
            ins = form.save(commit=False)
            ins.save()
            messages.success(request, '更新しました。')
        else:
            messages.error(request, '更新に失敗しました。')

        return redirect("web_order:user_masters")


# カルテダウンロード
class KarteDownloadView(TemplateView):
    template_name = 'unit_import.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        path = os.path.join(settings.MEDIA_ROOT, "user_karte", "karte.xlsx")

        if path:
            return FileResponse(
                open(path, 'rb'), as_attachment=True,
                filename=settings.KARTE_FORMAT_DOWNLOAD_NAME)
        else:
            return HttpResponse('カルテのテンプレートファイルに異常が発生しました。', status=500)


# 登録施設情報CSVダウンロード
class UserAccountCsvDownloadView(TemplateView):
    template_name = 'unit_import.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        user_id = kwargs['pk']
        target_user = User.objects.get(id=user_id)
        taregt_input = UserCreationInput.objects.filter(
            company_name=target_user.company_name, facility_name=target_user.facility_name).order_by('-id').first()
        if taregt_input:
            new_dir_path = os.path.join(settings.OUTPUT_DIR, 'user_input', str(taregt_input.import_file.id))
            os.makedirs(new_dir_path, exist_ok=True)
            filename = new_dir_path + "/施設登録情報.csv"

            # 同一ファイル内の同一施設をまとめて出力
            input_qs = UserCreationInput.objects.filter(
                import_file=taregt_input.import_file, company_name=taregt_input.company_name).values(
                'company_name', 'facility_name')
            input_df = read_frame(input_qs)

            user_qs = User.objects.filter(is_active=True).values(
                'id', 'username', 'company_name', 'facility_name', 'invoice_pass'
            ).order_by('username')
            user_df = read_frame(user_qs)

            merged_df = pd.merge(user_df, input_df, on=['company_name', 'facility_name'], how='inner')

            # ユニット単位で出力する(請求情報はユニット単位に出力)ため、結合
            unit_qs = UnitMaster.objects.filter(is_active=True).values(
                'username__id', 'unit_number', 'unit_name', 'unit_code'
            )
            unit_df = read_frame(unit_qs)
            merged_df = pd.merge(merged_df, unit_df, left_on='id', right_on='username__id', how='inner')

            parent = None
            for index, data in merged_df.iterrows():
                merged_df.loc[index, 'ログインパスワード'] = f'dan{data["username"]}'

                user = User.objects.get(id=data["id"])

                # 親会社の検索
                tmp_parent = User.objects.filter(is_active=True, is_parent=True, facility_name=user.company_name).first()
                if tmp_parent:
                    parent = tmp_parent
                    merged_df.loc[index, 'invoice_pass'] = ''

            merged_df = merged_df.rename(columns={'unit_number': '呼出番号',
                                                  'unit_code': '得意先コード'})

            if parent:
                # 親会社の追加
                df2 = pd.DataFrame({
                    'id': [parent.id],
                    'company_name': [parent.company_name], 'facility_name': [parent.facility_name],
                    'username': [parent.username], 'invoice_pass': [parent.invoice_pass], 'unit_name': [parent.facility_name],
                    'ログインパスワード': [f'dan{parent.username}'], '呼出番号': [''], '得意先コード': [parent.username]
                })
                merged_df = pd.concat([merged_df, df2])
            elif len(merged_df) > 1:
                # 販売登録情報の追加
                df2 = pd.DataFrame({
                    'id': [0],
                    'company_name': [merged_df.loc[0, 'company_name']], 'facility_name': [merged_df.loc[0, 'company_name']],
                    'username': [''], 'invoice_pass': [''], 'unit_name': [merged_df.loc[0, 'company_name']],
                    'ログインパスワード': [''], '呼出番号': [''], '得意先コード': [f"9{merged_df.loc[0, 'username']}"]
                })
                merged_df = pd.concat([merged_df, df2])


            # 列名を変更
            merged_df = merged_df.rename(columns={'company_name': '会社名',
                                                  'unit_name': 'ユニット名',
                                                  'username': 'ログインID',
                                                  'invoice_pass': '請求書確認用パスワード'})

            # CSVに不要な列を削除
            merged_df = merged_df.drop(columns=['id', 'username__id', 'facility_name'])
            merged_df = merged_df[
                ['会社名', 'ユニット名', 'ログインID', 'ログインパスワード', '請求書確認用パスワード', '呼出番号', '得意先コード']]

            # ファイル出力
            merged_df.to_csv(filename, index=False, header=True, encoding='cp932')

            return FileResponse(
                open(filename, 'rb'), as_attachment=True,
                filename="施設登録情報.csv")
        else:
            return HttpResponse('対象データが不正です。', status=401)


# 頻発アレルギー設定画面
class CommonAllergensView(TemplateView):
    def _get_context(self):
        allergens_qs = CommonAllergen.objects.all().select_related('allergen').order_by('seq_order')

        object_list = []
        prev_seq = 1
        for key, group in groupby(allergens_qs, key=lambda x: x.seq_order):
            obj = next(group)
            id = obj.id
            code = obj.code
            name = obj.name
            menu_name = obj.menu_name
            seq_order = key - settings.COMMON_ALLERGEN_MINIMUM_INDEX
            allergen_list = [obj.allergen.allergen_name,]

            # 同一に設定される他のアレルギーを取得
            try:
                obj = next(group)
                while obj:
                    allergen_list += [obj.allergen.allergen_name,]
                    obj = next(group)
            except StopIteration:
                pass

            # 空き番を埋める
            diff = seq_order - prev_seq
            if diff > 1:
                for i in range(diff - 1):
                    object_list.append({
                        'id': 0,
                        'code': '-',
                        'name': '(頻発アレルギー以外の食種)',
                        'menu_name': '-',
                        'seq_order': prev_seq + i + 1,
                        'allergens': '-'
                    })

            # 頻発アレルギーを設定
            object_list.append({
                'id': id,
                'code': code,
                'name': name,
                'menu_name': menu_name,
                'seq_order': seq_order,
                'allergens': ",".join(allergen_list)
            })

            prev_seq = seq_order

        context = {
            'object_list': object_list,
            'form': CommonAllergenForm()
        }

        return context

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        context = self._get_context()
        return render(request, template_name='common_allergens_settings.html', context=context)

    def insert_common_allergen(self, code, name, menu_name, allergen_list, seq):
        seq_order = seq + settings.COMMON_ALLERGEN_MINIMUM_INDEX

        # 表示順を後ろにずらしていく
        ignore_ids = []
        for ca in CommonAllergen.objects.filter(seq_order=seq_order):
            ca.seq_order += 1
            ignore_ids.append(ca.id)
            ca.save()

        max_seq_order = CommonAllergen.objects.all().order_by('-seq_order').first().seq_order
        current_seq = seq_order + 1
        while current_seq <= max_seq_order:
            for ca in CommonAllergen.objects.filter(seq_order=current_seq).exclude(id__in=ignore_ids):
                ca.seq_order += 1
                ignore_ids.append(ca.id)
                ca.save()

            current_seq += 1

        # 入力内容の登録
        for allergen_id in allergen_list:
            ca = CommonAllergen(code=code, name=name, menu_name=menu_name, seq_order=seq_order)
            allergen = AllergenMaster.objects.get(id=allergen_id)
            ca.allergen = allergen
            ca.save()

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        form = CommonAllergenForm(request.POST)
        form.is_valid()
        code = form.cleaned_data['code']
        name = form.cleaned_data['name']
        menu_name = form.cleaned_data['menu_name']
        seq_order = form.cleaned_data['seq_order']

        allergen_list = request.POST.getlist('allergen')

        # エラー判定
        if CommonAllergen.objects.filter(code=code, menu_name=menu_name).exists():
            messages.error(request, f'対象の頻発アレルギーは登録済みです(短縮名={code},献立種類={menu_name})。')
        else:
            self.insert_common_allergen(code, name, menu_name, allergen_list, seq_order)
            messages.success(request, '登録しました。')

        context = self._get_context()
        return render(request, template_name='common_allergens_settings.html', context=context)


# 頻発アレルギー設定削除
class DeleteCommonAllergenView(TemplateView):
    template_name = 'common_allergens_settings.html'

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        # 頻発アレルギーの削除
        seq = kwargs['seq'] + settings.COMMON_ALLERGEN_MINIMUM_INDEX
        CommonAllergen.objects.filter(seq_order=seq).delete()

        # 番号を詰める
        for ca in CommonAllergen.objects.filter(seq_order__gt=seq):
            ca.seq_order -= 1
            ca.save()

        messages.success(request, '削除しました。')

        return redirect("web_order:common_allergens")


# 頻発アレルギー設定順番変更-UP
class CommonAllergenSeqUpView(TemplateView):
    template_name = 'common_allergens_settings.html'

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        # 対象頻発アレルギーの更新
        seq = kwargs['seq'] + settings.COMMON_ALLERGEN_MINIMUM_INDEX
        if seq > (settings.COMMON_ALLERGEN_MINIMUM_INDEX - 1):
            ignore_ids = []
            for ca in CommonAllergen.objects.filter(seq_order=seq):
                ca.seq_order -= 1
                ignore_ids.append(ca.id)
                ca.save()

            # 番号を詰める
            for ca in CommonAllergen.objects.filter(seq_order=seq-1).exclude(id__in=ignore_ids):
                ca.seq_order += 1
                ca.save()

        return redirect("web_order:common_allergens")


# 頻発アレルギー設定順番変更-DOWN
class CommonAllergenSeqDownView(TemplateView):
    template_name = 'common_allergens_settings.html'

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        # 対象頻発アレルギーの更新
        seq = kwargs['seq'] + settings.COMMON_ALLERGEN_MINIMUM_INDEX

        ignore_ids = []
        for ca in CommonAllergen.objects.filter(seq_order=seq):
            ca.seq_order += 1
            ignore_ids.append(ca.id)
            ca.save()

        # 番号を詰める
        for ca in CommonAllergen.objects.filter(seq_order=seq+1).exclude(id__in=ignore_ids):
            ca.seq_order -= 1
            ca.save()

        return redirect("web_order:common_allergens")

# endregion


# region 注文停止・ログイン停止予約
class StopReservationList(ListView):
    """
    注文停止・ログイン停止予約一覧ビュー
    """
    model = User
    template_name = 'stop_reservations.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = User.objects.filter(is_parent=False, is_staff=False).order_by('username')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        users = context['object_list']
        object_list = []
        for user in users:
            # 施設に紐づくユニットの取得
            unit_list = list(user.unitmaster_set.filter(unit_number__gt=1))
            if len(unit_list) == 1:
                display_unit = unit_list[0].unit_name
            else:
                display_unit = '複数'

            # 運用状態の取得
            user_creation_qs = UserCreationInput.objects.filter(
                company_name=user.company_name, facility_name=user.facility_name,
                enable_start_day__gt=dt.datetime.today()
            )
            if user_creation_qs.exists():
                # 運用開始前
                status = '運用前'
            elif not [x for x in unit_list if not x.is_active]:
                # 注文停止中のユニットが存在しなければ、運用中
                status = '運用中'
            else:
                if user.is_active:
                    if [x for x in unit_list if x.is_active]:
                        status = '一部ユニット注文停止中'
                    else:
                        status = '全ユニット注文停止中'
                else:
                    status = 'ログイン停止中'

            # 設定済み予約情報の取得(対象施設に必ず1件以上のユニットがある前提)
            reservation = ReservedStop.objects.filter(unit_name__username=user).order_by('-order_stop_day').first()

            object_list.append({'user': user, 'unit': display_unit, 'status': status, 'reservation': reservation})

        context['object_list'] = object_list
        return context


class StopReservationUpdate(TemplateView):
    """
    注文停止・ログイン停止予約更新ビュー
    """
    template_name = 'stop_reservation_update.html'

    def _get_context_data(self, user):
        # 施設の全ユニットの予約情報取得
        unit_list = []
        login_stop = None
        for unit in user.unitmaster_set.filter(unit_number__gt=1).order_by('unit_number'):
            unit_reservation = ReservedStop.objects.filter(unit_name=unit).first()
            if unit_reservation:
                # ログイン停止日は全て同じになる前提
                login_stop = unit_reservation.login_stop_day
                order_stop = unit_reservation.order_stop_day
            else:
                order_stop = None
            unit_list.append({'unit': unit, 'reservation': order_stop})

        context = {'user': user, 'unit_list': unit_list, 'login_stop': login_stop, 'today': dt.datetime.today().date()}

        return context

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        user_id = kwargs['userid']
        user = User.objects.get(id=user_id)

        context = self._get_context_data(user)
        return render(request, template_name=self.template_name, context=context)

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        user_id = kwargs['userid']
        user = User.objects.get(id=user_id)

        # 入力パラメータの取得
        unit_input_list = []
        login_stop = None
        for key, value in request.POST.items():
            if 'order_stop_' in key:
                if value:
                    dt_value = dt.datetime.strptime(value, '%Y-%m-%d')
                else:
                    dt_value = None
                unit_input_list.append((int(key.replace('order_stop_', '')), dt_value))
            if key == 'login_stop':
                if value:
                    dt_value = dt.datetime.strptime(value, '%Y-%m-%d')
                    login_stop = dt_value
                else:
                    login_stop = None

        # バリデーション
        is_valid = True
        if login_stop:
            if [x for x in unit_input_list if not x[1]]:
                messages.error(request, 'ログイン停止を設定する場合は、全てのユニットに注文停止予約日を設定してください。')
                is_valid = False

            # 入力内容との比較
            elif [x for x in unit_input_list if x[1] > login_stop]:
                messages.error(request, 'ログイン停止開始日には、注文停止予約日より後の日付を設定してください。')
                is_valid = False

            # 登録済みのデータと比較
            elif ReservedStop.objects.filter(unit_name__username=user, order_stop_day__gte=login_stop).exists():
                messages.error(request, 'ログイン停止開始日には、注文停止予約日より後の日付を設定してください。')
                is_valid = False

        if is_valid:
            # 登録処理
            saved = False
            for unit_id, order_stop in unit_input_list:
                unit = UnitMaster.objects.get(id=unit_id)
                if order_stop:
                    reservation, is_create = ReservedStop.objects.get_or_create(unit_name=unit)
                    reservation.order_stop_day = order_stop
                    reservation.login_stop_day = login_stop
                    reservation.save()
                    saved = True

            if saved:
                messages.success(request, '登録しました。')

        # 画面の再表示
        context = self._get_context_data(user)
        if not is_valid:
            unit_list = context['unit_list']
            for unit in unit_list:
                for input in unit_input_list:
                    if unit['unit'].id == input[0]:
                        unit['reservation'] = input[1]
                        break

            context['login_stop'] = login_stop
        return render(request, template_name=self.template_name, context=context)
# endregion


# region 混ぜご飯マスタ
class MixRicePlateList(ListView):
    """
    混ぜご飯マスタ一覧ビュー
    """
    model = AggMeasureMixRiceMaster
    template_name = 'mix_rice_plates.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = AggMeasureMixRiceMaster.objects.all().order_by('name', 'search_word')
        return qs


class MixRicePlateCreate(CreateView):
    """
    混ぜご飯マスタ登録ビュー
    """
    model = AggMeasureMixRiceMaster
    template_name = 'mix_rice_plate_create.html'
    form_class = MixRicePlateForm
    success_url = reverse_lazy('web_order:mix_rice_plates')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.search_word = instance.name
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class MixRicePlateUpdate(UpdateView):
    """
    混ぜご飯マスタ更新ビュー
    """
    model = AggMeasureMixRiceMaster
    template_name = 'mix_rice_plate_update.html'
    form_class = MixRicePlateForm
    success_url = reverse_lazy('web_order:mix_rice_plates')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.search_word = instance.name
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class MixRicePlateDelete(DeleteView):
    """
    混ぜご飯マスタ削除ビュー
    """
    model = AggMeasureMixRiceMaster
    success_url = reverse_lazy('web_order:mix_rice_plates')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 原体料理マスタ
class RawPlateList(ListView):
    """
    原体料理マスタ一覧ビュー
    """
    model = RawPlatePackageMaster
    template_name = 'raw_plates.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = RawPlatePackageMaster.objects.all().order_by('base_name')
        return qs


class RawPlateCreate(CreateView):
    """
    原体料理マスタ登録ビュー
    """
    model = RawPlatePackageMaster
    template_name = 'raw_plate_create.html'
    form_class = RawPlateForm
    success_url = reverse_lazy('web_order:raw_plates')

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.chilled_name = instance.dry_name
        instance.chilled_unit = instance.cold_unit
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class RawPlateUpdate(UpdateView):
    """
    原体料理マスタ更新ビュー
    """
    model = RawPlatePackageMaster
    template_name = 'raw_plate_update.html'
    form_class = RawPlateForm
    success_url = reverse_lazy('web_order:raw_plates')

    def form_valid(self, form):
        # 冷蔵は現在は使用しないので更新不要
        instance = form.save(commit=False)
        instance.save()
        messages.success(self.request, '登録しました。')

        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class RawPlateDelete(DeleteView):
    """
    原体料理マスタ削除ビュー
    """
    model = RawPlatePackageMaster
    success_url = reverse_lazy('web_order:raw_plates')

    def form_valid(self, form):
        messages.success(self.request, '削除しました。')
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)
# endregion


# region 盛付指示書表示停止・再開設定
class SetoutDurationList(ListView):
    """
    原体料理マスタ一覧ビュー
    """
    model = SetoutDuration
    template_name = 'setout_duration_settings.html'

    def get(self, request):
        # スタッフユーザーでなければトップページ
        if not request.user.is_staff:
            return redirect('/')
        return super().get(request)

    def get_queryset(self):
        qs = SetoutDuration.objects.all().order_by('-create_at')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data()

        setout_durations = context['object_list']
        object_list = []
        today = dt.datetime.today().date()
        for duration in setout_durations:
            if today >= duration.last_enable:
                status = '表示中'
            else:
                status = '停止中'

            object_list.append({
                'name': duration.name,
                'create_at': duration.create_at,
                'last_enable': duration.last_enable,
                'status': status
            })

        context['object_list'] = object_list
        return context


class SetoutDurationSettingView(TemplateView):
    """
    盛付指示書表示停止・再開設定画面
    """
    template_name = 'setout_duration_setting_maintenance.html'

    def get(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        eating_day_str = request.GET.get('eating_day', None)
        context = {
            'eating_day': eating_day_str
        }
        if eating_day_str:
            eating_day = dt.datetime.strptime(eating_day_str, '%Y-%m-%d')
            search_form = SetoutDurationSearchForm(None, initial={'eating_day': eating_day})

            name = f'盛付指示書_{eating_day_str}'
            instance = SetoutDuration.objects.filter(name=name).first()
            if instance:
                form = SetoutDurationForm(None, instance=instance)
                is_stop = instance.is_hide
                obj_id = instance.id
            else:
                form = None
                is_stop = False
                obj_id = None
        else:
            search_form = SetoutDurationSearchForm()
            form = None
            obj_id = None
            is_stop = False
        context['search_form'] = search_form
        context['form'] = form
        context['is_stop'] = is_stop
        context['obj_id'] = obj_id

        return self.render_to_response(context)

    def validate(self, changed, prev_last_enable, prev_is_hide):
        if (not changed.is_hide) and prev_is_hide:
            # 表示しないが解除された場合は、期限の変更もOK
            return True
        else:
            if prev_last_enable != changed.last_enable:
                return False
        return True

    def post(self, request, **kwargs):
        if not request.user.is_staff:
            return HttpResponse('このページは表示できません', status=500)

        id = request.POST.get('obj_id', None)
        duration = SetoutDuration.objects.filter(id=id).first()
        prev_last_enable = duration.last_enable
        prev_is_hide = duration.is_hide

        form = SetoutDurationForm(request.POST, instance=duration)
        context = {
        }
        if form.is_valid():
            ins = form.save(commit=False)
            if self.validate(ins, prev_last_enable, prev_is_hide):
                ins.save()

                messages.success(request, '更新しました。')

            else:
                messages.error(request, '施設への表示を解除した場合のみ、表示最終日は更新できます。入力をクリアしたい場合は、検索ボタンを押してください。')
                context['is_error'] = True
            eating_day = dt.datetime.strptime(request.POST['eating_day'], '%Y-%m-%d')
            search_form = SetoutDurationSearchForm(None, initial={'eating_day': eating_day})

            context['eating_day'] = request.POST['eating_day']
            is_stop = ins.is_hide
            obj_id = ins.id
        else:
            messages.error(request, '更新失敗しました。')
            search_form = SetoutDurationSearchForm()
            form = None
            is_stop = False
            obj_id = None

        context['search_form'] = search_form
        context['form'] = form
        context['is_stop'] = is_stop
        context['obj_id'] = obj_id

        return self.render_to_response(context)

# endregion

# region マスタ画面用マニュアル
def master_manuals_contract(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(
        os.path.join(settings.MEDIA_ROOT, "documents", "master", "manual_contract"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", "master", "manual_contract")

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="master_manuals_contract.html", context=context)


def master_manuals_order(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(
        os.path.join(settings.MEDIA_ROOT, "documents", "master", "manual_order"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", "master", "manual_order")

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="master_manuals_order.html", context=context)


def master_manuals_direction(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(
        os.path.join(settings.MEDIA_ROOT, "documents", "master", "manual_direction"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", "master", "manual_direction")

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="master_manuals_direction.html", context=context)


def master_manuals_setout(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(
        os.path.join(settings.MEDIA_ROOT, "documents", "master", "manual_setout"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", "master", "manual_setout")

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="master_manuals_setout.html", context=context)


def master_manuals_documents(request):
    if not request.user.is_staff:
        return HttpResponse('このページは表示できません', status=500)

    _, all_manual_files = default_storage.listdir(
        os.path.join(settings.MEDIA_ROOT, "documents", "master", "manual_documents"))
    all_manual_files = natsorted(all_manual_files, reverse=True)
    manual_url = os.path.join(settings.MEDIA_URL, "documents", "master", "manual_documents")

    context = {
        "manual_files": all_manual_files,
        "manual_url": manual_url,
    }

    return render(request, template_name="master_manuals_documents.html", context=context)
# endregion

# endregion
