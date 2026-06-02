from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'get_full_name', 'email', 'role', 'department', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    fieldsets = UserAdmin.fieldsets + (
        ('Fleet Role', {'fields': ('role', 'department', 'phone', 'license_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Fleet Role', {'fields': ('role', 'department', 'phone', 'license_number')}),
    )
