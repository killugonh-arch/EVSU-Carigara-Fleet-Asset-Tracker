from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0002_assetrequest'),
    ]

    operations = [
        # Allow asset_tag to be blank (auto-generated on save)
        migrations.AlterField(
            model_name='asset',
            name='asset_tag',
            field=models.CharField(
                blank=True,
                help_text='Auto-generated if left blank (e.g. EVSU-VH-00042)',
                max_length=50,
                unique=True,
            ),
        ),
        # Add first_maintenance_date field
        migrations.AddField(
            model_name='asset',
            name='first_maintenance_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Date of first scheduled maintenance',
            ),
        ),
        # Add maintenance_frequency field
        migrations.AddField(
            model_name='asset',
            name='maintenance_frequency',
            field=models.CharField(
                blank=True,
                choices=[
                    ('daily',     'Daily'),
                    ('weekly',    'Weekly'),
                    ('monthly',   'Monthly'),
                    ('quarterly', 'Quarterly'),
                    ('annually',  'Annually'),
                ],
                help_text='How often maintenance should occur',
                max_length=20,
            ),
        ),
    ]