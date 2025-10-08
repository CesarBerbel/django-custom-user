from __future__ import annotations
from django.contrib.auth import login
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView,
    LoginView, LogoutView
)
from .forms_password import CustomPasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm
from .mixins import AnonymousRequiredMixin
from django.views.generic import TemplateView, UpdateView
from django.contrib.auth.views import PasswordChangeView
from .forms import ProfileUpdateForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages


class RegisterView(AnonymousRequiredMixin, CreateView):
    """Allow a new user to register with email and password."""
    form_class = CustomUserCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")  # after successful registration, go to login

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Account created successfully. You can now sign in.")
        # Optionally auto-login after signup:
        # login(self.request, self.object)
        return response


class EmailLoginView(AnonymousRequiredMixin, LoginView):
    """Email-based login view (uses AuthenticationForm by default)."""
    template_name = "users/login.html"

    def form_valid(self, form):
        messages.success(self.request, "Welcome back!")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Add an error toast on invalid credentials
        messages.error(self.request, "Invalid credentials. Please try again.")
        return super().form_invalid(form)

class EmailLogoutView(LogoutView):
    next_page = reverse_lazy("users:login")

    def post(self, request, *args, **kwargs):
        messages.info(request, "You have been logged out.")
        return super().post(request, *args, **kwargs)

class ProfileView(LoginRequiredMixin, TemplateView):
    """Display current user's profile."""
    template_name = "users/profile.html"
    login_url = "users:login"

class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Allow user to update own profile fields."""
    form_class = ProfileUpdateForm
    template_name = "users/profile_edit.html"
    success_url = reverse_lazy("users:profile")
    login_url = "users:login"

    def get_object(self, queryset=None):
        # Always edit the logged-in user
        return self.request.user

    def form_valid(self, form):
        # Detect if email changed to show a specific toast
        old_email = self.request.user.email
        response = super().form_valid(form)
        new_email = self.request.user.email
        if new_email.lower() != (old_email or "").lower():
            messages.success(self.request, "Email updated successfully.")
        else:
            messages.success(self.request, "Profile updated successfully.")
        return response  

class ProfilePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Let the user change password."""
    template_name = "users/password_change.html"
    success_url = reverse_lazy("users:profile")
    login_url = "users:login"
    form_class = CustomPasswordChangeForm  # NEW

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        return super().form_valid(form)

class PasswordResetRequestView(PasswordResetView):
    """
    Ask user email to send a password reset link.
    """
    template_name = "users/password_reset.html"
    email_template_name = "users/password_reset_email.txt"
    subject_template_name = "users/password_reset_subject.txt"
    success_url = reverse_lazy("users:password_reset_done")
    from_email = None  # use DEFAULT_FROM_EMAIL
    # html_email_template_name = "users/password_reset_email.html"  # optional HTML version

    def form_valid(self, form):
        messages.info(self.request, "If an account with that email exists, a reset link was sent.")
        return super().form_valid(form)


class PasswordResetDoneCustomView(PasswordResetDoneView):
    """
    Confirmation page after email submit.
    """
    template_name = "users/password_reset_done.html"


class PasswordResetConfirmCustomView(PasswordResetConfirmView):
    """
    Page where user sets a new password using the emailed token.
    """
    template_name = "users/password_reset_confirm.html"
    success_url = reverse_lazy("users:password_reset_complete")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been set. You can sign in now.")
        return super().form_valid(form)


class PasswordResetCompleteCustomView(PasswordResetCompleteView):
    """
    Final 'success' page after password was changed.
    """
    template_name = "users/password_reset_complete.html"    