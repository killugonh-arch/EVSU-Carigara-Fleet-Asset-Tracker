from django.contrib.auth.models import AbstractUser
from django.db import models


DEPARTMENT_CHOICES = [
    ('IT',        'IT'),
    ('EDUCATION', 'Education'),
    ('STAFF',     'Staff'),
    ('ENTREP',    'Entrep'),
    ('FI',        'FI'),
]


class User(AbstractUser):
    STAFF       = 'staff'
    AUDITOR     = 'auditor'
    MANAGER     = 'manager'
    MAINTENANCE = 'maintenance'

    ROLE_CHOICES = [
        (STAFF,       'User/Staff'),
        (AUDITOR,     'Auditor '),
        (MANAGER,     'Manager'),
        (MAINTENANCE, 'Maintenance Technician'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STAFF)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True, blank=True,
        help_text='Profile photo'
    )
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        blank=True,
        help_text='Department this user belongs to (required for Staff role)',
    )
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
    def is_maintenance(self):
        return self.role == self.MAINTENANCE

    @property
    def can_see_financials(self):
        return self.role == self.MANAGER