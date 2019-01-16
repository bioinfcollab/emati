import os
import json
import datetime
import requests
import multiprocessing
from collections import defaultdict
from subprocess import Popen
from ipware import get_client_ip


from django import db
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, QueryDict
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.core import management
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.dispatch import receiver
from django.conf import settings
from allauth.account.forms import LoginForm
from allauth.account.views import PasswordResetView, PasswordChangeView
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed, user_signed_up


from .forms import MyLoginForm, SearchForm, SettingsForm, ChangeEmailForm
from .models import UserUpload, UserLog, Article, Recommendation, Classifier
from machinelearning.ranker import ArticleRanker
from . import search

import logging
logger = logging.getLogger(__name__)



class WelcomePageView(TemplateView):
    """The default page located at root url / 
    This is the first thing people see when visiting the website.
    """
    template_name = 'website/welcome.html'

    def get(self, request, *args, **kwargs):
        # Logged-in users shouldn't see the welcome screen
        if request.user.is_authenticated:
            return redirect('home')
        else:
            return super(WelcomePageView, self).get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['login_form'] = MyLoginForm()
        context['contact_email'] = settings.WEBSITE_CONTACT_EMAIL
        return context


class WeekBrowsingMixin():
    """Provides functionality for browsing content by weeks.

    Requires that weeks are specified via the GET parameter 'w'.
    Weeks must be given in the format '2018w32'.

    This class automatically adds the following values 
    to the context dictionary:
    week_nr:           ISO number of requested week from 1 to 52 (or 53)
    week_range_pretty: e.g. '13 - 20 Aug 2018'
    week_request_prev: The url for requesting the previous week
    week_request_next: The url for requesting the next week
    """

    def get_context_data(self, **kwargs):
        context = super(WeekBrowsingMixin, self).get_context_data(**kwargs)

        # Fall back to the last week if none was specified
        if self.request.GET.get('w') is None:
            d = datetime.date.today() - datetime.timedelta(weeks=1)
            self.year, self.week, _ = d.isocalendar()
        else:
            # Parses the parameter w=2018w32:
            self.year, self.week = self.request.GET.get('w').split('w')
            self.year = int(self.year)
            self.week = int(self.week)

        # Use the same GET parameters as before
        # but also add/replace another week parameter
        querydict_prev = self.request.GET.copy()
        querydict_prev['w'] = self._get_week(week_delta=-1)
        url_prev_week = '{}?{}'.format(self.request.path, querydict_prev.urlencode())

        querydict_next = self.request.GET.copy()
        querydict_next['w'] = self._get_week(week_delta=1)
        url_next_week = '{}?{}'.format(self.request.path, querydict_next.urlencode())

        context['week_nr'] = self.week
        context['week_range_pretty'] = self._get_week_range_pretty()
        context['week_request_prev'] = url_prev_week
        context['week_request_next'] = url_next_week

        return context


    def _get_week(self, week_delta=0):
        """
        """
        d = self.iso_to_gregorian(self.year, self.week, 1)
        d += datetime.timedelta(weeks=week_delta)
        year, week, _ = d.isocalendar()
        return '{}w{}'.format(year, week)


    def iso_to_gregorian(self, iso_year, iso_week, iso_day):
        """Gregorian calendar date for the given ISO year, week and weekday.
        Returns a datetime.date object.
        """
        fourth_jan = datetime.date(iso_year, 1, 4)
        _, fourth_jan_week, fourth_jan_day = fourth_jan.isocalendar()
        return fourth_jan + datetime.timedelta(days=iso_day-fourth_jan_day, weeks=iso_week-fourth_jan_week)
        

    def get_week_range(self):
        """Returns the currently requested week as a tuple of strings
        representing the first and last day (i.e. monday and sunday).
        E.g. ('2018-08-13', '2018-08-19')
        """
        d = self.iso_to_gregorian(self.year, self.week, 1)
        monday = d - datetime.timedelta(days=d.weekday())
        sunday = monday + datetime.timedelta(days=6)
        
        # Change into string representations (YYYY-MM-DD)
        monday = monday.strftime('%Y-%m-%d')
        sunday = sunday.strftime('%Y-%m-%d')

        return (monday, sunday)


    def _get_week_range_pretty(self):
        """Returns the requested week as a nicely formatted range.
        Depending on whether month/year borders are crossed, one of
        three formats are used:
        '29 Dec 2014 - 4 Jan 2015'
        '30 Jul - 5 Aug 2018'
        '13 - 19 Aug 2018'
        """
        monday, sunday = self.get_week_range()
        
        # Convert into actual date objects
        monday = datetime.datetime.strptime(monday, '%Y-%m-%d').date()
        sunday = datetime.datetime.strptime(sunday, '%Y-%m-%d').date()

        # Different styles depending on the dates
        if monday.year != sunday.year:
            # '29 Dec 2014 - 4 Jan 2015'
            style = '{mon.day} {mon:%b} {mon:%Y} - {sun.day} {sun:%b} {sun:%Y}'
        elif monday.month != sunday.month:
            # '30 Jul - 5 Aug 2018'
            style = '{mon.day} {mon:%b} - {sun.day} {sun:%b} {sun:%Y}'
        else:
            # '13 - 19 Aug 2018'
            style = '{mon.day} - {sun.day} {sun:%b} {sun:%Y}'
                    
        return style.format(mon=monday, sun=sunday)


class HomePageView(LoginRequiredMixin, WeekBrowsingMixin, TemplateView):
    """The main page for logged-in users. Displays the recommendations."""
    template_name = 'website/home.html'
    offset = 0

    def get_context_data(self, **kwargs):
        context = super(HomePageView, self).get_context_data(**kwargs)
        
        start = self.offset
        end = self.offset + settings.WEBSITE_PAGINATE_BY
        recommendations = Recommendation.objects\
            .filter(user=self.request.user)\
            .filter(article__pubdate__range=self.get_week_range())\
            .select_related('article')\
            [start:end]

        context['recommendations'] = recommendations
        context['search_form'] = SearchForm(self.request.GET)
        context['load_more_url'] = reverse('load_more_home')
        context['classifier_initialized'] = self.request.user.classifier.is_initialized()
        return context


class SearchView(LoginRequiredMixin, TemplateView):
    template_name = 'website/search.html'
    results_to_show = 50
    offset = 0

    def get(self, request, *args, **kwargs):
        """Returns a response to a GET request."""
        # Go to HomePageView if no search query was specified
        if not request.GET.get('q'):
            url = self._get_home_url(request)
            return redirect(url)
        else:
            # Search query is present -> Return the normal response
            return super(SearchView, self).get(request, *args, **kwargs)


    def _get_home_url(self, request):
        """Returns the equivalent home url (showing the same week)."""
        querydict = QueryDict(mutable=True)
        if request.GET.get('w'):
            querydict['w'] = request.GET.get('w')
        return reverse('home') + '?' + querydict.urlencode()


    def get_context_data(self, *args, **kwargs):
        context = super(SearchView, self).get_context_data(*args, **kwargs)
        query = self.request.GET.get('q')
        if not query:
            return context

        # Log this search event
        UserLog.objects.create_log(
            user=self.request.user,
            event=UserLog.Events.SEARCH,
            context={'query': query}
        )

        # Search for articles
        total_results, articles = search.fulltext_search(
            query, max_results=settings.WEBSITE_SEARCH_MAX_RESULTS
        )

        # Only work with initialized classifiers
        if self.request.user.classifier.is_initialized():
            ranker = ArticleRanker(self.request.user.classifier)
            articles_with_scores = ranker.rank_articles(articles)

            # Limit results to the best ones
            articles_with_scores = articles_with_scores[:self.results_to_show]

            recommendations = self._load_recommendations_from_search_results(
                articles = [a for (a,s) in articles_with_scores],
                scores = [s for (a,s) in articles_with_scores]
            )
        else:
            # Limit results to the best ones
            articles = articles[:self.results_to_show]
            recommendations = self._load_recommendations_from_search_results(
                articles
            )

        context['query'] = query
        context['total_results'] = total_results
        context['recommendations'] = recommendations
        context['search_form'] = SearchForm(self.request.GET)
        context['cancel_search_url'] = self._get_home_url(self.request)

        return context


    def _load_recommendations_from_search_results(self, articles, scores=[]):
        """Returns recommendations for articles found using the search.
        Its main purpose is to load metadata for existing recommendations.

        Args:
            articles: a list of articles as returned by the search engine.
                They are expected to have additional fields for
                highlights (`title_highlighted` and `abstract_highlighted`).
            scores: a list of floats where the i-th item represents the score
                for the i-th article. If ommitted, scores will default to
                0. If provided, the list must have exactly as many items
                as there are provided articles.
            
        Returns:
            a list of recommendations. Recommendations that were already
            present in the database have the correct values for metadata
            such as liked/disliked/clicked. All recommendations have a
            new additional field `article_highlighted`. The list is sorted
            with the first item having the highest score.
        """
        # Map article-id to article for faster lookup
        article_dict = {int(a.pk):a for a in articles}

        # Map article-id to score
        # This assumes that the i-th score corresponds to the i-th article
        score_dict = {int(a.pk):score for (a,score) in zip(articles,scores)}
        score_dict = defaultdict(float, score_dict)

        # Try to load metadata from the DB (liked/disliked/clicked)
        recommendations = get_recommendations_or_new(
            user=self.request.user,
            article_ids=article_dict.keys()
        )

        # Update with highlighted search results and new scores
        for r in recommendations:
            # Do not overwrite r.article with an unsaved article. This 
            # would make saving the recommendation impossible until the
            # article is saved to the DB first. Instead introduce a new
            # temporary field with our highlighted article which will never
            # be saved to the database:
            r.article_highlighted = article_dict[r.article.pk]
            r.score = max(r.score, score_dict[r.article.pk])

        # Sort such that highest score comes first
        recommendations = sorted(
            recommendations, 
            key=lambda r: r.score, 
            reverse=True
        )

        # Do not save them yet. This would lead to many new 
        # recommendations for every new search.

        return recommendations


class LoadMoreMixin():
    """Inherit from this to add the 'Load more' functionality.

    Your base class must already specify an 'offset' that indicates
    from which index to start displaying content. This mixin only
    validates the request arguments and sets the offset.
    """
    def get(self, request, *args, **kwargs):
        try:
            self.offset = int(request.GET.get('offset', 0))
            return super().get(request, *args, **kwargs)
        except ValueError:
            # offset was not an integer
            return HttpResponse('Bad Request: the "offset" argument is not an integer.', status=400)
    
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['hide_empty_message'] = True
        return context


class LoadMoreHome(LoadMoreMixin, HomePageView):
    """The Ajax endpoint for requesting more content from the main page.
    
    Displays the same data as the HomePageView but renders it directly
    to the HTML snippet without any headers or CSS. The returned block
    can then be inserted in the page via Javascript.
    """
    template_name = 'website/snippets/recommendations.html'


class TermsAndConditionsView(TemplateView):
    template_name = 'website/termsandconditions.html'


class TermsAgreementView(LoginRequiredMixin, TemplateView):
    template_name = 'website/terms_agreement.html'

    def get(self, request, *args, **kwargs):
        # Do not show this page if the user has already agreed to our terms
        if request.user.profile.terms_consent:
            return redirect('home')
        else:
            # Do the usual rendering
            return super(TermsAgreementView, self).get(self, request, *args, **kwargs)
    

    def post(self, request, *args, **kwargs):
        """Handles the form that was submitted when clicking on 'Continue' on
        the terms and conditions page. This form contains only one single checkbox.
        """
        # In theory the form could only have been submitted if the checkbox
        # was checked. But let's not trust the frontend too much. Better
        # double check.
        checked = request.POST.get('consent')
        if checked:
            # Save consent to database and redirect to main page
            request.user.profile.terms_consent = True
            request.user.profile.save()
            return redirect('home')
        else:
            # This shouldn't happen but just in case something goes wrong
            # Reload the same page
            return redirect('terms_agree')


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'website/settings.html'

    def get_context_data(self, *args, **kwargs):
        context = super(SettingsView, self).get_context_data(*args, **kwargs)
        context['search_form'] = SearchForm(self.request.GET)
        context['uploaded_files'] = UserUpload.objects.filter(user=self.request.user)

        # Create a form and prepopulate it with the user's settings
        up = self.request.user.profile
        form = SettingsForm({'newsletter': up.newsletter})
        context['settings_form'] = form

        return context


    def update_content(self, userid):
        """Meant to run in the background as a separate process. 
        Called after a file was uploaded/deleted. Retrains the 
        classifier and creates some recommendations."""
        management.call_command('train_classifiers', userid)
        management.call_command('create_recommendations', '--last-week', user_ids=[userid])


    def post(self, request, *args, **kwargs):
        """Handles saving the user's settings."""
        new_files = request.FILES.getlist('newfile')
        remove_files = request.POST.getlist('removefile')

        files_changed = False
        encountered_error = False

        for f in remove_files:
            try:
                upload = UserUpload.objects.get(user=request.user, file=f)
                upload.delete()
                files_changed = True
            except UserUpload.DoesNotExist:
                messages.error(request, 'Could not delete "{}". File not found.'.format(f))
                encountered_error = True

        for f in new_files:
            if not self.has_valid_filesize(f):
                messages.warning(request, 'Could not upload "{}". File is too large. Maximum file size is {} KB'.format(f.name, settings.WEBSITE_UPLOAD_MAX_FILESIZE/2**10))
                encountered_error = True
                continue
            if not self.has_allowed_filetype(f):
                messages.warning(request, 'Could not upload "{}". Unsupported filetype.'.format(f.name))
                encountered_error = True
                continue
            if self.has_user_reached_upload_limit(request.user):
                messages.warning(request, 'Could not upload "{}". You have reached your upload limit.'.format(f.name))
                encountered_error = True
                continue
            upload = UserUpload(user=request.user, file=f)
            upload.save()
            files_changed = True
        
        # Retrain classifier if files were added or deleted
        if files_changed:

            # Close our database connection so that each process can generate
            # a custom connection. Sharing one connection is not allowed.
            db.connections.close_all()

            # Start a subprocess and create some recommendations based on the
            # new training data that we now have.
            multiprocessing.Process(
                target=self.update_content, 
                args=[request.user.pk]
            ).start()

            messages.info(request, "Your recommendations are being updated. This might take a minute.")

        # Save all other settings
        settings_form = SettingsForm(request.POST)
        if settings_form.is_valid():
            profile = request.user.profile
            profile.newsletter = settings_form.cleaned_data['newsletter']
            profile.save()
        else:
            encountered_error = True
        
        if not encountered_error:
            messages.success(request, "Successfully saved settings.")

        # Render the page as usual
        return self.get(request, *args, **kwargs)

    
    def has_allowed_filetype(self, file):
        """Checks if a given file is in the list of allowed filetypes."""
        for t in settings.WEBSITE_UPLOAD_VALID_FILETYPES:
            if file.name.endswith(t):
                return True
        return False

    def has_valid_filesize(self, file):
        """Checks if a file is within the allowed maximum filesize."""
        return file.size <= settings.WEBSITE_UPLOAD_MAX_FILESIZE

    def has_user_reached_upload_limit(self, user):
        """Check if a user has uploaded the maximum amount of files."""
        return user.uploads.count() >= settings.WEBSITE_UPLOAD_MAX_FILES


@login_required
@require_GET
def get_uploaded_file_html(request):
    """Renders the HTML representation of one uploaded file."""
    context = {
        'filesize': request.GET['filesize'],
        'filename': request.GET['filename']
    }
    return render(request, 'website/snippets/upload_new.html', context=context)


class AboutView(TemplateView):
    template_name = 'website/about.html'

    def get_context_data(self, *args, **kwargs):
        context = super(AboutView, self).get_context_data(*args, **kwargs)
        context['contact_email'] = settings.WEBSITE_CONTACT_EMAIL
        context['search_form'] = SearchForm(self.request.GET)

        return context


class ChangeEmailView(LoginRequiredMixin, TemplateView):
    template_name = 'website/change_email.html'

    def get_context_data(self, **kwargs):
        context = super(ChangeEmailView, self).get_context_data(**kwargs)
        context['email_form'] = ChangeEmailForm()
        return context


    def post(self, request, *args, **kwargs):
        form = ChangeEmailForm(request.POST)
        if form.is_valid():

            # Check password
            password_is_valid = request.user.check_password(form.cleaned_data['password'])
            if not password_is_valid:
                messages.warning(request, "Wrong password, try again.")
                return self.get(request, *args, **kwargs)

            # Delete any previous attempt at changing the email
            # address that remained unverified.
            EmailAddress.objects.filter(user=request.user, primary=False).delete()

            # Change email
            new_email_address, _ = EmailAddress.objects.get_or_create(
                user=request.user, 
                email=form.cleaned_data['new_email']
            )
            new_email_address.send_confirmation(request)
            messages.success(request, "We have sent a confirmation email to {}. Please verify that it belongs to you. Only then will your old address be replaced.".format(new_email_address.email))
            return redirect('settings')
        else:
            return self.get(request, *args, **kwargs)


@receiver(email_confirmed)
def change_email(request, email_address, **kwargs):
    """Sets the most recently confirmed email address as primary
    and deletes all other addresses.
    This is called every time a new address was confirmed.
    """
    try:       
        # Get the user associated with this email
        user = email_address.user

        # Set this user's email
        user.email = email_address.email
        user.save()

        # Set this email address to be primary
        email_address.primary = True
        email_address.save()

        # Delete all other addresses
        EmailAddress.objects.filter(user=user).exclude(pk=email_address.pk).delete()

    except User.DoesNotExist:
        # This shouldn't happen
        pass


class MyPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Redirect to settings view after successfully changing the password."""
    @property
    def success_url(self):
        return reverse('settings')


class DeleteAccountView(LoginRequiredMixin, TemplateView):
    template_name = 'website/account_delete.html'

    def post(self, request, *args, **kwargs):
        """Deletes a user."""
        try:
            request.user.delete()
            messages.success(request, 'You successfully deleted your account.')
        except User.DoesNotExist:
            messages.error(request, 'Could not delete "{}". User does not exist'.format(request.user))
            return redirect('settings')
        return redirect('account_logout')
        


class ResetAccountView(LoginRequiredMixin, TemplateView):
    template_name = 'website/account_reset.html'

    def post(self, request, *args, **kwargs):
        """Reset a user account. Calls the appropriate management command."""
        management.call_command('reset_account', request.user.pk)
        messages.info(request, "Successfully reset your account data.")
        return redirect('settings')


def social_signup_view(request):
    """Override allauth's url 'account/social/signup' with this view."""
    # Django-allauth does a stupid thing where if you register via
    # email/password and after that try to login with a social account
    # (google/facebook) that is connected to the same email, allauth detects
    # that and redirects you to a confirmation page. However the only thing
    # that page tells you is "There already is a user with this address". So
    # we replace it with a simple error message.
    messages.error(request, "There already is a user with this Email-Address. Please log in with Email and Password.")
    return redirect('account_login')


def account_inactive(request):
    messages.warning(request, "This account is inactive. Please contact an administrator to reactivate it.")
    return redirect('account_login')


@login_required
@require_GET
def download_file(request):
    file = request.GET.get('file')

    # Was a filename provided?
    if not file:
        return HttpResponse(status=404)
        
    # Extract filename
    fname = os.path.basename(file)

    # Does the file actually exist?
    try:
        upload = UserUpload.objects.get(
            user=request.user, 
            file=file
        )
    except UserUpload.DoesNotExist:
        return HttpResponse(status=404)

    # We have a file, so let's serve it to the user
    response = HttpResponse(upload.file)
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(fname)
    return response


def get_recommendation_or_new(user, article_id):
    """Returns the recommendation for this combination of user and article.
    If there is none then a new one will be created with a default score.
    The returned recommendation is not yet saved to the database. You have
    to call `save()` manually if that is what you desire.
    If you need to call this function multiple times in a row use the batch 
    version instead (`get_recommendations_or_new()`).
    """
    try:
        r = Recommendation.objects.get(user=user, article=article_id)
    except Recommendation.DoesNotExist:
        article = Article.objects.get(pk=article_id)
        r = Recommendation(user=user, article=article)
        # Score doesn't really matter here. The article was obiously not good
        # enough to appear in the weekly recommendations or else there would
        # already be a recommendation. And when searching for this article the
        # score is calculated on the fly anyway.
        r.score = 0
    return r


def get_recommendations_or_new(user, article_ids):
    """Batch processing version of `get_recommendation_or_new()`.
    Does only a single trip to the database for all specified articles.
    The returned recommendation is not yet saved to the database. You have
    to call `save()` manually if that is what you desire.
    """
    recommendations = Recommendation.objects.filter(
        user=user, 
        article__pk__in=article_ids
    ).select_related('article')

    # Execute the query (first trip to database)
    recommendations = list(recommendations)

    # All article ids where a recommendation was found
    article_ids_with_rec = [r.article.pk for r in recommendations]

    # Article ids where NO recommendation was found
    article_ids_without_rec = [a_id for a_id in article_ids if a_id not in article_ids_with_rec]

    # The actual articles where no recommendation was found
    # (second trip to database)
    articles = Article.objects.filter(pk__in=article_ids_without_rec)

    # Create new recommendations for articles that were not found
    # (But don't save them yet)
    for a in articles:
        r = Recommendation(user=user, article=a)
        r.score = 0
        recommendations.append(r)

    return recommendations



@csrf_exempt
@login_required
@require_POST
def log_click(request, article_pk):
    """Stores a user's click on an article.
    Called via the 'ping' argument on a link (sends a POST request).
    """
    r = get_recommendation_or_new(request.user, article_pk)
    r.clicked = True
    r.save()

    UserLog.objects.create_log(
        user=request.user, 
        event=UserLog.Events.CLICK, 
        context={"article_id": article_pk}
    )

    request.user.profile.recent_interactions += 1
    request.user.profile.save()

    return HttpResponse(status=204)


@login_required
@require_POST
def log_like(request, article_pk):
    """Stores a user's click on a like-button. 
    Toggles the `liked` state of the respective article. 
    Called via ajax.
    """
    r = get_recommendation_or_new(request.user, article_pk)
    r.liked = not r.liked
    r.disliked = False
    r.save()

    UserLog.objects.create_log(
        user=request.user, 
        event=UserLog.Events.LIKE, 
        context={"article_id": article_pk}
    )

    request.user.profile.recent_interactions += 1
    request.user.profile.save()

    return HttpResponse(status=204)


@login_required
@require_POST
def log_dislike(request, article_pk):
    """Stores a user's click on a dislike-button. 
    Toggles the `disliked` state of the respective article. 
    Called via ajax.
    """
    r = get_recommendation_or_new(request.user, article_pk)
    r.liked = False
    r.disliked = not r.disliked
    r.save()

    UserLog.objects.create_log(
        user=request.user, 
        event=UserLog.Events.DISLIKE, 
        context={"article_id": article_pk}
    )

    request.user.profile.recent_interactions += 1
    request.user.profile.save()

    return HttpResponse(status=204)


@receiver(user_signed_up)
def log_registration(request, user, **kwargs):
    # Get client ip
    client_ip, is_routable = get_client_ip(request)

    # Get location for this ip
    lat = lon = None
    if client_ip is not None and is_routable:
        url = 'http://ip-api.com/json/' + client_ip
        r = requests.get(url)
        if r.status_code == 200:
            response_content = json.loads(r.text)
            if response_content['status'] == 'success':
                if 'lat' in response_content and 'lon' in response_content:
                    lat = response_content['lat']
                    lon = response_content['lon']
            
    # Create a log event
    UserLog.objects.create_log(
        user, 
        UserLog.Events.REGISTRATION, 
        {'lat': lat, 'lon': lon}
    )

    logger.info("A new user signed up.")