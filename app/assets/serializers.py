from rest_framework import serializers
from .models import Asset, MaintenanceRequest, MileageLog

class AssetSerializer(serializers.ModelSerializer):
    maintenance_overdue = serializers.BooleanField(read_only=True)
    service_km_alert    = serializers.BooleanField(read_only=True)
    status_display      = serializers.CharField(source='get_status_display', read_only=True)
    asset_type_display  = serializers.CharField(source='get_asset_type_display', read_only=True)

    class Meta:
        model  = Asset
        fields = [
            'id', 'asset_type', 'asset_type_display', 'name', 'asset_tag',
            'make', 'model_name', 'year', 'serial_number',
            'status', 'status_display', 'department', 'location',
            'mileage', 'fuel_type', 'license_plate', 'next_service_km',
            'next_maintenance_date', 'last_maintenance_date',
            'notes', 'maintenance_overdue', 'service_km_alert',
            'created_at', 'updated_at',

            'procurement_cost', 'current_value', 'procurement_date',
        ]

class AssetPublicSerializer(AssetSerializer):
    """Non-manager view — financial fields removed."""
    class Meta(AssetSerializer.Meta):
        fields = [f for f in AssetSerializer.Meta.fields
                  if f not in ('procurement_cost', 'current_value', 'procurement_date')]

class MaintenanceRequestSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    approved_by_name  = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    asset_tag         = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name        = serializers.CharField(source='asset.name', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    priority_display  = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model  = MaintenanceRequest
        fields = [
            'id', 'work_order_number', 'asset', 'asset_tag', 'asset_name',
            'submitted_by', 'submitted_by_name', 'approved_by', 'approved_by_name',
            'title', 'description', 'priority', 'priority_display',
            'status', 'status_display',
            'estimated_cost', 'actual_cost',
            'requested_date', 'scheduled_date', 'completed_date',
            'vendor', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'work_order_number', 'submitted_by', 'approved_by',
                            'created_at', 'updated_at']

class MileageLogSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.get_full_name', read_only=True)
    asset_tag   = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name  = serializers.CharField(source='asset.name', read_only=True)

    class Meta:
        model  = MileageLog
        fields = [
            'id', 'asset', 'asset_tag', 'asset_name',
            'driver', 'driver_name', 'odometer', 'trip_km',
            'log_date', 'purpose', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'driver', 'created_at']

class DashboardAlertSerializer(serializers.Serializer):
    """Mobile API: push alert checks for a driver's assigned vehicles."""
    asset_id     = serializers.IntegerField()
    asset_tag    = serializers.CharField()
    asset_name   = serializers.CharField()
    alert_type   = serializers.CharField()   # 'overdue_maintenance' | 'service_km'
    message      = serializers.CharField()

class FleetSummarySerializer(serializers.Serializer):
    """Manager-only fleet-wide financial summary."""
    total_assets        = serializers.IntegerField()
    total_vehicles      = serializers.IntegerField()
    total_it_equipment  = serializers.IntegerField()
    total_valuation     = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_procurement   = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending_requests    = serializers.IntegerField()
    overdue_maintenance = serializers.IntegerField()
