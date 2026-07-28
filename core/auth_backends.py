from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class LowercaseUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username:
            username = username.lower()
        return super().authenticate(request, username=username, password=password, **kwargs)
