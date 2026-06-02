from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0005_alter_asset_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='mileagelog',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                default='pending',
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='mileagelog',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_mileage_logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='mileagelog',
            name='review_notes',
            field=models.TextField(blank=True, help_text='Admin notes on approval/rejection'),
        ),
        migrations.AddField(
            model_name='mileagelog',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Update the driver FK to add related_name
        migrations.AlterField(
            model_name='mileagelog',
            name='driver',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mileage_logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]