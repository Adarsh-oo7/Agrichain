from django.db import models
from django.conf import settings

class Farm(models.Model):
    FARM_STATUS_CHOICES = [
        ('red', 'High Risk'),
        ('orange', 'Moderate Risk'),
        ('green', 'Good Condition'),
    ]

    CROP_CHOICES = [
        ('wheat', 'Wheat'),
        ('rice', 'Rice'),
        ('corn', 'Corn'),
        ('vegetables', 'Vegetables'),
        ('fruits', 'Fruits'),
    ]

    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Corrected here
    latitude = models.FloatField()
    longitude = models.FloatField()
    soil_type = models.CharField(max_length=50)
    climate = models.CharField(max_length=50)
    oversupply_risk = models.BooleanField(default=False)
    recommended_crop = models.CharField(max_length=50, choices=CROP_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=10, choices=FARM_STATUS_CHOICES, default='green')

    def __str__(self):
        return f"{self.farmer.username}'s Farm"
