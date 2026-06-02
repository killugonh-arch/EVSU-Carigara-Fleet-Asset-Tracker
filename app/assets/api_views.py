from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from accounts.permissions import IsManager, IsManagerOrAuditor, IsManagerOrReadOwn
from .models import Asset, MaintenanceRequest, MileageLog, AssetType
from .serializers import (
    AssetSerializer, AssetPublicSerializer,
    MaintenanceRequestSerializer, MileageLogSerializer,
    DashboardAlertSerializer, FleetSummarySerializer,
)
from .filters import AssetFilter, MaintenanceFilter, MileageFilter

class AssetViewSet(viewsets.ModelViewSet):
    """
    list/retrieve   – all authenticated users (financial fields stripped for non-managers)
    create/update   – managers only
    destroy         – managers only
    """
    queryset         = Asset.objects.all()
    filter_backends  = [DjangoFilterBackend]
    filterset_class  = AssetFilter
    search_fields    = ['name', 'asset_tag', 'make', 'model_name', 'license_plate']
    ordering_fields  = ['name', 'asset_type', 'status', 'next_maintenance_date', 'mileage']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsManager()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.user.can_see_financials:
            return AssetSerializer
        return AssetPublicSerializer

class MaintenanceRequestViewSet(viewsets.ModelViewSet):
    queryset        = MaintenanceRequest.objects.select_related('asset', 'submitted_by', 'approved_by')
    serializer_class = MaintenanceRequestSerializer
    filterset_class  = MaintenanceFilter
    search_fields    = ['title', 'work_order_number', 'asset__asset_tag', 'vendor']
    ordering_fields  = ['created_at', 'scheduled_date', 'priority', 'status']

    def get_permissions(self):
        if self.action in ('destroy',):
            return [IsManager()]
        return [IsManagerOrReadOwn()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_staff_role:
            qs = qs.filter(submitted_by=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def approve(self, request, pk=None):
        """PATCH /api/maintenance/{id}/approve/"""
        mr = self.get_object()
        mr.status      = 'approved'
        mr.approved_by = request.user
        scheduled_date = request.data.get('scheduled_date')
        if scheduled_date:
            mr.scheduled_date = scheduled_date
        mr.save()
        return Response(self.get_serializer(mr).data)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def reject(self, request, pk=None):
        mr = self.get_object()
        mr.status = 'rejected'
        mr.notes  = request.data.get('reason', mr.notes)
        mr.save()
        return Response(self.get_serializer(mr).data)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def complete(self, request, pk=None):
        mr = self.get_object()
        mr.status         = 'completed'
        mr.completed_date = timezone.now().date()
        if 'actual_cost' in request.data:
            mr.actual_cost = request.data['actual_cost']
        mr.save()

        Asset.objects.filter(pk=mr.asset_id).update(last_maintenance_date=mr.completed_date)
        return Response(self.get_serializer(mr).data)

class MileageLogViewSet(viewsets.ModelViewSet):
    """Mobile-ready endpoint for drivers to submit odometer readings."""
    queryset         = MileageLog.objects.select_related('asset', 'driver')
    serializer_class = MileageLogSerializer
    filterset_class  = MileageFilter
    ordering_fields  = ['log_date', 'odometer']

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff_role:
            qs = qs.filter(driver=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)

class DashboardAlertsView(APIView):
    """
    GET /api/alerts/
    Returns maintenance overdue and service-km alerts for the requesting user.
    Managers see all. Staff/auditors see only vehicles assigned to them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        qs = Asset.objects.filter(asset_type=AssetType.VEHICLE)
        if request.user.is_staff_role:

            driver_assets = MileageLog.objects.filter(
                driver=request.user
            ).values_list('asset_id', flat=True).distinct()
            qs = qs.filter(pk__in=driver_assets)

        alerts = []
        for asset in qs:
            if asset.next_maintenance_date and asset.next_maintenance_date < today:
                alerts.append({
                    'asset_id':   asset.pk,
                    'asset_tag':  asset.asset_tag,
                    'asset_name': asset.name,
                    'alert_type': 'overdue_maintenance',
                    'message':    f'Maintenance overdue since {asset.next_maintenance_date}',
                })
            if asset.service_km_alert:
                alerts.append({
                    'asset_id':   asset.pk,
                    'asset_tag':  asset.asset_tag,
                    'asset_name': asset.name,
                    'alert_type': 'service_km',
                    'message':    f'Odometer {asset.mileage} km has reached service threshold ({asset.next_service_km} km)',
                })

        serializer = DashboardAlertSerializer(alerts, many=True)
        return Response(serializer.data)

class FleetSummaryView(APIView):
    """
    GET /api/fleet-summary/
    Returns financial summary. JWT without can_see_financials=True returns 403.
    """
    permission_classes = [IsManager]

    def get(self, request):
        from django.db.models import Sum, Count
        today = timezone.now().date()
        assets = Asset.objects.all()

        data = {
            'total_assets':       assets.count(),
            'total_vehicles':     assets.filter(asset_type=AssetType.VEHICLE).count(),
            'total_it_equipment': assets.filter(asset_type='it').count(),
            'total_valuation':    assets.aggregate(v=Sum('current_value'))['v'] or 0,
            'total_procurement':  assets.aggregate(v=Sum('procurement_cost'))['v'] or 0,
            'pending_requests':   MaintenanceRequest.objects.filter(status='pending').count(),
            'overdue_maintenance': assets.filter(next_maintenance_date__lt=today).count(),
        }
        return Response(FleetSummarySerializer(data).data)
