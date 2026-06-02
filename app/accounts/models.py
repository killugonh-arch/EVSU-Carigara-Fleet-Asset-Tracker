from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Extended user model with university fleet roles.
    Roles:
      STAFF        – regular driver/staff: log requests, view own records
      AUDITOR      – read-only across all records, no financial data
      MANAGER      – full access including fleet valuation & procurement costs
    """
    STAFF = 'staff'
    AUDITOR = 'auditor'
    MANAGER = 'manager'

    ROLE_CHOICES = [
        (STAFF,   'Staff / Driver'),
        (AUDITOR, 'Auditor (Read-Only)'),
        (MANAGER, 'Motorpool Manager'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STAFF)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    license_number = models.CharField(max_length=50, blank=True, help_text='Driver license #')

    class Meta:
        verbose_name = 'User'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_manager(self):
        return self.role == self.MANAGER

    @property
    def is_auditor(self):
        return self.role == self.AUDITOR

    @property
    def is_staff_role(self):
        return self.role == self.STAFF

    @property
    def can_see_financials(self):
        """Only managers may see fleet valuation and procurement costs."""
        return self.role == self.MANAGER
