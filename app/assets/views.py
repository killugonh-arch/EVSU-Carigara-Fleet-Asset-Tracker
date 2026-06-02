import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.http import JsonResponse

from .models import (Asset, MaintenanceRequest, MileageLog, AssetRequest,
                     AssetRequestStatus, MaintenanceNotification)
from .models import AssetType, AssetStatus, MaintenanceStatus
from .forms import (AssetForm, MaintenanceRequestForm, MaintenanceApprovalForm,
                    MileageLogForm, AssetRequestForm, AssetRequestReviewForm)
from .filters import AssetFilter, MaintenanceFilter

audit = logging.getLogger('fleet.audit')

# Priority sort annotation: Urgent=0  High=1  Medium=2  Low=3
PRIORITY_RANK = Case(
    When(priority='urgent', then=Value(0)),
    When(priority='high',   then=Value(1)),
    When(priority='medium', then=Value(2)),
    When(priority='low',    then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _sync_asset_status(asset):
    open_statuses = [
        MaintenanceStatus.IN_PROGRESS,
        MaintenanceStatus.APPROVED,
        MaintenanceStatus.PENDING,
    ]
    has_open = asset.maintenance_requests.filter(status__in=open_statuses).exists()
    if has_open:
        if asset.status != AssetStatus.MAINTENANCE:
            Asset.objects.filter(pk=asset.pk).update(status=AssetStatus.MAINTENANCE)
    else:
        if asset.status == AssetStatus.MAINTENANCE:
            Asset.objects.filter(pk=asset.pk).update(status=AssetStatus.AVAILABLE)


def _broadcast_notification(mr, new_status):
    """
    Send a MaintenanceNotification to all active Maintenance Technician users
    whenever a work-order changes to an actionable status.
    """
    from accounts.models import User
    technicians = User.objects.filter(role='maintenance', is_active=True)
    if not technicians.exists():
        return

    status_messages = {
        'approved':    f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} has been APPROVED. Please proceed with scheduling.',
        'in_progress': f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} is now IN PROGRESS.',
        'completed':   f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} has been marked COMPLETED.',
        'rejected':    f'Work order {mr.work_order_number} for [{mr.asset.asset_tag}] {mr.asset.name} has been REJECTED by the manager.',
    }
    msg = status_messages.get(new_status)
    if not msg:
        return

    for tech in technicians:
        MaintenanceNotification.objects.create(
            maintenance_request=mr,
            recipient=tech,
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
        context['my_asset_requests'] = AssetRequest.objects.filter(requested_by=user).count()

    if user.is_manager:
        pending_ars = AssetRequest.objects.select_related('requested_by').filter(
            status=AssetRequestStatus.PENDING
        ).order_by('created_at')
        context['pending_asset_requests'] = pending_ars.count()
        context['pending_asset_requests_list'] = pending_ars[:5]

    # Asset request summary for all roles
    context['total_asset_requests'] = AssetRequest.objects.count()
    context['pending_asset_requests_count'] = AssetRequest.objects.filter(
        status=AssetRequestStatus.PENDING
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

    return render(request, 'assets/dashboard.html', context)


# ─── maintenance portal (for MAINTENANCE role) ────────────────────────────────

@login_required
def maintenance_portal(request):
    """Dedicated portal for Maintenance Technician users."""
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
    }
    return render(request, 'assets/maintenance_portal.html', context)


@login_required
def maintenance_notifications(request):
    """Full notifications list for Maintenance Technician."""
    if not request.user.is_maintenance:
        messages.error(request, 'Access restricted to Maintenance Technicians.')
        return redirect('dashboard')

    notifs = MaintenanceNotification.objects.filter(
        recipient=request.user
    ).select_related('maintenance_request__asset').order_by('-created_at')

    # Mark all as read when viewing the list
    unread_ids = list(notifs.filter(is_read=False).values_list('id', flat=True))
    if unread_ids:
        MaintenanceNotification.objects.filter(id__in=unread_ids).update(is_read=True)

    paginator = Paginator(notifs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'assets/maintenance_notifications.html', {
        'notifications': page,
        'newly_read_count': len(unread_ids),
    })


@login_required
def maintenance_notification_mark_read(request, pk):
    """Mark a single notification as read via AJAX or POST."""
    notif = get_object_or_404(MaintenanceNotification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('maintenance_portal')


# ─── assets ───────────────────────────────────────────────────────────────────

@login_required
def asset_list(request):
    qs = Asset.objects.all()
    f  = AssetFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'assets/asset_list.html', {
        'filter': f,
        'assets': page,
        'query_string': query_params.urlencode(),
    })


@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    maintenance_requests = asset.maintenance_requests.select_related('submitted_by').order_by('-created_at')
    mileage_logs = asset.mileage_logs.select_related('driver').order_by('-log_date')[:10]
    return render(request, 'assets/asset_detail.html', {
        'asset': asset,
        'maintenance_requests': maintenance_requests,
        'mileage_logs': mileage_logs,
    })


@login_required
def asset_create(request):
    if not request.user.is_manager:
        messages.error(request, 'Only managers may add assets.')
        return redirect('asset_list')
    form = AssetForm(request.POST or None)
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
        Asset.objects.filter(pk=mr.asset_id).update(status=AssetStatus.MAINTENANCE)
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
    if request.user.is_staff_role and mr.submitted_by != request.user:
        messages.error(request, 'You may only edit your own requests.')
        return redirect('maintenance_list')
    form = MaintenanceRequestForm(request.POST or None, instance=mr)
    if request.method == 'POST' and form.is_valid():
        form.save()
        audit.info(f'MR_EDITED by={request.user.username} wo={mr.work_order_number}')
        messages.success(request, f'Work order {mr.work_order_number} updated.')
        return redirect('maintenance_detail', pk=pk)
    return render(request, 'assets/maintenance_form.html', {
        'form': form,
        'title': f'Edit Work Order {mr.work_order_number}',
    })


@login_required
def maintenance_delete(request, pk):
    mr = get_object_or_404(MaintenanceRequest, pk=pk)
    if request.user.is_auditor or request.user.is_maintenance:
        messages.error(request, 'You do not have permission to delete work orders.')
        return redirect('maintenance_list')
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
    approval_form = MaintenanceApprovalForm(instance=mr) if request.user.is_manager else None
    return render(request, 'assets/maintenance_detail.html', {'mr': mr, 'approval_form': approval_form})


@login_required
def maintenance_approve(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Only managers can approve work orders.')
        return redirect('maintenance_detail', pk=pk)
    mr   = get_object_or_404(MaintenanceRequest, pk=pk)
    form = MaintenanceApprovalForm(request.POST, instance=mr)
    if form.is_valid():
        mr             = form.save(commit=False)
        new_status     = request.POST.get('action', 'approved')
        mr.status      = new_status
        mr.approved_by = request.user
        if mr.status == MaintenanceStatus.COMPLETED:
            mr.completed_date = timezone.now().date()
            Asset.objects.filter(pk=mr.asset_id).update(last_maintenance_date=mr.completed_date)
        mr.save()
        _sync_asset_status(mr.asset)

        # ── Broadcast notification to all Maintenance Technicians ──
        _broadcast_notification(mr, new_status)

        audit.info(f'MR_STATUS_CHANGE by={request.user.username} wo={mr.work_order_number} status={mr.status}')
        messages.success(request, f'Work order {mr.work_order_number} updated to "{mr.get_status_display()}".')
    return redirect('maintenance_detail', pk=pk)


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
        if action == AssetRequestStatus.APPROVED:
            new_asset = Asset.objects.create(
                asset_type=ar.asset_type,
                name=ar.name,
                make=ar.make,
                model_name=ar.model_name,
                procurement_cost=ar.estimated_cost,
                status=AssetStatus.AVAILABLE,
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