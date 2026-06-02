from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from accounts.models import User
from assets.models import Asset, MaintenanceRequest, MileageLog

class Command(BaseCommand):
    help = 'Seed database with demo data'

    def handle(self, *args, **options):
        today = date.today()

        manager, _ = User.objects.get_or_create(username='manager1', defaults={
            'first_name': 'Maria', 'last_name': 'Santos', 'role': User.MANAGER,
            'department': 'Motorpool', 'email': 'manager@university.edu',
        })
        manager.set_password('manager123'); manager.save()

        auditor, _ = User.objects.get_or_create(username='auditor1', defaults={
            'first_name': 'Juan', 'last_name': 'dela Cruz', 'role': User.AUDITOR,
            'department': 'Internal Audit',
        })
        auditor.set_password('auditor123'); auditor.save()

        driver1, _ = User.objects.get_or_create(username='driver1', defaults={
            'first_name': 'Pedro', 'last_name': 'Reyes', 'role': User.STAFF,
            'department': 'Motorpool', 'license_number': 'N01-23-456789',
        })
        driver1.set_password('driver123'); driver1.save()

        driver2, _ = User.objects.get_or_create(username='driver2', defaults={
            'first_name': 'Rosa', 'last_name': 'Aguirre', 'role': User.STAFF,
            'department': 'Motorpool',
        })
        driver2.set_password('driver123'); driver2.save()

        tech1, _ = User.objects.get_or_create(username='tech1', defaults={
            'first_name': 'Carlos', 'last_name': 'Mendoza', 'role': User.MAINTENANCE,
            'department': 'Motorpool', 'email': 'tech1@university.edu',
        })
        tech1.set_password('tech1234'); tech1.save()

        van01, _ = Asset.objects.get_or_create(asset_tag='UV-001', defaults=dict(
            asset_type='vehicle', name='Toyota HiAce (Van 01)', make='Toyota',
            model_name='HiAce', year=2020, license_plate='ABD 1234', fuel_type='Diesel',
            mileage=78400, next_service_km=80000, status='active', department='Motorpool',
            next_maintenance_date=today - timedelta(days=3),
            procurement_cost=1850000, current_value=1200000, procurement_date=date(2020, 6, 15)))

        van02, _ = Asset.objects.get_or_create(asset_tag='UV-002', defaults=dict(
            asset_type='vehicle', name='Mitsubishi L300 (Van 02)', make='Mitsubishi',
            model_name='L300', year=2019, license_plate='ABD 5678', fuel_type='Diesel',
            mileage=102000, next_service_km=110000, status='maintenance', department='Motorpool',
            next_maintenance_date=today + timedelta(days=14),
            procurement_cost=980000, current_value=560000, procurement_date=date(2019, 3, 10)))

        Asset.objects.get_or_create(asset_tag='PU-001', defaults=dict(
            asset_type='vehicle', name='Ford Ranger (Pickup 01)', make='Ford',
            model_name='Ranger', year=2022, license_plate='XYZ 9999', fuel_type='Diesel',
            mileage=35000, next_service_km=40000, status='active', department='Facilities',
            next_maintenance_date=today + timedelta(days=30),
            procurement_cost=1550000, current_value=1380000, procurement_date=date(2022, 1, 20)))

        server, _ = Asset.objects.get_or_create(asset_tag='IT-SRV-001', defaults=dict(
            asset_type='it', name='Dell Server R740', make='Dell',
            model_name='PowerEdge R740', year=2021, serial_number='SN-DELL-001234',
            status='active', department='IT Services',
            procurement_cost=320000, current_value=240000, procurement_date=date(2021, 8, 1),
            next_maintenance_date=today + timedelta(days=60)))

        Asset.objects.get_or_create(asset_tag='IT-NET-002', defaults=dict(
            asset_type='it', name='Cisco Switch (Core)', make='Cisco',
            model_name='Catalyst 9300', year=2020, serial_number='SN-CISCO-5678',
            status='active', department='IT Services',
            procurement_cost=185000, current_value=130000, procurement_date=date(2020, 4, 12),
            next_maintenance_date=today - timedelta(days=10)))

        mr1 = MaintenanceRequest(
            asset=van01, submitted_by=driver1, title='Engine oil change + filter',
            description='Due for 80k km service.', priority='high',
            status='pending', estimated_cost=4500, requested_date=today)
        mr1.save()

        mr2 = MaintenanceRequest(
            asset=van02, submitted_by=driver2, title='Brake pad replacement',
            description='Front brake pads worn.', priority='urgent',
            status='approved', approved_by=manager, estimated_cost=12000,
            scheduled_date=today + timedelta(days=2), requested_date=today - timedelta(days=1))
        mr2.save()

        mr3 = MaintenanceRequest(
            asset=server, submitted_by=manager, title='RAM upgrade & firmware update',
            description='Upgrade RAM from 64 GB to 128 GB.', priority='medium',
            status='completed', approved_by=manager, estimated_cost=28000, actual_cost=26500,
            requested_date=today - timedelta(days=15), completed_date=today - timedelta(days=5))
        mr3.save()

        # Use update_or_create so re-running seed never fails
        MileageLog.objects.update_or_create(
            asset=van01, driver=driver1, log_date=today,
            defaults=dict(odometer=78400, trip_km=120, purpose='Campus shuttle'))
        MileageLog.objects.update_or_create(
            asset=van01, driver=driver1, log_date=today - timedelta(days=1),
            defaults=dict(odometer=78280, trip_km=200, purpose='Airport transfer'))

        self.stdout.write(self.style.SUCCESS(
            '\nDemo data seeded!\n'
            '  manager1 / manager123      (Motorpool Manager)\n'
            '  auditor1 / auditor123      (Auditor)\n'
            '  driver1  / driver123       (Staff / Driver)\n'
            '  driver2  / driver123       (Staff / Driver)\n'
            '  tech1    / tech1234        (Maintenance Technician)\n'))