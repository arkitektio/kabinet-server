# Generated by Django 4.2.9 on 2024-07-16 13:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bridge", "0002_backend_kind_backend_name_alter_pod_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="backend",
            name="kind",
            field=models.CharField(default="unknown", max_length=1000),
        ),
        migrations.AlterField(
            model_name="repo",
            name="creator",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
