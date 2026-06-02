from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0004_alter_asset_status'),
    ]

    operations = [
        # Update status choices (TextChoices are stored as varchar; no schema change needed)
        migrations.AlterField(
            model_name='asset',
            name='status',
            field=models.CharField(
                choices=[
                    ('available',    'Available'),
                    ('in_use',       'In Use'),
                    ('maintenance',  'In Maintenance'),
                    ('on_hold',      'On Hold'),
                    ('disposed',     'Disposed'),
                ],
                db_index=True,
                default='available',
                max_length=20,
            ),
        ),
        # Migrate existing rows: buying/active → available, inactive → on_hold
        migrations.RunSQL(
            sql="""
                UPDATE assets_asset SET status = 'available' WHERE status IN ('buying', 'active');
                UPDATE assets_asset SET status = 'on_hold'   WHERE status = 'inactive';
            """,
            reverse_sql="""
                UPDATE assets_asset SET status = 'active'   WHERE status = 'available';
                UPDATE assets_asset SET status = 'inactive' WHERE status = 'on_hold';
            """,
        ),
    ]