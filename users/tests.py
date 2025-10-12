#
# Arquivo: users/tests.py
#
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model, SESSION_KEY

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user(self):
        """Test creating a regular user with the custom manager."""
        user = User.objects.create_user(email="normal@user.com", password="foo")
        self.assertEqual(user.email, "normal@user.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("foo"))

    def test_email_is_normalized_on_save(self):
        """Test that the User model's save method normalizes the email."""
        email = "Test.EMAIL@Example.COM"
        user = User(email=email, password="foo")
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, email.lower())

    def test_create_superuser(self):
        """Test creating a superuser with the custom manager."""
        admin_user = User.objects.create_superuser(email="super@user.com", password="foo")
        self.assertEqual(admin_user.email, "super@user.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.check_password("foo"))

    def test_create_user_without_email_raises_error(self):
        """Test that creating a user without an email raises a ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="foo")


class RegistrationViewTests(TestCase):
    def setUp(self):
        self.url = reverse("users:register")

    def test_registration_page_status_code(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_registration_creates_new_user(self):
        response = self.client.post(self.url, {
            "email": "newuser@example.com",
            "password1": "StrongPass123",
            "password2": "StrongPass123",
        }, follow=True)

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.first().email, "newuser@example.com")
        self.assertRedirects(response, reverse("users:login"))
        self.assertContains(response, "Account created successfully")

    def test_registration_with_existing_email(self):
        User.objects.create_user(email="exists@example.com", password="pw")
        response = self.client.post(self.url, {
            "email": "exists@example.com",
            "password1": "anypass",
            "password2": "anypass",
        })

        self.assertEqual(User.objects.count(), 1)
        self.assertContains(response, "This email is already in use.")

    def test_authenticated_user_is_redirected_from_register(self):
        user = User.objects.create_user(email="test@user.com", password="pw")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:home"))


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@user.com", password="password123")
        self.login_url = reverse("users:login")
        self.logout_url = reverse("users:logout")

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_user_can_login(self):
        response = self.client.post(self.login_url, {
            "username": "test@user.com",  # AuthenticationForm uses 'username'
            "password": "password123"
        }, follow=True)
        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertContains(response, "Welcome back!")

    def test_user_cannot_login_with_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            "username": "test@user.com",
            "password": "wrongpassword"
        })
        self.assertFalse(SESSION_KEY in self.client.session)
        self.assertContains(response, "Invalid credentials")

    def test_user_can_logout(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url, follow=True)
        self.assertFalse(SESSION_KEY in self.client.session)
        self.assertRedirects(response, self.login_url)
        self.assertContains(response, "You have been logged out")

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse("core:home"))


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="profile@test.com", password="pw")
        self.profile_url = reverse("users:profile")
        self.edit_url = reverse("users:profile_edit")
        self.password_url = reverse("users:password_change")

    def test_profile_views_require_login(self):
        self.assertRedirects(self.client.get(self.profile_url), f"{reverse('users:login')}?next={self.profile_url}")
        self.assertRedirects(self.client.get(self.edit_url), f"{reverse('users:login')}?next={self.edit_url}")
        self.assertRedirects(self.client.get(self.password_url), f"{reverse('users:login')}?next={self.password_url}")

    def test_profile_view_displays_user_info(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.email)

    def test_profile_edit_updates_user_data(self):
        self.client.force_login(self.user)
        response = self.client.post(self.edit_url, {
            "first_name": "Test",
            "last_name": "User",
            "email": "profile@test.com", # email remains the same
        }, follow=True)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertRedirects(response, self.profile_url)
        self.assertContains(response, "Profile updated successfully")

    def test_password_change_works(self):
        self.client.force_login(self.user)
        response = self.client.post(self.password_url, {
            "old_password": "pw",
            "new_password1": "new_password_123",
            "new_password2": "new_password_123",
        }, follow=True)

        self.assertRedirects(response, self.profile_url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new_password_123"))
        self.assertContains(response, "Password changed successfully")

