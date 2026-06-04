from django.contrib import admin
from django.db.models import Case, IntegerField, Value, When

from .models import (
    Asset, AssetRequest, AssetRequestNotification,
    MaintenanceNotification, MaintenanceRequest, MileageLog,
    AssetUsageRequest,
)


# ── helper annotation ─────────────────────────────────────────────────────────

PRIORITY_RANK = Case(
    When(priority='urgent', then=Value(0)),
    When(priority='high',   then=Value(1)),
    When(priority='medium', then=Value(2)),
    When(priority='low',    then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display   = ['asset_tag', 'name', 'asset_type', 'status', 'department', 'mileage', 'next_maintenance_date']
    list_filter    = ['asset_type', 'status', 'department']
    search_fields  = ['asset_tag', 'name', 'make', 'model_name', 'license_plate', 'serial_number']
    date_hierarchy = 'next_maintenance_date'
    fieldsets = (
        ('Identification', {'fields': ('asset_type', 'name', 'asset_tag', 'make', 'model_name', 'year', 'serial_number')}),
        ('Status & Location', {'fields': ('status', 'department', 'location')}),
        ('Financial', {'fields': ('procurement_cost', 'current_value', 'procurement_date'), 'classes': ('collapse',)}),
        ('Vehicle', {'fields': ('mileage', 'fuel_type', 'license_plate', 'next_service_km')}),
        ('Maintenance Schedule', {'fields': ('next_maintenance_date', 'last_maintenance_date', 'notes')}),
    )


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display   = ['work_order_number', 'asset', 'title', 'priority_badge', 'status', 'submitted_by', 'scheduled_date', 'created_at']
    list_filter    = ['status', 'priority', 'asset__asset_type']
    search_fields  = ['work_order_number', 'title', 'asset__asset_tag']
    raw_id_fields  = ['asset', 'submitted_by', 'approved_by']
    date_hierarchy = 'scheduled_date'

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(priority_rank=PRIORITY_RANK)
            .order_by('priority_rank', 'created_at')
        )

    @admin.display(description='Priority', ordering='priority_rank')
    def priority_badge(self, obj):
        from django.utils.html import format_html
        colours = {
            'urgent': ('#dc2626', '#fff'),
            'high':   ('#ea580c', '#fff'),
            'medium': ('#d97706', '#fff'),
            'low':    ('#16a34a', '#fff'),
        }
        bg, fg = colours.get(obj.priority, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:4px;'
            'font-size:0.8em;font-weight:600;text-transform:uppercase">{}</span>',
            bg, fg, obj.get_priority_display()
        )


@admin.register(MileageLog)
class MileageLogAdmin(admin.ModelAdmin):
    list_display  = ['asset', 'driver', 'odometer', 'trip_km', 'log_date']
    list_filter   = ['log_date']
    search_fields = ['asset__asset_tag', 'driver__username']


@admin.register(AssetRequest)
class AssetRequestAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'name', 'asset_type', 'requested_by', 'status', 'created_at']
    list_filter   = ['status', 'asset_type']
    search_fields = ['name', 'requested_by__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AssetRequestNotification)
class AssetRequestNotificationAdmin(admin.ModelAdmin):
    list_display  = ['asset_request', 'recipient', 'is_read', 'created_at']
    list_filter   = ['is_read']
    search_fields = ['recipient__username']
    readonly_fields = ['created_at']


@admin.register(MaintenanceNotification)
class MaintenanceNotificationAdmin(admin.ModelAdmin):
    list_display  = ['maintenance_request', 'recipient', 'is_read', 'created_at']
    list_filter   = ['is_read', 'created_at']
    search_fields = ['recipient__username', 'maintenance_request__work_order_number']
    readonly_fields = ['created_at']


@admin.register(AssetUsageRequest)
class AssetUsageRequestAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'asset', 'requested_by', 'department', 'status', 'created_at']
    list_filter   = ['status', 'department']
    search_fields = ['asset__asset_tag', 'department']
    readonly_fields = ['created_at', 'updated_at']