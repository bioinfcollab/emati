from django.contrib import admin

from .models import UserProfile

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'newsletter', 'terms_consent']
    fields = ['user', 'newsletter', 'terms_consent', 'last_visit', 'recent_interactions']
    readonly_fields = ['user', 'last_visit', 'recent_interactions']

admin.site.register(UserProfile, UserProfileAdmin)