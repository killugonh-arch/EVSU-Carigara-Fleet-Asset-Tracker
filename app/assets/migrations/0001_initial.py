

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_type', models.CharField(choices=[('vehicle', 'Vehicle'), ('it', 'IT Equipment'), ('other', 'Other')], db_index=True, default='vehicle', max_length=20)),
                ('name', models.CharField(max_length=200)),
                ('asset_tag', models.CharField(help_text='University asset tag / plate number', max_length=50, unique=True)),
                ('make', models.CharField(blank=True, max_length=100)),
                ('model_name', models.CharField(blank=True, max_length=100, verbose_name='Model')),
                ('year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('serial_number', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('active', 'Active'), ('maintenance', 'In Maintenance'), ('retired', 'Retired'), ('disposed', 'Disposed')], db_index=True, default='active', max_length=20)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('location', models.CharField(blank=True, max_length=200)),
                ('procurement_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('current_value', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('procurement_date', models.DateField(blank=True, null=True)),
                ('mileage', models.PositiveIntegerField(default=0, help_text='Current odometer reading (km)')),
                ('fuel_type', models.CharField(blank=True, max_length=30)),
                ('license_plate', models.CharField(blank=True, max_length=30)),
                ('next_service_km', models.PositiveIntegerField(blank=True, help_text='Odometer reading at next scheduled service', null=True)),
                ('next_maintenance_date', models.DateField(blank=True, db_index=True, null=True)),
                ('last_maintenance_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['asset_type', 'name'],
                'indexes': [models.Index(fields=['asset_type', 'status'], name='assets_asse_asset_t_be4ea2_idx'), models.Index(fields=['next_maintenance_date'], name='assets_asse_next_ma_1dfa93_idx')],
            },
        ),
        migrations.CreateModel(
            name='MileageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('odometer', models.PositiveIntegerField(help_text='Odometer reading at submission (km)')),
                ('trip_km', models.PositiveIntegerField(default=0, help_text='Distance covered this trip (km)')),
                ('log_date', models.DateField(default=django.utils.timezone.now)),
                ('purpose', models.CharField(blank=True, max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('asset', models.ForeignKey(limit_choices_to={'asset_type': 'vehicle'}, on_delete=django.db.models.deletion.CASCADE, related_name='mileage_logs', to='assets.asset')),
                ('driver', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-log_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MaintenanceRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], db_index=True, default='medium', max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=20)),
                ('estimated_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('actual_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('requested_date', models.DateField(default=django.utils.timezone.now)),
                ('scheduled_date', models.DateField(blank=True, db_index=True, null=True)),
                ('completed_date', models.DateField(blank=True, null=True)),
                ('work_order_number', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('vendor', models.CharField(blank=True, max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_requests', to=settings.AUTH_USER_MODEL)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_requests', to='assets.asset')),
                ('submitted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submitted_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['status', 'priority'], name='assets_main_status_9671b6_idx'), models.Index(fields=['scheduled_date'], name='assets_main_schedul_e44f43_idx')],
            },
        ),
    ]
