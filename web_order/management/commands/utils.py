from openpyxl.styles.borders import Border, Side


class AggEngePackageMixin():
    def get_gram_package(self, quantity):
        if float(quantity) < 20:
            return 20
        else:
            return 14

    def _get_other_package(self, rule):
        if rule == 'sub-less':
            return 20
        elif rule == 'sub':
            return 14
        else:
            return 14

    def get_other_soup_quantity_function(self, quantity, num, row):
        total_quantity = float(quantity) * num
        return f'=IFERROR({total_quantity}/G{row},"")'

    def get_miso_soup_package_function(self, unit, quantity, row):
        num_of_package = 0
        if unit == 'g':
            num_of_package = self.get_gram_package(quantity)
        else:
            # 単位が個の場合
            if int(quantity) == 1:
                num_of_package = 20
            else:
                num_of_package = 14
        return f'=IF(D{row}=0,0,IF(D{row}<=2,1,ROUNDUP(D{row}/{num_of_package},0)))'

    def get_miso_soup_package_size(self, unit, quantity):
        num_of_package = 0
        if unit == 'g':
            return self.get_gram_package(quantity)
        else:
            # 単位が個の場合
            if int(quantity) == 1:
                return 20
            else:
                return 14

    def get_filling_quantity_function(self, quantity, num, row):
        total_quantity = float(quantity) * num
        return f'=IFERROR({total_quantity}/G{row},"")'

    def get_filling_package_excel_function(self, unit, quantity, rule, row):
        if rule == 'main':
            return f'=IF(D{row}=0,0,IF(D{row}<=2,1,ROUNDUP(D{row}/7,0)))'
        else:
            if unit == 'g':
                num_of_package = self.get_gram_package(quantity)
            else:
                num_of_package = self._get_other_package(rule)
            return f'=IF(D{row}=0,0,IF(D{row}<=2,1,ROUNDUP(D{row}/{num_of_package},0)))'

    def get_filling_package_size(self, unit, quantity, rule):
        if rule == 'main':
            return 7
        else:
            if unit == 'g':
                return self.get_gram_package(quantity)
            else:
                return self._get_other_package(rule)

    def get_combined_quantity(self, quantity, density):
        qty = float(quantity)
        dty = float(density)
        return qty + (qty * dty / 100)

    def get_inner_combined_quantity(self, quantity, density):
        qty = float(quantity)
        dty = float(density)

        # g以外の内容量指定の場合,densityにはその単位から直接液の量を計算できるように、あらかじめqtyが入っている
        return qty + (dty / 100)

class AggFixedOrderRule():
    """
    食数固定分ルールクラス
    """
    def __init__(self, name: str, quantity: float, unit: str, is_less: bool, inner: float = 0.0, dty: float = 0.0):
        self.name = name
        self.quantity = quantity
        self.unit = unit
        self.is_less = is_less
        self.preserve_j = {}
        self.preserve_u = {}
        self.needle_j = {}
        self.needle_u = {}
        self.is_use_unit_package = False
        self.inner = inner
        self.dty = dty
        self.analyze()

    def get_total_quantity(self):
        if self.unit == 'g':
            qty = self.quantity
            return qty + (qty * self.dty / 100)
        else:
            if self.inner:
                qty = self.inner

                # g以外の場合は計量表の出汁が、具材内容量を加味した量になるように、計量表出力処理の呼出元でg換算している
                return qty + self.dty / 100
            else:
                qty = self.quantity
                return qty + (qty * self.dty / 100)

    def analyze(self):
        if ((self.unit == 'g') and (self.get_total_quantity() < 20)) or self.is_less:
            self.preserve_j = {'pack': 10, 'count': 3}
            self.preserve_u = {'pack': 10, 'count': 2}
            self.needle_j = {'pack': 30, 'count': 2}
            self.needle_u = {'pack': 0, 'count': 0}
            self.is_use_unit_package = True
            return
        else:
            self.preserve_j = {'pack': 10, 'count': 3}
            self.preserve_u = {'pack': 10, 'count': 2}
            self.needle_j = {'pack': 10, 'count': 2}
            self.needle_u = {'pack': 0, 'count': 0}

    def get_preserve_j(self):
        return self.preserve_j['pack'], self.preserve_j['count']

    def get_preserve_j_10(self):
        return 3

    def get_preserve_j_5(self):
        return 8

    def get_preserve_u(self):
        return self.preserve_u['pack'], self.preserve_u['count']

    def get_needle_j(self):
        return self.needle_j['pack'], self.needle_j['count']

    def get_needle_u(self):
        return self.needle_u['pack'], self.needle_u['count']

    def get_needle_10(self):
        return 2

    def get_needle_5(self):
        return 2


class AggFixedOrderRuleForBasic(AggFixedOrderRule):
    """
    基本食対応後の食数固定分ルールクラス
    """
    def judge_use_unit_package(self):
        if self.unit != 'g' and (not self.inner):
            return self.is_less

        t_qty = self.get_total_quantity()
        if t_qty < 20:
            return True
        else:
            return self.is_less

    def analyze(self):
        if self.judge_use_unit_package():
            """
            if ((self.unit == 'g') and (self.get_total_quantity() < 20)) or \
                    ((self.unit != 'g') and self.inner and (self.get_total_quantity() < 20)) or self.is_less:
            """
            self.preserve_j = {'pack': 10, 'count': 5}
            self.preserve_u = {'pack': 0, 'count': 0}
            self.needle_j = {'pack': 30, 'count': 2}
            self.needle_u = {'pack': 0, 'count': 0}
            self.is_use_unit_package = True
            return
        else:
            self.preserve_j = {'pack': 10, 'count': 5}
            self.preserve_u = {'pack': 0, 'count': 0}
            self.needle_j = {'pack': 10, 'count': 2}
            self.needle_u = {'pack': 0, 'count': 0}

    def get_preserve_u(self):
        return 0, 0

    def get_needle_u(self):
        return 0, 0

    def get_preserve_j_10(self):
        return 5

    def get_preserve_j_5(self):
        return 12


class ExcelOutputMixin():
    def save_with_select(self, wb, path: str):
        for ws in wb.worksheets:
            ws.sheet_view.tabSelected = True
        wb.save(path)
        wb.close()


class ExcelHellper:
    @classmethod
    def set_outer_border(cls, ws, cell_range, side):
        """
        指定範囲の外枠をひく。
        """
        top = Border(top=side)
        bottom = Border(bottom=side)
        left = Border(left=side)
        right = Border(right=side)

        rows = ws[cell_range]

        # 外枠の描画
        for cell in rows[0]:
            cell.border = cell.border + top
        for cell in rows[-1]:
            cell.border = cell.border + bottom
        for row in rows:
            l = row[0]
            r = row[-1]
            l.border = l.border + left
            r.border = r.border + right

    @classmethod
    def set_grid_border_without_top(cls, ws, cell_range, outer_side, inner_side):
        """
        指定範囲の外枠と内枠をひく。
        """
        outer_bottom = Border(bottom=outer_side)
        outer_left = Border(left=outer_side)
        outer_right = Border(right=outer_side)

        inner_bottom = Border(bottom=inner_side)
        inner_right = Border(right=inner_side)

        rows = ws[cell_range]

        # 外枠の描画
        for cell in rows[0]:
            break
            # cell.border = cell.border + outer_top
        for cell in rows[-1]:
            cell.border = cell.border + outer_bottom
        for row in rows:
            l = row[0]
            r = row[-1]
            l.border = l.border + outer_left
            r.border = r.border + outer_right

        # 内枠の描画
        for row in rows[:-1]:
            for cell in row:
                cell.border = cell.border + inner_bottom

            for cell in row[:-1]:
                cell.border = cell.border + inner_right
        for cell in rows[-1][:-1]:
            cell.border = cell.border + inner_right
