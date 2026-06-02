from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('staff', 'Staff / Driver'),
                    ('auditor', 'Auditor (Read-Only)'),
                    ('manager', 'Motorpool Manager'),
                    ('maintenance', 'Maintenance Technician'),
                ],
                default='staff',
                max_length=20,
            ),
        ),
    ]