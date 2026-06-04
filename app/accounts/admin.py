from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ['username', 'full_name', 'email', 'role', 'department', 'is_active']
    list_filter   = ['role', 'is_active', 'department']
    fieldsets = UserAdmin.fieldsets + (
        ('Fleet Role', {'fields': ('role', 'department', 'phone', 'license_number', 'profile_picture')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Fleet Role', {'fields': ('role', 'department', 'phone', 'license_number')}),
    )

    @admin.display(description='Full Name', ordering='last_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'