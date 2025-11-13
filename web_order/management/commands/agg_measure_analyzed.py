import datetime as dt
import logging
import re
from django.core.management import call_command
from django.conf import settings
from django_pandas.io import read_frame

from .agg_measure import AggMeasureWriter
from .agg_measure_enge import AggEngeMeasureWriter
from .agg_miso_soup import MisoSoupMeasureWriter
from .agg_miso_soup_devide import MisoSoupDevideMeasureWriter
from .agg_other_soup import OtherSoupMeasureWriter
from .agg_other_soup_devide import OtherSoupDevideMeasureWriter

from web_order.picking import PlatePackageRegister, RawPlatePackageRegisterFactory
from web_order.cooking_direction_plates import PlateNameAnalizeUtil
from web_order.models import Order, OrderEveryday, UnitPackage, TmpPlateNamePackage, MixRiceDay
from web_order.p7 import P7Util

logger = logging.getLogger(__name__)


class AggMeasureTarget:
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit):
        self.index = index
        self.cooking_day = cooking_day
        self.eating_day = eating_day
        self.name = name
        self.meal = meal
        self.quantity = quantity
        self.unit = unit
        self.before_name = None

    def get_enge_adjust_status(self):
        return 0

    def call_command(self, manager, enge_adjust_status: int = 0):
        package_register = RawPlatePackageRegisterFactory.create(self.name)
        if package_register.is_valid:
            in_cooking_day = dt.datetime.strptime(self.cooking_day, '%Y-%m-%d').date()
            aggregation_day = dt.datetime.strptime(self.eating_day, '%Y-%m-%d').date()
            manager.set_eating(aggregation_day, self.meal)
            package_register.register(manager.get_df_raw(), in_cooking_day, aggregation_day, self.meal)


class AggMeasurePlate(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, number):
        super(AggMeasurePlate, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit)
        self.number = number
        self.inner_gram = 0
        if '▼' in self.name:
            self.is_less = True
            self.name = self.name.replace('▼', '')
            self.is_upper = False
            self.is_noodle_soup = False
            self.is_dilute = False
        elif '△' in self.name:
            self.is_upper = True
            self.name = self.name.replace('△', '')
            self.is_less = False
            self.is_noodle_soup = False
            self.is_dilute = False
        elif '◎' in self.name:
            self.is_upper = False
            self.name = self.name.replace('◎', '')
            self.is_less = False
            self.is_noodle_soup = True
            self.is_dilute = True
        else:
            self.is_less = False
            self.is_upper = False
            self.is_noodle_soup = False
            self.is_dilute = False

    def _is_filling_and_sause_mix(self):
        if '◆' in self.name:
            res = re.findall('具(\d+|\d+\.\d+)g\s*＋液(\d+|\d+\.\d+)g', self.name)
            if res and (res[0][0] and res[0][1]):
                return True

        return False

    def get_enge_adjust_status(self):
        if self._is_filling_and_sause_mix():
            return 1
        else:
            return 0

    def _is_main_plate(self):
        return self.number in ['⑩', '①']

    def _is_sub_plate(self):
        return self.number in ['②', '③']

    def _is_enge_soup_devide(self):
        #return self.name.find('カレーライス') != -1
        return self._is_filling_and_sause_mix()

    def _is_less_by_name(self):
        if ('花形にんじん' in self.name) or ('コインキャロット' in self.name):
            if (int(self.quantity) == 1) and (self.unit == '個'):
                return True

        return False

    def get_package_rule(self):
        if self.is_upper:
            # 名前に△があったら、主菜のルールを適用する
            return 'main'

        if PlateNameAnalizeUtil.is_raw_plate_name(self.name):
            e_day = dt.datetime.strptime(self.eating_day, '%Y-%m-%d').date()
            is_raw_enge, is_raw_main = PlateNameAnalizeUtil.is_raw_enge_plate_name(self.name, e_day)
            if is_raw_enge:
                # 原体嚥下製造時の袋サイズ対応
                # (subにすべき原体で①がついているものもあるので、個別に判定)
                return 'main' if is_raw_main else 'sub'
        if self._is_main_plate():
            if '三色丼' in self.name:
                # 三色丼は副菜扱いにする
                return 'sub'
            elif float(self.quantity) < 30.0:
                if ('赤飯' in self.name) or ('ひじきご' in self.name) or ('ピラフ' in self.name) or \
                        ('チャーハン' in self.name) or ('炒飯' in self.name):
                    # 特定の料理で、1人前30g未満の場合は副菜扱いにする
                    # ～ごはんは、「はん」の表記ゆれ回避のため「～ご」までとした
                    return 'sub'
                else:
                    return 'main'
            else:
                return 'main'
        else:
            if self.is_less:
                return 'sub-less'
            else:
                return 'sub'

    def call_command(self, enge_adjust_status, manager):
        writer = AggMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'quantity': self.quantity,
            'unit': self.unit,
            'package': self.get_package_rule(),
            'thickness': 0,
            'less': 1 if self.is_less else self._is_less_by_name(),
            'showenge': 1 if self.is_noodle_soup else 0,
            'dilute': 1 if self.is_dilute else 0,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'innergram': self.inner_gram,
            'adjust': enge_adjust_status,
        }
        writer.handle(manager, None, **option)


class AggMeasurePlateWithDensity(AggMeasurePlate):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, number, density, is_same_thickness, is_density_fixed=False, inner=0):
        super(AggMeasurePlateWithDensity, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit, number)
        self.density = density
        self.density_fixed = is_density_fixed
        self.is_same_thickness = is_same_thickness
        self.inner_gram = float(inner)

    def call_command(self, enge_adjust_status, manager):
        writer = AggMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'quantity': self.quantity,
            'unit': self.unit,
            'density': self.density,
            'fixed': self.density_fixed,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'less': 1 if self.is_less else self._is_less_by_name(),
            'showenge': 1 if self.is_noodle_soup else 0,
            'dilute': 1 if self.is_dilute else 0,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'innergram': self.inner_gram,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        writer.handle(manager, None, **option)

class AggMeasurePlateKoGram(AggMeasurePlateWithDensity):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, number, density, prefix_name, quantity2, is_same_thickness):
        super(AggMeasurePlateKoGram, self).__init__(
            index, cooking_day, eating_day, meal, name, quantity, '個', number, density, is_same_thickness, False)
        self.quantity2 = quantity2
        self.prefix_name = prefix_name

    def call_command(self, enge_adjust_status, manager):
        # この名称の構成では、麺類のスープの指定(◎)はない想定
        writer1 = AggMeasureWriter()
        opt1 = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            f'{self.prefix_name}_{self.name}',
        ]
        option1 = {
            'opt': opt1,
            'quantity': self.quantity,
            'unit': '個',
            'density': self.density,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'less': 1 if self.is_less else self._is_less_by_name(),
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        writer1.handle(manager, None, **option1)

        writer2 = AggMeasureWriter()
        opt2 = [
            -1,
            self.cooking_day,
            self.eating_day,
            self.meal,
            f'{self.prefix_name}_具',
        ]
        option2 = {
            'opt': opt2,
            'quantity': self.quantity2,
            'unit': 'g',
            'density': self.density,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'less': 1 if self.is_less else self._is_less_by_name(),
            'adjust': enge_adjust_status,
        }
        writer2.handle(manager, None, **option2)


class AggMeasurePlateKoGramDensity(AggMeasurePlateWithDensity):
    def __init__(self, index, cooking_day, eating_day, meal, names, quantity, number, density, original_name, quantity2, is_same_thickness, inner=None):
        name_ko = f'{names[0]}_{names[1]}{quantity}個'
        super(AggMeasurePlateKoGramDensity, self).__init__(
            index, cooking_day, eating_day, meal, name_ko, quantity, '個', number, density, is_same_thickness, False)
        self.name_ko = name_ko
        self.quantity2 = quantity2
        self.name_g = f'{names[0]}_{names[2]}{quantity2}g'
        self.name_soup = f'{names[0]}_液{density}g'
        self.original_name = original_name
        self.inner_gram = inner

    def call_command(self, enge_adjust_status, manager):
        total = float(self.quantity2 or 0.0) + float(self.inner_gram or 0.0) + float(self.density or 0.0)

        # 計量表を分けて出力する
        # (1):個を単位にする具(嚥下は出力しない)
        if self.inner_gram:
            writer1 = AggMeasureWriter()
            opt1 = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name_ko,
            ]
            option1 = {
                'opt': opt1,
                'quantity': self.quantity,
                'unit': '個',
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': self.is_same_thickness,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': -1,
                'less': 1 if self.is_less else self._is_less_by_name(),
                'innergram': self.inner_gram,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
                'total': total
            }
            writer1.handle(manager, None, **option1)
        else:
            writer1 = AggMeasureWriter()
            opt1 = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name_ko,
            ]
            option1 = {
                'opt': opt1,
                'quantity': self.quantity,
                'unit': '個',
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': self.is_same_thickness,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': -1,
                'less': 1 if self.is_less else self._is_less_by_name(),
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
                'total': total
            }
            writer1.handle(manager, None, **option1)

        # (2):gを単位にする具(嚥下は出力しない)
        writer2 = AggMeasureWriter()
        opt2 = [
            -1,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_g,
        ]
        option2 = {
            'opt': opt2,
            'quantity': self.quantity2,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': -1,
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'total': total
        }
        writer2.handle(manager, None, **option2)

        # (3):液(嚥下は出力しない)
        # diluteは、液同でない場合に0.8倍になるようにするため、is_same_thicknessを反転させる
        if self.density:
            writer3 = AggMeasureWriter()
            opt3 = [
                -1,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name_soup,
            ]
            option3 = {
                'opt': opt3,
                'quantity': self.density,
                'unit': 'g',
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': self.is_same_thickness,
                'dilute': 0 if self.is_same_thickness else 1,
                'showenge': -1,
                'less': 1 if self.is_less else 0,
                'adjust': enge_adjust_status,
                'total': total
            }
            writer3.handle(manager, None, **option3)

        # (4):嚥下
        enge_writer = AggEngeMeasureWriter()
        enge_opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.original_name,
        ]
        enge_option = {
            'opt': enge_opt,
            'quantity': self.density,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': 0,  # 1になることは想定外
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        enge_writer.handle(manager, None, **enge_option)


class AggMeasurePlateKoGramPercent(AggMeasurePlateWithDensity):
    def __init__(self, index, cooking_day, eating_day, meal, names, quantity, number, density, original_name, quantity2, is_same_thickness):
        name_ko = f'{names[0]}_{names[1]}{quantity}個'
        super(AggMeasurePlateKoGramPercent, self).__init__(
            index, cooking_day, eating_day, meal, name_ko, quantity, '個', number, density, is_same_thickness, False)
        self.name_ko = name_ko
        self.quantity2 = quantity2
        self.name_g = f'{names[0]}_{names[2]}{quantity2}g'
        self.name_soup = f'{names[0]}_液{density}g'
        self.original_name = original_name

    def call_command(self, enge_adjust_status, manager):
        total = float(self.quantity2 or 0.0) + float(self.inner_gram or 0.0) + float(self.density or 0.0)

        # 計量表を分けて出力する
        # (1):個を単位にする具(嚥下は出力しない)
        writer1 = AggMeasureWriter()
        opt1 = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_ko,
        ]
        option1 = {
            'opt': opt1,
            'quantity': self.quantity,
            'unit': '個',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': -1,
            'less': 1 if self.is_less else self._is_less_by_name(),
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
            'total': total
        }
        writer1.handle(manager, None, **option1)

        # (2):gを単位にする具(嚥下は出力しない)
        writer2 = AggMeasureWriter()
        opt2 = [
            -1,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_g,
        ]
        option2 = {
            'opt': opt2,
            'quantity': self.quantity2,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': -1,
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'total': total
        }
        writer2.handle(manager, None, **option2)

        # (4):嚥下
        enge_writer = AggEngeMeasureWriter()
        enge_opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.original_name,
        ]
        enge_option = {
            'opt': enge_opt,
            'quantity': self.density,
            'unit': '個',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': 0,  # 1になることは想定外
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        enge_writer.handle(manager, None, **enge_option)


class AggMeasurePlateGramGram(AggMeasurePlateWithDensity):
    def __init__(self, index, cooking_day, eating_day, meal, names, quantity, number, density, original_name, quantity2, is_same_thickness):
        name_g1 = f'{names[0]}_{names[1]}{quantity}g'
        super(AggMeasurePlateGramGram, self).__init__(
            index, cooking_day, eating_day, meal, name_g1, quantity, 'g', number, density, is_same_thickness, False)
        self.name_g1 = name_g1
        self.quantity2 = quantity2
        self.name_g2 = f'{names[0]}_{names[2]}{quantity2}g'
        self.name_soup = f'{names[0]}_液{density}g'
        self.original_name = original_name

    def call_command(self, enge_adjust_status, manager):
        total = float(self.quantity or 0.0) + float(self.quantity2 or 0.0) + float(self.density or 0.0)

        # 計量表を分けて出力する
        # (1):gを単位にする具(嚥下は出力しない)
        writer1 = AggMeasureWriter()
        opt1 = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_g1,
        ]
        option1 = {
            'opt': opt1,
            'quantity': self.quantity,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': -1,
            'less': 1 if self.is_less else 0,
            'adjust':  enge_adjust_status,
            'before_name': self.before_name,
            'total': total
        }
        writer1.handle(manager, None, **option1)

        # (2):gを単位にする具(嚥下は出力しない)
        writer2 = AggMeasureWriter()
        opt2 = [
            -1,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_g2,
        ]
        option2 = {
            'opt': opt2,
            'quantity': self.quantity2,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': -1,
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'total': total
        }
        writer2.handle(manager, None, **option2)

        # (3):液(嚥下は出力しない)
        # diluteは、液同でない場合に0.8倍になるようにするため、is_same_thicknessを反転させる
        writer3 = AggMeasureWriter()
        opt3 = [
            -1,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name_soup,
        ]
        option3 = {
            'opt': opt3,
            'quantity': self.density,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 0 if self.is_same_thickness else 1,
            'showenge': -1,
            'less': 1 if self.is_less else 0,
            'adjust': enge_adjust_status,
            'total': total
        }
        writer3.handle(manager, None, **option3)

        # (4):嚥下
        enge_writer = AggEngeMeasureWriter()
        enge_opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.original_name,
        ]
        enge_option = {
            'opt': enge_opt,
            'quantity': self.density,
            'unit': 'g',
            'density': 0,
            'fixed': False,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': 0,  # 1になることは想定外
            'less': 1 if self.is_less else 0,
            'before_name': self.before_name,
            'adjust': enge_adjust_status,
        }
        enge_writer.handle(manager, None, **enge_option)


class AggMeasurePlateWithAnotherUnit(AggMeasurePlateWithDensity):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity1, unit1, number, density, quantity2, unit2, is_same_thickness):
        super(AggMeasurePlateWithAnotherUnit, self).__init__(index, cooking_day, eating_day, meal, name, quantity1, unit1, number, density, is_same_thickness)
        self.quantity2 = quantity2
        self.unit2 = unit2

    def call_command(self, enge_adjust_status, manager):
        if self.density:
            density = self.density
        else:
            if self.unit2:
                density = float(self.quantity2) / float(self.quantity) * 100
            else:
                density = 0

        writer = AggMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'quantity': self.quantity,
            'unit': self.unit,
            'density': density,
            'package': self.get_package_rule(),
            'thickness': self.is_same_thickness,
            'less': 1 if self.is_less else 0,
            'dilute': 1 if self.is_dilute else 0,
            'showenge': 1 if self.is_noodle_soup else 0,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        writer.handle(manager, None, **option)


class AggMeasureMisoDevide(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name1, quantity1, unit1, name2, quantity2, unit2, is_first):
        super(AggMeasureMisoDevide, self).__init__(index, cooking_day, eating_day, meal, name1, quantity1, unit1)
        self.name2 = name2.replace('・', '')
        self.quantity2 = quantity2
        self.unit2 = unit2
        self.is_first = is_first
        self.items = {}

    def call_command(self, enge_adjust_status, manager):
        writer = MisoSoupDevideMeasureWriter()
        return writer.handle(
                               self.index,
                               self.cooking_day,
                               self.eating_day,
                               self.meal,
                               arg_name_ko=self.name,
                               arg_qty_ko=self.quantity,
                               arg_name_g=self.name2,
                               arg_qty_g=self.quantity2,
                               arg_is_first=1 if self.is_first else 0,
                               adjust=enge_adjust_status,
                               manager=manager,
                               before_name=self.before_name,
                               liquid_quantity=self.items
                            )


class AggMeasureMiso(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, is_first):
        super(AggMeasureMiso, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit)
        self.is_first = is_first
        self.items = {}

    def call_command(self, enge_adjust_status, manager):
        writer = MisoSoupMeasureWriter()
        return writer.handle(
                               arg_index=self.index,
                               arg_cook=self.cooking_day,
                               arg_date=self.eating_day,
                               arg_menu=self.meal,
                               arg_name=self.name,
                               arg_qty=self.quantity,
                               arg_unit=self.unit,
                               arg_enge_display=0,
                               arg_is_first=1 if self.is_first else 0,
                               adjust=enge_adjust_status,
                               manager=manager,
                               before_name=self.before_name,
                               liquid_quantity=self.items
                               )


class AggMeasureSoupFilling(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit):
        super(AggMeasureSoupFilling, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit)
        self.liquid = None

    def get_output_value(self):
        if self.liquid:
            output_value = 'reminder' if float(self.liquid.quantity) > 20.0 else 'unit'
        else:
            output_value = 'unit'
        return output_value

    def _get_default_soup_name(self):
        if 'スープ' in self.name:
            return 'スープ'
        else:
            return '汁'

    def call_command(self, enge_adjust_status, manager):
        output_value = self.get_output_value()

        writer = OtherSoupMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'quantity': self.quantity,
            'unit': self.unit,
            'soup_name': self.liquid.soup.name if self.liquid else self._get_default_soup_name(),
            'soup_quantity': self.liquid.quantity if self.liquid else self.quantity,
            'output': output_value,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        return writer.handle(manager, None, **option)


class AggMeasureSoupDevide(AggMeasureSoupFilling):
    def __init__(self, index, cooking_day, eating_day, meal, name1, quantity1, unit1, name2, quantity2, unit2):
        super(AggMeasureSoupDevide, self).__init__(index, cooking_day, eating_day, meal, name1, quantity1, unit1)
        self.name2 = name2.replace('・', '')
        self.quantity2 = quantity2
        self.unit2 = unit2

    def _get_default_soup_name(self):
        if 'スープ' in self.name:
            return 'スープ'
        else:
            return '汁'

    def call_command(self, enge_adjust_status, manager):
        output_value = self.get_output_value()
        writer = OtherSoupDevideMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'name1': self.name,
            'quantity1': self.quantity,
            'name2': self.name2,
            'quantity2': self.quantity2,
            'soup_name': self.liquid.soup.name if self.liquid else self._get_default_soup_name(),
            'short_name': self.liquid.soup.get_short_name() if self.liquid else '',
            'soup_quantity': self.liquid.quantity if self.liquid else self.quantity,
            'output': output_value,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        return writer.handle(manager, None, **option)


class AggMeasureSoupLiquid(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, soup):
        super(AggMeasureSoupLiquid, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit)
        self.fillings = []
        self.soup = soup

    def add_filling(self, filling: AggMeasureSoupFilling):
        self.fillings.append(filling)

    def call_command(self, enge_adjust_status, manager):
        if not self.fillings:
            # 対応する汁具がない場合は、単体で出力(ある場合は、汁具の計量表に含まれるので、ここでは出力しない)
            output_value = 'reminder' if float(self.quantity) > 20.0 else 'unit'

            writer = OtherSoupMeasureWriter()
            opt = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name,
            ]
            option = {
                'opt': opt,
                'quantity': self.quantity,
                'unit': self.unit,
                'soup_name': self.name,
                'soup_quantity': self.quantity,
                'output': output_value,
                'soup_only': 1,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
            }
            return writer.handle(manager, None, **option)

class AggMeasureMisoNone(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity):
        super(AggMeasureMisoNone, self).__init__(index, cooking_day, eating_day, meal, name, quantity, None)


class AggMeasureSoupNone(AggMeasureTarget):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity):
        super(AggMeasureSoupNone, self).__init__(index, cooking_day, eating_day, meal, name, quantity, None)


class AggMeasureLiquidSeasoning(AggMeasurePlate):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, number, has_gu):
        super(AggMeasureLiquidSeasoning, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit, number)
        self.has_gu = has_gu

    def call_command(self, enge_adjust_status, manager):
        writer = AggMeasureWriter()
        opt = [
            self.index,
            self.cooking_day,
            self.eating_day,
            self.meal,
            self.name,
        ]
        option = {
            'opt': opt,
            'quantity': self.quantity,
            'unit': self.unit,
            'package': self.get_package_rule(),
            'less': 0,
            'showenge': 0 if self.has_gu else 1,
            'dilute': 1,
            'engesoup': 1 if self._is_enge_soup_devide() else 0,
            'adjust': enge_adjust_status,
            'before_name': self.before_name,
        }
        writer.handle(manager, None, **option)


class AggMeasureMixRice(AggMeasurePlate):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, number, mix_rice, base_soup=None, percentage=None, items=None):
        super(AggMeasureMixRice, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit, number)
        self.mix_rice = mix_rice
        self.parts = []
        self.is_disable = False
        self.base_soup = base_soup
        self.percentage = percentage
        self.items = items

    def add_parts(self, rice_parts):
        self.parts.append(rice_parts)

    def get_mix_rice_name(self):
        return self.mix_rice.name

    def get_package_rule(self):
        if self.is_upper:
            # 名前に△があったら、主菜のルールを適用する
            return 'main'

        if '栗【くり】ご' in self.name:
            p = self.parts[0]
            if float(p.quantity) < 30.0:
                # 副菜扱いにする
                return 'sub'
            else:
                return 'main'
        else:
            return super().get_package_rule()


    def call_command(self, enge_adjust_status, manager):
        if self.unit == 'g':
            # 本体分の嚥下計量表の出力
            enge_writer = AggEngeMeasureWriter()
            enge_opt = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name,
            ]
            enge_option = {
                'opt': enge_opt,
                'quantity': self.quantity,
                'unit': 'g',
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': 0,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': 0,  # 1になることは想定外
                'less': 1 if self.is_less else 0,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
            }
            enge_writer.handle(manager, None, **enge_option)
        else:
            writer = AggMeasureWriter()
            opt = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name,
            ]
            option = {
                'opt': opt,
                'quantity': self.quantity,
                'unit': self.unit,
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': 0,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': 0,  # 1になることは想定外
                'less': 1 if self.is_less else 0,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
            }
            writer.handle(manager, None, **option)

            # パーツ分は、それぞれのパーツで実施

        # 混ぜご飯内容の保存
        MixRiceDay.objects.update_or_create(
            eating_day=self.eating_day, defaults={'eating_day': self.eating_day, 'mix_rice_name': self.mix_rice.name})

class AggMeasureMixRiceParts(AggMeasurePlate):
    def __init__(self, index, cooking_day, eating_day, meal, name, quantity, unit, number, items):
        super(AggMeasureMixRiceParts, self).__init__(index, cooking_day, eating_day, meal, name, quantity, unit, number)
        self.items = items

    def _is_soup_parts(self):
        if '出汁' in self.name:
            return True
        if 'だし汁' in self.name:
                return True
        elif '栗ご飯の液' in self.name:
            return True
        elif 'チキンライスの素' in self.name:
            return True
        else:
            return False

    def _is_seasoning_parts(self):
        if "酢" in self.name:
            return True
        elif re.findall('ゆず(\s*)(\d|\d.\d)g', self.name):
            return True
        else:
            return False

    def _is_extra_soup_parts(self):
        """
        名称そのものは汁・液・出汁ではないが、出汁扱いにするもの
        """
        if "チキンライスの素" in self.name:
            return True
        else:
            return False

    def call_command(self, enge_adjust_status, manager):
        if self.index == -1:
            TmpPlateNamePackage.objects.get_or_create(
                plate_name=self.before_name,
                cooking_day=self.cooking_day,
                size=10,
                menu_name='常食'
            )
        if self.unit == 'g':
            enge_writer = AggEngeMeasureWriter()
            enge_opt = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name,
            ]
            enge_option = {
                'opt': enge_opt,
                'quantity': self.quantity,
                'unit': 'g',
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': 0,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': 0,  # 1になることは想定外
                'less': 1 if self.is_less else 0,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
                'is_mix_rice_parts': 1
            }
            enge_writer.handle(manager, None, **enge_option)
        else:
            writer = AggMeasureWriter()
            opt = [
                self.index,
                self.cooking_day,
                self.eating_day,
                self.meal,
                self.name,
            ]
            option = {
                'opt': opt,
                'quantity': self.quantity,
                'unit': self.unit,
                'density': 0,
                'fixed': False,
                'package': self.get_package_rule(),
                'thickness': 0,
                'dilute': 1 if self.is_dilute else 0,
                'showenge': 0,  # 1になることは想定外
                'less': 1 if self.is_less else 0,
                'adjust': enge_adjust_status,
                'before_name': self.before_name,
            }
            writer.handle(manager, None, **option)

        if self._is_soup_parts() or self._is_seasoning_parts() or self._is_extra_soup_parts():
            # 本クラスが嚥下調整の発生源になることは運用上ない想定。そのため、enge_adjust_status = 1(調整発生)はチェックしない
            enge_soup_index = self.index + 1 if enge_adjust_status == 2 else self.index
            # 嚥下のP7袋数は出力しない
            P7Util.save_package_count_for_print(self.cooking_day, self.eating_day, enge_soup_index, 0, 0,
                                                'ソフト', self.meal)
            P7Util.save_package_count_for_print(self.cooking_day, self.eating_day, enge_soup_index, 0, 0,
                                                'ゼリー', self.meal)
            P7Util.save_package_count_for_print(self.cooking_day, self.eating_day, enge_soup_index, 0, 0,
                                                'ミキサー', self.meal)
            # UnitPackageも削除する
            qs = UnitPackage.objects.filter(cooking_day=self.cooking_day, eating_day=self.eating_day, meal_name=self.meal,
                                       index=enge_soup_index, menu_name__in=['ソフト', 'ゼリー', 'ミキサー']).delete()


class AggMeasureOrdersManager:
    """
    計量表出力時の注文情報を管理する。
    """

    def __init__(self):
        self.eating_day = None
        self.meal = None

        # 注文内容
        self.df_basic = None
        self.df_soft = None
        self.df_jelly = None
        self.df_mixer = None

        self.df_filling_basic = None
        self.df_filling_soft = None
        self.df_filling_jelly = None
        self.df_filling_mixer = None

        self.df_soup = None
        self.df_other_soup = None
        self.df_soup_soft = None
        self.df_soup_jelly = None
        self.df_soup_mixer = None

        self.df_raw = None
        self.df_soup_raw = None
        self.df_filling_raw = None

        # 食数固定内容
        # -針刺し用
        self.needle_orders = None

        # -保存用
        self.preserve_orders = None

        # -保存用(1人用)
        self.preserve_1p_orders = None
        self.preserve_1p_enge_orders = None

        # -写真用
        self.photo_orders = None

        # -保存用(50g)
        self.preserve_50g_orders = None

    def set_eating(self, eating_day, meal: str):
        # 変化がなければ何もしない
        if (self.eating_day == eating_day) and (self.meal == meal):
            return

        self.eating_day = eating_day
        self.meal = meal

        # dataframeの解放・初期化
        del self.df_basic
        self.df_basic = None
        del self.df_soft
        self.df_soft = None
        del self.df_jelly
        self.df_jelly = None
        del self.df_mixer
        self.df_mixer = None

        del self.df_filling_basic
        self.df_filling_basic = None
        del self.df_filling_soft
        self.df_filling_soft = None
        del self.df_filling_jelly
        self.df_filling_jelly = None
        del self.df_filling_mixer
        self.df_filling_mixer = None

        del self.df_soup
        self.df_soup = None
        del self.df_other_soup
        self.df_other_soup = None
        del self.df_soup_soft
        self.df_soup_soft = None
        del self.df_soup_jelly
        self.df_soup_jelly = None
        del self.df_soup_mixer
        self.df_soup_mixer = None

        del self.df_soup_raw
        self.df_soup_raw = None
        del self.df_filling_raw
        self.df_filling_raw = None
        del self.df_raw
        self.df_raw = None

        # 食数固定内容
        # -針刺し用
        self.needle_orders = None

        # -保存用
        self.preserve_orders = None

        # -保存用(1人用)
        self.preserve_1p_orders = None
        self.preserve_1p_enge_orders = None

        # -写真用
        self.photo_orders = None

        # -保存用(50g)
        self.preserve_50g_orders = None

    def make_dataframe(self, queryset):
        dataframe = read_frame(queryset)

        dataframe = dataframe.groupby(['unit_name__unit_number',
                                       'unit_name__calc_name',
                                       'meal_name__meal_name',
                                       'menu_name',
                                       'unit_name__username__dry_cold_type']).sum().reset_index()

        dataframe = dataframe.reindex(columns=['unit_name__unit_number',
                                               'unit_name__calc_name',
                                               'quantity', 'unit_name__username__dry_cold_type'])

        dataframe = dataframe.rename(columns={'unit_name__unit_number': '呼出番号',
                                              'unit_name__calc_name': 'ユニット名',
                                              'quantity': '注文数',
                                              'unit_name__username__dry_cold_type': '乾燥冷凍区分'})

        for idx, data in dataframe.iterrows():

            # ----------------------------------------------
            res = divmod(data['注文数'], 10)
            dataframe.loc[idx, '単位袋10'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '10の端数袋・入数'] = 0
                dataframe.loc[idx, '10の1人用袋'] = 1
            else:
                dataframe.loc[idx, '10の端数袋・入数'] = res[1]
                dataframe.loc[idx, '10の1人用袋'] = 0

            # ----------------------------------------------
            res = divmod(data['注文数'], 7)
            dataframe.loc[idx, '単位袋7'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '7の端数袋・入数'] = 0
                dataframe.loc[idx, '7の1人用袋'] = 1
            else:
                dataframe.loc[idx, '7の端数袋・入数'] = res[1]
                dataframe.loc[idx, '7の1人用袋'] = 0

            # ----------------------------------------------
            res = divmod(data['注文数'], 5)
            dataframe.loc[idx, '単位袋5'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '5の端数袋・入数'] = 0
                dataframe.loc[idx, '5の1人用袋'] = 1
            else:
                dataframe.loc[idx, '5の端数袋・入数'] = res[1]
                dataframe.loc[idx, '5の1人用袋'] = 0

        dataframe = dataframe.astype({'単位袋10': 'int64',
                                      '10の端数袋・入数': 'int64',
                                      '単位袋7': 'int64',
                                      '7の端数袋・入数': 'int64',
                                      '単位袋5': 'int64',
                                      '5の端数袋・入数': 'int64'
                                      })

        return dataframe

    def make_dataframe_raw(self, queryset):
        dataframe = read_frame(queryset)

        dataframe = dataframe.groupby(['unit_name__unit_number',
                                       'unit_name__calc_name',
                                       'meal_name__meal_name',
                                       'menu_name__menu_name',
                                       'unit_name__username__dry_cold_type']).sum().reset_index()

        dataframe = dataframe.reindex(columns=['unit_name__unit_number',
                                               'unit_name__calc_name',
                                               'menu_name__menu_name',
                                               'quantity', 'unit_name__username__dry_cold_type'])

        dataframe = dataframe.rename(columns={'unit_name__unit_number': '呼出番号',
                                              'unit_name__calc_name': 'ユニット名',
                                              'menu_name__menu_name': '献立種類',
                                              'quantity': '注文数',
                                              'unit_name__username__dry_cold_type': '乾燥冷凍区分'})

        return dataframe

    def get_df_basic(self):
        """
        基本食(常食)の注文内容を取得する
        """
        if self.df_basic is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day', 'unit_name__username__dry_cold_type')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=1)
            self.df_basic = self.make_dataframe(qs_plate)

        return self.df_basic

    def get_df_soft(self):
        """
        ソフト食の注文内容を取得する
        """
        if self.df_soft is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day', 'unit_name__username__dry_cold_type')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=5)
            self.df_soft = self.make_dataframe(qs_plate)

        return self.df_soft

    def get_df_jelly(self):
        """
        ゼリー食の注文内容を取得する
        """
        if self.df_jelly is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day', 'unit_name__username__dry_cold_type')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=3)
            self.df_jelly = self.make_dataframe(qs_plate)

        return self.df_jelly

    def get_df_mixer(self):
        """
        ミキサー食の注文内容を取得する
        """
        if self.df_mixer is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day', 'unit_name__username__dry_cold_type')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=4)
            self.df_mixer = self.make_dataframe(qs_plate)

        return self.df_mixer

    def make_df_filling(self, queryset):
        dataframe = read_frame(queryset)

        dataframe = dataframe.groupby(['unit_name__unit_number',
                                       'unit_name__calc_name',
                                       'meal_name__meal_name',
                                       'menu_name']).sum().reset_index()

        dataframe = dataframe.reindex(columns=['unit_name__unit_number',
                                               'unit_name__calc_name',
                                               'menu_name__menu_name',
                                               'quantity'])

        dataframe = dataframe.rename(columns={'unit_name__unit_number': '呼出番号',
                                              'unit_name__calc_name': 'ユニット名',
                                              'menu_name__menu_name': '献立種類',
                                              'quantity': '注文数'})

        return dataframe

    def make_df_soup(self, queryset):
        dataframe = read_frame(queryset)

        dataframe = dataframe.groupby(['unit_name__unit_number',
                                       'unit_name__calc_name',
                                       'meal_name__meal_name',
                                       'menu_name__group']).sum().reset_index()  # 嚥下も常食なので献立グループを指定

        dataframe = dataframe.reindex(columns=['unit_name__unit_number',
                                               'unit_name__calc_name',
                                               'menu_name__menu_name',
                                               'quantity'])

        dataframe = dataframe.rename(columns={'unit_name__unit_number': '呼出番号',
                                              'unit_name__calc_name': 'ユニット名',
                                              'menu_name__menu_name': '献立種類',
                                              'quantity': '注文数'})

        for idx, data in dataframe.iterrows():
            res = divmod(data['注文数'], 10)

            dataframe.loc[idx, '単位袋10'] = res[0]
            dataframe.loc[idx, '10の端数袋・入数'] = res[1]

            res = divmod(data['注文数'], 7)
            dataframe.loc[idx, '単位袋7'] = res[0]
            dataframe.loc[idx, '7の端数袋・入数'] = res[1]

            res = divmod(data['注文数'], 5)
            dataframe.loc[idx, '単位袋5'] = res[0]
            dataframe.loc[idx, '5の端数袋・入数'] = res[1]

        dataframe = dataframe.astype({'単位袋10': 'int64',
                                      '10の端数袋・入数': 'int64',
                                      '単位袋7': 'int64',
                                      '7の端数袋・入数': 'int64',
                                      '単位袋5': 'int64',
                                      '5の端数袋・入数': 'int64'
                                      })

        return dataframe

    def make_df_other_soup(self, queryset):
        dataframe = read_frame(queryset)

        dataframe = dataframe.groupby(['unit_name__unit_number',
                                       'unit_name__calc_name',
                                       'meal_name__meal_name',
                                       'menu_name__group']).sum().reset_index()  # 嚥下も常食なので献立グループを指定

        dataframe = dataframe.reindex(columns=['unit_name__unit_number',
                                               'unit_name__calc_name',
                                               'quantity'])

        dataframe = dataframe.rename(columns={'unit_name__unit_number': '呼出番号',
                                              'unit_name__calc_name': 'ユニット名',
                                              'quantity': '注文数'})

        for idx, data in dataframe.iterrows():
            # ----------------------------------------------
            res = divmod(data['注文数'], 10)
            dataframe.loc[idx, '単位袋10'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '10の端数袋・入数'] = 0
                dataframe.loc[idx, '10の1人用袋'] = 1
            else:
                dataframe.loc[idx, '10の端数袋・入数'] = res[1]
                dataframe.loc[idx, '10の1人用袋'] = 0

            # ----------------------------------------------
            res = divmod(data['注文数'], 7)
            dataframe.loc[idx, '単位袋7'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '7の端数袋・入数'] = 0
                dataframe.loc[idx, '7の1人用袋'] = 1
            else:
                dataframe.loc[idx, '7の端数袋・入数'] = res[1]
                dataframe.loc[idx, '7の1人用袋'] = 0

            # ----------------------------------------------
            res = divmod(data['注文数'], 5)
            dataframe.loc[idx, '単位袋5'] = res[0]

            if res[1] == 1:
                dataframe.loc[idx, '5の端数袋・入数'] = 0
                dataframe.loc[idx, '5の1人用袋'] = 1
            else:
                dataframe.loc[idx, '5の端数袋・入数'] = res[1]
                dataframe.loc[idx, '5の1人用袋'] = 0

        """
        dataframe = dataframe.astype({'単位袋10': 'int64',
                                      '10の端数袋・入数': 'int64',
                                      '単位袋7': 'int64',
                                      '7の端数袋・入数': 'int64',
                                      '単位袋5': 'int64',
                                      '5の端数袋・入数': 'int64'
                                      })
        """
        return dataframe

    def get_def_miso_raw_soup(self):
        if self.df_soup is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name__group='常食', meal_name__soup=True)

            # 味噌汁と他の汁・スープは被ることがない前提
            self.df_soup = self.make_df_soup(qs_raw_plate)
        return self.df_soup

    def get_def_miso_soup(self):
        if self.df_soup is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name__group='常食', meal_name__soup=True)

            # 味噌汁と他の汁・スープは被ることがない前提
            self.df_soup = self.make_df_soup(qs_raw_plate)
        return self.df_soup

    def get_def_other_soup(self):
        if self.df_other_soup is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name__menu_name='常食', meal_name__soup=True)

            # 味噌汁と他の汁・スープは被ることがない前提
            self.df_other_soup = self.make_df_other_soup(qs_raw_plate)
        return self.df_other_soup

    def get_def_other_soup_enge(self, menu_name):
        if menu_name == 'ソフト':
            df = self.df_soup_soft
        elif menu_name == 'ミキサー':
            df = self.df_soup_mixer
        elif menu_name == 'ゼリー':
            df = self.df_soup_jelly
        if df is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name__menu_name=menu_name, meal_name__soup=True)

            # 味噌汁と他の汁・スープは被ることがない前提
            df = self.make_df_other_soup(qs_raw_plate)
        return df

    def get_def_miso_raw_filling(self):
        if self.df_filling_raw is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=1, meal_name__filling=True)

            # 味噌汁と他の汁・スープは被ることがない前提
            self.df_filling_raw = self.make_df_filling(qs_raw_plate)
        return self.df_filling_raw

    def get_def_miso_filling(self):
        if self.df_filling_basic is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=1, meal_name__filling=True)  # 常食 具あり

            self.df_filling_basic = self.make_df_filling(qs_raw_plate)
        return self.df_filling_basic

    def get_def_miso_soft_filling(self):
        if self.df_filling_soft is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=5, meal_name__filling=True)  # ソフト 具あり

            self.df_filling_soft = self.make_df_filling(qs_raw_plate)
        return self.df_filling_soft

    def get_def_miso_mixer_filling(self):
        if self.df_filling_mixer is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=4, meal_name__filling=True)  # ソフト 具あり

            self.df_filling_mixer = self.make_df_filling(qs_raw_plate)
        return self.df_filling_mixer

    def get_def_miso_jelly_filling(self):
        if self.df_filling_jelly is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal, menu_name=3, meal_name__filling=True)  # ソフト 具あり

            self.df_filling_jelly = self.make_df_filling(qs_raw_plate)
        return self.df_filling_jelly

    def get_df_raw(self):
        """
        原体の注文内容を取得する。
        """
        if self.df_raw is None:
            qs = Order.objects\
                .filter(eating_day=self.eating_day, quantity__gt=0)\
                .values('unit_name__unit_number', 'unit_name__calc_name',
                        'meal_name__meal_name', 'meal_name__soup', 'meal_name__filling',
                        'menu_name__menu_name', 'menu_name__group',
                        'allergen', 'quantity', 'eating_day', 'unit_name__username__dry_cold_type')\
                .exclude(unit_name__unit_code__range=[80001, 80008])\
                .order_by('unit_name__unit_number', 'meal_name__seq_order',
                          'menu_name__seq_order', 'allergen__seq_order')
            qs_raw_plate = qs.filter(meal_name__meal_name=self.meal)
            self.df_raw = self.make_dataframe_raw(qs_raw_plate)

        return self.df_raw

    def get_fixed_quantity(self, id: int):
        qs_fix = OrderEveryday.objects.filter(id=id).values('quantity')
        if qs_fix.exists():
            return qs_fix.first()['quantity']
        else:
            return 0

    def get_needle_orders(self):
        if not self.needle_orders:
            if self.meal == '朝食':
                res_s = self.get_fixed_quantity(25)  # 針刺し・朝・ソフト
                res_m = self.get_fixed_quantity(28)  # 針刺し・朝・ミキサー
                res_z = self.get_fixed_quantity(31)  # 針刺し・朝・ゼリー
            elif self.meal == '昼食':
                res_s = self.get_fixed_quantity(26)  # 針刺し・昼・ソフト
                res_m = self.get_fixed_quantity(29)  # 針刺し・昼・ミキサー
                res_z = self.get_fixed_quantity(32)  # 針刺し・昼・ゼリー
            elif self.meal == '夕食':
                res_s = self.get_fixed_quantity(27)  # 針刺し・夕・ソフト
                res_m = self.get_fixed_quantity(30)  # 針刺し・夕・ミキサー
                res_z = self.get_fixed_quantity(33)  # 針刺し・夕・ゼリー

            self.needle_orders = (res_s, res_m, res_z)
        return self.needle_orders

    def get_preserve_orders(self):
        if not self.preserve_orders:
            if self.meal == '朝食':
                res_s = self.get_fixed_quantity(13)  # 保存用・朝・ソフト
                res_m = self.get_fixed_quantity(16)  # 保存用・朝・ミキサー
                res_z = self.get_fixed_quantity(19)  # 保存用・朝・ゼリー
            elif self.meal == '昼食':
                res_s = self.get_fixed_quantity(14)  # 保存用・昼・ソフト
                res_m = self.get_fixed_quantity(17)  # 保存用・昼・ミキサー
                res_z = self.get_fixed_quantity(20)  # 保存用・昼・ゼリー
            elif self.meal == '夕食':
                res_s = self.get_fixed_quantity(15)  # 保存用・夕・ソフト
                res_m = self.get_fixed_quantity(18)  # 保存用・夕・ミキサー
                res_z = self.get_fixed_quantity(21)  # 保存用・夕・ゼリー

            self.preserve_orders = (res_s, res_m, res_z)
        return self.preserve_orders

    def get_preserve_1p_orders(self):
        if not self.preserve_1p_orders:
            if self.meal == '朝食':
                res_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[0])  # 保存用・朝・常食
                res_u = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_U[0])  # 保存用・朝・薄味
            elif self.meal == '昼食':
                res_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[1])  # 保存用・昼・常食
                res_u = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_U[1])  # 保存用・昼・薄味
            elif self.meal == '夕食':
                res_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[2])  # 保存用・夕・常食
                res_u = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_U[2])  # 保存用・夕・薄味

            self.preserve_1p_orders = (res_j, res_u)
        return self.preserve_1p_orders

    def get_preserve_1p_enge_orders(self):
        if not self.preserve_1p_enge_orders:
            if self.meal == '朝食':
                pack_s = self.get_fixed_quantity(13)  # 保存用・朝・ソフト
                pack_m = self.get_fixed_quantity(16)  # 保存用・朝・ミキサー
                pack_z = self.get_fixed_quantity(19)  # 保存用・朝・ゼリー
            elif self.meal == '昼食':
                pack_s = self.get_fixed_quantity(14)  # 保存用・昼・ソフト
                pack_m = self.get_fixed_quantity(17)  # 保存用・昼・ミキサー
                pack_z = self.get_fixed_quantity(20)  # 保存用・昼・ゼリー
            elif self.meal == '夕食':
                pack_s = self.get_fixed_quantity(15)  # 保存用・夕・ソフト
                pack_m = self.get_fixed_quantity(18)  # 保存用・夕・ミキサー
                pack_z = self.get_fixed_quantity(21)  # 保存用・夕・ゼリー

            self.preserve_1p_enge_orders = (pack_s, pack_m, pack_z)
        return self.preserve_1p_enge_orders

    def get_photo_orders(self):
        if not self.photo_orders:
            if self.meal == '朝食':
                self.photo_orders = self.get_fixed_quantity(settings.ORDER_EVERYDAY_FOR_PHOTO_ID_J[0])  # 写真用・朝・常食
            elif self.meal == '昼食':
                self.photo_orders = self.get_fixed_quantity(settings.ORDER_EVERYDAY_FOR_PHOTO_ID_J[1])  # 写真用・昼・常食
            elif self.meal == '夕食':
                self.photo_orders = self.get_fixed_quantity(settings.ORDER_EVERYDAY_FOR_PHOTO_ID_J[2])  # 写真用・夕・常食
        return self.photo_orders

    def get_preserve_50g_orders(self):
        if not self.preserve_50g_orders:
            if self.meal == '朝食':
                pre_50g_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[0])  # 保存用50g・朝・常食
                pre_50g_s = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_S[0])  # 保存用50g・朝・ソフト
                pre_50g_z = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_Z[0])  # 保存用50g・朝・ゼリー
                pre_50g_m = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_M[0])  # 保存用50g・朝・ミキサー
            elif self.meal == '昼食':
                pre_50g_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[1])  # 保存用50g・昼・常食
                pre_50g_s = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_S[1])  # 保存用50g・昼・ソフト
                pre_50g_z = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_Z[1])  # 保存用50g・昼・ゼリー
                pre_50g_m = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_M[1])  # 保存用50g・昼・ミキサー
            elif self.meal == '夕食':
                pre_50g_j = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[2])  # 保存用50g・昼・常食
                pre_50g_s = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_S[2])  # 保存用50g・昼・ソフト
                pre_50g_z = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_Z[2])  # 保存用50g・昼・ゼリー
                pre_50g_m = self.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_M[2])  # 保存用50g・昼・ミキサー

            self.preserve_50g_orders = (pre_50g_j, pre_50g_s, pre_50g_z, pre_50g_m)
        return self.preserve_50g_orders
