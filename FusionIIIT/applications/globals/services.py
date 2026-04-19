from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .models import ExtraInfo


def get_user_by_username(username):
    return get_object_or_404(get_user_model(), username=username)


def get_extra_info_by_user(user):
    return get_object_or_404(ExtraInfo, user=user)
