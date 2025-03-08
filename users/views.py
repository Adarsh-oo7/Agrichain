from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from .forms import (
    CustomUserCreationForm, 
    FarmerRegistrationForm,
    GovernmentRegistrationForm,
    NonProfitRegistrationForm,
    CustomAuthenticationForm
)
from .models import UserType


def home(request):
    return render(request,'home.html')

def register_view(request):
    # Initialize forms
    user_form = CustomUserCreationForm()
    farmer_form = FarmerRegistrationForm()
    government_form = GovernmentRegistrationForm()
    nonprofit_form = NonProfitRegistrationForm()

    if request.method == 'POST':
        print("woring")
        user_form = CustomUserCreationForm(request.POST)
        user_type = request.POST.get('user_type')
        
        # Initialize profile_form to None
        profile_form = None
        
        # Only create and validate the form for the selected user type
        if user_type == UserType.GOVERNMENT:
            profile_form = GovernmentRegistrationForm(request.POST)
            government_form = profile_form
            # Empty the other forms so they don't interfere with validation
            # nonprofit_form = NonProfitRegistrationForm()
            # farmer_form = FarmerRegistrationForm()
        elif user_type == UserType.NON_PROFIT:
            profile_form = NonProfitRegistrationForm(request.POST)
            nonprofit_form = profile_form
            # Empty the other forms
            # government_form = GovernmentRegistrationForm()
            # farmer_form = FarmerRegistrationForm()
        elif user_type == UserType.FARMER:
            profile_form = FarmerRegistrationForm(request.POST)
            farmer_form = profile_form
            # Empty the other forms
            # government_form = GovernmentRegistrationForm()
            # nonprofit_form = NonProfitRegistrationForm()

        if user_form.is_valid() and (profile_form is None or profile_form.is_valid()):
            user = user_form.save()

            if profile_form:
                profile = profile_form.save(user)

            login(request, user)

            if user.user_type == UserType.GOVERNMENT:
                messages.success(request, f"High Priority Government Account created. Welcome {user.username}!")
            elif user.user_type == UserType.NON_PROFIT:
                messages.success(request, f"Medium Priority Non-Profit Account created. Welcome {user.username}!")
            else:
                messages.success(request, f"Farmer Account created. Welcome {user.username}!")

            return redirect('home')
        else:
            # Handle form errors
            for field, errors in user_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            if profile_form and profile_form.errors:
                for field, errors in profile_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")

    return render(request, 'users/register.html', {
        'user_form': user_form,
        'farmer_form': farmer_form,
        'government_form': government_form,
        'nonprofit_form': nonprofit_form,
    })



def login_view(request):
    """Handle user login with appropriate redirects and messages based on user type."""
    if request.user.is_authenticated:
        # Redirect already logged-in users
        return redirect('home')
        
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Customize welcome message based on user type
                if user.user_type == UserType.GOVERNMENT:
                    messages.success(request, f"Welcome back to your Government Account, {user.username}! (High Priority)")
                elif user.user_type == UserType.NON_PROFIT:
                    messages.success(request, f"Welcome back to your Non-Profit Account, {user.username}! (Medium Priority)")
                else:
                    messages.success(request, f"Welcome back to your Farmer Account, {user.username}!")
                
                # Get the next parameter or default to home
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    """Handle user logout with appropriate redirect and message."""
    user_type = request.user.user_type if request.user.is_authenticated else None
    logout(request)
    
    if user_type == UserType.GOVERNMENT:
        messages.info(request, "You have successfully logged out of your Government Account.")
    elif user_type == UserType.NON_PROFIT:
        messages.info(request, "You have successfully logged out of your Non-Profit Account.")
    else:
        messages.info(request, "You have successfully logged out.")
        
    return redirect('login')