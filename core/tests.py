from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

class HomeViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="pass12345")
        self.client.force_login(self.user)    

    def test_home_status_code(self):
        """Home page should return HTTP 200."""
        url = reverse("core:home")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_home_contains_message(self):
        """Home page should contain the expected message text."""
        url = reverse("core:home")
        resp = self.client.get(url)
        self.assertContains(resp, "It works!")
