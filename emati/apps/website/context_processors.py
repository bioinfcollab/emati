"""
Custom context processors for automatically adding variables to templates.
"""

from django.conf import settings


def extra(request):
    """Some extra context variables available to every template."""
    return {
        'contact_email': settings.WEBSITE_CONTACT_EMAIL,
    }