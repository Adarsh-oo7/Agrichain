# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, UserType

class CustomUserCreationForm(UserCreationForm):
    user_type = forms.ChoiceField(
        choices=UserType.choices, 
        initial=UserType.FARMER
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 'user_type']

class FarmerRegistrationForm(forms.Form):
    farm_size = forms.FloatField(label="Farm Size (Hectares)")
    primary_crops = forms.CharField(label="Primary Crops")
    annual_income = forms.DecimalField(label="Annual Income")