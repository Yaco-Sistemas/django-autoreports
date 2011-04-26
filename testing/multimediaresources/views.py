# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import HttpResponseRedirect


def index(request):
    admins = User.objects.filter(is_superuser=True)
    if admins:
        user = admins[0]
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        login(request, user)
    return HttpResponseRedirect('/admin/multimediaresources/resource/')
