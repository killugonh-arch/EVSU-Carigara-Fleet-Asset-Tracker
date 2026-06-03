from django.db import models
from django.conf import settings
from django.utils import timezone

class AssetType(models.TextChoices):
    VEHICLE   = 'vehicle',   'Vehicle'
    IT_EQUIPMENT = 'it',     'IT Equipment'
    OTHER     = 'other',     'Other'

class AssetStatus(models.TextChoices):
    AVAILABLE   = 'available',    'Available'
    IN_USE      = 'in_use',       'In Use'
    MAINTENANCE = 'maintenance',  'In Maintenance'
    ON_HOLD     = 'on_hold',      'On Hold'
    DISPOSED    = 'disposed',     'Disposed'

class MaintenanceStatus(models.TextChoices):
    PENDING   = 'pending',   'Pending Review'
    APPROVED  = 'approved',  'Approved'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    REJECTED  = 'rejected',  'Rejected'

class Priority(models.TextChoices):
    LOW    = 'low',    'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH   = 'high',   'High'
    URGENT = 'urgent', 'Urgent'

class MaintenanceFrequency(models.TextChoices):
    DAILY   = 'daily',   'Daily'
    WEEKLY  = 'weekly',  'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    ANNUALLY  = 'annually',  'Annually'

class Asset(models.Model):
    """
    Represents a university-owned vehicle or high-value IT asset.
    Financial fields (procurement_cost) are restricted at the API/template
    layer to MANAGER role only.
    """
    asset_type      = models.CharField(max_length=20, choices=AssetType.choices, default=AssetType.VEHICLE, db_index=True)
    name            = models.CharField(max_length=200)
    asset_tag       = models.CharField(max_length=50, unique=True, blank=True, help_text='Auto-generated if left blank (e.g. EVSU-VH-00042)')
    make            = models.CharField(max_length=100, blank=True)
    model_name      = models.CharField('Model', max_length=100, blank=True)
    year            = models.PositiveSmallIntegerField(null=True, blank=True)
    serial_number   = models.CharField(max_length=100, blank=True)
    status          = models.CharField(max_length=20, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE, db_index=True)
    department      = models.CharField(max_length=100, blank=True)
    location        = models.CharField(max_length=200, blank=True)

    procurement_cost  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_value     = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    procurement_date  = models.DateField(null=True, blank=True)

    mileage         = models.PositiveIntegerField(default=0, help_text='Current odometer reading (km)')
    fuel_type       = models.CharField(max_length=30, blank=True)
    license_plate   = models.CharField(max_length=30, blank=True)
    next_service_km = models.PositiveIntegerField(null=True, blank=True, help_text='Odometer reading at next scheduled service')

    next_maintenance_date = models.DateField(null=True, blank=True, db_index=True)
    last_maintenance_date = models.DateField(null=True, blank=True)
    first_maintenance_date = models.DateField(null=True, blank=True, help_text='Date of first scheduled maintenance')
    maintenance_frequency  = models.CharField(
        max_length=20, choices=MaintenanceFrequency.choices,
        blank=True, help_text='How often maintenance should occur'
    )

    notes    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['asset_type', 'name']
        indexes = [
            models.Index(fields=['asset_type', 'status']),
            models.Index(fields=['next_maintenance_date']),
        ]

    def __str__(self):
        return f'[{self.asset_tag}] {self.name}'

    def save(self, *args, **kwargs):
        # Auto-generate asset_tag if not provided
        if not self.asset_tag:
            prefix_map = {
                AssetType.VEHICLE:      'VH',
                AssetType.IT_EQUIPMENT: 'IT',
                AssetType.OTHER:        'OT',
            }
            prefix = prefix_map.get(self.asset_type, 'AS')
            super().save(*args, **kwargs)
            self.asset_tag = f'EVSU-{prefix}-{self.pk:05d}'
            Asset.objects.filter(pk=self.pk).update(asset_tag=self.asset_tag)
        else:
            super().save(*args, **kwargs)

    @property
    def maintenance_overdue(self):
        if self.next_maintenance_date:
            return self.next_maintenance_date < timezone.now().date()
        return False

    @property
    def service_km_alert(self):
        if self.next_service_km and self.asset_type == AssetType.VEHICLE:
            return self.mileage >= self.next_service_km
        return False

class MaintenanceRequest(models.Model):
    asset         = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_requests')
    submitted_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='submitted_requests'
    )
    approved_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_requests'
    )
    title         = models.CharField(max_length=200)
    description   = models.TextField()
    priority      = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, db_index=True)
    status        = models.CharField(max_length=20, choices=MaintenanceStatus.choices,
                                     default=MaintenanceStatus.PENDING, db_index=True)
    estimated_cost  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    requested_date  = models.DateField(default=timezone.now)
    scheduled_date  = models.DateField(null=True, blank=True, db_index=True)
    completed_date  = models.DateField(null=True, blank=True)

    work_order_number = models.CharField(max_length=50, blank=True, unique=True, null=True)
    vendor          = models.CharField(max_length=200, blank=True)
    notes           = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['scheduled_date']),
        ]

    def __str__(self):
        return f'{self.work_order_number or "WO-?"} – {self.title} ({self.asset})'

    def save(self, *args, **kwargs):
        if not self.work_order_number:
            super().save(*args, **kwargs)
            self.work_order_number = f'WO-{self.pk:06d}'
            MaintenanceRequest.objects.filter(pk=self.pk).update(work_order_number=self.work_order_number)
        else:
            super().save(*args, **kwargs)

class MileageLog(models.Model):
    """Driver-submitted mileage entries."""

    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    asset      = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='mileage_logs',
                                   limit_choices_to={'asset_type': AssetType.VEHICLE})
    driver     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name='mileage_logs')
    odometer   = models.PositiveIntegerField(help_text='Odometer reading at submission (km)')
    trip_km    = models.PositiveIntegerField(default=0, help_text='Distance covered this trip (km)')
    log_date   = models.DateField(default=timezone.now)
    purpose    = models.CharField(max_length=200, blank=True)
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Review fields (added in migration 0006)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                   default=STATUS_PENDING, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='reviewed_mileage_logs')
    review_notes = models.TextField(blank=True, help_text='Admin notes on approval/rejection')
    reviewed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-log_date', '-created_at']

    def __str__(self):
        return f'{self.asset.asset_tag} – {self.log_date} – {self.odometer} km'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.odometer > self.asset.mileage:
            Asset.objects.filter(pk=self.asset_id).update(mileage=self.odometer)


class AssetRequestStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class AssetRequest(models.Model):
    """Staff-submitted request for a new asset to be procured."""
    requested_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='asset_requests'
    )
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_asset_requests'
    )
    asset_type     = models.CharField(max_length=20, choices=AssetType.choices, default=AssetType.VEHICLE)
    name           = models.CharField(max_length=200, help_text='Requested asset name / description')
    make           = models.CharField(max_length=100, blank=True)
    model_name     = models.CharField('Model', max_length=100, blank=True)
    justification  = models.TextField(help_text='Why is this asset needed?')
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status         = models.CharField(max_length=20, choices=AssetRequestStatus.choices,
                                      default=AssetRequestStatus.PENDING, db_index=True)
    manager_notes  = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'AssetReq #{self.pk} – {self.name} ({self.get_status_display()})'


class AssetRequestNotification(models.Model):
    """Notification sent to the requester when a manager reviews their asset request."""
    asset_request = models.ForeignKey(
        AssetRequest,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_request_notifications',
    )
    message   = models.TextField()
    is_read   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'AssetRequestNotif for {self.recipient} – Request #{self.asset_request_id}'


class MaintenanceNotification(models.Model):
    """Notification sent to maintenance staff when a request is created or updated."""
    maintenance_request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='maintenance_notifications',
        limit_choices_to={'role': 'maintenance'},
    )
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Notification for {self.recipient} – {self.maintenance_request}'