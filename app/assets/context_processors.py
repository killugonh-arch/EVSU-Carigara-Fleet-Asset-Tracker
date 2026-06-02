from .models import AssetRequest, AssetRequestStatus, MaintenanceNotification


def pending_asset_requests(request):
    """Inject pending asset request count for the sidebar badge (managers only)."""
    if request.user.is_authenticated and hasattr(request.user, 'is_manager') and request.user.is_manager:
        return {'pending_nav_count': AssetRequest.objects.filter(status=AssetRequestStatus.PENDING).count()}
    return {'pending_nav_count': 0}


def maintenance_unread_notifications(request):
    """Inject unread notification count for Maintenance Technician sidebar badge."""
    if request.user.is_authenticated and hasattr(request.user, 'is_maintenance') and request.user.is_maintenance:
        count = MaintenanceNotification.objects.filter(recipient=request.user, is_read=False).count()
        return {'maintenance_notif_count': count}
    return {'maintenance_notif_count': 0}