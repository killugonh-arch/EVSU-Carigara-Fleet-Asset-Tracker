from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0008_assetrequestnotification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Change Asset.department to use Department choices (max_length 100→20)
        migrations.AlterField(
            model_name='asset',
            name='department',
            field=models.CharField(
                blank=True,
                choices=[
                    ('IT', 'IT'),
                    ('EDUCATION', 'Education'),
                    ('STAFF', 'Staff'),
                    ('ENTREP', 'Entrep'),
                    ('FI', 'FI'),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        # Create AssetUsageRequest model
        migrations.CreateModel(
            name='AssetUsageRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.CharField(
                    choices=[
                        ('IT', 'IT'),
                        ('EDUCATION', 'Education'),
                        ('STAFF', 'Staff'),
                        ('ENTREP', 'Entrep'),
                        ('FI', 'FI'),
                    ],
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Approval'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                        ('released', 'Released'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('notes', models.TextField(blank=True)),
                ('manager_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_requests',
                    to='assets.asset',
                )),
                ('requested_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='asset_usage_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_usage_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]