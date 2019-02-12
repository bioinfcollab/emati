from datetime import datetime, timedelta

from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress

import logging
logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = """Deletes users. The list of users can be specified explicitly
    via their primary keys (id), or implicitly by using one or multiple of 
    the command flags. The flags are connected with AND. By using more than
    one flag the set of users will be narrowed down to those that satisfy all 
    requirements. Admins and staff users will not be deleted. Running the
    command without any arguments is not supported and will print an error
    message. This is to avoid accidentally deleting all users.
    """


    def add_arguments(self, parser):
        parser.add_argument('user_ids', 
            type=int,
            nargs='*',
            help="""Delete the users in this list of primary keys (id). This 
            list is optional. Users in this list will only be deleted if they
            also satisfy all conditions specified by the supplied flags."""
        )
        parser.add_argument('-i', '--inactive', 
            type=int,
            nargs='?',
            const=365,
            dest="DAYS",
            help="""Deletes inactive users. You can specify the number of 
            days that must have passed since the user's last visit for them
            to be considered "inactive". Defaults to 365 days."""
        )
        parser.add_argument('-t', '--without-terms-consent', 
            action='store_true',
            dest="TERMS",
            help="""Deletes users who did not agree to our terms and 
            conditions."""
        )
        parser.add_argument('-e', '--without-verified-email', 
            action='store_true',
            dest="EMAIL",
            help="""Deletes users who have not a single verified email 
            connected to their account."""
        )


    def handle(self, *args, **options):
        """The main entry point for this command."""

        # Make sure that at least one option is set so that we don't 
        # accidentally delete all users
        if (not options['user_ids'] 
            and not options['DAYS']
            and not options['TERMS'] 
            and not options['EMAIL']):
            self.stderr.write("No users specified. Please set one or more flags "
                "to indicate which users you want to delete.")
            return

        # Begin with a list of all users. This is narrowed down later
        # because we are sure that at least one option is set.
        users = User.objects.all()

        # Collect reasons why users will be deleted (for pretty output)
        out = []

        # Users must have a specific ID
        if options['user_ids']:
            users = users.filter(pk__in=options['user_ids'])
            out.append("have a specific id ({})".format(
                ','.join(str(x) for x in options['user_ids'])
            ))

        # Users must be incative for a certain number of days
        if options['DAYS']:
            threshold_date = timezone.now() - timedelta(days=options['DAYS'])
            users = users.filter(profile__last_visit__lte=threshold_date)
            out.append("were last active before {}".format(
                datetime.strftime(threshold_date, '%Y-%m-%d')
            ))
        
        # Users that did not agree to our terms
        if options['TERMS']:
            users = users.filter(profile__terms_consent=False)
            out.append("did not agree to our terms")
        
        # Users that have only unverified email addresses
        if options['EMAIL']:
            # Users can have multiple email addresses so make sure to skip
            # those that have a verified and also unverified addresses.

            # Find users that have at least one verified email
            verified_users = EmailAddress.objects\
                .filter(verified=True)\
                .values_list('user', flat=True)

            # Now exclude those from our set
            users = users.exclude(pk__in=verified_users)
            out.append("have no verified email address")

        # Print the conditions a user must satisfy to be deleted
        if len(out) > 1:
            out[-1] = "and " + out[-1]
        logger.info("Deleting users who " + ', '.join(out) + " ...")

        # Now finally delete them
        for u in users:
            if u.is_superuser:
                logger.info("Skipping superuser {} ({})".format(u.pk, u.email))
                continue
            if u.is_staff:
                logger.info("Skipping staff user {} ({})".format(u.pk, u.email))
                continue

            logger.info("Deleting user {} ({})".format(u.pk, u.email))
            u.delete()
