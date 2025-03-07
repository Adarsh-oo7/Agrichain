# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class UserType(models.TextChoices):
    FARMER = 'FARMER', 'Farmer'
    GOVERNMENT = 'GOVERNMENT', 'Government Organization'
    NON_PROFIT = 'NON_PROFIT', 'Non-Profit Organization'

class CustomUser(AbstractUser):
    user_type = models.CharField(
        max_length=20, 
        choices=UserType.choices,
        default=UserType.FARMER
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    def __str__(self):
        return self.username