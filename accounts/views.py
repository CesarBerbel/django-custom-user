from __future__ import annotations
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm
from .mixins import AnonymousRequiredMixin
from django.views.generic import TemplateView, UpdateView
from django.contrib.auth.views import PasswordChangeView
from .forms import ProfileUpdateForm
from django.contrib.auth.mixins import LoginRequiredMixin


class RegisterView(AnonymousRequiredMixin, CreateView):
    """Allow a new user to register with email and password."""
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")  # after successful registration, go to login

    def form_valid(self, form):
        response = super().form_valid(form)
        # Optionally auto-login after signup:
        # login(self.request, self.object)
        return response


class EmailLoginView(AnonymousRequiredMixin, LoginView):
    """Email-based login view (uses AuthenticationForm by default)."""
    template_name = "accounts/login.html"


class EmailLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

class ProfileView(LoginRequiredMixin, TemplateView):
    """Display current user's profile."""
    template_name = "accounts/profile.html"
    login_url = "accounts:login"

class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Allow user to update own profile fields."""
    form_class = ProfileUpdateForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")
    login_url = "accounts:login"

    def get_object(self, queryset=None):
        # Always edit the logged-in user
        return self.request.user

class ProfilePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Let the user change password."""
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")
    login_url = "accounts:login"