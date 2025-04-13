from django.db import models
from django.conf import settings

class Farm(models.Model):
    CROP_CHOICES = [
        # Grains and Cereals
        ('wheat', 'Wheat'),
        ('rice', 'Rice'),
        ('corn', 'Corn'),  # Maize
        ('barley', 'Barley'),
        ('oats', 'Oats'),
        ('sorghum', 'Sorghum'),  # Jowar
        ('millet', 'Millet'),  # Includes Pearl Millet (Bajra), Finger Millet (Ragi)
        # Pulses and Legumes
        ('soybean', 'Soybean'),
        ('peanut', 'Peanut'),  # Groundnut
        ('bean', 'Bean'),  # Includes Rajma (Kidney Beans)
        ('pea', 'Pea'),  # Green Peas (Matar)
        ('lentil', 'Lentil'),  # Includes Masoor, Toor (Pigeon Pea)
        ('chickpea', 'Chickpea'),  # Chana
        ('mungbean', 'Mung Bean'),  # Moong
        # Cash Crops
        ('cotton', 'Cotton'),
        ('sugarcane', 'Sugarcane'),
        ('sunflower', 'Sunflower'),
        ('mustard', 'Mustard'),  # Sarson
        ('sesame', 'Sesame'),  # Til
        # Vegetables
        ('potato', 'Potato'),
        ('tomato', 'Tomato'),
        ('onion', 'Onion'),
        ('carrot', 'Carrot'),
        ('cabbage', 'Cabbage'),
        ('cauliflower', 'Cauliflower'),
        ('brinjal', 'Brinjal'),  # Eggplant/Aubergine
        ('okra', 'Okra'),  # Bhindi
        ('spinach', 'Spinach'),  # Palak
        ('chilli', 'Chilli'),  # Green Chilli
        ('bittergourd', 'Bitter Gourd'),  # Karela
        ('ridgegourd', 'Ridge Gourd'),  # Turai
        # Fruits
        ('banana', 'Banana (General)'),
        ('banana_robusta', 'Banana - Robusta'),
        ('banana_rasthali', 'Banana - Rasthali'),
        ('banana_poovan', 'Banana - Poovan'),
        ('banana_nendran', 'Banana - Nendran'),
        ('mango', 'Mango'),
        ('guava', 'Guava'),
        ('papaya', 'Papaya'),
        ('pomegranate', 'Pomegranate'),
        ('jackfruit', 'Jackfruit'),
        ('coconut', 'Coconut'),
    ]
    STATUS_CHOICES = [('green', 'Good Condition'), ('orange', 'Moderate Risk'), ('red', 'High Risk')]
    SOIL_CHOICES = [('loamy', 'Loamy'), ('clay', 'Clay'), ('sandy', 'Sandy'), ('silt', 'Silt')]
    CLIMATE_CHOICES = [('hot', 'Hot'), ('tropical', 'Tropical'), ('subtropical', 'Subtropical'), ('temperate', 'Temperate'), ('arid', 'Arid')]

    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    area = models.FloatField(default=1.0, help_text="Farm area in acres or hectares")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='green')
    soil_type = models.CharField(max_length=10, choices=SOIL_CHOICES)
    climate = models.CharField(max_length=15, choices=CLIMATE_CHOICES)
    recommended_crop = models.CharField(max_length=50, choices=CROP_CHOICES, null=True, blank=True)
    user_crop_preferences = models.CharField(max_length=50, choices=CROP_CHOICES, null=True, blank=True)
    oversupply_risk = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.farmer.username}'s Farm at ({self.latitude}, {self.longitude})"
    

class PricePrediction(models.Model):
    crop = models.CharField(max_length=100)
    date = models.DateField()
    predicted_price = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.crop} - {self.date}: ₹{self.predicted_price:.2f}"