from __future__ import annotations
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm
from .mixins import AnonymousRequiredMixin


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
