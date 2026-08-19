"""Unit tests for shared.access_decorators."""
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from shared import access_decorators


def _attach_messages(request):
    """Attach a session and message storage to a RequestFactory request."""
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _sample_view(request):
    """Return a trivial OK response for the decorated view."""
    return HttpResponse("ok")


class RequireModuleAccessTests(TestCase):
    """Tests for the single-module access decorator."""

    def setUp(self):
        """Create a request factory and a regular user."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u", password="x")

    def test_anonymous_redirected_to_login(self):
        """Anonymous users are redirected to the login view."""
        request = self.factory.get("/x/")
        request.user = AnonymousUser()
        with mock.patch.object(access_decorators, "redirect") as redirect:
            redirect.return_value = HttpResponse(status=302)
            access_decorators.require_module_access(_sample_view)(request)
        redirect.assert_called_once_with("login")

    def test_grants_access_when_user_has_module(self):
        """A user with module access reaches the wrapped view."""
        request = self.factory.get("/x/")
        request.user = self.user
        with mock.patch.object(
            access_decorators, "has_module_access", return_value=True
        ):
            response = access_decorators.require_module_access(_sample_view)(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_denies_access_without_module(self):
        """A user without module access is redirected to access_denied."""
        request = _attach_messages(self.factory.get("/x/"))
        request.user = self.user
        with mock.patch.object(
            access_decorators, "has_module_access", return_value=False
        ), mock.patch.object(access_decorators, "redirect") as redirect:
            redirect.return_value = HttpResponse(status=302)
            access_decorators.require_module_access(_sample_view)(request)
        self.assertEqual(redirect.call_args.args[0], "access_denied")


class RequireModulesAccessTests(TestCase):
    """Tests for the multi-module access decorator."""

    def setUp(self):
        """Create a request factory and a regular user."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u2", password="x")

    def test_anonymous_redirected_to_login(self):
        """Anonymous users are redirected to the login view."""
        request = self.factory.get("/x/")
        request.user = AnonymousUser()
        with mock.patch.object(access_decorators, "redirect") as redirect:
            redirect.return_value = HttpResponse(status=302)
            access_decorators.require_modules_access("metrologia", "rh")(_sample_view)(
                request
            )
        redirect.assert_called_once_with("login")

    def test_grants_when_any_module_allowed(self):
        """Access to any one of the modules is enough to pass."""
        request = self.factory.get("/x/")
        request.user = self.user
        with mock.patch.object(
            access_decorators, "has_module_access", side_effect=[False, True]
        ):
            response = access_decorators.require_modules_access("metrologia", "rh")(
                _sample_view
            )(request)
        self.assertEqual(response.status_code, 200)

    def test_denies_when_no_module_allowed(self):
        """Denied access to all modules redirects to access_denied."""
        request = _attach_messages(self.factory.get("/x/"))
        request.user = self.user
        with mock.patch.object(
            access_decorators, "has_module_access", return_value=False
        ), mock.patch.object(access_decorators, "redirect") as redirect:
            redirect.return_value = HttpResponse(status=302)
            access_decorators.require_modules_access("metrologia", "rh")(_sample_view)(
                request
            )
        self.assertEqual(redirect.call_args.args[0], "access_denied")
