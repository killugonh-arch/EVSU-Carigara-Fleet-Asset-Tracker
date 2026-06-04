from .models import AssetRequest, AssetRequestStatus, MaintenanceNotification, AssetRequestNotification


def pending_asset_requests(request):
    """Inject pending asset request count for the sidebar badge (managers only)."""
    if request.user.is_authenticated and hasattr(request.user, 'is_manager') and request.user.is_manager:
        return {'pending_nav_count': AssetRequest.objects.filter(status=AssetRequestStatus.PENDING).count()}
    return {'pending_nav_count': 0}


def maintenance_unread_notifications(request):
    """Inject unread notification count for sidebar badge (all authenticated users)."""
    if request.user.is_authenticated:
        count = MaintenanceNotification.objects.filter(recipient=request.user, is_read=False).count()
        return {'maintenance_notif_count': count}
    return {'maintenance_notif_count': 0}


def asset_request_unread_notifications(request):
    """Inject unread asset-request feedback count for staff users."""
    if request.user.is_authenticated and hasattr(request.user, 'is_staff_role') and request.user.is_staff_role:
        count = AssetRequestNotification.objects.filter(recipient=request.user, is_read=False).count()
        return {'asset_request_notif_count': count}
    return {'asset_request_notif_count': 0}