import os
import datetime as dt
from decimal import Decimal

from accounts.models import User
from django.db import models
from django.core import validators
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill


# アップロードする際にファイル名が同じだと一意の名称に変更されるので削除するようにFileSystemStorageを変更
class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name): os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


# これをモデルクラス内で呼び出す
fs = OverwriteStorage(location=settings.MEDIA_ROOT)


class UnitMaster(models.Model):
    unit_name = models.CharField(verbose_name='ユニット名', max_length=100,)
    group = models.CharField(verbose_name='グループ', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', validators=[validators.MinValueValidator(0)],)
    is_active = models.BooleanField(verbose_name='利用中')
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    unit_code = models.IntegerField(verbose_name='得意先コード', validators=[validators.MinValueValidator(0)],)
    unit_number = models.IntegerField(verbose_name='呼出番号', null=True, blank=True)
    calc_name = models.CharField(verbose_name='ユニット合算名称', max_length=100, null=True, blank=True)
    short_name = models.CharField(verbose_name='ユニット合算省略名称', max_length=10, null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = 'ユニット情報一覧'

    def __str__(self):
        return self.unit_name


class MealMaster(models.Model):
    meal_name = models.CharField(verbose_name='食事区分名', max_length=100,)
    soup = models.BooleanField(verbose_name='汁')
    filling = models.BooleanField(verbose_name='具')
    miso_soup = models.CharField(verbose_name='味噌汁の内容', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_食事区分'

    def __str__(self):
        return self.meal_name


class MealDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    meal_name = models.ForeignKey(MealMaster, verbose_name='表示する食事区分', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '食事区分一覧'


class MenuMaster(models.Model):
    menu_name = models.CharField(verbose_name='献立種類名', max_length=100,)
    group = models.CharField(verbose_name='グループ', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_献立種類'

    def __str__(self):
        return self.menu_name


class MenuDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='表示する献立種類', on_delete=models.PROTECT)
    price_breakfast = models.IntegerField(verbose_name='朝食価格', blank=True, null=True)
    price_lunch = models.IntegerField(verbose_name='昼食価格', blank=True, null=True)
    price_dinner = models.IntegerField(verbose_name='夕食価格', blank=True, null=True)
    price_snack = models.IntegerField(verbose_name='間食価格', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '献立種類一覧'


class AllergenMaster(models.Model):
    allergen_name = models.CharField(verbose_name='アレルギー種類名', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', default=900, validators=[validators.MinValueValidator(0)],)
    is_common = models.BooleanField(verbose_name='頻発アレルギー')
    rakukon_name = models.CharField(verbose_name='らくらく献立用アレルギー名', max_length=100, blank=True, null=True)
    kana_name = models.CharField(verbose_name='かな名', max_length=40, blank=True, null=True)

    ignore_karte = models.BooleanField(verbose_name='カルテ出力対象外', default=False)

    class Meta:
        verbose_name = verbose_name_plural = 'アレルギー種類一覧'

    def __str__(self):
        return self.allergen_name

    def get_rakukon_name(self):
        return self.rakukon_name if self.rakukon_name else self.allergen_name


class AllergenDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    allergen_name = models.ForeignKey(AllergenMaster, verbose_name='表示するアレルギー', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '顧客別_アレルギー表示'


class Order(models.Model):
    eating_day = models.DateField(verbose_name='喫食日')
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    meal_name = models.ForeignKey(MealMaster, verbose_name='食事区分', on_delete=models.PROTECT)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    quantity = models.IntegerField(verbose_name='食数', blank=True, null=True,
                                   validators=[validators.MaxValueValidator(200), validators.MinValueValidator(0)])
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '注文データ_食数一覧'


class OrderBackup(models.Model):
    eating_day = models.DateField(verbose_name='喫食日')
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    meal_name = models.CharField(max_length=100, verbose_name='食事区分')
    menu_name = models.CharField(max_length=100, verbose_name='献立種類')
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    quantity = models.IntegerField(verbose_name='食数', blank=True, null=True,
                                   validators=[validators.MaxValueValidator(200), validators.MinValueValidator(0)])
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '注文データ_契約変更前バックアップ'


class OrderHistory(models.Model):
    eating_day = models.DateField(verbose_name='喫食日')
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    meal_name = models.ForeignKey(MealMaster, verbose_name='食事区分', on_delete=models.PROTECT)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    quantity = models.IntegerField(verbose_name='食数', blank=True, null=True,
                                   validators=[validators.MaxValueValidator(200)],)
    prev = models.IntegerField(verbose_name='注文前食数', blank=True, null=True,
                               validators=[validators.MaxValueValidator(200)],)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '注文データ更新履歴'


class OrderEveryday(models.Model):
    eating_day = models.DateField(verbose_name='喫食日', blank=True, null=True)
    unit_name = models.ForeignKey(UnitMaster, verbose_name='製造品名', on_delete=models.PROTECT)
    meal_name = models.ForeignKey(MealMaster, verbose_name='食事区分', on_delete=models.PROTECT)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類名', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    quantity = models.IntegerField(verbose_name='食数', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '注文データ_食数固定製造分'


class OrderRice(models.Model):
    eating_day = models.DateField(verbose_name='喫食日', blank=True, null=True)
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    quantity = models.DecimalField(verbose_name='合数', max_digits=3, decimal_places=1,
                                   blank=True, null=True,
                                   validators=[validators.MinValueValidator(0), validators.MaxValueValidator(200)],)

    class Meta:
        verbose_name = verbose_name_plural = '注文データ_合数一覧'


class RakukonShortname(models.Model):
    short_name = models.IntegerField(verbose_name='短縮名')
    group = models.CharField(verbose_name='グループ', max_length=100, blank=True, null=True)
    allergen = models.CharField(verbose_name='アレルギー種類名', max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = 'らくらく献立短縮名'

    def __str__(self):
        return str(self.short_name) + 'の' + self.group + self.allergen


class Communication(models.Model):
    def savePath(instance, filename):
        return f'upload/communication/{instance.created_at.strftime("%Y%m%d%H%M%S")}/{filename}'

    group = models.ForeignKey(Group, verbose_name='グループ', on_delete=models.PROTECT)
    title = models.CharField(verbose_name='タイトル', max_length=100)
    message = models.TextField(verbose_name='メッセージ内容', blank=True, null=True)
    created_at = models.DateTimeField(verbose_name='登録日', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    document_file = models.FileField(upload_to=savePath, storage=fs, verbose_name='添付ファイル', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = 'お知らせ管理'

    def __str__(self):
        return self.title


class ProductMaster(models.Model):
    product_code = models.CharField(verbose_name='商品コード', max_length=100)
    product_name = models.CharField(verbose_name='商品名', max_length=100)
    meal_name = models.ForeignKey(MealMaster, verbose_name='食事区分', on_delete=models.PROTECT)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_商品'

    def __str__(self):
        return self.product_code


class EverydaySelling(models.Model):
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    product_code = models.CharField(verbose_name='商品コード', max_length=50)
    product_name = models.CharField(verbose_name='商品名', max_length=100)
    quantity = models.IntegerField(verbose_name='売上数量')
    price = models.IntegerField(verbose_name='売上単価')
    enable = models.DateField(verbose_name='有効日(売上日)')

    class Meta:
        verbose_name = verbose_name_plural = '販売固定商品一覧'

    def __str__(self):
        return self.product_name


class InvoiceException(models.Model):
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT, unique=True)
    ng_saturday = models.IntegerField(verbose_name='土曜受取不可・調整日数')
    ng_sunday = models.IntegerField(verbose_name='日曜受取不可・調整日数')
    ng_holiday = models.IntegerField(verbose_name='祝日受取不可・調整日数')
    reduced_rate = models.BooleanField(verbose_name='業務委託・軽減税率なし')
    is_far = models.BooleanField(verbose_name='遠隔地・金曜受取調整あり')

    class Meta:
        verbose_name = verbose_name_plural = '顧客別_売上日調整日数'

    def __str__(self):
        return str(self.unit_name)


class SerialCount(models.Model):
    serial_name = models.CharField(verbose_name='名称', max_length=100)
    serial_number = models.BigIntegerField(verbose_name='シリアル値')

    class Meta:
        verbose_name = verbose_name_plural = 'シリアル値管理'

    def __str__(self):
        return self.serial_name


class UserOption(models.Model):
    username = models.ForeignKey(User, verbose_name='施設名', on_delete=models.PROTECT)
    unlock_limitation = models.BooleanField(default=True, verbose_name='仮受注期限解除する')
    unlock_day = models.DateField(verbose_name='解除日', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '顧客別_特別対応'

    def __str__(self):
        return str(self.username)


class DocumentMaster(models.Model):
    document_kind = models.CharField(verbose_name='資料種類名', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_資料種類'

    def __str__(self):
        return self.document_kind


class DocGroupMaster(models.Model):
    group_name = models.CharField(verbose_name='登録グループ名', max_length=100,)
    seq_order = models.IntegerField(verbose_name='表示順', default=10, validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_資料登録グループ'

    def __str__(self):
        return str(self.group_name)


class DocGroupDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    group_name = models.ForeignKey(DocGroupMaster, verbose_name='登録グループ名', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '顧客別_資料登録グループ表示'

    def __str__(self):
        return str(self.username)


class PaperDocuments(models.Model):
    document_file = models.FileField(upload_to='documents/', verbose_name='ファイル名')
    document_kind = models.ForeignKey(DocumentMaster, verbose_name='資料種類', on_delete=models.PROTECT)
    document_group = models.ForeignKey(DocGroupMaster, verbose_name='資料登録グループ', on_delete=models.PROTECT)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_献立資料'


class ZippedDocumentFiles(models.Model):
    year = models.IntegerField(verbose_name='対象年')
    month = models.IntegerField(verbose_name='対象月',
                                validators=[validators.MinValueValidator(1), validators.MaxValueValidator(12)])
    document_file = models.FileField(upload_to='upload/', verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_献立資料zip'

    def __str__(self):
        return self.document_file.url


class InvoiceFiles(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    document_file = models.FileField(upload_to='invoice/', verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_請求書PDF'

    def __str__(self):
        return self.document_file.url


class ImportMenuName(models.Model):
    document_file = models.FileField(upload_to='upload/', storage=fs, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_調理表'


class ImportMonthlyMenu(models.Model):
    document_file = models.FileField(upload_to='upload/', storage=fs, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_月間献立表'


class MonthlyMenu(models.Model):
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分', max_length=50,)
    food_name = models.CharField(verbose_name='料理名', max_length=200)
    option = models.BooleanField(default=False, verbose_name='オプション')
    seq_order = models.IntegerField(verbose_name='表示順', default=10)

    class Meta:
        verbose_name = verbose_name_plural = '月間献立'

    def __str__(self):
        return self.food_name


def dir_path_name(instance, filename):
    now = dt.datetime.now()
    dir_path = os.path.join('photos', f'{now.timestamp()}_{filename}')
    return dir_path

SELECTION = (('温め', '温め'), ('冷蔵', '冷蔵'), ('その他', 'その他'))
fs_photo = FileSystemStorage(location=settings.MEDIA_ROOT)
class FoodPhoto(models.Model):
    food_name = models.CharField(verbose_name='料理名', max_length=200)
    menu = models.ForeignKey(MonthlyMenu, verbose_name='献立', blank=True, null=True, on_delete=models.CASCADE)
    hot_cool = models.CharField(choices=SELECTION, verbose_name='温め・冷蔵', max_length=10, blank=True, null=True)
    direction = models.TextField(verbose_name='調理補足説明', blank=True, null=True)
    direction2 = models.TextField(verbose_name='調理補足説明2', blank=True, null=True)
    photo_file = models.ImageField(upload_to=dir_path_name, storage=fs_photo, verbose_name='写真データ', blank=True, null=True)

    thumbnail = ImageSpecField(source='photo_file',
                               processors=[ResizeToFill(110, 90)],
                               format="JPEG",
                               options={'quality': 100}
                               )

    wide = ImageSpecField(source='photo_file',
                          processors=[ResizeToFill(180, 90)],
                          format="JPEG",
                          options={'quality': 100}
                          )

    basic = ImageSpecField(source='photo_file',
                           processors=[ResizeToFill(230, 133)],
                           options={'quality': 100}
                           )

    middle = ImageSpecField(source='photo_file',
                            processors=[ResizeToFill(600, 400)],
                            format="JPEG",
                            options={'quality': 100}
                            )

    class Meta:
        verbose_name = verbose_name_plural = '料理写真'

    def __str__(self):
        return self.food_name


class EngeFoodDirection(models.Model):
    menu = models.ForeignKey(MonthlyMenu, verbose_name='献立', on_delete=models.CASCADE)
    soft_direction = models.CharField(verbose_name='ソフト食調理補足説明', max_length=30, blank=True, null=True)
    soft_direction2 = models.CharField(verbose_name='ソフト食調理補足説明2', max_length=30, blank=True, null=True)
    soft_direction3 = models.CharField(verbose_name='ソフト食調理補足説明3', max_length=30, blank=True, null=True)
    soft_direction4 = models.CharField(verbose_name='ソフト食調理補足説明4', max_length=30, blank=True, null=True)
    soft_direction5 = models.CharField(verbose_name='ソフト食調理補足説明5', max_length=30, blank=True, null=True)

    mixer_direction = models.CharField(verbose_name='ミキサー食調理補足説明', max_length=30, blank=True, null=True)
    mixer_direction2 = models.CharField(verbose_name='ミキサー食調理補足説明2', max_length=30, blank=True, null=True)
    mixer_direction3 = models.CharField(verbose_name='ミキサー食調理補足説明3', max_length=30, blank=True, null=True)
    mixer_direction4 = models.CharField(verbose_name='ミキサー食調理補足説明4', max_length=30, blank=True, null=True)
    mixer_direction5 = models.CharField(verbose_name='ミキサー食調理補足説明5', max_length=30, blank=True, null=True)

    jelly_direction = models.CharField(verbose_name='ゼリー食調理補足説明', max_length=30, blank=True, null=True)
    jelly_direction2 = models.CharField(verbose_name='ゼリー食調理補足説明2', max_length=30, blank=True, null=True)
    jelly_direction3 = models.CharField(verbose_name='ゼリー食調理補足説明3', max_length=30, blank=True, null=True)
    jelly_direction4 = models.CharField(verbose_name='ゼリー食調理補足説明4', max_length=30, blank=True, null=True)
    jelly_direction5 = models.CharField(verbose_name='ゼリー食調理補足説明5', max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '嚥下料理料理説明'

    def __str__(self):
        return f'{self.menu.food_name}({self.menu.meal_name})'


class GenericSetoutDirection(models.Model):
    direction = models.TextField(verbose_name="定型文")
    shortening = models.CharField(verbose_name="短縮名称", max_length=24)
    for_enge = models.BooleanField(verbose_name="嚥下用", default=False)

    class Meta:
        verbose_name = verbose_name_plural = '献立定型文'

    def __str__(self):
        return self.shortening


class Chat(models.Model):

    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    is_sendto = models.BooleanField(verbose_name='送信メッセージ')
    message = models.TextField(verbose_name='メッセージ内容')
    is_read = models.BooleanField(verbose_name='既読')
    created_at = models.DateTimeField(verbose_name='登録日', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'チャット'

    def __str__(self):
        return str(self.username)


class HolidayList(models.Model):

    holiday_name = models.CharField(verbose_name='休暇種別', max_length=50)
    start_date = models.DateField(verbose_name='開始日')
    end_date = models.DateField(verbose_name='終了日')
    limit_day = models.DateField(verbose_name='入力締め切り日', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '長期休暇確認'

    def __str__(self):
        return str(self.holiday_name)


class JapanHoliday(models.Model):
    """
    祝日情報を持つmodel
    """
    name = models.CharField(verbose_name='祝日名', max_length=50)
    date = models.DateField(verbose_name='日付')

    class Meta:
        verbose_name = verbose_name_plural = '祝日'

    def __str__(self):
        return str(self.name)


SOUP_TYPE_SELECTION = (('スープ', 'スープ'), ('汁', '汁'))
AGG_MEASURE_OUTPUT_SELECTION = (('端数出力', '端数出力'), ('施設毎出力', '施設毎出力'))
class AggMeasureSoupMaster(models.Model):
    """
    計量表上の味噌汁以外の汁・スープ情報を持つmodel
    """
    name = models.CharField(verbose_name='名前', max_length=50)
    search_word = models.CharField(verbose_name='検索文言', max_length=50)
    soup_group = models.CharField(choices=SOUP_TYPE_SELECTION, verbose_name='汁・スープ', max_length=10)
    output_type = models.CharField(choices=AGG_MEASURE_OUTPUT_SELECTION, verbose_name='出力形式', max_length=10)

    class Meta:
        verbose_name = verbose_name_plural = 'マスタ_計量表用スープ'

    def __str__(self):
        return str(self.name)

    def get_short_name(self):
        if self.name.find('汁') != -1:
            find_index = self.name.find('汁') + 1
        elif self.name.find('スープ') != -1:
            find_index = self.name.find('スープ') + len('スープ')
        else:
            return self.name

        return self.name[0:find_index]


class AggMeasureMixRiceMaster(models.Model):
    """
    計量表上の混ぜご飯情報を持つmodel
    """
    name = models.CharField(verbose_name='混ぜご飯名', max_length=50)
    search_word = models.CharField(verbose_name='検索文言', max_length=50)
    is_mix_package = models.BooleanField(verbose_name='混ぜご飯の素を出力するもの', default=False)
    is_write_rate = models.BooleanField(verbose_name='個別食材出力対象', default=False)
    max_rate = models.DecimalField(verbose_name='材料比率最大値', default=100, max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = verbose_name_plural = '混ぜご飯一覧'

    def __str__(self):
        return str(self.name)


class CommonAllergen(models.Model):
    """
    頻発アレルギーの使用状況を管理するmodel
    """
    code = models.CharField(verbose_name='短縮名', max_length=6)
    name = models.CharField(verbose_name='対応アレルギー名', max_length=50)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    seq_order = models.IntegerField(verbose_name='らくらく献立表示順', default=10, validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = '頻発アレルギー'

    def __str__(self):
        return f'{str(self.code)}-{self.name}'


class UncommonAllergen(models.Model):
    """
    散発アレルギーの使用状況を管理するmodel
    """
    code = models.CharField(verbose_name='短縮名', max_length=6)
    name = models.CharField(verbose_name='対応アレルギー名', max_length=50)
    menu_name = models.ForeignKey(MenuMaster, verbose_name='献立種類', on_delete=models.PROTECT)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)
    last_use_date = models.DateTimeField(verbose_name='最終使用日時', auto_now=True)
    seq_order = models.IntegerField(verbose_name='らくらく献立表示順', default=10, validators=[validators.MinValueValidator(0)],)

    class Meta:
        verbose_name = verbose_name_plural = '散発アレルギー'

    def __str__(self):
        return f'{str(self.code)}-{self.name}'


class UncommonAllergenHistory(models.Model):
    cooking_day = models.DateField(verbose_name='製造日')
    code = models.CharField(verbose_name='短縮名', max_length=6)
    menu_name = models.CharField(verbose_name='献立種類', default='基本食', max_length=10)
    allergen = models.ForeignKey(AllergenMaster, verbose_name='アレルギー種類', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '散発アレルギー_履歴'

    def __str__(self):
        return f'{str(self.code)}({self.cooking_day})'


SELECTION_ENGE_DIRECTION = (('1', 'タレなどをかける'), ('2', 'タレなどを盛り付ける'), ('9', 'フリー入力'))
class EngeDirection(models.Model):
    food_name = models.CharField(verbose_name='料理名', max_length=200, unique=True)
    direction_type = models.CharField(choices=SELECTION_ENGE_DIRECTION, verbose_name='記述方針', max_length=10, blank=True, null=True)
    soe = models.CharField(verbose_name='タレなど', max_length=24, blank=True, null=True)
    direction_mixer_1 = models.CharField(verbose_name='指示(ミキサー)1行目', max_length=50, blank=True, null=True)
    direction_mixer_2 = models.CharField(verbose_name='指示(ミキサー)2行目', max_length=50, blank=True, null=True)
    direction_mixer_3 = models.CharField(verbose_name='指示(ミキサー)3行目', max_length=50, blank=True, null=True)
    direction_other_1 = models.CharField(verbose_name='指示(ミキサー以外)1行目', max_length=50, blank=True, null=True)
    direction_other_2 = models.CharField(verbose_name='指示(ミキサー以外)2行目', max_length=50, blank=True, null=True)
    direction_other_3 = models.CharField(verbose_name='指示(ミキサー以外)3行目', max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '嚥下献立指示書_特別対応'

    def __str__(self):
        return self.food_name


class NewYearDaySetting(models.Model):
    year = models.IntegerField(verbose_name='適用年', validators=[validators.MinValueValidator(2022)], unique=True,)
    enable_date_from = models.DateField(verbose_name='受付開始日')
    enable_date_to = models.DateField(verbose_name='受付締め切り日')

    class Meta:
        verbose_name = verbose_name_plural = '元日注文確認'

    def __str__(self):
        return f'{self.year}年({self.enable_date_from}～{self.enable_date_to})'


# 契約変更時、アレルギー注文で変更期日までは変更前の状態を選択できるようにするためのモデル
class ReservedMealDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    meal_name = models.ForeignKey(MealMaster, verbose_name='表示する食事区分', on_delete=models.PROTECT)
    disable_date = models.DateField(verbose_name='無効になる日')

    class Meta:
        verbose_name = verbose_name_plural = '契約変更_食事区分表示'

    def __str__(self):
        return f'{self.username}-{self.meal_name}(～{self.disable_date}))'


class DocumentDirDisplay(models.Model):
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    plate_dir_name = models.CharField(verbose_name='食種フォルダ名', max_length=50, blank=True, null=True)
    enable_date = models.DateField(verbose_name='設定有効日')

    class Meta:
        verbose_name = verbose_name_plural = '顧客別-献立資料フォルダ一覧'

    def __str__(self):
        return f'{self.username}-{self.plate_dir_name}({self.enable_date}～))'


# 栄養月報
class ImportMonthlyReport(models.Model):
    document_file = models.FileField(upload_to='upload/monthly/', storage=fs, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_栄養月報'


# 献立しないストレージを使用する
fs_menu = FileSystemStorage(location=settings.MEDIA_ROOT)


# ラベル印刷用月間献立ファイルインポート
class ImportP7SourceFile(models.Model):
    def savePath(instance, filename):
        return f'upload/p7/{instance.file_type_no}/{filename}'

    document_file = models.FileField(upload_to=savePath, storage=fs_menu, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    file_type_no = models.IntegerField(verbose_name='献立種類番号', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_ラベル印刷用月間献立ファイル'


class SetoutDuration(models.Model):
    name = models.CharField(verbose_name='献立指示書名', max_length=100)
    create_at = models.DateField(verbose_name='登録日', auto_now_add=True)
    last_enable = models.DateField(verbose_name='盛付指示書表示最終日', blank=True, null=True)
    is_hide = models.BooleanField(verbose_name='盛付指示書を施設に表示しない', default=False)

    class Meta:
        verbose_name = verbose_name_plural = '盛付指示書_保持期間'

    def __str__(self):
        return f'{self.name}'


class MixRicePackageMaster(models.Model):
    parts_name = models.CharField(verbose_name='献立・料理名', max_length=100)
    package_size = models.IntegerField(verbose_name='サイズ(g・個/袋)')

    class Meta:
        verbose_name = verbose_name_plural = '混ぜご飯袋サイズ一覧'

    def __str__(self):
        return f'{self.parts_name}({self.package_size}g・個/袋)'


class PlatePackageForPrint(models.Model):
    """
    ラベル印刷用献立パッケージ情報。食事区分は、朝食・昼食・夕食が分かれば良いので、参照ではなく文字列とした
    """
    plate_name = models.CharField(verbose_name='献立・料理名', max_length=100)
    cooking_day = models.DateField(verbose_name='製造日')
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分', max_length=8)
    is_basic_plate = models.BooleanField(verbose_name='基本食かどうか')
    index = models.IntegerField(verbose_name='献立出力インデックス')
    count = models.IntegerField(verbose_name='袋数', default=0)
    count_one_p = models.IntegerField(verbose_name='1人用袋数', default=0)
    count_one_50g = models.IntegerField(verbose_name='50g用袋数', default=0)
    updated_at = models.DateTimeField(verbose_name='更新日時', auto_now=True)
    menu_name = models.CharField(verbose_name='献立種類', default='基本食', max_length=10)

    class Meta:
        verbose_name = verbose_name_plural = 'ラベル印刷用献立パッケージ'

    def __str__(self):
        return f'({self.eating_day}_{self.meal_name}){self.plate_name}({"基本食" if self.is_basic_plate else "アレルギー食"})'


class PlateMenuForPrint(models.Model):
    """
    ラベル印刷用献立情報(P7対応で使用する)。らくらく献立から出力された月間献立(盛付指示書用のものとは別)を読み取った内容
    """
    name = models.CharField(verbose_name='献立・料理名', max_length=100)
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分', max_length=8)
    index = models.IntegerField(verbose_name='献立出力インデックス')
    additive = models.CharField(verbose_name='添加物', max_length=200)
    allergen = models.CharField(verbose_name='アレルギー', max_length=200)
    cal = models.FloatField(verbose_name='カロリー(kcal)', default=0.0)
    protein = models.FloatField(verbose_name='たんぱく質', default=0.0)
    fat = models.FloatField(verbose_name='脂質', default=0.0)
    carbohydrates = models.FloatField(verbose_name='炭水化物', default=0.0)
    salt = models.FloatField(verbose_name='食塩', default=0.0)
    updated_at = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    # 通常/アレルギー/サンプル
    type_name = models.CharField(verbose_name='献立表種別', default='通常', max_length=10)
    menu_name = models.CharField(verbose_name='献立種類', default='基本食', max_length=10)

    cooking_day = models.DateField(verbose_name='製造日', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = 'ラベル印刷用献立内容'

    def __str__(self):
        return f'({self.eating_day}_{self.meal_name}){self.name}'


class CookingDirectionPlate(models.Model):
    """
    調理表管理の献立内容
    """
    cooking_day = models.DateField(verbose_name='調理日')
    eating_day = models.DateField(verbose_name='喫食日')
    plate_name = models.CharField(verbose_name='料理名', max_length=100)
    meal_name = models.CharField(verbose_name='食事区分', max_length=8)
    seq_meal = models.IntegerField(verbose_name='食事区分表示順')
    index = models.IntegerField(verbose_name='料理出現位置インデックス')
    is_basic_plate = models.BooleanField(verbose_name='基本食かどうか', default=True)
    is_soup = models.BooleanField(verbose_name='汁・汁具かどうか', default=False)
    is_allergen_plate = models.BooleanField(verbose_name='アレルギー代替食かどうか', default=False)
    is_mix_rice = models.BooleanField(verbose_name='混ぜご飯関連かどうか', default=False)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '調理表献立'


class AllergenPlateRelations(models.Model):
    """
    アレルギー代替食の関連
    """
    plate = models.ForeignKey(CookingDirectionPlate, verbose_name='料理', on_delete=models.PROTECT, related_name='target_plate', blank=True, null=True)
    source = models.ForeignKey(CookingDirectionPlate, verbose_name='代替対象の料理', on_delete=models.PROTECT, related_name='source_plate')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)
    code = models.CharField(verbose_name='食種', max_length=50)

    class Meta:
        verbose_name = verbose_name_plural = '調理表献立_アレルギー紐付'


class BackupAllergenPlateRelations(models.Model):
    """
    AllergenPlateRelationsの前回入力内容
    """
    cooking_day = models.DateField(verbose_name='調理日')
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分', max_length=8)
    plate_name = models.CharField(verbose_name='料理', max_length=100, blank=True, null=True)
    source_name = models.CharField(verbose_name='代替対象の料理', max_length=100)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)
    code = models.CharField(verbose_name='食種', max_length=50)
    backuped_at = models.DateTimeField(verbose_name='バックアップ日時', default=None, blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = 'アレルギー紐付履歴'


class MonthlySalesPrice(models.Model):
    """
    売価計算情報
    """
    year = models.IntegerField(verbose_name='対象年', validators=[validators.MinValueValidator(2022)],)
    month = models.IntegerField(verbose_name='対象月',
                                validators=[validators.MinValueValidator(1), validators.MaxValueValidator(12)],)
    transport_price = models.IntegerField(verbose_name='配送料(税別)', validators=[validators.MinValueValidator(0)], default=0)

    basic_breakfast_count = models.IntegerField(verbose_name='基本食・朝食食数', validators=[validators.MinValueValidator(0)], default=0)
    basic_lunch_count = models.IntegerField(verbose_name='基本食・昼食食数', validators=[validators.MinValueValidator(0)], default=0)
    basic_dinner_count = models.IntegerField(verbose_name='基本食・夕食食数', validators=[validators.MinValueValidator(0)], default=0)

    basic_breakfast_sales = models.DecimalField(verbose_name='基本食・朝食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    basic_lunch_sales = models.DecimalField(verbose_name='基本食・昼食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    basic_dinner_sales = models.DecimalField(verbose_name='基本食・夕食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))

    basic_breakfast_soup_sales = models.DecimalField(verbose_name='基本食・朝食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    basic_lunch_soup_sales = models.DecimalField(verbose_name='基本食・昼食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    basic_dinner_soup_sales = models.DecimalField(verbose_name='基本食・夕食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))

    enge_breakfast_count = models.IntegerField(verbose_name='嚥下食・朝食食数', validators=[validators.MinValueValidator(0)], default=0)
    enge_lunch_count = models.IntegerField(verbose_name='嚥下食・昼食食数', validators=[validators.MinValueValidator(0)], default=0)
    enge_dinner_count = models.IntegerField(verbose_name='嚥下食・夕食食数', validators=[validators.MinValueValidator(0)], default=0)

    enge_breakfast_sales = models.DecimalField(verbose_name='嚥下食・朝食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    enge_lunch_sales = models.DecimalField(verbose_name='嚥下食・昼食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    enge_dinner_sales = models.DecimalField(verbose_name='嚥下食・夕食売上', max_digits=12, decimal_places=3, default=Decimal(0.0))

    enge_breakfast_soup_sales = models.DecimalField(verbose_name='嚥下食・朝食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    enge_lunch_soup_sales = models.DecimalField(verbose_name='嚥下食・昼食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))
    enge_dinner_soup_sales = models.DecimalField(verbose_name='嚥下食・夕食汁売上', max_digits=12, decimal_places=3, default=Decimal(0.0))

    transport_breakfast_rate = models.IntegerField(verbose_name='配送料比率・朝食', default=1)
    transport_lunch_rate = models.IntegerField(verbose_name='配送料比率・昼食', default=2)
    transport_dinner_rate = models.IntegerField(verbose_name='配送料比率・夕食', default=2)

    class Meta:
        verbose_name = verbose_name_plural = '売価履歴'

    def __str__(self):
        return f'{self.year}-{self.month}売上情報)'


class NewUnitPrice(models.Model):
    """
    単価変更情報。eating_dayは都合により喫食日の記述となっているが、売上日と紐づくため注意
    """
    username = models.ForeignKey(User, to_field='username', verbose_name='施設名', on_delete=models.PROTECT)
    menu_name = models.CharField(verbose_name='献立種類名', max_length=100,)
    price_breakfast = models.IntegerField(verbose_name='朝食価格', blank=True, null=True)
    price_lunch = models.IntegerField(verbose_name='昼食価格', blank=True, null=True)
    price_dinner = models.IntegerField(verbose_name='夕食価格', blank=True, null=True)
    price_snack = models.IntegerField(verbose_name='間食価格', blank=True, null=True)
    eating_day = models.DateField(verbose_name='単価適用喫食日')

    class Meta:
        verbose_name = verbose_name_plural = '単価情報一覧'


# ピッキング結果ファイル
fs_pick = FileSystemStorage(location=settings.MEDIA_ROOT)
class PickingResult(models.Model):
    document_file = models.FileField(upload_to='upload/picking/', storage=fs_pick, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_ピッキング結果'



class PackageMaster(models.Model):
    """
    料理を入れる袋の種類を定義するModel
    """
    name = models.CharField(verbose_name='袋名称', max_length=50, unique=True)
    quantity = models.IntegerField(verbose_name='内容量(人前)', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '袋種類マスタ'

    def __str__(self):
        return self.name


package_enge_choices = (
    ('常食', '常食'),
    ('ソフト', 'ソフト'),
    ('ゼリー', 'ゼリー'),
    ('ミキサー', 'ミキサー'),
)
package_mix_rice_plate_choices = (
    ('main', 'メイン'),
    ('parts', 'パーツ'),
    ('none', '対象外')
)
package_soup_plate_choices = (
    ('soup', '汁(スープ)'),
    ('filling', '汁具'),
    ('none', '対象外')
)
class UnitPackage(models.Model):
    """
    施設毎、喫食日、食事区分、料理毎の袋枚数を管理するモデルげ。
    ユニット名は合算名称を使用しているため、FK(UnitMaster)を非採用とした。
    食事区分も汁オプションの違いを持つ必要がないため、名称のみとした。
    """
    unit_name = models.CharField(verbose_name='ユニット名', max_length=100,)
    unit_number = models.IntegerField(verbose_name='呼出番号', null=True, blank=True)
    plate_name = models.CharField(verbose_name='料理名', max_length=100)
    cooking_day = models.DateField(verbose_name='製造日', null=True, blank=True)
    index = models.IntegerField(verbose_name='インデックス', null=True, blank=True)
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分名', max_length=10,)
    package = models.ForeignKey(PackageMaster, verbose_name='袋種類', on_delete=models.PROTECT)
    count = models.IntegerField(verbose_name='必要数', default=0)
    menu_name = models.CharField(verbose_name='献立種類', max_length=10, choices=package_enge_choices)
    register_at = models.DateTimeField(verbose_name='登録日時', auto_now=True)

    is_basic_plate = models.BooleanField(verbose_name='通常食', default=True)
    cooking_direction = models.ForeignKey(CookingDirectionPlate, verbose_name='調理票データ', null=True, blank=True, on_delete=models.PROTECT)

    mix_rice_type = models.CharField(verbose_name='混ぜご飯区分', max_length=10, choices=package_mix_rice_plate_choices)
    soup_type = models.CharField(verbose_name='汁種類区分', max_length=10, choices=package_soup_plate_choices)

    class Meta:
        verbose_name = verbose_name_plural = '施設毎_ピッキング袋数'

    def __str__(self):
        return f'{self.unit_name}({self.eating_day}-{self.meal_name}){self.package}'


enge_cooking_choices = (
    ('none', '対象外'),
    ('main', '対象(主菜)'),
    ('sub', '対象(主菜以外)')
)
class RawPlatePackageMaster(models.Model):
    """
    原体送り料理のパッケージの情報を定義するモデル
    """
    dry_name = models.CharField(verbose_name='注文名称(乾燥)', max_length=100,)
    cold_name = models.CharField(verbose_name='注文名称(冷凍)', max_length=100,)
    chilled_name = models.CharField(verbose_name='注文名称(冷蔵)', max_length=100,)
    base_name = models.CharField(verbose_name='原体料理名', max_length=100,)
    dry_eneble_name_gram = models.BooleanField(verbose_name='分量読取(乾燥)', default=False)
    dry_quantity = models.DecimalField(verbose_name='1人分分量(乾燥)', max_digits=5, decimal_places=2, default=Decimal(0.0))
    cold_eneble_name_gram = models.BooleanField(verbose_name='分量読取(冷凍)', default=False)
    cold_quantity = models.DecimalField(verbose_name='1人分分量(冷凍)', max_digits=5, decimal_places=2, default=Decimal(0.0))
    chilled_eneble_name_gram = models.BooleanField(verbose_name='分量読取(冷蔵)', default=False)
    chilled_quantity = models.DecimalField(verbose_name='1人分分量(冷蔵)', max_digits=5, decimal_places=2, default=Decimal(0.0))
    dry_unit = models.CharField(verbose_name='乾燥単位', max_length=8,)
    cold_unit = models.CharField(verbose_name='冷凍単位', max_length=8,)
    chilled_unit = models.CharField(verbose_name='冷蔵単位', max_length=8,)
    dry_package_quantity = models.DecimalField(verbose_name='1パッケージ分量(乾燥)', max_digits=8, decimal_places=2, default=Decimal(0.0))
    cold_package_quantity = models.DecimalField(verbose_name='1パッケージ分量(冷凍)', max_digits=8, decimal_places=2, default=Decimal(0.0))
    chilled_package_quantity = models.DecimalField(verbose_name='1パッケージ分量(冷蔵)', max_digits=8, decimal_places=2, default=Decimal(0.0))
    is_direct_dry = models.BooleanField(verbose_name='直送対象(乾燥)', default=False)
    is_direct_cold = models.BooleanField(verbose_name='直送対象(冷凍)', default=False)
    is_direct_chilled = models.BooleanField(verbose_name='直送対象(冷蔵)', default=False)

    enge_cooking_target = models.CharField(verbose_name='嚥下製造対象', max_length=10, choices=enge_cooking_choices, default='none')

    class Meta:
        verbose_name = verbose_name_plural = '原体送り料理一覧'

    def __str__(self):
        return f'{self.base_name}'

class PickingRawPlatePackage(models.Model):
    """
    原体送りの施設毎のピッキング袋数情報
    """
    cooking_day = models.DateField(verbose_name='製造日')
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分名', max_length=10,)
    unit_name = models.ForeignKey(UnitMaster, verbose_name="送付先ユニット", on_delete=models.CASCADE)
    package_master = models.ForeignKey(RawPlatePackageMaster, verbose_name='原体商品', on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name='数量', blank=True, null=True)
    package = models.IntegerField(verbose_name='1袋あたりの量', blank=True, null=True)
    register_at = models.DateTimeField(verbose_name='登録日時', auto_now=True)

    dry_cold_type = models.CharField(verbose_name='乾燥・冷凍区分', max_length=10,)

    class Meta:
        verbose_name = verbose_name_plural = 'ピッキング_原体送り袋数'

    def __str__(self):
        return f'{self.base_name}'


class TmpPlateNamePackage(models.Model):
    cooking_day = models.DateField(verbose_name='製造日')
    plate_name = models.CharField(verbose_name='料理名', max_length=100)
    size = models.IntegerField(verbose_name='袋サイズ')
    menu_name = models.CharField(verbose_name='献立種類', max_length=10)


picking_type_choices = (
    ('中袋', '中袋'),
    ('段ボール', '段ボール'),
)
class PickingResultRaw(models.Model):
    menu_file_no = models.IntegerField(verbose_name='ピッキングメニューファイル番号')
    menu_no = models.IntegerField(verbose_name='実施メニュー番号')
    terminal_no = models.CharField(verbose_name='端末番号', max_length=10)
    picking_date = models.DateTimeField(verbose_name='ピッキング実施日時')
    qr_value = models.CharField(verbose_name='QRコード値', max_length=24)
    result = models.CharField(verbose_name='読み取り結果', max_length=8)
    upload_file_name = models.CharField(verbose_name='結果ファイル名', max_length=256, default='')
    created_at = models.DateTimeField(verbose_name='登録日', auto_now=True)
    picking_phase = models.CharField(verbose_name='照合パターン', max_length=16, choices=picking_type_choices)

    class Meta:
        verbose_name = verbose_name_plural = 'ピッキング_照合結果'

    def __str__(self):
        return f'{self.terminal_no}-{self.picking_date}'


class PickingNotice(models.Model):
    cooking_date = models.DateTimeField(verbose_name='製造日')
    note = models.CharField(verbose_name='備考内容', max_length=2048, choices=picking_type_choices)

    class Meta:
        verbose_name = verbose_name_plural = 'ピッキング_備考'


class ReqirePickingPackage(models.Model):
    unit_number = models.IntegerField(verbose_name='呼出番号', null=True, blank=True)
    short_name = models.CharField(verbose_name='ユニット合算省略名称', max_length=10, null=True, blank=True)
    cooking_day = models.DateField(verbose_name='製造日')
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name='食事区分', max_length=10)
    picking_type_code = models.CharField(verbose_name='中袋種類', max_length=2)
    order_count = models.IntegerField(verbose_name='注文数', default=0)
    package_count = models.IntegerField(verbose_name='中袋数', default=0)
    created_at = models.DateTimeField(verbose_name='登録日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'ピッキング必要中袋数'


class InvoiceDataHistory(models.Model):
    created_at = models.DateTimeField(verbose_name='登録日時', auto_now=True)

    recode_code = models.IntegerField(verbose_name='レコード区分', default=0)
    data_recode_code = models.CharField(verbose_name='データレコード区分', max_length=10, default='ur01')
    report_code = models.IntegerField(verbose_name='伝票区分', default=0)
    report_number = models.CharField(verbose_name='伝票NO', max_length=10)
    sale_day = models.DateField(verbose_name='売上日')
    unit_code = models.IntegerField(verbose_name='得意先コード', validators=[validators.MinValueValidator(0)],)
    calc_name = models.CharField(verbose_name='得意先名称', max_length=100, null=True, blank=True)
    tax_code = models.IntegerField(verbose_name='消費税率コード', default=0)
    tax = models.IntegerField(verbose_name='消費税率', default=0)
    line_no = models.IntegerField(verbose_name='行番号', default=0)
    customer_type = models.IntegerField(verbose_name='行番号', default=0)
    customer_type_name = models.CharField(verbose_name='得意先名称', max_length=100, null=True, blank=True)
    item_code = models.CharField(verbose_name='商品コード', max_length=10)
    item_name = models.CharField(verbose_name='商品名', max_length=100, null=True, blank=True)
    input_code = models.IntegerField(verbose_name='数量入力区分', default=1)
    unit_price_code = models.IntegerField(verbose_name='選択単価区分', default=1)
    sales_quantity = models.IntegerField(verbose_name='売上数量', default=0)
    sales_unit_price = models.IntegerField(verbose_name='売上単価', default=0)
    cost_unit_price = models.IntegerField(verbose_name='原価単価', default=0)
    taxation_code = models.IntegerField(verbose_name='課税区分', default=1)
    tax_replace = models.IntegerField(verbose_name='消費税訂正額', default=0)
    sales = models.IntegerField(verbose_name='売上', default=0)

    sales = models.IntegerField(verbose_name='売上', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '請求データ履歴'


class ReservedStop(models.Model):
    unit_name = models.ForeignKey(UnitMaster, verbose_name='ユニット名', on_delete=models.PROTECT)
    order_stop_day = models.DateField(verbose_name='利用停止日', null=True, blank=True)
    login_stop_day = models.DateField(verbose_name='ログイン停止日', null=True, blank=True)
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '利用停止予約'


class ImportUnit(models.Model):
    document_file = models.FileField(upload_to='upload/unit_import', storage=fs, verbose_name='ファイル名')
    updated_at = models.DateTimeField(verbose_name='更新日', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'インポート_施設登録'


class TaxMaster(models.Model):
    """
    税率マスタ。連携先のシステムと情報を合わせること。
    """
    name = models.CharField(verbose_name='税設定_名称', max_length=10)
    code = models.IntegerField(verbose_name='税率コード')
    rate = models.IntegerField(verbose_name='税率')
    enable_day = models.DateField(verbose_name='適用開始日')

    class Meta:
        verbose_name = verbose_name_plural = '税率マスタ'

    def __str__(self):
        return self.name


class TaxSetting(models.Model):
    """
    税率設定。業務委託施設、そうでない施設の2レコードの運用。
    """
    name = models.CharField(verbose_name='税設定_名称', max_length=10)
    is_subcontracting = models.BooleanField(verbose_name='業務委託有無', unique=True)
    rate = models.ForeignKey(TaxMaster, verbose_name='税率', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '税率設定'


class TaxEverydaySellingSetting(models.Model):
    """
    販売固定商品税率設定。
    """
    product_code = models.CharField(verbose_name='商品コード', max_length=50)
    rate = models.ForeignKey(TaxMaster, verbose_name='税率', on_delete=models.PROTECT)

    class Meta:
        verbose_name = verbose_name_plural = '販売固定商品税率設定'


class UserCreationInput(models.Model):
    """
    施設追加入力情報
    """
    import_file = models.ForeignKey(ImportUnit, verbose_name='アップロードファイル', on_delete=models.CASCADE)
    company_name = models.CharField(verbose_name='会社名', max_length=100)
    facility_name = models.CharField(verbose_name='施設名', max_length=100)
    enable_start_day = models.DateField(verbose_name='開始日')
    e_mail = models.EmailField(verbose_name='メールアドレス', blank=True, null=True)
    dry_cold_type = models.CharField(verbose_name='乾燥冷凍区分', max_length=10)
    adjust_saturday = models.IntegerField(verbose_name='土曜日調整日数', blank=True, null=True)
    adjust_sunday = models.IntegerField(verbose_name='日曜日調整日数', blank=True, null=True)
    adjust_holyday = models.IntegerField(verbose_name='祝日調整日数', blank=True, null=True)
    has_adjust_friday = models.BooleanField(verbose_name='金曜調整有無')
    is_reduced = models.BooleanField(verbose_name='業務委託')

    class Meta:
        verbose_name = verbose_name_plural = '施設追加入力情報'


class UserCreationMenuInput(models.Model):
    """
    施設追加献立種類入力情報。本情報のない献立種類=契約なしとする。
    """
    user_creation = models.ForeignKey(UserCreationInput, verbose_name='施設追加情報', on_delete=models.CASCADE)
    menu_name = models.CharField(verbose_name='献立種類名称', max_length=10)

    class Meta:
        verbose_name = verbose_name_plural = '施設追加献立種類入力情報'


class UserCreationMealInput(models.Model):
    """
    施設追加食事区分情報。最低1件以上ある想定
    """
    user_creation = models.ForeignKey(UserCreationInput, verbose_name='施設追加情報', on_delete=models.CASCADE)
    basic_price = models.IntegerField(verbose_name='基本食価格', blank=True, null=True)
    enge_price = models.IntegerField(verbose_name='嚥下食価格', blank=True, null=True)
    has_soup = models.BooleanField(verbose_name='汁オプション_汁')
    has_filling = models.BooleanField(verbose_name='汁オプション_具')

    class Meta:
        verbose_name = verbose_name_plural = '施設追加食事区分入力情報'


class UserCreationUnitInput(models.Model):
    """
    施設追加ユニット情報。最低1件以上ある想定
    """
    user_creation = models.ForeignKey(UserCreationInput, verbose_name='施設追加情報', on_delete=models.CASCADE)
    unit_name = models.CharField(verbose_name='ユニット名称', max_length=100)
    short_name = models.CharField(verbose_name='省略名', max_length=10)

    class Meta:
        verbose_name = verbose_name_plural = '施設追加ユニット入力情報'


class UserCreationAllergenInput(models.Model):
    """
    施設追加食事区分アレルギー情報。最低1件以上ある想定
    """
    user_creation = models.ForeignKey(UserCreationInput, verbose_name='施設追加情報', on_delete=models.CASCADE)
    allergen_name = models.CharField(verbose_name='アレルギー名称', max_length=100)

    class Meta:
        verbose_name = verbose_name_plural = '施設追加アレルギー入力情報'


class UserCreationDefaultOrdersInput(models.Model):
    """
    施設追加基本食数情報。最低1件以上ある想定
    """
    user_creation = models.ForeignKey(UserCreationInput, verbose_name='施設追加情報', on_delete=models.CASCADE,
                                      related_name='default_orders')
    meal_name = models.CharField(verbose_name='食事区分名', max_length=100)
    menu_name = models.CharField(verbose_name='献立種類名', max_length=100)
    quantity = models.IntegerField(verbose_name='基本食数', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '施設追加アレルギー入力情報'


class MixRiceDay(models.Model):
    """
    混ぜご飯が発生した日とその種類を管理する。
    最新発注数取得APIで使用する。
    """
    eating_day = models.DateField(verbose_name='喫食日')
    mix_rice_name = models.CharField(verbose_name='混ぜご飯名', max_length=50)

    class Meta:
        verbose_name = verbose_name_plural = '混ぜご飯発生日'


class OutputSampleP7(models.Model):
    """
    P7に出力済みのサンプルメニューを記録する
    """
    cooking_day = models.DateField(verbose_name='出力対象調理日')
    eating_day = models.DateField(verbose_name='喫食日')
    meal_name = models.CharField(verbose_name="食事区分", max_length=100)

    class Meta:
        verbose_name = verbose_name_plural = 'サンプルメニューP7出力'


class GosuLogging(models.Model):
    """
    合数計算を記録する
    """
    eating_day = models.DateField(verbose_name='出力対象喫食日')

    needle_quantity = models.FloatField(verbose_name='針刺し用数量', default=0.0)
    needle_orders = models.IntegerField(verbose_name='針刺し用食数', default=0)
    soft_orders = models.IntegerField(verbose_name='ソフト食数', default=0)
    jelly_orders = models.IntegerField(verbose_name='ゼリー食数', default=0)
    mixer_orders = models.IntegerField(verbose_name='ミキサー食数', default=0)

    updated_at = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '合数計算ログ'


class UnitGosuLogging(models.Model):
    """
    ユニット別合数計算を記録する
    """
    gosu_logging = models.ForeignKey(GosuLogging, verbose_name='計算ログ', on_delete=models.PROTECT)
    unit = models.ForeignKey(UnitMaster, verbose_name='ユニット', on_delete=models.PROTECT)
    status = models.CharField(verbose_name="状態", max_length=16, default='', blank=True, null=True)
    quantity = models.FloatField(verbose_name="合数", default=0.0)

    updated_at = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = 'ユニット別合数計算ログ'
