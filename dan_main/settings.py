from .settings_common import *


# デバッグモードを有効にするかどうか(本番運用では必ずFalseにする)
DEBUG = False

# 許可するホスト名のリスト
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS')]

# 静的ファイルを配置する場所w
STATIC_ROOT = '/usr/share/nginx/html/static'
MEDIA_ROOT = '/usr/share/nginx/html/media'

OUTPUT_DIR = os.path.join(MEDIA_ROOT, 'output')

# Amazon SES関連設定
AWS_SES_ACCESS_KEY_ID = os.environ.get('AWS_SES_ACCESS_KEY_ID')
AWS_SES_SECRET_ACCESS_KEY = os.environ.get('AWS_SES_SECRET_ACCESS_KEY')
EMAIL_BACKEND = 'django_ses.SESBackend'

# ロギング
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    # ロガーの設定
    'loggers': {
        # Djangoが利用するロガー
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
        },
        # web_orderアプリケーションが利用するロガー
        'web_order': {
            'handlers': ['file_web_order'],
            'level': 'INFO',
        },
    },

    # ハンドラの設定
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/django.log'),
            'formatter': 'prod',
            'when': 'D',  # ログローテーション(新しいファイルへの切り替え)間隔の単位(D=日)
            'interval': 1,  # ログローテーション間隔(1日単位)
            'backupCount': 7,  # 保存しておくログファイル数
        },
        'file_web_order': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(BASE_DIR, "logs/web_order.log"),
            'formatter': 'create_order_blank',
            'when': 'D',
            'interval': 1,
            'backupCount': 35,
        },
    },

    # フォーマッタの設定
    'formatters': {
        'prod': {
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

# 検食が無料なユニット
FREE_KENSYOKU_UNITS = ['10044']

# --食数固定製造分ID(朝、昼、夕)--
# 常食保存用(1人用袋)
ORDER_EVERYDAY_PRESERVE_1PACK_ID_J = [7, 8, 9]

# 薄味保存用(1人用袋)
ORDER_EVERYDAY_PRESERVE_1PACK_ID_U = [10, 11, 12]

# 常食写真用(1人用袋)
ORDER_EVERYDAY_FOR_PHOTO_ID_J = [22, 23, 24]

# 常食保存用(50g)
ORDER_EVERYDAY_PRESERVE_50G_ID_J = [43, 44, 45]

# 嚥下保存用(50g)
ORDER_EVERYDAY_PRESERVE_50G_ID_S = [52, 53, 54]
ORDER_EVERYDAY_PRESERVE_50G_ID_Z = [46, 47, 48]
ORDER_EVERYDAY_PRESERVE_50G_ID_M = [49, 50, 51]
# -- --


# 食数集計のユニットの並び順
AGGREGATE_UNIT_SORT_ORDER = [
    41, 2, 40, 4, 5,
    6, 7, 3, 8, 9, 10,
    11, 12, 13, 14, 16,
    17, 42, 38, 39, 21,
    22, 23, 24, 25, 26,
    27, 28, 29, 31, 32,
    33, 34, 35, 36, 37,
    43, 44, 45, 46, 48,
    49, 55, 56, 57, 58,
    59, 60, 61, 62, 63,
    50, 51, 52, 53, 64,
    65, 66, 70
]

# 製造作成表:施設・献立種類毎の表の最大行(現在は未使用)
COOK_PRODUCT_UNIT_ROW_MAX = 69

# 請求書会社コード変換対象(ここに定義されたコードは、先頭に9を付与したuseridを使う)
CONVERT_INVERT_USERID_TO_PARENTS = [
    '10002',
    '10004',
    '10022',
    '10053',
    '10037',
    '10055',
    '10066',
    '10070',
    '10084',
    '10090',
    '10096',
    '10101',
    '10132',
    '22029',
]

# 食数集計:木沢個食の食種
KIZAWA_RAKUKON_CODE = '木沢個'
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
BASIC_PLATE_ENABLE_DATE = '2023-01-31'

# 混ぜご飯計量表出力で、集約するユニットの呼び出し番号。先頭要素の施設名を採用する
MIX_RICE_AGGREGATE_UNITS = [
    [4, 5, 6, 7]
]

KOSHOKU_UNIT_IDS = [82, 83]
FREEZE_UNIT_IDS = []

# P7献立読込スタブモード
STUB_MODE_P7_READ = False
IGNORE_ALLERGEN_RERATION_BACKUP = False
DEBUG_READ_PICKING_RESULT = False
ADJUST_PICKING_DAY = 0

# 喫食日・売上日関連(補正日と、有効日のタプル)
EATING_SALES_SETTINGS = [
    (2, '2000-01-01'),
    (3, '2024-03-01')
]

# 食数変更起源関連(バージョンと、有効日のタプル)
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
PICKING_RESULT_AUTO_RELOAD_INTERVAL = 5 * 60 * 1000

# 頻発アレルギー設定画面：インデックス補正値
COMMON_ALLERGEN_MINIMUM_INDEX = 24

# 他システムからのWebAPI呼出時の認証キー
WEB_API_KEY = os.environ.get('API_KEY_ID')

