"""Unit tests for helper functions in shared.permissions."""
from django.contrib.auth.models import User
from django.test import TestCase

from shared.permissions import get_module_key, has_module_access


class GetModuleKeyTests(TestCase):
    """Tests for get_module_key."""

    def test_extracts_first_segment(self):
        """The module key is the first dotted segment of the path."""
        self.assertEqual(get_module_key("metrologia.views.novo_fluxo"), "metrologia")

    def test_returns_value_when_no_dot(self):
        """A path without a dot is returned unchanged."""
        self.assertEqual(get_module_key("rh"), "rh")


class HasModuleAccessTests(TestCase):
    """Tests for has_module_access."""

    def test_superuser_has_access(self):
        """Superusers always have module access."""
        user = User.objects.create_superuser(username="root", password="x", email="")
        self.assertTrue(has_module_access(user, "metrologia"))

    def test_staff_has_access(self):
        """Staff users always have module access."""
        user = User.objects.create_user(username="staff", password="x", is_staff=True)
        self.assertTrue(has_module_access(user, "qms"))

    def test_regular_user_without_groups_denied(self):
        """A regular user without groups is denied access."""
        user = User.objects.create_user(username="plain", password="x")
        self.assertFalse(has_module_access(user, "metrologia"))
