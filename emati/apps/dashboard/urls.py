from django.urls import path, include
from django.contrib.admin.views.decorators import staff_member_required

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', staff_member_required(views.MainView.as_view()), name='main'),
    
    path('ajax/stats', views.ajax_load_stats),
]