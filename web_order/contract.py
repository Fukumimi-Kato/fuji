from itertools import groupby
from .models import MealDisplay, MenuDisplay, MealMaster, MenuMaster


class UserContract:
    """
    施設毎の契約状態を管理するクラス
    """
    def __init__(self, user):
        # 施設情報:User
        # 食事区分:MealDisplayのリスト
        # 献立種類:MenuDisplayのリスト
        self.user = user
        self.meal_list = []
        self.menu_list = []

    def __str__(self):
        return f'{str(self.user)}'

    def is_all_soup_with_filling(self, list):
        return len([x for x in list if x.meal_name.soup]) == 3

    def is_all_only_filling(self, list):
        return len([x for x in list if (not x.meal_name.soup) and x.meal_name.filling]) == 3

    def _equal_menu_name(self, menu: MenuMaster, name: str):
        if menu.menu_name == name:
            return True
        else:
            if (name == '基本食') and (menu.menu_name == '常食'):
                return True
        return False

    def get_soup_contract_name(self, menu):
        menu_contracts = [x for x in self.menu_list if self._equal_menu_name(x.menu_name, menu)]

        if menu_contracts:
            enable_meal_list = [x for x in self.meal_list if x.meal_name.filling]
            if enable_meal_list:
                if self.is_all_soup_with_filling(enable_meal_list):
                    return f'汁と具　3回'

                if self.is_all_only_filling(enable_meal_list):
                    return f'具のみ　3回'

                if len(enable_meal_list) == 1:
                    meal = enable_meal_list[0].meal_name
                    if meal.soup:
                        return f'汁具　1回　{meal.meal_name}'
                    elif meal.filling:
                        return f'具のみ　1回　{meal.meal_name}'
                else:
                    # 汁具、または具のみが2件
                    # 汁具と具のみの混在はないものとする
                    meal1 = enable_meal_list[0].meal_name
                    meal2 = enable_meal_list[1].meal_name
                    if meal1.meal_name == '朝食':
                        if meal2.meal_name == '昼食':
                            if meal1.soup:
                                return f'汁具　2回　朝・昼'
                            else:
                                return f'具のみ　2回　朝・昼'
                        else:
                            if meal1.soup:
                                return f'汁具　2回　朝・夕'
                            else:
                                return f'具のみ　2回　朝・夕'
                    elif meal1.meal_name == '昼食':
                        if meal2.meal_name == '朝食':
                            if meal1.soup:
                                return f'汁具　2回　朝・昼'
                            else:
                                return f'具のみ　2回　朝・昼'
                        else:
                            if meal1.soup:
                                return f'汁具　2回　昼・夕'
                            else:
                                return f'具のみ　2回　昼・夕'
                    else:
                        if meal2.meal_name == '朝食':
                            if meal1.soup:
                                return f'汁具　2回　朝・夕'
                            else:
                                return f'具のみ　2回　朝・夕'
                        else:
                            if meal1.soup:
                                return f'汁具　2回　昼・夕'
                            else:
                                return f'具のみ　2回　昼・夕'
            else:
                return f'汁無し'
        else:
            # 対象の献立の契約がない
            return None

class ContractManager:
    """
    全施設の契約状態を管理するクラス
    """
    def __init__(self):
        self.raw_meal_list = []
        self.raw_menu_list = []
        self.user_contract_list = []


    def read_all(self):
        meal_qs = MealDisplay.objects\
            .filter(username__is_active=True)\
            .exclude(username__username__range=['80010', '89999'])\
            .select_related('username', 'meal_name')\
            .order_by('username')
        self.raw_meal_list = list(meal_qs)

        menu_qs = MenuDisplay.objects\
            .filter(username__is_active=True)\
            .exclude(username__username__range=['80010', '89999'])\
            .select_related('username', 'menu_name')\
            .order_by('username')
        self.raw_menu_list = list(menu_qs)

        for key, group in groupby(self.raw_meal_list, key=lambda x: x.username):
            contract = UserContract(key)
            contract.meal_list = list(group)
            contract.menu_list = [x for x in self.raw_menu_list if x.username.id == key.id]
            self.user_contract_list.append(contract)

    def get_user_contract(self, user):
        user_list = [x for x in self.user_contract_list if x.user == user]
        if user_list:
            return user_list[0]
        else:
            return None
