# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm, FarmerRegistrationForm

def register_view(request):
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save()
            
            # Additional user type specific processing
            user_type = user_form.cleaned_data.get('user_type')
            
            if user_type == UserType.FARMER:
                farmer_form = FarmerRegistrationForm(request.POST)
                if farmer_form.is_valid():
                    # Process farmer-specific details
                    # You might want to create a FarmerProfile here
                    pass
            
            login(request, user)
            return redirect('home')
    else:
        user_form = CustomUserCreationForm()
    
    return render(request, 'users/register.html', {'form': user_form})