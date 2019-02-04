import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.mail import send_mass_mail, get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags, strip_spaces_between_tags
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from website.models import Recommendation


import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sends the newsletter to all subscribed users.'


    def handle(self, *args, **options):
        """The main entrypoint for this command."""
        mails = []
        subscribed_users = User.objects.filter(profile__newsletter=True)
        for user in subscribed_users:
            new_mail = self.create_newsletter(user)
            if new_mail is not None:
                mails.append(new_mail)
        
        logger.info("Sending newsletter to {} users.".format(len(mails)))

        # Only open a single connection to the mail server
        self.send_mass_html_mail(mails)


    def get_last_sunday(self):
        """Returns the last monday as YYYY-MM-DD"""
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        sunday = monday - datetime.timedelta(days=1)
        return sunday.strftime('%Y-%m-%d')

    
    def create_newsletter(self, user):
        """Composes a newsletter mail for the given user.

        Returns a tuple of the following form: 
        ('subject', 'txt_content', 'html_content', 'from@mail.com', 
        [to@mail.com])
        """

        # Get best three recommendations from last week
        recommendations = Recommendation.objects.filter(
            user=user,
            article__pubdate__gte=self.get_last_sunday()
        ).select_related('article')[:3]

        # Don't send any mail if no recommendations were found
        if not recommendations:
            return None

        context = {
            'recommendations': recommendations,
            'current_site': Site.objects.get_current(),
            'user': user
        }
        html_content = render_to_string('website/newsletter/newsletter.html', context)
        text_content = strip_tags(html_content)

        subject = settings.WEBSITE_NEWSLETTER_SUBJECT
        sender = settings.WEBSITE_NEWSLETTER_SENDER
        recipient = user.email
        return (subject, text_content, html_content, sender, [recipient])


    def send_mass_html_mail(self, datatuple, fail_silently=False, user=None, password=None, 
                            connection=None):
        """
        Given a datatuple of (subject, text_content, html_content, from_email,
        recipient_list), sends each message to each recipient list. Returns the
        number of emails sent.

        If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
        If auth_user and auth_password are set, they're used to log in.
        If auth_user is None, the EMAIL_HOST_USER setting is used.
        If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.
        """
        connection = connection or get_connection(
            username=user, password=password, fail_silently=fail_silently)
        messages = []
        for subject, text, html, from_email, recipient in datatuple:
            message = EmailMultiAlternatives(subject, text, from_email, recipient)
            message.attach_alternative(html, 'text/html')
            messages.append(message)
        return connection.send_messages(messages)