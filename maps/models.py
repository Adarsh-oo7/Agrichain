# maps/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Farm(models.Model):
    STATUS_CHOICES = [
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('red', 'Red'),
    ]
    CROP_CHOICES = [
        ('wheat', 'Wheat'),
        ('rice', 'Rice'),
        ('corn', 'Corn'),
        ('barley', 'Barley'),
        ('oats', 'Oats'),
        ('sorghum', 'Sorghum'),
        ('millet', 'Millet'),
        ('soybean', 'Soybean'),
        ('peanut', 'Peanut'),
        ('bean', 'Bean'),
        ('pea', 'Pea'),
        ('lentil', 'Lentil'),
        ('chickpea', 'Chickpea'),
        ('mungbean', 'Mungbean'),
        ('cotton', 'Cotton'),
        ('sugarcane', 'Sugarcane'),
        ('sunflower', 'Sunflower'),
        ('mustard', 'Mustard'),
        ('sesame', 'Sesame'),
        ('potato', 'Potato'),
        ('tomato', 'Tomato'),
        ('onion', 'Onion'),
        ('carrot', 'Carrot'),
        ('cabbage', 'Cabbage'),
        ('cauliflower', 'Cauliflower'),
        ('brinjal', 'Brinjal'),
        ('okra', 'Okra'),
        ('spinach', 'Spinach'),
        ('chilli', 'Chilli'),
        ('bittergourd', 'Bittergourd'),
        ('ridgegourd', 'Ridgegourd'),
        ('banana', 'Banana'),
        ('banana_robusta', 'Banana Robusta'),
        ('banana_rasthali', 'Banana Rasthali'),
        ('banana_poovan', 'Banana Poovan'),
        ('banana_nendran', 'Banana Nendran'),
        ('mango', 'Mango'),
        ('guava', 'Guava'),
        ('papaya', 'Papaya'),
        ('pomegranate', 'Pomegranate'),
        ('jackfruit', 'Jackfruit'),
        ('coconut', 'Coconut'),
    ]

    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    area = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='green')
    soil_type = models.CharField(max_length=100)
    climate = models.CharField(max_length=100)
    recommended_crop = models.CharField(max_length=100, choices=CROP_CHOICES, blank=True)
    user_crop_preferences = models.CharField(max_length=100, choices=CROP_CHOICES, null=True, blank=True)
    planting_date = models.DateField(null=True, blank=True)
    yield_per_acre = models.FloatField(null=True, blank=True)
    oversupply_risk = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.farmer.username}'s farm at ({self.latitude}, {self.longitude})"

class PricePrediction(models.Model):
    crop = models.CharField(max_length=100)
    date = models.DateField()
    predicted_price = models.FloatField()

    def __str__(self):
        return f"{self.crop} on {self.date}: ₹{self.predicted_price}"