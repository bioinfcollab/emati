from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.conf import settings

from website.models import UserUpload, Classifier, Recommendation, UserTextInput

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Deletes all data related to this user. '
        'This includes uploaded files, trained classifiers, '
        'clicks/likes/dislikes for any article. This does not '
        'delete any recommendations.'
    )


    def add_arguments(self, parser):
        parser.add_argument('user_ids', type=int, nargs='+', help="Specify which user(s) to reset")
        parser.add_argument('--only_classifier', action='store_true')


    def handle(self, *args, **options):
        """The main entrypoint for this command."""
        if not options['user_ids']:
            logger.info("No users specified. Exiting.")
            return

        for uid in options['user_ids']:
            try:
                user = User.objects.get(pk=uid)
            except User.DoesNotExist:
                logger.warning("Skipping ID {}. No user was found.".format(uid))
                continue
            if not(options['only_classifier']):
                logger.info("Resetting user {} ...".format(uid))
                logger.info("  Deleting uploads ...")
                self.delete_uploads(user)
                logger.info("  Deleting inputs ...")
                self.delete_inputs(user)
            logger.info("  Deleting classifier ...")
            self.delete_classifier(user)
            logger.info("  Deleting recommendations ...")
            self.delete_recommendations(user)


    def delete_uploads(self, user):
        """Deletes all files uploaded by this user."""
        uploads = UserUpload.objects.filter(user=user)
        uploads.delete()

    def delete_inputs(self, user):
        txtInputs= UserTextInput.objects.filter(user=user)
        txtInputs.delete()

    
    def delete_classifier(self, user):
        """Deletes all classifiers associated with this user."""
        user.classifier.delete()
        user.bert_classifier.delete()


    def reset_recommendations(self, user):
        """Reset metadata (likes/dislikes/clicks) on this 
        user's recommendations. Does not delete any recommendation."""

        # Get this user's recommendations
        all_recommendations = Recommendation.objects.filter(user=user)

        # Reduce query to only those where any value was modified
        modified_recommendations = (
            all_recommendations.filter(liked=True) 
            | all_recommendations.filter(disliked=True) 
            | all_recommendations.filter(clicked=True)
        )

        # Bulk update (single trip to the database):
        modified_recommendations.update(liked=False, disliked=False, clicked=False)

    
    def delete_recommendations(self, user):
        """Deletes all recommendations stored for this user."""
        Recommendation.objects.filter(user=user).delete()