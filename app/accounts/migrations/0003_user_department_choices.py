from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_maintenance_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='department',
            field=models.CharField(
                max_length=20,
                blank=True,
                choices=[
                    ('IT', 'IT'),
                    ('EDUCATION', 'Education'),
                    ('STAFF', 'Staff'),
                    ('ENTREP', 'Entrep'),
                    ('FI', 'FI'),
                ],
                help_text='Department this user belongs to (required for Staff role)',
            ),
        ),
    ]