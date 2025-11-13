from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import index, order, order_new_year, order_list, order_allergen, order_allergen_list, order_rice
from .views import exec_agg_temp, exec_agg_measure, exec_invoice_label, exec_aggregation, exec_setout_direction
from .views import control_panel, chat, chat_all, invoice_upload, exec_transfer_label, cooking_produce, cooking_produce_export
from .views import converted_cooking_direction_files, heating_processing, heating_processing_files, documents_upload, document_files
from .views import food_register, setout_file_download, monthly_report_import, sales_price_output
from .views import cooking_document_files, documents_delete, document_files_check, exec_sales_price, sales_price_files
from .views import cooking_files, cooking_produce_files, measure_files, invoice_files, label_files, setout_files, manual_files
from .views import manual_files_calc, manual_files_master, manual_files_label, manual_files_measure, manual_files_order
from .views import manual_files_cooiking, manual_files_document, manual_files_heating, manual_files_kakiokoshi
from .views import manual_files_p7, manual_files_raw_plate, manual_files_picking, manual_files_sales, manual_files_recipe
from .views import paper_documents_list, convert_cooking_direction, create_measure_table, register_monthly_menu, monthly_menu_list
from .views import setout_files_manage, exec_setout_create, setout_file_download_for_manage, p7_source_upload, p7_csv_output
from .views import p7_files, sales_price_management_view, exec_output_kakiokoshi, kakiokoshi_list_view, plate_relation_list_view
from .views import plate_relation_list_add_view, picking_upload, picking_output_view, seal_csv_output_view, picking_files
from .views import PickingResultView, PickingHistoriesView, seal_csv_files_view, order_list_csv, order_unit
from .views import pouch_output_view, pouch_files, manual_files_pouch, picking_notices_view, picking_notice_print_view
from .views import design_seal_csv_output_view, design_seal_csv_files_view, design_seal_csv_files_basic_view
from .views import design_seal_csv_files_soft_view, design_seal_csv_files_jelly_view, design_seal_csv_files_mixer_view
from .views import design_seal_csv_allergen_files_view, design_seal_csv_allergen_basic_view, design_seal_csv_allergen_soft_view
from .views import design_seal_csv_allergen_jelly_view, design_seal_csv_allergen_mixer_view, chat_delete, dry_cold_update_view
from .views import master_manuals_contract, master_manuals_order, master_manuals_direction, master_manuals_setout
from .views import master_manuals_documents

from .views import master_index

from .api_views import invoice_auth_api, show_new_year_api, get_stetout_direction
from .api_views import OperatedUnitsView, OrdersRateView, GosuInputView, MixRiceStructureView, GosuLogView

app_name = 'web_order'

router = DefaultRouter()

urlpatterns = [
    # トップページ
    path('', index, name="index"),

    # 仮注文・週間入力
    path('order/', order, name="order"),

    # 元日注文入力
    path('order-new-year/', order_new_year, name="order_new_year"),

    # 施設メンテナンス
    path('unit/import/', views.UnitImportView.as_view(), name="unit_import"),

    # 仮注文後の食数変更
    path('order-change-list/', views.OrderChangeList.as_view(), name="order_change_list"),
    path('order-change-update/<int:pk>/', views.OrderChangeUpdate.as_view(), name="order_change_update"),
    # path('order-change-update/<int:pk>/', update_order, name="order_change_update"),

    # アレルギーの注文
    path('order-allergen/', order_allergen, name="order_allergen"),
    path('order-allergen-list/', order_allergen_list, name="order_allergen_list"),
    path('order-allergen-update/<int:pk>/', views.OrderAllergenUpdate.as_view(), name="order_allergen_update"),

    # 混ぜご飯の注文
    path('order-rice/', order_rice, name="order_rice"),

    # すべての注文データ
    path('order-list/', order_list, name="order_list"),
    path('order-list/csv', order_list_csv, name="order_list_csv"),
    path('order-list/unit', order_unit, name="order_unit"),

    # お知らせ
    path('communication/', views.CommunicationCreate.as_view(), name="communication"),
    path('communication-list/', views.CommunicationList.as_view(), name="communication_list"),
    path('communication-detail/<int:pk>/', views.CommunicationDetail.as_view(), name="communication_detail"),
    path('communication-update/<int:pk>/', views.CommunicationUpdate.as_view(), name="communication_update"),
    path('communication-delete/<int:pk>/', views.CommunicationDelete.as_view(), name="communication_delete"),

    path('convert-cooking-direction/', convert_cooking_direction, name="convert_cooking_direction"),
    path('create-measure-table/', create_measure_table, name="create_measure_table"),

    path('register-monthly-menu/', register_monthly_menu, name="register_monthly_menu"),

    # 献立指示書
    path('food-photo-list/', views.FoodPhotoList.as_view(), name="food_photo_list"),
    path('food-photo-update/<int:pk>/', views.FoodPhotoUpdate.as_view(), name="food_photo_update"),
    path('food-photo-detail/<int:pk>/', views.FoodPhotoDetail.as_view(), name="food_photo_detail"),
    path('food-register/', food_register, name="food_register"),
    path('monthly-menu-list/', monthly_menu_list, name="monthly_menu_list"),

    path('paper-documents/', views.PaperDocumentsCreate.as_view(), name="paper_documents"),
    path('paper-documents-list/', paper_documents_list, name="paper_documents_list"),
    path('paper-documents-list-all/', views.PaperDocumentsListALL.as_view(), name="paper_documents_list_all"),

    # 献立資料管理
    path('cooking-documents/', cooking_document_files, name="cooking_documents"),
    path('documents-check/', document_files_check, name="documents_check"),
    path('documents-upload/', documents_upload, name="documents_upload"),
    path('documents-delete/', documents_delete, name="documents_delete"),

    # 営業月報登録
    path('monthly-report-upload/', monthly_report_import, name="monthly_report_upload"),
    path('sales-price-output/', sales_price_output, name="sales_price_output"),
    path('sales-price-management/', sales_price_management_view, name="sales_price_management"),

    path('invoice-upload/', invoice_upload, name="invoice_upload"),
    path('invoice-list/', views.InvoiceList.as_view(), name="invoice_list"),

    # P7対応(印刷用CSV出力)
    path('print-csv-output/', p7_source_upload, name="p7_import"),
    path('print-csv-output/p7file', p7_csv_output, name="p7_csv_output"),
    path('print-csv-output/files', p7_files, name="p7_csv_files"),

    # 書き起こし票
    path('kakiokoshi/output', exec_output_kakiokoshi, name="kakiokoshi_output"),
    path('kakiokoshi/list', kakiokoshi_list_view, name="kakiokoshi_list"),

    # ピッキング対応(中袋用シール印刷用CSV)
    path('seal-csv-output/', seal_csv_output_view, name="seal_output"),
    path('seal-csv-files/', seal_csv_files_view, name="seal_csv_files"),

    # 設計図パウチシール印刷用CSV
    path('design-seal-csv-output/', design_seal_csv_output_view, name="design_seal_output"),
    path('design-seal-files/', design_seal_csv_files_view, name="design_seal_files"),
    path('design-seal-files/basic', design_seal_csv_files_basic_view, name="design_seal_files_basic"),
    path('design-seal-files/soft', design_seal_csv_files_soft_view, name="design_seal_files_soft"),
    path('design-seal-files/jelly', design_seal_csv_files_jelly_view, name="design_seal_files_jelly"),
    path('design-seal-files/mixer', design_seal_csv_files_mixer_view, name="design_seal_files_mixer"),
    path('design-seal-files/allergen', design_seal_csv_allergen_files_view, name="design_seal_files_allergen"),
    path('design-seal-files/allergen/basic', design_seal_csv_allergen_basic_view, name="design_seal_files_allergen_basic"),
    path('design-seal-files/allergen/soft', design_seal_csv_allergen_soft_view, name="design_seal_files_allergen_soft"),
    path('design-seal-files/allergen/jelly', design_seal_csv_allergen_jelly_view, name="design_seal_files_allergen_jelly"),
    path('design-seal-files/allergen/mixer', design_seal_csv_allergen_mixer_view, name="design_seal_files_allergen_mixer"),

    # ピッキング対応(ピッキング指示書)
    path('picking-output/', picking_output_view, name="picking_output"),
    path('picking-files/', picking_files, name="picking_files"),

    path('control-panel', control_panel, name="control_panel"),
    path('cooking-files', cooking_files, name="cooking_files"),
    path('cooking-produce', cooking_produce, name="cooking_produce"),
    path('cooking-produce-export', cooking_produce_export, name="cooking_produce_export"),
    path('cooking-produce-files', cooking_produce_files, name="cooking_produce_files"),
    path('converted-cooking-files', converted_cooking_direction_files, name="converted_cooking_files"),
    path('measure-files', measure_files, name="measure_files"),
    path('invoice-files', invoice_files, name="invoice_files"),
    path('label-files', label_files, name="label_files"),
    path('setout-files', setout_files, name="setout_files"),
    path('sales-price-files', sales_price_files, name="sales_price_files"),
    path('document-files', document_files, name="document_files"),

    path('setout-files/management', setout_files_manage, name="setout_files_manage"),
    path('setout-files/download', setout_file_download, name="setout_file_download"),
    path('setout-files/management/download', setout_file_download_for_manage, name="setout_files_manage_download"),

    path('heating-processing', heating_processing, name="heating_processing"),
    path('heating-processing-files', heating_processing_files, name="heating_processing_files"),

    path('exec-agg-temp', exec_agg_temp, name="exec_agg_temp"),
    path('exec-agg-measure', exec_agg_measure, name="exec_agg_measure"),
    path('exec-invoice-label', exec_invoice_label, name="exec_invoice_label"),
    path('exec-transfer-label', exec_transfer_label, name="exec_transfer_label"),
    path('exec-sales-price', exec_sales_price, name="exec_sales_price"),
    path('exec-aggregation', exec_aggregation, name="exec_aggregation"),
    path('exec-setout-direction', exec_setout_direction, name="exec_setout_direction"),
    path('exec-setout-create', exec_setout_create, name="exec_setout_create"),

    path('chat/', chat, name="chat"),
    path('chat-all/', chat_all, name="chat_all"),
    path('chat-delete/<int:pk>', chat_delete, name="chat_delete"),

    # 料理代替食連携
    path('plate-relation', plate_relation_list_view, name="plate_relation"),
    path('plate-relation/add', plate_relation_list_add_view, name="plate_relation_add"),

    # ピッキング結果
    path('picking/upload', picking_upload, name="picking_upload"),
    path('picking/results', PickingResultView.as_view(), name="picking_result_list"),
    path('picking/histories', PickingHistoriesView.as_view(), name="picking_histories"),
    path('picking/notices', picking_notices_view, name="picking_notices"),
    path('picking/notice/print/<int:id>', picking_notice_print_view, name="picking_notice_print"),

    # パウチ設計図
    path('pouch-output/', pouch_output_view, name="pouch_output"),
    path('pouch-files/', pouch_files, name="pouch_files"),

    path('invoice-histories/', views.InvoiceHistoriesList.as_view(), name="invoice_histories"),

    # メンテナンス
    path('maintenance/dry-cold', dry_cold_update_view, name="maintenance_dry_cold"),

    # マニュアル
    path('manual-files/master', manual_files_master, name="manual_files_master"),
    path('manual-files/order', manual_files_order, name="manual_files_order"),
    path('manual-files/sales', manual_files_sales, name="manual_files_sales"),
    path('manual-files/calc-sales', manual_files_calc, name="manual_files_calc"),
    path('manual-files', manual_files, name="manual_files"),    # らくらく献立
    path('manual-files/cooking', manual_files_cooiking, name="manual_files_cooking"),
    path('manual-files/measure', manual_files_measure, name="manual_files_measure"),
    path('manual-files/recipe', manual_files_recipe, name="manual_files_recipe"),
    path('manual-files/label', manual_files_label, name="manual_files_label"),
    path('manual-files/heating', manual_files_heating, name="manual_files_heating"),
    path('manual-files/document', manual_files_document, name="manual_files_document"),
    path('manual-files/raw-plate', manual_files_raw_plate, name="manual_files_raw_plate"),
    path('manual-files/kakiokoshi', manual_files_kakiokoshi, name="manual_files_kakiokoshi"),
    path('manual-files/p7', manual_files_p7, name="manual_files_p7"),
    path('manual-files/picking', manual_files_picking, name="manual_files_picking"),
    path('manual-files/pouch', manual_files_pouch, name="manual_files_pouch"),

    # マスタメンテナンス用画面---
    # マスタメンテナンス画面のトップフォルダは「master」とすること
    path('master/index', master_index, name="master_index"),

    # 注文数変更メンテナンス
    path('master/order/maintenance/', views.OrderMaintenanceView.as_view(), name="order_maintenance"),

    # 販売固定商品マスタ
    path('master/everydayselling', views.EverydaySellingCreate.as_view(), name="everyday_selling_create"),
    path('master/everydayselling-list/', views.EverydaySellingList.as_view(), name="everyday_selling_list"),
    path('master/everydayselling-update/<int:pk>/', views.EverydaySellingUpdate.as_view(), name="everyday_selling_update"),

    # 単価変更マスタ
    path('master/new-price-create/<int:userid>/', views.NewUnitPriceCreate.as_view(), name="new_price_create"),
    path('master/new-price-list/', views.NewUnitPriceList.as_view(), name="new_price_list"),
    path('master/new-price-update/<int:pk>/', views.NewUnitPriceUpdate.as_view(), name="new_price_update"),
    path('master/new-price-history/<int:pk>/', views.NewUnitPriceHistory.as_view(), name="new_price_history"),
    path('master/new-price-delete/<int:delegate>/', views.NewUnitPriceDelete.as_view(), name="new_price_delete"),

    # 仮注文_特別対応マスタ
    path('master/pre-order-setting', views.PreorderSettingCreate.as_view(), name="pre_order_setting_create"),
    path('master/pre-order-settings/', views.PreorderSettingList.as_view(), name="pre_order_settings"),
    path('master/pre-order-setting-update/<int:pk>/', views.PreorderSettingUpdate.as_view(), name="pre_order_setting_update"),
    path('master/pre-order-setting-delete/<int:pk>/', views.PreorderSettingDelete.as_view(), name="pre_order_setting_delete"),

    # 注文データ_合数変更マスタ
    path('master/rice-order', views.RiceOrderCreate.as_view(), name="rice_order_create"),
    path('master/rice-orders/', views.RiceOrderList.as_view(), name="rice_orders"),
    path('master/rice-order-update/<int:pk>/', views.RiceOrderUpdate.as_view(), name="rice_order_update"),

    # 長期休暇設定マスタ
    path('master/long-holidays', views.LongHolidaysCreate.as_view(), name="long_holidays_create"),
    path('master/long-holidays-list/', views.LongHolidaysList.as_view(), name="long_holidays_list"),
    path('master/long-holidays-update/<int:pk>/', views.LongHolidaysUpdate.as_view(), name="long_holidays_update"),

    # 元日注文設定マスタ
    path('master/new_year_setting', views.NewYearSettingCreate.as_view(), name="new_year_setting_create"),
    path('master/new_year_settings/', views.NewYearSettingList.as_view(), name="new_year_settings"),
    path('master/new_year_setting-update/<int:pk>/', views.NewYearSettingUpdate.as_view(), name="new_year_setting_update"),

    # アレルギー種類マスタ
    path('master/allergen', views.AllergenMasterCreate.as_view(), name="allergen_master_create"),
    path('master/allergens/', views.AllergenMasterList.as_view(), name="allergen_masters"),
    path('master/allergen-update/<int:pk>/', views.AllergenMasterUpdate.as_view(), name="allergen_master_update"),

    # 顧客別_アレルギー設定マスタ
    path('master/allergen-setting', views.AllergenSettingCreate.as_view(), name="allergen_setting_create"),
    path('master/allergen-settings/', views.AllergenSettingList.as_view(), name="allergen_settings"),
    path('master/allergen-setting-update/<int:pk>/', views.AllergenSettingUpdate.as_view(), name="allergen_setting_update"),

    # 顧客別_売上日調整日数マスタ
    path('master/sales_day-setting', views.SalesDaySettingCreate.as_view(), name="sales_day_setting_create"),
    path('master/sales_day-settings/', views.SalesDaySettingList.as_view(), name="sales_day_settings"),
    path('master/sales_day-setting-update/<int:pk>/', views.SalesDaySettingUpdate.as_view(), name="sales_day_setting_update"),

    # 混ぜご飯袋サイズ設定マスタ
    path('master/mix-rice-package', views.MixRicePackageCreate.as_view(), name="mix_rice_package_create"),
    path('master/mix-rice-packages/', views.MixRicePackageList.as_view(), name="mix_rice_packages"),
    path('master/mix-rice-package-update/<int:pk>/', views.MixRicePackageUpdate.as_view(), name="mix_rice_package_update"),
    path('master/mix-rice-package-delete/<int:pk>/', views.MixRicePackageDelete.as_view(), name="mix_rice_package_delete"),

    # 献立定型文マスタ
    path('master/set-out-direction', views.SetOutDirectionCreate.as_view(), name="set_out_direction_create"),
    path('master/set-out-directions/', views.SetOutDirectionList.as_view(), name="set_out_directions"),
    path('master/set-out-direction-update/<int:pk>/', views.SetOutDirectionUpdate.as_view(), name="set_out_direction_update"),
    path('master/set-out-direction-delete/<int:pk>/', views.SetOutDirectionDelete.as_view(), name="set_out_direction_delete"),

    # 顧客別-献立資料フォルダ設定マスタ
    path('master/document-folder', views.DocumentFolderCreate.as_view(), name="document_folder_create"),
    path('master/document-folders/', views.DocumentFolderList.as_view(), name="document_folders"),
    path('master/document-folder-update/<int:pk>/', views.DocumentFolderUpdate.as_view(), name="document_folder_update"),
    path('master/document-folder-delete/<int:pk>/', views.DocumentFolderDelete.as_view(), name="document_folder_delete"),

    # 税率設定
    path('master/tax', views.TaxSettingsView.as_view(), name="tax_settings"),

    # 施設登録
    path('master/users', views.UserListView.as_view(), name="user_masters"),
    path('master/user-create', views.UnitImportView.as_view(), name="user_create"),
    path('master/user-create/confirm', views.UnitImportConfirmView.as_view(), name="user_create_confirm"),
    path('master/user/delete/<int:pk>', views.UserDeleteView.as_view(), name="user_delete"),
    path('master/user/detail/<int:pk>', views.UserDetailView.as_view(), name="user_detail"),
    path('master/karte', views.KarteDownloadView.as_view(), name="karte_download"),
    path('master/user-dry-cold/update/<int:pk>/', views.UserUpdateView.as_view(), name="user_dry_cold"),
    path('master/user-list', views.UserListForUpdateView.as_view(), name="user_master_list"),
    path('master/user/account/download/<int:pk>/', views.UserAccountCsvDownloadView.as_view(), name="user_account_download"),

    # 頻発アレルギー設定画面
    path('master/common-allergens', views.CommonAllergensView.as_view(), name="common_allergens"),
    path('master/common-allergen/delete/<int:seq>/', views.DeleteCommonAllergenView.as_view(), name="common_allergen_delete"),
    path('master/common-allergen/seq-up/<int:seq>/', views.CommonAllergenSeqUpView.as_view(), name="common_allergen_seq_up"),
    path('master/common-allergen/seq-down/<int:seq>/', views.CommonAllergenSeqDownView.as_view(), name="common_allergen_seq_down"),

    # 注文停止・ログイン停止予約
    path('master/stop-reservations', views.StopReservationList.as_view(), name="stop_reservations"),
    path('master/stop-reservation/update/<int:userid>/', views.StopReservationUpdate.as_view(), name="stop_reservation_update"),

    # 混ぜご飯画面
    path('master/mix-rice-plates', views.MixRicePlateList.as_view(), name="mix_rice_plates"),
    path('master/mix-rice-plate/create', views.MixRicePlateCreate.as_view(), name="mix_rice_plate_create"),
    path('master/mix-rice-plate/update/<int:pk>/', views.MixRicePlateUpdate.as_view(), name="mix_rice_plate_update"),
    path('master/mix-rice-plate/delete/<int:pk>/', views.MixRicePlateDelete.as_view(), name="mix_rice_plate_delete"),

    # 原体マスタ画面
    path('master/raw-plates', views.RawPlateList.as_view(), name="raw_plates"),
    path('master/raw-plate/create', views.RawPlateCreate.as_view(), name="raw_plate_create"),
    path('master/raw-plate/update/<int:pk>/', views.RawPlateUpdate.as_view(), name="raw_plate_update"),
    path('master/raw-plate/delete/<int:pk>/', views.RawPlateDelete.as_view(), name="raw_plate_delete"),

    # 盛付指示書表示停止・再開設定
    path('master/setout-duration-setting/maintenance/', views.SetoutDurationSettingView.as_view(), name="setout_duration_setting"),
    path('master/setout-duration-settings', views.SetoutDurationList.as_view(), name="setout_duration_settings"),

    # マスタメンテ画面用マニュアル
    path('master-manuals/contract', master_manuals_contract, name="master_manuals_contract"),
    path('master-manuals/order', master_manuals_order, name="master_manuals_order"),
    path('master-manuals/direction', master_manuals_direction, name="master_manuals_direction"),
    path('master-manuals/setout', master_manuals_setout, name="master_manuals_setout"),
    path('master-manuals/documents', master_manuals_documents, name="master_manuals_documents"),
    # --マスタメンテナンス用画面ここまで

    # Web-API
    path('api/', include(router.urls)),
    path('api/invoice-authorization', invoice_auth_api, name="invoice-auth-api"),
    path('api/show-new-year', show_new_year_api, name="show-new-year-api"),
    path('api/get-food-direction', get_stetout_direction, name="get-food-direction"),
    path('api/units', OperatedUnitsView.as_view(), name="units-api"),
    path('api/orders-rate', OrdersRateView.as_view(), name="orders-rate-api"),
    path('api/gousu-rate', GosuInputView.as_view(), name="gousu-rate-api"),
    path('api/gousu-log', GosuLogView.as_view(), name="gousu-log-api"),
    path('api/mix-rice-structure', MixRiceStructureView.as_view(), name="mix-rice-structure-api"),
]
