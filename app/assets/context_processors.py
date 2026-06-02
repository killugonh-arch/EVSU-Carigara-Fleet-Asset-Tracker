from .models import AssetRequest, AssetRequestStatus

def pending_asset_requests(request):
    """Inject pending asset request count for the sidebar badge (managers only)."""
    if request.user.is_authenticated and hasattr(request.user, 'is_manager') and request.user.is_manager:
        return {'pending_nav_count': AssetRequest.objects.filter(status=AssetRequestStatus.PENDING).count()}
    return {'pending_nav_count': 0}