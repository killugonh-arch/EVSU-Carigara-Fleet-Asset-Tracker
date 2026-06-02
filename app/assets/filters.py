import django_filters
from .models import Asset, MaintenanceRequest, MileageLog, AssetType, AssetStatus, MaintenanceStatus, Priority

class AssetFilter(django_filters.FilterSet):
    name         = django_filters.CharFilter(lookup_expr='icontains')
    asset_tag    = django_filters.CharFilter(lookup_expr='icontains')
    department   = django_filters.CharFilter(lookup_expr='icontains')
    next_maintenance_date_from = django_filters.DateFilter(field_name='next_maintenance_date', lookup_expr='gte')
    next_maintenance_date_to   = django_filters.DateFilter(field_name='next_maintenance_date', lookup_expr='lte')

    class Meta:
        model  = Asset
        fields = ['asset_type', 'status', 'department']

class MaintenanceFilter(django_filters.FilterSet):
    title          = django_filters.CharFilter(lookup_expr='icontains')
    asset          = django_filters.ModelChoiceFilter(queryset=Asset.objects.all())
    asset_tag      = django_filters.CharFilter(field_name='asset__asset_tag', lookup_expr='icontains')
    submitted_by   = django_filters.CharFilter(field_name='submitted_by__username', lookup_expr='icontains')
    scheduled_from = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='gte')
    scheduled_to   = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='lte')

    class Meta:
        model  = MaintenanceRequest
        fields = ['status', 'priority', 'asset']

class MileageFilter(django_filters.FilterSet):
    asset_tag  = django_filters.CharFilter(field_name='asset__asset_tag', lookup_expr='icontains')
    driver     = django_filters.CharFilter(field_name='driver__username', lookup_expr='icontains')
    date_from  = django_filters.DateFilter(field_name='log_date', lookup_expr='gte')
    date_to    = django_filters.DateFilter(field_name='log_date', lookup_expr='lte')

    class Meta:
        model  = MileageLog
        fields = ['asset', 'driver']
