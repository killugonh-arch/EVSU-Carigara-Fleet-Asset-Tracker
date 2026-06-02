from django.contrib import admin
from .models import Asset, MaintenanceRequest, MileageLog

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ['asset_tag', 'name', 'asset_type', 'status', 'department', 'mileage', 'next_maintenance_date']
    list_filter   = ['asset_type', 'status', 'department']
    search_fields = ['asset_tag', 'name', 'make', 'model_name', 'license_plate', 'serial_number']
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
    list_display  = ['work_order_number', 'asset', 'title', 'priority', 'status', 'submitted_by', 'scheduled_date']
    list_filter   = ['status', 'priority', 'asset__asset_type']
    search_fields = ['work_order_number', 'title', 'asset__asset_tag']
    raw_id_fields = ['asset', 'submitted_by', 'approved_by']
    date_hierarchy = 'scheduled_date'

@admin.register(MileageLog)
class MileageLogAdmin(admin.ModelAdmin):
    list_display  = ['asset', 'driver', 'odometer', 'trip_km', 'log_date']
    list_filter   = ['log_date']
    search_fields = ['asset__asset_tag', 'driver__username']

from .models import AssetRequest
@admin.register(AssetRequest)
class AssetRequestAdmin(admin.ModelAdmin):
    list_display = ['pk', 'name', 'asset_type', 'requested_by', 'status', 'created_at']
    list_filter  = ['status', 'asset_type']
