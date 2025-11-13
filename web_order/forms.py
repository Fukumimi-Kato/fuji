import datetime as dt
from dateutil.relativedelta import relativedelta

from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator

from accounts.models import User
from .date_management import SalesDayUtil
from .models import Order, OrderRice, Communication, PaperDocuments, InvoiceFiles, ReservedMealDisplay
from .models import ImportMenuName, ImportMonthlyMenu, FoodPhoto, ZippedDocumentFiles, ImportMonthlyReport
from .models import UnitMaster, DocumentMaster, DocGroupMaster, EngeFoodDirection, ImportP7SourceFile
from .models import MealDisplay, MenuDisplay, AllergenDisplay, MenuMaster, NewUnitPrice
from .models import Chat, PickingResult, PickingNotice, ReservedStop, ImportUnit, EverydaySelling, UserOption
from .models import HolidayList, NewYearDaySetting, AllergenMaster, AllergenDisplay, InvoiceException
from .models import MixRicePackageMaster, GenericSetoutDirection, DocumentDirDisplay, TaxMaster, CommonAllergen
from .models import AggMeasureSoupMaster, AggMeasureMixRiceMaster, RawPlatePackageMaster, SetoutDuration

class DateInput2(forms.DateInput):
    input_type = 'date'


class OrderForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        change_date = kwargs.pop('change_limit_day', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        if change_date:
            instance = kwargs.get('instance', None)
            if instance:
                if instance.eating_day < change_date:
                    field.widget.attrs['readonly'] = 'readonly'

        self.fields['quantity'].widget.attrs['onkeydown'] = "return event.keyCode !== 69"

        # 元日の入力制限対応
        instance = kwargs.get('instance', None)
        if instance:
            if instance.eating_day.month == 1 and instance.eating_day.day == 1:
                field.widget.attrs['readonly'] = 'readonly'
            if ReservedStop.objects.filter(unit_name=instance.unit_name, order_stop_day__lte=instance.eating_day).exists():
                field.widget.attrs['readonly'] = 'readonly'

    class Meta:
        model = Order
        fields = ('quantity',)  # 食数入力欄のみ週間注文フォームで並べるため
        # fields = ('eating_day', 'user', 'unit_name', 'meal_name', 'menu_name', 'allergen', 'quantity',)


class OrderNewYearForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        change_date = kwargs.pop('change_limit_day', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = Order
        fields = ('quantity',)  # 食数入力欄のみ週間注文フォームで並べるため
        # fields = ('eating_day', 'user', 'unit_name', 'meal_name', 'menu_name', 'allergen', 'quantity',)


class OrderMaintenanceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = Order
        fields = ('quantity',)  # 食数入力欄のみ週間注文フォームで並べるため


class OrderMaintenanceSearchForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['unit_name'].choices = \
            lambda: [(u.id, u.unit_name) for u in UnitMaster.objects.filter(is_active=True).order_by('unit_number')]

    class Meta:
        model = Order
        fields = ('unit_name', 'eating_day')
        widgets = {
            'eating_day': DateInput2(),
        }


class OrderListForm(forms.Form):

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻

    in_date = forms.DateField(label='喫食日',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class OrderListSalesForm(forms.Form):

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻

    in_date = forms.DateField(label='売上日(From)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    out_date = forms.DateField(label='売上日(To)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class OrderUnitForm(forms.Form):

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻

    in_date = forms.DateField(label='売上日(From)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    out_date = forms.DateField(label='売上日(To)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class OrderListCsvForm(forms.Form):

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻

    in_date = forms.DateField(label='売上日(From)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    out_date = forms.DateField(label='売上日(To)',
                              required=False,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class OrderChangeForm(forms.ModelForm):

    def __init__(self, *args, user, **kwargs):
        super(OrderChangeForm, self).__init__(*args, **kwargs)

        self.fields['unit_name'].widget.attrs['disabled'] = True

        self.fields['eating_day'].widget.attrs['readonly'] = True

        self.fields['meal_name'].widget.attrs['disabled'] = True
        self.fields['menu_name'].widget.attrs['disabled'] = True

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        # このセクション無くてもいいかも
        self.fields['unit_name'].choices = \
            lambda: [(u.id, u.unit_name) for u in UnitMaster.objects.filter(username=user)]
        self.fields['meal_name'].choices = \
            lambda: [(ml.meal_name_id, ml.meal_name) for ml in MealDisplay.objects.filter(username=user)]
        self.fields['menu_name'].choices = \
            lambda: [(mu.menu_name_id, mu.menu_name) for mu in MenuDisplay.objects.filter(username=user).exclude(menu_name__menu_name='薄味')]

    class Meta:
        model = Order
        fields = ('unit_name', 'eating_day', 'meal_name', 'menu_name', 'quantity',)

    def clean_quantity(self):
        new_val = self.cleaned_data['quantity']
        if new_val > self.instance.quantity + 10:
            raise forms.ValidationError("食材発注の都合上、恐れ入りますが10食以上増やす場合は別途ご連絡をお願いいたします")
        return new_val


class OrderRiceForm(forms.ModelForm):

    def __init__(self, *args, user, **kwargs):
        # self.user = kwargs.pop('user', None)  # このような「引数:user」の取り出し方もあるっぽい
        from_date = kwargs.pop('from_date', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        # 日付の下限の設定
        if from_date:
            self.from_date = from_date
            self.fields['eating_day'].widget.attrs['min'] = dt.datetime.strftime(from_date, "%Y-%m-%d")

        self.fields['unit_name'].choices = \
            lambda: [('', '選択してください')] + [(u.id, u.unit_name) for u in UnitMaster.objects.filter(username=user)]

        instance = kwargs.get('instance', None)
        if instance:
            if instance.eating_day < from_date:
                self.fields['eating_day'].widget.attrs['readonly'] = 'readonly'
                self.fields['unit_name'].widget.choices = [(instance.unit_name.id, instance.unit_name.unit_name)]
                self.fields['quantity'].widget.attrs['readonly'] = 'readonly'

    class Meta:
        model = OrderRice
        fields = '__all__'
        widgets = {
            'eating_day': DateInput2(),
        }


cache = {}
class AllergenForm(forms.ModelForm):

    def _get_menu(self, from_date, user):
        if from_date and (from_date >= dt.datetime.strptime(settings.BASIC_PLATE_ENABLE_DATE, '%Y-%m-%d').date()):
            choices = [(mu.menu_name_id, mu.menu_name)
                                  for mu in MenuDisplay.objects.filter(username=user).exclude(menu_name__menu_name='薄味')]
            for i, c in enumerate(choices):
                if c[1].menu_name == '常食':
                    c[1].menu_name = '基本食'
            return [('', '選択してください')] + choices
        else:
            return [('', '選択してください')] + [(mu.menu_name_id, mu.menu_name)
                                  for mu in MenuDisplay.objects.filter(username=user).exclude(menu_name__menu_name='薄味')]

    def __init__(self, *args, user, **kwargs):
        # self.user = kwargs.pop('user', None)  # このような「引数:user」の取り出し方もあるっぽい
        from_date = kwargs.pop('from_date', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        # 日付の下限の設定
        if from_date:
            self.from_date = from_date
            self.fields['eating_day'].widget.attrs['min'] = dt.datetime.strftime(from_date, "%Y-%m-%d")

        self.fields['unit_name'].choices = \
            lambda: [('', '選択してください')] + [(u.id, u.unit_name)
                                          for u in UnitMaster.objects.filter(username=user)]
        self.fields['meal_name'].choices = \
            lambda: [('', '選択してください')] + [(ml.meal_name_id, ml.meal_name)
                                          for ml in MealDisplay.objects.filter(username=user)]
        self.fields['menu_name'].choices = self._get_menu(from_date, user)
        self.fields['allergen'].choices = \
            lambda: [('', '選択してください')] + [(a.allergen_name_id, a.allergen_name)
                                          for a in AllergenDisplay.objects.filter(username=user)]
        '''
        if 'unit_name' not in cache:
            choices = [('', '選択してください')] + [(obj.id, obj.unit_name) 
                                            for obj in UnitMaster.objects.filter(username=user)]
            cache['unit_name'] = choices
        self.fields['unit_name'].choices = cache['unit_name']

        if 'meal_name' not in cache:
            choices = [('', '選択してください')] + [(obj.meal_name_id, obj.meal_name.meal_name) 
                                            for obj in MealDisplay.objects.filter(username=user)]
            cache['meal_name'] = choices
        self.fields['meal_name'].choices = cache['meal_name']

        if 'menu_name' not in cache:
            choices = [('', '選択してください')] + [(obj.menu_name_id, obj.menu_name) 
                                            for obj in MenuDisplay.objects.filter(username=user)]
            cache['menu_name'] = choices
        self.fields['menu_name'].choices = cache['menu_name']

        if 'allergen' not in cache:
            choices = [('', '選択してください')] + [(obj.allergen_name_id, obj.allergen_name) 
                                            for obj in AllergenDisplay.objects.filter(username=user)]
            cache['allergen'] = choices
        self.fields['allergen'].choices = cache['allergen']
        '''
    class Meta:
        model = Order
        fields = ('eating_day', 'unit_name', 'meal_name', 'menu_name', 'allergen', 'quantity',)
        # fields = '__all__'
        widgets = {
            'eating_day': DateInput2(),
        }

    def clean_eating_day(self):
        date = self.cleaned_data.get('eating_day')
        if not date:
            # 一旦ここはエラー回避のため通す
            return date
        if date < self.from_date:
            raise forms.ValidationError("喫食日の指定が不正です。")
        elif (date.month == 1) and (date.day == 1):
            self.add_error(None, '元日の注文は専用画面からのみ行えます。')
            raise forms.ValidationError("元日の注文は専用画面からのみ行えます。")
        return date

    def clean(self):
        date = self.cleaned_data.get('eating_day', None)
        menu = self.cleaned_data.get('menu_name', None)
        unit_name = self.cleaned_data.get('unit_name', None)
        if (not date) or (not menu) or (not unit_name):
            # 一旦ここはエラー回避のため通す
            return self.cleaned_data
        t_date = dt.datetime(2023, 1, 31).date()
        if (date >= t_date) and (menu.menu_name == '薄味'):
            raise forms.ValidationError("1月31日以降、薄味は廃止となります。常食を選択してください。")
        if ReservedStop.objects.filter(unit_name=unit_name, order_stop_day__lte=date).exists():
            raise forms.ValidationError("対象の喫食日は、注文受付停止中です。")
        return self.cleaned_data

class AllergenNewYearForm(forms.ModelForm):

    def __init__(self, *args, user, **kwargs):
        # self.user = kwargs.pop('user', None)  # このような「引数:user」の取り出し方もあるっぽい
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['unit_name'].choices = \
            lambda: [('', '選択してください')] + [(u.id, u.unit_name)
                                          for u in UnitMaster.objects.filter(username=user)]
        self.fields['meal_name'].choices = \
            lambda: [('', '選択してください')] + [(ml.meal_name_id, ml.meal_name)
                                          for ml in MealDisplay.objects.filter(username=user)]
        self.fields['menu_name'].choices = \
            lambda: [('', '選択してください')] + [(mu.menu_name_id, mu.menu_name)
                                          for mu in MenuDisplay.objects.filter(username=user).exclude(menu_name__menu_name='薄味')]

        self.fields['allergen'].choices = \
            lambda: [('', '選択してください')] + [(a.allergen_name_id, a.allergen_name)
                                          for a in AllergenDisplay.objects.filter(username=user)]

    class Meta:
        model = Order
        fields = ('unit_name', 'meal_name', 'menu_name', 'allergen', 'quantity',)


class PostCreateForm(forms.ModelForm):

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        if 'unit_name' not in cache:
            iterator = forms.models.ModelChoiceIterator(self.fields['unit_name'])
            choices = [iterator.choice(obj) for obj in UnitMaster.objects.filter(username=user)]
            cache['unit_name'] = choices
        self.fields['unit_name'].choices = cache['unit_name']

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = Order
        fields = '__all__'


class CommunicationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['document_file'].widget.attrs['accept'] = '.pdf,.docx,.xlsx,.pptx'

    class Meta:
        model = Communication
        fields = ('title', 'message', 'group', 'document_file')


class PaperDocumentsForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['document_kind'].choices = \
            lambda: [('', '---------')] + [(dm.id, dm.document_kind) for dm
                                           in DocumentMaster.objects.all().order_by('seq_order')]
        self.fields['document_group'].choices = \
            lambda: [('', '---------')] + [(dg.id, dg.group_name) for dg
                                           in DocGroupMaster.objects.all().order_by('seq_order')]

    class Meta:
        model = PaperDocuments
        fields = '__all__'


class DocumentCheckForm(forms.ModelForm):
    usr = forms.fields.ChoiceField(
        label='施設',
        choices=lambda: [('', '---------')] + [(u.username, u.facility_name) for u
                                               in User.objects.filter(is_staff=False, is_active=True).exclude(
                username__range=['80001', '89999']).exclude(username__range=['910003', '910089']).exclude(
                username__range=['910095', '929999']).order_by(
                'username')],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = User
        fields = []


class DocumentsUploadForm(forms.ModelForm):

    document_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'accept': '.zip'}),
    )

    class Meta:
        model = ZippedDocumentFiles
        fields = ('year', 'month', 'document_file',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class InvoiceFilesForm(forms.ModelForm):

    document_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True}),
    )

    class Meta:
        model = InvoiceFiles
        fields = ('document_file',)


class ImportMenuNameForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = ImportMenuName
        fields = ('document_file',)


class ConvertCookingDirectionForm(forms.ModelForm):
    COOKING_DIRECTION_CHOICES = (
        ('normal', '通常'),
        ('filter', '常食・薄味別'),
    )

    type = forms.fields.ChoiceField(
        label='種類',
        choices=COOKING_DIRECTION_CHOICES,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['document_file'].widget.attrs['accept'] = '.xlsx'
        self.fields['document_file'].validators = [FileExtensionValidator(['xlsx', ])]

    class Meta:
        model = ImportMenuName
        fields = ('document_file',)


class CreateMeasureTableForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = ImportMenuName
        fields = ('document_file',)


class RegisterMonthlyMenuForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = ImportMonthlyMenu
        fields = ('document_file',)


class FoodPhotoForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = FoodPhoto
        fields = ('hot_cool', 'direction', 'photo_file',)
        # fields = '__all__'


class FoodDirectionForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = FoodPhoto
        fields = ('direction', 'direction2', 'photo_file',)
        # fields = '__all__'


class EngeFoodDirectionForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = EngeFoodDirection
        fields = ('soft_direction', 'soft_direction2', 'soft_direction3', 'soft_direction4', 'soft_direction5',
                  'mixer_direction', 'mixer_direction2', 'mixer_direction3', 'mixer_direction4', 'mixer_direction5',
                  'jelly_direction', 'jelly_direction2', 'jelly_direction3', 'jelly_direction4', 'jelly_direction5')
        # fields = '__all__'


class ExecForm(forms.Form):

    in_date = forms.DateField(label='喫食日',
                              required=True,
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ExecMonthForm(forms.Form):

    in_date = forms.DateField(label='対象月',
                              required=True,
                              widget=forms.DateInput(attrs={"type": "month"}),
                              input_formats=['%Y-%m'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


# 売価計算表出力のフォーム
class ExecCalculateSalesPriceForm(forms.Form):

    in_date = forms.DateField(label='対象月',
                              required=True,
                              widget=forms.DateInput(attrs={"type": "month"}),
                              input_formats=['%Y-%m'])
    in_transport_price = forms.IntegerField(label='配送料請求合計額(税別)', required=True, validators=[MinValueValidator(1),])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


# 書き起こし票出力のフォーム
class ExecOutputKakiokoshiForm(forms.Form):

    in_date = forms.DateField(label='製造日',
                              required=True,
                              widget=DateInput2())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ChatForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = Chat
        fields = ('message',)

        widgets = {
            'message': forms.Textarea(attrs={'rows': 3}),
        }


class HolidayListForm(forms.ModelForm):

    def clean_end_date(self):
        s_day = self.cleaned_data['start_date']
        e_day = self.cleaned_data['end_date']
        if s_day > e_day:
            raise forms.ValidationError("終了日は開始日以降にしてください")
        return e_day

class AggrigationSearchForm(forms.Form):

    date_time_now = dt.datetime.now().date()  # 現在の日時と時刻
    MEAL_CHOICES = (
        ('朝食', '朝食'),
        ('昼食', '昼食'),
        ('夕食', '夕食'),
    )

    start_date = forms.DateField(label='喫食日(From)',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)
    start_meal = forms.fields.ChoiceField(
        label='食事区分(From)',
        choices=MEAL_CHOICES,
        required=True,
        initial='朝食',
    )
    end_date = forms.DateField(label='喫食日(To)',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'],
                              initial=date_time_now)
    end_meal = forms.fields.ChoiceField(
        label='食事区分(To)',
        choices=MEAL_CHOICES,
        required=True,
        initial='夕食',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_end_date(self):
        start_date = self.cleaned_data['start_date']
        end_date = self.cleaned_data['end_date']
        if start_date > end_date:
            raise forms.ValidationError("終了日は開始日以降にしてください")
        return end_date


class HeatingProcessingForm(forms.Form):
    cokking_date = forms.DateField(label='調理日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ImportMonthlyReportForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = ImportMonthlyReport
        fields = ('document_file', )
        # fields = '__all__'


class ImportP7FileForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = ImportP7SourceFile
        fields = ('document_file', )


class OutputP7FileForm(forms.Form):
    cooking_date = forms.DateField(label='製造日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class SearchSalesPriceForm(forms.Form):
    from_date = forms.DateField(label='開始日',
                              widget=forms.DateInput(attrs={"type": "date", "class": "form-control"},),
                              input_formats=['%Y-%m-%d'], required=False)
    to_date = forms.DateField(label='終了日',
                              widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
                              input_formats=['%Y-%m-%d'], required=False)
    from_sales = forms.IntegerField(label='売上(最小値)', required=False)
    to_sales = forms.IntegerField(label='売上(最大値)', required=False)

    display_item_group = forms.MultipleChoiceField(label='抽出対象',
                                                    widget=forms.CheckboxSelectMultiple(),
                                                   choices=[('1', '基本食・個食・フリーズ'), ('2', '嚥下')],
                                                   required=False, initial=['1', '2'])
    display_meal_group = forms.MultipleChoiceField(label='食事区分',
                                                   widget=forms.CheckboxSelectMultiple(),
                                                   choices=[('1', '朝食'), ('2', '昼食'), ('3', '夕食'), ('4', '合計')],
                                                   required=False, initial=['1', '2', '3', '4'])
    display_output_group = forms.MultipleChoiceField(label='出力項目',
                                                   widget=forms.CheckboxSelectMultiple(),
                                                   choices=[('1', '食数'), ('2', '売上'), ('3', '1食あたりの平均売価(配送料込み)'), ('4', '1食あたりの平均売価(配送料除く)')],
                                                   required=False, initial=['1', '2', '3', '4'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_sales'].widget.attrs["class"] = "form-control"
        self.fields['to_sales'].widget.attrs["class"] = "form-control"

    def clean_to_date(self):
        start_date = self.cleaned_data['from_date']
        end_date = self.cleaned_data['to_date']
        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("終了日は開始日以降にしてください")
            return end_date
        else:
            return end_date


class PickingResultFileForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = PickingResult
        fields = ('document_file',)


class OutputSealCsvForm(forms.Form):
    cooking_date = forms.DateField(label='製造日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])
    meal = forms.fields.ChoiceField(
        label='食事区分',
        choices=lambda: [('01', '朝食'), ('02', '昼食'), ('03', '夕食')],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class DirectionPickingForm(forms.Form):
    cooking_date = forms.DateField(label='製造日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])
    chiller_1_unit_from = forms.IntegerField(label='チラー1対象施設番号')
    chiller_1_unit_to = forms.IntegerField(label='チラー1対象施設番号')
    chiller_2_unit_from = forms.IntegerField(label='チラー2対象施設番号')
    chiller_2_unit_to = forms.IntegerField(label='チラー2対象施設番号')
    chiller_3_unit_from = forms.IntegerField(label='チラー3対象施設番号')
    chiller_3_unit_to = forms.IntegerField(label='チラー3対象施設番号')
    chiller_4_unit_from = forms.IntegerField(label='チラー4対象施設番号')
    chiller_4_unit_to = forms.IntegerField(label='チラー4対象施設番号')
    output_type = forms.fields.ChoiceField(
        label='中袋種類',
        choices=lambda: [('00', '全て'), ('011', '基本食(チラー1)'), ('012', '基本食(チラー2)'), ('013', '基本食(チラー3)'), ('014', '基本食(チラー4)'), ('02', '嚥下食'), ('03', '汁・汁具'), ('04', '原体')],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_chiller_1_unit_to(self):
        start_no = self.cleaned_data['chiller_1_unit_from']
        end_no = self.cleaned_data['chiller_1_unit_to']
        if start_no and end_no:
            if start_no > end_no:
                raise forms.ValidationError("施設番号の範囲指定が不正です。")
            return end_no
        else:
            return end_no

    def clean_chiller_2_unit_to(self):
        start_no = self.cleaned_data['chiller_2_unit_from']
        end_no = self.cleaned_data['chiller_2_unit_to']
        if start_no and end_no:
            if start_no > end_no:
                raise forms.ValidationError("施設番号の範囲指定が不正です。")
            return end_no
        else:
            return end_no

    def clean_chiller_3_unit_to(self):
        start_no = self.cleaned_data['chiller_3_unit_from']
        end_no = self.cleaned_data['chiller_3_unit_to']
        if start_no and end_no:
            if start_no > end_no:
                raise forms.ValidationError("施設番号の範囲指定が不正です。")
            return end_no
        else:
            return end_no

    def clean_chiller_4_unit_to(self):
        start_no = self.cleaned_data['chiller_4_unit_from']
        end_no = self.cleaned_data['chiller_4_unit_to']
        if start_no and end_no:
            if start_no > end_no:
                raise forms.ValidationError("施設番号の範囲指定が不正です。")
            return end_no
        else:
            return end_no

    def clean(self):
        cleand_data = super().clean()
        chiller_1_from = cleand_data.get('chiller_1_unit_from')
        chiller_1_to = cleand_data.get('chiller_1_unit_to')
        chiller_2_from = cleand_data.get('chiller_2_unit_from')
        chiller_2_to = cleand_data.get('chiller_2_unit_to')
        chiller_3_from = cleand_data.get('chiller_3_unit_from')
        chiller_3_to = cleand_data.get('chiller_3_unit_to')
        chiller_4_from = cleand_data.get('chiller_4_unit_from')
        chiller_4_to = cleand_data.get('chiller_4_unit_to')

        if chiller_1_from and chiller_1_to and chiller_2_from and chiller_2_to and chiller_3_from and chiller_3_to \
            and chiller_4_from and chiller_4_to:

            range1 = range(chiller_1_from, chiller_1_to + 1)
            range2 = range(chiller_2_from, chiller_2_to + 1)
            range3 = range(chiller_3_from, chiller_3_to + 1)
            range4 = range(chiller_4_from, chiller_4_to + 1)

            min_value = min([range1[0], range2[0], range3[0], range4[0]])
            max_value = max([range1[-1], range2[-1], range3[-1], range4[-1]])
            for number in range(min_value, max_value + 1):
                is_include_range1 = number in range1
                is_include_range2 = number in range2
                is_include_range3 = number in range3
                is_include_range4 = number in range4

                count = 0
                if is_include_range1:
                    count += 1
                if is_include_range2:
                    count += 1
                if is_include_range3:
                    count += 1
                if is_include_range4:
                    count += 1

                if count > 1:
                    raise forms.ValidationError("施設番号が重複しています。")
            return self.cleaned_data


class OutputPouchDesignForm(forms.Form):
    cooking_date = forms.DateField(label='製造日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class PickingNoticeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    class Meta:
        model = PickingNotice
        fields = '__all__'
        widgets = {
            'note': forms.Textarea(
                    attrs={
                        'placeholder': '内容を2,048文字以内で入力してください。',
                        'rows': 5
                    }
            )
        }


class SearchSalesInvoiceForm(forms.Form):
    unit_name = forms.fields.ChoiceField(label='ユニット', required=False)
    from_date = forms.DateField(label='開始日',
                              widget=forms.DateInput(attrs={"type": "date", "class": "form-control"},),
                              input_formats=['%Y-%m-%d'], required=False)
    to_date = forms.DateField(label='終了日',
                              widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
                              input_formats=['%Y-%m-%d'], required=False)
    from_sales = forms.IntegerField(label='売上(最小値)', required=False)
    to_sales = forms.IntegerField(label='売上(最大値)', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_sales'].widget.attrs["class"] = "form-control"
        self.fields['to_sales'].widget.attrs["class"] = "form-control"
        self.fields['unit_name'].widget.attrs["class"] = "form-control"
        self.fields['unit_name'].choices = \
            lambda: [('', '---------')] + \
                    [(u.id, u.unit_name) for u in UnitMaster.objects.filter(is_active=True).order_by('unit_code', 'calc_name')]

    def clean_to_date(self):
        start_date = self.cleaned_data['from_date']
        end_date = self.cleaned_data['to_date']
        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("終了日は開始日以降にしてください")
            return end_date
        else:
            return end_date


class DesignSealCsvForm(forms.Form):
    cooking_date = forms.DateField(label='製造日',
                              widget=forms.DateInput(attrs={"type": "date"}),
                              input_formats=['%Y-%m-%d'])
    output_type = forms.fields.ChoiceField(
        label='シール種類',
        choices=lambda: [('01', '基本食'), ('02', 'ソフト'), ('03', 'ゼリー'), ('04', 'ミキサー'), ('05', 'アレルギー')],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class UnitSearchForm(forms.Form):
    unit_name = forms.fields.ChoiceField(
        label='停止対象ユニット',
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['unit_name'].choices = \
            lambda: [('', '---------')] + [(u.id, u.unit_name) for u in UnitMaster.objects.filter(is_active=True).order_by('unit_code')]


class UnitImportForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['document_file'].widget.attrs['multiple'] = True

    class Meta:
        model = ImportUnit
        fields = ('document_file',)


# region マスタメンテ画面用のForm
class EverydaySellingForm(forms.ModelForm):
    """
    販売固定商品Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['unit_name'].choices = \
            lambda: [('', '---------')] + [
                (u.id, u.unit_name) for u in UnitMaster.objects.filter(
                    is_active=True).order_by('unit_code')]

    class Meta:
        model = EverydaySelling
        fields = ('unit_name', 'product_code', 'product_name', 'quantity', 'price', 'enable',)
        widgets = {
            'enable': DateInput2(),
        }


class NewUnitPriceForm(forms.Form):
    """
    単価情報Form
    """
    enable_day = forms.DateField(label='変更価格適用(売上計上日)',
                                 widget=forms.DateInput(attrs={"type": "date"}), input_formats=['%Y-%m-%d'])
    basic_breakfast_price = forms.IntegerField(label='朝食単価', min_value=0, required=False)
    basic_lunch_price = forms.IntegerField(label='昼食単価', min_value=0, required=False)
    basic_dinner_price = forms.IntegerField(label='夕食単価', min_value=0, required=False)

    enge_breakfast_price = forms.IntegerField(label='朝食単価', min_value=0, required=False)
    enge_lunch_price = forms.IntegerField(label='昼食単価', min_value=0, required=False)
    enge_dinner_price = forms.IntegerField(label='夕食単価', min_value=0, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        today = dt.datetime.today()
        self.fields['enable_day'].widget.attrs['min'] = today.strftime('%Y-%m-%d')


        """
        dict = args[1]
        if not dict.get('is_basic_enable', False):
            self.fields['basic_breakfast_price'].widget.attrs['readonly'] = 'readonly'
            self.fields['basic_lunch_price'].widget.attrs['readonly'] = 'readonly'
            self.fields['basic_dinner_price'].widget.attrs['readonly'] = 'readonly'
        if not dict.get('is_enge_enable', False):
            self.fields['enge_breakfast_price'].widget.attrs['readonly'] = 'readonly'
            self.fields['enge_lunch_price'].widget.attrs['readonly'] = 'readonly'
            self.fields['enge_dinner_price'].widget.attrs['readonly'] = 'readonly'
        """


    def clean_enable_day(self):
        enable_day = self.cleaned_data['enable_day']
        today = dt.datetime.today().date()
        if enable_day < today:
            raise forms.ValidationError('変更価格適用(売上計上日)には本日以降を指定してください。')

        return enable_day


class PreorderSettingForm(forms.ModelForm):
    """
    仮注文特別対応Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # unlock_limitationはform-controlを付けると、見えなくなってしまうので設定しない
        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['unlock_day'].widget.attrs['class'] = 'form-control'

        self.fields['unlock_limitation'].widget.attrs['value'] = '1'

        # プルダウンの設定
        self.fields['username'].choices = \
            lambda: [('', '---------')] + [
                (u.id, u.facility_name) for u in User.objects.filter(
                    is_staff=False, is_active=True).order_by('username')]

    class Meta:
        model = UserOption
        fields = '__all__'
        widgets = {
            'unlock_day': DateInput2(),
        }


class OrderRiceMasterForm(forms.ModelForm):
    """
    合数マスタ登録Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['unit_name'].choices = \
            lambda: [('', '選択してください')] + [(u.id, u.unit_name) for u in UnitMaster.objects.filter(is_active=True).order_by('unit_number')]

        today = dt.datetime.today().date()
        adjusted_day = today + relativedelta(days=SalesDayUtil.get_adjust_days_settings(today)+1)
        self.fields['eating_day'].widget.attrs['min'] = adjusted_day.strftime('%Y-%m-%d')

    class Meta:
        model = OrderRice
        fields = '__all__'
        widgets = {
            'eating_day': DateInput2(),
        }

    def _validate(self, unit: UnitMaster, eating_day, quantity):
        error_list = []
        if OrderRice.objects.filter(unit_name=unit, eating_day=eating_day).exists():
            error_list.append(forms.ValidationError(forms.ValidationError("すでに対象の注文は登録済みです。")))

        return error_list

    def clean(self):
        cleaned_data = super().clean()
        unit = cleaned_data.get('unit_name')
        eating_day = cleaned_data.get('eating_day')
        quantity = cleaned_data.get('quantity')

        # バリデーション実施
        error_list = self._validate(unit, eating_day, quantity)
        if error_list:
            raise forms.ValidationError(error_list)

        return cleaned_data


class OrderRiceMasterUpdateForm(OrderRiceMasterForm):
    """
    合数マスタ更新Form
    """

    def _validate(self, unit: UnitMaster, eating_day, quantity):
        error_list = []


        if quantity:
            if OrderRice.objects.filter(unit_name=unit, eating_day=eating_day).exclude(id=self.instance.id).exists():
                error_list.append(forms.ValidationError(forms.ValidationError("すでに対象の注文は登録済みです。")))

        return error_list


class LongHolidayForm(forms.ModelForm):
    """
    長期休暇Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = HolidayList
        fields = '__all__'
        widgets = {
            'start_date': DateInput2(),
            'end_date': DateInput2(),
            'limit_day': DateInput2(),
        }


class NewYearDaySettingForm(forms.ModelForm):
    """
    元旦注文設定Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = NewYearDaySetting
        fields = '__all__'
        widgets = {
            'enable_date_from': DateInput2(),
            'enable_date_to': DateInput2(),
        }


class AllergenMasterForm(forms.ModelForm):
    """
    アレルギーマスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            # チェックボックスのwidgetにform-contorolを設定すると、表示がつぶれてしまうため回避
            if key != 'is_common':
                field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = AllergenMaster
        fields = ('allergen_name', 'seq_order', 'is_common', 'kana_name', )


class AllergenMasterCreateForm(forms.ModelForm):
    """
    アレルギーマスタ登録用Form
    """
    display_orders = forms.fields.ChoiceField(
        label='表示順',
        required=True,
    )
    ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']

    def _set_display_order_choice(self, **kwargs):
        self.fields['display_orders'].choices = \
            lambda: [(0, '先頭')] + [(a.id, f'{a.allergen_name}の後') for a in AllergenMaster.objects.all(
                ).exclude(allergen_name__in=self.ignore_allergen_names).order_by('seq_order', '-id')]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            # チェックボックスのwidgetにform-contorolを設定すると、表示がつぶれてしまうため回避
            if key != 'is_common':
                field.widget.attrs['class'] = 'form-control'

        # プルダウンから設定位置を設定できるように対応
        self._set_display_order_choice(**kwargs)

    class Meta:
        model = AllergenMaster
        fields = ('allergen_name', 'is_common', 'kana_name', )


class AllergenMasterUpdateForm(AllergenMasterCreateForm):
    """
    アレルギーマスタ更新用Form
    """
    display_orders = forms.fields.ChoiceField(
        label='表示順',
        required=False,
    )

    def _set_display_order_choice(self, **kwargs):
        # Updateでinstanceが取得できないのはありえないはず
        instance = kwargs.get('instance', None)

        self.fields['display_orders'].choices = \
            lambda: [('', '--変更しない--')] + [('0', '先頭')] + [(a.id, f'{a.allergen_name}の後') for a in AllergenMaster.objects.all(
                ).exclude(allergen_name__in=self.ignore_allergen_names).exclude(id=instance.id).order_by('seq_order', '-id')]


class AllergenSettingForm(forms.ModelForm):
    """
    顧客別_アレルギー設定マスタForm
    """
    ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        # プルダウンの設定
        self.fields['username'].choices = \
            lambda: [('', '---------')] + [
                (u.username, u.facility_name) for u in User.objects.filter(
                    is_staff=False, is_active=True).order_by('username')]
        self.fields['allergen_name'].choices = \
            lambda: [('', '---------')] + [(a.id, a.allergen_name) for a in AllergenMaster.objects.all(
                ).exclude(allergen_name__in=self.ignore_allergen_names).order_by('seq_order', '-id')]

    class Meta:
        model = AllergenDisplay
        fields = '__all__'

    def _validate(self, user: User, cleaned_data):
        allergen = cleaned_data.get('allergen_name')

        error_list = []
        # 既存設定との不整合チェック
        if AllergenDisplay.objects.filter(username=user, allergen_name=allergen).exists():
            error_list.append(forms.ValidationError("対象の設定はすでに存在します。"))

        return error_list

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('username')

        # バリデーション実施
        error_list = self._validate(user, cleaned_data)

        # バリデーションエラー有無を判断
        if error_list:
            raise forms.ValidationError(error_list)

        return cleaned_data


class AllergenSettingUpdateForm(AllergenSettingForm):
    """
    顧客別_アレルギー設定更新マスタForm
    """
    def _validate(self, user: User, cleaned_data):
        allergen = cleaned_data.get('allergen_name')

        error_list = []
        # 施設毎_献立種類設定との不整合チェック
        if AllergenDisplay.objects.filter(username=user, allergen_name=allergen).exclude(self.id).exists():
            error_list.append(forms.ValidationError("対象の設定はすでに存在します。"))

        return error_list


class SalesDaySettingForm(forms.ModelForm):
    """
    施設別_売上日調整日数マスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['unit_name'].widget.attrs['class'] = 'form-control'
        self.fields['ng_saturday'].widget.attrs['class'] = 'form-control'
        self.fields['ng_sunday'].widget.attrs['class'] = 'form-control'
        self.fields['ng_holiday'].widget.attrs['class'] = 'form-control'

        # プルダウンの設定
        self.fields['unit_name'].choices = \
            lambda: [('', '選択してください')] + [
                (u.id, u.unit_name) for u in UnitMaster.objects.filter(is_active=True).order_by('unit_number')]

    class Meta:
        model = InvoiceException
        fields = '__all__'


class MixRicePackageForm(forms.ModelForm):
    """
    混ぜご飯袋サイズマスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = MixRicePackageMaster
        fields = '__all__'


class SetOutDirectionForm(forms.ModelForm):
    """
    献立定型文マスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['direction'].widget.attrs['class'] = 'form-control'
        self.fields['shortening'].widget.attrs['class'] = 'form-control'

    class Meta:
        model = GenericSetoutDirection
        fields = '__all__'


class DocumentFolderForm(forms.ModelForm):
    """
    献立資料フォルダマスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = DocumentDirDisplay
        fields = '__all__'
        widgets = {
            'enable_date': DateInput2(),
        }


class TaxSettingsForm(forms.Form):
    """
    税率設定Form
    """
    subcontracting = forms.fields.ChoiceField(
        label='業務委託施設設定',
        choices=lambda: [(tax.id, f'{tax.name}({tax.rate}%)') for tax in TaxMaster.objects.all().order_by('code')],
        required=True,
    )

    notcontracting = forms.fields.ChoiceField(
        label='業務委託外施設設定',
        choices=lambda: [(tax.id, f'{tax.name}({tax.rate}%)') for tax in TaxMaster.objects.all().order_by('code')],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        # プルダウンの設定
        self.fields['subcontracting'].choices = \
            lambda: [(u.id, u.name) for u in TaxMaster.objects.all().order_by('code')]
        self.fields['notcontracting'].choices = \
            lambda: [(u.id, u.name) for u in TaxMaster.objects.all().order_by('code')]

        #self.fields['subcontracting'].initial = kwargs['initial']['subcontracting'].id


class CommonAllergenForm(forms.ModelForm):
    """
    頻発アレルギーマスタForm
    """
    ignore_allergen_names = ['なし', '個食', 'フリーズ', 'あり']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        self.fields['menu_name'].choices = \
            lambda: [(m.id, m.menu_name) for m in MenuMaster.objects.all().order_by('seq_order')]

        self.fields['allergen'].choices = \
            lambda: [(a.id, a.allergen_name) for a in AllergenMaster.objects.filter(is_common=True).exclude(
                allergen_name__in=self.ignore_allergen_names).order_by('seq_order')]

    class Meta:
        model = CommonAllergen
        fields = '__all__'
        widgets = {
            'allergen': forms.SelectMultiple(),
        }


class UserDryColdUpdateForm(forms.ModelForm):
    """
    施設情報更新Form
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # unlock_limitationはform-controlを付けると、見えなくなってしまうので設定しない
        self.fields['dry_cold_type'].widget.attrs['class'] = 'form-control'

        # プルダウンの設定
        self.fields['dry_cold_type'].choices = \
            lambda: [('乾燥', '乾燥'), ('冷凍', '冷凍(直送)'), ('冷凍_談', '冷凍(談から送る)')]

    class Meta:
        model = User
        fields = ('dry_cold_type',)


class MixRicePlateForm(forms.ModelForm):
    """
    混ぜご飯マスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['class'] = 'form-control'

    class Meta:
        model = AggMeasureMixRiceMaster
        fields = ('name', 'is_mix_package', 'is_write_rate')


class RawPlateForm(forms.ModelForm):
    """
    原体料理マスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            # Bool以外の型項目にform-controlを設定
            if not (('is_' in key) or ('eneble_name_gram' in key)):
                field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = RawPlatePackageMaster
        fields = ('base_name',
                  'dry_name', 'dry_quantity', 'dry_unit', 'dry_package_quantity', 'dry_eneble_name_gram', 'is_direct_dry',
                  'cold_name', 'cold_quantity', 'cold_unit', 'cold_package_quantity', 'cold_eneble_name_gram', 'is_direct_cold',
                  'enge_cooking_target'
                  )


class SetoutDurationSearchForm(forms.Form):
    """
    盛付指示書表示停止・再開設定検索用Form
    """
    eating_day = forms.DateField(label='盛付指示書喫食日',
                                 widget=forms.DateInput(attrs={"type": "date"}), input_formats=['%Y-%m-%d'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class SetoutDurationForm(forms.ModelForm):
    """
    盛付指示書表示マスタForm
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['last_enable'].widget.attrs['class'] = 'form-control'
        self.fields['last_enable'].widget.attrs['readonly'] = 'readonly'

    class Meta:
        model = SetoutDuration
        fields = ('is_hide', 'last_enable')
        widgets = {
            'last_enable': DateInput2(),
        }
# endregion
# endregion
