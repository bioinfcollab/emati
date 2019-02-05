from django.urls import path, include

from . import views

urlpatterns = [
    path('', views.WelcomePageView.as_view(), name='welcome'),
    path('home/', views.HomePageView.as_view(), name='home'),
    path('terms/', views.TermsAndConditionsView.as_view(), name='terms_and_conditions'),
    path('terms/agree/', views.TermsAgreementView.as_view(), name='terms_agree'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('imprint/', views.ImprintView.as_view(), name='imprint'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('settings/', views.SettingsView.as_view(), name='settings'),

    path('log/click/<int:article_pk>', views.log_click, name='log_click'),
    path('log/like/<int:article_pk>', views.log_like, name='log_like'),
    path('log/dislike/<int:article_pk>', views.log_dislike, name='log_dislike'),

    # Overwrite some allauth pages with custom ones
    path('accounts/email/', views.ChangeEmailView.as_view(), name='change_email'),
    path('accounts/inactive/', views.account_inactive),
    path('accounts/password/change/', views.MyPasswordChangeView.as_view(), name='account_change_password'),
    path('accounts/social/signup/', views.social_signup_view),

    # Some custom account management pages
    path('accounts/delete', views.DeleteAccountView.as_view(), name='account_delete'),
    path('accounts/reset', views.ResetAccountView.as_view(), name='account_reset'),
    
    path('download_file', views.download_file, name='download_file'),
    path('ajax/load_more/home/', views.LoadMoreHome.as_view(), name='load_more_home'),
    path('ajax/get_uploaded_file_html/', views.get_uploaded_file_html, name='get_uploaded_file_html'),
]
