# Generated by Django 4.2.9 on 2024-07-07 10:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bridge", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="backend",
            name="kind",
            field=models.CharField(default="docker", max_length=1000),
        ),
        migrations.AddField(
            model_name="backend",
            name="name",
            field=models.CharField(default="unset", max_length=1000),
        ),
        migrations.AlterField(
            model_name="pod",
            name="status",
            field=models.CharField(default="PENDING", max_length=1000),
        ),
    ]