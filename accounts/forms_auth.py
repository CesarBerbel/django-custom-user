from __future__ import annotations
from django import forms
from django.contrib.auth.forms import AuthenticationForm

class EmailAuthenticationForm(AuthenticationForm):
    """
    Custom auth form with clearer error messages.
    Note: field names remain 'username' and 'password' (Django default),
    but 'username' represents the email for our custom user model.
    """
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                "Your account is inactive. Please contact support.",
                code="inactive",
            )

    def get_invalid_login_error(self):
        # Shown when credentials are invalid
        return forms.ValidationError(
            "We couldn't sign you in. Check your email and password and try again.",
            code="invalid_login",
        )
