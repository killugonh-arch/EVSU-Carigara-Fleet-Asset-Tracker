import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.http import JsonResponse

from .models import (Asset, MaintenanceRequest, MileageLog, AssetRequest,
                     AssetRequestStatus, MaintenanceNotification,
                     AssetRequestNotification, AssetUsageRequest,
                     AssetUsageRequestStatus, Department)
from .models import AssetType, AssetStatus, MaintenanceStatus
from .forms import (AssetForm, MaintenanceRequestForm, MaintenanceApprovalForm,
                    MileageLogForm, AssetRequestForm, AssetRequestReviewForm,
                    AssetUsageRequestForm)
from .filters import AssetFilter, MaintenanceFilter

audit = logging.getLogger('fleet.audit')

PRIORITY_RANK = Case(
    When(priority='urgent', then=Value(0)),
    When(priority='high',   then=Value(1)),
    When(priority='medium', then=Value(2)),
    When(priority='low',    then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _notify_technicians(mr, msg):
    from accounts.models import User
    for tech in User.objects.filter(role='maintenance', is_active=True):
        MaintenanceNotification.objects.create(
            maintenance_request=mr,
            recipient=tech,
            message=msg,
        )


def _notify_managers(mr, msg):
    from accounts.models import User
    for manager in User.objects.filter(role='manager', is_active=True):
        MaintenanceNotification.objects.create(
            maintenance_request=mr,
            recipient=manager,
            message=msg,
        )


# ─── dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    today = timezone.now().date()
    user  = request.user

    # Maintenance technicians get their own portal
    if user.is_maintenance:
        return redirect('maintenance_portal')

    assets_qs = Asset.objects.all()
    mr_qs     = MaintenanceRequest.objects.select_related('asset', 'submitted_by')

    if user.is_staff_role:
        mr_qs = mr_qs.filter(submitted_by=user)

    # Active maintenance orders: pending, approved, in_progress — sorted by priority
    active_statuses = [
        MaintenanceStatus.PENDING,
        MaintenanceStatus.APPROVED,
        MaintenanceStatus.IN_PROGRESS,
    ]
    active_requests = (
        mr_qs
        .filter(status__in=active_statuses)
        .annotate(priority_rank=PRIORITY_RANK)
        .order_by('priority_rank', '-created_at')[:5]
    )

    context = {
        'total_assets':   assets_qs.count(),
        'total_vehicles': assets_qs.filter(asset_type=AssetType.VEHICLE).count(),
        'active_assets':  assets_qs.filter(status=AssetStatus.AVAILABLE).count(),
        'in_maintenance': assets_qs.filter(status=AssetStatus.MAINTENANCE).count(),
        'pending_requests':  mr_qs.filter(status=MaintenanceStatus.PENDING).count(),
        'approved_requests': mr_qs.filter(status=MaintenanceStatus.APPROVED).count(),
        'active_requests':   active_requests,
        'today': today,
    }

    # Asset requests — visible to all non-maintenance users
    if user.is_staff_role:
        my_qs = AssetRequest.objects.filter(requested_by=user)
        my_pending = my_qs.filter(status=AssetRequestStatus.PENDING).order_by('created_at')
        # Stat card shows only MY pending count — decreases when manager approves
        context['total_asset_requests'] = my_pending.count()
        context['pending_asset_requests_count'] = my_pending.count()
        context['approved_asset_requests_count'] = my_qs.filter(status=AssetRequestStatus.APPROVED).count()
        context['rejected_asset_requests_count'] = my_qs.filter(status=AssetRequestStatus.REJECTED).count()
        context['pending_asset_requests_list'] = my_pending[:5]

    if user.is_manager or user.is_auditor:
        pending_ars = AssetRequest.objects.select_related('requested_by').filter(
            status=AssetRequestStatus.PENDING
        ).order_by('created_at')
        context['pending_asset_requests'] = pending_ars.count()
        context['pending_asset_requests_list'] = pending_ars[:5]
        context['total_asset_requests'] = AssetRequest.objects.count()
        context['pending_asset_requests_count'] = pending_ars.count()
        context['approved_asset_requests_count'] = AssetRequest.objects.filter(
            status=AssetRequestStatus.APPROVED
        ).count()

    if user.can_see_financials:
        # Monthly maintenance spend: sum of actual_cost on completed orders this month
        this_month_start = today.replace(day=1)
        context['monthly_maintenance_spend'] = (
            MaintenanceRequest.objects
            .filter(
                status=MaintenanceStatus.COMPLETED,
                updated_at__date__gte=this_month_start,
            )
            .aggregate(v=Sum('actual_cost'))['v'] or 0
        )
        context['total_procurement'] = assets_qs.aggregate(v=Sum('procurement_cost'))['v'] or 0

    # Ensure all context keys exist for template rendering
    context.setdefault('rejected_asset_requests_count', 0)
    context.setdefault('total_asset_requests', 0)
    context.setdefault('pending_asset_requests_count', 0)
    context.setdefault('approved_asset_requests_count', 0)

    return render(request, 'assets/dashboard.html', context)


# ─── maintenance portal (for MAINTENANCE role) ────────────────────────────────

@login_required
def maintenance_portal(request):
    if not request.user.is_maintenance:
        messages.error(request, 'Access restricted to Maintenance Technicians.')
        return redirect('dashboard')

    user = request.user
    today = timezone.now().date()

    # Unread notifications for this technician
    unread_notifs = MaintenanceNotification.objects.filter(
        recipient=user, is_read=False
    ).select_related('maintenance_request__asset').order_by('-created_at')

    # Work orders relevant to maintenance: approved or in_progress
    active_wos = MaintenanceRequest.objects.filter(
        status__in=[MaintenanceStatus.APPROVED, MaintenanceStatus.IN_PROGRESS]
    ).select_related('asset', 'submitted_by').annotate(priority_rank=PRIORITY_RANK).order_by('priority_rank', 'created_at')

    # Pending review — shown as urgent alert banner on portal
    pending_review = MaintenanceRequest.objects.filter(
        status=MaintenanceStatus.PENDING
    ).select_related('asset', 'submitted_by').annotate(priority_rank=PRIORITY_RANK).order_by('priority_rank', 'created_at')

    # Recently completed
    completed_wos = MaintenanceRequest.objects.filter(
        status=MaintenanceStatus.COMPLETED
    ).select_related('asset').order_by('-completed_date')[:10]

    context = {
        'unread_notifs': unread_notifs,
        'unread_count':  unread_notifs.count(),
        'active_wos':    active_wos,
        'completed_wos': completed_wos,
        'today':         today,
        'approved_count':    active_wos.filter(status=MaintenanceStatus.APPROVED).count(),
        'in_progress_count': active_wos.filter(status=MaintenanceStatus.IN_PROGRESS).count(),
        'pending_review':       pending_review,
        'pending_review_count': pending_review.count(),
    }
    return render(request, 'assets/maintenance_portal.html', context)


@login_required
def maintenance_notifications(request):
    # Maintenance notifications
    maint_qs = MaintenanceNotification.objects.filter(
        recipient=request.user
    ).select_related('maintenance_request__asset').order_by('-created_at')

    # Asset-request notifications
    ar_qs = AssetRequestNotification.objects.filter(
        recipient=request.user
    ).select_related('asset_request').order_by('-created_at')

    # Mark all unread as read on open
    maint_unread = list(maint_qs.filter(is_read=False).values_list('id', flat=True))
    ar_unread    = list(ar_qs.filter(is_read=False).values_list('id', flat=True))
    newly_read   = len(maint_unread) + len(ar_unread)
    if maint_unread:
        MaintenanceNotification.objects.filter(id__in=maint_unread).update(is_read=True)
    if ar_unread:
        AssetRequestNotification.objects.filter(id__in=ar_unread).update(is_read=True)

    # Merge and sort by date descending
    maint_items = [{'type': 'maintenance',   'obj': n, 'created_at': n.created_at} for n in maint_qs]
    ar_items    = [{'type': 'asset_request', 'obj': n, 'created_at': n.created_at} for n in ar_qs]
    all_notifs  = sorted(maint_items + ar_items, key=lambda x: x['created_at'], reverse=True)

    return render(request, 'assets/maintenance_notifications.html', {
        'notifications':    all_notifs,
        'total_count':      len(all_notifs),
        'newly_read_count': newly_read,
    })


@login_required
def maintenance_notification_mark_read(request, pk):
    notif = get_object_or_404(MaintenanceNotification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('maintenance_portal')


# ─── assets ───────────────────────────────────────────────────────────────────

@login_required
def asset_list(request):
    user = request.user
    qs = Asset.objects.all()

    # Regular staff/driver: only see assets assigned to their own department
    if not user.is_manager and not user.is_auditor and not user.is_maintenance:
        user_dept = (user.department or '').strip().upper()
        if user_dept:
            qs = qs.filter(department__iexact=user_dept)
        else:
            # No department assigned → show nothing until admin sets their dept
            qs = Asset.objects.none()
    # Managers, auditors, maintenance see all assets (no filter)

    f  = AssetFilter(request.GET, queryset=qs, user=user)
    paginator = Paginator(f.qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    # Attach pending usage request status for each asset (for the current user)
    pending_usage_asset_ids = set(
        AssetUsageRequest.objects.filter(
            requested_by=user,
            status=AssetUsageRequestStatus.PENDING,
        ).values_list('asset_id', flat=True)
    )
    approved_usage_asset_ids = set(
        AssetUsageRequest.objects.filter(
            requested_by=user,
            status=AssetUsageRequestStatus.APPROVED,
        ).values_list('asset_id', flat=True)
    )

    return render(request, 'assets/asset_list.html', {
        'filter': f,
        'assets': page,
        'query_string': query_params.urlencode(),
        'pending_usage_asset_ids': pending_usage_asset_ids,
        'approved_usage_asset_ids': approved_usage_asset_ids,
    })


@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)

    # Department users can only view assets from their own department
    user = request.user
    if not user.is_manager and not user.is_auditor and not user.is_maintenance:
        user_dept = (user.department or '').strip().upper()
        asset_dept = (asset.department or '').strip().upper()
        if not user_dept or (asset_dept and asset_dept != user_dept):
            messages.error(request, 'You can only view assets from your own department.')
            return redirect('asset_list')

    maintenance_requests = asset.maintenance_requests.select_related('submitted_by').order_by('-created_at')
    mileage_logs = asset.mileage_logs.select_related('driver').order_by('-log_date')[:10]

    # Active usage request for this asset
    active_usage = AssetUsageRequest.objects.filter(
        asset=asset,
        status__in=[AssetUsageRequestStatus.PENDING, AssetUsageRequestStatus.APPROVED]
    ).select_related('requested_by').first()

    # User's own pending/approved request for this asset
    my_usage_request = AssetUsageRequest.objects.filter(
        asset=asset, requested_by=user,
        status__in=[AssetUsageRequestStatus.PENDING, AssetUsageRequestStatus.APPROVED]
    ).first()

    return render(request, 'assets/asset_detail.html', {
        'asset': asset,
        'maintenance_requests': maintenance_requests,
        'mileage_logs': mileage_logs,
        'active_usage': active_usage,
        'my_usage_request': my_usage_request,
    })

@login_required
def asset_create(request):
    if not request.user.is_manager:
        messages.error(request, 'Only managers may add assets.')
        return redirect('asset_list')
    # Pre-fill department from the logged-in manager's own department
    initial = {}
    if request.user.department:
        initial['department'] = request.user.department.upper()
    form = AssetForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        asset = form.save()
        audit.info(f'ASSET_CREATED by={request.user.username} asset_tag={asset.asset_tag}')
        from django.urls import reverse
        detail_url = reverse('asset_detail', args=[asset.pk])
        messages.success(request, f'Asset created: {asset.asset_tag} — {asset.name}', extra_tags=f'link:{detail_url}')
        return redirect('asset_list')
    return render(request, 'assets/asset_form.html', {'form': form, 'title': 'Add Asset'})


@login_required
def asset_edit(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers may edit assets.')
        return redirect('asset_list')
    asset = get_object_or_404(Asset, pk=pk)
    form  = AssetForm(request.POST or None, instance=asset)
    if request.method == 'POST' and form.is_valid():
        form.save()
        audit.info(f'ASSET_UPDATED by={request.user.username} asset_tag={asset.asset_tag}')
        messages.success(request, 'Asset updated.')
        return redirect('asset_detail', pk=pk)
    return render(request, 'assets/asset_form.html', {'form': form, 'title': 'Edit Asset', 'asset': asset})


@login_required
def asset_bulk_update(request):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can perform bulk updates.')
        return redirect('asset_list')
    if request.method == 'POST':
        asset_ids  = request.POST.getlist('asset_ids')
        new_status = request.POST.get('bulk_status')
        valid_statuses = [s[0] for s in AssetStatus.choices]
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('asset_list')
        updated = Asset.objects.filter(pk__in=asset_ids).update(status=new_status)
        audit.info(f'BULK_STATUS_UPDATE by={request.user.username} ids={asset_ids} status={new_status} count={updated}')
        messages.success(request, f'{updated} asset(s) updated to "{new_status}".')
    return redirect('asset_list')


@login_required
def asset_delete(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers may delete assets.')
        return redirect('asset_list')
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == 'POST':
        tag = asset.asset_tag
        asset.delete()
        audit.info(f'ASSET_DELETED by={request.user.username} asset_tag={tag}')
        messages.success(request, f'Asset {tag} has been deleted.')
        return redirect('asset_list')
    return render(request, 'assets/asset_confirm_delete.html', {'asset': asset})


# ─── maintenance ──────────────────────────────────────────────────────────────

@login_required
def maintenance_list(request):
    qs = MaintenanceRequest.objects.select_related('asset', 'submitted_by')
    if request.user.is_staff_role:
        qs = qs.filter(submitted_by=request.user)
    f = MaintenanceFilter(request.GET, queryset=qs)
    sorted_qs = f.qs.annotate(priority_rank=PRIORITY_RANK).order_by('priority_rank', 'created_at')
    paginator = Paginator(sorted_qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'assets/maintenance_list.html', {
        'filter': f,
        'requests': page,
        'query_string': query_params.urlencode(),
    })


@login_required
def maintenance_create(request):
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
        return redirect('maintenance_list')
    if request.user.is_maintenance:
        messages.error(request, 'Maintenance Technicians cannot submit work orders.')
        return redirect('maintenance_portal')
    assets_qs = Asset.objects.all().values('pk', 'name', 'asset_tag', 'license_plate', 'status', 'asset_type')
    assets_json = [
        {'pk': a['pk'], 'name': a['name'], 'tag': a['asset_tag'] or '',
         'plate': a['license_plate'] or '', 'status': a['status'], 'type': a['asset_type']}
        for a in assets_qs
    ]
    form = MaintenanceRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        mr = form.save(commit=False)
        mr.submitted_by = request.user
        mr.status = MaintenanceStatus.PENDING
        if not mr.title:
            from django.utils import timezone as _tz
            mr.title = f'{mr.asset.name} – {_tz.localdate().strftime("%b %d, %Y")}'
        mr.save()
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.ON_HOLD)
        audit.info(f'MR_CREATED by={request.user.username} wo={mr.work_order_number} asset={mr.asset.asset_tag}')
        from django.urls import reverse
        detail_url = reverse('maintenance_detail', args=[mr.pk])
        messages.success(request, f'Work order submitted: {mr.work_order_number}', extra_tags=f'link:{detail_url}')
        return redirect('maintenance_list')
    return render(request, 'assets/maintenance_form.html', {
        'form': form,
        'title': 'New Maintenance Request',
        'assets_json': assets_json,
    })


@login_required
def maintenance_edit(request, pk):
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
        return redirect('maintenance_detail', pk=pk)
    if request.user.is_maintenance:
        messages.error(request, 'Maintenance Technicians cannot edit work orders.')
        return redirect('maintenance_portal')
    if mr.status == MaintenanceStatus.COMPLETED:
        if not request.user.is_manager:
            messages.error(request, 'Completed work orders cannot be edited.')
            return redirect('maintenance_detail', pk=pk)
    if request.user.is_staff_role and mr.submitted_by != request.user:
        messages.error(request, 'You may only edit your own requests.')
        return redirect('maintenance_list')
    assets_qs = Asset.objects.all().values('pk', 'name', 'asset_tag', 'license_plate', 'status', 'asset_type')
    assets_json = [
        {'pk': a['pk'], 'name': a['name'], 'tag': a['asset_tag'] or '',
         'plate': a['license_plate'] or '', 'status': a['status'], 'type': a['asset_type']}
        for a in assets_qs
    ]
    form = MaintenanceRequestForm(request.POST or None, instance=mr)
    if request.method == 'POST' and form.is_valid():
        form.save()
        audit.info(f'MR_EDITED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} updated.')
        return redirect('maintenance_detail', pk=pk)
    return render(request, 'assets/maintenance_form.html', {
        'form': form,
        'title': f'Edit Work Order {mr.work_order_number}',
        'assets_json': assets_json,
        'edit_asset_pk': mr.asset_id,
        'edit_asset_label': mr.asset.name + (' — ' + mr.asset.asset_tag if mr.asset.asset_tag else '') + (' · ' + mr.asset.license_plate if mr.asset.license_plate else ''),
    })


@login_required
def maintenance_delete(request, pk):
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if request.user.is_auditor or request.user.is_maintenance:
        messages.error(request, 'You do not have permission to delete work orders.')
        return redirect('maintenance_list')
    if mr.status == MaintenanceStatus.COMPLETED:
        if not request.user.is_manager:
            messages.error(request, 'Completed work orders cannot be deleted.')
            return redirect('maintenance_detail', pk=pk)
    if not request.user.is_manager and mr.submitted_by != request.user:
        messages.error(request, 'You may only delete your own requests.')
        return redirect('maintenance_list')
    if request.method == 'POST':
        wo = mr.work_order_number
        mr.delete()
        audit.info(f'MR_DELETED by={request.user.username} wo={wo}')
        messages.success(request, f'Work order {wo} has been deleted.')
        return redirect('maintenance_list')
    return render(request, 'assets/maintenance_confirm_delete.html', {'mr': mr})


@login_required
def maintenance_detail(request, pk):
    mr = get_object_or_404(
        MaintenanceRequest.objects.select_related('asset', 'submitted_by', 'approved_by'),
        pk=pk
    )
    if request.user.is_staff_role and mr.submitted_by != request.user:
        audit.warning(f'IDOR_ATTEMPT by={request.user.username} tried MR pk={pk}')
        messages.error(request, 'You may only view your own requests.')
        return redirect('maintenance_list')
    approval_form = MaintenanceApprovalForm(instance=mr) if (request.user.is_manager and mr.status == MaintenanceStatus.PENDING) else None
    return render(request, 'assets/maintenance_detail.html', {'mr': mr, 'approval_form': approval_form})


@login_required
def maintenance_approve(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can approve work orders.')
        return redirect('maintenance_detail', pk=pk)
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.PENDING:
        messages.error(request, 'Only pending work orders can be approved or rejected.')
        return redirect('maintenance_detail', pk=pk)
    form = MaintenanceApprovalForm(request.POST, instance=mr)
    if form.is_valid():
        mr         = form.save(commit=False)
        action     = request.POST.get('action', 'approved')
        if action not in (MaintenanceStatus.APPROVED, MaintenanceStatus.REJECTED):
            messages.error(request, 'Invalid action.')
            return redirect('maintenance_detail', pk=pk)
        mr.status      = action
        mr.approved_by = request.user
        mr.save()
        if action == MaintenanceStatus.APPROVED:
            # Asset stays ON_HOLD until technician accepts
            Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.ON_HOLD)
            _notify_technicians(
                mr,
                f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} '
                f'has been APPROVED. Please accept or hold.'
            )
        else:
            # Rejected — return asset to available
            Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.AVAILABLE)
        audit.info(f'MR_MANAGER_ACTION by={request.user.username} wo={mr.work_order_number} status={mr.status}')
        messages.success(request, f'Work order {mr.work_order_number} updated to "{mr.get_status_display()}".')
    return redirect('maintenance_detail', pk=pk)


# ─── technician actions ───────────────────────────────────────────────────────

@login_required
def maintenance_accept(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can accept work orders.')
        return redirect('maintenance_detail', pk=pk)
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.APPROVED:
        messages.error(request, 'Only approved work orders can be accepted.')
        return redirect('maintenance_detail', pk=pk)
    if request.method == 'POST':
        mr.status = MaintenanceStatus.IN_PROGRESS
        mr.save()
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.MAINTENANCE)
        audit.info(f'MR_ACCEPTED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} accepted — asset is now In Maintenance.')
    return redirect('maintenance_detail', pk=pk)


@login_required
def maintenance_hold(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can put work orders on hold.')
        return redirect('maintenance_detail', pk=pk)
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.APPROVED:
        messages.error(request, 'Only approved work orders can be put on hold.')
        return redirect('maintenance_detail', pk=pk)
    if request.method == 'POST':
        # Status stays APPROVED; asset stays ON_HOLD — no change needed, just log it
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.ON_HOLD)
        audit.info(f'MR_HELD by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} held — asset remains On Hold.')
    return redirect('maintenance_detail', pk=pk)


@login_required
def maintenance_complete(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can mark work orders complete.')
        return redirect('maintenance_detail', pk=pk)
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.IN_PROGRESS:
        messages.error(request, 'Only in-progress work orders can be marked complete.')
        return redirect('maintenance_detail', pk=pk)
    if request.method == 'POST':
        mr.status         = MaintenanceStatus.COMPLETED
        mr.completed_date = timezone.now().date()
        mr.save()
        Asset.objects.filter(pk=mr.asset_id).update(
            status=AssetStatus.AVAILABLE,
            last_maintenance_date=mr.completed_date,
        )
        tech_name = request.user.get_full_name() or request.user.username
        completed_msg = (
            f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} '
            f'has been marked COMPLETED by technician {tech_name}. Asset is now Available.'
        )
        _notify_managers(mr, completed_msg)
        # Notify the person who submitted the maintenance request
        if mr.submitted_by and mr.submitted_by != request.user:
            MaintenanceNotification.objects.create(
                maintenance_request=mr,
                recipient=mr.submitted_by,
                message=(
                    f'Your maintenance request "{mr.title}" (Work Order {mr.work_order_number}) '
                    f'for [{mr.asset.asset_tag}] {mr.asset.name} has been COMPLETED by technician '
                    f'{tech_name} on {mr.completed_date}. The asset is now back to Available.'
                ),
            )
        audit.info(f'MR_COMPLETED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} completed — asset returned to Available.')
    return redirect('maintenance_detail', pk=pk)


@login_required
def maintenance_take(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can take work orders.')
        return redirect('maintenance_portal')
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.APPROVED:
        messages.error(request, 'Only approved work orders can be taken.')
        return redirect('maintenance_portal')
    if request.method == 'POST':
        mr.status = MaintenanceStatus.IN_PROGRESS
        mr.save()
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.MAINTENANCE)
        audit.info(f'MR_TAKEN by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} accepted — asset is now In Maintenance.')
    return redirect('maintenance_portal')


@login_required
def maintenance_pass(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can decline work orders.')
        return redirect('maintenance_portal')
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.APPROVED:
        messages.error(request, 'Only approved work orders can be declined.')
        return redirect('maintenance_portal')
    if request.method == 'POST':
        # Keep status as APPROVED — just log the pass; asset stays ON_HOLD
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.ON_HOLD)
        audit.info(f'MR_PASSED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} declined — another technician may take it.')
    return redirect('maintenance_portal')


@login_required
def maintenance_decline(request, pk):
    if not request.user.is_maintenance:
        messages.error(request, 'Only maintenance technicians can decline work orders.')
        return redirect('maintenance_detail', pk=pk)
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if mr.status != MaintenanceStatus.APPROVED:
        messages.error(request, 'Only approved work orders can be declined.')
        return redirect('maintenance_detail', pk=pk)
    if request.method == 'POST':
        mr.status = MaintenanceStatus.REJECTED
        mr.save()
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.ON_HOLD)
        audit.info(f'MR_DECLINED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} declined — asset set to On Hold.')
    return redirect('maintenance_portal')


# ─── mileage ──────────────────────────────────────────────────────────────────

@login_required
def mileage_log(request):
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
        return redirect('dashboard')
    form = MileageLogForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        log.driver = request.user
        log.save()
        audit.info(f'MILEAGE_LOGGED by={request.user.username} asset={log.asset.asset_tag} odometer={log.odometer}')
        messages.success(request, 'Mileage log saved.')
        return redirect('asset_detail', pk=log.asset.pk)
    vehicles = list(
        Asset.objects.filter(asset_type='vehicle').values('pk', 'name', 'license_plate', 'asset_tag', 'mileage')
    )
    vehicles_json = [
        {'pk': v['pk'], 'name': v['name'], 'plate': v['license_plate'] or '', 'tag': v['asset_tag'] or '', 'mileage': v['mileage']}
        for v in vehicles
    ]
    return render(request, 'assets/mileage_form.html', {'form': form, 'vehicles_json': vehicles_json})




@login_required
def mileage_log_list(request):
    """List and filter mileage logs — managers see all, staff see own"""
    qs = MileageLog.objects.select_related('asset','driver').order_by('-log_date')
    if request.user.is_staff_role:
        qs = qs.filter(driver=request.user)
    status_filter = request.GET.get('status','')
    if status_filter:
        qs = qs.filter(status=status_filter)
    counts = {
        'all':      qs.count(),
        'pending':  qs.filter(status='pending').count(),
        'approved': qs.filter(status='approved').count(),
        'rejected': qs.filter(status='rejected').count(),
    }
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'assets/mileage_log_list.html',
                  {'logs': page, 'status_filter': status_filter, 'counts': counts})


@login_required
def mileage_log_review(request, pk):
    """Review and approve/reject mileage logs — managers only"""
    log = get_object_or_404(MileageLog, pk=pk)
    if not request.user.is_manager and not request.user.is_auditor:
        if log.driver != request.user:
            messages.error(request, 'Access denied.')
            return redirect('mileage_log_list')
    if request.method == 'POST' and request.user.is_manager:
        action = request.POST.get('action')
        if action in ('approved', 'rejected'):
            log.status       = action
            log.reviewed_by  = request.user
            log.review_notes = request.POST.get('review_notes', '').strip()
            log.reviewed_at  = timezone.now()
            if action == 'approved':
                log.asset.mileage = log.odometer
                log.asset.save(update_fields=['mileage'])
            log.save()
            audit.info(f'MILEAGE_REVIEW by={request.user.username} log={pk} action={action}')
            messages.success(request, f'Mileage log {action}.')
            return redirect('mileage_log_list')
    review_notes = request.POST.get('review_notes', '') if request.method == 'POST' else ''
    return render(request, 'assets/Mileage_log_review.html', {'log': log, 'review_notes': review_notes})


# ─── asset requests ───────────────────────────────────────────────────────────

@login_required
def asset_request_list(request):
    if request.user.is_manager or request.user.is_auditor:
        qs = AssetRequest.objects.select_related('requested_by', 'reviewed_by').all()
        status_filter = request.GET.get('status', '')
        if status_filter:
            qs = qs.filter(status=status_filter)
        counts = {
            'all':      AssetRequest.objects.count(),
            'pending':  AssetRequest.objects.filter(status=AssetRequestStatus.PENDING).count(),
            'approved': AssetRequest.objects.filter(status=AssetRequestStatus.APPROVED).count(),
            'rejected': AssetRequest.objects.filter(status=AssetRequestStatus.REJECTED).count(),
        }
        return render(request, 'assets/asset_request_list.html', {
            'requests': qs,
            'status_filter': status_filter,
            'counts': counts,
        })
    qs = AssetRequest.objects.select_related('requested_by', 'reviewed_by').filter(requested_by=request.user)
    return render(request, 'assets/asset_request_list.html', {'requests': qs})


@login_required
def asset_request_create(request):
    if request.user.is_manager:
        messages.error(request, 'Managers do not submit asset requests.')
        return redirect('dashboard')
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
        return redirect('asset_request_list')
    if request.user.is_maintenance:
        messages.error(request, 'Maintenance Technicians do not submit asset requests.')
        return redirect('maintenance_portal')
    if request.user.is_superuser:
        messages.error(request, 'Admin accounts cannot submit asset requests.')
        return redirect('dashboard')
    form = AssetRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ar = form.save(commit=False)
        ar.requested_by = request.user
        # Automatically attach the staff member's department to the request
        if request.user.department:
            ar.department = request.user.department.upper()
        ar.save()
        audit.info(f'ASSET_REQUEST_CREATED by={request.user.username} id={ar.pk}')
        messages.success(request, f'Asset request #{ar.pk} submitted for review.')
        return redirect('asset_request_list')
    return render(request, 'assets/asset_request_form.html', {'form': form})


@login_required
def asset_request_review(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can review asset requests.')
        return redirect('asset_request_list')
    ar   = get_object_or_404(AssetRequest, pk=pk)
    form = AssetRequestReviewForm(request.POST or None, instance=ar)
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action', AssetRequestStatus.APPROVED)
        ar = form.save(commit=False)
        ar.status = action
        ar.reviewed_by = request.user
        ar.save()
        audit.info(f'ASSET_REQUEST_REVIEWED by={request.user.username} id={ar.pk} status={ar.status}')

        # Notify the requester about the decision + feedback
        reviewer_name = request.user.get_full_name() or request.user.username
        if action == AssetRequestStatus.APPROVED:
            notif_msg = f'Your asset request #{ar.pk} "{ar.name}" has been APPROVED by {reviewer_name}.'
        else:
            notif_msg = f'Your asset request #{ar.pk} "{ar.name}" has been REJECTED by {reviewer_name}.'
        if ar.manager_notes:
            notif_msg += f' Feedback: {ar.manager_notes}'
        if ar.requested_by:
            AssetRequestNotification.objects.create(
                asset_request=ar,
                recipient=ar.requested_by,
                message=notif_msg,
            )

        if action == AssetRequestStatus.APPROVED:
            # Use the requester's department
            requester_dept = (
                ar.requested_by.department.upper()
                if ar.requested_by and ar.requested_by.department
                else ''
            )
            new_asset = Asset.objects.create(
                asset_type=ar.asset_type,
                name=ar.name,
                make=ar.make,
                model_name=ar.model_name,
                procurement_cost=ar.estimated_cost,
                status=AssetStatus.AVAILABLE,
                department=requester_dept,
                notes=f'Created from Asset Request #{ar.pk}. Justification: {ar.justification}',
            )
            audit.info(f'ASSET_AUTO_CREATED from_request={ar.pk} asset_tag={new_asset.asset_tag} by={request.user.username}')
            from django.urls import reverse
            asset_url = reverse('asset_detail', args=[new_asset.pk])
            messages.success(
                request,
                f'Asset request #{ar.pk} approved. Asset {new_asset.asset_tag} created.',
                extra_tags=f'link:{asset_url}'
            )
        else:
            messages.success(request, f'Asset request #{ar.pk} marked as "{ar.get_status_display()}".')
        return redirect('asset_request_list')
    created_assets = Asset.objects.filter(notes__contains=f'Asset Request #{ar.pk}')
    return render(request, 'assets/asset_request_review.html', {
        'ar': ar, 'form': form, 'created_assets': created_assets,
    })


@login_required
def asset_request_notifications(request):
    notifs = AssetRequestNotification.objects.filter(recipient=request.user).select_related('asset_request')
    unread_ids = list(notifs.filter(is_read=False).values_list('id', flat=True))
    if unread_ids:
        AssetRequestNotification.objects.filter(id__in=unread_ids).update(is_read=True)
    return render(request, 'assets/asset_request_notifications.html', {'notifs': notifs})

@login_required
def combined_notifications(request):
    """Single unified notification page combining maintenance + asset-request notifications."""
    import itertools, datetime

    # Maintenance notifications for this user
    maint_qs = MaintenanceNotification.objects.filter(
        recipient=request.user
    ).select_related('maintenance_request__asset').order_by('-created_at')

    # Asset-request notifications for this user
    ar_qs = AssetRequestNotification.objects.filter(
        recipient=request.user
    ).select_related('asset_request').order_by('-created_at')

    # Mark all unread as read on open
    maint_unread = list(maint_qs.filter(is_read=False).values_list('id', flat=True))
    ar_unread    = list(ar_qs.filter(is_read=False).values_list('id', flat=True))
    newly_read   = len(maint_unread) + len(ar_unread)

    if maint_unread:
        MaintenanceNotification.objects.filter(id__in=maint_unread).update(is_read=True)
    if ar_unread:
        AssetRequestNotification.objects.filter(id__in=ar_unread).update(is_read=True)

    # Tag each item with its type so the template can branch
    maint_items = [{'type': 'maintenance', 'obj': n, 'created_at': n.created_at} for n in maint_qs]
    ar_items    = [{'type': 'asset_request', 'obj': n, 'created_at': n.created_at} for n in ar_qs]

    # Merge and sort descending by date
    all_notifs = sorted(maint_items + ar_items, key=lambda x: x['created_at'], reverse=True)

    return render(request, 'assets/combined_notifications.html', {
        'all_notifs': all_notifs,
        'newly_read': newly_read,
        'total':      len(all_notifs),
    })


@login_required
def asset_request_delete(request, pk):
    ar = get_object_or_404(AssetRequest, pk=pk)
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
        return redirect('asset_request_list')
    if not request.user.is_manager and ar.requested_by != request.user:
        messages.error(request, 'You may only delete your own requests.')
        return redirect('asset_request_list')
    if ar.status != AssetRequestStatus.PENDING:
        messages.error(request, 'Only pending requests can be deleted.')
        return redirect('asset_request_list')
    if request.method == 'POST':
        pk_ref = ar.pk
        ar.delete()
        audit.info(f'ASSET_REQUEST_DELETED by={request.user.username} id={pk_ref}')
        messages.success(request, f'Asset request #{pk_ref} has been deleted.')
        return redirect('asset_request_list')
    return render(request, 'assets/asset_request_confirm_delete.html', {'ar': ar})

# ─── Asset Usage Requests ─────────────────────────────────────────────────────

@login_required
def asset_usage_request(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    user  = request.user

    # Only non-manager, non-auditor, non-maintenance users can request
    if user.is_auditor or user.is_maintenance:
        messages.error(request, 'You do not have permission to request asset use.')
        return redirect('asset_detail', pk=pk)

    # Must have a department
    if not user.department:
        messages.error(request, 'Your account has no department assigned. Contact the administrator.')
        return redirect('asset_detail', pk=pk)

    # Asset must belong to user's department
    if asset.department and asset.department.upper() != user.department.upper():
        messages.error(request, f'This asset belongs to the {asset.get_department_display()} department. You cannot request it.')
        return redirect('asset_list')

    # Asset must be available
    if asset.status != AssetStatus.AVAILABLE:
        messages.error(request, 'This asset is not available for use.')
        return redirect('asset_detail', pk=pk)

    # Check for existing pending/approved request by this user
    existing = AssetUsageRequest.objects.filter(
        asset=asset, requested_by=user,
        status__in=[AssetUsageRequestStatus.PENDING, AssetUsageRequestStatus.APPROVED]
    ).first()
    if existing:
        messages.warning(request, 'You already have an active request for this asset.')
        return redirect('asset_detail', pk=pk)

    if request.method == 'POST':
        form = AssetUsageRequestForm(request.POST)
        if form.is_valid():
            usage_req = form.save(commit=False)
            usage_req.asset        = asset
            usage_req.requested_by = user
            usage_req.department   = user.department.upper()
            usage_req.save()
            audit.info(f'ASSET_USAGE_REQUEST asset={asset.asset_tag} by={user.username} dept={usage_req.department}')
            messages.success(request, f'Request submitted for "{asset.name}". Awaiting manager approval.')
            return redirect('asset_detail', pk=pk)
    else:
        form = AssetUsageRequestForm()

    return render(request, 'assets/asset_usage_request.html', {
        'asset': asset,
        'form':  form,
    })


@login_required
def asset_usage_request_list(request):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can review usage requests.')
        return redirect('asset_list')

    pending  = AssetUsageRequest.objects.filter(status=AssetUsageRequestStatus.PENDING).select_related('asset', 'requested_by')
    approved = AssetUsageRequest.objects.filter(status=AssetUsageRequestStatus.APPROVED).select_related('asset', 'requested_by')
    return render(request, 'assets/asset_usage_request_list.html', {
        'pending_requests':  pending,
        'approved_requests': approved,
    })


@login_required
def asset_usage_approve(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can approve requests.')
        return redirect('asset_usage_request_list')

    usage_req = get_object_or_404(AssetUsageRequest, pk=pk, status=AssetUsageRequestStatus.PENDING)

    if request.method == 'POST':
        usage_req.status      = AssetUsageRequestStatus.APPROVED
        usage_req.reviewed_by = request.user
        usage_req.manager_notes = request.POST.get('manager_notes', '')
        usage_req.save()
        # Update asset status to In Use and assign department
        Asset.objects.filter(pk=usage_req.asset_id).update(
            status=AssetStatus.IN_USE,
            department=usage_req.department,
        )
        audit.info(f'ASSET_USAGE_APPROVED req={pk} asset={usage_req.asset.asset_tag} by={request.user.username}')
        messages.success(request, f'Usage request approved. "{usage_req.asset.name}" is now In Use by {usage_req.department}.')
        return redirect('asset_usage_request_list')

    return redirect('asset_usage_request_list')


@login_required
def asset_usage_reject(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can reject requests.')
        return redirect('asset_usage_request_list')

    usage_req = get_object_or_404(AssetUsageRequest, pk=pk, status=AssetUsageRequestStatus.PENDING)

    if request.method == 'POST':
        usage_req.status       = AssetUsageRequestStatus.REJECTED
        usage_req.reviewed_by  = request.user
        usage_req.manager_notes = request.POST.get('manager_notes', '')
        usage_req.save()
        audit.info(f'ASSET_USAGE_REJECTED req={pk} asset={usage_req.asset.asset_tag} by={request.user.username}')
        messages.success(request, f'Usage request for "{usage_req.asset.name}" has been rejected.')
        return redirect('asset_usage_request_list')

    return redirect('asset_usage_request_list')


@login_required
def asset_usage_release(request, pk):
    usage_req = get_object_or_404(AssetUsageRequest, pk=pk, status=AssetUsageRequestStatus.APPROVED)
    user = request.user

    if not user.is_manager and usage_req.requested_by != user:
        messages.error(request, 'You can only release assets you requested.')
        return redirect('asset_detail', pk=usage_req.asset_id)

    if request.method == 'POST':
        usage_req.status = AssetUsageRequestStatus.RELEASED
        usage_req.save()
        Asset.objects.filter(pk=usage_req.asset_id).update(status=AssetStatus.AVAILABLE)
        audit.info(f'ASSET_USAGE_RELEASED req={pk} asset={usage_req.asset.asset_tag} by={user.username}')
        messages.success(request, f'"{usage_req.asset.name}" has been released and is now Available.')
        return redirect('asset_detail', pk=usage_req.asset_id)

    return render(request, 'assets/asset_usage_release.html', {'usage_req': usage_req})

# ─── Admin History Views ───────────────────────────────────────────────────────

@login_required
def admin_asset_request_history(request):
    if not request.user.is_manager and not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    qs = AssetRequest.objects.select_related('requested_by', 'reviewed_by').filter(
        status=AssetRequestStatus.APPROVED
    )

    status_filter = ''

    # Search by requester name or asset name
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(requested_by__first_name__icontains=search) |
            Q(requested_by__last_name__icontains=search) |
            Q(requested_by__username__icontains=search)
        )

    counts = {
        'approved': AssetRequest.objects.filter(status=AssetRequestStatus.APPROVED).count(),
    }

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'assets/admin_asset_request_history.html', {
        'requests': page,
        'status_filter': status_filter,
        'search': search,
        'counts': counts,
    })


@login_required
def admin_maintenance_request_history(request):
    if not request.user.is_manager and not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    qs = MaintenanceRequest.objects.select_related('asset', 'submitted_by', 'approved_by').all()

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Search by work order, asset name, or requester name
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(work_order_number__icontains=search) |
            Q(asset__name__icontains=search) |
            Q(submitted_by__first_name__icontains=search) |
            Q(submitted_by__last_name__icontains=search) |
            Q(submitted_by__username__icontains=search)
        )

    counts = {
        'all':       MaintenanceRequest.objects.count(),
        'pending':   MaintenanceRequest.objects.filter(status=MaintenanceStatus.PENDING).count(),
        'approved':  MaintenanceRequest.objects.filter(status=MaintenanceStatus.APPROVED).count(),
        'completed': MaintenanceRequest.objects.filter(status=MaintenanceStatus.COMPLETED).count(),
        'rejected':  MaintenanceRequest.objects.filter(status=MaintenanceStatus.REJECTED).count(),
    }

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'assets/admin_maintenance_request_history.html', {
        'requests': page,
        'status_filter': status_filter,
        'search': search,
        'counts': counts,
    })