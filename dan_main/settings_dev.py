from .settings_common import *


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# ロギング設定
LOGGING = {
    'version': 1,  # 1固定
    'disable_existing_loggers': False,

    # ロガーの設定
    'loggers': {
        # Djangoが利用するロガー
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        # web_orderアプリケーションが利用するロガー
        'web_order': {
            'handlers': ['file_web_order'],
            'level': 'DEBUG',
        },
    },

    # ハンドラの設定
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'dev'
        },
        'file_web_order': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(BASE_DIR, "logs/web_order.log"),
            'formatter': 'create_order_blank',
            'when': 'D',
            'interval': 1,
            'backupCount': 7,
        },
    },

    # フォーマッタの設定
    'formatters': {
        'dev': {
            'format': '\t'.join([
                '%(asctime)s',
                '[%(levelname)s]',
                '%(pathname)s(Line:%(lineno)d)',
                '%(message)s'
            ])
        },
        'create_order_blank': {
            'format': ','.join([
                '%(asctime)s',
                '[%(levelname)s]',
                '%(message)s'
            ])
        },
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'shinji.harada@gmail.com'
EMAIL_HOST_PASSWORD = 'hindunwyyerhohup'
EMAIL_USE_TLS = True

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

OUTPUT_DIR = os.path.join(MEDIA_ROOT, 'output')

# 検食が無料なユニット
FREE_KENSYOKU_UNITS = []

# --食数固定製造分ID(朝、昼、夕)--
# 常食保存用(1人用袋)
ORDER_EVERYDAY_PRESERVE_1PACK_ID_J = [51,52,53]

# 薄味保存用(1人用袋)
ORDER_EVERYDAY_PRESERVE_1PACK_ID_U = [54,55,56]

# 常食写真用(1人用袋)
ORDER_EVERYDAY_FOR_PHOTO_ID_J = [48,49,50]

# 常食保存用(50g)
ORDER_EVERYDAY_PRESERVE_50G_ID_J = [61,62,63]

# 嚥下保存用(50g)
ORDER_EVERYDAY_PRESERVE_50G_ID_S = [64,67,70]
ORDER_EVERYDAY_PRESERVE_50G_ID_Z = [65,68,71]
ORDER_EVERYDAY_PRESERVE_50G_ID_M = [66,69,72]
# -- --

# 食数集計のユニットの並び順
AGGREGATE_UNIT_SORT_ORDER = [

]

# 製造作成表:施設・献立種類毎の表の最大行
COOK_PRODUCT_UNIT_ROW_MAX = 11

# 請求書会社コード変換対象(ここに定義されたコードは、先頭に9を付与したuseridを使う)
CONVERT_INVERT_USERID_TO_PARENTS = [
    '10002',
    '10004',
    '10022',
    '10053',
    '10037',
    '10050',
    '10055',
    '10066',
    '10070',
    '10084',
    '10090',
]

# 食数集計:木沢個食の食種
KIZAWA_RAKUKON_CODE = ''
FREEZE_RACKUKON_CODE = 'ﾌﾘｰｽﾞ'

# 調理表：常食、薄味の食数(アレルギー含む)用識別子
COOKING_DIRECTION_J_CODE = '常･基本食'
COOKING_DIRECTION_U_CODE = '薄･基本食'
COOKING_DIRECTION_SOUP_J_CODE = '常汁･基本食'
COOKING_DIRECTION_SOUP_U_CODE = '薄汁･基本食'
COOKING_DIRECTION_GU_J_CODE = '常具･基本食'
COOKING_DIRECTION_GU_U_CODE = '薄具･基本食'
COOKING_DIRECTION_B_CODE = '基･基本食'
COOKING_DIRECTION_SOUP_B_CODE = '基汁･基本食'
COOKING_DIRECTION_GU_B_CODE = '基具･基本食'

# 調理表：フリーズの食数用識別子
COOKING_DIRECTION_F_CODE = 'ﾌﾘｰｽﾞ･基本食'

# 調理表：サンプルの食種
COOKING_DIRECTION_SAMPLE_J_CODE = '常サン･基本食'
COOKING_DIRECTION_SAMPLE_S_CODE = 'サ）ソ･基本食'
COOKING_DIRECTION_SAMPLE_Z_CODE = 'サ）ゼ･基本食'
COOKING_DIRECTION_SAMPLE_M_CODE = 'サ）ミ･基本食'
COOKING_DIRECTION_TEST_CODE = 'テスト･基本食'

# 加熱加工記録簿：同一料理の記載回数
PLATE_WRITE_COUNT = 4
ENGE_WRITE_COUNT = 2
HEATING_PROCESSING_MAX_ROW = 900

# 薄味->常食統合基準日
BASIC_PLATE_ENABLE_DATE = '2022-09-20'

# 混ぜご飯計量表出力で、集約するユニット。先頭要素の施設名を採用する
MIX_RICE_AGGREGATE_UNITS = [
    [11,80]
]

KOSHOKU_UNIT_IDS = []
FREEZE_UNIT_IDS = [9]

ADJUST_PICKING_DAY = 1

# P7献立読込スタブモード
STUB_MODE_P7_READ = False
IGNORE_ALLERGEN_RERATION_BACKUP = False
DEBUG_READ_PICKING_RESULT = True
DEBUG_ADJUST_PICKING_DAY = 0

# 喫食日・売上日関連(補正日と、有効日のタプル)
EATING_SALES_SETTINGS = [
    (2, '2000-01-01'),
    (3, '2023-03-01')
]

# 食数変更期限関連(バージョンと、有効日のタプル)
# ver.1：日曜祝日以外
# ver.2：土日曜祝日以外
ORDER_CHANGEABLE_SETTINGS = [
    (1, '2000-01-01'),
    (2, '2024-02-22')
]

# 原体嚥下製造の有効日
RAW_TO_ENGE_ENABLE = '2024-03-01'

# ピッキング指示書出力用袋マスタID
PICKING_PACKAGES = {
    'BASIC_10': 1,
    'BASIC_5': 2,
    'BASIC_FRACTION': 3,
    'BASIC_1': 4,
    'BASIC_UNIT': 5,

    'ENGE_7': 6,
    'ENGE_14': 7,
    'ENGE_20': 8,
    'ENGE_1': 9,
    'ENGE_2': 10,

    'SOUP_10': 11,
    'SOUP_FRACTION': 12,
    'SOUP_UNIT': 13,
    'SOUP_1': 14,
}


# 照合結果画面リロード間隔(ミリ秒)
PICKING_RESULT_AUTO_RELOAD_INTERVAL = 1 * 60 * 1000

# 頻発アレルギー設定画面：インデックス補正値
COMMON_ALLERGEN_MINIMUM_INDEX = 9

# 他システムからのWebAPI呼出時の認証キー
WEB_API_KEY = 'dan_2024'

"""
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.logging.LoggingPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
    ]
"""
