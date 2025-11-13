import os

from django.contrib import admin
from django.contrib.staticfiles.urls import static
from django.urls import path, include

from . import settings_common, settings_dev

admin.site.site_header = os.environ.get('CUSTOMERNAME')
admin.site.site_title = os.environ.get('CUSTOMERNAME')
admin.site.index_title = os.environ.get('ADMINSITE_TITLE')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('web_order.urls')),
    path('accounts/', include('allauth.urls')),
]

# 開発サーバーでメディアを配信できるようにする設定
urlpatterns += static(settings_common.MEDIA_URL, document_root=settings_dev.MEDIA_ROOT)


if settings_dev.DEBUG:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
