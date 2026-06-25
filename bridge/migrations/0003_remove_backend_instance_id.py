from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bridge', '0002_statedefinition'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='backend',
            name='instance_id',
        ),
    ]
