import openpyxl as excel
from openpyxl.styles.borders import Border


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
    def set_grid_border(cls, ws, cell_range, outer_side, inner_side):
        """
        指定範囲の外枠と内枠をひく。
        """
        outer_top = Border(top=outer_side)
        outer_bottom = Border(bottom=outer_side)
        outer_left = Border(left=outer_side)
        outer_right = Border(right=outer_side)

        inner_bottom = Border(bottom=inner_side)
        inner_right = Border(right=inner_side)

        rows = ws[cell_range]

        # 外枠の描画
        for cell in rows[0]:
            cell.border = cell.border + outer_top
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
