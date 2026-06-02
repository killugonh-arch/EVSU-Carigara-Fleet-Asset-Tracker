import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.http import JsonResponse

from .models import Asset, MaintenanceRequest, MileageLog, AssetRequest, AssetRequestStatus
from .models import AssetType, AssetStatus, MaintenanceStatus
from .forms import (AssetForm, MaintenanceRequestForm, MaintenanceApprovalForm,
                    MileageLogForm, AssetRequestForm, AssetRequestReviewForm)
from .filters import AssetFilter, MaintenanceFilter

audit = logging.getLogger('fleet.audit')


def _sync_asset_status(asset):
    """
    Derive and save the correct Asset.status from its open maintenance requests.

    Rules:
      - If any request is IN_PROGRESS or APPROVED  → asset = 'maintenance'
      - If any request is PENDING                  → asset = 'maintenance'  (Pending Review)
      - Otherwise (all completed / rejected / none) → asset = 'active'
        (but only if the asset was already in 'maintenance'; never demote
         a manually-set 'retired' or 'disposed')
    """
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


@login_required
def dashboard(request):
    today = timezone.now().date()
    user  = request.user

    assets_qs = Asset.objects.all()
    mr_qs     = MaintenanceRequest.objects.select_related('asset', 'submitted_by')

    if user.is_staff_role:
        mr_qs = mr_qs.filter(submitted_by=user)

    context = {
        'total_assets':   assets_qs.count(),
        'total_vehicles': assets_qs.filter(asset_type=AssetType.VEHICLE).count(),
        'active_assets':  assets_qs.filter(status=AssetStatus.AVAILABLE).count(),
        'in_maintenance': assets_qs.filter(status=AssetStatus.MAINTENANCE).count(),
        'overdue_count':  assets_qs.filter(next_maintenance_date__lt=today).count(),
        'pending_requests':  mr_qs.filter(status=MaintenanceStatus.PENDING).count(),
        'approved_requests': mr_qs.filter(status=MaintenanceStatus.APPROVED).count(),
        'recent_requests':   mr_qs.order_by('-created_at')[:5],
        'overdue_assets':    assets_qs.filter(next_maintenance_date__lt=today).order_by('next_maintenance_date')[:5],
        'today': today,
    }

    # Asset requests: staff sees own count; manager sees pending list on dashboard
    if user.is_staff_role:
        context['my_asset_requests'] = AssetRequest.objects.filter(requested_by=user).count()
    elif user.is_manager:
        pending_ars = AssetRequest.objects.select_related('requested_by').filter(
            status=AssetRequestStatus.PENDING
        ).order_by('created_at')
        context['pending_asset_requests'] = pending_ars.count()
        context['pending_asset_requests_list'] = pending_ars[:5]

    if user.can_see_financials:
        context['total_valuation']   = assets_qs.aggregate(v=Sum('current_value'))['v'] or 0
        context['total_procurement'] = assets_qs.aggregate(v=Sum('procurement_cost'))['v'] or 0

    return render(request, 'assets/dashboard.html', context)


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


@login_required
def maintenance_list(request):
    qs = MaintenanceRequest.objects.select_related('asset', 'submitted_by')
    if request.user.is_staff_role:
        qs = qs.filter(submitted_by=request.user)
    f = MaintenanceFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 15)
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
        # auto-generate title from asset + date if blank
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
    if request.user.is_auditor:
        messages.error(request, 'Auditors have read-only access.')
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
        mr.status      = request.POST.get('action', 'approved')
        mr.approved_by = request.user
        if mr.status == MaintenanceStatus.COMPLETED:
            mr.completed_date = timezone.now().date()
            Asset.objects.filter(pk=mr.asset_id).update(last_maintenance_date=mr.completed_date)
        mr.save()
        _sync_asset_status(mr.asset)
        audit.info(f'MR_STATUS_CHANGE by={request.user.username} wo={mr.work_order_number} status={mr.status}')
        messages.success(request, f'Work order {mr.work_order_number} updated to "{mr.get_status_display()}".')
    return redirect('maintenance_detail', pk=pk)


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
        Asset.objects.filter(asset_type='vehicle').values('pk', 'name', 'license_plate', 'asset_tag')
    )
    vehicles_json = [
        {'pk': v['pk'], 'name': v['name'], 'plate': v['license_plate'] or '', 'tag': v['asset_tag'] or ''}
        for v in vehicles
    ]
    return render(request, 'assets/mileage_form.html', {'form': form, 'vehicles_json': vehicles_json})


# ── Asset Requests ────────────────────────────────────────────────────────────

@login_required
def asset_request_list(request):
    """Staff sees own requests. Managers/auditors see all with status filter tabs."""
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
    # Staff: own requests only
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
    """Manager approves or rejects an asset request.
    On approval, automatically creates an Asset record with status=buying."""
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

        # Auto-create asset when approved
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
    # Find assets auto-created from this request (matched by notes field)
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
    # Only the requester or a manager can delete
    if not request.user.is_manager and ar.requested_by != request.user:
        messages.error(request, 'You may only delete your own requests.')
        return redirect('asset_request_list')
    # Only allow deletion of pending requests
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