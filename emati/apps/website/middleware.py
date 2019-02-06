from django.shortcuts import redirect, reverse
from django.utils import timezone
from django.contrib import admin

from website.views import TermsAgreementView

class TermsAgreementMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, *args, **kwargs):
        if view_func.__name__ == TermsAgreementView.__name__:
            # Continue normal processing if we already are on the terms page
            return None
        elif request.path.startswith(reverse('account_logout')):
            # Enable logging-out without accepting our terms
            return None
        elif request.path.startswith(reverse('terms_and_conditions')):
            # Allow users to read our full terms before agreeing
            return None
        else:
            # All other pages are intercepted and redirected
            u = request.user
            if u.is_authenticated and not u.profile.terms_consent:
                return redirect('terms_agree')

        return None



class SetLastVisitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Update last visit time after request finished processing.
            request.user.profile.last_visit = timezone.now()
            request.user.profile.save()
        return self.get_response(request)
