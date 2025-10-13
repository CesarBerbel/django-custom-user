# appointments/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from .models import GoogleCredentials
from .services import get_upcoming_events

# Mock data to simulate responses from Google's API
MOCK_CALENDAR_RESPONSE = {
    'items': [
        {
            'summary': 'Team Meeting',
            'start': {'dateTime': '2025-10-15T10:00:00-03:00'}
        }
    ]
}

MOCK_TASKS_RESPONSE = {
    'items': [
        {
            'title': 'Submit Report',
            'due': '2025-10-16T23:59:59.000Z'
        }
    ]
}

class GoogleApiViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="gapi@test.com", password="pw")
        self.client.force_login(self.user)

    def test_connect_view_redirects_to_google(self):
        url = reverse("appointments:connect")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com/o/oauth2/auth", response.url)

    def test_disconnect_view_deletes_credentials(self):
        GoogleCredentials.objects.create(
            user=self.user,
            access_token="test_token",
            refresh_token="test_refresh"
        )
        self.assertTrue(GoogleCredentials.objects.filter(user=self.user).exists())
        
        url = reverse("appointments:disconnect")
        self.client.post(url, follow=True)
        
        self.assertFalse(GoogleCredentials.objects.filter(user=self.user).exists())


class GoogleApiServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="service@test.com", password="pw")
        # Create credentials so the service can find them
        GoogleCredentials.objects.create(
            user=self.user,
            access_token="test_token",
            refresh_token="test_refresh",
            scopes="scope1 scope2"
        )

    # The @patch decorator intercepts calls to googleapiclient.discovery.build
    # and replaces it with a mock object.
    @patch('appointments.services.build')
    def test_get_upcoming_events_with_mock_data(self, mock_build):
        """
        Tests if the service function correctly parses mocked API responses.
        """
        # We need to configure the mock to behave like the Google API client library
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Configure the Calendar API mock
        mock_service.events.return_value.list.return_value.execute.return_value = MOCK_CALENDAR_RESPONSE
        
        # Configure the Tasks API mock
        mock_service.tasks.return_value.list.return_value.execute.return_value = MOCK_TASKS_RESPONSE
        
        # Call the actual function we want to test
        result = get_upcoming_events(self.user)

        # Assertions to verify our service processed the mock data correctly
        self.assertIsNotNone(result)
        self.assertIn('events', result)
        self.assertIn('tasks', result)
        
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['events'][0]['title'], 'Team Meeting')
        
        self.assertEqual(len(result['tasks']), 1)
        self.assertEqual(result['tasks'][0]['title'], 'Submit Report')

        # Verify that the build function was called for both 'calendar' and 'tasks'
        self.assertEqual(mock_build.call_count, 2)