from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User
from .forms import AdminUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password', 'company_name', 'facility_name', 'invoice_pass', 'dry_cold_type', 'seq_order')}),
        (_('Personal info'), {'fields': ('email',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_parent', 'is_staff', 'is_management', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
                                                )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('username', 'email', 'password1', 'password2'), }),)
    form = CustomUserChangeForm
    add_form = AdminUserCreationForm
    list_display = ('username', 'company_name', 'facility_name', 'dry_cold_type', 'seq_order')
    search_fields = ('username', 'email')
    ordering = ('seq_order', 'username')

admin.site.register(User, CustomUserAdmin)