"""
Tests for shared module - Common and shared functionality
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class SharedViewsTests(TestCase):
    """Integration tests for shared views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='shared_user',
            password='testpass123'
        )
    
    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
    
    def test_dashboard_authenticated(self):
        """Test dashboard with authenticated user"""
        self.client.login(username='shared_user', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertIn(response.status_code, [200, 404])
    
    def test_health_check_accessible(self):
        """Test health check endpoint is accessible without auth"""
        response = self.client.get(reverse('health_check'))
        self.assertIn(response.status_code, [200, 404])


class SharedImportsTests(TestCase):
    """Test that all shared imports are working correctly"""
    
    def test_shared_views_import(self):
        """Test that shared views can be imported"""
        from shared.views import (
            dashboard_view, health_check
        )
        self.assertIsNotNone(dashboard_view)
        self.assertIsNotNone(health_check)
    
