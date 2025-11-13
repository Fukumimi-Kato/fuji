

class OperatedUnit:
    """
    運用対象ユニット
    """
    def __init__(self, id, code, name, status):
        self.user_id = id
        self.code = code
        self.name = name
        self.status = status


class OrderRateInput:
    """
    発注比率計算入力情報
    """
    def __init__(self, from_day, to_day, eating_list, logic_list):
        self.from_day = from_day
        self.to_day = to_day
        self.eating_list = eating_list
        self.logic_list = logic_list


class EatingTimingOrder:
    """
    喫食タイミング。
    喫食日+食事区分の情報
    """
    def __init__(self, eating_day, meal, quantity, has_mix_rice, mix_rice_quantity, liquid_quantity):
        self.eating_day = eating_day
        self.meal = meal
        self.quantity = quantity
        self.has_mix_rice = has_mix_rice

        # 混ぜご飯メイン具の分量(1合あたり)
        self.mix_rice_quantity = mix_rice_quantity
        self.liquid_quantity = liquid_quantity


class ReferenceLogic:
    """
    参照ロジック設定。
    """
    def __init__(self, user_id, week_day_settings, meal_settings, menu_settings, from_day, to_day):
        self.user_id = user_id
        self.week_day_settings = week_day_settings
        self.meal_settings = meal_settings,
        self.menu_settings = menu_settings
        self.from_day = from_day
        self.to_day = to_day


    def get_weekday(self, weekday_str):
        if weekday_str in self.week_day_settings:
            return self.week_day_settings[weekday_str]
        else:
            return []

    def get_meal_setting(self, meal_name):
        tmp_meal = meal_name
        if len(meal_name) > 1:
            tmp_meal = meal_name[0]

        for ms in self.meal_settings:
            if tmp_meal in ms:
                alternative_meal = ms[tmp_meal]
                if alternative_meal == '-':
                    # 現在無効化の場合は"-"の値で届く仕様
                    return 'disabled'
                else:
                    return ms[tmp_meal] + '食'

        return None


class UnitOrder:
    """
    ユニットの注文内容
    """
    def __init__(self, unit_number, unit_name, quantity, is_past_orders):
        self.unit_number = unit_number
        self.unit_name = unit_name
        self.quantity = quantity
        self.is_past_orders = is_past_orders


class OrderRateOutput:
    """
    発注比率計算出力情報
    """
    def __init__(self, eating_day, meal, rate, soup_filling_rate, total, unit_order_list, gosu_total=0.000, dry_gosu=0.000,
                 needle_quantity_per_pack=0.000, needle_packs=0, saved_packs=0, saved_1_packs=0, soft_orders=0,
                 jelly_orders=0, mixer_orders=0):
        self.eating_day = eating_day
        self.meal = meal
        self.rate = rate
        self.soup_filling_rate = soup_filling_rate
        self.total = total
        self.gosu_total = gosu_total
        self.dry_gosu = dry_gosu
        self.unit_order_list = unit_order_list

        self.needle_quantity_per_pack = needle_quantity_per_pack
        self.needle_packs = needle_packs
        self.saved_packs = saved_packs
        self.saved_1_packs = saved_1_packs
        self.soft_orders = soft_orders
        self.jelly_orders = jelly_orders
        self.mixer_orders = mixer_orders


class MixRiceStructureInput:
    """
    混ぜご飯構成入力情報
    """
    def __init__(self, eating_day, meal, plate_list):
        self.eating_day = eating_day
        self.meal = meal
        self.plate_list = plate_list


class MixRiceStructureOutput:
    """
    混ぜご飯構成出力情報
    """
    def __init__(self, name, plate_name, is_mix_rice, gosu_quantity, gosu_liquid_quantity):
        self.name = name
        self.plate_name = plate_name
        self.is_mix_rice = is_mix_rice

        # 1合あたりの料理分量
        self.gosu_quantity = gosu_quantity
        self.gosu_liquid_quantity = gosu_liquid_quantity


class GosuLoggingInput:
    """
    合数ログ情報取得入力情報
    """
    def __init__(self, eating_day):
        self.eating_day = eating_day


class GosuCalculationOutput:
    """
    合数計算出力情報
    """
    def __init__(self, eating_day, needle_quantity, needle_orders, soft_quantity, jelly_quantity, mixer_quantity, unit_logging_list):
        self.eating_day = eating_day
        self.needle_quantity = needle_quantity
        self.needle_orders = needle_orders

        # 嚥下
        self.soft_quantity = soft_quantity
        self.jelly_quantity = jelly_quantity
        self.mixer_quantity = mixer_quantity

        self.unit_logging_list = unit_logging_list


class GosuCalculationItemOutput:
    """
    合数計算出力情報
    """
    def __init__(self, unit_number, unit_name, status, quantity):
        self.unit_number = unit_number
        self.unit_name = unit_name
        self.status = status
        self.quantity = quantity
