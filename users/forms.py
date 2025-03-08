# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, UserType, UserPriority

class CustomUserCreationForm(UserCreationForm):
    user_type = forms.ChoiceField(
        choices=UserType.choices, 
        required=True,
        widget=forms.RadioSelect,
        initial=UserType.GOVERNMENT  # Default to highest priority
    )
    phone_number = forms.CharField(
        max_length=15, 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter phone number'})
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'user_type', 'phone_number')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = self.cleaned_data.get('user_type')
        user.phone_number = self.cleaned_data.get('phone_number')
        
        # Set priority based on user_type
        if user.user_type == UserType.GOVERNMENT:
            user.priority = UserPriority.HIGH
        elif user.user_type == UserType.NON_PROFIT:
            user.priority = UserPriority.MEDIUM
        else:  # FARMER
            user.priority = UserPriority.LOW
            
        if commit:
            user.save()
        return user

class FarmerRegistrationForm(forms.Form):
    farm_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Name of your farm'})
    )
    farm_location = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Farm location/address'})
    )
    farm_size = forms.FloatField(
        help_text="Size in acres",
        widget=forms.NumberInput(attrs={'placeholder': 'Farm size in acres', 'step': '0.01'})
    )
    primary_crops = forms.CharField(
        max_length=255, 
        help_text="Comma-separated list of crops",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Corn, Wheat, Soybeans'})
    )
    
    def save(self, user):
        from .models import FarmerProfile
        
        profile = FarmerProfile(
            user=user,
            farm_name=self.cleaned_data['farm_name'],
            farm_location=self.cleaned_data['farm_location'],
            farm_size=self.cleaned_data['farm_size'],
            primary_crops=self.cleaned_data['primary_crops']
        )
        profile.save()
        return profile

class GovernmentRegistrationForm(forms.Form):
    organization_name1 = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Name of government office'})
    )
    department = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Department/Division'})
    )
    jurisdiction = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Area of jurisdiction'})
    )
    official_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Official government email'})
    )
    
    def save(self, user):
        from .models import GovernmentProfile
        
        profile = GovernmentProfile(
            user=user,
            organization_name=self.cleaned_data['organization_name1'],
            department=self.cleaned_data['department'],
            jurisdiction=self.cleaned_data['jurisdiction'],
            official_email=self.cleaned_data['official_email']
        )
        profile.save()
        return profile

class NonProfitRegistrationForm(forms.Form):
    organization_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Name of non-profit organization'})
    )
    mission_statement = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Organization mission statement', 'rows': 4})
    )
    registration_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Official registration number'})
    )
    year_established = forms.IntegerField(
        widget=forms.NumberInput(attrs={'placeholder': 'Year established', 'min': '1800', 'max': '2025'})
    )
    
    def save(self, user):
        from .models import NonProfitProfile
        
        profile = NonProfitProfile(
            user=user,
            organization_name=self.cleaned_data['organization_name'],
            mission_statement=self.cleaned_data['mission_statement'],
            registration_number=self.cleaned_data['registration_number'],
            year_established=self.cleaned_data['year_established']
        )
        profile.save()
        return profile
