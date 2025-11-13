import datetime

from django import template
from django.conf import settings

register = template.Library()

@register.filter
def modulo(num, val):
    return num % val

@register.filter
def next(some_list, current_index):
    """
    Returns the next element of the list using the current index if it exists.
    Otherwise returns an empty string.
    """
    try:
        return some_list[int(current_index) + 1]  # access the next element
    except:
        return ''  # return empty string in case of exception

@register.filter
def previous(some_list, current_index):
    """
    Returns the previous element of the list using the current index if it exists.
    Otherwise returns an empty string.
    """
    try:
        return some_list[int(current_index) - 1]  # access the previous element
    except:
        return ''  # return empty string in case of exception


@register.filter
def eval_cycle(value1, value2):
    """
    引数１: リスト ex. menu_cycle: [0, 21, 42, 63, 84, 105]
    引数２: ループカウンタ
    フォームセットからフォームを１つずつ取り出す途中に７日分の日付行を挿入するために作成
    戻り値: True・次のif節での評価に使用
    """
    for i in value1:
        if i == value2:
            return True
        else:
            i = i + 1


@register.filter
def eval_index(value1, index):
    """
    引数１: リスト ex. menu_cycle: [0, 21, 42, 63, 84, 105]
    引数２: ループカウンタ
    フォームセットからフォームを１つずつ取り出す途中に７日分の日付行を挿入するために作成
    戻り値: True・次のif節での評価に使用
    """
    return value1[index]

@register.filter(expects_localtime=True)
def is_new(value):
    if type(value) is datetime.datetime:
        value = value.date()
    today = datetime.datetime.today().date()
    diff = today - value
    return diff.days <= settings.NEW_COMMUNICATION_DAYS
