import json
import datetime
from collections import defaultdict

from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from allauth.socialaccount.models import SocialAccount

from website.models import Article, Recommendation, UserLog, UserUpload
from dashboard.models import WeekStat

import logging
logger = logging.getLogger(__name__)


class MainView(LoginRequiredMixin, TemplateView):
    template_name = 'main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['num_users'] = User.objects.all().count()
        context['num_articles'] = Article.objects.all().count()
        context['num_recommendations'] = Recommendation.objects.all().count()
        context['num_uploads'] = UserUpload.objects.all().count()
        context['project_repository'] = settings.DASHBOARD_PROJECT_REPOSITORY

        return context


@login_required
@staff_member_required
def ajax_load_stats(request):
    labels = []
    data = defaultdict(list)
    for s in WeekStat.objects.all().order_by('timestamp'):
        label = datetime.datetime.strftime(s.timestamp, '%Y-%m-%d')
        labels.append(label)
        data['num_registered_users'].append(s.num_registered_users)
        data['num_verified_users'].append(s.num_verified_users)
        data['num_active_users'].append(s.num_active_users)
        data['num_returning_users'].append(s.num_returning_users)
        data['num_search_requests'].append(s.num_search_requests)
        data['num_users_searched'].append(s.num_users_searched)
        data['num_likes'].append(s.num_likes)
        data['num_dislikes'].append(s.num_dislikes)
        data['num_clicks'].append(s.num_clicks)
        data['num_articles_only_clicked'].append(s.num_articles_only_clicked)
        data['num_articles_clicked_liked'].append(s.num_articles_clicked_liked)
        data['num_articles_clicked_disliked'].append(s.num_articles_clicked_disliked)
        data['num_articles'].append(s.num_articles)
        data['num_recommendations'].append(s.num_recommendations)

    out = dict()
    out['statistics'] = {
        'labels': labels,
        'data': data,
    }
    out['current'] = {
        'num_users': User.objects.all().count(),
        'num_articles': Article.objects.all().count(),
        'num_recommendations': Recommendation.objects.all().count(),
        'num_uploads': UserUpload.objects.all().count(),
        'user_locations': get_user_locations(),
        'signup_distribution': get_signup_distribution(),
    }

    return JsonResponse(out)


def get_user_locations():
    """Returns a list of user locations. Each item is a tuple consisting of 
    latitude and longitude."""
    out = []
    context_strings = UserLog.objects\
        .filter(event=UserLog.Events.REGISTRATION)\
        .values_list('context_json_string', flat=True)
    for context_string in context_strings:
        c = json.loads(context_string)
        if 'lat' in c and 'lon' in c:
            if c['lat'] is not None and c['lon'] is not None:
                out.append((c['lat'], c['lon']))
    return out


def get_signup_distribution():
    google = SocialAccount.objects.filter(provider='google').count()
    facebook = SocialAccount.objects.filter(provider='facebook').count()
    other = User.objects.all().count() - google - facebook
    return {
        'google': google,
        'facebook': facebook,
        'other': other
    }
