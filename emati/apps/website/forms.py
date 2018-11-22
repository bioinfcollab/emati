from datetime import datetime

from django import forms
from allauth.account.forms import LoginForm, SignupForm, ResetPasswordForm
from allauth.account.models import EmailAddress
from django.shortcuts import redirect
from django.contrib import messages

from .models import Recommendation


class MyLoginForm(LoginForm):
    """A form that only allows logging in with your primary email address.

    Django-allauth let's you add multiple emails. You could then log in with
    any one of your (unverified) addresses. This form fixes this by only
    allowing a user's primary email to be considered for log in.
    """

    def __init__(self, *args, **kwargs):
        super(MyLoginForm, self).__init__(*args, **kwargs)

        # Set IDs
        self.fields['login'].widget.attrs['id'] = "login-email"
        self.fields['password'].widget.attrs['id'] = "login-password"

        # Classes
        self.fields['login'].widget.attrs['class'] = "inputfield"
        self.fields['password'].widget.attrs['class'] = "inputfield"

        # Placeholders
        self.fields['login'].widget.attrs['placeholder'] = "E-Mail"
        self.fields['password'].widget.attrs['placeholder'] = "Password"

        # Remove labels
        self.fields['login'].label = ""
        self.fields['password'].label = ""
    

    def login(self, request, redirect_url=None):
        try:
            # This assumes users log in with email and not their username
            email = self.user_credentials()['email']
        except KeyError:
            # No email submitted -> just do the regular flow
            return super(MyLoginForm, self).login(request, redirect_url=redirect_url)
        
        try:
            email_address = EmailAddress.objects.get(user=self.user, email=email)
        except EmailAddress.DoesNotExist:
            return super(MyLoginForm, self).login(request, redirect_url)
        
        # Only allow logging in with your primary email
        if email_address.primary:
            return super(MyLoginForm, self).login(request, redirect_url)
        else:
            messages.warning(request, "You have to verify this E-Mail address before you can log in.")
            return redirect('account_login')


class MySignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super(MySignupForm, self).__init__(*args, **kwargs)

        # Set IDs
        self.fields['email'].widget.attrs['id'] = "login-email"
        self.fields['password1'].widget.attrs['id'] = "login-password"
        self.fields['password2'].widget.attrs['id'] = "login-password"

        # Classes
        self.fields['email'].widget.attrs['class'] = "inputfield"
        self.fields['password1'].widget.attrs['class'] = "inputfield"
        self.fields['password2'].widget.attrs['class'] = "inputfield"

        # Placeholders
        self.fields['email'].widget.attrs['placeholder'] = "E-Mail"
        self.fields['password1'].widget.attrs['placeholder'] = "Password"
        self.fields['password2'].widget.attrs['placeholder'] = "Repeat password"

        # Remove labels
        self.fields['email'].label = ""
        self.fields['password1'].label = ""
        self.fields['password2'].label = ""


class SearchForm(forms.Form):
    q = forms.CharField(
        label='', 
        required=False, 
        widget=forms.TextInput(attrs={
            'type': 'search',
            'placeholder': 'SEARCH ...',
            'id': 'search-query-field',
        }),
    )


class SettingsForm(forms.Form):
    """The form displayed on a user's settings page."""
    newsletter = forms.BooleanField(
        label='',
        required=False,
    )


class ChangeEmailForm(forms.Form):
    """Our own form for changing the primary email.

    Allauth does not support "changing" an email per se.
    Only adding new addresses and managing them manually.
    But we want only a very limited interface for the user.
    """
    new_email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())


    def __init__(self, *args, **kwargs):
        super(ChangeEmailForm, self).__init__(*args, **kwargs)

        # Placeholders
        self.fields['new_email'].widget.attrs['placeholder'] = "your.new@email.com"
        self.fields['password'].widget.attrs['placeholder'] = "********"



class MyResetPasswordForm(ResetPasswordForm):
    """Customizes the allauth form for password resetting."""
    def __init__(self, *args, **kwargs):
        super(MyResetPasswordForm, self).__init__(*args, **kwargs)

        self.fields['email'].widget.attrs['class'] = "inputfield"
        self.fields['email'].widget.attrs['placeholder'] = "E-Mail"
        self.fields['email'].label = ""