from django.contrib import admin

from .models import UserProfile

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'newsletter', 'terms_consent']
    fields = ['user', 'newsletter', 'terms_consent']
    readonly_fields = ['user']

admin.site.register(UserProfile, UserProfileAdmin)