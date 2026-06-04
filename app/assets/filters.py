import django_filters
from django.db.models import Q
from .models import Asset, MaintenanceRequest, MileageLog, AssetType, AssetStatus, MaintenanceStatus, Priority

class AssetFilter(django_filters.FilterSet):
    search     = django_filters.CharFilter(method='filter_search', label='Search')
    department = django_filters.CharFilter(method='filter_department', label='Department')
    next_maintenance_date_from = django_filters.DateFilter(field_name='next_maintenance_date', lookup_expr='gte')
    next_maintenance_date_to   = django_filters.DateFilter(field_name='next_maintenance_date', lookup_expr='lte')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(asset_tag__icontains=value)
        )

    def filter_department(self, queryset, name, value):
        # Staff are locked to their own department — ignore the filter value
        if self.user and not self.user.is_manager and not self.user.is_auditor and not self.user.is_maintenance:
            return queryset
        return queryset.filter(department__icontains=value)

    class Meta:
        model  = Asset
        fields = ['asset_type', 'status', 'department']

class MaintenanceFilter(django_filters.FilterSet):
    search         = django_filters.CharFilter(method='filter_search', label='Search')
    title          = django_filters.CharFilter(lookup_expr='icontains')
    submitted_by   = django_filters.CharFilter(field_name='submitted_by__username', lookup_expr='icontains')
    scheduled_date_after = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='gte')
    scheduled_date_before = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='lte')

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(work_order_number__icontains=value) | Q(asset__asset_tag__icontains=value)
        )

    class Meta:
        model  = MaintenanceRequest
        fields = ['status', 'priority']

class MileageFilter(django_filters.FilterSet):
    asset_tag  = django_filters.CharFilter(field_name='asset__asset_tag', lookup_expr='icontains')
    driver     = django_filters.CharFilter(field_name='driver__username', lookup_expr='icontains')
    date_from  = django_filters.DateFilter(field_name='log_date', lookup_expr='gte')
    date_to    = django_filters.DateFilter(field_name='log_date', lookup_expr='lte')

    class Meta:
        model  = MileageLog
        fields = ['asset', 'driver']
