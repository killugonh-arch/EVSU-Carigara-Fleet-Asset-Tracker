from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from .api_views import (
    AssetViewSet, MaintenanceRequestViewSet, MileageLogViewSet,
    DashboardAlertsView, FleetSummaryView,
)

router = DefaultRouter()
router.register(r'assets',      AssetViewSet,              basename='asset')
router.register(r'maintenance', MaintenanceRequestViewSet, basename='maintenance')
router.register(r'mileage',     MileageLogViewSet,         basename='mileage')

urlpatterns = [
    path('', include(router.urls)),

    path('auth/token/',         TokenObtainPairView.as_view(),   name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(),      name='token_refresh'),
    path('auth/token/blacklist/', TokenBlacklistView.as_view(),  name='token_blacklist'),

    path('alerts/',       DashboardAlertsView.as_view(), name='alerts'),
    path('fleet-summary/', FleetSummaryView.as_view(),   name='fleet_summary'),
]
