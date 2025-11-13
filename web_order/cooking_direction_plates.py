import datetime
from itertools import groupby
import logging
import math
import re

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Sum

from .models import CookingDirectionPlate, AllergenPlateRelations, PlatePackageForPrint, CommonAllergen
from .models import UncommonAllergen, Order, UncommonAllergenHistory, BackupAllergenPlateRelations, PackageMaster, UnitPackage
from .models import TmpPlateNamePackage, OrderEveryday, RawPlatePackageMaster, AllergenMaster

EATING_MEAL_REGEX_PATTERN = re.compile('■(\d+)/(\d+)(\D+)')
KIND_REGEX_PATTERN = re.compile('\d+\s(.+)')
# サンプル食種のリスト
SAMPLE_PLATE_TYPES = [
    settings.COOKING_DIRECTION_SAMPLE_J_CODE,
    settings.COOKING_DIRECTION_SAMPLE_S_CODE,
    settings.COOKING_DIRECTION_SAMPLE_Z_CODE,
    settings.COOKING_DIRECTION_SAMPLE_M_CODE,
    settings.COOKING_DIRECTION_TEST_CODE
]


logger = logging.getLogger(__name__)


class CookingDirectionPlatesManager:
    """
    調理表上の料理を管理するクラス
    """
    @classmethod
    def parse_eating_meal(cls, eating_meal: str, cooking_day):
        """
        調理表の喫食日・食事区分(A列)を解析し、喫食日と食事区分を取得する。
        喫食日・食事区分例)■3/1朝食
        """
        res_parse = EATING_MEAL_REGEX_PATTERN.findall(eating_meal)
        if res_parse:
            date = datetime.datetime.strptime(cooking_day, '%Y-%m-%d').date()
            year = date.year
            month = int(res_parse[0][0])
            day = int(res_parse[0][1])
            if date.month == 12 and date.day >= 20 and month == 1:
                year += 1
                month = 1
            meal = res_parse[0][2]
            return datetime.date(year, month, day), meal
        else:
            raise ValueError("喫食日・食事区分変換:喫食食事区分不正")

    @classmethod
    def parse_kind(cls, key):
        parsed = KIND_REGEX_PATTERN.findall(key)
        if parsed:
            index = parsed[0].find('基本食')
            kind = parsed[0][:index - 1]
            return kind
        return key

    @classmethod
    def is_sample_plate_kind(cls, kind):
        for sample_type in SAMPLE_PLATE_TYPES:
            if sample_type in kind:
                return True

        return False

    @classmethod
    def is_ignore_plate(cls, plate):
        """
        保存対象外の料理であるかどうかを判定する。現在はサンプルの食種のみを持つ料理は対象外にする。
        """
        for eating_type in plate['eating_type_list']:
            if cls.is_sample_plate_kind(eating_type):
                pass
            else:
                return False

        # 全てサンプルの食種だった場合
        return True

    @classmethod
    def get_unique_normal_kind_list(cls, plate_list):
        # 基本食と判定する食種のリスト
        BASIC_PLATE_TYPES = [
            settings.COOKING_DIRECTION_J_CODE,
            settings.COOKING_DIRECTION_SOUP_J_CODE,
            settings.COOKING_DIRECTION_GU_J_CODE,
            settings.COOKING_DIRECTION_B_CODE,
            settings.COOKING_DIRECTION_SOUP_B_CODE,
            settings.COOKING_DIRECTION_GU_B_CODE,
        ]

        unique_list = []
        for plate in plate_list:
            if plate['is_basic_plate']:
                continue

            if plate['is_soup']:
                continue

            for eating_type in plate['eating_type_list']:
                if eating_type in BASIC_PLATE_TYPES:
                    continue

                if cls.is_sample_plate_kind(eating_type):
                    continue

                kind = cls.parse_kind(eating_type)
                if not (kind in unique_list):
                    unique_list.append(kind)
        return unique_list


    @classmethod
    def get_unique_soup_kind_list(cls, plate_list):
        # 基本食と判定する食種のリスト
        BASIC_PLATE_TYPES = [
            settings.COOKING_DIRECTION_J_CODE,
            settings.COOKING_DIRECTION_SOUP_J_CODE,
            settings.COOKING_DIRECTION_GU_J_CODE,
            settings.COOKING_DIRECTION_B_CODE,
            settings.COOKING_DIRECTION_SOUP_B_CODE,
            settings.COOKING_DIRECTION_GU_B_CODE,
        ]

        unique_list = []
        for plate in plate_list:
            if plate['is_basic_plate']:
                continue

            for eating_type in plate['eating_type_list']:
                if eating_type in BASIC_PLATE_TYPES:
                    continue

                if not plate['is_soup']:
                    continue

                if cls.is_sample_plate_kind(eating_type):
                    continue

                kind = cls.parse_kind(eating_type)
                if not (kind in unique_list):
                    unique_list.append(kind)
        return unique_list

    @classmethod
    def backup_relations(cls, cooking_day):
        now = datetime.datetime.now()
        for bk_relation in BackupAllergenPlateRelations.objects.filter(cooking_day=cooking_day, backuped_at=None):
            bk_relation.backuped_at = now
            bk_relation.save()

        # 不要な項目を整理(Backupに残す必要のない、不要なデータを削除)
        qs = AllergenPlateRelations.objects.filter(
            source__cooking_day=cooking_day, source__is_basic_plate=True
        ).select_related('source', 'plate').order_by(
            'source__eating_day', 'source__seq_meal', 'source__index', 'code')
        if qs.exists():
            for key, group in groupby(qs, key=lambda x: (x.source.eating_day, x.source.seq_meal, x.source.index, x.code)):
                dst_list = [(x.id, x.plate) for x in group]
                if len(dst_list) > 1:
                    for r_id, plate in dst_list:
                        if not plate:
                            AllergenPlateRelations.objects.filter(id=r_id).delete()

        qs = AllergenPlateRelations.objects.filter(source__cooking_day=cooking_day).select_related('plate', 'source')
        for relation in qs:
            bk = BackupAllergenPlateRelations(
                cooking_day=relation.source.cooking_day,
                eating_day=relation.source.eating_day,
                meal_name=relation.source.meal_name,
                plate_name=relation.plate.plate_name if relation.plate else None,
                source_name=relation.source.plate_name,
                code=relation.code
            )
            bk.save()

    @classmethod
    def _conatins_eating_list(cls, key, eating_list):
        for eating_type in eating_list:
            if key in eating_type:
                return True

        return False

    @classmethod
    def save(cls, plate_dict_list, cooking_day):
        """
        料理の情報をDBに登録する。
        """

        # 対象製造日の全情報を削除(別の製造日の料理でアレルギーのリレーションが組まれることはない)
        if not settings.IGNORE_ALLERGEN_RERATION_BACKUP:
            cls.backup_relations(cooking_day)
        AllergenPlateRelations.objects.filter(source__cooking_day=cooking_day).delete()
        CookingDirectionPlate.objects.filter(cooking_day=cooking_day).delete()

        test = list(BackupAllergenPlateRelations.objects.filter(cooking_day=cooking_day, meal_name='朝食', backuped_at=None))

        for plate_list in plate_dict_list:
            eating_day, meal = cls.parse_eating_meal(plate_list[0]['eating_meal'], cooking_day)

            # plate_list:喫食日・食事区分単位
            # 調理表料理情報を登録
            for index, target_plate in enumerate(plate_list):
                if cls.is_ignore_plate(target_plate):
                    continue

                meal_name = meal.strip()
                if meal_name == '朝食':
                    seq = 7
                elif meal_name == '昼食':
                    seq = 8
                elif meal_name == '夕食':
                    seq = 9
                else:
                    seq = 10
                if 'is_mix_rice' in target_plate:
                    is_mix_rice_value = target_plate['is_mix_rice']
                else:
                    is_mix_rice_value = False
                plate = CookingDirectionPlate(
                    cooking_day=cooking_day,
                    eating_day=eating_day,
                    meal_name=meal_name,
                    seq_meal=seq,
                    plate_name=target_plate['plate'],
                    index=index,
                    is_basic_plate=target_plate['is_basic_plate'],
                    is_soup=target_plate['is_soup'],
                    is_allergen_plate=target_plate['is_allergen'],
                    is_mix_rice=is_mix_rice_value
                )
                plate.save()
                target_plate['instance'] = plate

                target_plate['model_id'] = plate.id

                # アレルギーの元料理が先のインデックスの場合があるので、アレルギーは別ループで対応

            # バックアップに自動判定とは別の代替元が設定されていた場合の情報保持dict
            plate_dict = {}

            # アレルギー連携の登録(前回の編集内容で上書き)
            for index, target_plate in enumerate(plate_list):
                if 'allergen_base' in target_plate:
                    logger.info(target_plate)
                    logger.info(f'dict->{plate_dict}')
                    for key, value in target_plate['allergen_base'].items():
                        if cls.is_sample_plate_kind(key):
                            continue

                        if not (key in plate_dict):
                            plate_dict[key] = {}
                        if isinstance(value, str):
                            kind = cls.parse_kind(key)
                            # 代替元料理の取得
                            base_plate = CookingDirectionPlate.objects.filter(
                                cooking_day=cooking_day,
                                eating_day=eating_day,
                                meal_name=meal_name,
                                is_basic_plate=True,
                                plate_name=value
                            ).first()

                            key_plate_dict = plate_dict[key]

                            # 前回バックアップの取得
                            bk_qs = BackupAllergenPlateRelations.objects.filter(
                                cooking_day=cooking_day,
                                meal_name=meal_name,
                                code=kind,
                                source_name=value,
                                backuped_at=None
                            )
                            if bk_qs.exists():
                                bk = None
                                bk_list = list(bk_qs)
                                for x in bk_list:
                                    if x.plate_name == target_plate['plate']:
                                        bk = x
                                    elif not (x.plate_name in key_plate_dict):
                                        key_plate_dict[x.plate_name] = value
                                logger.info(f'backup復元1:{cooking_day}-{meal_name}-{kind}')
                                for x in bk_list:
                                    logger.info(x.plate_name)
                                if bk:
                                    logger.info(f'hit:{bk.plate_name}')

                                    # バックアップに保存された、代替先の情報
                                    plate = CookingDirectionPlate.objects.filter(
                                        cooking_day=cooking_day,
                                        meal_name=meal_name,
                                        eating_day=eating_day,
                                        is_basic_plate=False,
                                        plate_name=bk.plate_name
                                    ).first()
                                else:
                                    bk_alter = bk_list[0]
                                    logger.info('ヒットなし')
                                    if target_plate['plate'] in key_plate_dict:
                                        plate = CookingDirectionPlate.objects.filter(
                                            cooking_day=cooking_day,
                                            eating_day=eating_day,
                                            meal_name=meal_name,
                                            is_basic_plate=False,
                                            plate_name=target_plate['plate']
                                        ).first()

                                        base_plate = CookingDirectionPlate.objects.filter(
                                            cooking_day=cooking_day,
                                            eating_day=eating_day,
                                            meal_name=meal_name,
                                            is_basic_plate=True,
                                            plate_name=key_plate_dict[target_plate['plate']]
                                        ).first()
                                        logger.info(f"dictから取得({target_plate['plate']})-{key_plate_dict[target_plate['plate']]}:{plate}")
                                    elif bk_alter.plate_name:
                                        #名称変更で、今の調理表に存在しない(他の連携に使われているものを区別できないので、置き換え対象外にする)
                                        plate = None
                                        """
                                        plate = CookingDirectionPlate.objects.filter(
                                            cooking_day=cooking_day,
                                            meal_name=meal_name,
                                            is_basic_plate=False,
                                            plate_name=target_plate['plate']
                                        ).first()
                                        """
                                    else:
                                        # 前回紐づけなしを選択
                                        plate = None
                            else:
                                # 調理表からの判定で得られた代替先情報取得
                                plate = CookingDirectionPlate.objects.filter(
                                    cooking_day=cooking_day,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    is_basic_plate=False,
                                    plate_name=target_plate['plate']
                                ).first()

                            if plate:
                                relation = AllergenPlateRelations(
                                    plate=plate, source=base_plate, code=kind
                                )
                                relation.save()
                                logger.info(f'plate保存:{plate.id}')

                                # 空のものがあったら削除
                                del_relation = AllergenPlateRelations.objects.filter(
                                    plate=None, source=base_plate, code=kind
                                )
                                if del_relation.exists():
                                    del_relation.delete()
                            else:
                                # 他にない場合に登録
                                other_relation = AllergenPlateRelations.objects.filter(
                                    source=base_plate, code=kind
                                ).first()
                                if not other_relation:
                                    relation = AllergenPlateRelations(
                                        plate=plate, source=base_plate, code=kind
                                    )
                                    relation.save()
                        else:
                            kind = cls.parse_kind(key)
                            for v in value:
                                base_plate = CookingDirectionPlate.objects.filter(
                                    cooking_day=cooking_day,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    is_basic_plate=True,
                                    plate_name=v
                                ).first()

                                bk_qs = BackupAllergenPlateRelations.objects.filter(
                                    cooking_day=cooking_day,
                                    meal_name=meal_name,
                                    code=kind,
                                    source_name=value,
                                    backuped_at=None
                                )
                                if bk_qs.exists():
                                    bk_list = list(bk_qs)
                                    logger.info(f'backup復元2:{cooking_day}-{meal_name}-{kind}')
                                    for x in bk_list:
                                        logger.info(x.plate_name)
                                    #bk = bk_qs.first()
                                    bk = bk_qs[0]
                                    if bk.plate_name:
                                        plate = CookingDirectionPlate.objects.filter(
                                            cooking_day=cooking_day,
                                            eating_day=eating_day,
                                            meal_name=meal_name,
                                            is_basic_plate=False,
                                            plate_name=bk.plate_name
                                        ).first()

                                        if not plate:
                                            # 名称変更で、今の調理表に存在しない
                                            plate = CookingDirectionPlate.objects.filter(
                                                cooking_day=cooking_day,
                                                eating_day=eating_day,
                                                meal_name=meal_name,
                                                is_basic_plate=False,
                                                plate_name=target_plate['plate']
                                            ).first()
                                    else:
                                        # 前回紐づけなしを選択
                                        plate = None
                                else:
                                    # 調理表からの判定で得られた代替先情報取得
                                    plate = CookingDirectionPlate.objects.filter(
                                        cooking_day=cooking_day,
                                        eating_day=eating_day,
                                        meal_name=meal_name,
                                        is_basic_plate=False,
                                        plate_name=target_plate['plate']
                                    ).first()

                                relation = AllergenPlateRelations(
                                    plate=plate, source=base_plate, code=kind
                                )
                                relation.save()

            # 手動編集用の代替情報登録・前回情報による上書き
            normal_unique_list = cls.get_unique_normal_kind_list(plate_list)
            soup_unique_list = cls.get_unique_soup_kind_list(plate_list)
            for index, target_plate in enumerate(plate_list):
                if target_plate['is_allergen']:
                    continue

                if target_plate['is_soup']:
                    if '具' in target_plate['plate']:
                        for kind in soup_unique_list:
                            # 未登録の食種の連携情報を登録
                            base_plate = target_plate['instance']

                            bk_qs = BackupAllergenPlateRelations.objects.filter(
                                cooking_day=cooking_day,
                                meal_name=meal_name,
                                code=kind,
                                source_name=target_plate['plate'],
                                backuped_at=None
                            )
                            if bk_qs.exists():
                                bk = bk_qs.first()
                                if bk.plate_name:
                                    plate = CookingDirectionPlate.objects.filter(
                                        cooking_day=cooking_day,
                                        meal_name=meal_name,
                                        is_basic_plate=False,
                                        plate_name=bk.plate_name
                                    ).first()
                                else:
                                    plate = None
                            else:
                                plate = None
                            r, is_create = AllergenPlateRelations.objects.get_or_create(
                                code=kind, source=base_plate
                            )
                            if is_create and plate:
                                r.plate = plate
                                r.save()
                else:
                    eating_type_list = target_plate['eating_type_list']
                    for kind in normal_unique_list:
                        if cls._conatins_eating_list(kind, eating_type_list):
                            pass
                        else:
                            # 未登録の食種の連携情報を登録
                            base_plate = target_plate['instance']

                            bk_qs = BackupAllergenPlateRelations.objects.filter(
                                cooking_day=cooking_day,
                                meal_name=meal_name,
                                code=kind,
                                source_name=target_plate['plate'],
                                backuped_at=None
                            )
                            if bk_qs.exists():
                                bk = bk_qs.first()
                                if bk.plate_name:
                                    plate = CookingDirectionPlate.objects.filter(
                                        cooking_day=cooking_day,
                                        meal_name=meal_name,
                                        is_basic_plate=False,
                                        plate_name=bk.plate_name
                                    ).first()
                                else:
                                    plate = None
                            else:
                                plate = None

                            try:
                                r, is_create = AllergenPlateRelations.objects.get_or_create(
                                    code=kind, source=base_plate
                                )
                                if is_create and plate:
                                    r.plate = plate
                                    r.save()
                            except MultipleObjectsReturned:
                                pass

    @classmethod
    def get_kind_menu_name(cls, code):
        """
        食種の献立種類を取得する
        """
        if '常' in code:
            return '常食'
        elif 'ソ' in code:
            return 'ソフト'
        elif 'ゼ' in code:
            return 'ゼリー'
        elif 'ミ' in code:
            return 'ミキサー'
        else:
            return ''

    @classmethod
    def get_allergens_with_menu(self, code, cooking_day):
        if settings.KIZAWA_RAKUKON_CODE in code:
            if settings.KOSHOKU_UNIT_IDS:
                ar = AllergenMaster.objects.filter(allergen_name='個食').first()
                return [ar], '常食'
        if settings.FREEZE_RACKUKON_CODE in code:
            if settings.FREEZE_UNIT_IDS:
                return ['ﾌﾘｰｽﾞ'], '常食'

        # 献立種類名の取得
        menu_name = self.get_kind_menu_name(code)

        # 散発アレルギー履歴から検索(更新したい場合は別途レコードを削除してから対応する)
        uc_hist_qs = UncommonAllergenHistory.objects.filter(code=code, cooking_day=cooking_day, menu_name=menu_name)
        if uc_hist_qs.exists():
            logger.debug(f'menu={menu_name}')
            allergen = uc_hist_qs.first().allergen
            logger.debug(f'allergen={repr(allergen)}-{allergen.allergen_name}')

            return [allergen], menu_name

        # 履歴がなければ、散発アレルギーから検索
        uncommon_qs = UncommonAllergen.objects.filter(code=code, menu_name__menu_name=menu_name)
        if uncommon_qs.exists():
            logger.debug(f'menu={menu_name}/qs={uncommon_qs}')
            allergen = uncommon_qs.first().allergen
            logger.debug(f'allergen={repr(allergen)}-{allergen.allergen_name}')

            # 履歴を保存
            hist_qs = UncommonAllergenHistory.objects.filter(
                cooking_day=cooking_day,
                code=code,
                menu_name=menu_name
            )
            if not hist_qs.exists():
                # 本来、履歴はないが、念のため
                hist = UncommonAllergenHistory(
                    cooking_day=cooking_day,
                    code=code,
                    menu_name=menu_name,
                    allergen=allergen
                )
                hist.save()
            return [allergen], menu_name
        else:
            common_qs = CommonAllergen.objects.filter(code=code, menu_name__menu_name=menu_name)
            if common_qs.exists():
                return [x.allergen for x in common_qs], menu_name
            else:
                logger.info(f'allergen data is none.({code}-{menu_name})')
                return [], None

    @classmethod
    def get_fixed_quantity(cls, id: int):
        qs_fix = OrderEveryday.objects.filter(id=id)
        if qs_fix.exists():
            return qs_fix.first().quantity
        else:
            return 0

    @classmethod
    def get_preserved_count(cls, meal: str):
        """
        食数固定注文情報を元に保存用1人用袋の食数を取得する。
        """
        if meal == '朝食':
            pre_1pack_j = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[0])  # 保存用・朝・常食
        elif meal == '昼食':
            pre_1pack_j = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[1])  # 保存用・昼・常食
        elif meal == '夕食':
            pre_1pack_j = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_1PACK_ID_J[2])  # 保存用・夕・常食
        else:
            pre_1pack_j = 0

        return pre_1pack_j

    @classmethod
    def get_50g_pack_count(cls, meal: str):
        """
        食数固定注文情報から元に保存用50g袋の注文数を取得する。
        """
        if meal == '朝食':
            count = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[0])  # 保存用50g・朝・常食
        elif meal == '昼食':
            count = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[1])  # 保存用50g・昼・常食
        elif meal == '夕食':
            count = cls.get_fixed_quantity(settings.ORDER_EVERYDAY_PRESERVE_50G_ID_J[0])  # 保存用50g・昼・常食
        else:
            count = 0

        return count

    @classmethod
    def is_filling_and_sause_mix(cls, name):
        if '◆' in name:
            res = re.findall('具(\d+|\d+\.\d+)g\s*＋液(\d+|\d+\.\d+)g', name)
            if res and (res[0][0] and res[0][1]):
                return True
        elif 'カレーライス' in name:
        	 return True
        
        return False

    @classmethod
    def save_p7_allergen(cls, plate_dict_list, cooking_day):
        a_index = 0
        for plate_list in plate_dict_list:
            eating_day, meal_name = cls.parse_eating_meal(plate_list[0]['eating_meal'], cooking_day)
            meal_name = meal_name.strip()
            allergen_plate_index_dict = {'常食': 0, 'ソフト': 0, 'ミキサー': 0, 'ゼリー': 0}

            # plate_list:喫食日・食事区分単位
            for index, target_plate in enumerate(plate_list):
                if not target_plate['is_allergen']:
                    continue

                # 食数固定情報の取得
                preserved_count = cls.get_preserved_count(meal_name)
                count_50g = cls.get_50g_pack_count(meal_name)

                plate_name = target_plate['plate']
                # 食種から、常食/ソフト/ゼリー/ミキサーの食数を計算する
                count_dict = {'常食': 0, 'ソフト': 0, 'ゼリー': 0, 'ミキサー': 0}
                count_1p_dict = {'常食': 0, 'ソフト': 0, 'ゼリー': 0, 'ミキサー': 0}
                preserved_dict = {'常食': 0, 'ソフト': 0, 'ゼリー': 0, 'ミキサー': 0}
                unit_package_dict = {'常食': [], 'ソフト': [], 'ゼリー': [], 'ミキサー': []}
                # 食種分ループ
                for eating_type in target_plate['eating_type_list']:
                    if cls.is_sample_plate_kind(eating_type):
                        continue
                    code = cls.parse_kind(eating_type)
                    allergen_list, menu_name = cls.get_allergens_with_menu(code, cooking_day)
                    for allergen in allergen_list:
                        is_update = False
                        if allergen == '個食':
                            order_qs = Order.objects.filter(
                                eating_day=eating_day, allergen__allergen_name='なし', quantity__gt=0,
                                unit_name_id__in=settings.KOSHOKU_UNIT_IDS,
                                meal_name__meal_name=meal_name, menu_name__menu_name=menu_name
                            ).exclude(unit_name__unit_code__range=[80001, 80008]).annotate(
                                unit_quantity=Sum('quantity')).order_by('menu_name__seq_order', 'unit_name__unit_number')
                        elif allergen == 'ﾌﾘｰｽﾞ':
                            order_qs = Order.objects.filter(
                                eating_day=eating_day, allergen__allergen_name='なし', quantity__gt=0,
                                unit_name_id__in=settings.FREEZE_UNIT_IDS,
                                meal_name__meal_name=meal_name, menu_name__menu_name=menu_name
                            ).exclude(unit_name__unit_code__range=[80001, 80008]).annotate(
                                unit_quantity=Sum('quantity')).order_by('menu_name__seq_order', 'unit_name__unit_number')
                        else:
                            if target_plate['is_soup']:
                                # 対象アレルギーを注文している施設を取得
                                order_qs = Order.objects.filter(
                                    eating_day=eating_day, allergen=allergen, quantity__gt=0,
                                    meal_name__meal_name=meal_name, menu_name__menu_name=menu_name,
                                    meal_name__filling=True
                                ).exclude(unit_name__unit_code__range=[80001, 80008]).annotate(
                                    unit_quantity=Sum('quantity')).order_by('menu_name__seq_order', 'unit_name__unit_number')
                            else:
                                # 対象アレルギーを注文している施設を取得
                                order_qs = Order.objects.filter(
                                    eating_day=eating_day, allergen=allergen, quantity__gt=0,
                                    meal_name__meal_name=meal_name, menu_name__menu_name=menu_name
                                ).exclude(unit_name__unit_code__range=[80001, 80008]).annotate(
                                    unit_quantity=Sum('quantity')).order_by('menu_name__seq_order', 'unit_name__unit_number')

                        for order in order_qs:
                            if order.quantity:
                                unit_package_dict[menu_name].append(order)
                            if order.quantity % 10 == 1:
                                count_1p_dict[menu_name] += 1
                                is_update = True
                            if order.quantity > 1:
                                if order.quantity % 10 == 1:
                                    count_dict[menu_name] += math.ceil((order.quantity - 1) / 10)
                                else:
                                    count_dict[menu_name] += math.ceil(order.quantity / 10)
                                is_update = True
                        if is_update:
                            preserved_dict[menu_name] += preserved_count

                    # 袋数の保存
                    logger.info(f'アレルギー袋数:{plate_name}:{count_dict}')
                    logger.info(f'アレルギー袋数(1人用):{plate_name}:{count_1p_dict}')
                    logger.info(f'アレルギー袋数(保存用):{plate_name}:{preserved_dict}')

                # 対象料理の全ての食種に紐づくアレルギーの袋数を算出してから、保存処理を行う
                logger.info(f'アレルギーインデックス:{plate_name}:{allergen_plate_index_dict}')
                for key, value in count_dict.items():
                    value_1p = count_1p_dict[key]

                    # 0件の場合は登録しない
                    if (not value) and (not value_1p):
                        continue

                    a_index = allergen_plate_index_dict[key]
                    is_roux = False
                    plate_package_qs = PlatePackageForPrint.objects.filter(
                        cooking_day=cooking_day, eating_day=eating_day,
                        is_basic_plate=False, meal_name=meal_name, menu_name=key, index=a_index)
                    if plate_package_qs.exists():
                        plate_package = plate_package_qs.first()
                        plate_package.count = value
                        plate_package.count_one_p = value_1p + preserved_dict[key]
                        plate_package.count_one_50g = count_50g
                        plate_package.save()
                        logger.info(f'save:{eating_day}-{meal_name}-{key}-{a_index}:{value}/{value_1p}/{preserved_dict[key]}')

                        allergen_plate_index_dict[key] += 1

                        #　カレールー嚥下対応
                        if cls.is_filling_and_sause_mix(plate_name) and key != '常食':
                            roux_plate_package = PlatePackageForPrint.objects.filter(
                                cooking_day=cooking_day, eating_day=eating_day,
                                is_basic_plate=False, meal_name=meal_name, menu_name=key, index=a_index + 1).first()
                            if roux_plate_package:
                                is_roux = True

                                # 袋数の内容は、本体側と同じ
                                roux_plate_package.count = value
                                roux_plate_package.count_one_p = value_1p + preserved_dict[key]
                                roux_plate_package.count_one_50g = count_50g
                                roux_plate_package.save()
                                allergen_plate_index_dict[key] += 1
                    else:
                        plate_package = None
                        logger.warn(f'not exists:{eating_day}-{meal_name}-{key}-{a_index}:{value}/{value_1p}/{preserved_dict[key]}')

                    # ピッキング指示書用の袋数を登録
                    if plate_package:
                        logger.info(f'UnitPackage登録対象:{target_plate}')
                        bulk_insert_list = []
                        for order in unit_package_dict[key]:
                            logger.info(f'UnitPackage登録:{order.unit_name.calc_name}-{order.quantity}')
                            quantity = order.quantity
                            if (quantity == 2) and (key != '常食'):
                                unit_package = UnitPackage(
                                    unit_name=order.unit_name.calc_name,
                                    unit_number=order.unit_name.unit_number,
                                    plate_name=plate_package.plate_name,
                                    cooking_day=cooking_day,
                                    index=a_index,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    menu_name=key,
                                    is_basic_plate=False,
                                    package=PackageMaster.objects.get(id=settings.PICKING_PACKAGES['ENGE_2']),
                                    count=1,
                                    cooking_direction_id=target_plate['model_id']
                                )
                                unit_package.save()

                                if is_roux:
                                    roux_unit_package = UnitPackage(
                                        unit_name=order.unit_name.calc_name,
                                        unit_number=order.unit_name.unit_number,
                                        plate_name=f'{plate_package.plate_name}のルー',
                                        cooking_day=cooking_day,
                                        index=a_index + 1,
                                        eating_day=eating_day,
                                        meal_name=meal_name,
                                        menu_name=key,
                                        is_basic_plate=False,
                                        package=PackageMaster.objects.get(id=settings.PICKING_PACKAGES['ENGE_2']),
                                        count=1,
                                        cooking_direction_id=target_plate['model_id']
                                    )
                                    roux_unit_package.save()

                                logger.info('嚥下2人袋登録')
                                continue

                            if quantity % 10 == 1:
                                # 1人用袋の出力
                                unit_package = UnitPackage(
                                    unit_name=order.unit_name.calc_name,
                                    unit_number=order.unit_name.unit_number,
                                    plate_name=plate_package.plate_name,
                                    cooking_day=cooking_day,
                                    index=a_index,
                                    eating_day=eating_day,
                                    meal_name=meal_name,
                                    menu_name=key,
                                    is_basic_plate=False,
                                    cooking_direction_id=target_plate['model_id']
                                )
                                if key == '常食':
                                    if plate_package.plate_name[0] == '⑤':
                                        unit_package.package = \
                                            PackageMaster.objects.get(id=settings.PICKING_PACKAGES['SOUP_1'])
                                    else:
                                        unit_package.package = \
                                            PackageMaster.objects.get(id=settings.PICKING_PACKAGES['BASIC_1'])
                                elif quantity == 1:
                                    unit_package.package = \
                                        PackageMaster.objects.get(id=settings.PICKING_PACKAGES['ENGE_1'])
                                else:
                                    # 嚥下でちょうど1でない場合は、1人用を出力しない
                                    continue
                                unit_package.count = 1
                                bulk_insert_list.append(unit_package)

                                if is_roux:
                                    # is_roux=Trueは嚥下のみ
                                    roux_unit_package = UnitPackage(
                                        unit_name=order.unit_name.calc_name,
                                        unit_number=order.unit_name.unit_number,
                                        plate_name=f'{plate_package.plate_name}のルー',
                                        cooking_day=cooking_day,
                                        index=a_index + 1,
                                        eating_day=eating_day,
                                        meal_name=meal_name,
                                        menu_name=key,
                                        is_basic_plate=False,
                                        cooking_direction_id=target_plate['model_id'],
                                        package=unit_package.package,
                                        count=1
                                    )
                                    bulk_insert_list.append(roux_unit_package)

                                logger.info('1人袋登録')
                                if unit_package.id:
                                    logger.info(f'append-1:{unit_package}')

                                quantity -= 1

                            if 'work_name' in target_plate:
                                logger.info('1,2人袋以外登録処理')

                                tmp_package_qs = TmpPlateNamePackage.objects.filter(
                                    cooking_day=cooking_day,
                                    menu_name=key if key == '常食' else '嚥下',
                                    plate_name=target_plate['plate']
                                )
                                if tmp_package_qs.exists():
                                    tmp_package = tmp_package_qs.first()
                                    q, r = divmod(quantity, tmp_package.size)
                                    logger.info(f'商：{q},余り:{r}')
                                    if q >= 1:
                                        unit_package = UnitPackage(
                                            unit_name=order.unit_name.calc_name,
                                            unit_number=order.unit_name.unit_number,
                                            plate_name=plate_package.plate_name,
                                            cooking_day=cooking_day,
                                            index=a_index,
                                            eating_day=eating_day,
                                            meal_name=meal_name,
                                            menu_name=key,
                                            is_basic_plate=False,
                                            cooking_direction_id=target_plate['model_id']
                                        )
                                        if key == '常食':
                                            if plate_package.plate_name[0] == '⑤':
                                                if tmp_package.size == 30:
                                                    package_id = settings.PICKING_PACKAGES['SOUP_UNIT']
                                                else:
                                                    package_id = settings.PICKING_PACKAGES['SOUP_10']
                                            else:
                                                if tmp_package.size == 30:
                                                    package_id = settings.PICKING_PACKAGES['BASIC_UNIT']
                                                elif tmp_package.size == 10:
                                                    package_id = settings.PICKING_PACKAGES['BASIC_10']
                                                else:
                                                    package_id = settings.PICKING_PACKAGES['BASIC_5']
                                        else:
                                            if tmp_package.size == 7:
                                                package_id = settings.PICKING_PACKAGES['ENGE_7']
                                            elif tmp_package.size == 14:
                                                package_id = settings.PICKING_PACKAGES['ENGE_14']
                                            else:
                                                package_id = settings.PICKING_PACKAGES['ENGE_20']
                                            if r:
                                                q += 1
                                        unit_package.package = PackageMaster.objects.get(id=package_id)
                                        unit_package.count = q
                                        bulk_insert_list.append(unit_package)

                                        if is_roux:
                                            # is_roux=Trueは嚥下のみ
                                            roux_unit_package = UnitPackage(
                                                unit_name=order.unit_name.calc_name,
                                                unit_number=order.unit_name.unit_number,
                                                plate_name=f'{plate_package.plate_name}のルー',
                                                cooking_day=cooking_day,
                                                index=a_index + 1,
                                                eating_day=eating_day,
                                                meal_name=meal_name,
                                                menu_name=key,
                                                is_basic_plate=False,
                                                cooking_direction_id=target_plate['model_id'],
                                                package=unit_package.package,
                                                count=unit_package.count
                                            )
                                            bulk_insert_list.append(roux_unit_package)

                                        if unit_package.id:
                                            logger.info(f'append-2:{unit_package}')
                                    if r:
                                        # 端数袋
                                        unit_package = UnitPackage(
                                            unit_name=order.unit_name.calc_name,
                                            unit_number=order.unit_name.unit_number,
                                            plate_name=plate_package.plate_name,
                                            cooking_day=cooking_day,
                                            index=a_index,
                                            eating_day=eating_day,
                                            meal_name=meal_name,
                                            menu_name=key,
                                            is_basic_plate=False,
                                            cooking_direction_id=target_plate['model_id']
                                        )
                                        if key == '常食':
                                            if plate_package.plate_name[0] == '⑤':
                                                package_id = settings.PICKING_PACKAGES['SOUP_FRACTION']
                                            else:
                                                package_id = settings.PICKING_PACKAGES['BASIC_FRACTION']
                                        else:
                                            package_id = settings.PICKING_PACKAGES['ENGE_20']
                                        logger.info(f'save-package-id:{package_id}')
                                        unit_package.package = PackageMaster.objects.get(id=package_id)
                                        unit_package.count = 1
                                        bulk_insert_list.append(unit_package)

                                        if is_roux:
                                            # is_roux=Trueは嚥下のみ
                                            roux_unit_package = UnitPackage(
                                                unit_name=order.unit_name.calc_name,
                                                unit_number=order.unit_name.unit_number,
                                                plate_name=f'{plate_package.plate_name}のルー',
                                                cooking_day=cooking_day,
                                                index=a_index + 1,
                                                eating_day=eating_day,
                                                meal_name=meal_name,
                                                menu_name=key,
                                                is_basic_plate=False,
                                                cooking_direction_id=target_plate['model_id'],
                                                package=unit_package.package,
                                                count=unit_package.count
                                            )
                                            bulk_insert_list.append(roux_unit_package)

                                        if unit_package.id:
                                            logger.info(f'append-3:{unit_package}')
                                else:
                                    logger.warn(f'{target_plate["plate"]}')

                        # 袋数情報を一括登録
                        if bulk_insert_list:
                            logger.info(f'一括登録対象:{[x for x in bulk_insert_list if x.id]}')
                            UnitPackage.objects.bulk_create(bulk_insert_list)


class PlateNameAnalizeUtil:
    """
    献立・料理名称の解釈内容を共通化するクラス
    """
    @classmethod
    def is_boiled_fish_plate(cls, plate_name):
        if '煮' in plate_name:
            if '魚' in plate_name:
                return True
            elif '鯖' in plate_name:
                return True
            elif '【さば】' in plate_name:
                return True
            elif 'ホキ' in plate_name:
                return True
            elif '鰆' in plate_name:
                return True
            elif '【さわら】' in plate_name:
                return True
            elif '鯵' in plate_name:
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def is_5p_package_plate(cls, plate_name):
        return '⑩' in plate_name

    @classmethod
    def is_sansyokudon_plate(cls, plate_name):
        if '三色丼' in plate_name:
            return True
        else:
            return False

    @classmethod
    def is_miso_soup(cls, plate_name):
        """
        対象の料理の名称が味噌汁かどうかを判断する。スープかどうか(⑤がつくかどうか)のチェックは別途行うこと。
        """
        if '味噌汁' in plate_name:
            return True
        elif 'みそ汁' in plate_name:
            return True
        elif 'みそしる' in plate_name:
            return True
        else:
            return False

    @classmethod
    def is_soup_liquid(cls, plate_name):
        """
        対象の料理の名称がスープの液(具以外)かどうかを判断する。スープかどうか(⑤がつくかどうか)のチェックは別途行うこと。
        """
        if '具' in plate_name:
            return False

        # CCの記載のない汁もあるので、希釈だけで判断する
        if '希釈' in plate_name:
            return True
        elif '水入れる' in plate_name:
            return True
        else:
            return False

    @classmethod
    def is_raw_plate(cls, plate):
        """
        原体送りの料理かどうかを判断する。
        """
        return '原体' in plate.plate_name

    @classmethod
    def is_raw_plate_name(cls, plate_name):
        """
        原体送りの料理かどうかを判断する。
        """
        return '原体' in plate_name

    @classmethod
    def is_raw_enge_plate_name(cls, plate_name: str, eating_day) -> (bool, bool):
        """
        原体の料理のうちの、嚥下製造対象かどうかを判断する。原体料理かどうかの判定はis_raw_plate_nameで行うこと。
        戻り値：嚥下製造対象か,主菜扱いするか
        """
        enable_day = datetime.datetime.strptime(settings.RAW_TO_ENGE_ENABLE, '%Y-%m-%d').date()
        if eating_day < enable_day:
            return False, False

        # 原体の中で対象商品名に含まれるものがあれば、嚥下製造対象と判断する
        for raw_plate in RawPlatePackageMaster.objects.all().exclude(enge_cooking_target='none'):
            if raw_plate.base_name in plate_name:
                logger.info(f'嚥下製造対象：{plate_name}')
                return True, raw_plate.enge_cooking_target == 'main'

        # 嚥下製造対象でなければ、2要素目は使われない前提
        logger.info(f'嚥下製造対象でない：{plate_name}')
        return False, False

    @classmethod
    def is_required_dry_notice(cls, plate):
        """
        乾燥品注意書き出力が必要かどうかを判定する。現在は、混ぜご飯に使われる錦糸卵のみ
        """
        if plate.is_mix_rice:
            if ('錦糸卵' in plate.plate_name) or ('きんしたまご' in plate.plate_name):
                return True
            else:
                return False
        else:
            False

    @classmethod
    def is_required_reference(cls, plate_name):
        """
        ピッキング指示書用特別出力対象かどうかを判定する
        """
        if ('錦糸卵' in plate_name) or ('きんしたまご' in plate_name):
            return True
        else:
            return False


    @classmethod
    def is_sub_package_size_enge_mix_rice(cls, plate_name, quantity):
        """
        対象料理が、嚥下混ぜご飯で副菜と同じ袋サイズとなる料理かどうかを判定する。
        """
        if float(quantity) < 30.0:
            if ('赤飯' in plate_name) or ('ひじきご' in plate_name) or ('ピラフ' in plate_name) or \
               ('チャーハン' in plate_name) or ('炒飯' in plate_name):
                return True, float(quantity) < 20.0

        return False, False


