from django.contrib import admin
from rangefilter.filters import DateRangeFilter

# 一覧画面でチェックボックスでまとめて削除する機能を無効化する
admin.site.disable_action('delete_selected')


from .models import UnitMaster
class UnitMasterAdmin(admin.ModelAdmin):
    list_display = ('unit_number', 'user_facility_name', 'unit_name', 'calc_name', 'unit_code', 'group', 'seq_order')
    list_display_links = ('unit_name',)
    ordering = ('seq_order', 'id')

    def user_facility_name(self, obj):
        return obj.username.facility_name

    user_facility_name.short_description = '施設名'
    user_facility_name.admin_order_field = 'user__facility_name'

admin.site.register(UnitMaster, UnitMasterAdmin)


from .models import MealMaster
class MealMasterAdmin(admin.ModelAdmin):
    list_display = ('meal_name', 'soup', 'filling', 'miso_soup', 'seq_order')
    ordering = ('seq_order', 'id')

admin.site.register(MealMaster, MealMasterAdmin)


from .models import MealDisplay
class MealDisplayAdmin(admin.ModelAdmin):
    list_display = ('username', 'meal_name_miso_soup')
    list_filter = ('username',)
    ordering = ('id',)

    def meal_name_miso_soup(self, obj):
        return obj.meal_name.miso_soup

    meal_name_miso_soup.short_description = '食事区分'
    meal_name_miso_soup.admin_order_field = 'meal_name__miso_soup'


admin.site.register(MealDisplay, MealDisplayAdmin)


from .models import MenuMaster
class MenuMasterAdmin(admin.ModelAdmin):
    list_display = ('menu_name', 'group', 'seq_order')
    ordering = ('seq_order', 'id')

admin.site.register(MenuMaster, MenuMasterAdmin)


from .models import MenuDisplay
class MenuDisplayAdmin(admin.ModelAdmin):
    list_display = ('username', 'menu_name', 'price_breakfast', 'price_lunch', 'price_dinner')
    list_filter = ('username',)
    ordering = ('id',)

admin.site.register(MenuDisplay, MenuDisplayAdmin)


from .models import AllergenMaster
class AllergenMasterAdmin(admin.ModelAdmin):
    list_display = ('allergen_name', 'seq_order')
    list_editable = ('seq_order',)
    ordering = ('seq_order', 'id')

admin.site.register(AllergenMaster, AllergenMasterAdmin)


from .models import AllergenDisplay
class AllergenDisplayAdmin(admin.ModelAdmin):
    list_display = ('user_facility_name', 'allergen_name')
    list_filter = ('username',)
    list_editable = ('allergen_name',)
    ordering = ('id',)

    def user_facility_name(self, obj):
        return obj.username.facility_name

    user_facility_name.short_description = '施設名'
    user_facility_name.admin_order_field = 'user__facility_name'

admin.site.register(AllergenDisplay, AllergenDisplayAdmin)


from .models import Order
class OrderAdmin(admin.ModelAdmin):
    list_display = ('eating_day', 'quantity', 'meal_name_miso_soup', 'menu_name', 'allergen',
                    'unit_name_username', 'unit_name', 'updated_at')
    list_filter = (['eating_day', DateRangeFilter], 'meal_name__miso_soup', 'menu_name', 'unit_name', 'allergen')
    list_editable = ('quantity',)
    list_display_links = ('eating_day',)  # １列目は記載しておかないといけないっぽい
    ordering = ('eating_day', 'unit_name__unit_code', 'meal_name__seq_order', 'menu_name', 'allergen__seq_order')
    date_hierarchy = 'eating_day'

    def meal_name_miso_soup(self, obj):
        return obj.meal_name.miso_soup

    def unit_name_username(self, obj):
        return obj.unit_name.username

    meal_name_miso_soup.short_description = '食事区分'
    meal_name_miso_soup.admin_order_field = 'meal_name__miso_soup'

    unit_name_username.short_description = '施設名'
    unit_name_username.admin_order_field = 'unit_name__username'

admin.site.register(Order, OrderAdmin)


from .models import OrderEveryday
class OrderEverydayAdmin(admin.ModelAdmin):
    list_display = ('unit_name', 'meal_name_miso_soup', 'menu_name', 'quantity')
    list_filter = ('unit_name',)
    list_editable = ('quantity',)
    list_display_links = ('unit_name',)
    ordering = ('id', 'meal_name__seq_order')

    def meal_name_miso_soup(self, obj):
        return obj.meal_name.miso_soup

    meal_name_miso_soup.short_description = '食事区分'
    meal_name_miso_soup.admin_order_field = 'meal_name__miso_soup'

admin.site.register(OrderEveryday, OrderEverydayAdmin)


from .models import OrderRice
class OrderRiceAdmin(admin.ModelAdmin):
    list_display = ('eating_day', 'unit_name', 'quantity')
    list_filter = (['eating_day', DateRangeFilter], 'unit_name')
    list_editable = ('quantity',)
    list_display_links = ('eating_day', 'unit_name',)
    ordering = ('eating_day',)

admin.site.register(OrderRice, OrderRiceAdmin)


from .models import RakukonShortname
class RakukonShortnameAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'group', 'allergen')
    list_display_links = ('short_name',)
    ordering = ('short_name',)

admin.site.register(RakukonShortname, RakukonShortnameAdmin)


from .models import Communication
class CommunicationAdmin(admin.ModelAdmin):
    list_display = ('group', 'title', 'document_file', 'updated_at')
    list_display_links = ('title',)
    list_filter = ('group',)
    ordering = ('-updated_at',)

admin.site.register(Communication, CommunicationAdmin)


from .models import ProductMaster
class ProductMasterAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_name', 'meal_name', 'menu_name', 'allergen')
    list_display_links = ('product_name',)
    ordering = ('id',)

admin.site.register(ProductMaster, ProductMasterAdmin)


from .models import EverydaySelling
class EverydaySellingAdmin(admin.ModelAdmin):
    list_display = ('unit_name', 'product_code', 'product_name', 'quantity', 'price', 'enable')
    list_display_links = ('unit_name',)
    ordering = ('unit_name', '-enable')

admin.site.register(EverydaySelling, EverydaySellingAdmin)


from .models import InvoiceException
class InvoiceExceptionAdmin(admin.ModelAdmin):
    list_display = ('unit_name', 'ng_saturday', 'ng_sunday', 'ng_holiday', 'reduced_rate', 'is_far',)
    ordering = ('id',)

admin.site.register(InvoiceException, InvoiceExceptionAdmin)


from .models import SerialCount
class SerialCountAdmin(admin.ModelAdmin):
    list_display = ('serial_name', 'serial_number')

admin.site.register(SerialCount, SerialCountAdmin)


from .models import UserOption
class UserOptionAdmin(admin.ModelAdmin):
    list_display = ('username', 'unlock_limitation', 'unlock_day')
    list_editable = ('unlock_limitation',)

admin.site.register(UserOption, UserOptionAdmin)


from .models import DocumentMaster
class DocumentMasterAdmin(admin.ModelAdmin):
    list_display = ('document_kind', 'seq_order')
    list_editable = ('seq_order',)
    ordering = ('seq_order',)

admin.site.register(DocumentMaster, DocumentMasterAdmin)


from .models import DocGroupMaster
class DocumentsGroupMasterAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'seq_order')
    list_editable = ('seq_order',)
    ordering = ('seq_order',)

admin.site.register(DocGroupMaster, DocumentsGroupMasterAdmin)


from .models import DocGroupDisplay
class DocumentsGroupDisplayAdmin(admin.ModelAdmin):
    list_display = ('username', 'group_name')
    list_filter = ('group_name', 'username',)
    ordering = ('username', 'group_name',)

admin.site.register(DocGroupDisplay, DocumentsGroupDisplayAdmin)


from .models import PaperDocuments
class PaperDocumentsAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_kind', 'document_group', 'document_file')
    list_display_links = ('updated_at',)
    ordering = ('-updated_at', 'document_kind')

admin.site.register(PaperDocuments, PaperDocumentsAdmin)


from .models import InvoiceFiles
class InvoiceFilesAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file', 'username')
    ordering = ('-updated_at',)

admin.site.register(InvoiceFiles, InvoiceFilesAdmin)


from .models import ImportMenuName
class ImportMenuNameAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(ImportMenuName, ImportMenuNameAdmin)


from .models import ImportMonthlyMenu
class ImportMonthlyMenuAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(ImportMonthlyMenu, ImportMonthlyMenuAdmin)


from .models import MonthlyMenu
class MonthlyMenuAdmin(admin.ModelAdmin):
    list_display = ('eating_day', 'meal_name', 'food_name', 'option')
    list_filter = (['eating_day', DateRangeFilter], 'option')
    ordering = ('eating_day', 'seq_order',)
    date_hierarchy = 'eating_day'

admin.site.register(MonthlyMenu, MonthlyMenuAdmin)


from .models import FoodPhoto
class FoodPhotoAdmin(admin.ModelAdmin):
    list_display = ('food_name', 'hot_cool', 'photo_file', 'menu', )
    list_filter = (['menu__eating_day', DateRangeFilter], 'hot_cool', )
    ordering = ('-menu__eating_day', 'id',)
    search_fields = ['food_name']

admin.site.register(FoodPhoto, FoodPhotoAdmin)


from .models import Chat
class ChatAdmin(admin.ModelAdmin):
    list_display = ('username', 'is_sendto', 'is_read', 'created_at', 'updated_at')
    ordering = ('-created_at',)

admin.site.register(Chat, ChatAdmin)


from .forms import HolidayListForm
from .models import HolidayList
class HolidayListAdmin(admin.ModelAdmin):
    list_display = ('holiday_name', 'start_date', 'end_date')
    ordering = ('start_date',)
    form = HolidayListForm

admin.site.register(HolidayList, HolidayListAdmin)

from .models import JapanHoliday
class JapanHolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name')
    ordering = ('date',)

admin.site.register(JapanHoliday, JapanHolidayAdmin)

from .models import AggMeasureSoupMaster
class AggMeasureSoupMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'search_word', 'soup_group', 'output_type')
    ordering = ('name',)

admin.site.register(AggMeasureSoupMaster, AggMeasureSoupMasterAdmin)

from .models import AggMeasureMixRiceMaster
class AggMeasureMixRiceMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'search_word', 'is_mix_package', 'is_write_rate')
    ordering = ('name',)

admin.site.register(AggMeasureMixRiceMaster, AggMeasureMixRiceMasterAdmin)

from .models import UncommonAllergen
class UncommonAllergenAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'menu_name', 'allergen', 'last_use_date')
    ordering = ('seq_order',)

admin.site.register(UncommonAllergen, UncommonAllergenAdmin)

from .models import CommonAllergen
class CommonAllergenAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'menu_name', 'allergen', 'seq_order')
    ordering = ('seq_order',)

admin.site.register(CommonAllergen, CommonAllergenAdmin)

from .models import EngeDirection
class EngeDirectionAdmin(admin.ModelAdmin):
    list_display = ('food_name', 'direction_type', 'soe')
    ordering = ('food_name',)

admin.site.register(EngeDirection, EngeDirectionAdmin)

from .models import NewYearDaySetting
class NewYearDaySettingAdmin(admin.ModelAdmin):
    list_display = ('year', 'enable_date_from', 'enable_date_to')
    ordering = ('-year',)

admin.site.register(NewYearDaySetting, NewYearDaySettingAdmin)

from .models import ReservedMealDisplay
class ReservedMealDisplayAdmin(admin.ModelAdmin):
    list_display = ('username', 'meal_name', 'disable_date')
    ordering = ('username', 'meal_name', 'disable_date')

admin.site.register(ReservedMealDisplay, ReservedMealDisplayAdmin)

from .models import DocumentDirDisplay
class DocumentDirDisplayAdmin(admin.ModelAdmin):
    list_display = ('username', 'plate_dir_name', 'enable_date')
    ordering = ('username', 'plate_dir_name', 'enable_date')

admin.site.register(DocumentDirDisplay, DocumentDirDisplayAdmin)

from .models import ImportMonthlyReport
class ImportMonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(ImportMonthlyReport, ImportMonthlyReportAdmin)

from .models import EngeFoodDirection
class EngeFoodDirectionAdmin(admin.ModelAdmin):
    list_filter = (['menu__eating_day', DateRangeFilter], 'menu__meal_name', )
    ordering = ('id',)

admin.site.register(EngeFoodDirection, EngeFoodDirectionAdmin)


from .models import GenericSetoutDirection
class GenericSetoutDirectionAdmin(admin.ModelAdmin):
    list_display = ('shortening', 'for_enge')
    list_filter = ('for_enge', )
    ordering = ('shortening',)
    search_fields = ['direction']

admin.site.register(GenericSetoutDirection, GenericSetoutDirectionAdmin)

from . models import SetoutDuration
class SetoutDurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'create_at', 'last_enable')
    list_filter = (['create_at', DateRangeFilter], ['last_enable', DateRangeFilter])
    ordering = ('name',)

admin.site.register(SetoutDuration, SetoutDurationAdmin)

from .models import MixRicePackageMaster
class MixRicePackageMasterAdmin(admin.ModelAdmin):
    list_display = ('parts_name', 'package_size')
    ordering = ('parts_name',)

admin.site.register(MixRicePackageMaster, MixRicePackageMasterAdmin)

from .models import ImportP7SourceFile
class ImportP7SourceFileAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(ImportP7SourceFile, ImportP7SourceFileAdmin)

from .models import MonthlySalesPrice
class MonthlySalesPriceAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'transport_price' )
    ordering = ('year', 'month',)

admin.site.register(MonthlySalesPrice, MonthlySalesPriceAdmin)

from .models import NewUnitPrice
class NewUnitPriceAdmin(admin.ModelAdmin):
    list_display = ('username', 'eating_day', 'menu_name', 'price_breakfast', 'price_lunch', 'price_dinner')
    list_filter = ('username',)
    ordering = ('username', 'eating_day', 'id',)

admin.site.register(NewUnitPrice, NewUnitPriceAdmin)


from .models import PackageMaster
class PackageMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity')
    list_filter = ('name', )

admin.site.register(PackageMaster, PackageMasterAdmin)


from .models import UnitPackage
class UnitPackageAdmin(admin.ModelAdmin):
    list_display = ('unit_number', 'unit_name', 'eating_day', 'meal_name', 'plate_name', 'package', 'count', 'menu_name')
    list_filter = ('unit_name', ['eating_day', DateRangeFilter], 'meal_name', 'plate_name', 'package')
    list_display_links = ('eating_day',)
    ordering = ('eating_day', 'unit_number', 'meal_name', 'plate_name', 'menu_name')
    date_hierarchy = 'eating_day'

admin.site.register(UnitPackage, UnitPackageAdmin)


from .models import RawPlatePackageMaster
class RawPlatePackageMasterAdmin(admin.ModelAdmin):
    list_display = ('base_name', 'dry_name', 'dry_quantity', 'cold_name', 'cold_quantity', 'chilled_name', 'chilled_quantity')
    list_filter = ('base_name', )

admin.site.register(RawPlatePackageMaster, RawPlatePackageMasterAdmin)


from .models import PickingResult
class PickingResultAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(PickingResult, PickingResultAdmin)


from .models import PickingResultRaw
class PickingResultRawAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'terminal_no', 'qr_value')
    list_filter = ('terminal_no',)
    ordering = ('-created_at',)

admin.site.register(PickingResultRaw, PickingResultRawAdmin)


from .models import TaxMaster
class TaxMasterAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'rate', 'enable_day')
    ordering = ('code',)

admin.site.register(TaxMaster, TaxMasterAdmin)


from .models import TaxSetting
class TaxSettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'rate', 'is_subcontracting')

admin.site.register(TaxSetting, TaxSettingAdmin)

from .models import ImportUnit
class ImportUnitAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'document_file')
    ordering = ('-updated_at',)

admin.site.register(ImportUnit, ImportUnitAdmin)

from .models import ReservedStop
class ReservedStopAdmin(admin.ModelAdmin):
    list_display = ('unit_name', 'order_stop_day', 'login_stop_day')

admin.site.register(ReservedStop, ReservedStopAdmin)


from .models import MixRiceDay
class MixRiceDayAdmin(admin.ModelAdmin):
    list_display = ('eating_day', 'mix_rice_name')

admin.site.register(MixRiceDay, MixRiceDayAdmin)


from .models import OutputSampleP7
class OutputSampleP7Admin(admin.ModelAdmin):
    list_display = ('eating_day', 'meal_name', 'cooking_day')

admin.site.register(OutputSampleP7, OutputSampleP7Admin)

