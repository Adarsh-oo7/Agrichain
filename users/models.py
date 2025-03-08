# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class UserType(models.TextChoices):
    GOVERNMENT = 'GOVERNMENT', 'Government Office'  # Highest priority
    NON_PROFIT = 'NON_PROFIT', 'Non-Profit Organization'  # Medium priority
    FARMER = 'FARMER', 'Farmer'  # Lowest priority

class UserPriority(models.IntegerChoices):
    HIGH = 1, 'High'  # Government
    MEDIUM = 2, 'Medium'  # Non-profit
    LOW = 3, 'Low'  # Farmer

class CustomUser(AbstractUser):
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.FARMER
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    priority = models.IntegerField(
        choices=UserPriority.choices,
        default=UserPriority.LOW
    )
    
    def save(self, *args, **kwargs):
        # Set priority based on user_type when saving
        if self.user_type == UserType.GOVERNMENT:
            self.priority = UserPriority.HIGH
        elif self.user_type == UserType.NON_PROFIT:
            self.priority = UserPriority.MEDIUM
        else:  # FARMER
            self.priority = UserPriority.LOW
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.username
    
    class Meta:
        ordering = ['priority']  # Order by priority (lowest number first)

class FarmerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='farmer_profile')
    farm_name = models.CharField(max_length=100)
    farm_location = models.CharField(max_length=255)
    farm_size = models.FloatField(help_text="Size in acres")
    primary_crops = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.user.username}'s Farm: {self.farm_name}"

class GovernmentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='government_profile')
    organization_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    jurisdiction = models.CharField(max_length=100)
    official_email = models.EmailField()
    
    def __str__(self):
        return f"{self.organization_name} - {self.department}"

class NonProfitProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='nonprofit_profile')
    organization_name = models.CharField(max_length=100)
    mission_statement = models.TextField()
    registration_number = models.CharField(max_length=50)
    year_established = models.IntegerField()
    
    def __str__(self):
        return self.organization_name