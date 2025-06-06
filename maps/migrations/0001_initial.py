# Generated by Django 5.1.7 on 2025-04-03 15:16

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Farm",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("soil_type", models.CharField(max_length=50)),
                ("climate", models.CharField(max_length=50)),
                ("oversupply_risk", models.BooleanField(default=False)),
                (
                    "recommended_crop",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("wheat", "Wheat"),
                            ("rice", "Rice"),
                            ("corn", "Corn"),
                            ("vegetables", "Vegetables"),
                            ("fruits", "Fruits"),
                        ],
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("red", "High Risk"),
                            ("orange", "Moderate Risk"),
                            ("green", "Good Condition"),
                        ],
                        default="green",
                        max_length=10,
                    ),
                ),
                (
                    "farmer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
