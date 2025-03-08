# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, FarmerProfile, GovernmentProfile, NonProfitProfile

class FarmerProfileInline(admin.StackedInline):
    model = FarmerProfile
    can_delete = False
    verbose_name_plural = 'Farmer Profile'
    fk_name = 'user'

class GovernmentProfileInline(admin.StackedInline):
    model = GovernmentProfile
    can_delete = False
    verbose_name_plural = 'Government Office Profile'
    fk_name = 'user'

class NonProfitProfileInline(admin.StackedInline):
    model = NonProfitProfile
    can_delete = False
    verbose_name_plural = 'Non-Profit Organization Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = []
    list_display = ('username', 'email', 'user_type', 'priority', 'phone_number', 'is_staff')
    list_filter = ('user_type', 'priority', 'is_staff', 'is_active')
    ordering = ('priority',)  # Order by priority in admin
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'priority', 'phone_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone_number')}),
    )
    
    def get_inlines(self, request, obj=None):
        if obj:
            if obj.user_type == 'FARMER':
                return [FarmerProfileInline]
            elif obj.user_type == 'GOVERNMENT':
                return [GovernmentProfileInline]
            elif obj.user_type == 'NON_PROFIT':
                return [NonProfitProfileInline]
        return []

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(FarmerProfile)
admin.site.register(GovernmentProfile)
admin.site.register(NonProfitProfile)